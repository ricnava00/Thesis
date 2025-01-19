package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"os"
	"strings"
	"time"
)

const (
	port = ":8080"
)

func info(str string) {
	fmt.Fprintf(os.Stderr, str+"\n")
}

func handlePost(w http.ResponseWriter, r *http.Request) {
	var params = make(map[string]interface{})
	err := json.NewDecoder(r.Body).Decode(&params)
	if err != nil {
		log.Println("Error decoding JSON: " + err.Error())
		return
	}
	log.Println("Received JSON: " + fmt.Sprint(params))
	if params["is_response"] == true {
		fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(client-side): Listener started")
		handleResponse(w, r, params)
		fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(client-side): Listener finished")
	} else {
		fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(server-side): Listener started")
		handleRequest(w, r, params)
		fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(server-side): Listener finished")
	}
}

func handleRequest(w http.ResponseWriter, r *http.Request, params map[string]interface{}) {
	log.Println("Received request")
	request, err := ParseRawHTTPRequest(params["data"].(string))
	if err != nil {
		log.Println("Error parsing request: " + err.Error())
		return
	}
	log.Println("Parsed request: " + fmt.Sprint(request))
	fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(server-side): processRequest started")
	valid, user, messageType := processRequest(request)
	fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(server-side): processRequest finished")
	var output map[string]interface{}
	if valid {
		requestInfo[int(params["connection_id"].(float64))] = map[string]interface{}{
			"user":        user,
			"messageType": messageType,
		}
		rawRequest, err := httputil.DumpRequest(request, true)
		if err != nil {
			log.Println("Error dumping request: " + err.Error())
			return
		}
		output = map[string]interface{}{
			"success": true,
			"data":    string(rawRequest),
		}
	} else {
		output = map[string]interface{}{
			"success": false,
		}
	}
	out, err := json.Marshal(output)
	if err != nil {
		log.Println("Error marshalling JSON: " + err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(out)
}

func handleResponse(w http.ResponseWriter, r *http.Request, params map[string]interface{}) {
	log.Println("Received response")
	response, err := ParseRawHTTPResponse(params["data"].(string))
	if err != nil {
		log.Println("Error parsing response: " + err.Error())
		return
	}
	log.Println("Parsed response: " + fmt.Sprint(response))
	reqInfo, ok := requestInfo[int(params["connection_id"].(float64))]
	if !ok {
		log.Println("No request info found for connection ID")
		return
	}
	user := reqInfo["user"].(string)
	messageType := reqInfo["messageType"]
	fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(client-side): processResponse started")
	processResponse(response, user, messageType)
	fmt.Fprintln(os.Stderr, time.Now().UnixNano(), "splice", params["connection_id"], "(client-side): processResponse finished")
	delete(requestInfo, int(params["connection_id"].(float64)))
	rawResponse, err := httputil.DumpResponse(response, true)
	if err != nil {
		log.Println("Error dumping response: " + err.Error())
		return
	}
	output := map[string]interface{}{
		"success": true,
		"data":    string(rawResponse),
	}
	out, err := json.Marshal(output)
	if err != nil {
		log.Println("Error marshalling JSON: " + err.Error())
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(out)
}

func ParseRawHTTPRequest(raw string) (*http.Request, error) {
	buf := bufio.NewReader(strings.NewReader(raw))
	return http.ReadRequest(buf)
}

func ParseRawHTTPResponse(raw string) (*http.Response, error) {
	buf := bufio.NewReader(strings.NewReader(raw))
	return http.ReadResponse(buf, nil)
}

var requestInfo = map[int]map[string]interface{}{}

func main() {
	router := http.NewServeMux()
	router.HandleFunc("/", handlePost)

	server := &http.Server{
		Addr:    port,
		Handler: router,
	}

	log.Printf("Listening on %s...", port)
	err := server.ListenAndServe()
	if err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
