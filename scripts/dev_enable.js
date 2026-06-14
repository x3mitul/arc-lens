const fs = require("fs");
const path = require("path");

function enableDevMode() {
  const root = path.join(__dirname, "..");
  
  const filesToRestore = [
    { src: "private_backup/python/runner.py", dest: "python/runner.py" },
    { src: "private_backup/python/arc_agent_llm.py", dest: "python/arc_agent_llm.py" },
    { src: "private_backup/src/pro/licenseManager.ts", dest: "src/pro/licenseManager.ts" }
  ];

  console.log("Activating DEVELOPMENT Mode (Restoring real files)...");

  for (const item of filesToRestore) {
    const srcPath = path.join(root, item.src);
    const destPath = path.join(root, item.dest);

    if (fs.existsSync(srcPath)) {
      fs.copyFileSync(srcPath, destPath);
      console.log(`Restore: ${item.src} -> ${item.dest}`);
    } else {
      console.warn(`Warning: Backup file not found at ${item.src}`);
    }
  }

  console.log("\n=== Workspace successfully toggled to DEVELOPMENT mode (Real files active) ===");
}

enableDevMode();
