#!/usr/bin/env python3
"""Writes E15's fixture federations (PLAN.md). Deterministic: re-running rewrites the same files.

    python3 experiments/e15-precedence/make_fixtures.py

Four federations, each a directory under fixtures/ with a federation.ai-xf.yaml:

  f1  alpha, beta, gamma: id, alias and path collisions (gaps 1, 2, 5)
  f2  the same three bundles with a declared `precedence` (the proposed explicit order)
  f3  teama, team-b, zed: namespaces whose byte order and Postgres's default order differ (gap 3)
  f4  outer with team nested inside it (gap 4)

Every concept is minimal and passes Level 2 on its own bundle, except where a case needs otherwise
(outer, today, fails on the nested duplicate id: that is gap 4).
"""
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
AT = "2026-10-04T09:00:00Z"


def concept(path: Path, cid: str, title: str, aliases=(), note: str = "E15 fixture concept."):
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---", "type: Concept", f"id: {cid}", f"title: {title}", f"description: {note}"]
    if aliases:
        fm += ["aliases:"] + [f"  - {a}" for a in aliases]
    fm += ["generated:", "  by: human:e15-fixture", f"  at: {AT}", "---", "", f"# {title}", "", note, ""]
    path.write_text("\n".join(fm), encoding="utf-8")


def manifest(root: Path, ns: str, desc: str):
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.ai-xf.yaml").write_text(
        f'ai-xf: "0.5"\nname: {ns}\nnamespace: {ns}\ndescription: {desc}\n'
        f"producer: human:e15-fixture\ngenerated: {AT}\nconformance: 2\n", encoding="utf-8")


def federation(root: Path, name: str, bundles: list[tuple[str, str]], extra: str = ""):
    lines = ['ai-xf: "0.5"', f"federation: {name}", "bundles:"]
    for ns, rel in bundles:
        lines += [f"  - namespace: {ns}", "    source: path", f"    path: {rel}"]
    (root / "federation.ai-xf.yaml").write_text("\n".join(lines) + "\n" + extra, encoding="utf-8")


def f1_bundles(root: Path):
    a, b, g = root / "alpha", root / "beta", root / "gamma"
    manifest(a, "alpha", "E15 f1: holds the referencing concepts, a renamed concept and a path target.")
    concept(a / "concepts/glossary.md", "glossary", "Glossary (alpha)")
    concept(a / "concepts/renamed.md", "renamed", "Renamed (alpha)", aliases=["old-name"],
            note="Was called old-name; beta also has a live concept with that id.")
    concept(a / "concepts/home.md", "home", "Home (alpha)", note="A path target: concepts/home.md.")
    concept(a / "concepts/legacy.md", "legacy-thing", "Legacy thing (alpha)", aliases=["former"],
            note="Alias `former`; no other bundle has a concept with that id.")
    concept(a / "concepts/common.md", "common", "Common (alpha)", note="Also in beta: ordering alpha against beta.")
    manifest(b, "beta", "E15 f1: collides with alpha on ids and aliases.")
    concept(b / "concepts/glossary.md", "glossary", "Glossary (beta)")
    concept(b / "concepts/old-name.md", "old-name", "Old name (beta)", note="A live id equal to alpha's alias.")
    concept(b / "concepts/beta-only.md", "beta-only", "Beta only")
    concept(b / "concepts/beta-thing.md", "beta-thing", "Beta thing", aliases=["nickname"])
    concept(b / "concepts/shared-x.md", "shared-x", "Shared X (beta)")
    concept(b / "concepts/common.md", "common", "Common (beta)", note="Also in alpha.")
    manifest(g, "gamma", "E15 f1: a third bundle, so collisions have more than two candidates.")
    concept(g / "concepts/glossary.md", "glossary", "Glossary (gamma)")
    concept(g / "concepts/gamma-thing.md", "gamma-thing", "Gamma thing", aliases=["nickname"])
    concept(g / "concepts/gamma-only.md", "gamma-only", "Gamma only")
    concept(g / "concepts/shared-x.md", "shared-x", "Shared X (gamma)")


def main():
    if FIX.exists():
        shutil.rmtree(FIX)
    shared = FIX / "f1"
    f1_bundles(shared)
    federation(shared, "e15-f1", [("alpha", "./alpha"), ("beta", "./beta"), ("gamma", "./gamma")])

    f2 = FIX / "f2"                       # same bundles, declared order; gamma before beta, alpha unlisted
    f2.mkdir(parents=True)
    federation(f2, "e15-f2", [("alpha", "../f1/alpha"), ("beta", "../f1/beta"), ("gamma", "../f1/gamma")],
               extra="precedence: [gamma, beta]\n")

    f3 = FIX / "f3"
    for ns in ("teama", "team-b"):
        manifest(f3 / ns, ns, f"E15 f3: both teams define `handbook`; {ns}.")
        concept(f3 / ns / "concepts/handbook.md", "handbook", f"Handbook ({ns})")
    manifest(f3 / "zed", "zed", "E15 f3: references `handbook` unqualified.")
    concept(f3 / "zed/concepts/reader.md", "reader", "Reader (zed)")
    federation(f3, "e15-f3", [("teama", "./teama"), ("team-b", "./team-b"), ("zed", "./zed")])

    f4 = FIX / "f4"
    manifest(f4 / "outer", "outer", "E15 f4: a department bundle with a team bundle nested inside it.")
    concept(f4 / "outer/concepts/glossary.md", "glossary", "Glossary (outer)")
    concept(f4 / "outer/concepts/policy.md", "policy", "Policy (outer)")
    manifest(f4 / "outer/team", "team", "E15 f4: nested inside outer, with its own manifest.")
    concept(f4 / "outer/team/concepts/glossary.md", "glossary", "Glossary (team)",
            note="Same id as outer's glossary: the scoped definition.")
    concept(f4 / "outer/team/concepts/runbook.md", "runbook", "Runbook (team)")
    federation(f4, "e15-f4", [("outer", "./outer"), ("team", "./outer/team")])


if __name__ == "__main__":
    main()
