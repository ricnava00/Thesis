package main

import (
	"crypto/tls"
	"log"
	"net/url"
	"net/http"
        "net/http/httputil"
	"os"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"strings"
	"fmt"
	_"crypto"
)

const (
	port = ":8443"
	targetUrl = "http://192.168.58.1:8080"
)

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
	/*cert, _ := tls.LoadX509KeyPair("cert.pem", "key.pem")
	priv2, ok := cert.PrivateKey.(crypto.Signer)
	if !ok {
		return
	}
	fmt.Printf("%T\n",priv2.Public());

	x509Cert, err := x509.ParseCertificate(cert.Certificate[0]);
	if err != nil {
		log.Fatalf("failed to parse certificate in the chain: %w", err)
	}
	
	fmt.Printf("%T\n",x509Cert.PublicKey);*/

	// cert, err := tls.LoadX509KeyPair("cert.pem", "key.pem")
	cert, err := loadCertificate("cert.pem")
	if err != nil {
		log.Fatalf("Failed to load X509 key pair: %v", err)
	}

	dcBytes, err := os.ReadFile("dc.cred")
	if err != nil {
		log.Fatalf("Failed to open dc.cred for writing: %v", err)
	}

	dc, err := tls.UnmarshalDelegatedCredential(dcBytes)
	if err != nil {
		log.Fatalf("Failed to open dc.cred for writing: %v", err)
	}
	
	pemBytes, err := os.ReadFile("dckey.pem")
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
	serverDC=append(serverDC,tls.DelegatedCredentialPair{dc,priv})
	cert.DelegatedCredentials=serverDC
	config := &tls.Config{
		Certificates: []tls.Certificate{cert},
	}

	remote, err := url.Parse(targetUrl)
	if err != nil {
		panic(err)
	}

	handler := func(p *httputil.ReverseProxy) func(http.ResponseWriter, *http.Request) {
		return func(w http.ResponseWriter, r *http.Request) {
                        log.Println(r.URL)
			r.Host = remote.Host
			p.ServeHTTP(w, r)
		}
	}
	
	proxy := httputil.NewSingleHostReverseProxy(remote)
	router := http.NewServeMux()
	router.HandleFunc("/", handler(proxy))

	server := &http.Server{
		Addr: port,
		Handler: router,
		TLSConfig: config,
	}

	log.Printf("Listening on %s...", port)
	err = server.ListenAndServeTLS("", "")
	if err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}