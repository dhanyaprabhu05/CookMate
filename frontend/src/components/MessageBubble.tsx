import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy, TriangleAlert } from "lucide-react";
import type { Message, ToolStep } from "../api";
import { parseAsks } from "../lib/asks";
import { AskCard } from "./AskCard";
import { Avatar } from "./Logo";

type Props = {
  message: Message;
  isLast: boolean;
  busy: boolean;
  onAnswer: (text: string) => void;
};

export function MessageBubble({ message, isLast, busy, onAnswer }: Props) {
  if (message.role === "user")
    return (
      <div className="animate-rise flex flex-col items-end gap-2">
        {message.image && (
          <a href={message.image} target="_blank" rel="noreferrer">
            <img
              src={message.image}
              alt="Photo you sent"
              className="max-h-72 max-w-[min(85%,22rem)] rounded-3xl rounded-br-lg border border-line object-cover shadow-sm"
            />
          </a>
        )}
        {message.content && (
          <div className="max-w-[85%] rounded-3xl rounded-br-lg bg-user px-4 py-2.5 whitespace-pre-wrap text-user-ink shadow-sm">
            {message.content}
          </div>
        )}
      </div>
    );

  const { body, asks } = parseAsks(message.content);
  const thinking = message.pending && !message.content;

  return (
    <div className="animate-rise group flex gap-3">
      <div className="pt-0.5">
        <Avatar size={30} />
      </div>
      <div className="min-w-0 flex-1">
        {!!message.tools?.length && <ToolSteps steps={message.tools} />}

        {thinking && (
          <div className="flex h-8 items-center gap-1.5 text-accent">
            <span className="dot size-2 rounded-full bg-current" />
            <span className="dot size-2 rounded-full bg-current" />
            <span className="dot size-2 rounded-full bg-current" />
            <span className="ml-2 text-sm text-muted">CookMate is thinking…</span>
          </div>
        )}

        {body && (
          <div className="prose-cook prose max-w-none prose-p:leading-relaxed prose-li:my-0.5 prose-headings:mb-2 prose-headings:mt-5">
            <Markdown remarkPlugins={[remarkGfm]}>{body}</Markdown>
          </div>
        )}

        {asks.length > 0 && <AskCard asks={asks} active={isLast && !busy} onAnswer={onAnswer} />}

        {message.error && (
          <div className="mt-2 flex items-start gap-2 rounded-xl border border-red-300/50 bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-300">
            <TriangleAlert size={16} className="mt-0.5 shrink-0" />
            <span>
              Couldn't reach the kitchen 😕 Google's servers might be busy. Try sending again in a moment.
              <span className="mt-1 block text-xs opacity-70">{message.error}</span>
            </span>
          </div>
        )}

        {!!message.learned?.length && (
          <div className="animate-rise mt-3 flex items-start gap-2 rounded-xl border border-dashed border-accent/30 px-3 py-2 text-xs text-muted">
            <span>💡</span>
            <span>
              <span className="font-semibold text-ink/80">Noted for next time: </span>
              {message.learned.join(" · ")}
            </span>
          </div>
        )}

        {!message.pending && body && <Footer text={message.content} meta={message.meta} />}
      </div>
    </div>
  );
}

const TOOL_ICONS: Record<string, string> = {
  guess_cuisine: "🧠",
  scale_recipe: "⚖️",
  convert_units: "🔄",
  get_pantry: "🧺",
  update_pantry: "✏️",
  make_grocery_list: "🛒",
};

/** The tools CookMate used, shown as small badges above its reply. */
function ToolSteps({ steps }: { steps: ToolStep[] }) {
  return (
    <div className="mb-3 flex flex-wrap gap-1.5">
      {steps.map((step, i) => (
        <span
          key={i}
          className="animate-rise inline-flex items-center gap-1.5 rounded-full border border-accent/20 bg-accent-soft/60 px-2.5 py-1 text-xs font-medium text-ink/80"
        >
          <span>{TOOL_ICONS[step.name] ?? "🔧"}</span>
          {step.label}
        </span>
      ))}
    </div>
  );
}

function Footer({ text, meta }: { text: string; meta?: string | null }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(parseAsks(text).body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="mt-2 flex items-center gap-3 text-xs text-muted opacity-0 transition group-hover:opacity-100 max-md:opacity-100">
      <button onClick={copy} className="flex items-center gap-1 rounded-md py-1 hover:text-ink">
        {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Copy"}
      </button>
      {meta && <span>{meta}</span>}
    </div>
  );
}
