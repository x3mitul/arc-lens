"""
A PyTorch training script for ARC Lens to monitor.
Architecture: 3-layer MLP with BatchNorm and Dropout, trained on a 
non-linearly separable synthetic dataset (two interleaved Gaussian clusters).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
import time
import os
import math


torch.manual_seed(42)


N = 10000
FEATURES = 32


centres_0 = torch.tensor([[ 1.5,  1.5], [-1.5, -1.5]])
centres_1 = torch.tensor([[ 1.5, -1.5], [-1.5,  1.5]])

def _make_cluster(centres, n, scale=0.6):
    pts = []
    for c in centres:
        pts.append(torch.randn(n // len(centres), 2) * scale + c)
    return torch.cat(pts, dim=0)

X_2d_0 = _make_cluster(centres_0, N // 2)
X_2d_1 = _make_cluster(centres_1, N // 2)
X_2d = torch.cat([X_2d_0, X_2d_1], dim=0)
y = torch.cat([torch.zeros(N // 2, dtype=torch.long),
               torch.ones(N // 2, dtype=torch.long)], dim=0)

torch.manual_seed(7)
_proj = torch.randn(2, FEATURES) / math.sqrt(2)
X = X_2d @ _proj + torch.randn(N, FEATURES) * 0.1  # small noise

# Shuffle
perm = torch.randperm(N)
X, y = X[perm], y[perm]

# Split
n_train = int(N * 0.85)
X_train, y_train = X[:n_train], y[:n_train]
X_val,   y_val   = X[n_train:], y[n_train:]

BATCH_SIZE = 32
train_loader = DataLoader(
    TensorDataset(X_train, y_train),
    batch_size=BATCH_SIZE,
    shuffle=True,
    drop_last=True,
)

class ArcDemoMLP(nn.Module):
    """
    3-hidden-layer MLP with BatchNorm and Dropout.
    Architecture: 32 -> 256 -> 128 -> 64 -> 2
    """
    def __init__(self, in_features: int = FEATURES, num_classes: int = 2):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_features, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),

            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.15),

            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),

            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


model = ArcDemoMLP()


NUM_EPOCHS = 12
STEPS_PER_EPOCH = len(train_loader)
TOTAL_STEPS = NUM_EPOCHS * STEPS_PER_EPOCH

BASE_LR = 3e-3
WARMUP_STEPS = max(1, STEPS_PER_EPOCH // 2)       # warmup for first half epoch
NAN_INJECTION_STEP = 400                            # step at which we simulate failure

optimizer = torch.optim.Adam(
    model.parameters(),
    lr=BASE_LR,
    weight_decay=1e-4,
)

# CosineAnnealing over the full run
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
    optimizer,
    T_max=TOTAL_STEPS - WARMUP_STEPS,
    eta_min=BASE_LR * 0.01,
)

step_delay = float(os.environ.get("ARC_STEP_DELAY", "0.03"))


_grad_clip_enabled = False
_grad_clip_max_norm = 1.0


print("ARC Lens Demo — Starting training session.")
print(f"  Dataset: {N} samples | {FEATURES} features | 2 classes (XOR clusters)")
print(f"  Model: ArcDemoMLP (32->256->128->64->2) | Params: "
      f"{sum(p.numel() for p in model.parameters()):,}")
print(f"  Epochs: {NUM_EPOCHS} | Steps/epoch: {STEPS_PER_EPOCH} | "
      f"Total steps: {TOTAL_STEPS}")
print(f"  Optimizer: Adam (lr={BASE_LR}) | Schedule: CosineAnnealing")
print(f"  Failure injection at step {NAN_INJECTION_STEP}")
print()

global_step = 0
best_val_acc = 0.0
_nan_injected = False
training_start_time = time.time()

for epoch in range(NUM_EPOCHS):

    try:
        _arc_epoch[0] = epoch  # noqa: F821  — injected by runner.py
    except NameError:
        pass  

    model.train()
    epoch_loss = 0.0
    epoch_correct = 0
    epoch_total = 0

    for batch_idx, (bx, by) in enumerate(train_loader):
        global_step += 1


        if global_step == NAN_INJECTION_STEP and not _nan_injected:
            _nan_injected = True
            print(f"[Step {global_step}] SIMULATED DATA CORRUPTION: "
                  "injecting NaN into input batch to trigger ARC recovery.")
            # Corrupt the entire first sample — guarantees NaN propagates
            # through BatchNorm and produces NaN loss
            bx[0, :] = float("nan")

        optimizer.zero_grad()
        out = model(bx)
        loss = F.cross_entropy(out, by)

        # ARC Lens monitors this backward() call
        loss.backward()

        # Apply gradient clipping if ARC enabled it after recovery
        try:
            if _arc_intervention_count[0] > 0:
                _grad_clip_enabled = True
        except NameError:
            pass

        if _grad_clip_enabled:
            nn.utils.clip_grad_norm_(model.parameters(), _grad_clip_max_norm)

        optimizer.step()

        if global_step <= WARMUP_STEPS:
            # Linear warmup from BASE_LR * 0.1 → BASE_LR
            warmup_factor = 0.1 + 0.9 * (global_step / WARMUP_STEPS)
            for pg in optimizer.param_groups:
                pg["lr"] = BASE_LR * warmup_factor
        else:
            scheduler.step()

        loss_val = loss.item()
        if math.isfinite(loss_val):
            epoch_loss += loss_val
            with torch.no_grad():
                preds = out.argmax(dim=1)
                epoch_correct += (preds == by).sum().item()
                epoch_total += len(by)


        elapsed = time.time() - training_start_time
        target_elapsed = (global_step / TOTAL_STEPS) * 130.0
        sleep_needed = max(step_delay, target_elapsed - elapsed)
        time.sleep(sleep_needed)

    avg_loss = epoch_loss / max(1, epoch_total // BATCH_SIZE)
    train_acc = 100.0 * epoch_correct / max(1, epoch_total)

    # Validation pass
    model.eval()
    val_correct = 0
    with torch.no_grad():
        val_out = model(X_val)
        val_correct = (val_out.argmax(dim=1) == y_val).sum().item()
    val_acc = 100.0 * val_correct / len(y_val)
    model.train()

    if val_acc > best_val_acc:
        best_val_acc = val_acc

    current_lr = optimizer.param_groups[0]["lr"]
    print(
        f"[Epoch {epoch + 1}/{NUM_EPOCHS}] "
        f"avg_loss={avg_loss:.4f} | "
        f"train_acc={train_acc:.1f}% | "
        f"val_acc={val_acc:.1f}% | "
        f"lr={current_lr:.2e}"
    )

print()
print("Training complete.")
print(f"  Best validation accuracy: {best_val_acc:.1f}%")
print("  ARC Lens monitored the full run and applied recovery where needed.")
