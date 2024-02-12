#!/bin/bash
set -e
function log {
	echo -e "[INFO] $1"
}

function logerr {
	echo -e "[ERRO] $1"
}

log "Upgrade packages"
sudo apt-get update -qq
sudo apt-get upgrade -qq

log "Install nice-to-haves"
sudo apt-get install -qq \
		bash-completion \
		command-not-found

log "Install dependencies"
sudo apt-get install -qq golang-go \
  || exit 1

if [[ -f /home/vagrant/shared/go ]]; then
  cp -r /home/vagrant/shared/go go
else
  git clone https://github.com/ricnava00/go
fi
cd go/src
./make.bash
echo 'export PATH=/home/vagrant/go/bin:$PATH' >> ~/.bashrc
export PATH=/home/vagrant/go/bin:$PATH

cd ~/shared/certs
genDelegated=1
if [[ ! -f "cert.pem" || ! -f "key.pem" ]]
then
	log "Creating self-signed certificate"
	go run ~/go/src/crypto/tls/generate_cert.go -host 127.0.0.1 -allowDC
elif [[ -f "dc.cred" && -f "dckey.pem" ]]
then
	log "Certificate and delegated credentials found, using them"
	genDelegated=0
fi
if [[ $genDelegated == 1 ]]
then
	log "Creating delegated credentials"
	log "Remember: they expire after 7 days"
	log "Recreate them using the command"
	log "go run ~/go/src/crypto/tls/generate_delegated_credential.go -cert-path cert.pem -key-path key.pem -signature-scheme Ed25519 -duration 168h"
	go run ~/go/src/crypto/tls/generate_delegated_credential.go -cert-path cert.pem -key-path key.pem -signature-scheme Ed25519 -duration 168h
fi
tar -C /home/vagrant/go -cf /home/vagrant/shared/go-compiled.tar . || exit 1