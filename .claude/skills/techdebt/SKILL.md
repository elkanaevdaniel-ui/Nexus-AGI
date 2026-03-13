---
name: techdebt
description: >
  Find and kill duplicated code, dead imports, unused variables, and technical debt
  at the end of every coding session. Use this skill whenever the user says "/techdebt",
  "clean up", "find duplicates", "dead code", "unused imports", "end of session cleanup",
  or any request to reduce technical debt. Also trigger proactively at the end of any
  multi-file editing session — suggest running a techdebt scan before committing.
---

# Tech Debt Scanner

Run this at the end of every coding session to catch problems before they compound.

## Scan Checklist

### 1. Duplicate Code Detection
```bash
# Find duplicate function definitions across Python files
grep -rn "^def " --include="*.py" | sort -t: -k3 | uniq -d -f2
# Find duplicate class definitions
grep -rn "^class " --include="*.py" | sort -t: -k3 | uniq -d -f2
```

### 2. Dead Imports
```bash
for f in $(git diff --name-only --diff-filter=M -- '*.py'); do
  echo "=== $f ==="
  python3 -c "
import ast, sys
with open('$f') as fh:
    tree = ast.parse(fh.read())
imports = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            imports.append(alias.asname or alias.name)
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            imports.append(alias.asname or alias.name)
with open('$f') as fh:
    content = fh.read()
for imp in imports:
    uses = content.count(imp) - 1
    if uses <= 0:
        print(f'  UNUSED: {imp}')
" 2>/dev/null
done
```

### 3. Coding Standard Violations
```bash
echo "=== sync requests violations ==="
grep -rn "import requests" --include="*.py" | grep -v "httpx"
echo "=== potential hardcoded secrets ==="
grep -rn "api_key\s*=\s*['"]" --include="*.py" | grep -v "os.getenv\|os.environ\|\.env"
echo "=== potential SQL injection ==="
grep -rn "execute(f\"" --include="*.py"
grep -rn "execute(f'" --include="*.py"
```

### 4. TODO/FIXME/HACK Audit
```bash
echo "=== Outstanding TODOs ==="
grep -rn "TODO\|FIXME\|HACK\|XXX\|PLACEHOLDER" --include="*.py" --include="*.ts" --include="*.go"
```

### 5. Duplicate Systems Check
```bash
echo "=== Duplicate LLM routing ==="
grep -rln "def route\|def classify_task\|class.*Router" --include="*.py"
echo "=== Duplicate consensus ==="
grep -rln "consensus\|probability.*estimate" --include="*.py"
```

## After Scanning
- Fix any CRITICAL findings immediately (SQL injection, hardcoded secrets)
- Create GitHub issues for HIGH findings that need more thought
- Update CLAUDE.md with any new LEARNED rules
- Commit the cleanup as a separate commit: `fix: end-of-session techdebt cleanup`

