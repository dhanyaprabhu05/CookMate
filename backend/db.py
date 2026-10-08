# The database: saves every chat and message in ONE file on your laptop
# (CookMate/data/cookmate.db). Nothing is stored online.

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "cookmate.db"

STARTING_MEMORIES = [
    "Vegetarian",
    "Sometimes eats eggs, onion and garlic - it varies by dish, so ask each time",
    "Cooks in an Indian home kitchen",
]


@contextmanager
def connect():
    """Open the database, save changes when done, and always close it."""
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # lets us read rows like dictionaries
    try:
        with conn:                   # commits on success, rolls back on error
            yield conn
    finally:
        conn.close()


def init():
    """Create the two tables if they don't exist yet."""
    with connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id    TEXT NOT NULL,
                role       TEXT NOT NULL,      -- 'user' or 'assistant'
                content    TEXT NOT NULL,
                meta       TEXT,               -- e.g. 'gemini-3.5-flash · 2.1s'
                tools      TEXT,               -- JSON list of tools used for this reply
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pantry (
                item     TEXT PRIMARY KEY COLLATE NOCASE,
                added_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS memories (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        # First run only: start memory with what CookMate already knew about you.
        # (user_version is a spare number SQLite keeps for us - we use it as a flag.)
        if conn.execute("PRAGMA user_version").fetchone()[0] == 0:
            for fact in STARTING_MEMORIES:
                conn.execute("INSERT INTO memories (text, created_at) VALUES (?, ?)", (fact, time.time()))
            conn.execute("PRAGMA user_version = 1")
        # Databases made before step 2 don't have the 'tools' column yet - add it.
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(messages)")]
        if "tools" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN tools TEXT")
        if "image" not in columns:   # photos (fridge-photo feature)
            conn.execute("ALTER TABLE messages ADD COLUMN image TEXT")
        # ...and chats made before cuisine tags don't have a 'cuisine' column.
        columns = [row["name"] for row in conn.execute("PRAGMA table_info(chats)")]
        if "cuisine" not in columns:
            conn.execute("ALTER TABLE chats ADD COLUMN cuisine TEXT")


def list_chats():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM chats ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_chat(chat_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM chats WHERE id = ?", (chat_id,)).fetchone()
    return dict(row) if row else None


def create_chat(title="New chat"):
    now = time.time()
    chat = {"id": uuid.uuid4().hex, "title": title, "created_at": now, "updated_at": now, "cuisine": None}
    with connect() as conn:
        conn.execute(
            "INSERT INTO chats (id, title, created_at, updated_at) VALUES (:id, :title, :created_at, :updated_at)",
            chat,
        )
    return chat


def set_chat_cuisine(chat_id, cuisine):
    with connect() as conn:
        conn.execute("UPDATE chats SET cuisine = ? WHERE id = ?", (cuisine, chat_id))


def rename_chat(chat_id, title):
    with connect() as conn:
        conn.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))


def delete_chat(chat_id):
    with connect() as conn:
        conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


def get_messages(chat_id):
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, meta, tools, image FROM messages WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        ).fetchall()
    messages = [dict(r) for r in rows]
    for m in messages:
        m["tools"] = json.loads(m["tools"]) if m["tools"] else []
    return messages


def add_message(chat_id, role, content, meta=None, tools=None, image=None):
    now = time.time()
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content, meta, tools, image, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chat_id, role, content, meta, json.dumps(tools) if tools else None, image, now),
        )
        conn.execute("UPDATE chats SET updated_at = ? WHERE id = ?", (now, chat_id))


# --- Pantry: what you have at home -------------------------------------------

def get_pantry():
    with connect() as conn:
        rows = conn.execute("SELECT item FROM pantry ORDER BY item").fetchall()
    return [r["item"] for r in rows]


def add_pantry_item(item):
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO pantry VALUES (?, ?)", (item.strip().lower(), time.time()))


def remove_pantry_item(item):
    with connect() as conn:
        conn.execute("DELETE FROM pantry WHERE item = ?", (item.strip().lower(),))


# --- Memories: lasting things CookMate has learned about you -----------------

def get_memories():
    with connect() as conn:
        rows = conn.execute("SELECT id, text FROM memories ORDER BY id").fetchall()
    return [dict(r) for r in rows]


def add_memory(text):
    with connect() as conn:
        conn.execute("INSERT INTO memories (text, created_at) VALUES (?, ?)", (text, time.time()))


def delete_memory(memory_id):
    with connect() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
