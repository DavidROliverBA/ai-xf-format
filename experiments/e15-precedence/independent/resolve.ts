// E15 independent resolver: implements PROPOSED-RULE.md per INTERFACE.md.
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, resolve as presolve, relative, sep, posix } from "node:path";

export interface Result {
  kind: "qualified" | "path" | "id";
  target: string | null;
  via: "id" | "alias" | "path" | null;
  warning: boolean;
  error: boolean;
  candidates: string[];
}

interface Concept { id: string | null; aliases: string[]; relPath: string; }
interface Bundle { namespace: string; root: string; concepts: Concept[]; }
interface Federation { bundles: Map<string, Bundle>; precedence: string[]; }

function frontmatter(text: string): any | null {
  const lines = text.split(/\r?\n/);
  const marks: number[] = [];
  for (let i = 0; i < lines.length && marks.length < 2; i++) {
    if (lines[i].trimEnd() === "---") marks.push(i);
  }
  if (marks.length < 2) return null;
  const body = lines.slice(marks[0] + 1, marks[1]);
  const asMap = (y: any) => (y && typeof y === "object" && !Array.isArray(y) ? y : null);
  try {
    return asMap(Bun.YAML.parse(body.join("\n")));
  } catch {
    // Strict by default: invalid YAML is not "YAML frontmatter", so not a concept.
    // E15_LENIENT_YAML=1 retries with top-level scalar values containing ": " quoted (see NOTES.md).
    if (process.env.E15_LENIENT_YAML !== "1") return null;
    const fixed = body.map(l => {
      const m = /^([A-Za-z_][\w-]*): (.*: .*)$/.exec(l);
      return m && !/^["'\[{|>]/.test(m[2]) ? `${m[1]}: ${JSON.stringify(m[2])}` : l;
    });
    try { return asMap(Bun.YAML.parse(fixed.join("\n"))); } catch { return null; }
  }
}

function readConcept(abs: string, relPath: string): Concept | null {
  const base = posix.basename(relPath);
  if (base === "index.md" || base === "log.md") return null;
  let fm: any;
  try { fm = frontmatter(readFileSync(abs, "utf8")); } catch { return null; }
  if (!fm || !("type" in fm)) return null;
  const id = fm.id == null ? null : String(fm.id);
  const aliases = Array.isArray(fm.aliases) ? fm.aliases.filter((a: unknown) => typeof a === "string") : [];
  return { id, aliases, relPath };
}

function scanBundle(root: string): Concept[] {
  const out: Concept[] = [];
  const walk = (dir: string) => {
    for (const name of readdirSync(dir).sort()) {
      const abs = join(dir, name);
      let st; try { st = statSync(abs); } catch { continue; }
      if (st.isDirectory()) {
        // §1: a subdirectory with its own manifest is a separate bundle.
        if (existsSync(join(abs, "manifest.ai-xf.yaml"))) continue;
        walk(abs);
      } else if (st.isFile() && name.endsWith(".md")) {
        const rel = relative(root, abs).split(sep).join("/");
        const c = readConcept(abs, rel);
        if (c) out.push(c);
      }
    }
  };
  walk(root);
  return out;
}

const fedCache = new Map<string, Federation>();
export function loadFederation(fedPath: string): Federation {
  const key = presolve(fedPath);
  const hit = fedCache.get(key); if (hit) return hit;
  const doc: any = Bun.YAML.parse(readFileSync(key, "utf8")) ?? {};
  const base = dirname(key);
  const bundles = new Map<string, Bundle>();
  for (const b of doc.bundles ?? []) {
    if (!b || b.namespace == null || b.path == null) continue;
    const ns = String(b.namespace);
    if (bundles.has(ns)) continue;
    const root = presolve(base, String(b.path));
    bundles.set(ns, { namespace: ns, root, concepts: existsSync(root) ? scanBundle(root) : [] });
  }
  const precedence: string[] = [];
  for (const p of Array.isArray(doc.precedence) ? doc.precedence : []) {
    const s = String(p);
    if (!precedence.includes(s)) precedence.push(s);
  }
  const fed = { bundles, precedence };
  fedCache.set(key, fed);
  return fed;
}

function cmpBytes(a: string, b: string): number {
  const ea = Buffer.from(a, "utf8"), eb = Buffer.from(b, "utf8");
  return Buffer.compare(ea, eb);
}

export function federationOrder(fed: Federation, own: string): string[] {
  const order: string[] = [];
  for (const ns of fed.precedence) {
    if (ns === own || !fed.bundles.has(ns) || order.includes(ns)) continue;
    order.push(ns);
  }
  const rest = [...fed.bundles.keys()].filter(ns => ns !== own && !order.includes(ns)).sort(cmpBytes);
  return order.concat(rest);
}

export function classify(to: string): { kind: Result["kind"]; ns?: string; id?: string } {
  if (to.startsWith("ai-xf://")) {
    const rest = to.slice("ai-xf://".length);
    const i = rest.indexOf("/");
    return i < 0 ? { kind: "qualified", ns: rest, id: "" } : { kind: "qualified", ns: rest.slice(0, i), id: rest.slice(i + 1) };
  }
  if (to.endsWith(".md") || to.startsWith("./") || to.startsWith("../")) return { kind: "path" };
  if (/^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9-]*$/.test(to)) {
    const [ns, id] = to.split("/");
    return { kind: "qualified", ns, id };
  }
  return { kind: "id" };
}

const byId = (b: Bundle, id: string) => b.concepts.find(c => c.id === id);
const byAlias = (b: Bundle, a: string) => b.concepts.find(c => c.id !== null && c.aliases.includes(a));
const mk = (kind: Result["kind"], target: string | null, via: Result["via"], warning: boolean, error = false, candidates: string[] = []): Result =>
  ({ kind, target, via, warning, error, candidates });

export function resolveLink(fedPath: string, fromNs: string, fromConcept: string, to: string): Result {
  const fed = loadFederation(fedPath);
  const own = fed.bundles.get(fromNs);
  if (!own) throw new Error(`namespace not held by federation: ${fromNs}`);
  const cls = classify(to);

  if (cls.kind === "qualified") {
    const ns = cls.ns!, id = cls.id!;
    if (ns === fromNs) return mk("qualified", null, null, false, true);
    const b = fed.bundles.get(ns);
    if (!b || id === "") return mk("qualified", null, null, true);
    const c = byId(b, id);
    if (c) return mk("qualified", `${ns}/${c.id}`, "id", false);
    const a = byAlias(b, id);
    if (a) return mk("qualified", `${ns}/${a.id}`, "alias", true);
    return mk("qualified", null, null, true);
  }

  if (cls.kind === "path") {
    const fromDir = posix.dirname(fromConcept.split(sep).join("/"));
    for (const baseDir of [fromDir, "."]) {
      const rel = posix.normalize(posix.join(baseDir, to));
      if (rel === ".." || rel.startsWith("../") || posix.isAbsolute(rel)) continue; // outside the bundle
      const c = own.concepts.find(x => x.relPath === rel);
      if (c && c.id !== null) return mk("path", `${fromNs}/${c.id}`, "path", false);
    }
    return mk("path", null, null, true);
  }

  // id
  const c1 = byId(own, to);
  if (c1) return mk("id", `${fromNs}/${c1.id}`, "id", false);
  const c2 = byAlias(own, to);
  if (c2) return mk("id", `${fromNs}/${c2.id}`, "alias", true);
  const order = federationOrder(fed, fromNs);
  for (const [via, find] of [["id", byId], ["alias", byAlias]] as const) {
    const hits: { ns: string; c: Concept }[] = [];
    for (const ns of order) {
      const c = find(fed.bundles.get(ns)!, to);
      if (c) hits.push({ ns, c });
    }
    if (hits.length) return mk("id", `${hits[0].ns}/${hits[0].c.id}`, via, true, false, hits.map(h => h.ns));
  }
  return mk("id", null, null, true);
}

if (import.meta.main) {
  const args = process.argv.slice(2);
  if (args.length !== 4) {
    console.error("usage: resolve <federation.ai-xf.yaml> <from-namespace> <from-concept> <to>");
    process.exit(2);
  }
  console.log(JSON.stringify(resolveLink(args[0], args[1], args[2], args[3])));
}
