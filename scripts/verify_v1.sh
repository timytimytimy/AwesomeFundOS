#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[AwesomeFundOS] running unit test suite"
python3 -m pip install -e . >/dev/null
python3 -m unittest discover -s tests -q

echo "[AwesomeFundOS] running strict system audit"
AUDIT_OUTPUT="$(python3 -m fundos.cli system audit --strict)"
printf '%s\n' "$AUDIT_OUTPUT"

echo "$AUDIT_OUTPUT" | grep -F "failed_requirements=0" >/dev/null
echo "$AUDIT_OUTPUT" | grep -F "real_trade_allowed=False" >/dev/null
echo "$AUDIT_OUTPUT" | grep -F "broker_integration=disabled" >/dev/null

echo "[AwesomeFundOS] checking patch whitespace"
git diff --check

echo "[AwesomeFundOS] V1 verification passed: real_trade_allowed=False broker_integration=disabled"
