package main

import (
	"net/http"
)

func processRequest(inputData *http.Request) (bool, string, any) {
	return true, "", nil
}

func processResponse(inputData *http.Response, user string, messageType any) {
}
