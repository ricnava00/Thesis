import argparse
from enum import Enum
import json
import os
import re

DEBUG = False

class Columns(Enum):
    TOTAL_REQUEST_RESPONSE_HANDSHAKE_TTFB_TTC = "Total (request+response+handshake+ttfb+ttc)"
    HANDSHAKE = "Handshake"
    TOTAL_REQUEST = "Total (request)"
    TOTAL_RESPONSE = "Total (response)"
    TLMSP_MB_TO_HANDLER_REQUEST = "tlmsp-mb -> handler (request)"
    TLMSP_MB_TO_HANDLER_RESPONSE = "tlmsp-mb -> handler  (response)"
    HANDLER_TO_LISTENER_REQUEST = "handler -> listener (request)"
    HANDLER_TO_LISTENER_RESPONSE = "handler -> listener (response)"
    LISTENER_TOTAL_REQUEST = "Listener total (request)"
    LISTENER_TOTAL_RESPONSE = "Listener total (response)"
    PROCESS_REQUEST = "processRequest"
    PROCESS_RESPONSE = "processResponse"
    HANDLER_TOTAL = "Handler total"
    SERVER_TOTAL = "Server total"
    TIME_TO_FIRST_BYTE = "Time to first byte"
    TIME_TO_CLOSE = "Time to close"

tlmsp_strings = [
    ["(client-side): Local  address is", Columns.HANDSHAKE, Columns.TOTAL_REQUEST_RESPONSE_HANDSHAKE_TTFB_TTC],
    ["(server-side): Handshake complete", Columns.HANDSHAKE, Columns.TIME_TO_FIRST_BYTE],
    ["(client-side): Received container (length=", Columns.TOTAL_REQUEST, Columns.TIME_TO_FIRST_BYTE],
    ["(server-side): Running handler './client {} 2>> stderr.txt'", Columns.TLMSP_MB_TO_HANDLER_REQUEST],
    ["(server-side): Client started", Columns.HANDLER_TO_LISTENER_REQUEST],
    ["(server-side): Listener started", Columns.LISTENER_TOTAL_REQUEST],
    ["(server-side): processRequest started", Columns.PROCESS_REQUEST],
    ["(server-side): processRequest finished", Columns.PROCESS_REQUEST],
    ["(server-side): Listener finished", Columns.LISTENER_TOTAL_REQUEST],
    ["(server-side): Client finished", Columns.HANDLER_TO_LISTENER_REQUEST],
    ["(server-side): Handler exited with status code 0", Columns.TLMSP_MB_TO_HANDLER_REQUEST],
    ["(server-side): Sending container (length=", Columns.TOTAL_REQUEST, Columns.SERVER_TOTAL],
    ["(server-side): Received container (length=", Columns.TOTAL_RESPONSE, Columns.SERVER_TOTAL],
    ["(client-side): Running handler './client {} 2>> stderr.txt'", Columns.TLMSP_MB_TO_HANDLER_RESPONSE],
    ["(client-side): Client started", Columns.HANDLER_TO_LISTENER_RESPONSE],
    ["(client-side): Listener started", Columns.LISTENER_TOTAL_RESPONSE],
    ["(client-side): processResponse started", Columns.PROCESS_RESPONSE],
    ["(client-side): processResponse finished", Columns.PROCESS_RESPONSE],
    ["(client-side): Listener finished", Columns.LISTENER_TOTAL_RESPONSE],
    ["(client-side): Client finished", Columns.HANDLER_TO_LISTENER_RESPONSE],
    ["(client-side): Handler exited with status code 0", Columns.TLMSP_MB_TO_HANDLER_RESPONSE],
    ["(client-side): Sending container (length=", Columns.TOTAL_RESPONSE, Columns.TIME_TO_CLOSE],
    ["(server-side): Closing", Columns.TOTAL_REQUEST_RESPONSE_HANDSHAKE_TTFB_TTC, Columns.TIME_TO_CLOSE]
]

dc_strings = [
    ["(both-side): Handler started", Columns.HANDLER_TOTAL],
    ["(server-side): processRequest started", Columns.PROCESS_REQUEST],
    ["(server-side): processRequest finished", Columns.PROCESS_REQUEST],
    ["(client-side): processResponse started", Columns.PROCESS_RESPONSE],
    ["(client-side): processResponse started", Columns.PROCESS_RESPONSE],
    ["(both-side): Handler finished", Columns.HANDLER_TOTAL]
]

tlmsp_types = set(sum([ n[1:] for n in tlmsp_strings], []))
dc_types = set(sum([ n[1:] for n in dc_strings], []))

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


try:
    with open("requests.json") as f:
        requests = json.load(f)
except FileNotFoundError:
    print("requests.json not found")
    exit(1)
except json.decoder.JSONDecodeError as e:
    print("JSONDecodeError: " + str(e))
    exit(1)

parser = argparse.ArgumentParser()
parser.add_argument("input_file", nargs='+', help="Input result file")

args = parser.parse_args()

all_results = []
tlmsp = dict()
dc = dict()
for filename in args.input_file:
    if not os.path.exists(filename+".mb.log"):
        print(f"File {filename}.mb.log not found")
        exit(1)
    if (os.path.exists(filename+".mb_listener.log") or os.path.exists(filename+".client_listener.log")) and (not os.path.exists(filename+".mb_listener.log") or not os.path.exists(filename+".client_listener.log")):
        print(f"Only one TLMSP log found for {filename}, expected 2 or 0")
        exit(1)
    lines = []
    with open(filename+".mb.log") as f:
        lines = f.readlines()
    if os.path.exists(filename+".mb_listener.log"):
        lines += open(filename+".mb_listener.log").readlines()
        lines += open(filename+".client_listener.log").readlines()
    #filter timestamps in format 1736802002424097230 + ...
    lines = [line for line in lines if re.match(r"\d{19}\s", line)]
    lines.sort()
    if os.path.exists(filename+".mb_listener.log"):
        tlmsp[filename] = lines
    else:
        dc[filename] = lines
        # print("".join(lines))
        # exit(0)

if len(tlmsp) and len(dc):
    print("\033[93mBoth TLMSP and DC logs found. They will be kept separate, but the main idea of this script is to merge logs of the same type, not to compare different types.\033[0m")

def get_timestamps(files, strings):
    splice = -1
    strings_index = 0
    temp_timestamps = dict()
    timestamps = dict()
    for filename, lines in files.items():
        for line in lines:
            if splice == -1:
                match = re.match("(\d+).*splice (\d+) "+re.escape(strings[strings_index][0]), line)
            else:
                match = re.match("(\d+).*splice ("+str(splice)+") "+re.escape(strings[strings_index][0]), line)
            if match:
                if DEBUG:
                    print(round(int(match.group(1))/1e6%10000, 2), match.group(0))
                if splice == -1:
                    splice = int(match.group(2))
                    if splice != 0:
                        print(f"Warning: {filename} started at splice {splice}")
                for index in strings[strings_index][1:]:
                    if index not in temp_timestamps:
                        temp_timestamps[index] = int(match.group(1))
                        if DEBUG:
                            print(f"{index} -> {round(int(match.group(1))/1e6%10000, 2)}")
                    else:
                        timestamps[splice] = dict() if splice not in timestamps else timestamps[splice]
                        timestamps[splice][index] = int(match.group(1)) - temp_timestamps[index]
                        if DEBUG:
                            print(f"{index} - {round(int(match.group(1))/1e6%10000, 2)} = {round(timestamps[splice][index]/1e6, 2)}")
                strings_index = (strings_index + 1) % len(strings)
                if strings_index == 0:
                    splice += 1
                    temp_timestamps = dict()
                    if DEBUG:
                        print(timestamps)
                        exit(0)
                # print(f"Matched {filename} at match {strings_index} with splice {splice}")
    return timestamps

tlmsp_timestamps = get_timestamps(tlmsp, tlmsp_strings)
dc_timestamps = get_timestamps(dc, dc_strings)

def get_avg_timestamps(timestamps):
    avg_timestamps = dict()
    for _, values in timestamps.items():
        for index, value in values.items():
            avg_timestamps[index] = value if index not in avg_timestamps else avg_timestamps[index] + value
    for index in avg_timestamps:
        avg_timestamps[index] /= len(timestamps)
    return avg_timestamps

avg_tlmsp_timestamps = get_avg_timestamps(tlmsp_timestamps)
avg_dc_timestamps = get_avg_timestamps(dc_timestamps)

if len(avg_tlmsp_timestamps) and len(avg_dc_timestamps):
    print("TLMSP:")

for column in Columns:
    if column in avg_tlmsp_timestamps:
        print(f"{column.value}: {round(avg_tlmsp_timestamps[column]/1e6, 2)}ms")

if len(avg_tlmsp_timestamps) and len(avg_dc_timestamps):
    print("\nDC:")

for column in Columns:
    if column in avg_dc_timestamps:
        print(f"{column.value}: {round(avg_dc_timestamps[column]/1e6, 2)}ms")