// Extract structured facets (colour, material, type, year) from a raw listing
// title so the listings table can filter and sort by them. Canonical display
// value on the left, matching tokens on the right. First match in title wins.

type Dict = Array<[string, string[]]>;

const COLORS: Dict = [
  ["Black", ["black", "noir"]],
  ["White", ["white", "blanc"]],
  ["Cream", ["cream", "ivory", "ecru", "off white", "off-white"]],
  ["Beige", ["beige", "sand", "greige"]],
  ["Tan", ["tan", "camel", "caramel"]],
  ["Cognac", ["cognac", "whiskey", "whisky"]],
  ["Brown", ["brown", "chocolate", "espresso", "mocha"]],
  ["Grey", ["grey", "gray", "charcoal", "anthracite"]],
  ["Silver", ["silver"]],
  ["Gold", ["gold", "golden"]],
  ["Red", ["red", "rouge", "cherry", "scarlet"]],
  ["Burgundy", ["burgundy", "bordeaux", "wine", "maroon", "oxblood"]],
  ["Pink", ["pink", "blush", "rose", "fuchsia", "magenta"]],
  ["Orange", ["orange", "coral", "rust"]],
  ["Yellow", ["yellow", "mustard"]],
  ["Green", ["green", "olive", "khaki", "emerald", "teal", "mint"]],
  ["Blue", ["blue", "navy", "cobalt", "denim blue", "turquoise"]],
  ["Purple", ["purple", "violet", "lavender", "plum", "amarante"]],
  ["Nude", ["nude", "taupe"]],
  ["Multicolor", ["multicolor", "multicolour", "tricolor", "rainbow", "murakami", "multicolore"]],
];

const MATERIALS: Dict = [
  ["Patent leather", ["patent", "vernis"]],
  ["Suede", ["suede", "nubuck"]],
  ["Lambskin", ["lambskin", "agneau"]],
  ["Calfskin", ["calfskin", "calf", "chevre", "box calf"]],
  ["Saffiano", ["saffiano"]],
  ["Caviar", ["caviar"]],
  ["Grained leather", ["grained", "grain", "pebbled", "pebble", "togo"]],
  ["Nappa", ["nappa", "vitello"]],
  ["Canvas", ["canvas", "toile", "monogram", "monogramme", "damier", "guccissima", "jacquard", "zucca", "zucchino"]],
  ["Nylon", ["nylon", "tessuto"]],
  ["Denim", ["denim"]],
  ["Python", ["python", "snakeskin"]],
  ["Croc/Alligator", ["crocodile", "croc", "alligator"]],
  ["Ostrich", ["ostrich"]],
  ["Exotic", ["exotic"]],
  ["Velvet", ["velvet"]],
  ["Satin", ["satin"]],
  ["Tweed", ["tweed"]],
  ["Raffia/Straw", ["raffia", "straw"]],
  ["Leather", ["leather", "cuir"]], // generic — checked last so specific wins
];

const TYPES: Dict = [
  ["Satchel", ["satchel"]],
  ["Tote", ["tote"]],
  ["Hobo", ["hobo"]],
  ["Shoulder", ["shoulder"]],
  ["Crossbody", ["crossbody", "cross body"]],
  ["Clutch", ["clutch"]],
  ["Bucket", ["bucket"]],
  ["Backpack", ["backpack"]],
  ["Flap", ["flap"]],
  ["Bowling", ["bowling", "bauletto", "boston", "doctor"]],
  ["Pouch", ["pouch", "pochette", "wristlet"]],
  ["Top handle", ["top handle", "top-handle"]],
];

function norm(title: string): string {
  return ` ${title.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()} `;
}

function firstMatch(haystack: string, dict: Dict): string | null {
  let best: { display: string; index: number } | null = null;
  for (const [display, tokens] of dict) {
    for (const token of tokens) {
      const idx = haystack.indexOf(` ${token} `);
      // also allow token adjacent to non-space boundaries handled by norm padding
      const loose = idx === -1 ? haystack.indexOf(token) : idx;
      if (loose !== -1 && (best === null || loose < best.index)) {
        best = { display, index: loose };
        break;
      }
    }
  }
  return best?.display ?? null;
}

export type ListingAttributes = {
  color: string | null;
  material: string | null;
  type: string | null;
  year: number | null;
};

export function extractAttributes(title: string): ListingAttributes {
  const h = norm(title);
  const yearMatch = title.match(/\b(19[7-9]\d|20[0-2]\d)\b/);
  let year = yearMatch ? Number(yearMatch[1]) : null;
  if (year === null) {
    const decade = title.match(/\b((?:19|20)\d0)s\b/) ?? title.match(/\by2k\b/i);
    if (decade) {
      year = /y2k/i.test(decade[0]) ? 2000 : Number(decade[1]);
    }
  }
  return {
    color: firstMatch(h, COLORS),
    material: firstMatch(h, MATERIALS),
    type: firstMatch(h, TYPES),
    year,
  };
}
