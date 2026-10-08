import { useState, type ReactNode } from "react";
import { Brain, Check, ChevronDown, Lock, Moon, Pencil, Plus, Search, ShoppingBasket, Sun, Trash2, X } from "lucide-react";
import type { Chat, Memory } from "../api";
import { groupChats } from "../lib/time";
import { Wordmark } from "./Logo";

type Props = {
  chats: Chat[];
  pantry: string[];
  onRemovePantryItem: (item: string) => void;
  memories: Memory[];
  onRemoveMemory: (id: number) => void;
  activeId: string | null;
  open: boolean;
  dark: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onToggleTheme: () => void;
};

export function Sidebar(p: Props) {
  const [query, setQuery] = useState("");
  const filtered = p.chats.filter((c) => c.title.toLowerCase().includes(query.toLowerCase()));

  return (
    <>
      {/* Dark overlay behind the sidebar on phones */}
      <div
        onClick={p.onClose}
        className={`fixed inset-0 z-30 bg-black/30 backdrop-blur-[2px] transition-opacity md:hidden ${
          p.open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[280px] flex-col border-r border-line bg-panel transition-transform duration-300 md:static md:translate-x-0 ${
          p.open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-4 pt-5 pb-4">
          <Wordmark />
          <button onClick={p.onClose} className="rounded-lg p-1.5 text-muted hover:bg-line/60 md:hidden" aria-label="Close menu">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-2 px-3">
          <button
            onClick={p.onNew}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2.5 text-sm font-semibold text-white shadow-sm shadow-accent/25 transition hover:brightness-110 active:scale-[0.98]"
          >
            <Plus size={17} strokeWidth={2.5} /> New chat
          </button>
          <label className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-sm focus-within:border-accent/60">
            <Search size={15} className="text-muted" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats"
              className="w-full bg-transparent outline-none placeholder:text-muted"
            />
          </label>
        </div>

        <nav className="mt-4 flex-1 overflow-y-auto px-2 pb-4">
          {groupChats(filtered).map((group) => (
            <div key={group.label} className="mb-4">
              <div className="px-3 pb-1.5 text-[11px] font-semibold tracking-wider text-muted uppercase">{group.label}</div>
              {group.chats.map((chat) => (
                <ChatRow key={chat.id} chat={chat} active={chat.id === p.activeId} {...p} />
              ))}
            </div>
          ))}
          {!filtered.length && (
            <p className="px-3 py-8 text-center text-sm text-muted">
              {query ? "No chats match that." : "Your chats will show up here."}
            </p>
          )}
        </nav>

        <Memories items={p.memories} onRemove={p.onRemoveMemory} />
        <Pantry items={p.pantry} onRemove={p.onRemovePantryItem} />

        <div className="flex items-center justify-between border-t border-line px-4 py-3">
          <span className="flex items-center gap-1.5 text-xs text-muted">
            <Lock size={12} /> Saved only on this laptop
          </span>
          <button
            onClick={p.onToggleTheme}
            className="rounded-lg p-2 text-muted transition hover:bg-line/60 hover:text-ink"
            aria-label="Toggle dark mode"
          >
            {p.dark ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </aside>
    </>
  );
}

const CUISINE_LABELS: Record<string, string> = { southern_us: "Southern US", cajun_creole: "Cajun" };
const cuisineLabel = (c: string) => CUISINE_LABELS[c] ?? c.charAt(0).toUpperCase() + c.slice(1);

/** A collapsible sidebar section with a title and a count. */
function Section({ icon, title, count, children }: { icon: ReactNode; title: string; count: number; children: ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border-t border-line px-3 py-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 rounded-lg px-1 py-1 text-[11px] font-semibold tracking-wider text-muted uppercase hover:text-ink"
      >
        {icon}
        {title}
        <span className="rounded-full bg-accent-soft px-1.5 py-px text-[10px] text-accent">{count}</span>
        <ChevronDown size={14} className={`ml-auto transition ${open ? "" : "-rotate-90"}`} />
      </button>
      {open && children}
    </div>
  );
}

/** What CookMate has learned about you - the LangGraph "remember" step fills this. */
function Memories({ items, onRemove }: { items: Memory[]; onRemove: (id: number) => void }) {
  return (
    <Section icon={<Brain size={14} className="text-accent" />} title="What I know about you" count={items.length}>
      <ul className="mt-2 max-h-36 space-y-0.5 overflow-y-auto px-1">
        {items.map((memory) => (
          <li key={memory.id} className="group/item animate-rise flex items-start gap-2 rounded-md py-1 text-xs leading-snug">
            <span className="mt-1.5 size-1 shrink-0 rounded-full bg-accent" />
            <span className="flex-1">{memory.text}</span>
            <button
              onClick={() => onRemove(memory.id)}
              className="rounded-full p-0.5 text-muted opacity-0 transition group-hover/item:opacity-100 hover:bg-red-500/15 hover:text-red-500 max-md:opacity-60"
              aria-label="Forget this"
              title="Forget this"
            >
              <X size={11} strokeWidth={2.5} />
            </button>
          </li>
        ))}
        {!items.length && <p className="text-xs leading-relaxed text-muted">Nothing yet. Chat a bit and I'll pick things up.</p>}
      </ul>
    </Section>
  );
}

/** What's in your kitchen - CookMate fills this in when you tell it what you bought. */
function Pantry({ items, onRemove }: { items: string[]; onRemove: (item: string) => void }) {
  return (
    <Section icon={<ShoppingBasket size={14} className="text-accent" />} title="My pantry" count={items.length}>
      <div className="mt-2 flex max-h-32 flex-wrap gap-1.5 overflow-y-auto px-1">
        {items.length ? (
          items.map((item) => (
            <span
              key={item}
              className="group/item animate-rise flex items-center gap-1 rounded-full border border-line bg-surface py-0.5 pr-1 pl-2.5 text-xs capitalize"
            >
              {item}
              <button
                onClick={() => onRemove(item)}
                className="rounded-full p-0.5 text-muted opacity-50 transition group-hover/item:opacity-100 hover:bg-red-500/15 hover:text-red-500"
                aria-label={`Remove ${item} from pantry`}
              >
                <X size={11} strokeWidth={2.5} />
              </button>
            </span>
          ))
        ) : (
          <p className="text-xs leading-relaxed text-muted">
            Empty. Tell CookMate what you have, e.g. "I bought paneer and rice".
          </p>
        )}
      </div>
    </Section>
  );
}

function ChatRow({ chat, active, onSelect, onRename, onDelete }: { chat: Chat; active: boolean } & Props) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(chat.title);

  const save = () => {
    setEditing(false);
    if (title.trim() && title !== chat.title) onRename(chat.id, title.trim());
    else setTitle(chat.title);
  };

  if (editing)
    return (
      <div className="flex items-center gap-1 rounded-lg bg-surface px-2 py-1.5 ring-1 ring-accent/50">
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") save();
            if (e.key === "Escape") {
              setTitle(chat.title);
              setEditing(false);
            }
          }}
          onBlur={save}
          className="w-full bg-transparent px-1 text-sm outline-none"
        />
        <Check size={15} className="text-accent" />
      </div>
    );

  return (
    <div
      onClick={() => onSelect(chat.id)}
      className={`group relative flex cursor-pointer items-center rounded-lg px-3 py-2 text-sm transition ${
        active ? "bg-surface font-medium shadow-sm" : "text-ink/80 hover:bg-line/50"
      }`}
    >
      {active && <span className="absolute top-2 bottom-2 left-0 w-[3px] rounded-full bg-accent" />}
      <span className="flex-1 truncate">{chat.title}</span>
      {chat.cuisine && (
        <span
          title="Tagged by your cuisine model"
          className="ml-2 shrink-0 rounded-full bg-accent-soft px-2 py-px text-[10px] font-semibold text-accent group-hover:invisible"
        >
          {cuisineLabel(chat.cuisine)}
        </span>
      )}
      {!chat.cuisine && <span className="w-12 shrink-0" />}
      <div className="absolute right-1.5 hidden gap-0.5 group-hover:flex">
        <button
          onClick={(e) => {
            e.stopPropagation();
            setTitle(chat.title);
            setEditing(true);
          }}
          className="rounded-md p-1.5 text-muted hover:bg-line hover:text-ink"
          aria-label="Rename chat"
        >
          <Pencil size={13} />
        </button>
        <button
          onClick={(e) => {
            e.stopPropagation();
            if (confirm(`Delete "${chat.title}"? This can't be undone.`)) onDelete(chat.id);
          }}
          className="rounded-md p-1.5 text-muted hover:bg-line hover:text-red-500"
          aria-label="Delete chat"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}
