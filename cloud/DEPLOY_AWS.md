# NEXUS AGI — AWS Deployment Guide (Step-by-Step)

## Plan: AWS Free Tier (6 months)
- **$200 free credits** for 6 months
- After 6 months: upgrade to paid or account closes (no surprise bills)
- Recommended instance: **t3.small** (2 vCPU, 2GB RAM) — ~$15/month after free tier

---

## Prerequisites
- AWS account (Free plan — 6 months, $200 credits)
- Your API keys ready: Telegram token, chat ID, OpenRouter key, Google API key
- SSH key pair (we'll create one during setup)

---

## STEP 1: Sign Up for AWS

1. Go to **https://aws.amazon.com** → Click **"Create an AWS Account"**
2. Choose **"Free (6 months)"** plan
3. Enter email, password, account name
4. Add payment method (credit/debit card — won't be charged on Free plan)
5. Complete identity verification (phone number)
6. Wait for account activation (can take a few minutes)

---

## STEP 2: Launch an EC2 Instance

1. Go to **AWS Console** → Search **"EC2"** → Click **EC2 Dashboard**
2. Click **"Launch Instance"** (orange button)
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `nexus-agi` |
| **OS Image** | Ubuntu Server 24.04 LTS (Free tier eligible) |
| **Architecture** | 64-bit (x86) |
| **Instance type** | `t3.small` (2 vCPU, 2GB RAM) — **best value for $200 credit** |
| **Key pair** | Click "Create new key pair" → Name: `nexus-key` → Type: RSA → Format: .pem → **Download it!** |

4. **Network Settings** — Click "Edit":
   - Allow SSH traffic from: **My IP** (more secure) or Anywhere
   - Check: **Allow HTTP traffic from the internet**
   - Check: **Allow HTTPS traffic from the internet**

5. **Storage**: Change to **30 GB** gp3 (free tier allows up to 30GB)

6. Click **"Launch Instance"**
7. Wait for status: **Running** (1-2 minutes)
8. Click on instance → Copy the **Public IPv4 address**

### Cost Breakdown (with $200 credit):
| Resource | Monthly Cost |
|----------|-------------|
| t3.small (2 vCPU, 2GB) | ~$15.18 |
| 30GB gp3 storage | ~$2.40 |
| Elastic IP (optional) | Free while attached |
| Data transfer (first 100GB) | Free |
| **Total** | **~$18/month** |
| **With $200 credit** | **~11 months free!** |

> **Tip**: t3.small at $15/mo means your $200 credit lasts ~11 months (longer than the 6-month free period). You're covered.

---

## STEP 3: Allocate Elastic IP (Static IP)

EC2 instances get a new IP every time they stop/start. Fix this:

1. Go to **EC2** → **Elastic IPs** (left sidebar, under Network & Security)
2. Click **"Allocate Elastic IP address"** → Click **"Allocate"**
3. Select the new IP → **Actions** → **"Associate Elastic IP address"**
4. Choose your `nexus-agi` instance → Click **"Associate"**

Now your IP stays the same even if you stop/restart the instance.

---

## STEP 4: Set Up DuckDNS Domain (Free)

1. Go to **https://www.duckdns.org** → Sign in with Google/GitHub
2. Create a subdomain, e.g.: `nexus-elkana`
   - You get: **nexus-elkana.duckdns.org**
3. Set the IP to your **Elastic IP** from Step 3
4. Click **Update**
5. Save your **DuckDNS token** (shown at top of page) — you'll need it later

---

## STEP 5: Connect via SSH

**Windows (PowerShell):**
```powershell
ssh -i Downloads\nexus-key.pem ubuntu@YOUR_ELASTIC_IP
```

**Mac/Linux:**
```bash
chmod 600 ~/Downloads/nexus-key.pem
ssh -i ~/Downloads/nexus-key.pem ubuntu@YOUR_ELASTIC_IP
```

Type `yes` when asked about the fingerprint.

> **Tip**: Replace `YOUR_ELASTIC_IP` with your actual Elastic IP from Step 3.

---

## STEP 6: Clone the Repository

```bash
cd ~
git clone https://github.com/elkanaevdaniel-ui/ai-projects.git
cd ai-projects/workdir
```

---

## STEP 7: Create Your .env File

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

## STEP 8: Run the AWS Setup Script

```bash
cd ~/ai-projects/workdir
sudo bash cloud/setup-aws.sh nexus-elkana.duckdns.org
```

Replace `nexus-elkana.duckdns.org` with your actual DuckDNS domain.

This automatically installs:
- Python 3 + virtual environment with all dependencies
- Redis (message broker & cache)
- Caddy (HTTPS reverse proxy with auto-SSL)
- Docker + Docker Compose
- UFW firewall (ports 22, 80, 443)
- All systemd services (auto-start on boot, auto-restart on crash)
- Daily backup timer
- 2GB swap file (important for t3.small)

Wait 5-10 minutes for completion.

---

## STEP 9: Verify Everything Works

Check all services are running:
```bash
sudo systemctl status nexus-bot
sudo systemctl status nexus-dashboard
sudo systemctl status nexus-command
sudo systemctl status caddy
sudo systemctl status redis-server
```

All should show **active (running)**.

Test locally:
```bash
curl -s http://localhost:7860 | head -5   # LinkedIn Dashboard
curl -s http://localhost:7862 | head -5   # Command Center
```

---

## STEP 10: Access Your Dashboard

Open in browser: **https://nexus-elkana.duckdns.org**

Login with your DASHBOARD_USER / DASHBOARD_PASSWORD from the .env file.

---

## STEP 11: Test Telegram Commands

Open your Telegram bot and try:
- `/status` — System status (services, memory, disk)
- `/stats` — Bot statistics (posts, costs)
- `/budget` — API cost tracking
- `/ai What is cybersecurity?` — Ask AI (uses smart routing)
- `/search ransomware` — Search and generate post
- `/post` — Generate a LinkedIn post

---

## STEP 12: Set Up DuckDNS Auto-Update

Keep your domain IP in sync (in case Elastic IP changes):

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

# Add to cron (runs every 5 minutes)
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
```

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

## Update Code from GitHub

```bash
cd ~/ai-projects
git pull origin main
sudo systemctl restart nexus-bot nexus-dashboard nexus-command
```

---

## AWS-Specific Tips

### Monitor Your Credits
1. Go to **AWS Console** → **Billing** → **Credits**
2. Check remaining balance regularly
3. Set up a **Billing Alert**:
   - Go to **Billing** → **Budgets** → **Create Budget**
   - Set monthly budget to **$20**
   - Add email alert at **80%** ($16)

### Stop Instance to Save Credits
When not using the server (e.g., overnight):
```bash
# From AWS Console: EC2 → Instances → Select → Instance State → Stop
# This pauses billing for compute (storage still costs ~$2.40/mo)
```

### Security Best Practices
- Never open all ports (0.0.0.0/0) — the setup script only opens 22, 80, 443
- Use "My IP" for SSH access in Security Group when possible
- Regularly update: `sudo apt-get update && sudo apt-get upgrade -y`

---

## Cost Summary

| Item | Cost |
|------|------|
| AWS Free Plan | $200 credits for 6 months |
| t3.small (2 vCPU, 2GB) | ~$15/month |
| 30GB gp3 storage | ~$2.40/month |
| DuckDNS domain | FREE |
| Caddy auto-HTTPS | FREE |
| **Total** | **~$18/month (covered by credits for ~11 months)** |
| **After credits expire** | **~$18/month** or downgrade to t3.micro (~$8/month) |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Can't SSH | Check Security Group has port 22 open for your IP |
| Site not loading | Check Security Group ports 80/443 + `sudo ufw status` |
| Service won't start | `sudo journalctl -u nexus-bot --no-pager -n 50` |
| HTTPS not working | `sudo journalctl -u caddy --no-pager -n 20` |
| Out of memory | `free -h` — swap should help, restart services if needed |
| Instance unreachable | Check if instance is running in EC2 console |
| DuckDNS not resolving | Wait 5 min, verify IP on duckdns.org matches Elastic IP |
| Billing surprise | Check **Billing → Credits** in AWS Console |
