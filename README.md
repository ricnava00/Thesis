# TLMSP middlebox deployment
## Installation
1. Install [VirtualBox](https://www.virtualbox.org/wiki/Downloads)
2. Install [Vagrant](https://developer.hashicorp.com/vagrant/downloads)
3. `cd vm`
4. (Optional) If `tlmsp-compiled-20.04.tar` is missing, or you want to recreate it, run `vagrant up etsi-20.04 --provision`
5. `vagrant up`, checking that all provisioning scripts run successfully
## Test deployment
Open 3-4 terminal windows, and for each of _free5gc_, _etsi_, _openfaas_ run `vagrant ssh {name}`. You can either open two terminals for free5gc or split a single one with `tmux` or similar solutions.  
It could be preferable to have the terminals in the aforementioned order, as to resemble the configuration of the physical network.

#### Network layout
- Client (free5gc):
  - IP: `192.168.56.1`
  - Interface: `eth1`
- Middblebox (etsi, client side):
  - IP: `192.168.56.2`
  - Interface: `eth1`
- Middblebox (etsi, server side):
  - IP: `192.168.58.2`
  - Interface: `eth2`
- Server (openfaas):
  - IP: `192.168.58.1`
  - Interface: `eth1`

For more information check the `ip-*.sh` scripts

Check that the machines can ping each other by running `ping {IP} -I {interface}` and `ping {IP}` (the correct routes are preconfigured so both commands should work).

To test middlebox functionality, run the following commands
### Server
```
sudo kubectl port-forward --address 0.0.0.0 -n openfaas svc/gateway 8080:8080 >/dev/null 2>/dev/null &
httpd -X
```
The terminal should then stop asking for input  
If after running httpd you can run more commands, then it failed to start. Check the logs in `~/tlmsp/install/var/logs/`

### Middlebox
```
tlmsp-mb -c ~/shared/TLMSP/tlmsp-tools/examples/apache.1mbox.ucl -t mbox1 -P
```
The terminal should then stop asking for input

### Client
#### Terminal 1
```
cd free5gc-compose
docker compose up -d
```
On the host machine, navigate to http://127.0.0.1:5000, login with user `admin` and password `free5gc`  
Navigate to the **Subscribers** tab, click on **New Subscriber**  
The information should be correct, check that SUPI ends with `...001` and add however many clients you need (**Subscriber data number** field). For testing, 1 client will suffice

Return to the terminal
```
docker exec -it ueransim bash
./nr-ue -c config/uecfg.yaml
```
There should be no errors. If you get `ILLEGAL_UE`, make sure that the previously registered SUPI is correct
#### Terminal 2
```
docker exec -it ueransim bash
curl -k --tlmsp /shared/TLMSP/tlmsp-tools/examples/apache.1mbox.ucl 'https://192.168.58.1:4444/function/figlet.openfaas-fn' --data "Test"
```
The output should be
```
 _           _____
| |_ ___  __|_   _|
| __/ __|/ _ \| |
| |_\__ \  __/| |
 \__|___/\___||_|
```
since the middlebox reverses the input string sent to the server

## Notes
- The openfaas webui is available on the host on http://127.0.0.1:5001. The username is `admin`; to get the password, run on the server   
`sudo kubectl get secret -n openfaas basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode`
