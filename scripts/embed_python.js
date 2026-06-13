const fs = require("fs");
const path = require("path");

function run() {
  const root = path.join(__dirname, "..");
  const runnerPath = path.join(root, "python", "runner.py");
  const agentPath = path.join(root, "python", "arc_agent_llm.py");
  const demoPath = path.join(root, "python", "train_demo.py");
  const extensionJsPath = path.join(root, "out", "extension.js");

  if (!fs.existsSync(extensionJsPath)) {
    console.error("extension.js not found in out/! Compile first.");
    process.exit(1);
  }

  const base64Runner = fs.readFileSync(runnerPath).toString("base64");
  const base64Agent = fs.readFileSync(agentPath).toString("base64");
  const base64Demo = fs.readFileSync(demoPath).toString("base64");

  let content = fs.readFileSync(extensionJsPath, "utf8");

  content = content.replace("PLACEHOLDER_BASE64_RUNNER", base64Runner);
  content = content.replace("PLACEHOLDER_BASE64_AGENT", base64Agent);
  content = content.replace("PLACEHOLDER_BASE64_DEMO", base64Demo);

  fs.writeFileSync(extensionJsPath, content, "utf8");
  console.log("Successfully embedded python script base64 constants into out/extension.js!");
}

run();
