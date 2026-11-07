#!/bin/bash
# Bring Tailscale up without taking over DNS (for Macs where a VPN owns DNS).
# Rolls back with `tailscale down` if DNS or HTTPS stops working.
# Usage: bash tailscale-safe-up.sh [peer-ip ...]
check() {
  dns=$(dscacheutil -q host -a name github.com 2>/dev/null | grep -c ip_address)
  web=$(curl -s -o /dev/null -m 10 -w '%{http_code}' https://api.anthropic.com/ 2>/dev/null)
  echo "dns_answers=$dns https_code=$web"
  [ "$dns" -gt 0 ] && [ "$web" != "000" ]
}
echo "before:"; check || echo "WARNING: network already broken before tailscale up"
tailscale up --accept-dns=false --timeout=20s 2>&1 | tail -3
sleep 5
echo "after up:"
if ! check; then
  sleep 10; echo "recheck:"
  check || { echo "ROLLBACK: tailscale down"; tailscale down; sleep 3; check; exit 1; }
fi
tailscale debug prefs 2>/dev/null | grep -E '"(CorpDNS|WantRunning)"'
for ip in "$@"; do
  echo "$ip -> $(route -n get "$ip" 2>/dev/null | awk '/interface/{print $2}')"
  tailscale ping -c 2 "$ip" 2>&1 | tail -1
done
