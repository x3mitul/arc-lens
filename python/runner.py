"""
ARC Agent — Python Backend Runner (Mock / Simulation for Public Repository)
==========================================================================
This script simulates the ARC telemetry engine. It outputs mock training metrics,
triggers a simulated failure, runs a mock reasoning loop, applies a mock rollback,
and completes training. This enables full evaluation of the ARC Lens dashboard
without exposing the core AST wrapping or telemetry capture logic.
"""

import sys
import os
import json
import time
import math
import random
from pathlib import Path

def emit(event: dict):
    """Write a JSON event to stdout (read by the VS Code extension)."""
    print(json.dumps(event), flush=True)

def emit_log(message: str, level: str = "info"):
    emit({"type": "log", "level": level, "message": message})

def emit_metric(step: int, epoch: int, loss: float, grad_norm: float, lr: float, gpu_mem_mb: float, advanced: dict = None):
    emit({
        "type": "metric",
        "step": step,
        "epoch": epoch,
        "loss": loss if not math.isnan(loss) else None,
        "grad_norm": round(grad_norm, 4),
        "lr": lr,
        "gpu_mem_mb": round(gpu_mem_mb, 1),
        "timestamp": time.time(),
        "advanced": advanced
    })

def emit_thought(thought: str, phase: str = "reasoning"):
    emit({"type": "thought", "phase": phase, "message": thought})

def emit_intervention(action: str, detail: str):
    emit({"type": "intervention", "action": action, "detail": detail})

def emit_risk(score: float, label: str):
    emit({"type": "risk", "score": score, "label": label})

def main():
    if len(sys.argv) < 2:
        emit({"type": "error", "message": "Usage: runner.py <path_to_training_script.py>"})
        sys.exit(1)

    target_path = sys.argv[1]
    
    emit_log(f"ARC Agent starting for: {Path(target_path).name}")
    emit_log("Injecting ARC monitoring hooks...")
    time.sleep(0.5)
    
    emit_log("ARC package loaded successfully.")
    emit_log("ARC Advanced Telemetry Collector attached successfully.")
    emit_log("ARC monitoring hook installed on PyTorch. Training is now protected.")
    time.sleep(0.3)
    
    emit_log("Hooks injected. Launching training...")
    emit({"type": "status", "status": "running"})
    
    # Read delay from environment or default
    step_delay = float(os.environ.get("ARC_STEP_DELAY", "0.08"))
    
    lr = 0.001
    epoch = 0
    gpu_mem = 1420.5
    
    # Step 1 to 20: Healthy run progressing towards a NaN divergence
    for step in range(1, 21):
        time.sleep(step_delay)
        
        # Simulate normal training metrics
        if step < 15:
            loss = 0.85 * (0.93 ** step) + random.uniform(-0.02, 0.02)
            grad_norm = 1.2 + random.uniform(-0.1, 0.3)
            risk = 0.08
            risk_label = "LOW"
        elif step < 20:
            # Diverging loss
            loss = 0.2 + (step - 14) * 0.45 + random.uniform(-0.05, 0.05)
            grad_norm = 4.5 * (step - 13) + random.uniform(-1.0, 2.0)
            risk = 0.45
            risk_label = "MEDIUM"
        else:
            # Critical failure step
            loss = float('nan')
            grad_norm = 95.4
            risk = 1.0
            risk_label = "CRITICAL"
            
        advanced_metrics = {
            "grad_norm_l2": float(grad_norm),
            "gradient_entropy": 3.82 - (0.05 * step) if step < 20 else 0.85,
            "weight_norm": 24.5 + (0.1 * step),
            "effective_rank": 8.42 - (0.02 * step) if step < 20 else 2.14,
            "weight_update_ratio": 0.002 * (1.5 ** (step - 12)) if step >= 13 else 0.0015,
            "grad_flow_ratio": 1.05 if step < 20 else 18.5
        }
        
        emit_risk(risk, risk_label)
        emit_metric(step, epoch, loss, grad_norm, lr, gpu_mem + (step * 2.3), advanced_metrics)
        
        # Trigger the simulated failure and recovery
        if step == 20:
            emit_log("Critical failure detected: loss value is NaN", "error")
            emit({"type": "failure_detected", "step": step, "loss": "NaN/Inf", "grad_norm": grad_norm})
            
            # Simulate the ReAct reasoning loops
            time.sleep(0.8)
            emit_thought("Failure detected. Initialising ARC reasoning agent...", "perception")
            time.sleep(0.8)
            emit_thought("Calling tool: get_training_snapshot(None)", "action")
            time.sleep(0.6)
            
            snapshot = {
                "step": step,
                "epoch": epoch,
                "loss": "NaN/Inf",
                "is_nan_or_inf": True,
                "grad_norm": round(grad_norm, 4),
                "learning_rate": lr,
                "loss_trend": "exploding",
                "recent_losses": [0.22, 0.65, 1.12, 1.55, None]
            }
            emit_thought(f"Tool result: {json.dumps(snapshot)}", "observation")
            time.sleep(1.0)
            
            emit_thought(
                "Analysis: The training loss has diverged to NaN. This is a critical numerical failure "
                "caused by gradient explosion (L2 norm: 95.4). I need to roll back to the last healthy checkpoint "
                "and reduce the learning rate to stabilize optimization.",
                "reasoning"
            )
            time.sleep(1.2)
            
            emit_thought("Calling tool: rollback_and_reduce_lr()", "action")
            time.sleep(0.8)
            
            # Apply the recovery parameters
            old_lr = lr
            lr = lr * 0.2
            emit_intervention(
                "rollback_and_reduce_lr",
                f"Emergency rollback of 10 steps. LR {old_lr:.2e} -> {lr:.2e}"
            )
            
            emit_thought(
                f"Tool result: {json.dumps({'success': True, 'steps_back': 10, 'old_lr': old_lr, 'new_lr': lr})}",
                "observation"
            )
            time.sleep(0.8)
            emit_thought("Calling tool: continue_training(None)", "action")
            time.sleep(0.5)
            emit_thought("Recovery complete. Resuming training.", "action")
            time.sleep(0.6)
            
            # Simulate resuming from step 10
            emit_log("Resuming training from checkpoint step 10 with updated learning rate...", "info")
            time.sleep(0.3)

    # Step 21 to 30: Recovered training loop with lower learning rate
    for step in range(21, 31):
        time.sleep(step_delay)
        
        # Training stabilizes with lower learning rate
        offset = step - 21
        loss = 0.18 * (0.92 ** offset) + random.uniform(-0.01, 0.01)
        grad_norm = 0.45 + random.uniform(-0.05, 0.1)
        risk = 0.02
        risk_label = "LOW"
        
        advanced_metrics = {
            "grad_norm_l2": float(grad_norm),
            "gradient_entropy": 3.95 + (0.01 * offset),
            "weight_norm": 25.8 + (0.02 * offset),
            "effective_rank": 8.12 + (0.01 * offset),
            "weight_update_ratio": 0.0003,
            "grad_flow_ratio": 1.01
        }
        
        emit_risk(risk, risk_label)
        emit_metric(step, epoch, loss, grad_norm, lr, gpu_mem + (step * 1.8), advanced_metrics)

    time.sleep(0.5)
    emit({"type": "status", "status": "complete", "message": "Training finished successfully."})

if __name__ == "__main__":
    main()
