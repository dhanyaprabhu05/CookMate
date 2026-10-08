import type { Chat } from "../api";

/** Group chats into Today / Yesterday / Previous 7 days / Older for the sidebar. */
export function groupChats(chats: Chat[]) {
  const startOfToday = new Date().setHours(0, 0, 0, 0) / 1000;
  const day = 86400;
  const groups: { label: string; chats: Chat[] }[] = [
    { label: "Today", chats: [] },
    { label: "Yesterday", chats: [] },
    { label: "Previous 7 days", chats: [] },
    { label: "Older", chats: [] },
  ];
  for (const chat of chats) {
    const t = chat.updated_at;
    const i = t >= startOfToday ? 0 : t >= startOfToday - day ? 1 : t >= startOfToday - 7 * day ? 2 : 3;
    groups[i].chats.push(chat);
  }
  return groups.filter((g) => g.chats.length);
}

export function greeting() {
  const h = new Date().getHours();
  if (h < 5) return "Late-night cravings?";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}
