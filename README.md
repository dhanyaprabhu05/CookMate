# 🍳 CookMate

An AI cooking buddy that asks before it cooks, does exact kitchen maths, remembers what you like, reads photos of your fridge — and uses a cuisine classifier I trained myself.

Built with **LangGraph + Gemini**, a **FastAPI** backend, a **React** frontend, and a **scikit-learn** model trained on ~40,000 recipes.

## Features

- **Asks before cooking** — servings, eggs, onion & garlic — as tappable answer chips, and only when relevant (no egg question for dal)
- **Agent with tools** — the AI decides when to call real Python functions:
  - ⚖️ `scale_recipe` — exact quantity scaling with kitchen-sensible rounding (½ an onion, not 7½ tomatoes)
  - 🔄 `convert_units` — cups ↔ grams using ingredient densities
  - 🧺 `get_pantry` / ✏️ `update_pantry` — remembers what's in your kitchen
  - 🛒 `make_grocery_list` — recipe vs pantry: what you have, what to buy
  - 🧠 `guess_cuisine` — **my own trained model** (see below)
- **Long-term memory** — learns lasting facts ("prefers mild spice", "no oven") and uses them in every chat; viewable and deletable in the sidebar
- **Fridge photo → recipes** — send a photo; it identifies ingredients, fills the pantry, asks the cuisine model and suggests dishes
- **Chat app** — streaming replies, chat history with search / rename / delete, auto titles, cuisine tags, light & dark mode
- **Private by design** — chats, photos, pantry and memories stay in a local SQLite file (messages still go to the Gemini API to get replies)
- **Resilient on the free tier** — falls back across 5 Gemini models, skips models that are out of daily quota, and recovers from replies that fail midway

## How it works

```
                      React app (Vite, Tailwind)
                               │  Server-Sent Events (streaming)
                               ▼
                      FastAPI server ── SQLite (chats, pantry, memories, photos)
                               │
                               ▼
             LangGraph agent
   START → [ agent ] ⇄ [ tools ]          agent = Gemini decides what to do
               │ answered                  tools = Python functions + my ML model
               ▼
          [ remember ] → END               remember = extracts lasting facts
```

## The cuisine model

A text classifier that predicts one of 20 cuisines from a list of ingredients.

| | |
|---|---|
| Data | Kaggle *Recipe Ingredients Dataset* ("What's Cooking?"), 39,774 labelled recipes |
| Approach | Ingredient cleaning + Indian-name translation (haldi → turmeric) → TF-IDF → logistic regression |
| Accuracy | **78.8%** on a hidden 20% test set (baseline "always Italian": 19.7%) |
| Size / speed | 1.4 MB, ~1 ms per prediction, ~15 s to train on a laptop CPU |

**Neural network experiment:** a PyTorch MLP (3.5M weights, 25× bigger) scored the same 78.8%; an ensemble reached 79.1%. Both models fail on the *same* 18.9% of recipes — ambiguous or mislabelled ones — so the bottleneck is the data, not the model. The app keeps the smaller model.

## Run it

Requirements: Python 3.11+, Node.js 20+, a free Gemini API key from [aistudio.google.com](https://aistudio.google.com).

```bash
# 1. Python environment
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt      # Windows
# .venv/bin/python -m pip install -r requirements.txt        # macOS / Linux

# 2. Your API key
cp .env.example .env        # then paste your key into .env

# 3. Frontend packages
cd frontend
npm install

# 4. Start everything (backend + frontend, opens the browser)
npm start
```

**Retraining the cuisine model** needs the Kaggle dataset (not included): download it, unzip `train.json` into `model/data/`, then:

```bash
.venv/Scripts/python model/train.py            # ~15 s  (add --tune to search settings, ~4 min)
.venv/Scripts/python model/train_nn.py         # neural network experiment (needs: pip install torch)
.venv/Scripts/python model/try_models.py       # type ingredients, compare both models
```

## Project structure

```
backend/
  main.py      API endpoints + streaming
  graph.py     the LangGraph agent (agent → tools → remember)
  agent.py     system prompt, chat titles, and the original hand-written agent loop (for comparison)
  tools.py     the agent's tools
  db.py        SQLite storage
frontend/src/  React app (App, Sidebar, MessageBubble, Composer, ...)
model/
  cuisine.py   ingredient cleaning + predictions
  train.py     logistic regression training & evaluation
  net.py, train_nn.py   neural network experiment
step1_hello.py the very first Gemini call this project started from
```

## What I learned

- An **agent** is a model that can *ask* to use tools — your code runs them and hands back results. I wrote the loop by hand first, then rebuilt it with LangGraph.
- **Exact maths belongs in code**, not in the language model.
- **Hide a test set and beat a baseline**, or an accuracy number means nothing.
- **Data quality caps model quality**: mislabelled recipes and American ingredient names mattered more than model size.
- Free-tier APIs fail a lot — fallbacks, quota tracking and recovery are real engineering work.
