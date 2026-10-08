# Try your cuisine models side by side.
#
# Run from the CookMate folder:
#   .venv/Scripts/python model/try_models.py          -> type ingredients, see both models' guesses
#   .venv/Scripts/python model/try_models.py --exam   -> score both on the hidden 20% test recipes

import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.model_selection import train_test_split

from cuisine import load_model, recipe_to_text

HERE = Path(__file__).resolve().parent
NN_PATH = HERE / "cuisine_nn.joblib"


def load_nn():
    """The neural network, or None if train_nn.py hasn't been run yet."""
    if not NN_PATH.exists():
        return None
    import torch
    from net import CuisineNet

    saved = joblib.load(NN_PATH)
    net = CuisineNet(len(saved["vectorizer"].vocabulary_), len(saved["classes"]), saved["hidden"], saved["dropout"])
    net.load_state_dict(saved["state"])
    net.eval()

    def probabilities(texts):
        x = torch.tensor(saved["vectorizer"].transform(texts).toarray(), dtype=torch.float32)
        with torch.no_grad():
            return torch.softmax(net(x), dim=1).numpy()

    return saved["classes"], probabilities


def top3(classes, probs):
    order = np.argsort(probs)[::-1][:3]
    return ", ".join(f"{classes[i]} {probs[i]:.0%}" for i in order)


lr = load_model()
nn = load_nn()
if nn is None:
    print("(No neural network found - run model/train_nn.py first. Showing logistic regression only.)\n")

if "--exam" in sys.argv:
    # Same hidden 20% as the training scripts (same split settings).
    recipes = json.load(open(HERE / "data" / "train.json", encoding="utf-8"))
    texts = [recipe_to_text(r["ingredients"]) for r in recipes]
    labels = [r["cuisine"] for r in recipes]
    _, test_x, _, test_y = train_test_split(texts, labels, test_size=0.2, random_state=42, stratify=labels)
    print(f"Exam: {len(test_x)} hidden recipes\n")
    # Note: train.py's saved model has seen these recipes (it retrains on everything
    # before saving), so its score here is inflated. train.py's printed score is the honest one.
    print(f"  Logistic regression: {np.mean(lr.predict(test_x) == np.array(test_y)):.1%}  (inflated - see note)")
    if nn:
        classes, probabilities = nn
        guesses = np.array(classes)[probabilities(test_x).argmax(axis=1)]
        print(f"  Neural network:      {np.mean(guesses == np.array(test_y)):.1%}  (honest - never saw these)")
    sys.exit()

print("Type ingredients separated by commas (or 'quit').")
print("Example: paneer, tomato, cream, garam masala\n")
while True:
    line = input("Ingredients: ").strip()
    if line.lower() in ("quit", "exit", "q", ""):
        break
    text = recipe_to_text([i.strip() for i in line.split(",")])
    print(f"  Logistic regression: {top3(list(lr.classes_), lr.predict_proba([text])[0])}")
    if nn:
        classes, probabilities = nn
        print(f"  Neural network:      {top3(classes, probabilities([text])[0])}")
    print()
