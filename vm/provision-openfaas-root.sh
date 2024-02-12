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
#For ease of mofication outside of VM
ln -sf /home/vagrant/shared/vm/httpd_tlmsp.conf /home/vagrant/tlmsp/install/etc/apache24/

log "Upgrade packages"
apt-get update -qq \
	&& apt-get upgrade -qq \
	|| exit 1

log "Install nice-to-haves"
apt-get install -qq \
		bash-completion \
		command-not-found \
	|| exit 1

log "Install dependencies"
apt-get install -qq \
		acl \
		golang-go \
		libev4 \
	|| exit 1
echo 'export GOPATH=$HOME/go' >> /home/vagrant/.bashrc
echo 'export PATH=$PATH:$GOPATH/bin' >> /home/vagrant/.bashrc

log "Install latest version of docker and docker-compose"
apt-get remove -qq \
		docker \
		docker.io \
		containerd \
		runc \
	&& apt-get install -qq \
		apt-transport-https \
		ca-certificates \
		curl \
		gnupg \
		gnupg-agent \
		software-properties-common \
	&& install -m 0755 -d /etc/apt/keyrings \
	&& curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg \
	&& chmod a+r /etc/apt/keyrings/docker.gpg \
	&& echo "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" > /etc/apt/sources.list.d/docker.list \
	&& apt-get update -qq \
	&& apt-get install -qq \
		docker-ce \
		docker-ce-cli \
		docker-compose-plugin \
		containerd.io \
	&& groupadd docker | true \
	&& usermod -aG docker $(id -nu $VAGRANT_UID) \
	&& setfacl -m user:$(id -nu $VAGRANT_UID):rw /var/run/docker.sock \
	&& systemctl enable docker \
	|| exit 1