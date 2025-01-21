package main

import (
	"bytes"
	"context"
	"crypto"
	"crypto/ecdsa"
	"crypto/ed25519"
	"crypto/md5"
	"crypto/rsa"
	"encoding/gob"
	"encoding/json"
	"fmt"
	"hash/fnv"
	"io"
	"log"
	"mime"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	"github.com/go-jose/go-jose/v3"
	"golang.org/x/oauth2"
)

const (
	oidcServer            = "https://accounts.google.com"
	CodeExpirationSeconds = 600
	AllowTestingHeader    = true // After executing code check, accept even if code is invalid
	JWKSCacheFile         = "jwks.dat"
)

var mutex sync.Mutex
var ctx = context.Background()
var verifier *oidc.IDTokenVerifier

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
/* 
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
*/

var states = []State{
	{[]Transition{{1, &initMessageType}}},
	{[]Transition{{2, &initMessageType}}},
	{[]Transition{{3, &initMessageType}}},
	{[]Transition{{4, &initMessageType}}},
	{[]Transition{{5, &initMessageType}}},
	{[]Transition{{6, &initMessageType}}},
	{[]Transition{{7, &initMessageType}}},
	{[]Transition{{8, &initMessageType}}},
	{[]Transition{{0, &initMessageType}}},
}

var session = make(map[string]Session)

func generateCode() string {
	h := fnv.New64a()
	h.Write([]byte(strconv.FormatInt(time.Now().UnixNano(), 10)))
	return fmt.Sprintf("%x", h.Sum64())
}

func parseJWT(idToken string) (map[string]any, error) {
	token, err := verifier.Verify(ctx, idToken)
	if err != nil {
		return nil, err
	}
	claims := map[string]any{}
	token.Claims(&claims)
	return (map[string]any{"email": claims["email"]}), nil
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
			return false, user, nil
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

	if responseCode == 200 {
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

type oidc_providerJSON struct {
	Issuer        string   `json:"issuer"`
	AuthURL       string   `json:"authorization_endpoint"`
	TokenURL      string   `json:"token_endpoint"`
	DeviceAuthURL string   `json:"device_authorization_endpoint"`
	JWKSURL       string   `json:"jwks_uri"`
	UserInfoURL   string   `json:"userinfo_endpoint"`
	Algorithms    []string `json:"id_token_signing_alg_values_supported"`
}

type cachedKeys struct {
	Keys       []crypto.PublicKey
	Expiration time.Time
}

func writeCache(m cachedKeys) ([]byte, error) {
	b := bytes.Buffer{}
	e := gob.NewEncoder(&b)
	err := e.Encode(m)
	if err != nil {
		return []byte{}, err
	}
	return b.Bytes(), nil
}

func readCache(by []byte) (cachedKeys, error) {
	m := cachedKeys{}
	b := bytes.Buffer{}
	b.Write(by)
	d := gob.NewDecoder(&b)
	err := d.Decode(&m)
	if err != nil {
		return cachedKeys{}, err
	}
	return m, nil
}

func oidc_doRequest(ctx context.Context, req *http.Request) (*http.Response, error) {
	client := http.DefaultClient
	if c := oidc_getClient(ctx); c != nil {
		client = c
	}
	return client.Do(req.WithContext(ctx))
}

func oidc_getClient(ctx context.Context) *http.Client {
	if c, ok := ctx.Value(oauth2.HTTPClient).(*http.Client); ok {
		return c
	}
	return nil
}

func oidc_unmarshalResp(r *http.Response, body []byte, v interface{}) error {
	err := json.Unmarshal(body, &v)
	if err == nil {
		return nil
	}
	ct := r.Header.Get("Content-Type")
	mediaType, _, parseErr := mime.ParseMediaType(ct)
	if parseErr == nil && mediaType == "application/json" {
		return fmt.Errorf("got Content-Type = application/json, but could not unmarshal as JSON: %v", err)
	}
	return fmt.Errorf("expected Content-Type = application/json, got %q: %v", ct, err)
}

func refreshProviderConfig(ctx context.Context, issuer string) ([]crypto.PublicKey, time.Time, error) {
	wellKnown := strings.TrimSuffix(issuer, "/") + "/.well-known/openid-configuration"
	req, err := http.NewRequest("GET", wellKnown, nil)
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), err
	}
	resp, err := oidc_doRequest(ctx, req)
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), fmt.Errorf("unable to read response body: %v", err)
	}

	if resp.StatusCode != http.StatusOK {
		return []crypto.PublicKey{}, time.Now(), fmt.Errorf("%s: %s", resp.Status, body)
	}

	var p oidc_providerJSON
	err = oidc_unmarshalResp(resp, body, &p)
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), fmt.Errorf("oidc: failed to decode provider discovery object: %v", err)
	}

	if p.Issuer != issuer {
		return []crypto.PublicKey{}, time.Now(), fmt.Errorf("oidc: issuer did not match the issuer returned by provider, expected %q got %q", issuer, p.Issuer)
	}

	req, err = http.NewRequest("GET", p.JWKSURL, nil)
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), err
	}
	resp, err = oidc_doRequest(ctx, req)
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), err
	}
	expiration, err := time.Parse(time.RFC1123, resp.Header.Get("Expires"))
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), err
	}
	defer resp.Body.Close()

	jwks, err := io.ReadAll(resp.Body)

	if resp.StatusCode != http.StatusOK {
		return []crypto.PublicKey{}, time.Now(), fmt.Errorf("oidc: get keys failed: %s %s", resp.Status, body)
	}

	var keySet jose.JSONWebKeySet
	err = oidc_unmarshalResp(resp, jwks, &keySet)
	if err != nil {
		return []crypto.PublicKey{}, time.Now(), fmt.Errorf("oidc: failed to decode keys: %v %s", err, body)
	}

	keys := []crypto.PublicKey{}
	for _, key := range keySet.Keys {
		keys = append(keys, key.Key)
	}

	return keys, expiration, nil
}

func init() {
	gob.Register(rsa.PublicKey{})
	gob.Register(ecdsa.PublicKey{})
	gob.Register(ed25519.PublicKey{})
	reload := false
	serializedBytes, err := os.ReadFile(JWKSCacheFile)
	if err != nil {
		reload = true
	}
	cached, err := readCache(serializedBytes)
	if err != nil {
		reload = true
	}
	publicKeys := cached.Keys
	expiration := cached.Expiration
	if expiration.Before(time.Now()) {
		reload = true
	}
	if reload {
		info("Reloading jwks")
		publicKeys, expiration, err = refreshProviderConfig(ctx, oidcServer)
		if err != nil {
			log.Fatal(err)
		}
		serialized, err := writeCache(cachedKeys{Keys: publicKeys, Expiration: expiration})
		if err != nil {
			log.Fatal(err)
		}
		err = os.WriteFile(JWKSCacheFile, serialized, 0644)
		if err != nil {
			log.Fatal(err)
		}
	}
	//Validate wants pointers
	for i, key := range publicKeys {
		switch key.(type) {
		case rsa.PublicKey:
			tmp := key.(rsa.PublicKey)
			publicKeys[i] = crypto.PublicKey(&tmp)
		case ecdsa.PublicKey:
			tmp := key.(ecdsa.PublicKey)
			publicKeys[i] = crypto.PublicKey(&tmp)
		}
	}
	keySet := &oidc.StaticKeySet{PublicKeys: publicKeys}
	verifier = oidc.NewVerifier(oidcServer, keySet, &oidc.Config{SkipClientIDCheck: true})
}
