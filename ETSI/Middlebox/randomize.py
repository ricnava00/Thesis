import math
import os
import pickle
import re
import time
import hashlib
from dataclasses import dataclass
from pprint import pprint
from typing import Type
from MessageTypes import *
from jwtParser import parse_jwt

print_graph_and_exit = False

CODE_EXPIRATION_SECONDS = 600


class Message:
    def __init__(self, connection_id: int, type: Type[MessageType], valid: bool, response_code: int):
        self.connection_id = connection_id
        self.type = type
        self.valid = valid
        self.response_code = response_code

    def __repr__(self):
        return f'(connection_id={self.connection_id}, type={self.type}, valid={self.valid}, response_code={self.response_code})'


@dataclass
class Transition:
    to_state: int
    message_type: Type[MessageType]


@dataclass
class State:
    transitions: list[Transition]


# testing fsm looping through all states (the weird order is to stay consistent with the numbering of the production graph)
# states = [
#     State([Transition(1, InitMessageType)]),
#     State([Transition(4, BuildProductMessageType)]),
#     State([Transition(3, CategoriesMessageType)]),
#     State([Transition(6, ProductPurchaseMessageType)]),
#     State([Transition(5, ProductImageMessageType)]),
#     State([Transition(2, ProductsMessageType)]),
#     State([Transition(7, PhotographerRegisterMessageType)]),
#     State([Transition(8, PhotoRequestMessageType)]),
#     State([Transition(0, PhotoAssignmentMessageType)]),
# ]

# testing fsm looping through all states (no weird order)
states = [
    State([Transition(1, InitMessageType)]),
    State([Transition(2, BuildProductMessageType)]),
    State([Transition(3, ProductImageMessageType)]),
    State([Transition(4, ProductsMessageType)]),
    State([Transition(5, CategoriesMessageType)]),
    State([Transition(6, ProductPurchaseMessageType)]),
    State([Transition(7, PhotographerRegisterMessageType)]),
    State([Transition(8, PhotoRequestMessageType)]),
    State([Transition(0, PhotoAssignmentMessageType)]),
]

# possible fsm in production
# states = [
#     State([Transition(1, InitMessageType)]),
#     State([Transition(2, ProductsMessageType),
#            Transition(3, CategoriesMessageType),
#            Transition(4, BuildProductMessageType),
#            Transition(7, PhotographerRegisterMessageType)]
#           ),
#     State([Transition(6, ProductPurchaseMessageType)]
#           ),
#     State([Transition(2, ProductsMessageType),
#            Transition(4, BuildProductMessageType)]
#           ),
#     State([Transition(5, ProductImageMessageType),
#            Transition(8, PhotoRequestMessageType)]
#           ),
#     State([Transition(2, ProductsMessageType),
#            Transition(3, CategoriesMessageType),
#            Transition(4, BuildProductMessageType),
#            Transition(7, PhotographerRegisterMessageType)]
#           ),
#     State([Transition(2, ProductsMessageType),
#            Transition(3, CategoriesMessageType),
#            Transition(4, BuildProductMessageType),
#            Transition(6, ProductPurchaseMessageType),
#            Transition(7, PhotographerRegisterMessageType)]
#           ),
#     State([Transition(9, PhotoAssignmentMessageType)]
#           ),
#     State([Transition(2, ProductsMessageType),
#            Transition(3, CategoriesMessageType),
#            Transition(4, BuildProductMessageType),
#            Transition(7, PhotographerRegisterMessageType)]
#           ),
#     State([Transition(9, PhotoAssignmentMessageType)]
#           )
# ]

if 'print_graph_and_exit' in globals() and print_graph_and_exit:
    import networkx as nx
    from matplotlib import pyplot as plt, patches as mpatches, colors as mcolors

    plt.rcParams.update({'font.size': 20})
    plt.rcParams.update({'font.family': 'serif'})
    # comment to print without LaTeX installed
    plt.rcParams.update({'text.usetex': True})

    colors = list(mcolors.TABLEAU_COLORS.values())
    if len(colors) < len(states):
        new_colors = []
        loops = math.ceil(len(states) / len(colors))
        for i in range(loops - 1):
            for color in colors:
                hsv = mcolors.rgb_to_hsv(mcolors.to_rgb(color))
                hsv[2] *= (loops - i - 1) / loops
                new_colors.append(mcolors.hsv_to_rgb(hsv))
        colors += new_colors
    colors = {mt: colors[i] for i, mt in enumerate(MessageType.__subclasses__())}

    G = nx.DiGraph()
    for i in range(len(states)):
        G.add_node(i)
    for i in range(len(states)):
        for transition in states[i].transitions:
            G.add_edge(i, transition.to_state, color=colors[transition.message_type])
    pos = nx.circular_layout(G.subgraph(range(1, len(states))))
    pos = {k: (-x, y) for k, (x, y) in pos.items()}
    pos[0] = (min([x for x, _ in pos.values()]) - 0.5, 0)
    # pos = nx.circular_layout(G)
    # pos = {k: (-x, y) for k, (x, y) in pos.items()}
    nx.draw_networkx_nodes(G, pos, node_size=700, node_color="white", edgecolors="black")
    nx.draw_networkx_labels(G, pos, font_size=24)
    edge_colors = [edgedata["color"] for _, _, edgedata in G.edges(data=True)]
    nx.draw_networkx_edges(G, pos, edgelist=G.edges(), edge_color=edge_colors, arrows=True, node_size=700, connectionstyle='arc3, rad = 0.02')
    patches = [mpatches.Patch(color=color, label=mt.url.removeprefix("/function/")) for mt, color in colors.items()]
    plt.legend(handles=patches, loc="upper left", bbox_to_anchor=(1, 1), borderaxespad=0)
    plt.axis('off')
    plt.savefig("graph.pdf", dpi=300, bbox_inches="tight")
    sys.exit(0)


def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def plog(*args, **kwargs):
    pprint(*args, stream=sys.stderr, **kwargs)


def generate_code():
    return os.urandom(8).hex()


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
    input_data = sys.stdin.read()
    if input_data is None:
        return
    log("\033[1;2m" + input_data + "\033[0m")
    if connection_id in waiting_bodies:
        body = input_data
        match_groups, headers, old_body, old_header = waiting_bodies[connection_id]
        input_data = old_header + "\r\n\r\n" + old_body + input_data
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
                log("Invalid request")
                sys.exit(1)
            method, uri, http_version = match.groups()
        else:
            match = re.match(r"HTTP/(\d+(?:\.\d+)?) (\d+)", req)
            if not match:
                log("Invalid response")
                sys.exit(1)
            http_version, response_code = match.groups()
        match_groups = match.groups()

        headers = {line.split(": ")[0].title(): line.split(": ", 1)[1] for line in tmp}

    if not is_response and len(body) < int(headers.get("Content-Length", 0)):
        log("Waiting for body for connection " + str(connection_id))
        waiting_bodies[connection_id] = match_groups, headers, body, header
        log(waiting_bodies)
        pickle.dump(waiting_bodies, open("waiting.dat", "wb"))
        sys.exit(0)
    elif connection_id in waiting_bodies:
        del waiting_bodies[connection_id]
        pickle.dump(waiting_bodies, open("waiting.dat", "wb"))

    if not is_response:
        log(f"method: {method}, uri: {uri}, http_version: {http_version}")

        user = "Unknown"
        if "Authorization" in headers:
            try:
                id_token = headers["Authorization"]
                if id_token.startswith("Bearer "):
                    id_token = headers["Authorization"][7:]
                user = parse_jwt(id_token)["email"]
            except Exception as e:
                log("\033[1;33mCouldn't get email from token: " + str(e) + "\033[0m")
        else:
            log("\033[33mNo auth token in request\033[0m")

        message_type = None
        message_data = None

        user_session_tmp = session.get(user, {"messages": [], "state": 0, "codes": {}})  # To keep the session list clean, initialize a new session now but save it later only if there's a match
        for n, code in list(user_session_tmp["codes"].items()):
            if code["expiration"] < time.time():
                del user_session_tmp["codes"][n]
        code = headers.get("X-Code", None)
        for test_message_type in (t.message_type for t in states[user_session_tmp["state"]].transitions):
            if test_message_type.match_request(method, uri, headers, body):
                message_type = test_message_type
                valid = True
                if not (MessageType.validate_schemas(message_type, body)):
                    log("\033[1;33mRequest not matching schema\033[0m")
                    valid = False
                elif not (message_type in user_session_tmp["codes"] and user_session_tmp["codes"][message_type]["code"] == code or test_message_type == InitMessageType or "X-Testing" in headers):
                    log("\033[1;33mInvalid code\033[0m")
                    valid = False
                break
        if message_type is None:  # Gave precedence to valid messages, now check for invalid ones
            for test_message_type in MessageType.__subclasses__():
                if test_message_type.match_request(method, uri, headers, body):
                    log("\033[1;33mMessage type not allowed in this state\033[0m")
                    message_type = test_message_type
                    valid = False
                    break

        if message_type is None:
            log("\033[1;31mNo match\033[0m")
            sys.exit(1)
        else:
            session[user] = user_session_tmp
            session[user]["messages"].append(Message(connection_id, message_type, valid, 0))
            if not valid:
                sys.exit(1)
            print(input_data, end="")
            log(f"\033[36m{input_data}\033[0m")
    else:
        response_code = int(response_code)
        # retries = 0
        # while True:
        #     indexes = []
        #     for user, user_session in session.items():
        #         indexes += [(idx, user) for idx, message in enumerate(user_session["messages"]) if message.connection_id == connection_id]
        #     if len(indexes) == 0:
        #         if retries == 0:
        #             log(f"\033[1;33mFound no messages with connection_id {connection_id}, retrying\033[0m")  # Since the script is called asynchronously, it's possible that the message hasn't been added to the session yet
        #         elif retries == 100:
        #             log(f"\033[1;31mFound no messages with connection_id {connection_id}, giving up\033[0m")
        #             break
        #         retries += 1
        #         time.sleep(0.01)
        #         if os.path.isfile("session.dat"):
        #             session = pickle.load(open("session.dat", "rb"))
        #     else:
        #         break
        indexes = []
        for user, user_session in session.items():
            indexes += [(idx, user) for idx, message in enumerate(user_session["messages"]) if message.connection_id == connection_id]
        if len(indexes) != 1:
            log(f"\033[1;31mFound {len(indexes)} messages with connection_id {connection_id}\033[0m")
        else:
            index, user = indexes[0]
            if not session[user]["messages"][index].valid:  # Legacy, the middlebox doesn't forward invalid messages anymore
                log("\033[1;31mResponse is relative to an invalid message\033[0m")
            else:
                message_type = session[user]["messages"][index].type
                if response_code == 200:
                    session[user]["state"] = [t.to_state for t in states[session[user]["state"]].transitions if t.message_type == message_type][0]
                    session[user]["codes"] = {mt.message_type: {"code": generate_code(), "expiration": time.time() + CODE_EXPIRATION_SECONDS} for mt in states[session[user]["state"]].transitions}
                    log(session[user]["codes"])
                    response = f"HTTP/{http_version} {response_code}\n"
                    for k, v in headers.items():
                        response += f"{k}: {v}\n"
                    for k, v in session[user]["codes"].items():
                        response += f"X-Code-{hashlib.md5(k.url.encode('utf-8')).hexdigest()}: {v['code']}\n"
                    response += "\n"
                    print(response, end="")
                    log(f"\033[36m{response}\033[0m")
                else:
                    log(f"\033[1;31mResponse code {response_code}, forwarding\033[0m")
                    print(input_data, end="")

            session[user]["messages"][index].response_code = response_code

    plog(session)
    pickle.dump(session, open("session.dat", "wb"))


if __name__ == "__main__":
    main()
