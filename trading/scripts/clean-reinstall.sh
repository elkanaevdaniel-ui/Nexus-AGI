#!/bin/bash
########################################################################
# Clean Reinstall — Wipe everything and start fresh
#
# Usage:  bash clean-reinstall.sh
#
# REQUIREMENTS before running:
#   - EC2 instance type: t3.medium (4GB RAM) or larger
#   - EBS volume: 50GB or larger
#
# To resize in AWS Console:
#   1. EBS: EC2 → Volumes → select volume → Modify → Size: 50
#   2. Instance: Stop instance → Actions → Instance Settings →
#      Change Instance Type → t3.medium → Start
#   3. After boot, run: sudo growpart /dev/xvda 1 && sudo resize2fs /dev/xvda1
#      (or /dev/nvme0n1p1 on nitro instances)
########################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${RED}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   CLEAN REINSTALL — This will DELETE everything!    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Pre-flight checks
echo -e "${CYAN}[PRE-CHECK] Verifying system resources...${NC}"
echo ""

# Check disk
DISK_AVAIL=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
DISK_TOTAL=$(df -BG / | awk 'NR==2 {print $2}' | tr -d 'G')
echo -e "  Disk: ${DISK_AVAIL}GB free / ${DISK_TOTAL}GB total"

# Check RAM
RAM_TOTAL=$(free -m | awk '/Mem:/ {print $2}')
echo -e "  RAM:  ${RAM_TOTAL}MB total"

# Warn if undersized
FAIL=0
if [[ "$DISK_TOTAL" -lt 40 ]]; then
    echo -e "  ${RED}✗ Disk too small! Need 50GB, have ${DISK_TOTAL}GB${NC}"
    echo -e "  ${YELLOW}  → Resize EBS volume to 50GB in AWS Console${NC}"
    echo -e "  ${YELLOW}  → Then run: sudo growpart /dev/xvda 1 && sudo resize2fs /dev/xvda1${NC}"
    echo -e "  ${YELLOW}  → (use /dev/nvme0n1p1 if on nitro instance)${NC}"
    FAIL=1
fi

if [[ "$RAM_TOTAL" -lt 3500 ]]; then
    echo -e "  ${RED}✗ RAM too low! Need 4GB+, have ${RAM_TOTAL}MB${NC}"
    echo -e "  ${YELLOW}  → Change instance type to t3.medium (4GB) in AWS Console${NC}"
    FAIL=1
fi

if [[ "$FAIL" -eq 1 ]]; then
    echo ""
    echo -e "${RED}Fix the above issues first, then re-run this script.${NC}"
    exit 1
fi

echo -e "  ${GREEN}✓ System resources OK${NC}"
echo ""

read -p "This will DELETE agent-zero, polymarket-agent, all venvs, and caches. Continue? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
fi

########################################################################
# STEP 1: Stop all running services
########################################################################
echo -e "${CYAN}[1/4] Stopping services...${NC}"

# Stop Redis
sudo systemctl stop redis-server 2>/dev/null || true

# Kill any running Python processes from our apps
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "python.*run.py" 2>/dev/null || true

echo -e "${GREEN}[OK] Services stopped${NC}"

########################################################################
# STEP 2: Delete everything
########################################################################
echo -e "${CYAN}[2/4] Removing old installations...${NC}"

# Remove project directories
rm -rf ~/agent-zero
rm -rf ~/polymarket-agent

# Remove caches
rm -rf ~/.cache/pip
rm -rf ~/.cache/ms-playwright
rm -rf ~/.npm/_cacache
rm -rf /tmp/pip-*

# Remove launcher scripts
rm -f ~/start-*.sh

# Clean apt cache
sudo apt clean 2>/dev/null || true

echo -e "${GREEN}[OK] Everything cleaned${NC}"

########################################################################
# STEP 3: Expand filesystem (if EBS was resized but FS wasn't)
########################################################################
echo -e "${CYAN}[3/4] Expanding filesystem if needed...${NC}"

# Try both device naming conventions
if command -v growpart &>/dev/null; then
    sudo growpart /dev/xvda 1 2>/dev/null || sudo growpart /dev/nvme0n1 1 2>/dev/null || true
    sudo resize2fs /dev/xvda1 2>/dev/null || sudo resize2fs /dev/nvme0n1p1 2>/dev/null || true
fi

# Show new disk space
echo -e "  Disk after cleanup:"
df -h / | awk 'NR==2 {printf "  %s used / %s total / %s free (%s)\n", $3, $2, $4, $5}'

echo -e "${GREEN}[OK] Filesystem ready${NC}"

########################################################################
# STEP 4: Ensure swap exists
########################################################################
echo -e "${CYAN}[4/4] Setting up swap...${NC}"

if ! swapon --show | grep -q '/swapfile'; then
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    echo -e "${GREEN}[OK] 4GB swap created${NC}"
else
    echo -e "${GREEN}[OK] Swap already exists${NC}"
fi

########################################################################
# DONE — Ready for fresh install
########################################################################
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         CLEAN COMPLETE — Ready for fresh install    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
df -h / | awk 'NR==2 {printf "  Disk: %s free / %s total\n", $4, $2}'
free -h | awk '/Mem:/ {printf "  RAM:  %s free / %s total\n", $4, $2}'
swapon --show --noheadings | awk '{printf "  Swap: %s\n", $3}'
echo ""
echo -e "${YELLOW}Now run the full setup:${NC}"
echo -e "  git clone https://github.com/elkanaevdaniel-ui/polymarket-agent.git"
echo -e "  cd polymarket-agent"
echo -e "  bash scripts/full-setup.sh"
echo ""
