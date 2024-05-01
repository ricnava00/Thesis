import json
import os
import pickle
import re
import sys
import urllib.request

def log(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def main():
    waiting_bodies = {}
    if os.path.isfile("../Middlebox/waiting.dat"):
        waiting_bodies = pickle.load(open("../Middlebox/waiting.dat", "rb"))
    connection_id = int(sys.argv[1])
    splice_id = int(sys.argv[2])
    is_response = bool(int(sys.argv[3]))
    input_data = sys.stdin.read()
    if input_data is None:
        return
    log("\033[1;2m" + input_data + "\033[0m")
    if connection_id in waiting_bodies:
        body = input_data
        headers, old_body, old_header = waiting_bodies[connection_id]
        input_data = old_header + "\r\n\r\n" + old_body + input_data
        body = old_body + body
    else:
        header, body = input_data.split("\r\n\r\n", 1)
        tmp = header.split("\r\n")
        req = tmp.pop(0)

        if not is_response:
            match = re.match(r"(GET|POST|HEAD|PUT|DELETE) ([^ ]+) HTTP/(\d+(?:\.\d+)?)", req)
            if not match:
                log("Invalid request")
                sys.exit(1)
        else:
            match = re.match(r"HTTP/(\d+(?:\.\d+)?) (\d+)", req)
            if not match:
                log("Invalid response")
                sys.exit(1)

        headers = {line.split(": ")[0].title(): line.split(": ", 1)[1] for line in tmp}

    if not is_response and len(body) < int(headers.get("Content-Length", 0)):
        log("Waiting for body for connection " + str(connection_id))
        waiting_bodies[connection_id] = headers, body, header
        log(waiting_bodies)
        pickle.dump(waiting_bodies, open("../Middlebox/waiting.dat", "wb"))
        sys.exit(0)
    elif connection_id in waiting_bodies:
        del waiting_bodies[connection_id]
        pickle.dump(waiting_bodies, open("../Middlebox/waiting.dat", "wb"))

    try:
        out = json.loads(urllib.request.urlopen("http://localhost:8080", data=json.dumps({"connection_id": connection_id, "is_response": is_response, "data": input_data}).encode()).read().decode())
        log(out)
        if out["success"]:
            print(out["data"], end="")
            sys.exit(0)
        else:
            log("Invalid request/response")
    except json.decoder.JSONDecodeError:
        log("Remote error")
    sys.exit(1)



if __name__ == "__main__":
    main()
