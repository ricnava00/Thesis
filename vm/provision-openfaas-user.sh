#!/bin/bash 
function log {
	echo -e "[INFO] $1"
}

log "Install kind"
go install sigs.k8s.io/kind@v0.20.0 \
	|| exit 1

log "Create cluster if missing"
[[ -z $(sudo /home/vagrant/go/bin/kind get clusters) ]] \
	&& (
		sudo /home/vagrant/go/bin/kind create cluster \
		|| exit 1
	)

log "Install openfaas"
curl -SLsf https://get.arkade.dev/ | sudo sh \
	&& arkade get kubectl faas-cli \
	&& sudo mv /home/vagrant/.arkade/bin/kubectl /usr/local/bin/ \
	&& sudo mv /home/vagrant/.arkade/bin/faas-cli /usr/local/bin/ \
	&& sudo arkade install openfaas \
	|| exit 1

log "Run openfaas"
sudo kubectl rollout status -n openfaas deploy/gateway \
	|| exit 1
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
	&& faas-cli list \
	|| exit 1
