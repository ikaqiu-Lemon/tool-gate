#!/bin/sh
# check-demo-env.sh — preflight for tool-gate demo workspaces.
# Reads nothing, runs nothing but read-only probes; fails only on ❌.
# Docs: examples/QUICKSTART.md §7.

set -eu

STATUS_OK=0
STATUS_WARN=0
STATUS_FAIL=0

ok()   { printf '  \033[32m✅\033[0m  %s\n' "$1"; STATUS_OK=$((STATUS_OK + 1)); }
warn() { printf '  \033[33m⚠️\033[0m  %s\n' "$1"; STATUS_WARN=$((STATUS_WARN + 1)); }
fail() { printf '  \033[31m❌\033[0m  %s\n' "$1"; STATUS_FAIL=$((STATUS_FAIL + 1)); }

REPO_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

echo
echo "── tool-gate demo preflight ─────────────────────────────────"

# 1. Python ≥ 3.11
if py=$(command -v python3 2>/dev/null || command -v python 2>/dev/null); then
    ver=$("$py" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")
    case "$ver" in
        3.1[1-9]|3.[2-9][0-9]|[4-9].*) ok "python $ver ($py)" ;;
        3.[0-9]|3.10|3.1) fail "python $ver — need 3.11+; see QUICKSTART §2" ;;
        *) warn "python found at $py but version $ver unparseable" ;;
    esac
else
    fail "python / python3 not found in PATH"
fi

# 2. tg-hook console script on PATH
if command -v tg-hook >/dev/null 2>&1; then
    ok "tg-hook on PATH ($(command -v tg-hook))"
else
    fail "tg-hook missing — run 'pip install -e \".[dev]\"' from $REPO_ROOT"
fi

# 3. tg-mcp console script on PATH
if command -v tg-mcp >/dev/null 2>&1; then
    ok "tg-mcp on PATH ($(command -v tg-mcp))"
else
    fail "tg-mcp missing — run 'pip install -e \".[dev]\"' from $REPO_ROOT"
fi

# 4. claude CLI (optional — absence is ⚠️ not ❌; Method B still works)
if command -v claude >/dev/null 2>&1; then
    ok "claude CLI on PATH ($(command -v claude)) — Method A available"
else
    warn "claude CLI not found — only Method B (offline replay) available; see QUICKSTART §3"
fi

# 5. Each workspace .mcp.json JSON-parseable
for ws in "$REPO_ROOT"/examples/0[1-9]-*; do
    [ -d "$ws" ] || continue
    mcp="$ws/.mcp.json"
    if [ ! -f "$mcp" ]; then
        warn "${ws##*/}/.mcp.json missing"
        continue
    fi
    if "$py" -c "import json,sys; json.load(open(sys.argv[1]))" "$mcp" 2>/dev/null; then
        ok "${ws##*/}/.mcp.json valid JSON"
    else
        fail "${ws##*/}/.mcp.json parse error"
    fi
done

# 6. Each workspace mcp/*.py parses as valid Python
for ws in "$REPO_ROOT"/examples/0[1-9]-*; do
    [ -d "$ws/mcp" ] || continue
    for f in "$ws"/mcp/mock_*.py; do
        [ -f "$f" ] || continue
        if "$py" -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f" 2>/dev/null; then
            ok "${f#$REPO_ROOT/} parses"
        else
            fail "${f#$REPO_ROOT/} syntax error"
        fi
    done
done

echo "──────────────────────────────────────────────────────────────"
printf "Summary: %d OK · %d warn · %d fail\n" "$STATUS_OK" "$STATUS_WARN" "$STATUS_FAIL"
echo

if [ "$STATUS_FAIL" -gt 0 ]; then
    echo "One or more ❌ checks failed. See QUICKSTART §6 (troubleshooting)."
    exit 1
fi
exit 0
