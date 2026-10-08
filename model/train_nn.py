# Train a NEURAL NETWORK cuisine model and compare it with the first model.
#
# Run from the CookMate folder:   .venv/Scripts/python model/train_nn.py
#
# Uses the exact same 80/20 split as train.py, so the scores are a fair fight.

import json
import time
from pathlib import Path

import joblib
import numpy as np
import torch
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from torch import nn

from cuisine import recipe_to_text
from net import CuisineNet

HERE = Path(__file__).resolve().parent
NN_PATH = HERE / "cuisine_nn.joblib"

torch.set_num_threads(2)   # use only 2 of your CPU cores - keeps the laptop usable
torch.manual_seed(42)      # same random start every run, so results repeat

# Settings ("hyperparameters") - things YOU choose, not things it learns.
HIDDEN = 512        # neurons in the middle layer
DROPOUT = 0.5       # fraction of neurons switched off during training
LEARNING_RATE = 1e-3
BATCH_SIZE = 256    # recipes looked at before each small weight update
MAX_EPOCHS = 20     # one epoch = one pass over all training recipes
PATIENCE = 3        # stop if validation hasn't improved for this many epochs

start = time.time()

# --- 1. Data: same split as train.py ---------------------------------------
recipes = json.load(open(HERE / "data" / "train.json", encoding="utf-8"))
texts = [recipe_to_text(r["ingredients"]) for r in recipes]
labels = [r["cuisine"] for r in recipes]
train_x, test_x, train_y, test_y = train_test_split(
    texts, labels, test_size=0.2, random_state=42, stratify=labels
)
# Take 10% of the training recipes as a "validation" set: checked after every
# epoch to decide when to stop. The real test set stays hidden until the end.
train_x, val_x, train_y, val_y = train_test_split(
    train_x, train_y, test_size=0.1, random_state=42, stratify=train_y
)

# --- 2. Turn text into numbers (same TF-IDF idea as before) ------------------
vectorizer = TfidfVectorizer(sublinear_tf=True)
X_train = vectorizer.fit_transform(train_x)
X_val, X_test = vectorizer.transform(val_x), vectorizer.transform(test_x)

classes = sorted(set(labels))
index = {c: i for i, c in enumerate(classes)}
y_train = torch.tensor([index[c] for c in train_y])
y_val = np.array([index[c] for c in val_y])
y_test = np.array([index[c] for c in test_y])
print(f"{X_train.shape[0]} training recipes, {X_train.shape[1]} input features, {len(classes)} cuisines")


def as_tensor(sparse_rows):
    return torch.tensor(sparse_rows.toarray(), dtype=torch.float32)


def accuracy(net, X, y):
    net.eval()                 # evaluation mode: dropout OFF
    correct = 0
    with torch.no_grad():      # no learning here, just predicting
        for i in range(0, X.shape[0], 1024):
            guesses = net(as_tensor(X[i:i + 1024])).argmax(dim=1).numpy()
            correct += (guesses == y[i:i + 1024]).sum()
    return correct / len(y)


# --- 3. Build the network ----------------------------------------------------
net = CuisineNet(X_train.shape[1], len(classes), HIDDEN, DROPOUT)
n_weights = sum(p.numel() for p in net.parameters())
print(f"Network has {n_weights:,} weights to learn (your first model had ~{X_train.shape[1] * len(classes):,})")

loss_fn = nn.CrossEntropyLoss()   # how wrong is each guess? (lower = better)
optimizer = torch.optim.Adam(net.parameters(), lr=LEARNING_RATE, weight_decay=1e-5)

# --- 4. The training loop ----------------------------------------------------
# For each small batch of recipes:
#   forward:  the network guesses the cuisines
#   loss:     measure how wrong the guesses were
#   backward: work out how each weight contributed to the mistakes
#   step:     nudge every weight a little in the direction that reduces mistakes
print(f"\n{'epoch':>5} {'train loss':>11} {'val acc':>8} {'time':>6}")
best_val, best_state, bad_epochs = 0, None, 0
for epoch in range(1, MAX_EPOCHS + 1):
    epoch_start = time.time()
    net.train()                                  # training mode: dropout ON
    order = torch.randperm(X_train.shape[0])     # shuffle recipes every epoch
    total_loss = 0.0
    for i in range(0, len(order), BATCH_SIZE):
        batch = order[i:i + BATCH_SIZE].numpy()
        guesses = net(as_tensor(X_train[batch]))       # forward
        loss = loss_fn(guesses, y_train[batch])        # loss
        optimizer.zero_grad()
        loss.backward()                                # backward
        optimizer.step()                               # step
        total_loss += loss.item() * len(batch)

    val_acc = accuracy(net, X_val, y_val)
    marker = ""
    if val_acc > best_val:
        best_val, bad_epochs, marker = val_acc, 0, "  ← best so far"
        best_state = {k: v.clone() for k, v in net.state_dict().items()}
    else:
        bad_epochs += 1
    print(f"{epoch:>5} {total_loss / len(order):>11.3f} {val_acc:>8.1%} {time.time() - epoch_start:>5.0f}s{marker}")
    if bad_epochs >= PATIENCE:
        print(f"Validation stopped improving - stopping early (this avoids overfitting).")
        break

net.load_state_dict(best_state)

# --- 5. Final exam on the hidden 20% ----------------------------------------
test_acc = accuracy(net, X_test, y_test)
print(f"\nNEURAL NETWORK accuracy on hidden test: {test_acc:.1%}")
print("First model (logistic regression):      78.8%")

# --- 6. Save -------------------------------------------------------------------
joblib.dump(
    {"vectorizer": vectorizer, "classes": classes, "state": best_state,
     "hidden": HIDDEN, "dropout": DROPOUT, "test_accuracy": float(test_acc)},
    NN_PATH,
)
print(f"Saved to {NN_PATH.name} ({NN_PATH.stat().st_size / 1e6:.0f} MB) | total time {time.time() - start:.0f}s")
