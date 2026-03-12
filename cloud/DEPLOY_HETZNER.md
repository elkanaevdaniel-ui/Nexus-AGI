# NEXUS AGI — Hetzner Cloud Deployment Guide

## Overview
Deploy your entire NEXUS AGI platform on a **Hetzner CX22** VPS for **$4.35/month**.

**What you get:**
- 2 vCPU, 4GB RAM, 40GB SSD, 20TB traffic
- All NEXUS services running 24/7
- HTTPS with free SSL certificate
- Free domain via DuckDNS
- Daily automated backups

**Total cost: ~$4.35/month** (server only — API keys separate)

---

## STEP 1: Create a Hetzner Account

1. Go to **https://www.hetzner.com/cloud**
2. Click **"Sign Up"** → create account with your email
3. Verify your email
4. Add a **payment method** (credit card or PayPal)
   - You only pay for what you use (~$4.35/month for CX22)

---

## STEP 2: Create Your Server

1. Go to **Hetzner Cloud Console** → https://console.hetzner.cloud
2. Click **"+ Create Server"**
3. Configure:

| Setting | Value |
|---------|-------|
| **Location** | Falkenstein (cheapest) or Nuremberg or Helsinki |
| **Image** | Ubuntu 22.04 |
| **Type** | Shared vCPU → **CX22** (2 vCPU, 4GB RAM, 40GB) |
| **Networking** | Public IPv4 ✅ (checked by default) |
| **SSH Key** | Click "Add SSH Key" (see below) |
| **Name** | `nexus-agi` |

4. **Generate SSH Key** (if you don't have one):

   **Windows (PowerShell):**
   ```powershell
   ssh-keygen -t ed25519 -f $HOME\.ssh\nexus-key
   cat $HOME\.ssh\nexus-key.pub
   ```

   **Mac/Linux:**
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/nexus-key
   cat ~/.ssh/nexus-key.pub
   ```

   Copy the output (starts with `ssh-ed25519 ...`) and paste it into Hetzner's "Add SSH Key" field.

5. Click **"Create & Buy Now"** (~$4.35/month)
6. Wait 30 seconds → copy the **IP Address** shown

---

## STEP 3: Set Up Firewall (Hetzner Console)

1. In Hetzner Console → go to **Firewalls** (left menu)
2. Click **"Create Firewall"**
3. Name: `nexus-firewall`
4. Add these **Inbound Rules**:

| Protocol | Port | Source | Description |
|----------|------|--------|-------------|
| TCP | 22 | Any | SSH |
| TCP | 80 | Any | HTTP |
| TCP | 443 | Any | HTTPS |

5. Click **"Create Firewall"**
6. Go to **Servers** tab in the firewall → **Apply to** → select `nexus-agi`

---

## STEP 4: Get Free Domain (DuckDNS)

1. Go to **https://www.duckdns.org**
2. Sign in with Google or GitHub
3. Create a subdomain, for example: `nexus-elkana`
   - You get: **nexus-elkana.duckdns.org**
4. Set the **IP** to your Hetzner server's IP address
5. Click **"Update IP"**
6. **Save your DuckDNS token** (shown at the top of the page) — you'll need it later

---

## STEP 5: Connect to Your Server via SSH

**Windows (PowerShell):**
```powershell
ssh -i $HOME\.ssh\nexus-key root@YOUR_SERVER_IP
```

**Mac/Linux:**
```bash
chmod 600 ~/.ssh/nexus-key
ssh -i ~/.ssh/nexus-key root@YOUR_SERVER_IP
```

Type `yes` when asked about the fingerprint.

> **Note:** Hetzner uses `root` by default (not `ubuntu` like Oracle).

---

## STEP 6: Initial Server Setup

Run this on the server after connecting via SSH:

```bash
# Create a non-root user (safer than running as root)
adduser nexus --disabled-password --gecos ""
usermod -aG sudo nexus
echo "nexus ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/nexus

# Copy SSH key to new user
mkdir -p /home/nexus/.ssh
cp /root/.ssh/authorized_keys /home/nexus/.ssh/
chown -R nexus:nexus /home/nexus/.ssh

# Switch to the new user
su - nexus
```

From now on, connect as: `ssh -i ~/.ssh/nexus-key nexus@YOUR_SERVER_IP`

---

## STEP 7: Install Dependencies

```bash
# Update system
sudo apt-get update -y && sudo apt-get upgrade -y

# Install Python, Redis, and tools
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    git curl wget sqlite3 redis-server \
    ufw

# Install Caddy (web server with auto-HTTPS)
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update -y && sudo apt-get install -y caddy

# Enable Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

---

## STEP 8: Configure Firewall (UFW)

```bash
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable
sudo ufw status
```

---

## STEP 9: Clone the Repository

```bash
cd ~
git clone https://github.com/elkanaevdaniel-ui/ai-projects.git
cd ai-projects/workdir
```

---

## STEP 10: Create Your .env File

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
DASHBOARD_PASSWORD=your_strong_password_here
DAILY_BUDGET=1.00
MONTHLY_BUDGET=20.00
```

Save: `Ctrl+O` → `Enter` → `Ctrl+X`

---

## STEP 11: Run the Setup Script

```bash
cd ~/ai-projects/workdir
sudo bash cloud/setup.sh nexus-elkana.duckdns.org
```

This automatically installs:
- Python virtual environment with all dependencies
- Caddy web server (auto-HTTPS with Let's Encrypt)
- All systemd services (auto-start on boot, auto-restart on crash)
- Daily backup timer

Wait 5-10 minutes for completion.

---

## STEP 12: Verify Everything Works

```bash
# Check all services are running
sudo systemctl status nexus-bot
sudo systemctl status nexus-dashboard
sudo systemctl status nexus-command
sudo systemctl status caddy
sudo systemctl status redis-server

# All should show: active (running)
```

---

## STEP 13: Access Your Dashboard

Open in your browser: **https://nexus-elkana.duckdns.org**

Login with your DASHBOARD_USER / DASHBOARD_PASSWORD.

---

## STEP 14: Test Telegram Commands

Open your Telegram bot and try:
- `/start` — Welcome message
- `/status` — System status (services, memory, disk)
- `/stats` — Bot statistics (posts, costs)
- `/budget` — API cost tracking
- `/ai What is cybersecurity?` — Ask AI (uses smart routing)
- `/post` — Generate a LinkedIn post
- `/logs` — View recent logs

---

## STEP 15: Set Up DuckDNS Auto-Update

Keeps your domain pointing to the correct IP:

```bash
mkdir -p ~/duckdns
cat > ~/duckdns/duck.sh << 'EOF'
#!/bin/bash
echo url="https://www.duckdns.org/update?domains=YOUR_SUBDOMAIN&token=YOUR_TOKEN&ip=" | curl -k -o ~/duckdns/duck.log -K -
EOF
chmod 700 ~/duckdns/duck.sh

# Edit with your real values
nano ~/duckdns/duck.sh
# Replace YOUR_SUBDOMAIN with your subdomain (e.g., nexus-elkana)
# Replace YOUR_TOKEN with your DuckDNS token

# Run every 5 minutes automatically
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
```

---

## Managing Your Server

### View Logs
```bash
sudo journalctl -u nexus-bot -f          # Telegram bot logs
sudo journalctl -u nexus-dashboard -f     # Dashboard logs
sudo journalctl -u nexus-command -f       # Command center logs
sudo journalctl -u caddy -f              # Web server logs
```

### Restart Services
```bash
sudo systemctl restart nexus-bot
sudo systemctl restart nexus-dashboard
sudo systemctl restart nexus-command
```

### Update Code from GitHub
```bash
cd ~/ai-projects
git pull origin main
sudo systemctl restart nexus-bot nexus-dashboard nexus-command
```

### Check Memory & Disk
```bash
free -h        # RAM usage
df -h          # Disk usage
htop           # Live process monitor (install with: sudo apt install htop)
```

### Backup Timer
```bash
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

---

## Monthly Costs

| Item | Cost |
|------|------|
| Hetzner CX22 (2 vCPU, 4GB RAM) | $4.35/month |
| DuckDNS domain | FREE |
| Caddy auto-HTTPS (Let's Encrypt) | FREE |
| Redis | FREE (self-hosted) |
| **Total infrastructure** | **$4.35/month** |
| API costs (OpenRouter, Google, etc.) | ~$1-5/month (depends on usage) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Can't SSH | Check Hetzner firewall has port 22 open |
| Site not loading | Check UFW: `sudo ufw status`, ensure 80/443 open |
| Service won't start | Check logs: `sudo journalctl -u nexus-bot --no-pager -n 50` |
| HTTPS not working | Check Caddy: `sudo journalctl -u caddy --no-pager -n 20` |
| DuckDNS not resolving | Wait 5 min, verify IP on duckdns.org matches server IP |
| Out of memory | Check: `free -h`, restart services if needed |
| Redis not connecting | Check: `sudo systemctl status redis-server` |
| Permission errors | Ensure files owned by nexus: `sudo chown -R nexus:nexus ~/ai-projects` |

---

## Security Hardening (Optional)

```bash
# Disable root SSH login
sudo sed -i 's/PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Install fail2ban (blocks brute-force SSH attempts)
sudo apt-get install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Enable automatic security updates
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```
