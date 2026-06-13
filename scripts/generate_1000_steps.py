import json
import random
import time

events = []
events.append({"type": "log", "level": "info", "message": "ARC Agent starting for: train_demo.py"})
events.append({"type": "log", "level": "info", "message": "Injecting ARC monitoring hooks..."})
events.append({"type": "status", "status": "running"})

lr = 1e-3
loss = 4.5
grad_norm = 2.0
epoch = 0

for step in range(1, 1001):
    if step % 100 == 0:
        epoch += 1

    # Simulate random chance of failure
    if step in [150, 420, 780]:
        events.append({"type": "metric", "step": step, "epoch": epoch, "loss": None, "grad_norm": 9.2e10, "lr": lr, "gpu_mem_mb": 8500.0})
        events.append({"type": "failure_detected", "step": step, "loss": "NaN/Inf", "grad_norm": 9.2e10})
        
        lr *= 0.5 # Intervention
        events.append({"type": "intervention", "action": "rollback_and_reduce_lr", "detail": f"Emergency rollback. LR reduced to {lr:.2e}"})
        
        # stabilize
        loss = loss * 1.5
        grad_norm = 1.0
        continue
    
    # Normal smooth training
    loss = loss * 0.995 + random.uniform(-0.05, 0.05)
    loss = max(0.1, loss)
    
    grad_norm = grad_norm * 0.98 + random.uniform(0.01, 0.2)
    
    events.append({
        "type": "metric", 
        "step": step, 
        "epoch": epoch, 
        "loss": round(loss, 4), 
        "grad_norm": round(grad_norm, 4), 
        "lr": lr, 
        "gpu_mem_mb": 8500.0 + random.uniform(-50, 50)
    })
    
    # risk score calculation
    score = 0.0
    if grad_norm > 5.0: score = 0.4
    if grad_norm > 15.0: score = 0.8
    label = "LOW" if score < 0.5 else ("HIGH" if score < 0.9 else "CRITICAL")
    
    if step % 10 == 0:
        events.append({"type": "risk", "score": score, "label": label})

events.append({"type": "status", "status": "complete", "message": "Training finished successfully."})

with open("media/demo_dashboard.html", "r") as f:
    content = f.read()

import re
# Find the events array and replace it
json_str = json.dumps(events)
new_content = re.sub(r'const events = \[.*?\];', f'const events = {json_str};', content, flags=re.DOTALL)

with open("media/demo_dashboard.html", "w") as f:
    f.write(new_content)

print("Generated 1000 step simulation and injected into demo_dashboard.html")
