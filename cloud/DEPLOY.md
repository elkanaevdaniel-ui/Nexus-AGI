# NEXUS AGI — Cloud Deployment Guide (No Docker)

## Prerequisites
- Oracle Cloud account (free tier, A1.Flex ARM instance)
- Your API keys ready: Telegram token, chat ID, OpenRouter key, Google API key
- SSH key pair (generated during VM creation)

---

## Step 1: Create Oracle Cloud VM

1. Go to **Oracle Cloud Console** → **Compute** → **Instances** → **Create Instance**
2. Settings:
   - **Name**: `nexus-agi`
   - **Image**: Ubuntu 22.04 (or 24.04)
   - **Shape**: VM.Standard.A1.Flex — **2 OCPU / 12GB RAM** (reduce if out of capacity)
   - **Networking**: Create new VCN + public subnet
   - **SSH Keys**: Generate key pair → **save both keys** to your computer
   - Check "Create instance without specifying a fault domain" if out of capacity
3. Click **Create** and wait for status **RUNNING**
4. Copy the **Public IP Address** from the instance details page

---

## Step 2: Open Firewall Ports (Oracle Cloud Console)

1. Go to **Networking** → **Virtual Cloud Networks** → click your VCN
2. Click your **Public Subnet** → click the **Security List**
3. Click **Add Ingress Rules** and add:

| Source CIDR | Protocol | Port | Description |
|-------------|----------|------|-------------|
| 0.0.0.0/0   | TCP      | 80   | HTTP        |
| 0.0.0.0/0   | TCP      | 443  | HTTPS       |

---

## Step 3: Connect via SSH

**Windows (PowerShell):**
```powershell
ssh -i Downloads\ssh-key.key ubuntu@YOUR_PUBLIC_IP
```

**Mac/Linux:**
```bash
chmod 600 ~/Downloads/ssh-key.key
ssh -i ~/Downloads/ssh-key.key ubuntu@YOUR_PUBLIC_IP
```

Type `yes` if asked about fingerprint.

---

## Step 4: Clone the Repository

```bash
git clone https://github.com/elkanaevdaniel-ui/ai-projects.git
cd ai-projects/workdir
```

---

## Step 5: Create Your .env File

```bash
cp linkedin-bot/.env.example linkedin-bot/.env
nano linkedin-bot/.env
```

Fill in your real credentials:
```
TELEGRAM_TOKEN=your_real_telegram_token
TELEGRAM_CHAT_ID=your_real_chat_id
OPENROUTER_API_KEY=your_real_openrouter_key
GOOGLE_API_KEY=your_real_google_key
DASHBOARD_USER=admin
DASHBOARD_PASSWORD=your_strong_password
DAILY_BUDGET=1.00
MONTHLY_BUDGET=20.00
```

Save: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## Step 6: Set Up DuckDNS Domain

1. Go to https://www.duckdns.org → Sign in with Google
2. Add subdomain: `nexus-agi`
3. Set the IP to your VM's **Public IP Address**
4. Click **Update IP**

Your domain: **nexus-agi.duckdns.org**

---

## Step 7: Run the Setup Script

```bash
cd ~/ai-projects/workdir
sudo bash cloud/setup.sh nexus-agi.duckdns.org
```

This installs everything automatically:
- Python 3 + virtual environment
- Caddy web server (HTTPS)
- Firewall rules
- All systemd services (auto-start/restart)
- Daily backup timer

Wait 5-10 minutes for completion.

---

## Step 8: Verify Everything Works

Check all services are running:
```bash
sudo systemctl status nexus-bot
sudo systemctl status nexus-dashboard
sudo systemctl status nexus-command
sudo systemctl status caddy
```

All should show **active (running)**.

---

## Step 9: Access Your Dashboard

Open in browser: **https://nexus-agi.duckdns.org**

Login with your DASHBOARD_USER / DASHBOARD_PASSWORD.

---

## Step 10: Test Telegram Commands

Open your Telegram bot and try:
- `/status` — System status (services, memory, disk)
- `/stats` — Bot statistics (posts, costs)
- `/budget` — API cost tracking
- `/ai What is cybersecurity?` — Ask AI (uses smart routing)
- `/search ransomware` — Search and generate post
- `/logs` — View recent logs
- `/run uptime` — Run shell command
- `/view linkedin-bot/config.py` — View file
- `/post` — Generate a LinkedIn post

---

## Managing Services

```bash
# View logs
sudo journalctl -u nexus-bot -f          # Follow bot logs
sudo journalctl -u nexus-dashboard -f     # Follow dashboard logs

# Restart services
sudo systemctl restart nexus-bot
sudo systemctl restart nexus-dashboard
sudo systemctl restart nexus-command

# Stop/Start
sudo systemctl stop nexus-bot
sudo systemctl start nexus-bot

# Check backup timer
sudo systemctl status nexus-backup.timer
sudo systemctl list-timers nexus-backup*
```

---

## Telegram Command Reference

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + help |
| `/post` | Generate a new LinkedIn post |
| `/last` | Show last generated post |
| `/search <keyword>` | Search news & generate post |
| `/status` | System status (services, memory, disk, spend) |
| `/stats` | Post statistics |
| `/logs [lines] [file]` | View recent logs |
| `/budget` | Budget report (costs, limits) |
| `/budget set daily 2.00` | Set daily budget limit |
| `/budget set monthly 30.00` | Set monthly budget limit |
| `/ai <question>` | Ask AI (smart model routing) |
| `/ai --model premium <q>` | Force specific model tier |
| `/run <command>` | Execute shell command (with safety) |
| `/view <file>` | View file contents |
| `/edit <file>` | Edit file contents |
| `/schedule` | View posting schedule |
| `/topic` | Change weekly topic |
| `/style` | Change image style |

---

## Smart AI Model Routing

The system automatically picks the cheapest capable model:

| Complexity | Model Used | Cost |
|-----------|-----------|------|
| Simple (translate, summarize) | Gemini Flash (FREE) | $0.00 |
| Moderate (write, explain) | Claude 3 Haiku | ~$0.001 |
| Complex (analyze, code) | GPT-4o Mini | ~$0.003 |
| Expert (architect, debug) | Claude Opus 4.6 | ~$0.05+ |

Override with: `/ai --model premium <question>`

---

## Troubleshooting

**Service won't start:**
```bash
sudo journalctl -u nexus-bot --no-pager -n 50
```

**HTTPS not working:**
```bash
sudo systemctl status caddy
sudo journalctl -u caddy --no-pager -n 20
```

**Out of memory:**
```bash
free -h
# If low, restart services:
sudo systemctl restart nexus-bot nexus-dashboard nexus-command
```

**Update code from GitHub:**
```bash
cd ~/ai-projects
git pull origin main
sudo systemctl restart nexus-bot nexus-dashboard nexus-command
```
