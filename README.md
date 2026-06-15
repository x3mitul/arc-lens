# ARC Lens

ARC Lens is a real-time training visualization dashboard, telemetry collector, and automated recovery extension for PyTorch inside VS Code. Designed as the visualization and interactive control center for the **ARC (Autonomic Recovery Controller)** ecosystem, it automatically monitors, analyzes, and recovers training runs from optimization pathologies (such as NaN loss, exploding gradients, or representational collapse) using a local agent-guided reasoning loop.

## Architecture

The extension uses a decoupled three-tier architecture to monitor and recover training loops with zero user-side code modification:

1. **VS Code Extension**: Manages the host processes, communication channels, dashboard webviews, and AI failure diagnostics.
2. **Telemetry Engine**: Runs inside the user's execution context. It utilizes the `arc-training` package to hook into PyTorch execution and stream step telemetry (loss, learning rates, gradient norms, and GPU memory usage) in real time.
3. **Local Reasoning Loop**: Implements a local offline agent. When step metrics exceed safety thresholds (e.g., NaN loss or exploding gradients), the loop pauses execution and applies recovery tools, such as restoring weights from a previous healthy checkpoint and scaling down learning rates.

## How It Works (Production Workflow)

In production environments, the system automates telemetry extraction and recovery through the following workflow:

1. **Environment Setup**:
   Ensure the Python dependencies are installed in your active virtual environment:
   ```bash
   pip install torch arc-training
   ```

2. **Zero-Code Instrumentation**:
   When you click the **Run with ARC Lens** button in the editor toolbar, the extension runs your PyTorch script via a launcher. This launcher dynamically hooks into the PyTorch training loop to stream step-by-step telemetry (e.g., loss, learning rates, gradient norms) to the extension.

3. **Dashboard Monitoring**:
   Metrics are streamed live to the VS Code dashboard webview, rendering interactive plots of core and advanced diagnostics (Representation Rank, Gradient Entropy, etc.).

4. **Autonomic Recovery**:
   When a step metric crosses safety thresholds, the local reasoning loop intercepts execution:
   * **State Rollback**: It automatically rolls back model weights to the last known healthy checkpoint stored in GPU memory.
   * **Parameter Adaptation**: It adjusts learning rate schedules or activates gradient clipping to bypass the pathology.
   * **Resumed Execution**: Once corrected, training continues smoothly without user intervention.

## Telemetry Metrics

ARC Lens tracks a variety of optimization metrics to diagnose training failure modes:

### Core Metrics
* **Loss**: Tracks optimization objective progression.
* **Learning Rate**: Intercepts optimizer parameter groups in real time.
* **Gradient L2 Norm**: Monitors optimization step magnitude to detect potential divergence.
* **GPU Memory**: Tracks allocated and reserved VRAM to warn of Out-Of-Memory (OOM) conditions.

### Advanced Diagnostics
* **Effective Rank**: Estimates layer representation collapse or dimensional reduction.
* **Gradient Entropy**: Measures gradient noise distribution to identify flat minima.
* **Weight Update Ratio**: Compares update step magnitude against weight norms ($||\Delta W|| / ||W||$).
* **Gradient Flow Ratio**: Computes the gradient ratio between early and deep layers to monitor vanishing gradient trends.

## Automated Interventions

When training anomalies are detected, the local agent can perform targeted recovery operations:
* `rollback_and_reduce_lr`: Reverts model weights to the last known healthy checkpoint and scales down the learning rate.
* `reduce_lr`: Adapts learning rates mid-run to stabilize optimization.
* `enable_grad_clipping`: Recommends gradient clipping thresholds when gradient norms exceed safety limits.

## Configuration

Configure ARC Lens settings in VS Code (`ctrl+,` / `cmd+,`):

| Setting | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `arcAgent.pythonPath` | `string` | `"python"` | Path to the Python interpreter (e.g., virtual environment binary). |
| `arcAgent.stepDelay` | `number` | `0.02` | Pause duration (in seconds) introduced after each step to pace visualization. |
| `arcAgent.licenseKey` | `string` | `""` | ARC Lens Pro license key. Unlocked by default in evaluation mode. |
| `arcAgent.openRouterKey` | `string` | `""` | OpenRouter API key (`sk-or-...`) used for AI diagnostics features. |
| `arcAgent.llmModel` | `string` | `"google/gemini-2.5-flash:free"` | LLM model identifier used for analysis. |

## Evaluation (Simulation Mode)

This repository is pre-configured to build and run in a standalone **Simulation Mode** for evaluation and demonstration. In this mode, the extension executes a simulated training loop that showcases real-time chart updates, failure detection, and automatic intervention logs without requiring PyTorch, CUDA, or local machine learning packages.

For real-world usage on actual training scripts, please install the official [ARC Lens VS Code Extension](https://marketplace.visualstudio.com/items?itemName=arclens.arc-lens) (which performs actual PyTorch hook injection and active weight recovery) and refer to the [ARC Framework Documentation](https://pyarc.pages.dev/).

To run the local evaluation:

1. **Install Dependencies**:
   ```bash
   npm install
   ```
2. **Compile the Extension**:
   ```bash
   npm run compile
   ```
3. **Launch the Extension**:
   Press `F5` to open the VS Code **Extension Development Host**.
4. **Run the Demo**:
   * Open any Python (`.py`) file in the new host window.
   * Click the **Run with ARC Lens** button in the top-right editor toolbar.
   * The dashboard will open, simulating a real-time training loop that hits a NaN loss at step 20, runs a diagnostic reasoning loop, executes a weight rollback, and recovers successfully.

## License

This extension is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0).
