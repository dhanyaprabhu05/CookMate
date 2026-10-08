// CookMate asks questions using lines like:
//   <<ask: How many people? | Just me | 2 | 4>>
// This pulls them out of the text so we can show them as tappable chips.

export type Ask = { question: string; options: string[] };

const ASK_LINE = /<<ask:\s*([\s\S]*?)>>/g;

export function parseAsks(text: string): { body: string; asks: Ask[] } {
  const asks: Ask[] = [];
  const body = text
    .replace(ASK_LINE, (_, inner: string) => {
      const [question, ...options] = inner.split("|").map((s) => s.trim()).filter(Boolean);
      if (question) asks.push({ question, options });
      return "";
    })
    // While streaming, hide a half-written "<<ask: ..." until it's complete.
    .replace(/<<[^>]*$/, "")
    .trim();
  return { body, asks };
}
