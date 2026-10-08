import { useEffect, useRef, useState } from "react";
import { Menu, SquarePen } from "lucide-react";
import { api, sendMessage, type Chat, type Memory, type Message } from "./api";
import { Composer } from "./components/Composer";
import { MessageBubble } from "./components/MessageBubble";
import { Sidebar } from "./components/Sidebar";
import { Welcome } from "./components/Welcome";

export default function App() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [pantry, setPantry] = useState<string[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [busy, setBusy] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const bottomRef = useRef<HTMLDivElement>(null);

  // Load the chat list and pantry once when the app opens.
  useEffect(() => {
    api.listChats().then(setChats).catch(() => {});
    api.pantry().then(setPantry).catch(() => {});
    api.memories().then(setMemories).catch(() => {});
  }, []);

  // Keep the newest message in view.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const toggleTheme = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("cookmate-theme", next ? "dark" : "light");
    } catch {}
  };

  const openChat = async (id: string) => {
    setMenuOpen(false);
    if (id === activeId) return;
    setActiveId(id);
    setMessages([]);
    setMessages(await api.messages(id));
  };

  const newChat = () => {
    setMenuOpen(false);
    setActiveId(null);
    setMessages([]);
  };

  // Update the last message (the one CookMate is currently writing).
  const patchLast = (change: (m: Message) => Partial<Message>) =>
    setMessages((all) => [...all.slice(0, -1), { ...all[all.length - 1], ...change(all[all.length - 1]) }]);

  const send = async (text: string, image: string | null = null) => {
    if (busy) return;
    setBusy(true);
    setMessages((all) => [
      ...all,
      { role: "user", content: text, image },
      { role: "assistant", content: "", pending: true },
    ]);

    try {
      // A brand-new chat is only created when you send the first message.
      let id = activeId;
      if (!id) {
        const chat = await api.createChat();
        id = chat.id;
        setActiveId(id);
        setChats((all) => [chat, ...all]);
      }
      const chatId = id;

      await sendMessage(chatId, text, image, (event) => {
        if (event.type === "delta") patchLast((m) => ({ content: m.content + event.text }));
        if (event.type === "reset") patchLast(() => ({ content: event.content }));
        if (event.type === "tool") {
          patchLast((m) => ({ tools: [...(m.tools ?? []), { name: event.name, label: event.label }] }));
          if (event.name === "update_pantry") api.pantry().then(setPantry);
        }
        if (event.type === "done") patchLast(() => ({ pending: false, meta: event.meta }));
        if (event.type === "error") patchLast(() => ({ pending: false, error: event.message }));
        if (event.type === "title")
          setChats((all) => all.map((c) => (c.id === chatId ? { ...c, title: event.title } : c)));
        if (event.type === "memory") {
          if (event.added.length) patchLast(() => ({ learned: event.added }));
          api.memories().then(setMemories);
        }
        if (event.type === "cuisine")
          setChats((all) => all.map((c) => (c.id === chatId ? { ...c, cuisine: event.cuisine } : c)));
      });
      // Move this chat to the top of the sidebar.
      setChats((all) => {
        const chat = all.find((c) => c.id === chatId);
        return chat ? [{ ...chat, updated_at: Date.now() / 1000 }, ...all.filter((c) => c.id !== chatId)] : all;
      });
    } catch (error) {
      patchLast(() => ({ pending: false, error: String(error) }));
    } finally {
      setBusy(false);
    }
  };

  const rename = async (id: string, title: string) => {
    const chat = await api.rename(id, title);
    setChats((all) => all.map((c) => (c.id === id ? chat : c)));
  };

  const remove = async (id: string) => {
    await api.remove(id);
    setChats((all) => all.filter((c) => c.id !== id));
    if (id === activeId) newChat();
  };

  const title = chats.find((c) => c.id === activeId)?.title;

  return (
    <div className="flex h-full">
      <Sidebar
        chats={chats}
        pantry={pantry}
        onRemovePantryItem={(item) => api.removePantryItem(item).then(setPantry)}
        memories={memories}
        onRemoveMemory={(id) => api.removeMemory(id).then(setMemories)}
        activeId={activeId}
        open={menuOpen}
        dark={dark}
        onClose={() => setMenuOpen(false)}
        onSelect={openChat}
        onNew={newChat}
        onRename={rename}
        onDelete={remove}
        onToggleTheme={toggleTheme}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line/70 px-3 md:px-6">
          <button onClick={() => setMenuOpen(true)} className="rounded-lg p-2 text-muted hover:bg-line/60 md:hidden" aria-label="Open menu">
            <Menu size={19} />
          </button>
          <h2 className="flex-1 truncate font-display text-lg font-medium">{title ?? "New chat"}</h2>
          <button onClick={newChat} className="rounded-lg p-2 text-muted hover:bg-line/60 hover:text-ink md:hidden" aria-label="New chat">
            <SquarePen size={18} />
          </button>
        </header>

        <div className="flex flex-1 flex-col overflow-y-auto">
          {messages.length === 0 ? (
            <Welcome onPick={send} />
          ) : (
            <div className="mx-auto w-full max-w-3xl flex-1 space-y-7 px-4 py-8">
              {messages.map((m, i) => (
                <MessageBubble
                  key={m.id ?? `local-${i}`}
                  message={m}
                  isLast={i === messages.length - 1}
                  busy={busy}
                  onAnswer={send}
                />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <Composer busy={busy} onSend={send} />
      </main>
    </div>
  );
}
