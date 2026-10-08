import { ChefHat } from "lucide-react";

/** CookMate's avatar: a chef hat on a warm gradient. */
export function Avatar({ size = 32 }: { size?: number }) {
  return (
    <div
      className="grid shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent-2 to-accent text-white shadow-sm shadow-accent/30"
      style={{ width: size, height: size }}
    >
      <ChefHat size={size * 0.55} strokeWidth={2} />
    </div>
  );
}

export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <Avatar size={30} />
      <span className="font-display text-xl font-medium tracking-tight">
        Cook<span className="text-accent">Mate</span>
      </span>
    </div>
  );
}
