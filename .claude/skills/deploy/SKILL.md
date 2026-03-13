---
name: deploy
description: >
  Standard deploy workflow for Nexus-AGI to EC2. Use this skill whenever the user says
  "/deploy", "push to production", "deploy to EC2", "ship it", "go live", or any
  request to deploy code changes. Also trigger when the user says "restart services",
  "update the server", or mentions the EC2 instance. ALWAYS run verification after deploy.
---

# Nexus-AGI Deploy Workflow

## Pre-Deploy Checklist
1. Run /techdebt scan — fix any CRITICAL findings
2. Run /review on all changes — address any CRITICAL/HIGH feedback
3. Ensure all tests pass: cd trading && python -m pytest tests/ -x -q
4. Check git status is clean: git status

## Deploy Steps

### 1. Commit & Push
```bash
git add -A
git status  # Review what's being committed
git commit -m "descriptive message here"
git push origin main
```

### 2. Pull on EC2
```bash
ssh ubuntu@13.50.115.230 "cd ~/ai-projects/workdir && git pull origin main"
```
Or via Agent Zero: send the command through the web UI at http://13.50.115.230:50001

### 3. Install Dependencies (if requirements changed)
```bash
ssh ubuntu@13.50.115.230 "source ~/nexus-venv/bin/activate && pip install -r ~/ai-projects/workdir/linkedin-bot/requirements.txt -q"
```

### 4. Restart Affected Services
```bash
ssh ubuntu@13.50.115.230 "sudo systemctl restart nexus-bot"
ssh ubuntu@13.50.115.230 "sudo systemctl restart nexus-trading"
ssh ubuntu@13.50.115.230 "sudo systemctl restart nexus-llm-router"
ssh ubuntu@13.50.115.230 "sudo systemctl restart caddy"
```

### 5. Post-Deploy Verification (MANDATORY)
```bash
curl -s https://nexus-elkana.duckdns.org/health
ssh ubuntu@13.50.115.230 "systemctl status nexus-bot nexus-trading --no-pager | grep Active"
ssh ubuntu@13.50.115.230 "journalctl --since '2 minutes ago' --priority=err --no-pager"
```

## Rollback
If anything is broken after deploy:
```bash
ssh ubuntu@13.50.115.230 "cd ~/ai-projects/workdir && git revert HEAD && sudo systemctl restart nexus-bot nexus-trading"
```

