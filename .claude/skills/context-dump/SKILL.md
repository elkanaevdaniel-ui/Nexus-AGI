---
name: context-dump
description: >
  Sync all recent context from Telegram, GitHub, service logs, and cost data into one
  unified briefing. Use this skill at the START of every new session, when the user says
  "/context-dump", "what's happening", "catch me up", "status update", "briefing",
  or any request for a project status overview.
---

# Context Dump — Session Start Briefing

Run this at the start of every session to get full project context in one place.

## 1. Git Status
```bash
cd ~/ai-projects/workdir
git log --oneline -10
git status
git diff --stat HEAD~5
```

## 2. Service Health
```bash
echo "=== Service Health ==="
for svc in nexus-bot nexus-dashboard nexus-trading nexus-llm-router nexus-command; do
  status=$(systemctl is-active $svc 2>/dev/null || echo "unknown")
  echo "  $svc: $status"
done
echo "=== External Health ==="
curl -s -o /dev/null -w "HTTPS: %{http_code}\n" https://nexus-elkana.duckdns.org/health
```

## 3. Recent Errors
```bash
echo "=== Errors (last 2 hours) ==="
journalctl --since "2 hours ago" --priority=err --no-pager | tail -30
```

## 4. Cost Status
```bash
echo "=== Budget Status ==="
curl -s http://localhost:5200/api/budget/status 2>/dev/null || echo "Cost tracker not reachable"
```

## 5. GitHub Issues
```bash
gh issue list --repo elkanaevdaniel-ui/Nexus-AGI --limit 10 2>/dev/null || echo "gh CLI not available"
```

## 6. Trading Status
```bash
curl -s http://localhost:8000/api/portfolio 2>/dev/null || echo "Trading API not reachable"
```

## 7. CLAUDE.md Check
```bash
echo "=== Recent LEARNED rules ==="
grep "^LEARNED" CLAUDE.md | tail -5
```

## Output Format
Summarize everything into a concise briefing:
- What changed since last session
- What's healthy / what's broken
- Any budget concerns
- Suggested priorities for this session

