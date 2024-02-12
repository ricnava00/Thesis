#!/bin/bash
function log {
	echo -e "[INFO] $1"
}

function logerr {
	echo -e "[ERRO] $1"
}

if [[ ! -f /home/vagrant/shared/go-compiled.tar ]]
then
	logerr "Compiled go binaries missing in shared folder! Did you start the middlebox vm?"
	exit 1
fi
mkdir /home/vagrant/go
tar -C /home/vagrant/go -xf /home/vagrant/shared/go-compiled.tar
echo 'export PATH=/home/vagrant/go/bin:$PATH' >> ~/.bashrc
export PATH=/home/vagrant/go/bin:$PATH

log "Upgrade packages"
apt-get update -qq \
	&& apt-get upgrade -qq \
	|| exit 1

log "Install nice-to-haves"
apt-get install -qq \
		bash-completion \
		command-not-found \
	|| exit 1