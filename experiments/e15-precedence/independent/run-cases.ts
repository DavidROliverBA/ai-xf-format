import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { resolveLink } from "./resolve.ts";

const dir = dirname(new URL(import.meta.url).pathname);
const input = JSON.parse(readFileSync(join(dir, "cases-input.json"), "utf8"));
const cases = input.cases.map((c: any) => ({
  case: c.case,
  result: resolveLink(join(dir, c.federation), c.from_namespace, c.from_concept, c.to),
}));
writeFileSync(join(dir, "results-indep.json"), JSON.stringify({ cases }, null, 1) + "\n");
console.log(`ran ${cases.length} cases`);
for (const c of cases) console.log(c.case, JSON.stringify(c.result));
