package main

import (
	"crypto/tls"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
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

func httpsClient(method string, url string, headers []string, data string) (int, []byte) {
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify:         true,
			SupportDelegatedCredential: true,
		},
	}
	client := &http.Client{Transport: tr}

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
	//fmt.Println("Response status:", resp.Status)
	msg, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, msg
}

func main() {
	var headers []string
	var postData string
	var outputFile string

	// Parse flags
	flag.Var((*headerList)(&headers), "H", "Header")
	flag.StringVar(&outputFile, "output", "", "File to write the response, if specified")
	flag.StringVar(&outputFile, "o", "", "File to write the response, if specified (shorthand)")
	flag.StringVar(&postData, "data", "", "POST data")
	flag.Parse()

	var method string
	if isFlagPassed("data") {
		method = "POST"
	} else {
		method = "GET"
	}
	// Check if there is a non-flag parameter (URL)
	if flag.NArg() != 1 {
		_, currentFile, _, _ := runtime.Caller(0)
		originalFile := filepath.Base(currentFile)
		fmt.Printf("Usage: %s [-H headers] [--data POST_data] url\n", originalFile)
		os.Exit(1)
	}

	// Retrieve the URL
	url := flag.Arg(0)

	defer func() { // When the middlebox closes the connection because of a wrong code, the client will panic. Catch it and print the error. If the panic is not caused by a closed connection, panic again.
		if err := recover(); err != nil {
			if strings.HasSuffix(fmt.Sprintf("%v", err), "EOF") {
				fmt.Fprintf(os.Stderr, "Error: %s\n", err)
				os.Exit(1)
			} else {
				panic(err)
			}
		}
	}()

	// Display the URL and headers
	responseCode, msg := httpsClient(method, url, headers, postData)
	if responseCode != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Error: %d: %s\n", responseCode, msg)
		os.Exit(1)
	}
	if outputFile != "" {
		err := ioutil.WriteFile(outputFile, msg, 0644)
		if err != nil {
			fmt.Printf("Error writing to output file: %v\n", err)
			os.Exit(1)
		}
	} else {
		fmt.Println(string(msg))
	}
}

// Custom type to parse multiple headers
type headerList []string

// Implement the String method for the custom type
func (h *headerList) String() string {
	return fmt.Sprintf("%v", *h)
}

// Implement the Set method for the custom type
func (h *headerList) Set(value string) error {
	*h = append(*h, value)
	return nil
}
