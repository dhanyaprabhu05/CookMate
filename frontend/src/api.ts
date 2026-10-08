// Everything the web app needs from the Python backend.

export type Chat = {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  cuisine?: string | null; // tagged by your own model
};

export type ToolStep = { name: string; label: string };

export type Memory = { id: number; text: string };

export type Message = {
  id?: number;
  role: "user" | "assistant";
  content: string;
  meta?: string | null;
  tools?: ToolStep[]; // tools CookMate used for this reply
  learned?: string[]; // memories saved after this reply
  image?: string | null; // photo you sent (URL or data URL)
  pending?: boolean; // still streaming in
  error?: string;
};

export type StreamEvent =
  | { type: "delta"; text: string }
  | { type: "tool"; name: string; label: string }
  | { type: "reset"; content: string }
  | { type: "done"; meta: string }
  | { type: "title"; title: string }
  | { type: "cuisine"; cuisine: string }
  | { type: "memory"; added: string[]; removed: string[] }
  | { type: "error"; message: string };

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export const api = {
  listChats: () => fetch("/api/chats").then(json<Chat[]>),
  createChat: () => fetch("/api/chats", { method: "POST" }).then(json<Chat>),
  messages: (id: string) => fetch(`/api/chats/${id}/messages`).then(json<Message[]>),
  rename: (id: string, title: string) =>
    fetch(`/api/chats/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    }).then(json<Chat>),
  remove: (id: string) => fetch(`/api/chats/${id}`, { method: "DELETE" }).then(json),
  pantry: () => fetch("/api/pantry").then(json<string[]>),
  memories: () => fetch("/api/memories").then(json<Memory[]>),
  removeMemory: (id: number) => fetch(`/api/memories/${id}`, { method: "DELETE" }).then(json<Memory[]>),
  removePantryItem: (item: string) =>
    fetch(`/api/pantry/${encodeURIComponent(item)}`, { method: "DELETE" }).then(json<string[]>),
};

/** Send a message and receive the reply live, piece by piece. */
export async function sendMessage(
  chatId: string,
  content: string,
  image: string | null,
  onEvent: (event: StreamEvent) => void,
) {
  const res = await fetch(`/api/chats/${chatId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, image }),
  });
  if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    // Events are separated by a blank line: "data: {...}\n\n"
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const line = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      if (line.startsWith("data: ")) onEvent(JSON.parse(line.slice(6)));
    }
  }
}
