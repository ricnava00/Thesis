#!/bin/bash 
reg_name='kind-registry'
reg_port='5001'
set -o errexit

function log {
	echo -e "[INFO] $1"
}

log "Install kind"
go install sigs.k8s.io/kind@v0.20.0

#https://kind.sigs.k8s.io/docs/user/local-registry/
log "Create cluster if missing"
if [[ -z $(sudo /home/vagrant/go/bin/kind get clusters) ]]
then
    # 1. Create registry container unless it already exists
    if [ "$(sudo docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
      sudo docker run \
        -d --restart=always -p "127.0.0.1:${reg_port}:5000" --network bridge --name "${reg_name}" \
        registry:2
    fi

    # 2. Create kind cluster with containerd registry config dir enabled
    cat <<EOF | sudo /home/vagrant/go/bin/kind create cluster --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    config_path = "/etc/containerd/certs.d"
EOF

    # 3. Add the registry config to the nodes
    #
    # This is necessary because localhost resolves to loopback addresses that are
    # network-namespace local.
    # In other words: localhost in the container is not localhost on the host.
    #
    # We want a consistent name that works from both ends, so we tell containerd to
    # alias localhost:${reg_port} to the registry container when pulling images
    REGISTRY_DIR="/etc/containerd/certs.d/localhost:${reg_port}"
    for node in $(sudo /home/vagrant/go/bin/kind get nodes); do
      sudo docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
      cat <<EOF | sudo docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${reg_name}:5000"]
EOF
    done

    # 4. Connect the registry to the cluster network if not already connected
    # This allows kind to bootstrap the network but ensures they're on the same network
    if [ "$(sudo docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${reg_name}")" = 'null' ]; then
      sudo docker network connect "kind" "${reg_name}"
    fi

    # 5. Document the local registry
    # https://github.com/kubernetes/enhancements/tree/master/keps/sig-cluster-lifecycle/generic/1755-communicating-a-local-registry
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${reg_port}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
fi

log "Install openfaas"
curl -SLsf https://get.arkade.dev/ | sudo sh \
	&& arkade get kubectl faas-cli \
	&& sudo mv /home/vagrant/.arkade/bin/kubectl /usr/local/bin/ \
	&& sudo mv /home/vagrant/.arkade/bin/faas-cli /usr/local/bin/ \
	&& sudo arkade install openfaas

log "Run openfaas"
sudo kubectl rollout status -n openfaas deploy/gateway
if [[ -z $(ps -ax | grep port-forward | grep 8080) ]]
then
	retries=0
	while [[ $retries -lt 60 ]]
	do
		sudo kubectl port-forward --address 0.0.0.0 -n openfaas svc/gateway 8080:8080 >/dev/null 2>/dev/null & #Leave in background
		sleep 1
		[[ ! -z $(jobs -r) ]] && break
		echo "Waiting for kubernetes to start"
		let retries++
	done
	[[ -z $(jobs -r) ]] && exit 1 #Check if started, otherwise error
fi

log "Login and deploy test function"
PASSWORD=$(sudo kubectl get secret -n openfaas basic-auth -o jsonpath="{.data.basic-auth-password}" | base64 --decode; echo)
[[ -z $PASSWORD ]] && exit 1
echo -n $PASSWORD | faas-cli login --username admin --password-stdin \
	&& faas-cli store deploy figlet \
	&& faas-cli list
