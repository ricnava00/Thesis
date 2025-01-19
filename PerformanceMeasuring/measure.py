import argparse
import json
import os
import random
import shlex
import subprocess
import time
import signal
import logging
import select


# https://stackoverflow.com/a/56944256/23244567
class CustomFormatter(logging.Formatter):
    bold = "\x1b[1m"
    grey = "\x1b[38m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    light_red = "\x1b[91m"
    reset = "\x1b[0m"
    format = "%(asctime)s.%(msecs)03d - %(levelname)s: %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: bold + yellow + format + reset,
        logging.ERROR: bold + red + format + reset,
        logging.CRITICAL: bold + light_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%H:%M:%S")
        return formatter.format(record)


log = logging.getLogger()
log.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(CustomFormatter())
log.addHandler(ch)
#

parser = argparse.ArgumentParser()
parser.add_argument('-o', '--output', help='Output filename', required=True)
parser.add_argument('-s', '--server-address', help='Enable TLMSP, and use the specified ucl file', required=True)
parser.add_argument('-a', '--auth-token', help='Google OAuth2 token', required=True)
parser.add_argument('--tlmsp', metavar="UCL_PATH", help='Enable TLMSP, and use the specified ucl file', type=argparse.FileType('r'))
parser.add_argument('--go', metavar="CLIENT_PATH", help='Use the specified go client instead of curl', type=argparse.FileType('r'))
parser.add_argument('-t', '--time', help='Duration of the test in seconds', type=int)
parser.add_argument('-r', '--requests', help='Number of requests to send', type=int)
parser.add_argument('-e', '--continue-on-error', help='Continue on error', action='store_true')

try:
    with open("requestsNew.json") as f:
        requests = json.load(f)
except FileNotFoundError:
    log.error("requestsNew.json not found")
    exit(1)
except json.decoder.JSONDecodeError as e:
    log.error("JSONDecodeError: " + str(e))
    exit(1)

args = parser.parse_args()
if args.go and args.tlmsp:
    log.error("Cannot use go client with TLMSP")
    exit(1)

if args.time and args.requests:
    log.error("Cannot specify both time and requests")
    exit(1)

if not args.time and not args.requests:
    args.time = 60

try:
    with open(args.output, 'a'):
        pass
    if os.stat(args.output).st_size == 0:
        os.remove(args.output)
except FileNotFoundError:
    log.error(f"File {args.output} cannot be created")
    exit(1)

fail_with_body_supported = False
if not args.go and not args.tlmsp:
    output = subprocess.run(['curl', '--version'], stdout=subprocess.PIPE).stdout.decode('utf-8')
    curl_version = output.split('\n')[0].split(' ')[1]
    is_tlmsp = "TLMSP" in curl_version
    curl_version = tuple(map(int, curl_version.split('-')[0].split('.')))
    fail_with_body_supported = curl_version >= (7, 76, 0)
    if not fail_with_body_supported:
        log.warning("Your curl version does not support --fail-with-body, in case of error the response body will not be printed.\n" +
                    ("Consider removing tlmsp from your path to use the default curl (remember to also reset LD_LIBRARY_PATH)" if is_tlmsp
                     else "Consider updating your curl version to 7.76.0 or later"))

command = 'loop=' + str(random.randint(1000, 9999) * 1000) + '\n' \
          'date +%s%N\n' \
          'while true; do\n' \
          'let loop++\n'
for r in requests:
    data = r["post_data"]
    # replace {} with loop number, escape the rest
    data = map(shlex.quote, data.split("{}"))
    data = "${loop}".join(data)
    curl = (shlex.quote(os.path.abspath(args.go.name)) + ' --time ' if args.go else 'curl --fail'+('-with-body' if fail_with_body_supported else '')+' --insecure --silent -w \'%{time_total}\n\' ') + '--output /dev/null ' + ('--tlmsp ' + shlex.quote(args.tlmsp.name) + ' ' if args.tlmsp else '') + '-H "X-Testing: 1" -H "Authorization: Bearer ' + shlex.quote(args.auth_token) + '" -H "Content-Type: application/json" --data ' + data + ' ' + args.server_address.rstrip('/') + '/function/' + r["path"]
    command += curl + '\n'
    command += 'returnCode=$?\n'
    command += 'if [ $returnCode -ne 0 ]; then\n'
    command += '  echo >&2 \n'
    command += '  echo -e "\\e[1;31mFailed\\e[0m (escaped): " >&2 \n'
    command += '  echo ' + shlex.quote(curl) + ' >&2 \n'
    command += '  echo >&2 \n'
    command += '  echo -e "\\e[1;31mFailed\\e[0m (unescaped): " >&2 \n'
    command += '  echo ' + curl + ' >&2 \n'
    command += '  echo >&2 \n'
    if not args.continue_on_error:
        command += 'exit 1\n'
    command += 'fi\n'
    command += 'echo -n "$returnCode "; date +%s%N\n'
command += 'done'
# print(command)
process = subprocess.Popen(command, shell=True, executable="/bin/bash", stdout=subprocess.PIPE, preexec_fn=os.setsid)
def stop_process(*args):
    if process.poll() is None:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
signal.signal(signal.SIGINT,stop_process)
max_latency_ms = 90
results = []
old_timestamp = None
total = 0
failed = 0
start = time.time()
last_print_time = 0
line_type = 0
poll_obj = select.poll()
poll_obj.register(process.stdout, select.POLLIN)
while True:
    if process.poll() is not None:
        log.error("Subprocess exited before timeout")
        exit(1)
    if poll_obj.poll(0):
        line = process.stdout.readline().decode('utf-8')
        if old_timestamp is None:
            old_timestamp = int(line)
            continue
        if line_type == 0:
            request_latency = float(line.replace(",", "."))
            if request_latency * 1000 > max_latency_ms:
                log.info(f"\033[1;33mRequest {total + 1} (type {(total % len(requests)) + 1}) took {round(request_latency * 1000, 1)}ms\033[0m\033[K")
        elif line_type == 1:
            code, timestamp = line.split()
            total_latency = (int(timestamp) - old_timestamp) / 1000000000
            old_timestamp = int(timestamp)
            fail = code != "0"
            total += 1
            if fail:
                failed += 1
            results.append({"fail": fail, "total_latency": total_latency, "request_latency": request_latency})
        line_type = (line_type + 1) % 2
    else:
        time.sleep(0.001)
    if old_timestamp is not None and time.time() - old_timestamp / 1000000000 >= 5:
        log.error("More than 5 seconds passed from last successful request, aborting")
        stop_process()
        exit(1)
    if (args.time and time.time() - start >= args.time) or (args.requests and total >= args.requests):
        stop_process()
        break
    if time.time() - last_print_time > 1:
        print(f"Total requests: {total}, failed: {failed}, time elapsed: {round(time.time() - start, 1)}s", end='\r')
        last_print_time = time.time()
print(f"Total requests: {total}, failed: {failed}, time elapsed: {round(time.time() - start, 1)}s")

if failed != 0:
    log.warning("\033[1;33mSome errors present in requests, results may be inaccurate\033[0m")
json.dump(results, open(args.output, 'w'))
