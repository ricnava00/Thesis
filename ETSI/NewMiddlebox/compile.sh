#!/bin/bash
go="$HOME/go_DC/bin/go"
if [ ! -f $go ]; then
    go="$HOME/go/bin/go"
fi
if [ ! -f $go ]; then
    echo -e "\e[1;33mWarning: using system go, results might not be comparable\e[0m"
    go="go"
fi
"$go" build -o client client.go
"$go" build -o listener_empty listener.go emptyHandler.go
"$go" build -o listener listener.go middleboxHandler.go messageTypes.go
