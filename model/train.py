# Train CookMate's cuisine model: ingredients in -> cuisine out.
#
# Run from the CookMate folder:   .venv/Scripts/python model/train.py
# Add --tune to also search for the best settings (slower, ~4 min).
#
# Stages:
#   1. Load the Kaggle recipes
#   2. Split: 80% to learn from, 20% hidden for the final test
#   3. Turn ingredients into numbers (TF-IDF)
#   4. Try a few models and keep the best
#   5. Test on the hidden 20% and see what it gets wrong
#   6. Peek inside: which ingredients point to which cuisine?
#   7. Save the model

import json
import sys
import time
from collections import Counter
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline

from cuisine import MODEL_PATH, recipe_to_text

HERE = Path(__file__).resolve().parent
start = time.time()


def heading(text):
    print(f"\n{'=' * 60}\n{text}\n{'=' * 60}")


# --- 1. Load ------------------------------------------------------------------
heading("1. Loading recipes")
recipes = json.load(open(HERE / "data" / "train.json", encoding="utf-8"))
texts = [recipe_to_text(r["ingredients"]) for r in recipes]
labels = [r["cuisine"] for r in recipes]
print(f"{len(recipes)} recipes, {len(set(labels))} cuisines")
print("Example after cleaning:", texts[0])

# --- 2. Split -----------------------------------------------------------------
# The model must NEVER see the test recipes while learning - otherwise it's
# like giving students the exam answers in advance.
# stratify=labels keeps the same cuisine mix in both parts.
heading("2. Splitting 80% train / 20% hidden test")
train_x, test_x, train_y, test_y = train_test_split(
    texts, labels, test_size=0.2, random_state=42, stratify=labels
)
print(f"Learning from {len(train_x)} recipes, testing on {len(test_x)}")
most_common, count = Counter(train_y).most_common(1)[0]
print(f"Lazy baseline (always guess '{most_common}'): {Counter(test_y)[most_common] / len(test_y):.1%}")

# --- 3 & 4. Numbers + model ---------------------------------------------------
# TF-IDF gives each ingredient-word a score per recipe:
#   high if it's in this recipe but RARE overall (garam_masala -> very telling)
#   low if it's everywhere (salt, water -> tells you nothing)
# Logistic regression then learns a weight for every (word, cuisine) pair.
#
# C controls how strictly the model sticks to the training data:
#   small C = cautious, simple rules;  big C = trusts every little pattern.
# We test a few values with cross-validation: train on 4/5 of the training
# data, check on the other 1/5, repeat 5 times. The hidden test stays hidden.
#
# This search takes ~4 minutes, so it only runs with --tune.
# Last result: C=1 -> 78.0%, C=3 -> 79.0%, C=10 -> 78.5%.
best_c = 3
if "--tune" in sys.argv:
    heading("3-4. Trying different settings (cross-validation)")
    best_score = 0
    for c in [1, 3, 10]:
        candidate = make_pipeline(
            TfidfVectorizer(sublinear_tf=True),
            LogisticRegression(C=c, max_iter=2000),
        )
        score = cross_val_score(candidate, train_x, train_y, cv=5).mean()
        print(f"  C={c:<3} -> average accuracy {score:.1%}")
        if score > best_score:
            best_score, best_c = score, c
    print(f"Best: C={best_c}")
else:
    heading(f"3-4. Training (C={best_c}; run with --tune to search for the best C)")

model = make_pipeline(
    TfidfVectorizer(sublinear_tf=True),
    LogisticRegression(C=best_c, max_iter=2000),
)
model.fit(train_x, train_y)

# --- 5. Final test on the hidden 20% -------------------------------------------
heading("5. Final exam: the hidden 20%")
predicted = model.predict(test_x)
print(f"ACCURACY: {accuracy_score(test_y, predicted):.1%}\n")
print("Per cuisine (precision = when it says X, how often it's right;")
print("            recall    = of all real X recipes, how many it caught):\n")
print(classification_report(test_y, predicted, digits=2))

print("Most common mix-ups (real -> guessed):")
classes = list(model.classes_)
matrix = confusion_matrix(test_y, predicted, labels=classes)
mixups = [
    (matrix[i][j], classes[i], classes[j])
    for i in range(len(classes)) for j in range(len(classes)) if i != j
]
for n, real, guess in sorted(mixups, reverse=True)[:8]:
    print(f"  {n:4}x  {real:>12} -> {guess}")

# --- 6. Peek inside -------------------------------------------------------------
heading("6. What did it learn? Strongest clues per cuisine")
words = model.named_steps["tfidfvectorizer"].get_feature_names_out()
weights = model.named_steps["logisticregression"].coef_
for cuisine in ["indian", "chinese", "italian", "mexican", "thai", "japanese"]:
    row = weights[classes.index(cuisine)]
    top = [words[i] for i in row.argsort()[::-1][:8]]
    print(f"  {cuisine:>9}: {', '.join(top)}")

# --- 7. Save --------------------------------------------------------------------
heading("7. Saving")
# The test above gave us an honest score. Now let the final model learn from
# ALL the recipes (including the hidden 20%) - more data = slightly better.
model.fit(texts, labels)
joblib.dump(model, MODEL_PATH)
print(f"Saved to {MODEL_PATH.name} ({MODEL_PATH.stat().st_size / 1e6:.1f} MB)")
print(f"Total time: {time.time() - start:.0f}s")
