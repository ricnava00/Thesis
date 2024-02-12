ip link set eth1 up
ip addr add 192.168.58.1/24 dev eth1
ip route add 192.168.56.0/24 via 192.168.58.2