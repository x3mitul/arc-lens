"""
ARC Agent — Local Reasoning Brain
================================
Called by runner.py when ARC detects a training failure.
Implements a deterministic ReAct loop mimicking an LLM agent offline.
All reasoning is streamed back as JSON events via the emit functions.
"""

import time
import json
import math
from typing import Callable, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions
# ─────────────────────────────────────────────────────────────────────────────

def _tool_rollback(model, optimizer, emit_thought, emit_intervention, rollback_fn=None, scale_lr_fn=None) -> dict:
    """Roll back to previous healthy checkpoint and reduce LR."""
    try:
        old_lr = optimizer.param_groups[0]["lr"]
        steps_back = 0
        if rollback_fn is not None:
            steps_back = rollback_fn()
        if scale_lr_fn is not None:
            scale_lr_fn(0.2)
        else:
            for pg in optimizer.param_groups:
                pg["lr"] *= 0.2
        new_lr = optimizer.param_groups[0]["lr"]
        emit_intervention("rollback_and_reduce_lr",
                          f"Emergency rollback of {steps_back} steps. LR {old_lr:.2e} → {new_lr:.2e}")
        return {"success": True, "steps_back": steps_back, "old_lr": old_lr, "new_lr": new_lr}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_reduce_lr(model, optimizer, emit_thought, emit_intervention, factor: float = 0.5, scale_lr_fn=None) -> dict:
    """Reduce the learning rate by a given factor."""
    try:
        old_lr = optimizer.param_groups[0]["lr"]
        if scale_lr_fn is not None:
            scale_lr_fn(factor)
        else:
            for pg in optimizer.param_groups:
                pg["lr"] *= factor
        new_lr = optimizer.param_groups[0]["lr"]
        emit_intervention("reduce_lr", f"LR {old_lr:.2e} → {new_lr:.2e} (factor={factor})")
        return {"success": True, "old_lr": old_lr, "new_lr": new_lr}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _tool_enable_grad_clipping(model, optimizer, emit_intervention, max_norm: float = 1.0) -> dict:
    """Register gradient clipping (informational — caller must apply it)."""
    emit_intervention("enable_grad_clipping", f"max_norm={max_norm}")
    return {"success": True, "max_norm": max_norm,
            "note": "Apply torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm) before optimizer.step()"}


def _tool_snapshot(step, epoch, loss, grad_norm, lr, loss_history, advanced=None) -> dict:
    """Return the current training snapshot for the agent to reason about."""
    is_nan = math.isnan(loss) or math.isinf(loss)
    trend = "rising" if len(loss_history) >= 3 and loss_history[-1] > loss_history[-3] else "stable"
    snapshot = {
        "step": step,
        "epoch": epoch,
        "loss": "NaN/Inf" if is_nan else round(loss, 6),
        "is_nan_or_inf": is_nan,
        "grad_norm": round(grad_norm, 4),
        "learning_rate": lr,
        "loss_trend": trend,
        "recent_losses": [round(l, 4) for l in loss_history[-8:]],
    }
    if advanced:
        snapshot["advanced_telemetry"] = advanced
    return snapshot


# ─────────────────────────────────────────────────────────────────────────────
# ARC Local ReAct Agent Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def run_llm_agent(
    step: int,
    epoch: int,
    loss: float,
    grad_norm: float,
    lr: float,
    loss_history: List[float],
    model,
    optimizer,
    emit_thought: Callable,
    emit_intervention: Callable,
    max_rounds: int = 5,
    rollback_fn: Optional[Callable] = None,
    scale_lr_fn: Optional[Callable] = None,
    advanced: Optional[dict] = None,
):
    """
    Entry point called by runner.py when a failure is detected.
    Runs the local ReAct loop and applies recovery tools.
    """
    _run_local_react_agent(
        step=step,
        epoch=epoch,
        loss=loss,
        grad_norm=grad_norm,
        lr=lr,
        loss_history=loss_history,
        model=model,
        optimizer=optimizer,
        emit_thought=emit_thought,
        emit_intervention=emit_intervention,
        rollback_fn=rollback_fn,
        scale_lr_fn=scale_lr_fn,
        advanced=advanced
    )


def _run_local_react_agent(
    step: int,
    epoch: int,
    loss: float,
    grad_norm: float,
    lr: float,
    loss_history: List[float],
    model,
    optimizer,
    emit_thought: Callable,
    emit_intervention: Callable,
    rollback_fn: Optional[Callable] = None,
    scale_lr_fn: Optional[Callable] = None,
    advanced: Optional[dict] = None,
):
    """Local offline ReAct agent that simulates the thought loop and applies tools deterministically."""
    emit_thought("Failure detected. Initialising ARC reasoning agent...", "perception")
    time.sleep(0.5)
    
    emit_thought("Calling tool: get_training_snapshot(None)", "action")
    snapshot = _tool_snapshot(step, epoch, loss, grad_norm, lr, loss_history, advanced)
    time.sleep(0.4)
    emit_thought(f"Tool result: {json.dumps(snapshot)}", "observation")
    time.sleep(0.5)
    
    is_nan = math.isnan(loss) or math.isinf(loss)
    has_recovered = False
    
    # 1. NaN/Inf recovery
    if is_nan:
        emit_thought(
            "Analysis: The training loss has diverged to NaN/Inf. This is a critical numerical failure "
            "often caused by high learning rates or exploding gradients. I need to roll back to the last "
            "healthy checkpoint and aggressively scale down the learning rate.",
            "reasoning"
        )
        time.sleep(0.6)
        emit_thought("Calling tool: rollback_and_reduce_lr(None)", "action")
        res = _tool_rollback(model, optimizer, emit_thought, emit_intervention, rollback_fn=rollback_fn, scale_lr_fn=scale_lr_fn)
        time.sleep(0.4)
        emit_thought(f"Tool result: {json.dumps(res)}", "observation")
        has_recovered = True
        time.sleep(0.5)
        
    # 2. Gradient explosion recovery
    if grad_norm > 50.0:
        emit_thought(
            f"Analysis: Gradient L2 norm ({grad_norm:.2f}) exceeds stable threshold (>50). This indicates "
            "gradient explosion. I will enable gradient clipping to restrict updating step size.",
            "reasoning"
        )
        time.sleep(0.6)
        emit_thought("Calling tool: enable_gradient_clipping({'max_norm': 1.0})", "action")
        res = _tool_enable_grad_clipping(model, optimizer, emit_intervention, max_norm=1.0)
        time.sleep(0.4)
        emit_thought(f"Tool result: {json.dumps(res)}", "observation")
        time.sleep(0.5)

    # 3. Structural/Advanced Telemetry recovery
    if advanced:
        weight_update_ratio = advanced.get("weight_update_ratio", 0.0)
        effective_rank = advanced.get("effective_rank", 8.0)
        
        if weight_update_ratio > 0.05:
            emit_thought(
                f"Analysis: Weight update ratio ({weight_update_ratio:.4f}) is high (>0.05). The weights are "
                "changing too fast per step, risking optimization divergence. Reducing learning rate.",
                "reasoning"
            )
            time.sleep(0.6)
            emit_thought("Calling tool: reduce_learning_rate({'factor': 0.5})", "action")
            res = _tool_reduce_lr(model, optimizer, emit_thought, emit_intervention, factor=0.5, scale_lr_fn=scale_lr_fn)
            time.sleep(0.4)
            emit_thought(f"Tool result: {json.dumps(res)}", "observation")
            has_recovered = True
            time.sleep(0.5)
            
        elif effective_rank < 3.0:
            emit_thought(
                f"Analysis: Mean effective rank ({effective_rank:.2f}) has dropped significantly, indicating "
                "representation collapse (layer rank deficiency). Scaling down learning rate to regularize representations.",
                "reasoning"
            )
            time.sleep(0.6)
            emit_thought("Calling tool: reduce_learning_rate({'factor': 0.5})", "action")
            res = _tool_reduce_lr(model, optimizer, emit_thought, emit_intervention, factor=0.5, scale_lr_fn=scale_lr_fn)
            time.sleep(0.4)
            emit_thought(f"Tool result: {json.dumps(res)}", "observation")
            has_recovered = True
            time.sleep(0.5)

    # If nothing was triggered but we ended up here, apply fallback rollback just in case
    if not has_recovered and is_nan:
        _apply_fallback_recovery(optimizer, emit_thought, emit_intervention, rollback_fn, scale_lr_fn)
        
    emit_thought("Calling tool: continue_training(None)", "action")
    time.sleep(0.3)
    emit_thought("Recovery complete. Resuming training.", "action")
    emit_thought(f"Tool result: {json.dumps({'status': 'resuming'})}", "observation")


def _apply_fallback_recovery(optimizer, emit_thought, emit_intervention, rollback_fn=None, scale_lr_fn=None):
    """Executes the standard rule-based recovery if the agent fails."""
    try:
        steps_back = 0
        if rollback_fn is not None:
            steps_back = rollback_fn()
        old_lr = optimizer.param_groups[0]["lr"]
        if scale_lr_fn is not None:
            scale_lr_fn(0.2)
        else:
            for pg in optimizer.param_groups:
                pg["lr"] *= 0.2
        new_lr = optimizer.param_groups[0]["lr"]
        emit_intervention("rollback_and_reduce_lr",
                          f"Fallback: Emergency rollback of {steps_back} steps. LR {old_lr:.2e} → {new_lr:.2e}")
    except Exception as e:
        emit_thought(f"Fallback recovery error: {e}", "error")
