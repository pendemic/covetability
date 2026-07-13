// Decorative colorway/model swatch. The data model has no per-variant hex, so we
// map common colour words and fall back to a deterministic hue from the name.
// Purely visual — never presented as a data claim.
const SWATCH_WORDS: Array<[string, string]> = [
  ["black", "#2B2520"],
  ["whiskey", "#B0623E"],
  ["cognac", "#9A5A2E"],
  ["tan", "#C9A878"],
  ["camel", "#C19A6B"],
  ["cream", "#E7DDC9"],
  ["white", "#EFE9DC"],
  ["beige", "#D9C7A8"],
  ["brown", "#5A3A24"],
  ["chocolate", "#3B2A1E"],
  ["red", "#8A2E2E"],
  ["burgundy", "#5E2130"],
  ["pink", "#C98A9A"],
  ["blue", "#3A4A6E"],
  ["navy", "#2A3350"],
  ["green", "#3A5140"],
  ["grey", "#8A857C"],
  ["gray", "#8A857C"],
  ["silver", "#B9B4AC"],
  ["gold", "#C29A54"],
];

export function swatchColor(name: string): string {
  const lower = name.toLowerCase();
  const match = SWATCH_WORDS.find(([word]) => lower.includes(word));
  if (match) {
    return match[1];
  }
  let hue = 0;
  for (const char of name) {
    hue = (hue * 31 + char.charCodeAt(0)) % 360;
  }
  return `hsl(${hue} 26% 46%)`;
}
