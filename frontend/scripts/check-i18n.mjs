// Fails when a string is missing from a language file.
//  1. en.json and ar.json must have exactly the same keys, and no value may be empty.
//  2. Every literal t("key") / msg("key") in the source must exist in both files.
// Test files (*.test.ts(x), *.spec.ts(x)) are not scanned: they may use a missing key on purpose.
// Keys built at run time (t(`x.${y}`)) can't be seen here; the placeholders {name} must still match between languages.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const root = new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const en = JSON.parse(readFileSync(join(root, "locales/en.json"), "utf8"));
const ar = JSON.parse(readFileSync(join(root, "locales/ar.json"), "utf8"));
const problems = [];

for (const k of Object.keys(en)) if (!(k in ar)) problems.push(`missing in ar.json: ${k}`);
for (const k of Object.keys(ar)) if (!(k in en)) problems.push(`missing in en.json: ${k}`);
for (const [lang, d] of [["en", en], ["ar", ar]]) for (const [k, v] of Object.entries(d)) if (!String(v).trim()) problems.push(`empty value in ${lang}.json: ${k}`);
const vars = (s) => [...new Set([...String(s).matchAll(/\{(\w+)(?:\|[^}]*)?\}/g)].map((m) => m[1]))].sort().join(",");
for (const k of Object.keys(en)) if (k in ar && vars(en[k]) !== vars(ar[k])) problems.push(`placeholders differ for ${k}: en {${vars(en[k])}} vs ar {${vars(ar[k])}}`);

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* walk(p);
    else if (/\.(ts|tsx)$/.test(name) && !/\.(test|spec)\.(ts|tsx)$/.test(name)) yield p; // tests may use a missing key on purpose (i18n.test.tsx)
  }
}
const used = new Map();
for (const file of walk(root)) {
  const src = readFileSync(file, "utf8");
  for (const m of src.matchAll(/\b(?:t|msg)\(\s*"([A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)"/g)) if (!used.has(m[1])) used.set(m[1], file);
}
for (const [k, f] of used) {
  if (!(k in en)) problems.push(`used but not in en.json: ${k} (${f.replace(root, "src")})`);
  if (!(k in ar)) problems.push(`used but not in ar.json: ${k} (${f.replace(root, "src")})`);
}
if (problems.length) {
  console.error(problems.join("\n"));
  console.error(`\n${problems.length} i18n problem(s).`);
  process.exit(1);
}
console.log(`i18n ok: ${Object.keys(en).length} keys in both languages, ${used.size} literal keys used in the source.`);
