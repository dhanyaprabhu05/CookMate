import { useState } from "react";
import { ArrowRight } from "lucide-react";
import type { Ask } from "../lib/asks";

/** CookMate's counter-questions as tappable chips. */
export function AskCard({ asks, active, onAnswer }: { asks: Ask[]; active: boolean; onAnswer: (text: string) => void }) {
  const [picked, setPicked] = useState<Record<number, string>>({});
  const allAnswered = asks.every((_, i) => picked[i]);

  const submit = () => onAnswer(asks.map((a, i) => `${a.question} ${picked[i]}`).join("\n"));

  return (
    <div className="mt-3 space-y-3 rounded-2xl border border-line bg-panel/60 p-4">
      {asks.map((ask, i) => (
        <div key={i}>
          <div className="mb-2 text-sm font-medium">{ask.question}</div>
          <div className="flex flex-wrap gap-2">
            {ask.options.map((opt) => {
              const selected = picked[i] === opt;
              return (
                <button
                  key={opt}
                  disabled={!active}
                  onClick={() => {
                    const next = { ...picked, [i]: opt };
                    setPicked(next);
                    // Only one question? Send straight away.
                    if (asks.length === 1) onAnswer(`${ask.question} ${opt}`);
                  }}
                  className={`rounded-full border px-3.5 py-1.5 text-sm transition disabled:cursor-default disabled:opacity-50 ${
                    selected
                      ? "border-accent bg-accent text-white shadow-sm shadow-accent/30"
                      : "border-line bg-surface hover:border-accent/50 hover:bg-accent-soft"
                  }`}
                >
                  {opt}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      {active && asks.length > 1 && (
        <div className="flex items-center justify-between gap-3 pt-1">
          <span className="text-xs text-muted">Pick one for each, or just type your answer.</span>
          <button
            onClick={submit}
            disabled={!allAnswered}
            className="flex shrink-0 items-center gap-1.5 rounded-full bg-ink px-4 py-2 text-sm font-semibold text-bg transition hover:opacity-90 disabled:opacity-30"
          >
            Let's cook <ArrowRight size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
