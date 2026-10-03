#!/usr/bin/env python3
"""E13: canonical serialisation of AI-XF concepts, Python implementation.

Implements CANONICAL.md. Needs PyYAML, used only as a parser, with the YAML 1.1
implicit resolvers replaced by YAML 1.2 core ones and no timestamp resolver,
so the data model is the one CANONICAL.md §1 defines.

    uv run --with pyyaml python3 canon.py <in-root> <out-root> <file-list>

reads every relative path in <file-list> under <in-root>, and writes its
canonical form to the same path under <out-root>. As a module: parse(text),
canonical(text), content_hash(text).
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

import yaml

# --- §1: YAML 1.2 core schema, timestamps as strings -------------------------


class CoreLoader(yaml.SafeLoader):
    pass


CoreLoader.yaml_implicit_resolvers = {}
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:null", re.compile(r"^(?:~|null|Null|NULL|)$"), ["~", "n", "N", ""])
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int", re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"), list("-+0123456789"))
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^(?:[-+]?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)(?:[eE][-+]?[0-9]+)?"
               r"|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+.0123456789"))


def _core_int(loader, node):
    v = loader.construct_scalar(node)
    if v.startswith("0o"):
        return int(v[2:], 8)
    if v.startswith("0x"):
        return int(v[2:], 16)
    return int(v, 10)          # YAML 1.2: a leading zero is still decimal


def _core_float(loader, node):
    v = loader.construct_scalar(node).lower()
    if v.endswith(".inf"):
        return -math.inf if v.startswith("-") else math.inf
    if v == ".nan":
        return math.nan
    return float(v)


CoreLoader.add_constructor("tag:yaml.org,2002:int", _core_int)
CoreLoader.add_constructor("tag:yaml.org,2002:float", _core_float)

FM_RE = re.compile(r"\A---[ \t]*\r?\n(?:(.*?)\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.S)


def split(text: str):
    """(frontmatter text, body text) or None when the file has no frontmatter."""
    if text.startswith("﻿"):
        text = text[1:]
    m = FM_RE.match(text)
    if not m:
        return None
    return m.group(1) or "", text[m.end():]


def parse(text: str):
    """(frontmatter mapping, body) under the §1 data model."""
    parts = split(text)
    if parts is None:
        raise ValueError("no frontmatter")
    fm = yaml.load(parts[0], Loader=CoreLoader) if parts[0].strip() else {}
    if fm is None:
        fm = {}
    if not isinstance(fm, dict):
        raise ValueError("frontmatter is not a mapping")
    return fm, parts[1]


# --- §3: key order ---------------------------------------------------------

ORDER = {
    "top": ["type", "id", "title", "description", "resource", "tags", "aliases", "generated", "verified",
            "status", "stale_after", "sources", "usage_window", "provenance", "links", "media"],
    "generated": ["by", "at"],
    "verified[]": ["by", "at"],
    "sources[]": ["id", "resource", "title", "author", "last_modified", "usage_count", "usage_window", "withheld"],
    "usage_window": ["from", "to"],
    "provenance": ["confidence", "source"],
    "links[]": ["rel", "to", "note", "by", "at", "state", "resolved", "verified"],
    "resolved": ["by", "at", "outcome"],
    "media[]": ["uri", "hash", "type", "describes"],
}
MAP_ROLES = {"generated", "usage_window", "provenance", "resolved"}
ITEM_ROLES = {"verified", "sources", "links", "media"}


def ordered_keys(m: dict, role: str | None) -> list:
    listed = [k for k in ORDER.get(role or "", []) if k in m]
    rest = sorted((k for k in m if k not in listed), key=lambda k: str(k).encode("utf-8"))
    return listed + rest


# --- §5: scalars -------------------------------------------------------------

TS_KEYS = {"at", "stale_after", "last_modified", "from", "to"}
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# E13b: "keys" (option A, CANONICAL.md §5 as first run) or "shape" (option B: any ISO date or datetime)
DATES = os.environ.get("AIXF_CANON_DATES", "shape")   # "shape" adopted in E13b
RESERVED = {"null", "true", "false", "yes", "no", "y", "n", "on", "off"}


def needs_escape(c: int) -> bool:
    """Outside YAML's printable set, or a YAML 1.1 line break or BOM (E13c)."""
    printable = c in (0x09, 0x0A, 0x0D) or 0x20 <= c <= 0x7E or 0xA0 <= c <= 0xD7FF \
        or 0xE000 <= c <= 0xFFFD or c >= 0x10000
    return not printable or c in (0x85, 0x2028, 0x2029, 0xFEFF)


def check_surrogates(s: str) -> None:
    if any(0xD800 <= ord(c) <= 0xDFFF for c in s):
        raise ValueError("a string with an unpaired surrogate cannot be serialised")


def plain_safe(s: str) -> bool:
    if not s or s[0] in " \t" or s[-1] in " \t":
        return False
    first = s[0]
    if not ((first.isascii() and first.isalpha()) or first in "_/"
            or (s.startswith("./") and len(s) > 2 and s[2] != ".")
            or (s.startswith("../") and len(s) > 3 and s[3] != ".")):
        return False
    if any(ord(c) < 0x20 or needs_escape(ord(c)) for c in s) or "#" in s or ": " in s or s.endswith(":"):
        return False
    return s.lower() not in RESERVED


def double_quote(s: str) -> str:
    out = []
    for c in s:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif needs_escape(ord(c)):
            out.append("\\u%04X" % ord(c))
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def js_number(f: float) -> str:
    """ECMAScript Number.prototype.toString for a finite, non-integral double."""
    sign = "-" if f < 0 else ""
    _, digits, exp = Decimal(repr(abs(f))).normalize().as_tuple()
    ds = "".join(map(str, digits))
    k, n = len(ds), len(ds) + exp          # value = 0.ds × 10^n
    if k <= n <= 21:
        return sign + ds + "0" * (n - k)
    if 0 < n <= 21:
        return sign + ds[:n] + "." + ds[n:]
    if -6 < n <= 0:
        return sign + "0." + "0" * (-n) + ds
    e = n - 1
    mant = ds[0] + ("." + ds[1:] if k > 1 else "")
    return f"{sign}{mant}e{'+' if e >= 0 else '-'}{abs(e)}"


def scalar(v, key=None) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if math.isnan(v):
            return ".nan"
        if math.isinf(v):
            return "-.inf" if v < 0 else ".inf"
        if v == 0:
            return "0"
        if v.is_integer() and abs(v) < 1e21:
            return str(int(v))
        return js_number(v)
    s = str(v)
    check_surrogates(s)
    if DATES == "shape" and (TS_RE.match(s) or DATE_RE.match(s)):
        return s
    if DATES == "keys" and key in TS_KEYS and TS_RE.match(s):
        return s
    return s if plain_safe(s) else double_quote(s)


def key_text(k) -> str:
    if isinstance(k, str):
        check_surrogates(k)
    return scalar(k) if not isinstance(k, str) else (k if plain_safe(k) else double_quote(k))


# --- §4: structure -----------------------------------------------------------

def is_leaf(v) -> bool:
    return not isinstance(v, (dict, list)) or len(v) == 0


def leaf(v, key=None) -> str:
    if isinstance(v, list):
        return "[]"
    if isinstance(v, dict):
        return "{}"
    return scalar(v, key)


def emit_map(m: dict, indent: int, role: str | None, out: list) -> None:
    pad = " " * indent
    for k in ordered_keys(m, role):
        v = m[k]
        kt = key_text(k)
        if is_leaf(v):
            out.append(f"{pad}{kt}: {leaf(v, k)}")
        elif isinstance(v, dict):
            out.append(f"{pad}{kt}:")
            emit_map(v, indent + 2, k if k in MAP_ROLES else None, out)
        else:
            out.append(f"{pad}{kt}:")
            emit_list(v, indent + 2, k, out)


def emit_list(lst: list, indent: int, key, out: list) -> None:
    pad = " " * indent
    role = f"{key}[]" if key in ITEM_ROLES else None
    for item in lst:
        if is_leaf(item):
            out.append(f"{pad}- {leaf(item, key)}")
        elif isinstance(item, dict):
            sub: list = []
            emit_map(item, indent + 2, role, sub)
            sub[0] = pad + "- " + sub[0][indent + 2:]
            out.extend(sub)
        else:
            out.append(f"{pad}-")
            emit_list(item, indent + 2, None, out)


def serialise(fm: dict, body: str) -> str:
    """The canonical file for a frontmatter mapping and a body (§2–§5)."""
    lines: list = []
    emit_map(fm, 0, "top", lines)
    head = "---\n" + "".join(l + "\n" for l in lines) + "---\n"
    b = body.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    return head + ("\n" + b + "\n" if b else "")


def canonical(text: str) -> str:
    return serialise(*parse(text))


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(canonical(text).encode("utf-8")).hexdigest()


def main() -> None:
    src, dst, listing = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    failed = 0
    for rel in listing.read_text(encoding="utf-8").split("\n"):
        if not rel:
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            out.write_text(canonical((src / rel).read_text(encoding="utf-8")), encoding="utf-8", newline="")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"canon.py: {rel}: {e}", file=sys.stderr)
    print(f"canon.py: wrote {dst}, {failed} failed")


if __name__ == "__main__":
    main()
