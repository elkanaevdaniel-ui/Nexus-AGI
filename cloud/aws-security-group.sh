#!/bin/bash
# ================================================================
# NEXUS AGI — AWS Security Group Helper
# Optional: Use this if you have AWS CLI configured to automate
# security group setup. Otherwise, do it in the AWS Console (GUI).
# Usage: bash aws-security-group.sh <security-group-id>
# ================================================================
set -euo pipefail

SG_ID="${1:-}"

if [ -z "$SG_ID" ]; then
    echo "Usage: bash aws-security-group.sh <security-group-id>"
    echo ""
    echo "Find your Security Group ID:"
    echo "  AWS Console → EC2 → Instances → Select instance → Security tab"
    echo "  It looks like: sg-0123456789abcdef"
    exit 1
fi

echo "Configuring Security Group: $SG_ID"

# Allow SSH (port 22)
echo "[1/3] Allowing SSH (port 22)..."
aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0 \
    2>/dev/null && echo "  ✓ SSH allowed" || echo "  - SSH rule already exists"

# Allow HTTP (port 80) — needed for Let's Encrypt
echo "[2/3] Allowing HTTP (port 80)..."
aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 80 \
    --cidr 0.0.0.0/0 \
    2>/dev/null && echo "  ✓ HTTP allowed" || echo "  - HTTP rule already exists"

# Allow HTTPS (port 443)
echo "[3/3] Allowing HTTPS (port 443)..."
aws ec2 authorize-security-group-ingress \
    --group-id "$SG_ID" \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    2>/dev/null && echo "  ✓ HTTPS allowed" || echo "  - HTTPS rule already exists"

echo ""
echo "Done! Security Group $SG_ID is configured."
echo "Ports open: 22 (SSH), 80 (HTTP), 443 (HTTPS)"
