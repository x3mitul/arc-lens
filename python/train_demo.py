"""
Demo training script — intentionally uses LR=1e10 to trigger NaN loss.
This is what the user would run with: arc-agent run train_demo.py
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
import time
import os

# Simple model
model = nn.Sequential(
    nn.Linear(20, 128), nn.ReLU(),
    nn.Linear(128, 64), nn.ReLU(),
    nn.Linear(64, 10)
)

# Intentionally bad learning rate — will cause NaN within ~3 steps
optimizer = torch.optim.SGD(model.parameters(), lr=1e10, momentum=0.9)

# Synthetic data: 6400 samples, batch size 32 = 200 batches per epoch
X = torch.randn(6400, 20)
y = torch.randint(0, 10, (6400,))
loader = DataLoader(TensorDataset(X, y), batch_size=32, shuffle=True)

print("Starting training with lr=1e10 (intentionally unstable)...")

# 12 epochs * 200 batches = 2400 steps
# The delay is configurable from VS Code settings (default is 0.02s for fast visualization)
step_delay = float(os.environ.get("ARC_STEP_DELAY", "0.02"))

for epoch in range(12):
    for bx, by in loader:
        optimizer.zero_grad()
        out = model(bx)
        loss = F.cross_entropy(out, by)
        loss.backward()   # <-- ARC hook fires here
        optimizer.step()
        time.sleep(step_delay)  # Configurable delay to pace telemetry monitoring
    print(f"Epoch {epoch} done")

print("Training complete.")

