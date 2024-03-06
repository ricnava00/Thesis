import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("input_file", nargs='+', type=argparse.FileType('r'), help="Input result file")
parser.add_argument('-o', '--output', help='Output result file', required=True)

args = parser.parse_args()

if len(args.input_file) < 1:
    print("At least two input files are required")
    sys.exit(1)

results = []
for f in args.input_file:
    try:
        results.append(json.load(f))
    except json.decoder.JSONDecodeError as e:
        print("JSONDecodeError: " + str(e))
        sys.exit(1)

results = [item for sublist in results for item in sublist]
with open(args.output, 'w') as f:
    json.dump(results, f)