#!/usr/bin/env python3
"""E14 measurements (PLAN.md H1-H4) for one vault bundle, before and after re-export.

    uv run --with pyyaml python3 measure.py <label> <bundle-dir> <slice-glob> <federation.yaml>

Loads MyVault's ai-xf-export.py as a module to reuse its own sensitivity rule (sensitive_slug), so
the set of withheld targets is the exporter's, not a second opinion. Prints one JSON object.
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

VAULT = Path.home() / "Documents" / "MyVault"
REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("exporter", VAULT / ".claude" / "scripts" / "ai-xf-export.py")
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)

label, bundle, slice_glob, fed = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]

# The slice and the sensitive targets it links to (the exporter's own rule).
slice_files = sorted(VAULT.glob(slice_glob))
slice_ids = {ex.slugify(f.stem) for f in slice_files}
for f in slice_files:                       # aliases count as in-slice too, as in build_id_map
    fm, _ = ex.parse_note(f)
    for a in (fm or {}).get("aliases") or []:
        if isinstance(a, str):
            slice_ids.add(ex.slugify(a))
sensitive = {}
for f in slice_files:
    for raw in ex.WIKILINK_RE.findall(f.read_text(encoding="utf-8")):
        slug = ex.slugify(raw)
        if slug not in slice_ids and ex.sensitive_slug(slug):
            sensitive[slug] = ex.TYPE_PREFIX_RE.sub("", raw.strip())

# H1: what the exporter generated that names a withheld target (PLAN.md clarification).
src_by_id = {ex.slugify(f.stem): f for f in slice_files}
leaks = []
for p in sorted(bundle.rglob("*.md")):
    if p.name in ("index.md", "log.md"):
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    head, _, body = text.partition("\n---\n")
    related = body.split("\n## Related\n", 1)[1] if "\n## Related\n" in body else ""
    src = src_by_id.get(p.stem)
    src_text = src.read_text(encoding="utf-8", errors="replace") if src else ""
    for slug, title in sensitive.items():
        if re.search(rf"^\s*(?:-\s*)?to:\s*{re.escape(slug)}\s*$", head, re.M):
            leaks.append(f"{p.name}: to {slug}")
        if slug in related.lower() or title.lower() in related.lower():
            leaks.append(f"{p.name}: Related names {slug}")
        prose = ex.WIKILINK_RE.sub(lambda mm: "" if ex.slugify(mm.group(1)) == slug else mm.group(1), src_text)
        allowed = prose.lower().count(title.lower())
        if text.lower().count(title.lower()) > allowed:
            leaks.append(f"{p.name}: title '{title}' beyond its own prose")
for p in (bundle / "index.md", bundle / "log.md", bundle / "manifest.ai-xf.yaml"):
    if p.exists():
        t2 = p.read_text(encoding="utf-8", errors="replace").lower()
        leaks += [f"{p.name}: {slug}" for slug in sensitive if slug in t2]

# H2: markers and unresolved warnings.
markers = 0
for p in bundle.rglob("*.md"):
    if p.name in ("index.md", "log.md"):
        continue
    markers += sum(int(m) for m in re.findall(r"^\s*-\s*withheld:\s*(\d+)\s*$", p.read_text(encoding="utf-8"), re.M))


def validate(pyyaml: bool) -> dict:
    runner = ["uv", "run", "-q", "--with", "pyyaml", "python3"] if pyyaml else ["python3"]
    r = subprocess.run(runner + [str(REPO / "tools" / "ai-xf-validate.py"), str(bundle), "--level", "3",
                                 "--federation", fed, "--json"], capture_output=True, text=True)
    return json.loads(r.stdout)


v_std, v_py = validate(False), validate(True)
unresolved = sum("does not resolve" in f["message"] for f in v_py["findings"])
canon = subprocess.run(["uv", "run", "-q", "--with", "pyyaml", "python3", str(REPO / "tools" / "ai-xf-canon.py"),
                        "check", str(bundle)], capture_output=True, text=True).stdout.strip().splitlines()[-1]
print(json.dumps({
    "label": label, "sensitive_targets_linked_from_slice": len(sensitive),
    "leaks": len(leaks), "leak_examples": leaks[:5],
    "withheld_markers_sum": markers, "unresolved_warnings": unresolved,
    "level3_stdlib": v_std["passed"], "level3_pyyaml": v_py["passed"],
    "canonical": canon,
}))
