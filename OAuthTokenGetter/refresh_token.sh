#!/bin/bash
clientId=$(grep YOUR_CLIENT_ID secrets.js | sed -r "s/.* *= *.//" | sed 's/.;//')
clientSecret=$(grep YOUR_CLIENT_SECRET secrets.js | sed -r "s/.* *= *.//" | sed 's/.;//')
refreshToken=$(cat refresh_token.txt | tr -d '\n')
if [[ -z $refreshToken ]]
then
	echo Put the refresh token in refresh_token.txt
	exit 1
fi
if [[ -z $clientId || -z $clientSecret ]]
then
	echo Check formatting of secrets.js
	exit 1
fi
curl -s "https://oauth2.googleapis.com/token" -H "Content-Type: application/x-www-form-urlencoded" --data "client_id=$clientId&client_secret=$clientSecret&refresh_token=$refreshToken&grant_type=refresh_token"