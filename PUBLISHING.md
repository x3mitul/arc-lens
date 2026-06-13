# Publishing ARC Lens to the VS Code Marketplace

This guide outlines the modern, streamlined ways to publish your **ARC Lens** extension to the official VS Code Marketplace.

---

## Method 1: Direct Web Upload (easiest & Recommended)

This is the simplest and most secure method. It requires **no command-line authentication, no Azure DevOps setup, and no access tokens**.

### 1. Create a Publisher Account
1. Go directly to the [VS Code Marketplace Publisher Management Console](https://marketplace.visualstudio.com/manage).
2. Sign in with your Microsoft or GitHub account.
3. Click **Create Publisher**.
4. Set the publisher **ID** to `arclens` (matching the `"publisher"` field in `package.json`).

### 2. Package the Extension
Run the package command in your project directory:
```bash
npx @vscode/vsce package --allow-missing-repository
```
This will compile the TypeScript code and generate a file named `arc-lens-0.1.0.vsix` in your root directory.

### 3. Upload to the Marketplace
1. Go back to your [Marketplace Management Console](https://marketplace.visualstudio.com/manage).
2. Select your `arclens` publisher.
3. Click the **New Extension** button and select **Visual Studio Code**.
4. Drag and drop your newly generated `arc-lens-0.1.0.vsix` file into the upload box.
5. Within a few minutes, the Marketplace will verify the package and your extension will be live!

---

## Method 2: Command-Line Publishing (for CI/CD or Automation)

Use this method if you prefer publishing directly from your terminal or want to automate it via GitHub Actions.

### 1. Generate an Access Token
1. Go to your [Azure DevOps Profile](https://aex.dev.azure.com/me) or [dev.azure.com](https://dev.azure.com).
2. Under **User Settings** (top-right cog next to your profile picture), click **Personal Access Tokens**.
3. Click **New Token** and set:
   * **Organization**: **All accessible organizations** (Required)
   * **Scopes**: Click **Show all scopes** -> Scroll to **Marketplace** -> check **Manage**.
4. Create the token and copy it.

### 2. Login and Publish via Terminal
Run the login command using `vsce` and paste your token when prompted:
```bash
npx @vscode/vsce login arc-lens
```

To publish updates directly:
```bash
npx @vscode/vsce publish --allow-missing-repository
```
