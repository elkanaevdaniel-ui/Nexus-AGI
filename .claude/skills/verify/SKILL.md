---
name: verify
description: >
  Run verification loops after any code change, deploy, or fix. This is the most
  important skill — it 2-3x's the quality of every output. Use this skill after ANY
  code modification, after ANY deploy to EC2, after ANY bug fix, or when the user says
  "/verify", "check if it works", "test this", "prove it works", or "verify". Also
  trigger AUTOMATICALLY after any file write or edit — never skip verification.
---

# Verification Loop

This skill implements the single most important pattern from the Claude Code best practices:
**Always give Claude a way to verify its own work.** This reportedly 2-3x's output quality.

## After Every Code Change

1. **Syntax check** — Parse the modified file(s)
```bash
python3 -c "import ast; ast.parse(open('FILE').read()); print('OK')"
```

2. **Import check** — Verify all imports resolve
```bash
python3 -c "import FILE_MODULE" 2>&1 | head -5
```

3. **Grep for common mistakes**
```bash
git diff --cached | grep -E "(TODO|FIXME|PLACEHOLDER|import requests[^_]|execute\(f['\"'])"
```

4. **Run existing tests** (if available)
```bash
cd trading && python -m pytest tests/ -x -q 2>&1 | tail -20
```

## After Every Deploy

1. **Health check** — Hit every service endpoint
```bash
for port in 50001 5100 5200 5300 7860 8000; do
  status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/health 2>/dev/null || echo "DOWN")
  echo "  :$port -> $status"
done
```

2. **External health check** — Hit the public URL
```bash
curl -s https://nexus-elkana.duckdns.org/health
```

3. **Service status** — Check systemd
```bash
for svc in nexus-bot nexus-dashboard nexus-trading nexus-llm-router; do
  status=$(systemctl is-active $svc 2>/dev/null || echo "not found")
  echo "  $svc -> $status"
done
```

4. **Recent errors** — Scan logs for crashes
```bash
journalctl --since "5 minutes ago" --priority=err --no-pager | tail -20
```

## After Every Bug Fix

1. **Reproduce the original bug** — Verify it existed
2. **Apply the fix**
3. **Verify the bug is gone** — Same reproduction steps should now pass
4. **Check for regressions** — Run the full test suite, not just the affected test
5. **Update CLAUDE.md** — Add a LEARNED rule preventing this class of bug

## Verification Prompts to Use

- "Prove to me this works by showing the before/after behavior"
- "Diff the behavior between main and this fix"
- "What edge cases could break this?"
- "Grill me on these changes — what did I miss?"

