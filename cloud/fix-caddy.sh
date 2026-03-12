#!/bin/bash
# Quick fix: deploy correct Caddyfile with nexus-elkana.duckdns.org
set -e

DOMAIN="nexus-elkana.duckdns.org"
echo "Fixing Caddy for $DOMAIN..."

# Write the correct Caddyfile
cat > /etc/caddy/Caddyfile << CADDYEOF
$DOMAIN {
    handle /leadgen/api/* {
        uri strip_prefix /leadgen
        reverse_proxy localhost:8082
    }
    handle /leadgen/* {
        uri strip_prefix /leadgen
        reverse_proxy localhost:3001
    }
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        -Server
    }
    log {
        output file /var/log/caddy/access.log {
            roll_size 10mb
            roll_keep 5
        }
    }
    handle {
        respond "NEXUS AGI" 200
    }
}
CADDYEOF

# Clear stale certs/locks and restart
systemctl stop caddy
rm -rf /var/lib/caddy/.local/share/caddy/locks
rm -rf /var/lib/caddy/.local/share/caddy/certificates
mkdir -p /var/log/caddy
systemctl start caddy

echo ""
echo "Caddyfile updated. Waiting for TLS cert..."
sleep 5
systemctl status caddy --no-pager | head -20
echo ""
echo "Test: https://$DOMAIN/leadgen/"
