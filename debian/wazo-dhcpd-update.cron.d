SHELL=/bin/bash
0 0 * * 0   root       sleep $[ ( $RANDOM * 3 ) ]s; /usr/sbin/dhcpd-update -dr; systemctl restart isc-dhcp-server.service
