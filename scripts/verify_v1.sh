#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

select_python() {
  if [ -n "${PYTHON_BIN:-}" ]; then
    printf '%s\n' "$PYTHON_BIN"
    return 0
  fi
  local bundled_python="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
  for candidate in "$bundled_python" python3 python3.12 python3.11 /usr/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      local version_ok
      version_ok="$($candidate - <<'PY' 2>/dev/null || true
import sys
print('ok' if sys.version_info >= (3, 11) else 'old')
PY
)"
      if [ "$version_ok" = "ok" ]; then
        printf '%s\n' "$candidate"
        return 0
      fi
    fi
  done
  printf '%s\n' "python3"
}

PYTHON_BIN="$(select_python)"
VENV_DIR="${FUNDOS_VERIFY_VENV:-.venv-fundos-verify}"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
fi

if ! "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import setuptools
PY
then
  rm -rf "$VENV_DIR"
  "$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
fi

EXTRA_PYTHONPATH=""
if ! "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import yaml
PY
then
  for path in /Library/Python/3.12/site-packages /Library/Python/3.11/site-packages /Library/Python/3.9/site-packages; do
    if [ -f "$path/yaml/__init__.py" ]; then
      EXTRA_PYTHONPATH="$path"
      break
    fi
  done
fi
if [ -n "$EXTRA_PYTHONPATH" ]; then
  export PYTHONPATH="$EXTRA_PYTHONPATH${PYTHONPATH:+:$PYTHONPATH}"
fi

echo "[AwesomeFundOS] running unit test suite"
"$VENV_DIR/bin/python" -m pip install --no-build-isolation --no-deps -e . >/dev/null
"$VENV_DIR/bin/python" -m unittest discover -s tests -q

echo "[AwesomeFundOS] running system doctor"
DOCTOR_OUTPUT="$($VENV_DIR/bin/fundos system doctor)"
printf '%s\n' "$DOCTOR_OUTPUT"

echo "$DOCTOR_OUTPUT" | grep -F "doctor_status=pass" >/dev/null
echo "$DOCTOR_OUTPUT" | grep -F "failed_checks=0" >/dev/null
echo "$DOCTOR_OUTPUT" | grep -F "real_trade_allowed=False" >/dev/null
echo "$DOCTOR_OUTPUT" | grep -F "broker_integration=disabled" >/dev/null

echo "[AwesomeFundOS] running strict system audit"
AUDIT_OUTPUT="$($VENV_DIR/bin/python -m fundos.cli system audit --strict)"
printf '%s\n' "$AUDIT_OUTPUT"

echo "$AUDIT_OUTPUT" | grep -F "failed_requirements=0" >/dev/null
echo "$AUDIT_OUTPUT" | grep -F "real_trade_allowed=False" >/dev/null
echo "$AUDIT_OUTPUT" | grep -F "broker_integration=disabled" >/dev/null

echo "[AwesomeFundOS] checking patch whitespace"
git diff --check

echo "[AwesomeFundOS] V1 verification passed: real_trade_allowed=False broker_integration=disabled"
