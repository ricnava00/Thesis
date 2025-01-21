gopath="$HOME/go_DC"
go="$HOME/go_DC/bin/go"
if [ ! -f $go ]; then
    gopath="$HOME/go"
    go="$HOME/go/bin/go"
fi
if [ ! -f $go ]; then
    echo "Could not find modded go binary"
    exit 1
fi
"$go" run "$gopath"/src/crypto/tls/generate_delegated_credential.go -cert-path cert.pem -key-path key.pem -signature-scheme Ed25519 -duration 168h
