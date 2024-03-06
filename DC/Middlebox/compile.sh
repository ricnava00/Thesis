go build -o client client.go
go build -o middlebox_empty middlebox.go emptyHandler.go
go build -o middlebox middlebox.go middleboxHandler.go messageTypes.go
