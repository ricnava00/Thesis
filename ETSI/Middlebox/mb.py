import os
import pickle
import re
import sys
from pprint import pprint
import requests
from typing import Type, Callable
from MessageTypes import *
from jwtParser import *


class Message:
    def __init__(self, connection_id: int, type: Type[MessageType], data: object, response_code: int):
        self.connection_id = connection_id
        self.type = type
        self.data = data
        self.response_code = response_code

    def __repr__(self):
        return f'(connection_id={self.connection_id}, type={self.type}, data={self.data}, response_code={self.response_code})'


class Transition:
    pass


class State:
    def __init__(self, transitions=None):
        if transitions is None:
            transitions = []
        self.transitions = transitions


def init_transition(self, to_state: State, execute: Callable[[], bool]):
    self.to_state = to_state
    self.verify = execute


Transition.__init__ = init_transition

init = State()
has = State()

states = [
    State([Transition(0, lambda *_: True)])
]


def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def main():
    session = {}
    if os.path.isfile("session.dat"):
        session = pickle.load(open("session.dat", "rb"))
    waiting_bodies = {}
    if os.path.isfile("waiting.dat"):
        waiting_bodies = pickle.load(open("waiting.dat", "rb"))
    connection_id = int(sys.argv[1])
    splice_id = int(sys.argv[2])
    is_response = bool(int(sys.argv[3]))
    print(f"{connection_id} {splice_id} {is_response}")
    log(f"{connection_id} {splice_id} {is_response}")
    input_data = sys.stdin.read()
    if input_data is None:
        return
    print("\033[1;2m" + input_data + "\033[0m")
    if connection_id in waiting_bodies:
        body = input_data
        match_groups, headers, old_body = waiting_bodies[connection_id]
        body = old_body + body
        if not is_response:
            method, uri, http_version = match_groups
        else:
            http_version, response_code = match_groups
    else:
        header, body = input_data.split("\r\n\r\n", 1)
        tmp = header.split("\r\n")
        req = tmp.pop(0)

        if not is_response:
            match = re.match(r"(GET|POST|HEAD|PUT|DELETE) ([^ ]+) HTTP/(\d+(?:\.\d+)?)", req)
            if not match:
                print("Invalid request")
                sys.exit(1)
            method, uri, http_version = match.groups()
        else:
            match = re.match(r"HTTP/(\d+(?:\.\d+)?) (\d+)", req)
            if not match:
                print("Invalid response")
                sys.exit(1)
            http_version, response_code = match.groups()
        match_groups = match.groups()

        headers = {line.split(": ")[0]: line.split(": ", 1)[1] for line in tmp}

    if len(body) < int(headers.get("Content-Length", 0)):
        print("Waiting for body for connection " + str(connection_id))
        waiting_bodies[connection_id] = match_groups, headers, body
        print(waiting_bodies)
        pickle.dump(waiting_bodies, open("waiting.dat", "wb"))
        sys.exit(0)
    elif connection_id in waiting_bodies:
        del waiting_bodies[connection_id]
        pickle.dump(waiting_bodies, open("waiting.dat", "wb"))

    if not is_response:
        print(f"method: {method}, uri: {uri}, http_version: {http_version}")

        user = "Unknown"
        if "Authorization" in headers:
            try:
                id_token = headers["Authorization"]
                if id_token.startswith("Bearer "):
                    id_token = headers["Authorization"][7:]
                user = parse_jwt(id_token)["email"]
            except Exception as e:
                print("\033[1;33mCouldn't get email from token: " + str(e) + "\033[0m")
        else:
            print("\033[33mNo auth token in request\033[0m")

        message_type = None
        message_data = None

        user_session_tmp = session.get(user, {"messages": [], "created_products": [], "has_seen_products": False})  # To keep the session list clean, initialize a new session now but save it later only if there's a match
        for test_message_type in MessageType.__subclasses__():
            if test_message_type.match_request(method, uri, headers, body):
                message_type = test_message_type
                user_session_tmp, message_data = test_message_type.parse_request(user_session_tmp, method, uri, headers, body)
                if (validation_error := test_message_type.validate_request(user_session_tmp, message_data)) is not None:
                    print("\033[1;33mValidation error: " + validation_error + "\033[0m")
                break

        if message_type is None:
            print("\033[1;31mNo match\033[0m")
        else:
            session[user] = user_session_tmp
            session[user]["messages"].append(Message(connection_id, message_type, message_data, 0))
    else:
        response_code = int(response_code)
        indexes = []
        for user, user_session in session.items():
            indexes += [(idx, user) for idx, message in enumerate(user_session["messages"]) if message.connection_id == connection_id]
        if len(indexes) != 1:
            print(f"\033[1;31mFound {len(indexes)} messages with connection_id {connection_id}\033[0m")
        else:
            index, user = indexes[0]
            message_type = session[user]["messages"][index].type
            if session[user]["messages"][index].data is not None and session[user]["messages"][index].data.get("invalid", False):
                print("\033[1;33mResponse is relative to an invalid message, not parsing\033[0m")
                pass
            else:
                session[user], session[user]["messages"][index].data = message_type.parse_response(session[user], session[user]["messages"][index].data, response_code, body)
            session[user]["messages"][index].response_code = response_code

    pprint(session)
    pickle.dump(session, open("session.dat", "wb"))


if __name__ == "__main__":
    main()
