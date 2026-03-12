#!/usr/bin/env bash
# ==============================================================================
# verify_claude_work.sh — Enhanced verification after Claude Code finishes a task
# ==============================================================================
# Checks: Git, Tests, Syntax, Key Files, Secrets, Imports, API Health,
#         Security Scan, Performance Check
#
# Usage: bash ~/polymarket-agent/scripts/verify_claude_work.sh
# Returns exit code 0 = all good, 1 = something is wrong
# ==============================================================================

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

pass() { echo -e "${GREEN}✅ PASS${NC}: $1"; PASS=$((PASS + 1)); }
fail() { echo -e "${RED}❌ FAIL${NC}: $1"; FAIL=$((FAIL + 1)); }
warn() { echo -e "${YELLOW}⚠️  WARN${NC}: $1"; WARN=$((WARN + 1)); }
info() { echo -e "${BLUE}ℹ️  INFO${NC}: $1"; }

echo "=========================================="
echo "🔍 Enhanced Claude Code Work Verification"
echo "   $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# ---------- 1. Git checks ----------
echo "--- Git Status ---"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "DETACHED")
if [ "$BRANCH" = "claude/polymarket-trading-agent-LJYBO" ]; then
    pass "On correct branch: $BRANCH"
else
    fail "Wrong branch: $BRANCH (expected claude/polymarket-trading-agent-LJYBO)"
fi

if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
    pass "No uncommitted changes (Claude committed its work)"
else
    warn "Uncommitted changes detected — Claude may not have committed"
    git diff --stat 2>/dev/null || true
fi

LAST_COMMIT_EPOCH=$(git log -1 --format=%ct 2>/dev/null || echo "0")
NOW_EPOCH=$(date +%s)
AGE_MINUTES=$(( (NOW_EPOCH - LAST_COMMIT_EPOCH) / 60 ))
if [ "$AGE_MINUTES" -lt 30 ]; then
    pass "Last commit was ${AGE_MINUTES}m ago (recent)"
else
    warn "Last commit was ${AGE_MINUTES}m ago — Claude may not have committed new work"
fi

LAST_MSG=$(git log -1 --format='%s' 2>/dev/null || echo "none")
echo "   Last commit: $LAST_MSG"
echo ""

# ---------- 2. Tests ----------
echo "--- Running Tests ---"
TEST_OUTPUT=$(python -m pytest --tb=short -q 2>&1)
TEST_EXIT=$?
echo "$TEST_OUTPUT" | tail -5
if [ $TEST_EXIT -eq 0 ]; then
    TEST_COUNT=$(echo "$TEST_OUTPUT" | grep -oP '\d+ passed' | grep -oP '\d+' || echo "?")
    pass "All $TEST_COUNT tests passed"
else
    fail "Tests are FAILING — Claude broke something"
fi
echo ""

# ---------- 3. Syntax check ----------
echo "--- Syntax Check ---"
SYNTAX_ERRORS=0
for pyfile in $(find src/ -name '*.py' -type f 2>/dev/null); do
    if ! python -c "import py_compile; py_compile.compile('$pyfile', doraise=True)" 2>/dev/null; then
        fail "Syntax error in $pyfile"
        SYNTAX_ERRORS=$((SYNTAX_ERRORS + 1))
    fi
done

if [ $SYNTAX_ERRORS -eq 0 ]; then
    pass "All Python files have valid syntax"
fi
echo ""

# ---------- 4. Key files exist ----------
echo "--- Key Files ---"
MISSING=0
for f in \
    "src/main.py" \
    "src/config.py" \
    "src/context.py" \
    "src/core/pipeline.py" \
    "src/core/probability.py" \
    "src/core/scanner.py" \
    "src/core/edge.py" \
    "src/core/kelly.py" \
    "src/core/risk.py" \
    "src/core/executor.py" \
    "src/core/portfolio.py" \
    "src/integrations/telegram.py" \
    "requirements.txt" \
    ".env.example"; do
    if [ ! -f "$f" ]; then
        fail "Missing key file: $f"
        MISSING=$((MISSING + 1))
    fi
done
if [ $MISSING -eq 0 ]; then
    pass "All 14 key files present"
fi
echo ""

# ---------- 5. OpenRouter integration check ----------
echo "--- OpenRouter Integration ---"
if grep -q 'openrouter' src/core/probability.py 2>/dev/null; then
    pass "OpenRouter provider exists in probability.py"
else
    warn "OpenRouter not found in probability.py"
fi

if grep -q 'openrouter_api_key' src/config.py 2>/dev/null; then
    pass "openrouter_api_key in config.py"
else
    warn "openrouter_api_key not in config.py"
fi

if grep -q 'openrouter_estimate' src/data/schemas.py 2>/dev/null; then
    pass "openrouter_estimate field in schemas.py"
else
    warn "openrouter_estimate not in schemas.py"
fi

if grep -q 'OPENROUTER_API_KEY' .env.example 2>/dev/null; then
    pass "OPENROUTER_API_KEY in .env.example"
else
    warn "OPENROUTER_API_KEY not in .env.example"
fi
echo ""

# ---------- 6. No accidental secrets ----------
echo "--- Secret Safety ---"
LEAKED=0
for pattern in 'sk-ant-[a-zA-Z0-9_-]\{20,\}' 'sk-proj-[a-zA-Z0-9_-]\{20,\}' 'AIza[a-zA-Z0-9_-]\{35\}' 'AKIA[A-Z0-9]\{16\}'; do
    MATCHES=$(grep -rn "$pattern" src/ tests/ 2>/dev/null \
        | grep -v 're\.compile' \
        | grep -v 'assert.*not in' \
        | grep -v '# Anthropic' \
        | grep -v '# Google' \
        | grep -v 'read -p' \
        | grep -v 'test_.*\.py:.*".*key' \
        | grep -v 'test_.*\.py:.*msg = ' \
        || true)
    if [ -n "$MATCHES" ]; then
        fail "Possible hardcoded secret found:"
        echo "$MATCHES"
        LEAKED=$((LEAKED + 1))
    fi
done
if [ $LEAKED -eq 0 ]; then
    pass "No hardcoded secrets detected"
fi
echo ""

# ---------- 7. Import check ----------
echo "--- Import Check ---"
if python -c "from src.config import StaticConfig; print('StaticConfig OK')" 2>/dev/null; then
    pass "src.config imports cleanly"
else
    fail "src.config import failed"
fi
if python -c "from src.core.probability import call_single_llm, calculate_consensus; print('probability OK')" 2>/dev/null; then
    pass "src.core.probability imports cleanly"
else
    fail "src.core.probability import failed"
fi
echo ""

# ---------- 8. API Health Check (NEW) ----------
echo "--- API Health Check ---"
HEALTH=$(curl -sf --connect-timeout 3 http://localhost:8000/health 2>/dev/null)
if [ -n "$HEALTH" ]; then
    STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
    if [ "$STATUS" = "ok" ]; then
        pass "Trading API health: OK"
    else
        warn "Trading API health: $STATUS"
    fi

    # Check trading mode hasn't accidentally changed
    MODE=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('trading_mode','unknown'))" 2>/dev/null || echo "unknown")
    if [ "$MODE" = "paper" ]; then
        pass "Trading mode: paper (safe)"
    elif [ "$MODE" = "live" ]; then
        warn "Trading mode: LIVE — verify this is intentional"
    else
        info "Trading mode: $MODE"
    fi
else
    warn "Trading API not reachable (may be expected if not running)"
fi
echo ""

# ---------- 9. Security Scan on Changed Files (NEW) ----------
echo "--- Security Scan ---"
CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | grep '\.py$' || true)
SEC_ISSUES=0

if [ -n "$CHANGED_FILES" ]; then
    for f in $CHANGED_FILES; do
        if [ -f "$f" ]; then
            # Check for eval/exec (code injection risk)
            if grep -n 'eval(' "$f" 2>/dev/null | grep -v '# safe' | grep -v 'test_' | grep -v '#.*eval' >/dev/null; then
                warn "eval() found in $f — verify it's safe"
                SEC_ISSUES=$((SEC_ISSUES + 1))
            fi

            # Check for subprocess with shell=True
            if grep -n 'shell=True' "$f" 2>/dev/null | grep -v '# safe' | grep -v 'test_' >/dev/null; then
                warn "shell=True in $f — potential command injection"
                SEC_ISSUES=$((SEC_ISSUES + 1))
            fi

            # Check for SQL string formatting (injection risk)
            if grep -nP 'f".*SELECT|f".*INSERT|f".*UPDATE|f".*DELETE' "$f" 2>/dev/null | grep -v 'test_' >/dev/null; then
                warn "Possible SQL injection in $f — use parameterized queries"
                SEC_ISSUES=$((SEC_ISSUES + 1))
            fi

            # Check for hardcoded URLs with credentials
            if grep -nP 'https?://[^/]*:[^/]*@' "$f" 2>/dev/null | grep -v 'test_' | grep -v '#' >/dev/null; then
                fail "Hardcoded credentials in URL in $f"
                SEC_ISSUES=$((SEC_ISSUES + 1))
            fi
        fi
    done

    if [ $SEC_ISSUES -eq 0 ]; then
        pass "Security scan clean on $(echo "$CHANGED_FILES" | wc -l) changed files"
    fi
else
    info "No Python files changed — security scan skipped"
fi
echo ""

# ---------- 10. Performance Check (NEW) ----------
echo "--- Performance Check ---"

# Memory check
MEM_USED_PCT=$(free 2>/dev/null | awk '/Mem:/ {printf "%.0f", $3/$2*100}')
if [ -n "$MEM_USED_PCT" ]; then
    if [ "$MEM_USED_PCT" -lt 80 ]; then
        pass "Memory usage: ${MEM_USED_PCT}% (healthy)"
    elif [ "$MEM_USED_PCT" -lt 90 ]; then
        warn "Memory usage: ${MEM_USED_PCT}% (elevated)"
    else
        fail "Memory usage: ${MEM_USED_PCT}% (critical)"
    fi
fi

# Disk check
DISK_USED_PCT=$(df / 2>/dev/null | awk 'NR==2 {gsub(/%/,""); print $5}')
if [ -n "$DISK_USED_PCT" ]; then
    if [ "$DISK_USED_PCT" -lt 80 ]; then
        pass "Disk usage: ${DISK_USED_PCT}% (healthy)"
    elif [ "$DISK_USED_PCT" -lt 90 ]; then
        warn "Disk usage: ${DISK_USED_PCT}% (elevated)"
    else
        fail "Disk usage: ${DISK_USED_PCT}% (critical — clean up!)"
    fi
fi

# Load check
LOAD=$(uptime 2>/dev/null | awk -F'load average:' '{print $2}' | awk -F, '{gsub(/ /,""); print $1}')
if [ -n "$LOAD" ]; then
    # Compare with number of CPUs
    CPUS=$(nproc 2>/dev/null || echo 2)
    LOAD_INT=$(echo "$LOAD" | awk '{printf "%d", $1}')
    if [ "$LOAD_INT" -lt "$CPUS" ]; then
        pass "CPU load: $LOAD (healthy for $CPUS cores)"
    else
        warn "CPU load: $LOAD (high for $CPUS cores)"
    fi
fi
echo ""

# ---------- Summary ----------
echo "=========================================="
TOTAL=$((PASS + FAIL + WARN))
echo -e "Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC} (${TOTAL} total)"

if [ $FAIL -gt 0 ]; then
    echo -e "${RED}❌ VERIFICATION FAILED — Claude Code did NOT complete the work correctly.${NC}"
    echo "   Do NOT tell the user it's done. Fix the issues first."
    exit 1
elif [ $WARN -gt 0 ]; then
    echo -e "${YELLOW}⚠️  VERIFICATION PASSED WITH WARNINGS — Review the warnings above.${NC}"
    exit 0
else
    echo -e "${GREEN}✅ VERIFICATION PASSED — Claude Code work is confirmed done.${NC}"
    exit 0
fi
