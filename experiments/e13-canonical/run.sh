#!/usr/bin/env bash
# experiments/e13-canonical/run.sh
#
# E13 — Canonical serialisation (PLAN.md fixes the hypotheses and pass marks).
#
# Assembles the corpus, canonicalises every concept with canon.py and canon.ts (twice each, for
# idempotence), then measure.py computes H1–H6 and the producer diagnostic into results.json.
#
# Needs: uv, bun. Optional: Docker (H4, the Postgres round trip; and the Longview diagnostic with
# E13_LONGVIEW=1, which also needs ~/Documents/GitHub/longview). Downloads no third-party code: the
# KnowledgeX notebook is a fixture saved from E9 (knowledgex@0.4.0, 2026-10-02), and containers
# listen on 127.0.0.1 only. Writes only to a temp directory, plus results.json here. Never touches
# an existing container.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
W="$(mktemp -d -t e13)"
C="$W/corpus"
mkdir -p "$C"
echo "# E13 run, $(date -u +%Y-%m-%dT%H:%M:%SZ), workdir $W"

copy() { mkdir -p "$C/$2"; (cd "$1" && tar --exclude .git -cf - .) | (cd "$C/$2" && tar -xf -); }
copy "$REPO/examples" examples
copy "$REPO/experiments/fixtures/data-eng" fixtures-data-eng
copy "$REPO/experiments/fixtures/household" fixtures-household
for b in a b c; do copy "$REPO/experiments/e2-resolution/bundle-$b" "e2-bundle-$b"; done
for b in psychology-kb ai-concepts-kb; do
  if [ -d "$HOME/Documents/GitHub/$b" ]; then copy "$HOME/Documents/GitHub/$b" "$b"; else echo "skip: $b not found"; fi
done

# A KnowledgeX notebook (a third-party producer): saved from E9's run rather than regenerated, so
# no package is downloaded and run here.
copy "$HERE/fixtures/knowledgex" knowledgex

DOCKER=0; command -v docker >/dev/null && docker info >/dev/null 2>&1 && DOCKER=1

# Longview's export, from its mock eval-day fixture on a throwaway database (opt-in).
if [ "${E13_LONGVIEW:-0}" = 1 ] && [ "$DOCKER" = 1 ] && [ -d "$HOME/Documents/GitHub/longview" ]; then
  docker run -d --rm --name aixf-e13-lv -e POSTGRES_USER=longview -e POSTGRES_PASSWORD=longview \
    -e POSTGRES_DB=longview -p 127.0.0.1:55416:5432 pgvector/pgvector:pg17 >/dev/null
  trap 'docker stop aixf-e13-lv >/dev/null 2>&1 || true' EXIT
  for _ in $(seq 1 30); do docker exec aixf-e13-lv pg_isready -U longview -q && break; sleep 1; done
  (cd "$HOME/Documents/GitHub/longview" && export DATABASE_URL=postgres://longview:longview@localhost:55416/longview \
     RESEND_API_KEY= LONGVIEW_LLM=mock && bun --no-env-file run db:migrate >/dev/null && \
     bun --no-env-file run scripts/eval-day.ts >/dev/null && bun --no-env-file run export:ai-xf --out "$C/longview" >/dev/null)
  docker stop aixf-e13-lv >/dev/null; trap - EXIT
else
  echo "skip: Longview export (set E13_LONGVIEW=1, needs Docker and the longview checkout)"
fi

# Every concept file: any .md that is not index.md or log.md.
(cd "$C" && find . -name '*.md' ! -name index.md ! -name log.md | sed 's#^\./##' | LC_ALL=C sort) > "$W/list.txt"
echo "concept files: $(wc -l < "$W/list.txt" | tr -d ' ')"

cd "$HERE"
[ -d node_modules ] || bun install --frozen-lockfile >/dev/null
uv run -q --with pyyaml python3 canon.py "$C" "$W/py" "$W/list.txt"
bun run canon.ts "$C" "$W/ts" "$W/list.txt"
uv run -q --with pyyaml python3 canon.py "$W/py" "$W/py2" "$W/list.txt"
bun run canon.ts "$W/ts" "$W/ts2" "$W/list.txt"

# H4: a throwaway Postgres for the jsonb round trip.
DB_ARGS=()
if [ "$DOCKER" = 1 ]; then
  docker run -d --rm --name aixf-e13-pg -e POSTGRES_PASSWORD=e13 -p 127.0.0.1:55413:5432 postgres:17 >/dev/null
  trap 'docker stop aixf-e13-pg >/dev/null 2>&1 || true' EXIT
  for _ in $(seq 1 30); do docker exec aixf-e13-pg pg_isready -U postgres -q && break; sleep 1; done
  DB_ARGS=(--db "postgresql://postgres:e13@localhost:55413/postgres")
else
  echo "skip: H4 (no Docker)"
fi

uv run -q --with pyyaml --with 'psycopg[binary]' python3 measure.py "$W" "${DB_ARGS[@]}"
