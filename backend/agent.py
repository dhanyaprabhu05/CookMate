# The agent: CookMate's personality + the code that talks to Gemini.

import logging
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

import db
import tools

logging.getLogger("google_genai").setLevel(logging.ERROR)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Fail fast: no retries and a 40s time limit. If a model is busy we
# immediately move on to the next one instead of waiting.
client = genai.Client(
    http_options=types.HttpOptions(
        retry_options=types.HttpRetryOptions(attempts=1), timeout=40_000
    )
)

# Models to try in order - if one is busy, use the next.
MODELS = [
    "gemini-3.6-flash",
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
]
TITLE_MODEL = "gemini-flash-lite-latest"

# The model that worked last time - we try it first next time.
last_good_model = MODELS[0]

# The system prompt: instructions Gemini follows for the whole chat.
# {memories} is filled in with what CookMate has learned about you.
SYSTEM_PROMPT = """
You are CookMate, a warm, cheerful cooking buddy. You talk like a friendly
friend who loves food - casual, encouraging, a light emoji now and then.

## What you remember about them (learned from past chats)
{memories}
Use these naturally - adjust spice, servings, tone and suggestions to fit.
Match their way of talking (e.g. if they write short messages or mix Hindi
and English, do the same). Don't list these memories back unless asked.

## Asking before cooking
When they ask for a recipe or meal idea, check whether you know, FOR THIS DISH:
  1. How many people it's for
  2. Whether eggs are okay this time - ONLY if this dish could sensibly
     use eggs (e.g. baking, fried rice, breakfast, desserts). Never ask
     about eggs for dishes like paneer curries or dal.
  3. Whether onion and garlic are okay this time - ONLY if this dish
     normally uses them.
If something relevant is missing, DON'T give the recipe yet. Reply with one short
friendly sentence, then ask only the missing questions, each on its own line
in exactly this format:
<<ask: Question? | Option 1 | Option 2 | Option 3>>
Keep options short (1-4 words), 2-4 options per question. Example:
<<ask: How many people are eating? | Just me | 2 | 4 | 6>>
<<ask: Onion & garlic this time? | Yes, both | Only onion | Only garlic | Neither>>
If they already told you everything, skip the questions and cook.
If they're only asking for ideas, you may suggest dishes first and ask later.

## Giving recipes
- Scale every quantity exactly to the number of people.
- Use Indian kitchen measures (tsp, tbsp, cups) and grams/ml in brackets.
- Structure: a one-line intro, **Ingredients** (grouped), **Steps** (numbered,
  with heat level and time for each step), then a short **Tips** section.
- Be clear and concise - no long stories.

## Your tools - use them, don't guess
- scale_recipe: for EVERY recipe. Think of the recipe at its natural base
  size (e.g. for 2 or 4), then call scale_recipe to get the exact amounts for
  the number of people. Use ONLY the amounts it returns - never do the maths
  yourself. (Skip it if the base size already equals the number of people.)
- convert_units: whenever they ask to convert a quantity.
- update_pantry: when their LATEST message says they bought, have, used up
  or ran out of something. Never repeat updates from earlier messages - those
  are already saved. Confirm briefly what you updated.
- get_pantry: when they ask what they have, or what they can cook with it.
- make_grocery_list: after working out a recipe, call it with the ingredient
  names, then end the recipe with a short "🛒 To buy" section listing only
  what's missing (grouped as returned). If nothing is missing, say so.
- guess_cuisine: this is the user's OWN model that they trained - be proud
  of it! Use it when they list ingredients and ask what to make, or ask what
  cuisine something is. Mention its guess naturally, e.g. "Your cuisine model
  says this leans Thai (84%)", then use it to suggest dishes. If its top
  guess looks wrong (it was trained on American recipe data), say so kindly.
Don't mention tool names to the user - just use the results naturally.

## Photos
If they send a photo of their fridge, shelves, groceries or ingredients:
1. Briefly list the ingredients you can clearly see. Skip anything you're
   unsure about (or mark it with "?"). Don't invent things hidden from view.
2. Call update_pantry to add them (simple names: "tomato", "paneer", "milk").
3. Call guess_cuisine with them, then suggest 2-3 dishes they could make,
   fitting what you remember about them. Offer to give the full recipe.
4. Mention they can remove anything you got wrong with the × in My pantry.
If it's a photo of a cooked dish, say what it looks like and offer a recipe.

## Other topics
You can chat about anything briefly, but you're happiest talking food.
"""



def system_prompt(memories):
    """Fill the system prompt with the memories from the database."""
    listing = "\n".join(f"- {m['text']}" for m in memories) or "- Nothing yet."
    return SYSTEM_PROMPT.replace("{memories}", listing)


# ---------------------------------------------------------------------------
# THE HAND-WRITTEN AGENT LOOP (step 2)
# The app now uses graph.py (LangGraph) instead. This is kept so you can
# compare the two - it's the same idea, written by hand.
# ---------------------------------------------------------------------------

def make_config(memories):
    return types.GenerateContentConfig(
        system_instruction=system_prompt(memories),
        tools=[types.Tool(function_declarations=tools.DECLARATIONS)],
        # We run the tools ourselves (that's the agent loop below), so turn off
        # the library's automatic tool-running.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


MAX_STEPS = 6   # safety limit so the agent can't loop forever


def to_gemini(history):
    """Convert our saved messages into the format Gemini expects.
    Gemini calls the assistant 'model' instead of 'assistant'."""
    return [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in history
    ]


class FailedMidway(Exception):
    """A model broke AFTER it had started writing its reply."""

    def __init__(self, model, error):
        super().__init__(str(error))
        self.model, self.error = model, error


def ask_model(contents, models, config):
    """ONE call to Gemini, streamed. Tries each model until one works.

    Yields ("text", chunk) as words arrive, then ("done", (model, parts))
    where parts is everything the model sent - text AND tool requests.
    """
    last_error = None
    for model in models:
        parts, started = [], False
        try:
            for chunk in client.models.generate_content_stream(
                model=model, contents=contents, config=config
            ):
                candidate = chunk.candidates[0] if chunk.candidates else None
                if not candidate or not candidate.content or not candidate.content.parts:
                    continue
                for part in candidate.content.parts:
                    parts.append(part)
                    if part.text and not part.thought:
                        started = True
                        yield ("text", part.text)
            if not any(part.text or part.function_call for part in parts):
                raise RuntimeError(f"{model} sent an empty reply")
            yield ("done", (model, parts))
            return
        # Busy (503), too slow, connection dropped, empty reply... any failure
        # means: try the next model.
        except Exception as error:
            if started:
                raise FailedMidway(model, error)
            last_error = error
    raise last_error


def run_agent(history):
    """THE AGENT LOOP.

      1. Send the conversation to Gemini.
      2. If Gemini asks to use tools -> run them, add the results to the
         conversation, and go back to 1.
      3. If Gemini just answers with text -> we're done.

    Yields ("text", chunk), ("tool", {name, label}), ("ingredients", [names])
    when a tool was given a recipe's ingredients, ("reset", n) meaning
    "delete the last n characters" (a model broke midway and we're redoing
    that step), and finally ("model", name).
    """
    global last_good_model
    contents = to_gemini(history)
    config = make_config(db.get_memories())
    wrote_text = False

    for step in range(MAX_STEPS):
        # Try the model that worked last first, then the others as backups.
        models = [last_good_model] + [m for m in MODELS if m != last_good_model]
        while True:
            parts, written = [], 0   # written = characters sent during this attempt
            try:
                for kind, value in ask_model(contents, models, config):
                    if kind == "text":
                        if written == 0 and wrote_text:
                            value = "\n\n" + value   # gap between text from different steps
                        written += len(value)
                        yield ("text", value)
                    else:
                        model, parts = value
                break
            except FailedMidway as failure:
                # Undo the half-written text and redo this step with another model.
                models = [m for m in models if m != failure.model]
                if not models:
                    raise failure.error
                yield ("reset", written)
        wrote_text = wrote_text or written > 0
        last_good_model = model

        calls = [part.function_call for part in parts if part.function_call]
        if not calls:
            yield ("model", model)
            return

        # Gemini asked for tools. Remember its request, run each tool,
        # then hand the results back so it can continue.
        contents.append(types.Content(role="model", parts=parts))
        results = []
        for call in calls:
            args = dict(call.args or {})
            result, label = tools.run(call.name, args)
            yield ("tool", {"name": call.name, "label": label})
            # Remember recipe ingredients so we can tag the chat's cuisine.
            names = tools.ingredient_names(call.name, args)
            if names:
                yield ("ingredients", names)
            results.append(types.Part.from_function_response(name=call.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=results))

    yield ("text", "\n\nSorry, I got a bit tangled up there - could you ask that again? 🙈")
    yield ("model", model)


def make_title(first_message):
    """Ask a small, fast model for a short title for the sidebar."""
    try:
        response = client.models.generate_content(
            model=TITLE_MODEL,
            contents=(
                "Write a 2-5 word title for a cooking chat that starts with the "
                "message below. Reply with only the title - no quotes, no emoji.\n\n"
                + first_message
            ),
        )
        title = (response.text or "").strip().strip('"').strip()
        if title:
            return title[:60]
    except genai.errors.APIError:
        pass
    return first_message[:40] + ("…" if len(first_message) > 40 else "")
