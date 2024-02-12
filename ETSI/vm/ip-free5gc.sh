ip link set eth1 up
ip addr add 192.168.56.1/24 dev eth1
ip route add 192.168.58.0/24 via 192.168.56.2