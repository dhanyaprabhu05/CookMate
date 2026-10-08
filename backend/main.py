# The server: the web app talks to these URLs ("endpoints").
# Run with:  uvicorn main:app --app-dir backend --port 8000

import base64
import binascii
import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

import agent
import db
import graph
import tools

db.init()
app = FastAPI(title="CookMate")
background = ThreadPoolExecutor(max_workers=2)   # for small side jobs (chat titles)

# Photos you send are saved here, on your laptop (next to the database).
IMAGES_DIR = db.DB_PATH.parent / "images"
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
IMAGE_NAME = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
MAX_IMAGE_BYTES = 6_000_000


class NewMessage(BaseModel):
    content: str = ""
    image: str | None = None   # a photo as a "data URL": data:image/jpeg;base64,....


def save_image(data_url):
    """Decode a data URL from the browser and save it. Returns the file name."""
    match = re.match(r"^data:(image/[a-z]+);base64,(.+)$", data_url, re.DOTALL)
    if not match or match.group(1) not in IMAGE_TYPES:
        raise HTTPException(400, "Photo must be a JPEG, PNG or WebP image")
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except binascii.Error:
        raise HTTPException(400, "Photo data is broken")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Photo is too big")
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{IMAGE_TYPES[match.group(1)]}"
    (IMAGES_DIR / name).write_bytes(data)
    return name


def with_image_urls(messages):
    """Turn stored image file names into URLs the browser can load."""
    for m in messages:
        m["image"] = f"/api/images/{m['image']}" if m.get("image") else None
    return messages


class Rename(BaseModel):
    title: str


def sse(data):
    """Format one Server-Sent Event: the browser reads these as they arrive."""
    return f"data: {json.dumps(data)}\n\n"


def require_chat(chat_id):
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "Chat not found")
    return chat


@app.get("/api/pantry")
def get_pantry():
    return db.get_pantry()


@app.delete("/api/pantry/{item}")
def remove_pantry_item(item: str):
    db.remove_pantry_item(item)
    return db.get_pantry()


@app.get("/api/memories")
def get_memories():
    return db.get_memories()


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    db.delete_memory(memory_id)
    return db.get_memories()


@app.get("/api/chats")
def list_chats():
    return db.list_chats()


@app.post("/api/chats")
def create_chat():
    return db.create_chat()


@app.get("/api/chats/{chat_id}/messages")
def get_messages(chat_id: str):
    require_chat(chat_id)
    return with_image_urls(db.get_messages(chat_id))


@app.get("/api/images/{name}")
def get_image(name: str):
    if not IMAGE_NAME.match(name) or not (IMAGES_DIR / name).exists():
        raise HTTPException(404, "Photo not found")
    return FileResponse(IMAGES_DIR / name)


@app.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, body: Rename):
    require_chat(chat_id)
    db.rename_chat(chat_id, body.title.strip()[:80] or "Untitled")
    return db.get_chat(chat_id)


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    # Delete the chat's photos from disk too - deleting a chat should really delete it.
    for m in db.get_messages(chat_id):
        if m.get("image"):
            (IMAGES_DIR / m["image"]).unlink(missing_ok=True)
    db.delete_chat(chat_id)
    return {"ok": True}


@app.post("/api/chats/{chat_id}/messages")
def send_message(chat_id: str, body: NewMessage):
    require_chat(chat_id)
    text = body.content.strip()
    if not text and not body.image:
        raise HTTPException(400, "Message is empty")
    image = save_image(body.image) if body.image else None

    is_first_message = not db.get_messages(chat_id)
    db.add_message(chat_id, "user", text, image=image)
    history = db.get_messages(chat_id)

    # First message: name the chat in the background, at the same time as the
    # reply. It saves itself, so it still works if you close the page early.
    title_job = None
    if is_first_message:
        def name_chat():
            title = agent.make_title(text or "A photo of my fridge / ingredients")
            db.rename_chat(chat_id, title)
            return title
        title_job = background.submit(name_chat)

    def events():
        """Stream the reply to the browser as it's generated (Server-Sent Events)."""
        start = time.time()
        reply, used_tools, ingredients, answered = "", [], [], False
        try:
            for kind, value in graph.run(history):
                if kind == "text":
                    reply += value
                    yield sse({"type": "delta", "text": value})
                elif kind == "reset":
                    # A model broke midway and another took over - fix the text.
                    reply = value
                    yield sse({"type": "reset", "content": reply})
                elif kind == "tool":
                    used_tools.append(value)
                    yield sse({"type": "tool", **value})
                elif kind == "ingredients":
                    ingredients = value
                elif kind == "answered":
                    # The reply is finished - save it and tell the browser right
                    # away (the memory step carries on afterwards).
                    answered = True
                    meta = f"{value} · {time.time() - start:.1f}s"
                    db.add_message(chat_id, "assistant", reply, meta, used_tools)
                    yield sse({"type": "done", "meta": meta})
                    yield from after_reply(ingredients)
                elif kind == "memory":
                    yield sse({"type": "memory", **value})
        except Exception as error:
            if not answered:   # after answering, a failure here isn't worth showing
                yield sse({"type": "error", "message": str(error)[:200]})

    def after_reply(ingredients):
        """Extras once the reply is saved: cuisine tag and chat title."""
        # Your model tags the chat with the recipe's cuisine.
        if ingredients:
            cuisine = tools.tag_cuisine(ingredients)
            if cuisine:
                db.set_chat_cuisine(chat_id, cuisine)
                yield sse({"type": "cuisine", "cuisine": cuisine})

        if title_job:
            yield sse({"type": "title", "title": title_job.result()})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
