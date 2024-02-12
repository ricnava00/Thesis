package main

import (
	"bytes"
	"crypto/md5"
	"fmt"
	"hash/fnv"
	"io"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	CodeExpirationSeconds = 600
	AllowTestingHeader    = true // After executing code check, accept even if code is invalid
)

var mutex sync.Mutex

type Message struct {
	ConnectionID int
	Type         *MessageType
	Valid        bool
	ResponseCode int
}

type State struct {
	Transitions []Transition
}

type Transition struct {
	ToState     int
	MessageType *MessageType
}

type Code struct {
	Code       string
	Expiration time.Time
}

type Session struct {
	Messages []Message
	State    int
	Codes    map[*MessageType]Code
}

var states = []State{
	{[]Transition{{1, &initMessageType}}},
	{[]Transition{{2, &buildProductMessageType}}},
	{[]Transition{{3, &productImageMessageType}}},
	{[]Transition{{4, &productsMessageType}}},
	{[]Transition{{5, &categoriesMessageType}}},
	{[]Transition{{6, &productPurchaseMessageType}}},
	{[]Transition{{7, &photographerRegisterMessageType}}},
	{[]Transition{{8, &photoRequestMessageType}}},
	{[]Transition{{0, &photoAssignmentMessageType}}},
}

var session = make(map[string]Session)

func generateCode() string {
	h := fnv.New64a()
	h.Write([]byte(strconv.FormatInt(time.Now().UnixNano(), 10)))
	return fmt.Sprintf("%x", h.Sum64())
}

func parseJWT(idToken string) (map[string]any, error) {
	return (map[string]any{"email": "TODO"}), nil
}

func processRequest(inputData *http.Request) (bool, string, *MessageType) {
	//read body without consuming it
	body := []byte{}
	if inputData.Body != nil {
		body, _ = io.ReadAll(inputData.Body)
		inputData.Body = io.NopCloser(bytes.NewBuffer(body))
	}
	headers := inputData.Header
	method := inputData.Method
	uri := inputData.URL.Path

	info("method: " + method + ", uri: " + uri)
	user := "Unknown"
	if id_token := headers.Get("Authorization"); id_token != "" {
		if strings.HasPrefix(id_token, "Bearer ") {
			id_token = id_token[7:]
		}
		if userObj, err := parseJWT(id_token); err != nil {
			info("\033[1;33mCouldn't get email from token: " + err.Error() + "\033[0m")
		} else {
			user = userObj["email"].(string)
		}
	} else {
		info("\033[33mNo auth token in request\033[0m")
	}

	messageType := (*MessageType)(nil)

	userSessionTmp, ok := session[user]
	if !ok {
		userSessionTmp = Session{Messages: []Message{}, State: 0, Codes: map[*MessageType]Code{}}
	}

	for n, code := range userSessionTmp.Codes {
		if code.Expiration.Before(time.Now()) {
			delete(userSessionTmp.Codes, n)
		}
	}

	valid := false
	code := headers.Get("X-Code")
	for _, testMessage := range states[userSessionTmp.State].Transitions {
		info("Testing " + testMessage.MessageType.Uri)
		if testMessage.MessageType.MatchRequest(method, uri) {
			messageType = testMessage.MessageType
			valid = true
			if !messageType.ValidateSchemas(body) {
				info("\033[1;33mRequest not matching schema\033[0m")
				valid = false
			}
			if testCode, ok := userSessionTmp.Codes[messageType]; !((ok && testCode.Code == code) || messageType == &initMessageType) {
				if _, ok := headers["X-Testing"]; !(AllowTestingHeader && ok) {
					info("\033[1;33mInvalid code\033[0m")
					valid = false
				}
			}
			break
		}
	}
	if messageType == nil {
		info("\033[1;31mNo match\033[0m")
	} else {
		session[user] = userSessionTmp
	}
	return valid, user, messageType
}

func processResponse(inputData *http.Response, user string, messageType any) {
	messageType = messageType.(*MessageType)
	//read body without consuming it
	body := []byte{}
	if inputData.Body != nil {
		body, _ = io.ReadAll(inputData.Body)
		inputData.Body = io.NopCloser(bytes.NewBuffer(body))
	}
	headers := inputData.Header
	responseCode := inputData.StatusCode

	info("responseCode: " + strconv.Itoa(responseCode))

	userSessionTmp, _ := session[user]

	if responseCode == 200 || messageType == &initMessageType {
		userSessionTmp.State = states[userSessionTmp.State].Transitions[0].ToState
		userSessionTmp.Codes = make(map[*MessageType]Code)
		for _, t := range states[userSessionTmp.State].Transitions {
			userSessionTmp.Codes[t.MessageType] = Code{generateCode(), time.Now().Add(CodeExpirationSeconds * time.Second)}
			info(t.MessageType.Uri + ": " + userSessionTmp.Codes[t.MessageType].Code)
		}
		for k, v := range userSessionTmp.Codes {
			headers.Add("X-Code-"+fmt.Sprintf("%x", md5.Sum([]byte(k.Uri))), v.Code)
		}
	}
	session[user] = userSessionTmp
}
