SHELL=/bin/bash
0 0 * * 0   root       sleep $[ ( $RANDOM * 3 ) ]s; /usr/sbin/dhcpd-update -dr; systemctl try-restart isc-dhcp-server.service
