import * as vscode from "vscode";
import * as path from "path";
import * as cp from "child_process";
import * as fs from "fs";

// Embedded python base64 constants (filled by build script)
const BASE64_RUNNER = "PLACEHOLDER_BASE64_RUNNER";
const BASE64_AGENT = "PLACEHOLDER_BASE64_AGENT";
const BASE64_DEMO = "PLACEHOLDER_BASE64_DEMO";

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
let panel: vscode.WebviewPanel | undefined;
let activeProcess: cp.ChildProcess | undefined;

// ─────────────────────────────────────────────────────────────────────────────
// Activate
// ─────────────────────────────────────────────────────────────────────────────
export function activate(context: vscode.ExtensionContext) {
  // Register "Run with ARC Lens" command
  context.subscriptions.push(
    vscode.commands.registerCommand("arc-lens.run", () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || !editor.document.fileName.endsWith(".py")) {
        vscode.window.showErrorMessage(
          "ARC Lens: Open a Python (.py) training script first."
        );
        return;
      }

      // Save the file before running
      editor.document.save().then(() => {
        launchAgent(editor.document.fileName, context);
      });
    })
  );

  // Register "Stop" command
  context.subscriptions.push(
    vscode.commands.registerCommand("arc-lens.stop", () => {
      if (activeProcess) {
        activeProcess.kill("SIGTERM");
        activeProcess = undefined;
        sendToPanel({ type: "status", status: "stopped", message: "Training stopped by user." });
      }
    })
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Launch Agent
// ─────────────────────────────────────────────────────────────────────────────
function ensureArcTrainingInstalled(pythonPath: string): Promise<boolean> {
  return new Promise((resolve) => {
    cp.exec(`"${pythonPath}" -c "import arc"`, (err) => {
      if (!err) {
        resolve(true);
        return;
      }

      vscode.window
        .showWarningMessage(
          "The Python package 'arc-training' is not installed in the selected environment. ARC Lens needs it to apply automatic self-healing interventions.",
          "Install via pip",
          "Run in Monitor-Only Mode"
        )
        .then((selection) => {
          if (selection === "Install via pip") {
            vscode.window.withProgress(
              {
                location: vscode.ProgressLocation.Notification,
                title: "Installing arc-training...",
                cancellable: false,
              },
              (progress) => {
                return new Promise<void>((resolveInstall, rejectInstall) => {
                  cp.exec(`"${pythonPath}" -m pip install arc-training`, (installErr, stdout, stderr) => {
                    if (installErr) {
                      vscode.window.showErrorMessage(
                        `Failed to install arc-training: ${stderr || installErr.message}`
                      );
                      rejectInstall(installErr);
                    } else {
                      vscode.window.showInformationMessage(
                        "arc-training installed successfully!"
                      );
                      resolveInstall();
                    }
                  });
                });
              }
            ).then(
              () => resolve(true),
              () => resolve(false)
            );
          } else if (selection === "Run in Monitor-Only Mode") {
            resolve(true);
          } else {
            resolve(false);
          }
        });
    });
  });
}

async function launchAgent(targetFile: string, context: vscode.ExtensionContext) {
  // Resolve config first
  const config = vscode.workspace.getConfiguration("arcAgent");
  const pythonPath: string = config.get("pythonPath") || "python";

  // Check and install arc-training if missing
  const shouldProceed = await ensureArcTrainingInstalled(pythonPath);
  if (!shouldProceed) {
    return;
  }

  // Kill any existing run
  if (activeProcess) {
    activeProcess.kill("SIGTERM");
    activeProcess = undefined;
  }

  // Create or reveal the dashboard panel
  if (!panel) {
    panel = vscode.window.createWebviewPanel(
      "arcAgentDashboard",
      "ARC Lens - Training Dashboard",
      vscode.ViewColumn.Beside,
      {
        enableScripts: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(context.extensionPath, "media")),
        ],
        retainContextWhenHidden: true,
      }
    );

    panel.iconPath = {
      light: vscode.Uri.file(path.join(context.extensionPath, "media", "logo_dark.png")),
      dark: vscode.Uri.file(path.join(context.extensionPath, "media", "logo_light.png")),
    };

    // Load the dashboard HTML
    panel.webview.html = getDashboardHtml(context, panel.webview);

    // Handle panel disposal
    panel.onDidDispose(() => {
      panel = undefined;
      if (activeProcess) {
        activeProcess.kill("SIGTERM");
        activeProcess = undefined;
      }
    });

    // Handle messages FROM the webview (e.g., user clicks Stop inside the panel)
    panel.webview.onDidReceiveMessage(async (msg) => {
      if (msg.command === "stop") {
        vscode.commands.executeCommand("arc-lens.stop");
      } else if (msg.command === "download") {
        try {
          if (!msg.dataUrl || !msg.dataUrl.includes(',')) {
            throw new Error("Invalid image data received.");
          }
          const workspaceFolders = vscode.workspace.workspaceFolders;
          let defaultUri: vscode.Uri;
          if (workspaceFolders && workspaceFolders.length > 0) {
            defaultUri = vscode.Uri.joinPath(workspaceFolders[0].uri, msg.filename || 'chart.png');
          } else {
            const homedir = require('os').homedir();
            defaultUri = vscode.Uri.file(path.join(homedir, msg.filename || 'chart.png'));
          }

          const uri = await vscode.window.showSaveDialog({
            defaultUri: defaultUri,
            filters: { 'Images': ['png'] }
          });
          if (uri) {
            const base64Data = msg.dataUrl.split(',')[1];
            const buffer = Buffer.from(base64Data, 'base64');
            await vscode.workspace.fs.writeFile(uri, buffer);
            vscode.window.showInformationMessage(`Saved ${msg.filename} successfully!`);
          }
        } catch (err: any) {
          vscode.window.showErrorMessage(`Failed to save chart: ${err.message || err}`);
        }
      }
    });
  } else {
    panel.reveal(vscode.ViewColumn.Beside);
    // Refresh the HTML so the dashboard always has the latest markup
    panel.webview.html = getDashboardHtml(context, panel.webview);
  }

  // Tell the panel we are starting a new run (delay to allow webview to load)
  setTimeout(() => {
    sendToPanel({
      type: "start",
      file: path.basename(targetFile),
      timestamp: new Date().toISOString(),
    });
  }, 500);

  // ── Resolve config ─────────────────────────────────────────────────────────
  // Re-use config and pythonPath defined at start of launchAgent
  const stepDelay: number = config.get("stepDelay") ?? 0.02;

  // Ensure python folder in globalStorage exists and write the scripts
  const pythonDir = path.join(context.globalStorageUri.fsPath, "python");
  if (!fs.existsSync(pythonDir)) {
    fs.mkdirSync(pythonDir, { recursive: true });
  }

  const runnerScript = path.join(pythonDir, "runner.py");
  const agentScript = path.join(pythonDir, "arc_agent_llm.py");
  const demoScript = path.join(pythonDir, "train_demo.py");

  fs.writeFileSync(runnerScript, Buffer.from(BASE64_RUNNER, "base64").toString("utf8"), "utf8");
  fs.writeFileSync(agentScript, Buffer.from(BASE64_AGENT, "base64").toString("utf8"), "utf8");
  fs.writeFileSync(demoScript, Buffer.from(BASE64_DEMO, "base64").toString("utf8"), "utf8");

  const env = {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    ARC_STEP_DELAY: stepDelay.toString(),
  };

  // ── Spawn the Python backend ───────────────────────────────────────────────
  activeProcess = cp.spawn(pythonPath, [runnerScript, targetFile], {
    env,
    cwd: path.dirname(targetFile),
  });

  let stdoutBuffer = "";
  let messageBatch: any[] = [];
  let batchTimer: NodeJS.Timeout | null = null;

  const flushBatch = () => {
    if (messageBatch.length > 0) {
      sendToPanel({ type: "batch", events: messageBatch });
      messageBatch = [];
    }
    batchTimer = null;
  };

  activeProcess.stdout?.on("data", (chunk: Buffer) => {
    stdoutBuffer += chunk.toString();
    const lines = stdoutBuffer.split("\n");
    stdoutBuffer = lines.pop() || ""; // keep incomplete line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) { continue; }

      try {
        messageBatch.push(JSON.parse(trimmed));
      } catch {
        messageBatch.push({ type: "log", message: trimmed });
      }
    }

    if (!batchTimer) {
      batchTimer = setTimeout(flushBatch, 100);
    }
  });

  activeProcess.stderr?.on("data", (chunk: Buffer) => {
    const text = chunk.toString().trim();
    if (text) {
      sendToPanel({ type: "error", message: text });
    }
  });

  activeProcess.on("close", (code) => {
    activeProcess = undefined;
    sendToPanel({
      type: "done",
      exitCode: code,
      message: code === 0 ? "Training completed successfully." : `Process exited with code ${code}.`,
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function sendToPanel(event: Record<string, unknown>) {
  panel?.webview.postMessage(event);
}

function getDashboardHtml(
  context: vscode.ExtensionContext,
  webview: vscode.Webview
): string {
  // We inline the HTML directly (avoids URI issues). Load from disk.
  const fs = require("fs");
  try {
    let html = fs.readFileSync(
      path.join(context.extensionPath, "media", "dashboard.html"),
      "utf8"
    );
    const logoUri = webview.asWebviewUri(
      vscode.Uri.file(path.join(context.extensionPath, "media", "logo.png"))
    );
    html = html.replace("{{LOGO_URI}}", logoUri.toString());
    return html;
  } catch {
    return `<html><body><h1>ARC Lens</h1><p>Could not load dashboard.html</p></body></html>`;
  }
}

export function deactivate() {
  if (activeProcess) {
    activeProcess.kill("SIGTERM");
  }
}
