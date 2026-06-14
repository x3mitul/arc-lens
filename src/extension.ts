import * as vscode from "vscode";
import * as path from "path";
import * as cp from "child_process";
import * as fs from "fs";
import { isPro, promptUpgrade, getLLMModel, requireOpenRouterKey, shouldBypassArcCheck } from "./pro/licenseManager";
import { buildSystemPrompt, MetricPoint, AgentLogEntry } from "./pro/contextBuilder";
import { streamChatCompletion, ChatMessage } from "./pro/chatManager";
import { buildScriptGenMessages, extractCodeBlock, ScriptGenRequest } from "./pro/scriptGenerator";

// Embedded python base64 constants (filled by build script)
const BASE64_RUNNER = "PLACEHOLDER_BASE64_RUNNER";
const BASE64_AGENT = "PLACEHOLDER_BASE64_AGENT";
const BASE64_DEMO = "PLACEHOLDER_BASE64_DEMO";

// ─────────────────────────────────────────────────────────────────────────────
// State
// ─────────────────────────────────────────────────────────────────────────────
let panel: vscode.WebviewPanel | undefined;
let chatPanel: vscode.WebviewPanel | undefined;
let activeProcess: cp.ChildProcess | undefined;

// Pro telemetry accumulation
const metricHistory: MetricPoint[] = [];
const agentLog: AgentLogEntry[] = [];
let activeTargetFile = "";
let chatHistory: ChatMessage[] = [];
let cancelCurrentStream: (() => void) | null = null;

// ─────────────────────────────────────────────────────────────────────────────
// Activate
// ─────────────────────────────────────────────────────────────────────────────
export function activate(context: vscode.ExtensionContext) {
  console.log("=== ARC LENS PRO ACTIVATED ===");
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

  // Register "Open Pro Chat" command
  context.subscriptions.push(
    vscode.commands.registerCommand("arc-lens.openChat", () => {
      if (!isPro()) {
        promptUpgrade("AI Failure Analyst");
        return;
      }
      if (!requireOpenRouterKey()) return;
      openChatPanel(context);
    })
  );

  // Register "Generate Script" command
  context.subscriptions.push(
    vscode.commands.registerCommand("arc-lens.generateScript", () => {
      if (!isPro()) {
        promptUpgrade("ARC Script Generator");
        return;
      }
      if (!requireOpenRouterKey()) return;
      openGeneratorPanel(context);
    })
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Launch Agent
// ─────────────────────────────────────────────────────────────────────────────
function ensureArcTrainingInstalled(pythonPath: string): Promise<boolean> {
  if (shouldBypassArcCheck()) {
    return Promise.resolve(true);
  }
  return new Promise((resolve) => {
    cp.exec(`"${pythonPath}" -c "import arc"`, (err) => {
      if (!err) {
        resolve(true);
        return;
      }

      vscode.window
        .showWarningMessage(
          "The Python package 'arc-training' is not installed in the selected environment. ARC Lens needs it to apply automatic recovery interventions.",
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
      } else if (msg.command === "upgrade") {
        // Dev key: signed with arc-lens-pro-secret-2024, expires 2029
        const devKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkZXYtdXNlckBhcmMtbGVucy5kZXYiLCJ0aWVyIjoicHJvIiwiaWF0IjoxNzgxNDI3ODE2LCJleHAiOjE4NzYwMzU4MTZ9.noY0WxfaEidelugDG6wC00PFw4rXETvYiIaDXKBdAoU";
        await vscode.workspace.getConfiguration("arcAgent").update("licenseKey", devKey, vscode.ConfigurationTarget.Global);
        vscode.window.showInformationMessage("🎉 ARC Lens Pro activated! Set your OpenRouter API key to use AI features.", "Open Settings").then(sel => {
          if (sel === "Open Settings") {
            vscode.commands.executeCommand("workbench.action.openSettings", "arcAgent.openRouterKey");
          }
        });
        if (panel) {
          panel.webview.html = getDashboardHtml(context, panel.webview);
        }
      } else if (msg.command === "openChat") {
        vscode.commands.executeCommand("arc-lens.openChat");
      } else if (msg.command === "openGenerator") {
        vscode.commands.executeCommand("arc-lens.generateScript");
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

  // Reset Pro telemetry on new run
  metricHistory.length = 0;
  agentLog.length = 0;
  activeTargetFile = targetFile;
  chatHistory = [];

  // Tell the panel we are starting a new run (delay to allow webview to load)
  setTimeout(() => {
    sendToPanel({
      type: "start",
      file: path.basename(targetFile),
      timestamp: new Date().toISOString(),
      isPro: isPro(),
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
        const parsed = JSON.parse(trimmed);
        // Accumulate Pro telemetry
        if (parsed.type === "metric") {
          metricHistory.push(parsed as MetricPoint);
          if (metricHistory.length > 10000) metricHistory.shift();
        } else if (parsed.type === "failure_detected" || parsed.type === "intervention" || parsed.type === "thought") {
          agentLog.push({
            type: parsed.type,
            step: parsed.step ?? metricHistory.length,
            message: parsed.message ?? "",
            action: parsed.action,
            detail: parsed.detail,
          } as AgentLogEntry);
        }
        messageBatch.push(parsed);
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
    console.log("=== getDashboardHtml: isPro =", isPro());
    let html = fs.readFileSync(
      path.join(context.extensionPath, "media", "dashboard.html"),
      "utf8"
    );
    const logoUri = webview.asWebviewUri(
      vscode.Uri.file(path.join(context.extensionPath, "media", "logo.png"))
    );
    html = html.replace("{{LOGO_URI}}", logoUri.toString());
    html = html.replace("{{IS_PRO_PLACEHOLDER}}", isPro() ? "true" : "false");
    return html;
  } catch {
    return `<html><body><h1>ARC Lens</h1><p>Could not load dashboard.html</p></body></html>`;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Pro: Chat Panel
// ─────────────────────────────────────────────────────────────────────────────
function openChatPanel(context: vscode.ExtensionContext) {
  if (chatPanel) {
    chatPanel.reveal(vscode.ViewColumn.Beside);
    return;
  }

  chatPanel = vscode.window.createWebviewPanel(
    "arcLensChat",
    "ARC Analyst",
    vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  chatPanel.webview.html = getChatHtml(getFriendlyModelName());

  chatPanel.onDidDispose(() => {
    cancelCurrentStream?.();
    chatPanel = undefined;
  });

  chatPanel.webview.onDidReceiveMessage(async (msg) => {
    if (msg.command === "chat") {
      cancelCurrentStream?.();

      const systemPrompt = buildSystemPrompt(
        metricHistory,
        agentLog,
        activeTargetFile
      );

      if (chatHistory.length === 0) {
        chatHistory.push({ role: "system", content: systemPrompt });
      } else {
        chatHistory[0] = { role: "system", content: systemPrompt };
      }
      chatHistory.push({ role: "user", content: msg.text });

      chatPanel?.webview.postMessage({ type: "stream_start" });

      let assistantReply = "";
      cancelCurrentStream = streamChatCompletion(
        chatHistory,
        (chunk) => {
          assistantReply += chunk;
          chatPanel?.webview.postMessage({ type: "stream_chunk", text: chunk });
        },
        () => {
          chatHistory.push({ role: "assistant", content: assistantReply });
          chatPanel?.webview.postMessage({ type: "stream_done" });
          cancelCurrentStream = null;
        },
        (err) => {
          chatPanel?.webview.postMessage({ type: "stream_error", text: err });
          cancelCurrentStream = null;
        }
      );
    } else if (msg.command === "clear") {
      chatHistory = [];
    } else if (msg.command === "cancel") {
      cancelCurrentStream?.();
      cancelCurrentStream = null;
      chatPanel?.webview.postMessage({ type: "stream_done" });
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Pro: Script Generator Panel
// ─────────────────────────────────────────────────────────────────────────────
function getFriendlyModelName(): string {
  const model = getLLMModel();
  if (!model) return "AI Analyst";
  // Normalize known models to a clean display name
  const knownNames: Record<string, string> = {
    "deepseek/deepseek-chat": "DeepSeek V3",
    "deepseek/deepseek-r1": "DeepSeek R1",
    "deepseek/deepseek-r1:free": "DeepSeek R1 (Free)",
    "google/gemini-2.5-flash:free": "Gemini 2.5 Flash (Free)",
    "meta-llama/llama-3.3-70b-instruct:free": "Llama 3.3 70B (Free)",
    "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
    "openai/gpt-4o": "GPT-4o",
    "openai/gpt-4o-mini": "GPT-4o Mini",
    "google/gemini-2.0-flash-001": "Gemini 2.0 Flash",
  };
  
  if (knownNames[model]) {
    return knownNames[model];
  }
  
  // Dynamic fallback: splits 'vendor/model-name-here:free' to 'Model Name Here (Free)'
  const parts = model.split('/');
  let rawName = parts[parts.length - 1] || model;
  let isFree = false;
  if (rawName.endsWith(':free')) {
    isFree = true;
    rawName = rawName.slice(0, -5);
  }
  
  const formatted = rawName
    .split(/[-_]/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
    
  return isFree ? `${formatted} (Free)` : formatted;
}

function openGeneratorPanel(context: vscode.ExtensionContext) {
  const genPanel = vscode.window.createWebviewPanel(
    "arcLensGenerator",
    "ARC Script Generator",
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );

  genPanel.webview.html = getGeneratorHtml(getFriendlyModelName());

  genPanel.webview.onDidReceiveMessage(async (msg) => {
    if (msg.command !== "generate") return;

    const req = msg.request as ScriptGenRequest;
    const messages = buildScriptGenMessages(req);

    genPanel.webview.postMessage({ type: "generating" });

    let fullResponse = "";
    streamChatCompletion(
      messages,
      (chunk) => { fullResponse += chunk; },
      async () => {
        const code = extractCodeBlock(fullResponse, req.outputFormat);
        if (!code) {
          genPanel.webview.postMessage({ type: "error", text: "Failed to extract code from response. Try rephrasing your task description." });
          return;
        }

        const ext = req.outputFormat === "py" ? "py" : "ipynb";
        const defaultName = `arc_train.${ext}`;
        const uri = await vscode.window.showSaveDialog({
          defaultUri: vscode.Uri.file(path.join(require("os").homedir(), defaultName)),
          filters: req.outputFormat === "py"
            ? { "Python Script": ["py"] }
            : { "Jupyter Notebook": ["ipynb"] },
        });

        if (uri) {
          fs.writeFileSync(uri.fsPath, code, "utf8");
          vscode.window.showInformationMessage(`✅ ARC-tested script saved: ${path.basename(uri.fsPath)}`);
          vscode.window.showTextDocument(uri);
        }
        genPanel.webview.postMessage({ type: "done" });
      },
      (err) => {
        genPanel.webview.postMessage({ type: "error", text: err });
      }
    );
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Pro: Webview HTML helpers
// ─────────────────────────────────────────────────────────────────────────────
function getChatHtml(modelName: string): string {
  return `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'unsafe-inline';">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<title>ARC Analyst</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{
  background: #000000;
  color: #ededed;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}
header{
  padding: 16px 20px;
  border-bottom: 1px solid #27272a;
  background: #000000;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  z-index: 10;
}
.title{
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: #ededed;
}
.pro-badge {
  background: transparent;
  border: 1px solid #333333;
  color: #a1a1aa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
  display: inline-flex;
  align-items: center;
}
.model-badge {
  font-size: 11px;
  color: #888888;
  font-weight: 500;
  margin-left: auto;
}
.btn-clear{
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #a1a1aa;
  padding: 4px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
  transition: all 0.2s ease;
}
.btn-clear:hover{
  border-color: rgba(255, 255, 255, 0.2);
  color: #ffffff;
  background: rgba(255, 255, 255, 0.06);
}
#messages{
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}
#messages::-webkit-scrollbar{
  width: 5px;
}
#messages::-webkit-scrollbar-thumb{
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}
.msg{
  max-width: 90%;
  animation: fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes fadeIn{
  from{opacity:0;transform:translateY(6px)}
  to{opacity:1;transform:translateY(0)}
}
.msg-user{
  align-self: flex-end;
  background: rgba(139, 92, 246, 0.08);
  border: 1px solid rgba(139, 92, 246, 0.25);
  border-radius: 12px 12px 2px 12px;
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.5;
  color: #f4f4f5;
}
.msg-assistant{
  align-self: flex-start;
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 12px 12px 12px 2px;
  padding: 16px;
  max-width: 95%;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}
.msg-assistant pre{
  background: #09090b;
  border: 1px solid #27272a;
  border-radius: 8px;
  padding: 14px;
  overflow-x: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  margin: 12px 0;
  color: #e4e4e7;
}
.msg-assistant p{
  font-size: 13px;
  line-height: 1.6;
  color: #d4d4d8;
  margin: 8px 0;
}
.msg-assistant p:first-child{
  margin-top: 0;
}
.msg-assistant p:last-child{
  margin-bottom: 0;
}
.msg-assistant code{
  background: rgba(255, 255, 255, 0.06);
  color: #f472b6;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}
.msg-system{
  align-self: center;
  color: #a1a1aa;
  font-size: 11px;
  padding: 6px 14px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(8px);
}
.cursor{
  display: inline-block;
  width: 2px;
  height: 14px;
  background: #8b5cf6;
  margin-left: 2px;
  animation: blink 0.8s infinite;
}
@keyframes blink{
  0%,100%{opacity:1}
  50%{opacity:0}
}
.input-area{
  padding: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  background: #09090b;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}
.prompt-container {
  border: 1px solid #27272a;
  background: #18181b;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  padding: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.prompt-container {
  background: #000000;
  border: 1px solid #333333;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: border-color 0.15s ease;
}
.prompt-container:focus-within {
  border-color: #888888;
}
#user-input {
  background: transparent;
  border: none;
  color: #ededed;
  padding: 4px 6px;
  font-family: inherit;
  font-size: 13px;
  resize: none;
  outline: none;
  max-height: 200px;
  line-height: 1.5;
  width: 100%;
}
#user-input::placeholder {
  color: #888888;
}
.prompt-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px 0;
}
.telemetry-pill {
  font-size: 11px;
  color: #a1a1aa;
  background: transparent;
  padding: 2px 0px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  user-select: none;
}
.btn-send {
  background: #ededed;
  border: none;
  color: #000000;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}
.btn-send:hover {
  background: #ffffff;
}
.btn-send:disabled {
  background: #333333;
  color: #888888;
  cursor: not-allowed;
}
.empty-state{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 16px;
  color: #a1a1aa;
  text-align: center;
  max-width: 320px;
  margin: 0 auto;
}
.empty-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  background: #0a0a0a;
  border: 1px solid #27272a;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #a1a1aa;
  margin-bottom: 8px;
}
.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: #ededed;
}
.empty-desc {
  font-size: 13px;
  line-height: 1.5;
  color: #888896;
}
.empty-sub {
  font-size: 11px;
  color: #52526b;
  border-top: 1px solid rgba(255,255,255,0.03);
  padding-top: 12px;
  width: 100%;
}
</style></head><body>
<header>
  <div class="title">ARC Analyst <span class="pro-badge">PRO</span> <span class="model-badge">${modelName}</span></div>
  <button class="btn-clear" onclick="clearChat()">Clear</button>
</header>
<div id="messages">
  <div class="empty-state" id="empty-state">
    <div class="empty-icon-wrapper">
      <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
    </div>
    <div class="empty-title">AI Failure Analyst</div>
    <div class="empty-desc">Ask ARC why your training failed, or request architecture suggestions.</div>
    <div class="empty-sub">Telemetry from the active training run is attached automatically.</div>
  </div>
</div>
<div class="input-area">
  <div class="prompt-container">
    <textarea id="user-input" placeholder="Why did the gradient explode at step 40?" rows="1"
      onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
    <div class="prompt-footer">
      <div class="telemetry-pill">
        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
        Telemetry Attached
      </div>
      <button class="btn-send" id="btn-send" onclick="sendMessage()">
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
      </button>
    </div>
  </div>
</div>
<script>
const vscode = acquireVsCodeApi();
let streaming = false;
let streamEl = null;

function clearChat(){
  vscode.postMessage({command:'clear'});
  document.getElementById('messages').innerHTML='<div class="empty-state" id="empty-state"><div class="empty-icon-wrapper"><svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg></div><div class="empty-title">AI Failure Analyst</div><div class="empty-desc">Ask ARC why your training failed, or request architecture suggestions.</div><div class="empty-sub">Telemetry from the active training run is attached automatically.</div></div>';
}

function autoResize(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,120)+'px'}

function handleKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage()}}

function sendMessage(){
  if(streaming) return;
  const input=document.getElementById('user-input');
  const text=input.value.trim();
  if(!text) return;
  hideEmpty();
  appendMsg('user',text);
  input.value='';input.style.height='auto';
  vscode.postMessage({command:'chat',text});
}

function hideEmpty(){const e=document.getElementById('empty-state');if(e)e.remove()}

function appendMsg(role,text){
  const div=document.createElement('div');
  div.className='msg msg-'+role;
  if(role==='assistant'){div.innerHTML=renderMarkdown(text);}
  else{div.textContent=text;}
  document.getElementById('messages').appendChild(div);
  scrollBottom();
  return div;
}

function renderMarkdown(text){
  // Escape HTML entities first to prevent XSS
  const escaped = text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return escaped
    .replace(/\\\`\\\`\\\`([\\s\\S]*?)\\\`\\\`\\\`/g,'<pre><code>$1</code></pre>')
    .replace(/\\\`([^\\\`]+)\\\`/g,'<code>$1</code>')
    .replace(/\\*\\*(.+?)\\*\\*/g,'<strong>$1</strong>')
    .replace(/\\*(.+?)\\*/g,'<em>$1</em>')
    .replace(/^### (.+)$/gm,'<h4 style="font-size:13px;font-weight:600;margin:12px 0 4px;color:#fff">$1</h4>')
    .replace(/^## (.+)$/gm,'<h3 style="font-size:14px;font-weight:600;margin:12px 0 4px;color:#fff">$1</h3>')
    .replace(/^- (.+)$/gm,'<li style="margin:4px 0 4px 16px;list-style:disc">$1</li>')
    .replace(/\\n/g,'<br>');
}

function scrollBottom(){const m=document.getElementById('messages');m.scrollTop=m.scrollHeight}

window.addEventListener('message',e=>{
  const msg=e.data;
  if(msg.type==='stream_start'){
    streaming=true;
    document.getElementById('btn-send').disabled=true;
    streamEl=appendMsg('assistant','');
    streamEl.innerHTML='<span class="cursor"></span>';
  } else if(msg.type==='stream_chunk'){
    if(streamEl){
      const cur=streamEl.dataset.raw||'';
      streamEl.dataset.raw=cur+msg.text;
      streamEl.innerHTML=renderMarkdown(streamEl.dataset.raw)+'<span class="cursor"></span>';
      scrollBottom();
    }
  } else if(msg.type==='stream_done'){
    if(streamEl){streamEl.innerHTML=renderMarkdown(streamEl.dataset.raw||'');}
    streaming=false;streamEl=null;
    document.getElementById('btn-send').disabled=false;
  } else if(msg.type==='stream_error'){
    if(streamEl){streamEl.innerHTML='<p style="color:#ff4444">Error: '+msg.text+'</p>';}
    streaming=false;streamEl=null;
    document.getElementById('btn-send').disabled=false;
  }
});
</script></body></html>`;
}

function getGeneratorHtml(modelName: string): string {
  return `<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; script-src 'unsafe-inline';">
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<title>ARC Script Generator</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{
  background: #000000;
  color: #ededed;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  padding: 24px 32px;
  min-height: 100vh;
}
.header-container {
  margin-bottom: 32px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
h1{
  font-size: 20px;
  font-weight: 600;
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  letter-spacing: -0.02em;
  color: #ededed;
}
.pro-badge {
  background: transparent;
  border: 1px solid #333333;
  color: #a1a1aa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
  display: inline-flex;
  align-items: center;
}
.sub{
  color: #a1a1aa;
  font-size: 13px;
  line-height: 1.5;
}
.card {
  background: #0a0a0a;
  border: 1px solid #27272a;
  border-radius: 8px;
  padding: 24px;
}
.sub{
  color: #888896;
  font-size: 13.5px;
  line-height: 1.5;
}
.card {
  background: rgba(24, 24, 27, 0.4);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
  border-radius: 16px;
  padding: 24px;
  animation: fadeIn 0.5s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
.form-group{
  margin-bottom: 16px;
}
label{
  display: block;
  font-size: 12px;
  color: #a1a1aa;
  margin-bottom: 8px;
  font-weight: 500;
}
select,input,textarea{
  width: 100%;
  background: #000000;
  border: 1px solid #333333;
  border-radius: 6px;
  color: #ededed;
  padding: 10px 12px;
  font-family: inherit;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s ease;
}
select:focus,input:focus,textarea:focus{
  border-color: #888888;
}
select option {
  background: #000000;
  color: #ededed;
}
textarea{
  resize: vertical;
  min-height: 72px;
  line-height: 1.5;
}
.row{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.format-toggle {
  display: flex;
  background: #000000;
  border: 1px solid #333333;
  padding: 2px;
  border-radius: 6px;
}
.format-btn {
  flex: 1;
  background: transparent;
  border: none;
  color: #a1a1aa;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s ease;
}
.format-btn:hover {
  color: #ededed;
}
.format-btn.active {
  background: #27272a;
  color: #ededed;
}
.btn-generate {
  width: 100%;
  background: #ededed;
  border: 1px solid #ededed;
  color: #000000;
  padding: 10px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  margin-top: 8px;
  transition: background 0.15s ease;
}
.btn-generate:hover {
  background: #ffffff;
}
.btn-generate:disabled {
  background: #333333;
  border-color: #333333;
  color: #888888;
  cursor: not-allowed;
}
.status{
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 12.5px;
  display: none;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  animation: fadeIn 0.2s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
.status.generating{
  display: flex;
  background: rgba(16, 185, 129, 0.05);
  border: 1px solid rgba(16, 185, 129, 0.2);
  color: #10b981;
}
.status.error{
  display: flex;
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #fca5a5;
}
</style></head><body>
<div class="header-container">
  <h1>🛠 ARC Script Generator <span class="pro-badge">PRO</span></h1>
  <p class="sub">Generate ARC-instrumented training scripts ready for Kaggle, Colab, or local GPU.</p>
</div>
<div class="card">
  <div class="form-group">
    <label>Architecture</label>
    <select id="arch">
      <option value="resnet">ResNet-50 (Image Classification)</option>
      <option value="transformer">Transformer (Sequence Tasks)</option>
      <option value="custom_cnn">Custom CNN</option>
      <option value="mlp">MLP / Tabular</option>
      <option value="custom">Custom (placeholder)</option>
    </select>
  </div>
  <div class="form-group">
    <label>Describe your task</label>
    <textarea id="task" placeholder="e.g. Fine-tune ResNet-50 on CIFAR-10 for image classification with 10 classes"></textarea>
  </div>
  <div class="row">
    <div class="form-group">
      <label>Platform</label>
      <select id="platform">
        <option value="kaggle">Kaggle</option>
        <option value="colab">Google Colab</option>
        <option value="local">Local GPU</option>
      </select>
    </div>
    <div class="form-group">
      <label>Optimizer</label>
      <select id="optimizer">
        <option value="AdamW">AdamW</option>
        <option value="Adam">Adam</option>
        <option value="SGD with momentum">SGD + Momentum</option>
      </select>
    </div>
  </div>
  <div class="row">
    <div class="form-group">
      <label>Epochs</label>
      <input type="number" id="epochs" value="20" min="1" max="1000">
    </div>
    <div class="form-group">
      <label>Output Format</label>
      <div class="format-toggle">
        <div class="format-btn active" id="btn-py" onclick="setFormat('py')">.py Script</div>
        <div class="format-btn" id="btn-ipynb" onclick="setFormat('ipynb')">.ipynb Notebook</div>
      </div>
    </div>
  </div>
  <div class="form-group">
    <label>Extra requirements (optional)</label>
    <input type="text" id="notes" placeholder="e.g. Mixed precision, cosine LR schedule, gradient clipping">
  </div>
  <button class="btn-generate" id="btn-gen" onclick="generate()">Generate ARC-Tested Script</button>
  <div class="status" id="status-gen">🔄 Generating with ${modelName}... this may take 15–30 seconds.</div>
  <div class="status" id="status-err"></div>
</div>
<script>
const vscode=acquireVsCodeApi();
let fmt='py';
function setFormat(f){fmt=f;document.getElementById('btn-py').className='format-btn'+(f==='py'?' active':'');document.getElementById('btn-ipynb').className='format-btn'+(f==='ipynb'?' active':'');}
function generate(){
  const btn=document.getElementById('btn-gen');
  btn.disabled=true;
  hideStatus('status-gen');
  hideStatus('status-err');
  vscode.postMessage({command:'generate',request:{
    architecture:document.getElementById('arch').value,
    task:document.getElementById('task').value||'image classification',
    platform:document.getElementById('platform').value,
    outputFormat:fmt,
    epochs:parseInt(document.getElementById('epochs').value)||20,
    optimizer:document.getElementById('optimizer').value,
    extraNotes:document.getElementById('notes').value,
  }});
}
function showStatus(id, cls, text) {
  const el = document.getElementById(id);
  el.className = 'status ' + cls;
  if (text) el.textContent = text;
}
function hideStatus(id) {
  document.getElementById(id).className = 'status';
}
window.addEventListener('message',e=>{
  const msg=e.data;
  if(msg.type==='generating'){
    showStatus('status-gen','generating',null);
    hideStatus('status-err');
  } else if(msg.type==='done'){
    document.getElementById('btn-gen').disabled=false;
    hideStatus('status-gen');
    hideStatus('status-err');
  } else if(msg.type==='error'){
    document.getElementById('btn-gen').disabled=false;
    hideStatus('status-gen');
    showStatus('status-err','error','⚠ Error: '+msg.text);
  }
});
</script></body></html>`;
}

export function deactivate() {
  if (activeProcess) {
    activeProcess.kill("SIGTERM");
  }
  cancelCurrentStream?.();
}

