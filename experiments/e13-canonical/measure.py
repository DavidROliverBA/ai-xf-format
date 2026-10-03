#!/usr/bin/env python3
"""E13 measurements: H1-H6 and the producer diagnostic, as PLAN.md defines them.

    uv run --with pyyaml [--with 'psycopg[binary]'] python3 measure.py <workdir> [--db URL]

<workdir> is what run.sh built: corpus/<bundle>/..., list.txt, py/, ts/, py2/, ts2/.
Writes results.json beside this script and prints a summary.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import yaml

import canon

HERE = Path(__file__).resolve().parent
VALIDATOR = HERE.parent.parent / "tools" / "ai-xf-validate.py"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# --- typed deep equality (bool is not a number; numbers compare as JSON numbers) ----------------

def kind(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "num"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "map"
    return type(v).__name__


def same(a, b, skip_timestamps=False) -> bool:
    """Data-model equality. With skip_timestamps, a YAML 1.1 date/datetime on the
    left matches any timestamp-shaped string on the right (H6 excludes them)."""
    if skip_timestamps and isinstance(a, (dt.date, dt.datetime)) and isinstance(b, str) \
            and (canon.TS_RE.match(b) or DATE_RE.match(b)):
        return True
    ka, kb = kind(a), kind(b)
    if ka != kb:
        return False
    if ka == "map":
        return a.keys() == b.keys() and all(same(a[k], b[k], skip_timestamps) for k in a)
    if ka == "list":
        return len(a) == len(b) and all(same(x, y, skip_timestamps) for x, y in zip(a, b))
    if ka == "num" and a != a and b != b:   # NaN
        return True
    return a == b


def changed_leaves(a, b) -> int:
    """Values a YAML 1.1 reader sees differently (type or value) between two readings."""
    if isinstance(a, dict) and isinstance(b, dict):
        return sum(changed_leaves(a.get(k), b.get(k)) for k in a.keys() | b.keys())
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return sum(changed_leaves(x, y) for x, y in zip(a, b))
    return 0 if (type(a) is type(b) and a == b) else 1


def norm_body(b: str) -> str:
    return b.replace("\r\n", "\n").replace("\r", "\n").strip("\n")


# --- H5: formatting-only variants and mutations -------------------------------------------------

class SingleQuoteDumper(yaml.SafeDumper):
    pass


SingleQuoteDumper.add_representer(
    str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="'"))


def shuffled(v, rng):
    if isinstance(v, dict):
        keys = list(v)
        rng.shuffle(keys)
        return {k: shuffled(v[k], rng) for k in keys}
    if isinstance(v, list):
        return [shuffled(x, rng) for x in v]
    return v


def file_of(fm_text: str, body: str) -> str:
    return "---\n" + fm_text + ("" if fm_text.endswith("\n") else "\n") + "---\n" + body


def variants(fm: dict, body: str, rng) -> dict[str, str]:
    dump = lambda obj, **kw: yaml.dump(obj, Dumper=kw.pop("Dumper", yaml.SafeDumper), sort_keys=False,
                                       allow_unicode=True, **kw)
    canon_text = canon.serialise(fm, body)
    out = {
        "keys shuffled": file_of(dump(shuffled(fm, rng), default_flow_style=False, width=10**6), body),
        "flow lists": file_of(dump(fm, default_flow_style=None, width=10**6), body),
        "single-quoted strings": file_of(dump(fm, Dumper=SingleQuoteDumper, default_flow_style=False, width=10**6), body),
        "lists at column 0 (PyYAML default)": file_of(dump(fm, default_flow_style=False, width=10**6), body),
        "long lines wrapped": file_of(dump(fm, default_flow_style=False, width=30), body),
        "CRLF": canon_text.replace("\n", "\r\n"),
        "blank lines around body": file_of(dump(fm, default_flow_style=False, width=10**6), "\n\n\n" + body + "\n\n"),
    }
    lines = canon_text.split("\n")
    end = lines.index("---", 1)
    commented = [lines[0]] + [l if (l.startswith(" ") or l.startswith("-")) else f"# note\n{l}" for l in lines[1:end]] + lines[end:]
    out["comments added"] = "\n".join(commented)
    return out


def first_string_path(v, path=()):
    if isinstance(v, dict):
        for k in v:
            if k == "type":
                continue
            r = first_string_path(v[k], path + (k,))
            if r:
                return r
    elif isinstance(v, list):
        for i, x in enumerate(v):
            r = first_string_path(x, path + (i,))
            if r:
                return r
    elif isinstance(v, str):
        return path
    return None


def first_list_path(v, path=()):
    if isinstance(v, dict):
        for k in v:
            if isinstance(v[k], list) and v[k]:
                return path + (k,)
            r = first_list_path(v[k], path + (k,))
            if r:
                return r
    return None


def get_parent(v, path):
    for p in path[:-1]:
        v = v[p]
    return v


def mutations(fm: dict, body: str) -> dict[str, str]:
    out = {}
    sp = first_string_path(fm)
    if sp:
        m = copy.deepcopy(fm)
        get_parent(m, sp)[sp[-1]] += "x"
        out["one string value edited"] = canon.serialise(m, body)
    lp = first_list_path(fm)
    if lp:
        m = copy.deepcopy(fm)
        get_parent(m, lp)[lp[-1]].pop()
        out["one list item dropped"] = canon.serialise(m, body)
    keys = sorted(k for k in fm if k != "type")
    if keys:
        m = {(k + "_x" if k == keys[0] else k): v for k, v in fm.items()}
        out["one key renamed"] = canon.serialise(m, body)
    out["body edited"] = canon.serialise(fm, body + " x")
    return out


# --- validator ----------------------------------------------------------------------------------

def findings(bundle: Path, pyyaml: bool) -> tuple:
    runner = ["uv", "run", "-q", "--with", "pyyaml", "python3"] if pyyaml else ["python3"]  # plain python3: stdlib parser
    cmd = runner + [str(VALIDATOR), str(bundle), "--level", "3", "--json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    d = json.loads(r.stdout)
    return d["passed"], sorted((f["severity"], f["file"], f["message"]) for f in d["findings"])


# --- main -----------------------------------------------------------------------------------------

def main() -> None:
    work = Path(sys.argv[1])
    db_url = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else None
    corpus = work / "corpus"
    files = [l for l in (work / "list.txt").read_text().split("\n") if l]
    rng = random.Random(13)

    res = {k: defaultdict(int) for k in ("H1", "H2", "H3", "H4", "H5a", "H5b", "H6")}
    fails = defaultdict(list)
    diag = defaultdict(lambda: [0, 0])
    gen_invalid = defaultdict(int)
    whole_floats = []        # PLAN amendment: a float with no fractional part would change type
    documented_limit = []    # E13d: the adversarial set's deliberate whole-number floats
    y11_changes = defaultdict(lambda: [0, 0])   # E13b: bundle -> [values changed, concepts affected]
    models = {}

    for rel in files:
        bundle = rel.split("/")[0]
        orig = (corpus / rel).read_text(encoding="utf-8")
        try:
            fm, body = canon.parse(orig)
        except Exception as e:  # noqa: BLE001
            fails["unparseable"].append(f"{rel}: {e}")
            continue
        models[rel] = (fm, body)

        def walk(v, path=""):
            if isinstance(v, float) and v.is_integer() and bundle != "adversarial":   # E13d scope
                whole_floats.append(f"{rel}:{path}")
            elif isinstance(v, float) and v.is_integer():
                documented_limit.append(f"{rel}:{path}")
            elif isinstance(v, dict):
                for k, x in v.items():
                    walk(x, f"{path}.{k}" if path else str(k))
            elif isinstance(v, list):
                for i, x in enumerate(v):
                    walk(x, f"{path}[{i}]")
        walk(fm)
        py, ts = (work / "py" / rel).read_text(encoding="utf-8"), (work / "ts" / rel).read_text(encoding="utf-8")
        py2, ts2 = (work / "py2" / rel).read_text(encoding="utf-8"), (work / "ts2" / rel).read_text(encoding="utf-8")
        diag[bundle][0] += 1
        diag[bundle][1] += orig == py

        def tally(h, ok, why=""):
            res[h]["n"] += 1
            res[h]["ok"] += bool(ok)
            if not ok and len(fails[h]) < 15:
                fails[h].append(f"{rel}{': ' + why if why else ''}")

        tally("H1", py2 == py and ts2 == ts, "python" if py2 != py else "typescript")
        cfm, cbody = canon.parse(py)
        tally("H2", same(fm, cfm) and norm_body(body) == norm_body(cbody),
              "frontmatter" if not same(fm, cfm) else "body")
        tally("H3", py == ts)
        h_orig = canon.content_hash(orig)
        for name, text in variants(fm, body, rng).items():
            try:
                vfm, vbody = canon.parse(text)
            except Exception:  # noqa: BLE001
                gen_invalid[name] += 1
                continue
            if not same(vfm, fm) or norm_body(vbody) != norm_body(body):
                gen_invalid[name] += 1      # the generator changed meaning: not a formatting-only variant
                continue
            tally("H5a", canon.content_hash(text) == h_orig, name)
        for name, text in mutations(fm, body).items():
            tally("H5b", "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest() != h_orig, name)
        try:
            y11 = yaml.safe_load(canon.split(py)[0]) or {}
        except yaml.YAMLError as e:          # E13c: an unreadable canonical file fails H6
            tally("H6", False, f"PyYAML cannot read the canonical file: {type(e).__name__}")
            continue
        try:
            n_changed = changed_leaves(yaml.safe_load(canon.split(orig)[0]) or {}, y11)
        except yaml.YAMLError:
            n_changed = 0
        y11_changes[bundle][0] += n_changed
        y11_changes[bundle][1] += n_changed > 0
        tally("H6", same(y11, cfm, skip_timestamps=True))

    # H2, second half: validator findings, before and after, under both parsers
    validator = {}
    canon_root = work / "canon-bundles"
    for bundle in sorted({r.split("/")[0] for r in files}):
        dst = canon_root / bundle
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(corpus / bundle, dst)
        for rel in files:
            if rel.split("/")[0] == bundle and rel in models:
                (canon_root / rel).write_text((work / "py" / rel).read_text(encoding="utf-8"), encoding="utf-8")
        for parser in ("stdlib", "pyyaml"):
            before, after = findings(corpus / bundle, parser == "pyyaml"), findings(dst, parser == "pyyaml")
            validator[f"{bundle} ({parser})"] = {"identical": before == after, "passed": before[0],
                                                 "findings": len(before[1])}
    validator_ok = all(v["identical"] for v in validator.values())

    # H4: through Postgres jsonb
    if db_url:
        import psycopg
        with psycopg.connect(db_url, autocommit=True) as conn:
            conn.execute("drop table if exists e13_concepts")
            conn.execute("create table e13_concepts (rel text primary key, fm jsonb not null, body text not null)")
            with conn.cursor() as cur:
                for rel, (fm, body) in models.items():
                    cur.execute("insert into e13_concepts values (%s, %s::jsonb, %s)", (rel, json.dumps(fm), body))
            for rel, fm_json, body in conn.execute("select rel, fm::text, body from e13_concepts"):
                regen = canon.serialise(json.loads(fm_json), body)
                ok = regen == (work / "py" / rel).read_text(encoding="utf-8")
                res["H4"]["n"] += 1
                res["H4"]["ok"] += ok
                if not ok and len(fails["H4"]) < 15:
                    fails["H4"].append(rel)

    rate = lambda h: (res[h]["ok"], res[h]["n"])
    passed = {h: (res[h]["n"] > 0 and res[h]["ok"] == res[h]["n"]) for h in res}
    passed["H2"] = passed["H2"] and validator_ok and not whole_floats
    if not db_url:
        passed["H4"] = None
    out = {
        "concepts": len(models),
        "files_listed": len(files),
        "results": {h: {"ok": rate(h)[0], "of": rate(h)[1], "pass": passed[h]} for h in res},
        "validator_before_after": validator,
        "whole_number_floats": whole_floats,
        "whole_number_floats_documented_limit": documented_limit,
        "dates_option": canon.DATES,
        "yaml11_view_changes": {b: {"values": v, "concepts": c} for b, (v, c) in sorted(y11_changes.items())},
        "yaml11_view_changes_total": sum(v for v, _ in y11_changes.values()),
        "variant_generator_invalid": dict(gen_invalid),
        "failures": dict(fails),
        "diagnostic_already_canonical": {b: {"canonical": c, "of": n} for b, (n, c) in sorted(diag.items())},
    }
    (HERE / os.environ.get("E13_RESULTS", "results.json")).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"concepts": out["concepts"], "results": out["results"],
                      "validator_identical": validator_ok,
                      "whole_number_floats": len(whole_floats),
                      "dates_option": canon.DATES,
                      "yaml11_view_changes_total": out["yaml11_view_changes_total"],
                      "already_canonical": out["diagnostic_already_canonical"]}, indent=1))


if __name__ == "__main__":
    main()
