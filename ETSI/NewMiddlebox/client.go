package main

import (
	"encoding/gob"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
)

func isFlagPassed(name string) bool {
	found := false
	flag.Visit(func(f *flag.Flag) {
		if f.Name == name {
			found = true
		}
	})
	return found
}

func httpsClient(method string, url string, headers []string, data string) []byte {
	client := &http.Client{}

	req, err := http.NewRequest(method, url, strings.NewReader(data))
	if err != nil {
		fmt.Printf("Error creating HTTP request: %v\n", err)
		os.Exit(1)
	}
	for _, header := range headers {
		parts := strings.SplitN(header, ":", 2)
		if len(parts) == 2 {
			req.Header.Add(strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1]))
		} else {
			fmt.Println("Invalid header format:", header)
			os.Exit(1)
		}
	}
	resp, err := client.Do(req)
	if err != nil {
		panic(err)
	}
	defer resp.Body.Close()
	msg, _ := io.ReadAll(resp.Body)
	return msg
}

func main() {
	var waitingBodies = make(map[int][]interface{})
	if _, err := os.Stat("waiting.dat"); err == nil {
		file, _ := os.Open("waiting.dat")
		defer file.Close()
		decoder := gob.NewDecoder(file)
		err = decoder.Decode(&waitingBodies)
		if err != nil {
			fmt.Printf("Error decoding file: %v\n", err)
			os.Exit(1)
		}
	}
	fmt.Println(os.Args)
	connectionID, _ := strconv.Atoi(os.Args[1])
	//spliceID, _ := strconv.Atoi(os.Args[2])
	isResponse, _ := strconv.ParseBool(os.Args[3])
	inputDataBytes, _ := io.ReadAll(os.Stdin)
	if inputDataBytes == nil {
		return
	}
	inputData := string(inputDataBytes)
	var headers map[string]string
	var body string
	var header string
	fmt.Printf("\033[1;2m%s\033[0m\n", inputData)
	if _, ok := waitingBodies[connectionID]; ok {
		body = inputData
		headers = waitingBodies[connectionID][0].(map[string]string)
		oldBody := waitingBodies[connectionID][1].(string)
		oldHeader := waitingBodies[connectionID][2].(string)
		inputData = oldHeader + "\r\n\r\n" + oldBody + inputData
		body = oldBody + body
	} else {
		parts := strings.SplitN(inputData, "\r\n\r\n", 2)
		header = parts[0]
		body = parts[1]
		tmp := strings.Split(header, "\r\n")
		req := tmp[0]
		if !isResponse {
			match := regexp.MustCompile(`(GET|POST|HEAD|PUT|DELETE) ([^ ]+) HTTP/(\d+(?:\.\d+)?)`).FindStringSubmatch(req)
			if match == nil {
				fmt.Println("Invalid request")
				os.Exit(1)
			}
		} else {
			match := regexp.MustCompile(`HTTP/(\d+(?:\.\d+)?) (\d+)`).FindStringSubmatch(req)
			if match == nil {
				fmt.Println("Invalid response")
				os.Exit(1)
			}
		}
		headers = make(map[string]string)
		for _, line := range tmp[1:] {
			parts := strings.SplitN(line, ": ", 2)
			headers[parts[0]] = parts[1]
		}
	}
	cl, _ := strconv.Atoi(headers["Content-Length"])
	if !isResponse && len(body) < cl {
		fmt.Printf("Waiting for body for connection %d\n", connectionID)
		waitingBodies[connectionID] = []interface{}{headers, body, header}
		fmt.Println(waitingBodies)
		file, _ := os.Create("waiting.dat")
		defer file.Close()
		encoder := gob.NewEncoder(file)
		err := encoder.Encode(waitingBodies)
		if err != nil {
			fmt.Printf("Error encoding file: %v\n", err)
			os.Exit(1)
		}
		os.Exit(0)
	} else if _, ok := waitingBodies[connectionID]; ok {
		delete(waitingBodies, connectionID)
		file, _ := os.Create("waiting.dat")
		defer file.Close()
		encoder := gob.NewEncoder(file)
		err := encoder.Encode(waitingBodies)
		if err != nil {
			fmt.Printf("Error encoding file: %v\n", err)
			os.Exit(1)
		}
	}
	reqHeaders := []string{
		"Content-Type: application/json",
	}
	data := map[string]interface{}{
		"connection_id": connectionID,
		"is_response":   isResponse,
		"data":          inputData,
	}
	jsonData, err := json.Marshal(data)
	if err != nil {
		fmt.Printf("Error marshalling JSON: %v\n", err)
		os.Exit(1)
	}
	msg := httpsClient("POST", "http://localhost:8080", reqHeaders, string(jsonData))
	fmt.Println(string(msg))
	var out map[string]interface{}
	err = json.Unmarshal(msg, &out)
	if err != nil {
		fmt.Printf("Remote error")
	} else if out["success"].(bool) {
		fmt.Print(out["data"])
		os.Exit(0)
	} else {
		fmt.Println("Invalid request/response")
	}
	os.Exit(1)
}
