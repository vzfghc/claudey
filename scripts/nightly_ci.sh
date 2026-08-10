#!/usr/bin/env bash
# Nightly adversarial batteries, runnable locally (informational, non-blocking).
# Mirrors .github/workflows/nightly.yml: mutmut mutation + Schemathesis schema fuzz.
# Never blocks: prints a summary and exits 0 unless the harness itself is broken.
#
# Requires: uv on PATH (the same environment as scripts/ci.sh).

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UV="${UV:-uv}"
FAILED=0

echo "==> mutation: mutmut (providers/ + application/)"
(
  cd "$ROOT"
  "$UV" run mutmut run
) && echo "mutmut: ok" || { echo "mutmut: mutants survived (expected)"; FAILED=1; }
(
  cd "$ROOT"
  "$UV" run mutmut results 2>&1 | tail -5 || true
)

echo "==> schema fuzz: schemathesis (api handlers, admin excluded)"
(
  cd "$ROOT"
  "$UV" run uvicorn scripts.hans_schemathesis_app:app --host 127.0.0.1 --port 8082 &
  UV_PID=$!
  trap 'kill "$UV_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do
    if curl -fsS http://127.0.0.1:8082/health >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  "$UV" run schemathesis run http://127.0.0.1:8082/openapi.json \
    -u http://127.0.0.1:8082 \
    -n 25 \
    --max-failures 50 \
    --exclude-path-regex '^/admin' \
    --exclude-path-regex '^/docs' \
    --exclude-path-regex '^/openapi' \
    --exclude-path-regex '^/health' \
    --suppress-health-check all
) && echo "schemathesis: ok" || { echo "schemathesis: failures found (informational)"; FAILED=1; }

echo "==> done (informational; exit code: $FAILED)"
exit 0