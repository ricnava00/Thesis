package main

import (
	"crypto/tls"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
)

const (
	port                    = ":8443"
	targetUrl               = "http://192.168.58.1:8080"
	useDelegatedCredentials = true
	certFile                = "../certs/cert.pem"
	certKeyFile             = "../certs/key.pem"
	delegatedFile           = "../certs/dc.cred"
	delegatedKeyFile        = "../certs/dckey.pem"
)

func info(str string) {
	fmt.Fprintf(os.Stderr, str+"\n")
}

func loadCertificate(certFile string) (tls.Certificate, error) {
	certPEMBlock, err := os.ReadFile(certFile)
	if err != nil {
		return tls.Certificate{}, err
	}

	fail := func(err error) (tls.Certificate, error) { return tls.Certificate{}, err }

	var cert tls.Certificate
	var skippedBlockTypes []string
	for {
		var certDERBlock *pem.Block
		certDERBlock, certPEMBlock = pem.Decode(certPEMBlock)
		if certDERBlock == nil {
			break
		}
		if certDERBlock.Type == "CERTIFICATE" {
			cert.Certificate = append(cert.Certificate, certDERBlock.Bytes)
		} else {
			skippedBlockTypes = append(skippedBlockTypes, certDERBlock.Type)
		}
	}

	if len(cert.Certificate) == 0 {
		if len(skippedBlockTypes) == 0 {
			return fail(errors.New("tls: failed to find any PEM data in certificate input"))
		}
		if len(skippedBlockTypes) == 1 && strings.HasSuffix(skippedBlockTypes[0], "PRIVATE KEY") {
			return fail(errors.New("tls: failed to find certificate PEM data in certificate input, but did find a private key; PEM inputs may have been switched"))
		}
		return fail(fmt.Errorf("tls: failed to find \"CERTIFICATE\" PEM block in certificate input after skipping PEM blocks of the following types: %v", skippedBlockTypes))
	}

	_, err = x509.ParseCertificate(cert.Certificate[0])
	if err != nil {
		return fail(err)
	}

	return cert, nil
}

func main() {
	var cert tls.Certificate
	if !useDelegatedCredentials {
		info("Warning: Delegated Credentials are not being used")
		var err error
		cert, err = tls.LoadX509KeyPair(certFile, certKeyFile)
		if err != nil {
			log.Fatalf("Failed to load X509 key pair: %v", err)
		}
	} else {
		// Uncomment these and comment after to test on a system without modified go
		// info("Uncomment")
		// os.Exit(1)
		var err error
		cert, err = loadCertificate(certFile)
		if err != nil {
			log.Fatalf("Failed to load X509 key pair: %v", err)
		}

		dcBytes, err := os.ReadFile(delegatedFile)
		if err != nil {
			log.Fatalf("Failed to open dc.cred for writing: %v", err)
		}

		dc, err := tls.UnmarshalDelegatedCredential(dcBytes)
		if err != nil {
			log.Fatalf("Failed to open dc.cred for writing: %v", err)
		}

		pemBytes, err := os.ReadFile(delegatedKeyFile)
		if err != nil {
			log.Fatalf("Failed to open dc.cred for writing: %v", err)
		}

		block, _ := pem.Decode(pemBytes)

		if block == nil {
			log.Fatalf("Failed to open dc.cred for writing: %v", err)
		}

		priv, err := x509.ParsePKCS8PrivateKey(block.Bytes)
		if err != nil {
			log.Fatalf("Failed to open dc.cred for writing: %v", err)
		}

		var serverDC []tls.DelegatedCredentialPair
		serverDC = append(serverDC, tls.DelegatedCredentialPair{dc, priv})
		cert.DelegatedCredentials = serverDC
	}
	config := &tls.Config{
		Certificates: []tls.Certificate{cert},
	}

	remote, err := url.Parse(targetUrl)
	if err != nil {
		panic(err)
	}

	var connectionID int = 0
	var valid bool
	var user string
	var messageType any

	handler := func(p *httputil.ReverseProxy) func(http.ResponseWriter, *http.Request) {
		return func(w http.ResponseWriter, r *http.Request) {
			log.Println(r.URL)
			r.Host = remote.Host
			valid, user, messageType = processRequest(r)
			if valid {
				p.ServeHTTP(w, r)
			} else {
				conn, _, err := w.(http.Hijacker).Hijack()
				if err != nil {
					log.Println("Hijack failed: " + err.Error())
					return
				}
				log.Println("Hijack OK")
				conn.Close()
			}
			connectionID++
		}
	}

	proxy := httputil.NewSingleHostReverseProxy(remote)
	proxy.ModifyResponse = func(r *http.Response) error {
		info("Valid: " + fmt.Sprint(valid) + ", user: " + user + ", messageType: " + fmt.Sprint(messageType) + "\n")
		processResponse(r, user, messageType)
		return nil
	}
	router := http.NewServeMux()
	router.HandleFunc("/", handler(proxy))

	server := &http.Server{
		Addr:      port,
		Handler:   router,
		TLSConfig: config,
		TLSNextProto: map[string]func(*http.Server, *tls.Conn, http.Handler){}, // Force HTTP/1.1 for hijack support
	}

	log.Printf("Listening on %s...", port)
	err = server.ListenAndServeTLS("", "")
	if err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
