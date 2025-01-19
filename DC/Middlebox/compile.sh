#!/bin/bash
go="$HOME/go_DC/bin/go"
if [ ! -f $go ]; then
    go="$HOME/go/bin/go"
fi
if [ ! -f $go ]; then
    go="go"
fi
"$go" build -o client client.go
"$go" build -o middlebox_empty middlebox.go emptyHandler.go
"$go" build -o middlebox middlebox.go middleboxHandler.go messageTypes.go
