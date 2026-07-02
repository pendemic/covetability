import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const scanRoots = ["app", "lib"];
const allowlistedFiles = new Set([path.normalize("lib/vocabulary.ts")]);

const phrasePatterns = [
  ["market value", /\bmarket value\b/i],
  ["worth", /\bworth\b/i],
  ["valuation", /\bvaluation\b/i],
  ["sold", /\bsold\b/i],
  ["sell-through", /\bsell-through\b/i],
  ["sales rate", /\bsales rate\b/i],
  ["sales", /\bsales\b/i],
  ["bare authenticated", /(?<!platform-)\bauthenticated\b/i],
  ["demand", /\bdemand\b/i],
  ["investment", /\binvestment\b/i],
  ["appreciating", /\bappreciating\b/i],
  ["ROI", /\bROI\b/i],
  ["forecast", /\bforecast\b/i],
  ["prediction", /\bprediction\b/i],
];

const sourceExtensions = new Set([".ts", ".tsx", ".js", ".jsx", ".mdx"]);

async function* walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      yield* walk(fullPath);
    } else if (sourceExtensions.has(path.extname(entry.name))) {
      yield fullPath;
    }
  }
}

const failures = [];

for (const scanRoot of scanRoots) {
  const absoluteRoot = path.join(root, scanRoot);
  for await (const file of walk(absoluteRoot)) {
    const relative = path.relative(root, file);
    if (allowlistedFiles.has(path.normalize(relative))) {
      continue;
    }

    const contents = await readFile(file, "utf8");
    for (const [label, pattern] of phrasePatterns) {
      if (pattern.test(contents)) {
        failures.push(`${relative}: prohibited vocabulary "${label}"`);
      }
    }
  }
}

if (failures.length > 0) {
  console.error("Vocabulary lint failed:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("Vocabulary lint passed.");
