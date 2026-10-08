# CookMate's brain, built with LangGraph.
#
# The same agent as step 2, drawn as a graph of boxes ("nodes") and arrows:
#
#           ┌─────────┐  wants tools  ┌─────────┐
#   START → │  agent  │ ────────────→ │  tools  │
#           │ (Gemini)│ ←──────────── │ (yours) │
#           └─────────┘    results    └─────────┘
#                │ answered
#                ▼
#           ┌──────────┐
#           │ remember │ → END     (learns lasting things about you)
#           └──────────┘
#
# LangGraph runs the boxes, follows the arrows and keeps the conversation
# ("state") as it goes. We just write what each box does.

import base64
import json
import os
import re
import time

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph
from pydantic import BaseModel, Field

import agent   # system prompt + model list (also loads the .env key)
import db
import tools

MEMORY_MODEL = "gemini-flash-lite-latest"   # cheap model for the memory step


def make_llm(name):
    # max_retries=0 + timeout: if a model is busy, move on to the next quickly.
    return ChatGoogleGenerativeAI(
        model=name, api_key=os.environ["GEMINI_API_KEY"], max_retries=0, timeout=40
    )


# Tell each model about our tools (same "menu" as step 2).
TOOL_SCHEMAS = [
    {"name": d["name"], "description": d["description"], "parameters": d["parameters_json_schema"]}
    for d in tools.DECLARATIONS
]
LLMS = {name: make_llm(name).bind_tools(TOOL_SCHEMAS) for name in agent.MODELS}

# ---------------------------------------------------------------------------
# Free-tier quota: each model only allows ~20 requests a day. When one runs
# out, skip it until it resets instead of wasting time on it every message.
# ---------------------------------------------------------------------------
exhausted_until = {}
last_good_model = agent.MODELS[0]


def note_failure(name, error):
    text = str(error)
    if "RESOURCE_EXHAUSTED" in text or "429" in text:
        wait = re.search(r"retryDelay'?\"?:\s*'?\"?(\d+)s", text)
        exhausted_until[name] = time.time() + (int(wait.group(1)) if wait else 3600)


def models_to_try():
    order = [last_good_model] + [m for m in agent.MODELS if m != last_good_model]
    return [m for m in order if exhausted_until.get(m, 0) < time.time()]


# ---------------------------------------------------------------------------
# The state: what flows through the graph. MessagesState gives us a
# "messages" list; we add a slot for what the remember step learned.
# ---------------------------------------------------------------------------
class State(MessagesState):
    memory_changes: dict


# ---------------------------------------------------------------------------
# Node 1: agent - ask Gemini what to do next
# ---------------------------------------------------------------------------
def agent_node(state):
    global last_good_model
    system = SystemMessage(agent.system_prompt(db.get_memories()))
    last_error = RuntimeError("Every model is out of free quota for today - try again tomorrow!")
    for name in models_to_try():
        try:
            reply = LLMS[name].invoke([system] + state["messages"])
            if not (reply.text or reply.tool_calls):
                raise RuntimeError(f"{name} sent an empty reply")
            last_good_model = name
            reply.response_metadata["cookmate_model"] = name
            return {"messages": [reply]}
        except Exception as error:   # busy, out of quota, timed out, empty...
            note_failure(name, error)
            last_error = error
    raise last_error


# ---------------------------------------------------------------------------
# Node 2: tools - run the tools Gemini asked for
# ---------------------------------------------------------------------------
def tools_node(state):
    results = []
    for call in state["messages"][-1].tool_calls:
        result, label = tools.run(call["name"], call["args"])
        results.append(ToolMessage(
            content=json.dumps(result, ensure_ascii=False),   # what Gemini reads
            tool_call_id=call["id"],
            name=call["name"],
            # Extra info for our UI (Gemini never sees the "artifact").
            artifact={"label": label, "ingredients": tools.ingredient_names(call["name"], call["args"])},
        ))
    return {"messages": results}


# ---------------------------------------------------------------------------
# Node 3: remember - learn lasting things about the user
# ---------------------------------------------------------------------------
class MemoryUpdate(BaseModel):
    add: list[str] = Field(default_factory=list, description="New lasting facts, short third-person sentences")
    remove: list[int] = Field(default_factory=list, description="ids of saved memories that are now wrong")


MEMORY_PROMPT = """You manage the long-term memory of a cooking assistant.

Saved memories (id: text):
{saved}

The user's latest message:
"{message}"

Save ONLY lasting facts that will help in FUTURE chats: diet, allergies,
likes and dislikes, spice tolerance, how many people they usually cook for,
kitchen equipment, cooking skill, their name, and how they like to be talked
to (reply length, tone, language - e.g. "Writes in Hinglish").
Do NOT save: today's request, what's in their pantry, anything already saved.
Write each fact as a short third-person sentence, e.g. "Prefers mild spice".
If the message contradicts a saved memory, put its id in `remove` and add the
corrected fact. Most messages contain nothing worth saving - then return
empty lists."""

memory_llm = make_llm(MEMORY_MODEL).with_structured_output(MemoryUpdate)


def remember_node(state):
    message = next(m.text for m in reversed(state["messages"]) if isinstance(m, HumanMessage))
    saved = db.get_memories()
    listing = "\n".join(f"{m['id']}: {m['text']}" for m in saved) or "(none yet)"
    try:
        update = memory_llm.invoke(MEMORY_PROMPT.format(saved=listing, message=message))
    except Exception:
        return {"memory_changes": {}}   # memory is a bonus - never break the reply over it

    saved_by_id = {m["id"]: m["text"] for m in saved}
    removed = [saved_by_id[i] for i in update.remove if i in saved_by_id]
    for i in update.remove:
        if i in saved_by_id:
            db.delete_memory(i)
    known = {t.lower() for t in saved_by_id.values()}
    added = [t.strip() for t in update.add[:3] if t.strip() and t.strip().lower() not in known]
    for text in added:
        db.add_memory(text)
    return {"memory_changes": {"added": added, "removed": removed}}


# ---------------------------------------------------------------------------
# The arrows
# ---------------------------------------------------------------------------
def after_agent(state):
    """Gemini asked for tools -> run them. Otherwise it answered -> remember."""
    return "tools" if state["messages"][-1].tool_calls else "remember"


builder = StateGraph(State)
builder.add_node("agent", agent_node)
builder.add_node("tools", tools_node)
builder.add_node("remember", remember_node)
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", after_agent, ["tools", "remember"])
builder.add_edge("tools", "agent")
builder.add_edge("remember", END)
graph = builder.compile()


# ---------------------------------------------------------------------------
# Running it: turn LangGraph's stream into simple events for the server.
# ---------------------------------------------------------------------------
IMAGE_MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


def to_messages(history):
    """Our saved messages -> LangChain messages. Only the LATEST photo is sent
    to Gemini (re-sending old photos every time would waste quota)."""
    messages = []
    for i, m in enumerate(history):
        if m["role"] != "user":
            messages.append(AIMessage(m["content"]))
            continue
        text = m["content"] or "Here's a photo - what can I make?"
        if m.get("image") and i == len(history) - 1:
            data = base64.b64encode((db.DB_PATH.parent / "images" / m["image"]).read_bytes()).decode()
            mime = IMAGE_MIME[m["image"].rsplit(".", 1)[1]]
            messages.append(HumanMessage(content=[
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            ]))
        else:
            messages.append(HumanMessage(text + ("\n[sent a photo]" if m.get("image") else "")))
    return messages


def run(history):
    """Yields ("text", chunk), ("reset", full_text), ("tool", {name, label}),
    ("ingredients", [names]), ("answered", model) and ("memory", changes)."""
    messages = to_messages(history)
    shown = ""       # the reply text the browser is showing
    step_base = ""   # what was shown before the current agent step began
    try:
        # Two streams at once: "messages" = words as they're written,
        # "updates" = each node's finished output.
        for mode, data in graph.stream(
            {"messages": messages},
            stream_mode=["messages", "updates"],
            config={"recursion_limit": 14},   # safety limit on steps
        ):
            if mode == "messages":
                chunk, info = data
                if info.get("langgraph_node") != "agent" or not chunk.text:
                    continue
                piece = chunk.text
                if shown == step_base and step_base:
                    piece = "\n\n" + piece   # gap between text from different steps
                shown += piece
                yield ("text", piece)
                continue

            for node, update in data.items():
                if not update:
                    continue
                if node == "agent":
                    reply = update["messages"][-1]
                    # The finished message is the truth. If a model broke midway and
                    # another took over, fix what the browser shows.
                    correct = step_base + ("\n\n" if step_base and reply.text else "") + reply.text
                    if shown != correct:
                        shown = correct
                        yield ("reset", shown)
                    step_base = shown
                    if not reply.tool_calls:
                        yield ("answered", reply.response_metadata.get("cookmate_model"))
                elif node == "tools":
                    for result in update["messages"]:
                        yield ("tool", {"name": result.name, "label": result.artifact["label"]})
                        if result.artifact["ingredients"]:
                            yield ("ingredients", result.artifact["ingredients"])
                elif node == "remember":
                    changes = update.get("memory_changes") or {}
                    if changes.get("added") or changes.get("removed"):
                        yield ("memory", changes)
    except GraphRecursionError:
        yield ("text", "\n\nSorry, I got a bit tangled up there - could you ask that again? 🙈")
        yield ("answered", last_good_model)
