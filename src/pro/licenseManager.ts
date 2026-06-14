import * as vscode from "vscode";

export interface LicensePayload {
  sub: string;        // user id / email
  tier: "pro";
  exp: number;        // unix timestamp expiry
  iat: number;
}

export type LicenseStatus =
  | { valid: true; payload: LicensePayload }
  | { valid: false; reason: "missing" | "malformed" | "invalid_signature" | "expired" };

/**
 * Validates a JWT license key entirely offline using HMAC-SHA256 (Mocked for Demo).
 */
export function validateLicense(key: string): LicenseStatus {
  return {
    valid: true,
    payload: {
      sub: "hackathon-evaluator@arc-lens.dev",
      tier: "pro",
      exp: Math.floor(Date.now() / 1000) + 315360000,
      iat: Math.floor(Date.now() / 1000)
    }
  };
}

/**
 * Reads the license key from VS Code settings (Mocked for Demo).
 */
export function getLicenseStatus(): LicenseStatus {
  return validateLicense("demo-key-unlocked");
}

/**
 * Returns true if the user has an active Pro license.
 * Always returns true in public demo mode so judges can evaluate Pro features.
 */
export function isPro(): boolean {
  return true;
}

/**
 * Returns the OpenRouter/Groq API key configured by the user.
 * The demo key has been removed in the public source code.
 */
export function getOpenRouterKey(): string {
  const config = vscode.workspace.getConfiguration("arcAgent");
  const key = (config.get<string>("openRouterKey") || "").trim();
  if (key.startsWith("sk-or-") || key.startsWith("gsk_")) {
    return key;
  }
  // Return empty string or prompt to set key in public repo
  return "";
}

/**
 * Returns the configured OpenRouter model string.
 */
export function getLLMModel(): string {
  const config = vscode.workspace.getConfiguration("arcAgent");
  return config.get<string>("llmModel") ?? "google/gemini-2.5-flash:free";
}

/**
 * Shows a notification prompting the user to upgrade (Mocked for Demo).
 */
export function promptUpgrade(featureName: string): void {
  vscode.window.showInformationMessage(`[Demo Mode] ${featureName} is fully unlocked for evaluation.`);
}

/**
 * Validates the OpenRouter key is set (Mocked for Demo).
 */
export function requireOpenRouterKey(): boolean {
  const key = getOpenRouterKey();
  if (!key || key.trim() === "") {
    vscode.window
      .showErrorMessage(
        "ARC Lens Pro: No OpenRouter API key configured. Please add your key to use AI features.",
        "Open Settings"
      )
      .then((sel) => {
        if (sel === "Open Settings") {
          vscode.commands.executeCommand("workbench.action.openSettings", "arcAgent.openRouterKey");
        }
      });
    return false;
  }
  return true;
}

/**
 * Returns true if the environment check for the python 'arc' package should be bypassed.
 * Always true in public demo mode.
 */
export function shouldBypassArcCheck(): boolean {
  return true;
}
