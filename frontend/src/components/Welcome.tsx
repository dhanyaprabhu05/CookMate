import { greeting } from "../lib/time";
import { Avatar } from "./Logo";

const SUGGESTIONS = [
  { emoji: "⚡", title: "Quick dinner", text: "Something quick and easy for dinner tonight" },
  { emoji: "🧈", title: "Paneer butter masala", text: "Paneer butter masala for 4 people" },
  { emoji: "🍚", title: "Leftover rice", text: "What can I make with leftover rice?" },
  { emoji: "🍪", title: "No-oven dessert", text: "A sweet treat I can make without an oven" },
];

export function Welcome({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col items-center justify-center px-4 py-10 text-center">
      <div className="animate-rise">
        <Avatar size={56} />
      </div>
      <h1
        className="animate-rise mt-6 font-display text-4xl leading-tight font-medium tracking-tight sm:text-5xl"
        style={{ animationDelay: "60ms" }}
      >
        {greeting()}, <span className="italic text-accent">chef</span>.
      </h1>
      <p className="animate-rise mt-3 text-muted" style={{ animationDelay: "120ms" }}>
        What are we cooking today?
      </p>

      <div className="mt-10 grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((s, i) => (
          <button
            key={s.title}
            onClick={() => onPick(s.text)}
            className="animate-rise group flex items-start gap-3 rounded-2xl border border-line bg-surface p-4 text-left transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-lg hover:shadow-accent/5"
            style={{ animationDelay: `${180 + i * 60}ms` }}
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent-soft text-lg transition group-hover:scale-110">
              {s.emoji}
            </span>
            <span>
              <span className="block text-sm font-semibold">{s.title}</span>
              <span className="mt-0.5 block text-sm text-muted">{s.text}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
