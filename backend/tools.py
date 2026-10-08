# CookMate's tools: normal Python functions the AI can decide to call.
#
# Two parts:
#   1. The functions themselves (plain Python - exact maths, database).
#   2. DECLARATIONS - a "menu" that tells Gemini what each tool does and
#      what inputs it needs. Gemini reads the menu, decides which tool to
#      use, and WE run the function and hand back the result.

import sys
from pathlib import Path

import db

# Your own trained model lives in CookMate/model/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))
import cuisine  # noqa: E402

# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

UNIT_ALIASES = {
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp",
    "cup": "cup", "cups": "cup",
    "ml": "ml", "millilitre": "ml", "milliliter": "ml", "millilitres": "ml",
    "l": "l", "litre": "l", "liter": "l", "litres": "l", "liters": "l",
    "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "pound": "lb", "pounds": "lb",
}
VOLUME_ML = {"tsp": 5, "tbsp": 15, "cup": 240, "ml": 1, "l": 1000}
WEIGHT_G = {"g": 1, "kg": 1000, "oz": 28.35, "lb": 453.6}

# Grams per ml - lets us convert cups <-> grams. Approximate kitchen values.
DENSITY = {
    "water": 1.0, "milk": 1.03, "curd": 1.03, "yogurt": 1.03, "cream": 1.0,
    "oil": 0.92, "ghee": 0.91, "butter": 0.96, "honey": 1.42,
    "sugar": 0.85, "powdered sugar": 0.5, "jaggery": 0.9, "salt": 1.2,
    "atta": 0.53, "wheat flour": 0.53, "maida": 0.53, "flour": 0.53,
    "besan": 0.38, "gram flour": 0.38, "rava": 0.7, "sooji": 0.7, "semolina": 0.7,
    "rice": 0.8, "basmati": 0.78, "poha": 0.3, "oats": 0.38,
    "dal": 0.8, "toor dal": 0.8, "moong dal": 0.8, "masoor dal": 0.8,
    "chana": 0.75, "rajma": 0.75, "cashew": 0.55, "peanut": 0.6,
    "cocoa": 0.42, "tomato puree": 1.05,
}


def unit_of(unit):
    return UNIT_ALIASES.get(unit.strip().lower().rstrip("."), unit.strip().lower())


def nice(x, step):
    """Round x to the nearest step and write it nicely, e.g. 1.5 -> '1 ½'."""
    x = max(round(x / step) * step, step)
    whole, frac = int(x), round(x - int(x), 2)
    symbol = {0.25: "¼", 0.5: "½", 0.75: "¾"}.get(frac)
    if symbol:
        return f"{whole} {symbol}" if whole else symbol
    return f"{x:g}" if step < 1 else str(round(x))


def format_amount(qty, unit):
    """Round a quantity sensibly for its unit (nobody measures 7.3 g of salt)."""
    if unit == "tsp" and qty >= 3:
        qty, unit = qty / 3, "tbsp"
    if unit == "g" and qty >= 1000:
        qty, unit = qty / 1000, "kg"
    if unit == "ml" and qty >= 1000:
        qty, unit = qty / 1000, "l"

    if unit in ("tsp", "tbsp", "cup"):
        amount = nice(qty, 0.25)
    elif unit in ("g", "ml"):
        amount = nice(qty, 1 if qty < 20 else 5 if qty < 200 else 10)
    elif unit in ("kg", "l"):
        amount = f"{round(qty, 2):g}"
    else:  # pieces, cloves, pinches, "medium" onions...
        # Half an onion makes sense; 7 ½ tomatoes doesn't - round bigger counts.
        amount = nice(qty, 0.5 if qty < 3 else 1)
    if unit == "cup" and qty > 1:
        unit = "cups"
    return f"{amount} {unit}".strip()


# ---------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------

def scale_recipe(ingredients, from_servings, to_servings):
    factor = to_servings / from_servings
    scaled = []
    for item in ingredients:
        unit = unit_of(item.get("unit") or "")
        try:
            amount = format_amount(float(item["quantity"]) * factor, unit)
        except (KeyError, TypeError, ValueError):
            amount = "to taste"   # e.g. salt with no number - nothing to scale
        scaled.append({"name": item.get("name", "?"), "amount": amount})
    return {"factor": round(factor, 3), "servings": to_servings, "ingredients": scaled}


def convert_units(quantity, from_unit, to_unit, ingredient=""):
    src, dst = unit_of(from_unit), unit_of(to_unit)
    # Same kind of unit (volume->volume or weight->weight): simple maths.
    for table in (VOLUME_ML, WEIGHT_G):
        if src in table and dst in table:
            value = quantity * table[src] / table[dst]
            return {"result": f"{round(value, 2):g} {dst}"}

    # Volume <-> weight: needs the ingredient's density.
    name = ingredient.lower()
    density = next((d for key, d in sorted(DENSITY.items(), key=lambda kv: -len(kv[0])) if key in name), None)
    if density is None:
        return {"error": f"Don't know the density of '{ingredient}' - tell the user it's an estimate."}
    if src in VOLUME_ML and dst in WEIGHT_G:
        value = quantity * VOLUME_ML[src] * density / WEIGHT_G[dst]
    elif src in WEIGHT_G and dst in VOLUME_ML:
        value = quantity * WEIGHT_G[src] / density / VOLUME_ML[dst]
    else:
        return {"error": f"Can't convert {from_unit} to {to_unit}."}
    return {"result": f"{round(value, 2):g} {dst}", "note": "approximate - depends on how it's packed"}


def get_pantry():
    return {"items": db.get_pantry()}


def update_pantry(add=None, remove=None):
    for item in add or []:
        db.add_pantry_item(item)
    for item in remove or []:
        db.remove_pantry_item(item)
    return {"items": db.get_pantry()}


CATEGORIES = {
    "🥬 Vegetables & fruits": ["onion", "tomato", "potato", "spinach", "palak", "capsicum", "carrot", "peas",
                              "chilli", "chili pepper", "ginger", "garlic", "coriander leaves", "cilantro", "lemon",
                              "lime", "mint", "curry leaves", "cauliflower", "beans", "cabbage", "mushroom", "banana",
                              "apple", "cucumber", "brinjal", "okra", "bhindi", "methi leaves"],
    "🥛 Dairy & eggs": ["milk", "paneer", "curd", "yogurt", "cream", "butter", "ghee", "cheese", "egg", "khoya"],
    "🌾 Grains, flours & dals": ["rice", "atta", "flour", "maida", "besan", "rava", "sooji", "poha", "oats", "dal",
                                "chana", "rajma", "pasta", "noodles", "bread", "semolina"],
    "🌶️ Spices & masalas": ["salt", "turmeric", "haldi", "masala", "cumin", "jeera", "mustard", "chilli powder",
                            "chili powder", "coriander powder", "cardamom", "clove", "cinnamon", "bay leaf", "hing",
                            "asafoetida", "kasuri methi", "pepper", "saffron", "fenugreek", "ajwain", "fennel"],
    "🥜 Nuts & dry fruits": ["cashew", "kaju", "almond", "badam", "raisin", "kishmish", "peanut", "pistachio",
                            "walnut", "dates", "coconut"],
}


def category_of(name):
    lowered = name.lower()
    # Check spices first so "chilli powder" isn't filed under vegetables.
    for cat in ["🌶️ Spices & masalas", "🥛 Dairy & eggs", "🌾 Grains, flours & dals", "🥜 Nuts & dry fruits",
                "🥬 Vegetables & fruits"]:
        if any(word in lowered for word in CATEGORIES[cat]):
            return cat
    return "🧂 Other"


def make_grocery_list(ingredients):
    pantry = [p.lower() for p in db.get_pantry()]
    have, to_buy = [], {}
    for name in ingredients:
        lowered = name.lower()
        if any(p in lowered or lowered in p for p in pantry):
            have.append(name)
        else:
            to_buy.setdefault(category_of(name), []).append(name)
    return {"to_buy": to_buy, "already_have": have}


def guess_cuisine(ingredients):
    """Ask YOUR trained model which cuisine these ingredients belong to."""
    guesses = cuisine.predict(ingredients, top=3)
    return {"guesses": [{"cuisine": c.replace("_", " "), "confidence": f"{p:.0%}"} for c, p in guesses]}


# ---------------------------------------------------------------------------
# The "menu" Gemini sees (JSON Schema describing each tool's inputs)
# ---------------------------------------------------------------------------

INGREDIENT_LIST = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "e.g. 'basmati rice' or 'onion (medium)'"},
            "quantity": {"type": "number"},
            "unit": {"type": "string", "description": "tsp, tbsp, cup, g, ml, pcs, cloves, pinch... or '' for whole items"},
        },
        "required": ["name", "quantity", "unit"],
    },
}

DECLARATIONS = [
    {
        "name": "scale_recipe",
        "description": "Exactly scale recipe ingredient quantities from one number of servings to another, "
                       "with sensible kitchen rounding. ALWAYS use this for recipe quantities instead of doing maths yourself.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "ingredients": INGREDIENT_LIST,
                "from_servings": {"type": "number", "description": "servings the base quantities are for"},
                "to_servings": {"type": "number", "description": "servings the user wants"},
            },
            "required": ["ingredients", "from_servings", "to_servings"],
        },
    },
    {
        "name": "convert_units",
        "description": "Convert a kitchen quantity between units, e.g. cups to grams or tbsp to ml. "
                       "Give the ingredient for volume<->weight conversions.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "quantity": {"type": "number"},
                "from_unit": {"type": "string"},
                "to_unit": {"type": "string"},
                "ingredient": {"type": "string", "description": "e.g. 'basmati rice', 'sugar'"},
            },
            "required": ["quantity", "from_unit", "to_unit"],
        },
    },
    {
        "name": "get_pantry",
        "description": "See which ingredients the user currently has at home.",
        "parameters_json_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "update_pantry",
        "description": "Add or remove items from the user's pantry when they say they bought, have, "
                       "used up or ran out of something.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "add": {"type": "array", "items": {"type": "string"}},
                "remove": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "make_grocery_list",
        "description": "Compare a recipe's ingredient names with the user's pantry. Returns what they "
                       "already have and what to buy, grouped by shop section.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {
                "ingredients": {"type": "array", "items": {"type": "string"}, "description": "ingredient names only"},
            },
            "required": ["ingredients"],
        },
    },
]

DECLARATIONS.append({
    "name": "guess_cuisine",
    "description": "CookMate's own machine-learning model (trained by the user on ~40,000 recipes). "
                   "Predicts which cuisine a list of ingredients belongs to, with confidence. "
                   "Knows 20 cuisines: Indian, Chinese, Thai, Italian, Mexican, Japanese, Korean, "
                   "French, Greek, Spanish, Vietnamese, Moroccan, etc. No Indo-Chinese category.",
    "parameters_json_schema": {
        "type": "object",
        "properties": {"ingredients": {"type": "array", "items": {"type": "string"}}},
        "required": ["ingredients"],
    },
})

FUNCTIONS = {
    "guess_cuisine": guess_cuisine,
    "scale_recipe": scale_recipe,
    "convert_units": convert_units,
    "get_pantry": get_pantry,
    "update_pantry": update_pantry,
    "make_grocery_list": make_grocery_list,
}


def describe(name, args, result):
    """A short human label for the UI, e.g. 'Scaled recipe 2 → 6 people'."""
    if name == "scale_recipe":
        return f"Scaled recipe {args.get('from_servings', '?'):g} → {args.get('to_servings', '?'):g} people"
    if name == "convert_units":
        out = result.get("result", "?")
        qty, unit = args.get("quantity", 0), unit_of(args.get("from_unit", ""))
        if unit == "cup" and qty > 1:
            unit = "cups"
        return f"Converted {qty:g} {unit} → {out}"
    if name == "get_pantry":
        return f"Checked your pantry ({len(result['items'])} items)"
    if name == "update_pantry":
        changes = [f"+{a}" for a in args.get("add") or []] + [f"−{r}" for r in args.get("remove") or []]
        return "Updated pantry: " + ", ".join(changes)
    if name == "guess_cuisine":
        top = result["guesses"][0]
        return f"Your model: {top['cuisine'].title()} ({top['confidence']})"
    if name == "make_grocery_list":
        count = sum(len(v) for v in result["to_buy"].values())
        return f"Made grocery list ({count} to buy, {len(result['already_have'])} at home)"
    return name


def ingredient_names(name, args):
    """If this tool call contained a recipe's ingredients, return their names."""
    items = args.get("ingredients") if name in ("scale_recipe", "make_grocery_list", "guess_cuisine") else None
    if not items:
        return []
    return [item["name"] if isinstance(item, dict) else str(item) for item in items]


def tag_cuisine(ingredients):
    """Ask your model for the chat's cuisine tag - only if it's at least 50% sure."""
    top, confidence = cuisine.predict(ingredients, top=1)[0]
    return top if confidence >= 0.5 else None


def run(name, args):
    """Run the tool Gemini asked for. Returns (result, label)."""
    function = FUNCTIONS.get(name)
    if not function:
        return {"error": f"No tool called {name}"}, name
    try:
        result = function(**args)
    except Exception as error:   # bad inputs from the AI shouldn't crash the app
        return {"error": str(error)}, f"{name} failed"
    return result, describe(name, args, result)
