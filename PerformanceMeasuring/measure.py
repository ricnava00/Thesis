import argparse
import json
import os
import random
import shlex
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('-o', '--output', type=argparse.FileType('w'), help='Output filename', required=True)
parser.add_argument('-s', '--server-address', help='Enable TLMSP, and use the specified ucl file', required=True)
parser.add_argument('-a', '--auth-token', help='Google OAuth2 token', required=True)
parser.add_argument('--tlmsp', metavar="UCL_PATH", help='Enable TLMSP, and use the specified ucl file')
parser.add_argument('--go', help='Use go client instead of curl', action='store_true')
parser.add_argument('-t', '--time', default=60, help='Duration of the test in seconds')

try:
    with open("requests.json") as f:
        requests = json.load(f)
except FileNotFoundError:
    print("requests.json not found")
    exit(1)
except json.decoder.JSONDecodeError as e:
    print("JSONDecodeError: " + str(e))
    exit(1)

args = parser.parse_args()
if args.go and args.tlmsp:
    print("ERROR: Cannot use go client with TLMSP")
    exit(1)

if args.go:
    if not os.path.isfile("client"):
        print("ERROR: Go client not found, run this script in the shared folder or run `go build client.go` in the middlebox VM")
        exit(1)

command = 'total=0\n' \
          'failed=0\n' \
          'loop=' + str(random.randint(1000, 9999)*1000) + '\n' \
          'echo -n "$total $failed "; date +%s%N\n' \
          'while true; do\n' \
          'let loop++\n'
for r in requests:
    data = r["post_data"]
    # replace {} with loop number, escape the rest
    data = map(shlex.quote, data.split("{}"))
    data = "${loop}".join(data)
    curl = ('./client ' if args.go else 'curl --fail --insecure --silent ') + '--output /dev/null ' + ('--tlmsp ' + shlex.quote(args.tlmsp) + ' ' if args.tlmsp else '') + '-H "X-Testing: 1" -H "Authorization: Bearer ' + shlex.quote(args.auth_token) + '" -H "Content-Type: application/json" --data ' + data + ' ' + args.server_address.rstrip('/') + '/function/' + r["path"]
    command += curl + '\n'
    command += 'if [ $? -ne 0 ]; then\n'
    command += 'let failed++\n'
    command += 'echo "Failed: " >&2 \n'
    command += 'echo ' + shlex.quote(curl) + ' >&2 \n'
    command += 'echo >&2 \n'
    command += 'fi\n'
    command += 'let total++\n'
    command += 'echo -n "$total $failed "; date +%s%N\n'
command += 'done'
# print(command)
try:
    subprocess.check_output(command, timeout=int(args.time), shell=True, executable="/bin/bash")
    print("ERROR: Subprocess exited before timeout")
    exit(1)
except subprocess.TimeoutExpired as e:
    output = e
results = list(map(lambda line: {k: round(int(v) / 1000000, 1) if k == "timestamp" else int(v) for k, v in zip(["total", "fail", "timestamp"], line.split())}, output.stdout.decode('utf-8').strip().split('\n')))
if "timestamp" not in results[-1]:  # Could happen if the script times out while running date
    results = results[:-1]
total, fail, end_timestamp = results[-1].values()
print(f"Total requests: {total}, failed: {fail}")
if fail != 0:
    print("\033[1;33mSome errors present in requests, results may be inaccurate\033[0m")
json.dump(results, args.output)
