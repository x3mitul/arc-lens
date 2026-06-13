"""
ARC Agent — Python Backend Runner
==================================
This script is spawned by the VS Code extension. It:
  1. Reads the user's training script.
  2. Injects ARC wrapping via AST manipulation.
  3. Executes the modified script in a subprocess.
  4. Intercepts training metrics in real-time.
  5. Calls the LLM agent when a failure is detected.
  6. Emits all events as newline-delimited JSON to stdout.

The VS Code extension reads this stdout and forwards events to the WebView.
"""

import ast
import sys
import os
import json
import math
import textwrap
import threading
import time
import traceback
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Event emitter — all communication back to VS Code is via JSON lines on stdout
# ─────────────────────────────────────────────────────────────────────────────

def emit(event: dict):
    """Write a JSON event to stdout (read by the VS Code extension)."""
    print(json.dumps(event), flush=True)


def emit_log(message: str, level: str = "info"):
    emit({"type": "log", "level": level, "message": message})


def emit_metric(step: int, epoch: int, loss: float, grad_norm: float, lr: float, gpu_mem_mb: float = 0.0):
    emit({
        "type": "metric",
        "step": step,
        "epoch": epoch,
        "loss": loss if not math.isnan(loss) else None,
        "grad_norm": round(grad_norm, 4),
        "lr": lr,
        "gpu_mem_mb": round(gpu_mem_mb, 1),
        "timestamp": time.time(),
    })


def emit_thought(thought: str, phase: str = "reasoning"):
    """Emit a single LLM thought/reasoning step."""
    emit({"type": "thought", "phase": phase, "message": thought})


def emit_intervention(action: str, detail: str):
    emit({"type": "intervention", "action": action, "detail": detail})


def emit_risk(score: float, label: str):
    emit({"type": "risk", "score": score, "label": label})


# ─────────────────────────────────────────────────────────────────────────────
# AST Injection — wraps the user's model + optimizer with ARC
# ─────────────────────────────────────────────────────────────────────────────

ARC_PREAMBLE = textwrap.dedent("""
import sys as _arc_sys
import os as _arc_os
import math as _arc_math
import json as _arc_json
import time as _arc_time

# ARC Agent monitoring bridge
_arc_step = [0]
_arc_epoch = [0]
_arc_loss_history = []
_arc_intervention_count = [0]
_arc_rollback_helper = [None]

def _arc_emit(event):
    print(_arc_json.dumps(event), flush=True)

def _arc_emit_metric(step, epoch, loss, grad_norm, lr, gpu_mem_mb=0.0, advanced=None):
    _arc_emit({
        "type": "metric",
        "step": step,
        "epoch": epoch,
        "loss": loss if not _arc_math.isnan(loss) else None,
        "grad_norm": round(grad_norm, 4),
        "lr": lr,
        "gpu_mem_mb": round(gpu_mem_mb, 1),
        "timestamp": _arc_time.time(),
        "advanced": advanced
    })

def _arc_emit_thought(thought, phase="reasoning"):
    _arc_emit({"type": "thought", "phase": phase, "message": thought})

def _arc_emit_intervention(action, detail):
    _arc_emit({"type": "intervention", "action": action, "detail": detail})
    _arc_intervention_count[0] += 1

def _arc_emit_risk(score, label):
    _arc_emit({"type": "risk", "score": score, "label": label})

try:
    import arc as _arc_pkg
    _arc_emit({"type": "log", "level": "info", "message": "ARC package loaded successfully."})
except ImportError:
    _arc_emit({"type": "log", "level": "warning", "message": "arc-training not installed. Running in monitor-only mode. Install with: pip install arc-training"})
    _arc_pkg = None

try:
    import torch as _arc_torch
    _arc_has_torch = True
except ImportError:
    _arc_has_torch = False

def _arc_get_gpu_mem():
    if _arc_has_torch and _arc_torch.cuda.is_available():
        return _arc_torch.cuda.memory_allocated() / 1024 / 1024
    return 0.0

def _arc_get_grad_norm(model):
    total = 0.0
    for p in model.parameters():
        if p.grad is not None:
            total += p.grad.norm().item() ** 2
    return total ** 0.5

""")

ARC_STEP_HOOK = textwrap.dedent("""
def _arc_on_loss(loss_val, model, optimizer):
    \"\"\"Called after each loss.backward(). Emits metrics and triggers LLM agent on failure.\"\"\"
    _arc_step[0] += 1
    step = _arc_step[0]
    epoch = _arc_epoch[0]

    # Initialize Rollback helper on first step if ARC package is present
    if _arc_pkg is not None and _arc_rollback_helper[0] is None:
        try:
            from arc.intervention.rollback import WeightRollback, RollbackConfig
            config = RollbackConfig(checkpoint_frequency=10, max_checkpoints=3)
            _arc_rollback_helper[0] = WeightRollback(model, optimizer, config=config, verbose=False)
            _arc_emit({"type": "log", "level": "info", "message": "Initialized ARC WeightRollback checkpointing."})
        except Exception as e:
            _arc_emit({"type": "log", "level": "warning", "message": f"Could not initialize WeightRollback: {e}"})

    # Attach Composite Collectors on first step if ARC package is present
    if _arc_pkg is not None and not hasattr(_arc_on_loss, "_collector"):
        try:
            from arc.signals import CompositeCollector, GradientCollector, WeightCollector
            _arc_on_loss._collector = CompositeCollector([GradientCollector(), WeightCollector()])
            _arc_on_loss._collector.attach(model, optimizer)
            _arc_emit({"type": "log", "level": "info", "message": "ARC Advanced Telemetry Collector attached successfully."})
        except Exception as e:
            _arc_emit({"type": "log", "level": "warning", "message": f"Could not attach ARC Advanced Telemetry: {e}"})
            _arc_on_loss._collector = None

    try:
        grad_norm = _arc_get_grad_norm(model)
    except Exception:
        grad_norm = 0.0

    try:
        lr = optimizer.param_groups[0]['lr']
    except Exception:
        lr = 0.0

    gpu_mem = _arc_get_gpu_mem()
    is_bad = _arc_math.isnan(loss_val) or _arc_math.isinf(loss_val) or loss_val > 1e6

    # Save checkpoint periodically if healthy
    if _arc_rollback_helper[0] is not None and not is_bad:
        try:
            helper = _arc_rollback_helper[0]
            helper.state.step_count += 1
            if helper.state.step_count % helper.config.checkpoint_frequency == 0:
                helper._save_checkpoint()
        except Exception:
            pass

    # Extract advanced metrics from collectors if available
    advanced = None
    if _arc_pkg is not None and getattr(_arc_on_loss, "_collector", None) is not None:
        try:
            _arc_on_loss._collector.step()
            snapshot = _arc_on_loss._collector.collect()
            signals = snapshot.signals
            
            grad_g = signals.get("gradient.global", {})
            weight_g = signals.get("weight.global", {})
            
            advanced = {
                "grad_norm_l2": float(grad_g.get("total_grad_norm_l2", 0.0)),
                "gradient_entropy": float(grad_g.get("total_grad_entropy", 0.0)),
                "weight_norm": float(weight_g.get("total_weight_norm", 0.0)),
                "effective_rank": float(weight_g.get("mean_effective_rank", 0.0)),
            }
            if "mean_update_ratio" in weight_g:
                advanced["weight_update_ratio"] = float(weight_g["mean_update_ratio"])
            if "grad_flow_ratio" in grad_g:
                gfr = grad_g["grad_flow_ratio"]
                if _arc_math.isinf(gfr) or _arc_math.isnan(gfr):
                    advanced["grad_flow_ratio"] = 9999.0
                else:
                    advanced["grad_flow_ratio"] = float(gfr)
        except Exception as e:
            pass

    # Compute rolling risk score (heuristic)
    _arc_loss_history.append(loss_val if not is_bad else _arc_loss_history[-1] if _arc_loss_history else 0.0)
    risk = 0.0
    if len(_arc_loss_history) >= 3:
        recent = _arc_loss_history[-5:]
        if recent[-1] > recent[0] * 2.0:
            risk += 0.4
        if grad_norm > 10.0:
            risk += 0.4
        if is_bad:
            risk = 1.0
    risk = min(risk, 1.0)

    risk_label = "CRITICAL" if risk > 0.8 else "HIGH" if risk > 0.5 else "MEDIUM" if risk > 0.25 else "LOW"
    _arc_emit_risk(risk, risk_label)
    _arc_emit_metric(step, epoch, loss_val if not is_bad else float('nan'), grad_norm, lr, gpu_mem, advanced)

    def rollback_fn():
        if _arc_rollback_helper[0] is not None:
            return _arc_rollback_helper[0]._restore_checkpoint()
        return 0

    def scale_lr_fn(factor):
        # Scale current optimizer
        for pg in optimizer.param_groups:
            pg['lr'] *= factor
        # Scale inside rollback helper checkpoints
        if _arc_rollback_helper[0] is not None:
            helper = _arc_rollback_helper[0]
            helper.state.current_lr *= factor
            for cp in helper.state.checkpoints:
                cp['lr'] *= factor
                if 'optimizer_state' in cp:
                    for pg in cp['optimizer_state'].get('param_groups', []):
                        pg['lr'] *= factor

    if is_bad:
        _arc_emit({"type": "failure_detected", "step": step, "loss": "NaN/Inf", "grad_norm": grad_norm})
        # Trigger LLM agent
        try:
            from arc_agent_llm import run_llm_agent
            run_llm_agent(
                step=step,
                epoch=epoch,
                loss=loss_val,
                grad_norm=grad_norm,
                lr=lr,
                loss_history=list(_arc_loss_history[-20:]),
                model=model,
                optimizer=optimizer,
                emit_thought=_arc_emit_thought,
                emit_intervention=_arc_emit_intervention,
                rollback_fn=rollback_fn,
                scale_lr_fn=scale_lr_fn,
                advanced=advanced,
            )
        except Exception as e:
            _arc_emit({"type": "log", "level": "warning", "message": f"LLM agent unavailable: {e}. Applying default recovery."})
            # Fallback: basic recovery without LLM
            _arc_emit_thought("NaN detected. Applying emergency recovery.", "action")
            try:
                steps_back = rollback_fn()
                old_lr = optimizer.param_groups[0]['lr']
                scale_lr_fn(0.3)
                new_lr = optimizer.param_groups[0]['lr']
                _arc_emit_intervention("rollback_and_reduce_lr", f"Emergency rollback of {steps_back} steps. LR {old_lr:.2e} → {new_lr:.2e}")
            except Exception:
                pass
        try:
            optimizer.zero_grad()
        except Exception:
            pass

""")


def inject_arc(source_code: str, script_path: str) -> str:
    """
    Injects ARC monitoring into the user's training script.
    Strategy: prepend the ARC preamble + hook, then add sys.path fix.
    We don't try to parse and rewrite AST (too fragile for a hackathon);
    instead we inject a monitoring hook via a trace function.
    """
    script_dir = str(Path(script_path).parent)
    python_dir = str(Path(__file__).parent)

    header = f"""
import sys
sys.path.insert(0, {repr(script_dir)})
sys.path.insert(0, {repr(python_dir)})

{ARC_PREAMBLE}

{ARC_STEP_HOOK}

# ── Monkey-patch torch.Tensor.backward to intercept every loss.backward() ──
try:
    import torch
    _original_backward = torch.Tensor.backward

    def _arc_patched_backward(self, *args, **kwargs):
        _original_backward(self, *args, **kwargs)
        try:
            loss_val = self.item()
            # Try to find model and optimizer in caller's frame
            import inspect
            frame = inspect.currentframe()
            caller_locals = {{}}
            for _ in range(5):
                if frame is None:
                    break
                caller_locals.update(frame.f_locals)
                frame = frame.f_back

            model = None
            optimizer = None
            for v in caller_locals.values():
                if isinstance(v, torch.nn.Module) and model is None:
                    model = v
                if isinstance(v, torch.optim.Optimizer) and optimizer is None:
                    optimizer = v

            if model is not None and optimizer is not None:
                _arc_on_loss(loss_val, model, optimizer)
        except Exception:
            pass

    torch.Tensor.backward = _arc_patched_backward
    _arc_emit({{"type": "log", "level": "info", "message": "ARC monitoring hook installed on PyTorch. Training is now protected."}})
except ImportError:
    _arc_emit({{"type": "log", "level": "warning", "message": "PyTorch not found. Install PyTorch to enable ARC monitoring."}})

# ═══════════════════════════════════════════════════
# BEGIN USER SCRIPT: {Path(script_path).name}
# ═══════════════════════════════════════════════════
"""
    return header + source_code


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        emit({"type": "error", "message": "Usage: runner.py <path_to_training_script.py>"})
        sys.exit(1)

    target_path = sys.argv[1]

    if not os.path.exists(target_path):
        emit({"type": "error", "message": f"File not found: {target_path}"})
        sys.exit(1)

    emit({"type": "log", "level": "info", "message": f"ARC Agent starting for: {Path(target_path).name}"})
    emit({"type": "log", "level": "info", "message": "Injecting ARC monitoring hooks..."})

    # Read user's script
    with open(target_path, "r", encoding="utf-8") as f:
        source = f.read()

    # Inject ARC
    injected_source = inject_arc(source, target_path)

    emit({"type": "log", "level": "info", "message": "Hooks injected. Launching training..."})
    emit({"type": "status", "status": "running"})

    # Execute the injected script
    try:
        exec_globals = {"__name__": "__main__", "__file__": target_path}
        exec(compile(injected_source, target_path, "exec"), exec_globals)
        emit({"type": "status", "status": "complete", "message": "Training finished successfully."})
    except SystemExit:
        emit({"type": "status", "status": "complete", "message": "Script exited."})
    except Exception as e:
        tb = traceback.format_exc()
        emit({"type": "error", "message": str(e), "traceback": tb})
        emit({"type": "status", "status": "error"})


if __name__ == "__main__":
    main()
