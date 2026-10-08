# Shared code for the cuisine model: cleaning ingredients + making predictions.
# Used by train.py (to train) and by CookMate's backend (to predict).

import re
from functools import lru_cache
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent / "cuisine_model.joblib"

# Words that describe HOW an ingredient is prepared, not WHAT it is.
# "finely chopped fresh coriander" and "coriander" should look the same.
PREP_WORDS = {
    "fresh", "freshly", "chopped", "minced", "sliced", "diced", "grated", "shredded",
    "crushed", "large", "small", "medium", "finely", "thinly", "roughly", "whole",
    "boneless", "skinless", "low", "fat", "reduced", "sodium", "free", "lowfat",
    "nonfat", "organic", "extra", "virgin", "light", "unsalted", "salted", "plain",
    "cooked", "uncooked", "frozen", "canned", "dried", "dry", "softened", "melted",
    "peeled", "cut", "into", "pieces", "and", "or", "of", "to", "taste", "cubed",
    "oz", "lb", "lbs", "pound", "ounce", "cup", "cups", "tsp", "tbsp",
    "can", "cans", "jar", "package", "packet", "bottle", "container",
}


# The Kaggle data uses American names. Translate Indian names into them so the
# model recognises what you type ("haldi" never appears in the data).
WORD_SYNONYMS = {
    "haldi": "turmeric", "dhania": "coriander", "jeera": "cumin", "hing": "asafoetida",
    "besan": "chickpea flour", "atta": "whole wheat flour", "maida": "all purpose flour",
    "dahi": "yogurt", "sooji": "semolina", "rava": "semolina", "rajma": "kidney bean",
    "chana": "chickpea", "aloo": "potato", "gobi": "cauliflower", "palak": "spinach",
    "pyaz": "onion", "elaichi": "cardamom", "laung": "clove", "dalchini": "cinnamon",
}
PHRASE_SYNONYMS = {
    "coriander leaf": "cilantro", "coriander leave": "cilantro",
    "ginger garlic paste": "ginger garlic",
    "red chilli powder": "chili powder", "chilli powder": "chili powder",
}


def singular(word):
    """Very simple plural -> singular: tomatoes -> tomato, chillies -> chilly."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("oes"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def clean_ingredient(text):
    """'2 (15 oz.) cans Diced Tomatoes' -> 'tomato'."""
    text = text.lower()
    text = re.sub(r"\(.*?\)", " ", text)          # drop anything in brackets
    text = re.sub(r"[^a-z ]", " ", text)          # keep letters only
    words = [singular(w) for w in text.split() if w not in PREP_WORDS]
    cleaned = " ".join(WORD_SYNONYMS.get(w, w) for w in words)
    return PHRASE_SYNONYMS.get(cleaned, cleaned)


def recipe_to_text(ingredients):
    """Turn a list of ingredients into one string the model can read.

    Each ingredient's words are kept, PLUS the whole ingredient joined with
    underscores, so the model sees both 'garam' 'masala' and 'garam_masala'.
    """
    parts = []
    for ingredient in ingredients:
        cleaned = clean_ingredient(ingredient)
        if cleaned:
            parts.append(cleaned)
            if " " in cleaned:
                parts.append(cleaned.replace(" ", "_"))
    return " ".join(parts)


@lru_cache(maxsize=1)
def load_model():
    import joblib   # imported here so cleaning works without scikit-learn
    return joblib.load(MODEL_PATH)


def predict(ingredients, top=3):
    """Return the most likely cuisines, e.g. [('indian', 0.91), ('thai', 0.03), ...]."""
    model = load_model()
    probabilities = model.predict_proba([recipe_to_text(ingredients)])[0]
    ranked = sorted(zip(model.classes_, probabilities), key=lambda pair: -pair[1])
    return [(cuisine, round(float(p), 3)) for cuisine, p in ranked[:top]]
