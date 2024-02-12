#!/bin/bash
function log {
	echo -e "[INFO] $1"
}

function logerr {
	echo -e "[ERRO] $1"
}

if [[ ! -f /home/vagrant/shared/tlmsp-compiled-20.04.tar ]]
then
	logerr "Compiled 20.04 TLMSP binaries missing in shared folder! Did you start the 20.04 vm?"
	exit 1
fi
mkdir /home/vagrant/tlmsp
tar -C /home/vagrant/tlmsp -xf /home/vagrant/shared/tlmsp-compiled-20.04.tar

FREE5GC_COMPOSE_REPO='https://github.com/free5gc/free5gc-compose.git'
VAGRANT_UID='1000'
# Original configuration uses vagrant shared folder, but since it's not essential and I'm using windows/ntfs I'll move this to an internal folder
# SYNCED_FOLDER='/vagrant'
SYNCED_FOLDER='/home/vagrant'
WORKSPACE='free5gc-compose'

log "Start pre-config script"

log "Set environment variables"
export DEBIAN_FRONTEND=noninteractive

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
		git \
		build-essential \
		vim \
		strace \
		net-tools \
		iputils-ping \
		iproute2 \
	|| exit 1

log "Update linux kernel"
apt-get install -qq \
		linux-image-generic \
		linux-headers-generic \
	|| exit 1

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

log "Verify docker install"
docker --version

log "Verify docker-compose install"
docker compose version

mkdir -p $SYNCED_FOLDER/$WORKSPACE

log "Git clone free5gc-compose project"
git clone $FREE5GC_COMPOSE_REPO $SYNCED_FOLDER/$WORKSPACE

log "Add shared folders to ueransim container"
patch -N -d/ -p0 <<< '--- '$SYNCED_FOLDER/$WORKSPACE'/docker-compose.yaml 2023-11-22 16:20:03.700678250 +0000
+++ '$SYNCED_FOLDER/$WORKSPACE'/docker-compose-WithShared.yaml      2023-11-22 16:19:48.604678390 +0000
@@ -235,10 +235,12 @@
   ueransim:
     container_name: ueransim
     image: free5gc/ueransim:latest
-    command: ./nr-gnb -c ./config/gnbcfg.yaml
+    command: bash -c "echo -e '"'"'export PATH=/tlmsp/install/bin:$$PATH\\nexport LD_LIBRARY_PATH=/tlmsp/install/lib:$$LD_LIBRARY_PATH'"'"' >> /root/.bashrc; ./nr-gnb -c ./config/gnbcfg.yaml"
     volumes:
       - ./config/gnbcfg.yaml:/ueransim/config/gnbcfg.yaml
       - ./config/uecfg.yaml:/ueransim/config/uecfg.yaml
+      - ../tlmsp:/tlmsp
+      - ../shared:/shared
     cap_add:
       - NET_ADMIN
     devices:'

log "End pre-config script. Reload the box.."
