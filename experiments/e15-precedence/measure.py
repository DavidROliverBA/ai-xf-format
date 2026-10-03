#!/usr/bin/env python3
"""E15 measurements (PLAN.md). Run by run.sh; each mode writes one JSON file.

    measure.py before   <validator.py> <out.json>   current behaviour per case, from a probe link (no pass mark)
    measure.py snapshot <validator.py> <out.json>   H3 corpus: validator JSON under both parsers
    measure.py resolve  <validator.py> <out.json>   (b): --resolve for every case, under both parsers
    measure.py compare  <results-dir>               H1-H5 and the step-4 decision -> results.json
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
GH = Path.home() / "Documents" / "GitHub"
CASES = json.loads((HERE / "cases.json").read_text())["cases"]


def run(validator: str, args: list[str], pyyaml: bool, cwd: Path = REPO) -> tuple[int, str]:
    pre = ["uv", "run", "-q", "--with", "pyyaml", "python3"] if pyyaml else [sys.executable]
    r = subprocess.run(pre + [validator, *args], capture_output=True, text=True, cwd=cwd)
    return r.returncode, r.stdout


def bundle_root(fed: Path, ns: str) -> Path:
    text = fed.read_text()
    m = re.search(rf"- namespace: {re.escape(ns)}\n\s+source: path\n\s+path: (\S+)", text)
    return (fed.parent / m.group(1)).resolve()


def before(validator: str, out: str):
    rows = []
    for c in CASES:
        with tempfile.TemporaryDirectory() as t:
            fx = Path(t) / "fixtures"
            shutil.copytree(HERE / "fixtures", fx)
            fed = Path(t) / c["federation"]
            root = bundle_root(fed, c["from_namespace"])
            concept = root / c["from_concept"]
            head, sep, body = concept.read_text().partition("\n---\n")
            head += f"\nlinks:\n  - rel: relates-to\n    to: {c['to']}"
            concept.write_text(head + sep + body + f"\nSee [the target]({c['to']}).\n")
            _, outp = run(validator, [str(root), "--level", "2", "--federation", str(fed), "--json"], False)
            data = json.loads(outp)
            msgs = [f"{f['severity']}: {f['message']}" for f in data["findings"]
                    if f.get("path", f.get("file")) == c["from_concept"] or "duplicate id" in f["message"]]
            rows.append({"case": c["case"], "gap": c["gap"], "to": c["to"], "findings": msgs})
    Path(out).write_text(json.dumps({"cases": rows}, indent=1) + "\n")


def corpus() -> list[tuple[str, list[str]]]:
    items = [
        ("examples", ["examples", "--level", "3"]),
        ("fixtures/data-eng", ["experiments/fixtures/data-eng", "--level", "3", "--federation",
                               "experiments/fixtures/federation.ai-xf.yaml"]),
        ("fixtures/household", ["experiments/fixtures/household", "--level", "3", "--federation",
                                "experiments/fixtures/federation.ai-xf.yaml"]),
    ]
    for b in "abc":
        items.append((f"e2/bundle-{b}", [f"experiments/e2-resolution/bundle-{b}", "--level", "2", "--federation",
                                          "experiments/e2-resolution/federation.ai-xf.yaml"]))
    for kb in ("psychology-kb", "ai-concepts-kb"):
        if (GH / kb).is_dir():
            items.append((kb, [str(GH / kb), "--level", "3", "--federation",
                               "experiments/real-federation/federation.ai-xf.yaml"]))
    return items


def snapshot(validator: str, out: str):
    res = {}
    for name, args in corpus():
        for parser in ("stdlib", "pyyaml"):
            code, o = run(validator, args + ["--json"], parser == "pyyaml")
            d = json.loads(o)
            d.pop("bundle", None)
            res[f"{name} [{parser}]"] = {"exit": code, "result": d}
    Path(out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")


def resolve(validator: str, out: str):
    rows = []
    for c in CASES:
        r = {}
        for parser in ("stdlib", "pyyaml"):
            code, o = run(validator, [str(HERE / c["federation"]), "--resolve", c["from_namespace"],
                                      c["from_concept"], c["to"]], parser == "pyyaml")
            r[parser] = json.loads(o) if code == 0 and o.strip() else {"exit": code, "stdout": o}
        rows.append({"case": c["case"], **r})
    Path(out).write_text(json.dumps({"cases": rows}, indent=1) + "\n")


def compare(d: str):
    d = Path(d)
    val = {r["case"]: r for r in json.loads((d / "after-resolve.json").read_text())["cases"]}
    ind = {r["case"]: r["result"] for r in json.loads((d / "results-indep.json").read_text())["cases"]}
    h1 = []
    for c in CASES:
        e, b, i = c["expected"], val[c["case"]]["pyyaml"], ind.get(c["case"])
        ok = e == b == i
        h1.append({"case": c["case"], "agree": ok, **({} if ok else {"expected": e, "validator": b, "independent": i})})
    h2 = [c["case"] for c in CASES for res in (val[c["case"]]["pyyaml"], ind.get(c["case"]) or {})
          if res.get("kind") == "id" and res.get("target")
          and not res["target"].startswith(c["from_namespace"] + "/") and not res.get("warning")]
    h5_resolve = [c["case"] for c in CASES if val[c["case"]]["stdlib"] != val[c["case"]]["pyyaml"]]
    snap_b = json.loads((d / "before-snapshot.json").read_text())
    snap_a = json.loads((d / "after-snapshot.json").read_text())
    h3_changed = sorted(k for k in snap_b if snap_b[k] != snap_a.get(k))
    h5_corpus = sorted({k.rsplit(" [", 1)[0] for k in snap_a
                        if k.endswith("[stdlib]") and snap_a[k]["result"] != snap_a[k.replace("[stdlib]", "[pyyaml]")]["result"]})
    nest = json.loads((d / "nesting.json").read_text())
    # step-4 decision: with step 4 (the validator's results), against intent
    mis = [c["case"] for c in CASES if c["intent"] and val[c["case"]]["pyyaml"].get("target")
           and val[c["case"]]["pyyaml"]["target"] != c["intent"]]
    gained = [c["case"] for c in CASES if c["intent"] and val[c["case"]]["pyyaml"].get("via") == "alias"
              and val[c["case"]]["pyyaml"].get("candidates") and val[c["case"]]["pyyaml"]["target"] == c["intent"]]
    out = {
        "H1_agree": f"{sum(x['agree'] for x in h1)}/{len(h1)}", "H1_disagreements": [x for x in h1 if not x["agree"]],
        "H2_silent_cross_bundle": h2,
        "H3_changed_corpus_entries": h3_changed, "H3_suites": json.loads((d / "suites.json").read_text()),
        "H4_nesting": nest,
        "H5_resolve_parser_diffs": h5_resolve, "H5_corpus_parser_diffs": h5_corpus,
        "step4_misresolved_against_intent": mis, "step4_gained_intended": gained,
    }
    (HERE / "results.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    mode = sys.argv[1]
    {"before": lambda: before(sys.argv[2], sys.argv[3]), "snapshot": lambda: snapshot(sys.argv[2], sys.argv[3]),
     "resolve": lambda: resolve(sys.argv[2], sys.argv[3]), "compare": lambda: compare(sys.argv[2])}[mode]()
