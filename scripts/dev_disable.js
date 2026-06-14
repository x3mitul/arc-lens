const fs = require("fs");
const path = require("path");

function disableDevMode() {
  const root = path.join(__dirname, "..");
  
  const filesToSave = [
    { src: "python/runner.py", dest: "private_backup/python/runner.py" },
    { src: "python/arc_agent_llm.py", dest: "private_backup/python/arc_agent_llm.py" },
    { src: "src/pro/licenseManager.ts", dest: "private_backup/src/pro/licenseManager.ts" }
  ];

  const stubsToApply = [
    { src: "private_backup/public_stubs/python/runner.py", dest: "python/runner.py" },
    { src: "private_backup/public_stubs/python/arc_agent_llm.py", dest: "python/arc_agent_llm.py" },
    { src: "private_backup/public_stubs/src/pro/licenseManager.ts", dest: "src/pro/licenseManager.ts" }
  ];

  console.log("Saving your latest development changes to private_backup/...");
  for (const item of filesToSave) {
    const srcPath = path.join(root, item.src);
    const destPath = path.join(root, item.dest);

    if (fs.existsSync(srcPath)) {
      // Create parent dir if it doesn't exist
      const parentDir = path.dirname(destPath);
      if (!fs.existsSync(parentDir)) {
        fs.mkdirSync(parentDir, { recursive: true });
      }
      fs.copyFileSync(srcPath, destPath);
      console.log(`Saved: ${item.src} -> ${item.dest}`);
    }
  }

  console.log("\nActivating RELEASE Mode (Applying public stubs)...");
  for (const item of stubsToApply) {
    const srcPath = path.join(root, item.src);
    const destPath = path.join(root, item.dest);

    if (fs.existsSync(srcPath)) {
      fs.copyFileSync(srcPath, destPath);
      console.log(`Stubbed: ${item.src} -> ${item.dest}`);
    } else {
      console.error(`Error: Stub file not found at ${item.src}. Cannot complete disable.`);
      process.exit(1);
    }
  }

  console.log("\n=== Workspace successfully toggled to RELEASE mode (Mock stubs active for Git) ===");
}

disableDevMode();
