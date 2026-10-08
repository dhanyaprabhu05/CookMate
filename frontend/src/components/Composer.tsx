import { useEffect, useRef, useState } from "react";
import { ArrowUp, ImagePlus, X } from "lucide-react";
import { shrinkImage } from "../lib/image";

const PHOTO_ONLY_TEXT = "What can I make with these?";

/** The message box at the bottom. Enter sends, Shift+Enter makes a new line.
 *  Photos: tap the image button, or paste one (Ctrl+V). */
export function Composer({ busy, onSend }: { busy: boolean; onSend: (text: string, image: string | null) => void }) {
  const [text, setText] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  // Grow the box as you type (up to a limit).
  const fit = () => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };
  useEffect(fit, [text]);

  // Re-measure once fonts finish loading and whenever the window resizes.
  useEffect(() => {
    document.fonts?.ready.then(fit);
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  const attach = async (file: File | undefined) => {
    if (!file || !file.type.startsWith("image/")) return;
    setPhotoError("");
    try {
      setImage(await shrinkImage(file));
      ref.current?.focus();
    } catch {
      setPhotoError("Couldn't read that photo - try a JPEG or PNG.");
    }
  };

  const canSend = (text.trim() || image) && !busy;
  const send = () => {
    if (!canSend) return;
    onSend(text.trim() || PHOTO_ONLY_TEXT, image);
    setText("");
    setImage(null);
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4">
      <div className="rounded-3xl border border-line bg-surface p-2 shadow-lg shadow-black/[0.03] transition focus-within:border-accent/50 focus-within:shadow-accent/10">
        {image && (
          <div className="animate-rise relative mb-1 ml-2 inline-block">
            <img src={image} alt="Photo to send" className="h-20 rounded-xl border border-line object-cover" />
            <button
              onClick={() => setImage(null)}
              className="absolute -top-2 -right-2 grid size-6 place-items-center rounded-full bg-ink text-bg shadow"
              aria-label="Remove photo"
            >
              <X size={13} strokeWidth={2.5} />
            </button>
          </div>
        )}
        <div className="flex items-end gap-1">
          <button
            onClick={() => fileInput.current?.click()}
            className="grid size-10 shrink-0 place-items-center rounded-full text-muted transition hover:bg-accent-soft hover:text-accent"
            aria-label="Add a photo"
            title="Add a photo of your fridge or ingredients"
          >
            <ImagePlus size={20} />
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              attach(e.target.files?.[0]);
              e.target.value = ""; // let you pick the same photo again
            }}
          />
          <textarea
            ref={ref}
            rows={1}
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            onPaste={(e) => {
              const file = [...e.clipboardData.files].find((f) => f.type.startsWith("image/"));
              if (file) {
                e.preventDefault();
                attach(file);
              }
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={image ? PHOTO_ONLY_TEXT : "Ask CookMate anything… or send a photo of your fridge 📸"}
            className="max-h-[200px] flex-1 resize-none bg-transparent px-1 py-2 leading-relaxed outline-none placeholder:text-muted"
          />
          <button
            onClick={send}
            disabled={!canSend}
            aria-label="Send"
            className="grid size-10 shrink-0 place-items-center rounded-full bg-accent text-white shadow-md shadow-accent/30 transition hover:brightness-110 active:scale-95 disabled:bg-line disabled:text-muted disabled:shadow-none"
          >
            <ArrowUp size={19} strokeWidth={2.5} />
          </button>
        </div>
      </div>
      <p className="mt-2 text-center text-[11px] text-muted">
        {photoError || "CookMate can make mistakes. Taste as you go 🍋"}
      </p>
    </div>
  );
}
