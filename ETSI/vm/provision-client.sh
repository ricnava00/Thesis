#!/bin/bash
function log {
	echo -e "[INFO] $1"
}

function logerr {
	echo -e "[ERRO] $1"
}

if [[ ! -f /home/vagrant/shared/tlmsp-compiled.tar ]]
then
	logerr "Compiled TLMSP binaries missing in shared folder! Did the etsi vm fail?"
	exit 1
fi
mkdir /home/vagrant/tlmsp
tar -C /home/vagrant/tlmsp -xf /home/vagrant/shared/tlmsp-compiled.tar
echo ". /home/vagrant/tlmsp/install/share/tlmsp-tools/tlmsp-env.sh" >> /home/vagrant/.bashrc

log "Upgrade packages"
apt-get update -qq \
	&& apt-get upgrade -qq \
	|| exit 1

log "Install nice-to-haves"
apt-get install -qq \
		bash-completion \
		command-not-found \
	|| exit 1