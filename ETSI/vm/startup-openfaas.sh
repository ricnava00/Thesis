#Unused - for some reason the port forward stops working (obviously, it stops immediately when the ssh session closes, but even using disown to keep it running, after some time it will stop. For now, start it manually)
sudo kubectl rollout status -n openfaas deploy/gateway
if [[ -z $(ps -ax | grep port-forward | grep 8080) ]]
then
	retries=0
	while [[ $retries -lt 60 ]]
	do
		sudo kubectl port-forward --address 0.0.0.0 -n openfaas svc/gateway 8080:8080 >/dev/null 2>/dev/null & #Leave in background
		sleep 1 #Wait
		[[ ! -z $(jobs -r) ]] && break
		echo "Waiting for kubernetes to start"
		let retries++
	done
	[[ -z $(jobs -r) ]] && echo "Kubernetes didn't start" && exit 1
fi
exit 0 #Explicitly exit with success since last status code is error