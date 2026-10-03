// E13: canonical serialisation of AI-XF concepts, TypeScript implementation.
//
// Implements CANONICAL.md independently of canon.py; H3 checks that the two agree byte for byte.
// Parses with the `yaml` package's YAML 1.2 core schema, which has no timestamp type, so the data
// model is the one CANONICAL.md §1 defines.
//
//   bun run canon.ts <in-root> <out-root> <file-list>

import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { parse as parseYaml } from "yaml";

type Value = null | boolean | number | string | Value[] | { [k: string]: Value };
type Mapping = { [k: string]: Value };

// --- §1 and §2: data model and file layout -------------------------------------------------------

const FM_RE = /^---[ \t]*\r?\n(?:([\s\S]*?)\r?\n)?---[ \t]*(?:\r?\n|$)/;

export function parse(text: string): { fm: Mapping; body: string } {
  const t = text.startsWith("﻿") ? text.slice(1) : text;
  const m = FM_RE.exec(t);
  if (!m) throw new Error("no frontmatter");
  const src = m[1] ?? "";
  const fm = src.trim() ? parseYaml(src, { schema: "core", version: "1.2" }) : {};
  if (fm === null || fm === undefined) return { fm: {}, body: t.slice(m[0].length) };
  if (typeof fm !== "object" || Array.isArray(fm)) throw new Error("frontmatter is not a mapping");
  return { fm: fm as Mapping, body: t.slice(m[0].length) };
}

// --- §3: key order -------------------------------------------------------------------------------

const ORDER: Record<string, string[]> = {
  top: ["type", "id", "title", "description", "resource", "tags", "aliases", "generated", "verified",
    "status", "stale_after", "sources", "usage_window", "provenance", "links", "media"],
  generated: ["by", "at"],
  "verified[]": ["by", "at"],
  "sources[]": ["id", "resource", "title", "author", "last_modified", "usage_count", "usage_window", "withheld"],
  usage_window: ["from", "to"],
  provenance: ["confidence", "source"],
  "links[]": ["rel", "to", "note", "by", "at", "state", "resolved", "verified"],
  resolved: ["by", "at", "outcome"],
  "media[]": ["uri", "hash", "type", "describes"],
};
const MAP_ROLES = new Set(["generated", "usage_window", "provenance", "resolved"]);
const ITEM_ROLES = new Set(["verified", "sources", "links", "media"]);

function orderedKeys(m: Mapping, role: string | null): string[] {
  const listed = (ORDER[role ?? ""] ?? []).filter((k) => Object.hasOwn(m, k));
  const rest = Object.keys(m)
    .filter((k) => !listed.includes(k))
    .sort((a, b) => Buffer.compare(Buffer.from(a, "utf8"), Buffer.from(b, "utf8")));
  return [...listed, ...rest];
}

// --- §5: scalars ---------------------------------------------------------------------------------

const TS_KEYS = new Set(["at", "stale_after", "last_modified", "from", "to"]);
const TS_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
// E13b: "keys" (option A, CANONICAL.md §5 as first run) or "shape" (option B: any ISO date or datetime)
const DATES = process.env.AIXF_CANON_DATES ?? "shape"; // "shape" adopted in E13b
const RESERVED = new Set(["null", "true", "false", "yes", "no", "y", "n", "on", "off"]);

/** Outside YAML's printable set, or a YAML 1.1 line break or BOM (E13c). */
function needsEscape(c: number): boolean {
  const printable = c === 0x09 || c === 0x0a || c === 0x0d || (c >= 0x20 && c <= 0x7e) ||
    (c >= 0xa0 && c <= 0xd7ff) || (c >= 0xe000 && c <= 0xfffd) || c >= 0x10000;
  return !printable || c === 0x85 || c === 0x2028 || c === 0x2029 || c === 0xfeff;
}

function checkSurrogates(s: string): void {
  for (const c of s) {
    const code = c.codePointAt(0) as number;
    if (code >= 0xd800 && code <= 0xdfff) throw new Error("a string with an unpaired surrogate cannot be serialised");
  }
}

const hasEscapable = (s: string) => [...s].some((c) => needsEscape(c.codePointAt(0) as number));

function plainSafe(s: string): boolean {
  if (s.length === 0 || /^[ \t]|[ \t]$/.test(s)) return false;
  const pathStart = (s.startsWith("./") && s.length > 2 && s[2] !== ".") ||
    (s.startsWith("../") && s.length > 3 && s[3] !== ".");
  if (!/^[A-Za-z_/]/.test(s) && !pathStart) return false;
  if (/[\u0000-\u001f#]/.test(s) || hasEscapable(s) || s.includes(": ") || s.endsWith(":")) return false;
  return !RESERVED.has(s.toLowerCase());
}

function doubleQuote(s: string): string {
  let out = '"';
  for (const c of s) {
    const code = c.codePointAt(0) as number;
    if (c === "\\") out += "\\\\";
    else if (c === '"') out += '\\"';
    else if (c === "\n") out += "\\n";
    else if (c === "\t") out += "\\t";
    else if (c === "\r") out += "\\r";
    else if (needsEscape(code)) out += `\\u${code.toString(16).toUpperCase().padStart(4, "0")}`;
    else out += c;
  }
  return `${out}"`;
}

function scalar(v: Value, key?: string): string {
  if ((v as unknown) === undefined) throw new Error("undefined is not a YAML value: drop the key instead"); // not data
  if (v === null) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (Number.isNaN(v)) return ".nan";
    if (!Number.isFinite(v)) return v < 0 ? "-.inf" : ".inf";
    if (v === 0) return "0";
    // E13d: integer digits at any magnitude; an exponent mantissa gets a decimal point for YAML 1.1
    if (Number.isInteger(v)) return Math.abs(v) < 1e21 ? String(v) : BigInt(v).toString();
    const r = String(v);
    const e = r.indexOf("e");
    return e >= 0 && !r.slice(0, e).includes(".") ? `${r.slice(0, e)}.0${r.slice(e)}` : r;
  }
  const s = String(v);
  checkSurrogates(s);
  if (DATES === "shape" && (TS_RE.test(s) || DATE_RE.test(s))) return s;
  if (DATES === "keys" && key !== undefined && TS_KEYS.has(key) && TS_RE.test(s)) return s;
  return plainSafe(s) ? s : doubleQuote(s);
}

// --- §4: structure -------------------------------------------------------------------------------

const isLeaf = (v: Value) =>
  v === null || typeof v !== "object" || (Array.isArray(v) ? v.length === 0 : Object.keys(v).length === 0);
const leaf = (v: Value, key?: string) =>
  Array.isArray(v) ? "[]" : v !== null && typeof v === "object" ? "{}" : scalar(v, key);
const keyText = (k: string) => {
  checkSurrogates(k);
  return plainSafe(k) ? k : doubleQuote(k);
};

function emitMap(m: Mapping, indent: number, role: string | null, out: string[]): void {
  const pad = " ".repeat(indent);
  for (const k of orderedKeys(m, role)) {
    const v = m[k] as Value;
    if (isLeaf(v)) out.push(`${pad}${keyText(k)}: ${leaf(v, k)}`);
    else if (Array.isArray(v)) {
      out.push(`${pad}${keyText(k)}:`);
      emitList(v, indent + 2, k, out);
    } else {
      out.push(`${pad}${keyText(k)}:`);
      emitMap(v as Mapping, indent + 2, MAP_ROLES.has(k) ? k : null, out);
    }
  }
}

function emitList(list: Value[], indent: number, key: string | undefined, out: string[]): void {
  const pad = " ".repeat(indent);
  const role = key !== undefined && ITEM_ROLES.has(key) ? `${key}[]` : null;
  for (const item of list) {
    if (isLeaf(item)) out.push(`${pad}- ${leaf(item, key)}`);
    else if (Array.isArray(item)) {
      out.push(`${pad}-`);
      emitList(item, indent + 2, undefined, out);
    } else {
      const sub: string[] = [];
      emitMap(item as Mapping, indent + 2, role, sub);
      sub[0] = `${pad}- ${(sub[0] as string).slice(indent + 2)}`;
      out.push(...sub);
    }
  }
}

export function serialise(fm: Mapping, body: string): string {
  const lines: string[] = [];
  emitMap(fm, 0, "top", lines);
  const head = `---\n${lines.map((l) => `${l}\n`).join("")}---\n`;
  const b = body.replace(/\r\n?/g, "\n").replace(/^\n+|\n+$/g, "");
  return head + (b ? `\n${b}\n` : "");
}

export function canonical(text: string): string {
  const { fm, body } = parse(text);
  return serialise(fm, body);
}

export function contentHash(text: string): string {
  return `sha256:${createHash("sha256").update(canonical(text), "utf8").digest("hex")}`;
}

if (import.meta.main) {
  const [src, dst, listing] = Bun.argv.slice(2) as [string, string, string];
  let failed = 0;
  for (const rel of readFileSync(listing, "utf8").split("\n").filter(Boolean)) {
    const out = join(dst, rel);
    mkdirSync(dirname(out), { recursive: true });
    try {
      writeFileSync(out, canonical(readFileSync(join(src, rel), "utf8")), "utf8");
    } catch (e) {
      failed++;
      console.error(`canon.ts: ${rel}: ${(e as Error).message}`);
    }
  }
  console.log(`canon.ts: wrote ${dst}, ${failed} failed`);
}
