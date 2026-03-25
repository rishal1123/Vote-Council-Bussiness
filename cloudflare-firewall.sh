#!/bin/bash
# Allow only Cloudflare IPs to access port 80
# Run this script on the Linode server as root

# Flush existing rules for port 80
iptables -D INPUT -p tcp --dport 80 -j DROP 2>/dev/null

# Cloudflare IPv4 ranges (https://www.cloudflare.com/ips-v4/)
CF_IPS=(
    173.245.48.0/20
    103.21.244.0/22
    103.22.200.0/22
    103.31.4.0/22
    141.101.64.0/18
    108.162.192.0/18
    190.93.240.0/20
    188.114.96.0/20
    197.234.240.0/22
    198.41.128.0/17
    162.158.0.0/15
    104.16.0.0/13
    104.24.0.0/14
    172.64.0.0/13
    131.0.72.0/22
)

# Allow each Cloudflare IP range
for ip in "${CF_IPS[@]}"; do
    iptables -I INPUT -p tcp --dport 80 -s "$ip" -j ACCEPT
    echo "Allowed: $ip"
done

# Allow localhost
iptables -I INPUT -p tcp --dport 80 -s 127.0.0.1 -j ACCEPT

# Drop all other traffic to port 80
iptables -A INPUT -p tcp --dport 80 -j DROP

echo ""
echo "Done. Port 80 now only accepts Cloudflare traffic."
echo "To persist across reboots, run: apt install iptables-persistent && netfilter-persistent save"
