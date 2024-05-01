go build -o client client.go
go build -o listener_empty listener.go emptyHandler.go
go build -o listener listener.go middleboxHandler.go messageTypes.go
