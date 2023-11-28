ip link set eth1 up
ip link set eth2 up
ip addr add 192.168.56.2/24 dev eth1
ip addr add 192.168.58.2/24 dev eth2
echo 1 > /proc/sys/net/ipv4/ip_forward