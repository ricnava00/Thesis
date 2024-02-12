/*
Original python code:
import json
import sys
from typing import Callable

import jsonschema
from abc import abstractmethod

def log(*args, **kwargs):

	print(*args, file=sys.stderr, **kwargs)

def method_and_uri_match(method: str, uri: str, wanted_method: str, wanted_uri: str) -> bool:

	return method == wanted_method and uri == wanted_uri

class MessageType:

	@property
	@abstractmethod
	def url(self):
	    pass

	@classmethod
	@abstractmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    pass

	@classmethod
	def match_request(cls, method: str, uri: str, headers: dict[str, str], body: str) -> bool:
	    return method_and_uri_match(method, uri, "POST", cls.url)

	@classmethod
	@abstractmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    pass

	@classmethod
	@abstractmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    pass

	@classmethod
	@abstractmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    pass

	@classmethod
	def validate_schemas(cls, target_cls: type, body: str | object) -> bool:
	    if isinstance(body, str):
	        try:
	            json_body = json.loads(body or "null")
	        except json.decoder.JSONDecodeError:
	            return False
	    else:
	        json_body = body
	    for json_getter, json_schema_filename in target_cls.schemas().items():
	        try:
	            with open(json_schema_filename, "r") as json_schema_file:
	                json_schema = json.load(json_schema_file)
	            json_fragment = json_getter(json_body)
	            try:
	                jsonschema.validate(json_fragment, json_schema)
	            except jsonschema.exceptions.ValidationError as e:
	                log(e)
	                return False
	        except jsonschema.exceptions as e:
	            log(e)
	            return False
	    return True

class InitMessageType(MessageType):

	url = "/function/init"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {}

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    return session, {}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    return session, {}

class ProductsMessageType(MessageType):

	url = "/function/product-catalog-api/products"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {
	        lambda json_body: json_body: "schemas/products-request-schema.json"
	    }

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    if not super().validate_schemas(cls, body):
	        return session, {"invalid": True}
	    return session, {}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    if response_code == 200:
	        session["has_seen_products"] = True
	    return session, request_data

class CategoriesMessageType(MessageType):  # Note: the response code for this message is always 500 for a bug in the server code

	url = "/function/product-catalog-api/categories"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {}

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    if not super().validate_schemas(cls, body):
	        return session, {"invalid": True}
	    return session, {}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    return session, request_data

class BuildProductMessageType(MessageType):

	url = "/function/product-catalog-builder/product"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {
	        lambda json_body: json_body: "schemas/retail-stream-schema-ingress.json",
	        lambda json_body: json_body['data']: "schemas/product-create-schema.json"
	    }

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    try:
	        json_body = json.loads(body)
	    except json.decoder.JSONDecodeError:
	        return session, {"invalid": True}
	    if not super().validate_schemas(cls, json_body):
	        return session, {"invalid": True}
	    return session, {"id": json_body["data"]["id"]}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    if response_code == 200:
	        if "created_products" not in session:
	            session["created_products"] = []
	        session["created_products"].append(request_data["id"])
	    return session, request_data

class ProductImageMessageType(MessageType):

	url = "/function/product-catalog-builder/image"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {
	        lambda json_body: json_body: "schemas/retail-stream-schema-ingress.json",
	        lambda json_body: json_body['data']: "schemas/product-image-schema.json"
	    }

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    try:
	        json_body = json.loads(body)
	    except json.decoder.JSONDecodeError:
	        return session, {"invalid": True}
	    if not super().validate_schemas(cls, json_body):
	        return session, {"invalid": True}
	    return session, {"id": json_body["data"]["id"]}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    if "id" in request_data and request_data["id"] not in session["created_products"]:
	        return "Set image for product not created by self"
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    return session, request_data

class ProductPurchaseMessageType(MessageType):

	url = "/function/product-purchase"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {
	        lambda json_body: json_body: "schemas/product-purchase-schema.json"
	    }

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    if not super().validate_schemas(cls, body):
	        return session, {"invalid": True}
	    return session, {}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    if not session.get("has_seen_products", False):
	        return "Bought a product without seeing the catalog"
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    return session, request_data

class PhotographerRegisterMessageType(MessageType):

	url = "/function/product-photos-register"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {
	        lambda json_body: json_body: "schemas/retail-stream-schema-ingress.json",
	        lambda json_body: json_body['data']: "schemas/user-update-phone-schema.json"
	    }

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    try:
	        json_body = json.loads(body)
	    except json.decoder.JSONDecodeError:
	        return session, {"invalid": True}
	    if not super().validate_schemas(cls, json_body):
	        return session, {"invalid": True}
	    return session, {"phone": json_body["data"]["phone"]}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    if response_code == 200:
	        session["registered_phone"] = ("" if request_data["phone"][0] == "+" else "+1") + request_data["phone"]
	    return session, request_data

class PhotoRequestMessageType(MessageType):

	url = "/function/product-photos/request"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {
	        lambda json_body: json_body: "schemas/retail-stream-schema-ingress.json",
	        lambda json_body: json_body["data"]: "schemas/photo-request-schema.json"
	    }

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    try:
	        json_body = json.loads(body)
	    except json.decoder.JSONDecodeError:
	        return session, {"invalid": True}
	    if not super().validate_schemas(cls, json_body):
	        return session, {"invalid": True}
	    return session, {"id": json_body["data"]["id"]}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    if "id" in request_data and request_data["id"] not in session["created_products"]:
	        return "Requested image for product not created by self"
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    return session, request_data

class PhotoAssignmentMessageType(MessageType):

	url = "/function/product-photos/photos"

	@classmethod
	def schemas(cls) -> dict[Callable[[dict], dict], str]:
	    return {
	        lambda json_body: json_body: "schemas/photo-assignment-schema.json"
	    }

	@classmethod
	def parse_request(cls, session: dict, method: str, uri: str, headers: dict[str, str], body: str) -> (dict, dict):
	    try:
	        json_body = json.loads(body)
	    except json.decoder.JSONDecodeError:
	        return session, {"invalid": True}
	    if not super().validate_schemas(cls, json_body):
	        return session, {"invalid": True}
	    return session, {"from": json_body["From"]}

	@classmethod
	def validate_request(cls, session: dict, request_data: dict) -> str | None:
	    if "registered_phone" not in session:
	        return "Uploaded photo without being registered as a photographer"
	    elif session["registered_phone"] != request_data["from"]:
	        return "Uploaded photo with different phone number as the registered one"
	    return None

	@classmethod
	def parse_response(cls, session: dict, request_data: dict, response_code: int, body: str) -> (dict, dict):
	    return session, request_data

fail = False
for message_type in MessageType.__subclasses__():

	for schema in message_type.schemas().values():
	    with open(schema, "r") as schema_file:
	        try:
	            json.load(schema_file)
	        except json.decoder.JSONDecodeError as e:
	            log(e)
	            fail = True

if fail:

	sys.exit(1)
*/
package main

import (
	"encoding/json"
	"log"

	"github.com/santhosh-tekuri/jsonschema/v5"
)

type MessageType struct {
	Method  string
	Uri     string
	Schemas []Schema
}

type Schema struct {
	JsonGetter         func(any) any
	JsonSchemaFilename string
}

var initMessageType = MessageType{"POST", "/function/init", []Schema{}}
var productsMessageType = MessageType{"POST", "/function/product-catalog-api/products", []Schema{{func(jsonBody any) any { return jsonBody }, "schemas/products-request-schema.json"}}}
var categoriesMessageType = MessageType{"POST", "/function/product-catalog-api/categories", []Schema{}}
var buildProductMessageType = MessageType{"POST", "/function/product-catalog-builder/product", []Schema{{func(jsonBody any) any { return jsonBody }, "schemas/retail-stream-schema-ingress.json"}, {func(jsonBody any) any { return jsonBody.(map[string]any)["data"] }, "schemas/product-create-schema.json"}}}
var productImageMessageType = MessageType{"POST", "/function/product-catalog-builder/image", []Schema{{func(jsonBody any) any { return jsonBody }, "schemas/retail-stream-schema-ingress.json"}, {func(jsonBody any) any { return jsonBody.(map[string]any)["data"] }, "schemas/product-image-schema.json"}}}
var productPurchaseMessageType = MessageType{"POST", "/function/product-purchase", []Schema{{func(jsonBody any) any { return jsonBody }, "schemas/product-purchase-schema.json"}}}
var photographerRegisterMessageType = MessageType{"POST", "/function/product-photos-register", []Schema{{func(jsonBody any) any { return jsonBody }, "schemas/retail-stream-schema-ingress.json"}, {func(jsonBody any) any { return jsonBody.(map[string]any)["data"] }, "schemas/user-update-phone-schema.json"}}}
var photoRequestMessageType = MessageType{"POST", "/function/product-photos/request", []Schema{{func(jsonBody any) any { return jsonBody }, "schemas/retail-stream-schema-ingress.json"}, {func(jsonBody any) any { return jsonBody.(map[string]any)["data"] }, "schemas/photo-request-schema.json"}}}
var photoAssignmentMessageType = MessageType{"POST", "/function/product-photos/photos", []Schema{{func(jsonBody any) any { return jsonBody }, "schemas/photo-assignment-schema.json"}}}

var messageTypes = []MessageType{
	initMessageType,
	productsMessageType,
	categoriesMessageType,
	buildProductMessageType,
	productImageMessageType,
	productPurchaseMessageType,
	photographerRegisterMessageType,
	photoRequestMessageType,
	photoAssignmentMessageType,
}

func (m *MessageType) MatchRequest(method string, uri string) bool {
	return method == m.Method && uri == m.Uri
}

func (m *MessageType) ValidateSchemas(body []byte) bool {
	var jsonBody any
	if len(m.Schemas) == 0 && len(body) == 0 {
		return true
	}
	if err := json.Unmarshal(body, &jsonBody); err != nil {
		return false
	}
	for _, schema := range m.Schemas {
		jsonFragment := schema.JsonGetter(jsonBody)
		if err := ValidateJSONSchema(jsonFragment, schema.JsonSchemaFilename); err != nil {
			log.Println(err)
			return false
		}
	}

	return true
}

func ValidateJSONSchema(jsonFragment any, jsonSchemaFilename string) error {
	sch, err := jsonschema.Compile(jsonSchemaFilename)
	if err != nil {
		return err
	}
	if err = sch.Validate(jsonFragment); err != nil {
		return err
	}
	return nil
}
