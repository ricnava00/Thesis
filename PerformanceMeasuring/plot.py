import argparse
import json
import numpy as np
from matplotlib import pyplot as plt, patches as mpatches, colors as mcolors
from scipy.signal import savgol_filter
import pandas as pd

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


parser = argparse.ArgumentParser()
parser.add_argument("input_file", nargs='+', type=argparse.FileType('r'), help="Input result file")
parser.add_argument('-o', '--output', default='plot.png', help='Output filename')
parser.add_argument('-x', '--color_offset', type=int, default=0, help='Offset of label colors list')

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

all_results = []
for f in args.input_file:
    try:
        all_results.append(json.load(f))
    except json.decoder.JSONDecodeError as e:
        print("JSONDecodeError: " + str(e))
        exit(1)

colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

plt.rcParams.update({'font.size': 10})
# use same font as latex
plt.rcParams.update({'font.family': 'serif'})
plt.rcParams.update({'text.usetex': True})
bar_width = 1 / (len(args.input_file) + 1)
alpha = 0.3

labels = []
for n, file in enumerate(args.input_file):
    filename = file.name
    filename = filename[:filename.rfind('.')]
    color = colors[n + args.color_offset]
    labels.append((mpatches.Patch(color=color), filename))

table = "\\begin{tabular}{|l|c|c|c|c|}\n" + \
        "\\hline\n" + \
        " & ".join([f"\\textbf{{{label}}}" for label in ["Method", "Total", "Avg. RPS", "Avg. Latency", "Latency\\std dev."]]) + "\\\\\n" + \
        "\\hline\n"
for n, results in enumerate(all_results):
    premultiplied_color = np.array(mcolors.to_rgba(colors[n + args.color_offset])) * alpha + (1 - alpha)
    timestamps = [res["timestamp"] for res in results]
    results = results[1:]  # The first result is printed before starting and doesn't represent a completed request
    start_timestamp = timestamps[0]
    total, fail, end_timestamp = results[-1].values()
    filename = args.input_file[n].name
    filename = filename[:filename.rfind('.')]
    print(f"{filename}: \ttotal requests: {total}, failed: {fail}")
    if fail != 0:
        print("\033[1;33m" + filename + ": some errors present in requests, results may be inaccurate\033[0m")
    latencies = np.diff(timestamps)
    per_request_latencies = list(chunks(latencies, len(requests)))
    if len(per_request_latencies[-1]) != len(per_request_latencies[0]):  # Remove last loop if it was cut off by the timer
        per_request_latencies = per_request_latencies[:-1]
    average_per_request_latency = np.average(per_request_latencies, axis=0)
    requests_per_second = []
    for min_timestamp in np.arange(start_timestamp, end_timestamp, 1000):
        requests_per_second.append(len([res for res in results if min_timestamp <= res["timestamp"] < min_timestamp + 1000]))
    plt.figure(1)
    window_seconds = 10
    smoothed_requests_per_second = savgol_filter(requests_per_second, window_seconds, 2)
    plt.plot(smoothed_requests_per_second, label=filename, color=colors[n+args.color_offset])
    plt.plot(np.arange(len(requests_per_second)), [np.average(requests_per_second)] * len(requests_per_second), color=colors[n+args.color_offset], alpha=0.5, linewidth=1)
    plt.ylim(bottom=0, top=max(max(requests_per_second), plt.ylim()[1]))
    plt.figure(2)
    v = plt.violinplot(latencies, [n], showmedians=False, showextrema=True, quantiles=[[0.25, 0.5, 0.75, 0.99]])
    v['bodies'][0].set_alpha(1)
    v['bodies'][0].set_facecolor(premultiplied_color)
    v['bodies'][0].set_edgecolor(colors[n + args.color_offset])
    v['bodies'][0].set_linewidth(0.5)
    v['cmins'].set_segments([])
    v['cmaxes'].set_segments([])
    v['cbars'].set_linewidth(1)
    v['cbars'].set_color(colors[n + args.color_offset])
    v['cbars'].set_alpha(0.8)
    v['cquantiles'].set_color('black')
    v['cquantiles'].set_linewidths(0.5)
    v['cquantiles'].set_alpha(0.8)
    segments = np.array(v['cquantiles'].get_segments())
    scales = np.array([2, 3, 2, 1])
    segments[:, :, 0] = np.array([np.average(segments[:, :, 0], axis=1) - 0.125 * scales, np.average(segments[:, :, 0], axis=1) + 0.125 * scales]).T
    v['cquantiles'].set_segments(segments)
    plt.ylim(bottom=0, top=max(max(latencies), plt.ylim()[1]))
    plt.figure(3)
    plt.boxplot(np.array(per_request_latencies), positions=np.arange(len(requests)) + bar_width * (n + 1) - 0.5, widths=bar_width, showfliers=True, patch_artist=True, boxprops=dict(facecolor=premultiplied_color, edgecolor=colors[n + args.color_offset], linewidth=0.5), medianprops=dict(color='black', linewidth=0.5), whiskerprops=dict(color=colors[n + args.color_offset]), capprops=dict(color=colors[n + args.color_offset]), flierprops=dict(marker='o', markerfacecolor=colors[n + args.color_offset], markersize=1.5, markeredgecolor='none', alpha=alpha))
    escaped_filename = filename.replace('_', '\\_')
    table += f"{escaped_filename} & {total} & {round(np.average(requests_per_second), 2)} & {round(np.average(latencies), 2)} & {round(np.std(latencies), 2)}\\\\\n"
table += "\\hline\n" + \
         "\\end{tabular}"

plt.figure(1)
plt.xlabel("Time (s)")
plt.ylabel("Requests per second")
plt.figure(2)
plt.ylabel("Latency (ms)")
plt.xticks([])
plt.figure(3)
plt.xlabel("Request type")
plt.ylabel("Latency (ms)")
plt.xticks(np.arange(len(requests)), np.arange(len(requests)) + 1)
plt.tick_params(axis='x', which='both', bottom=False, top=False, labelbottom=True)
for i in range(1, len(requests)):
    plt.axvline(x=i - 0.5, color='black', linewidth=0.5)
plt.xlim(left=-0.5, right=len(requests) - 0.5)

for i in range(1, 4):
    plt.figure(i)
    plt.ylim(bottom=plt.ylim()[0], top=plt.ylim()[1] * 1.01)
    plt.legend(*zip(*labels), loc='lower center', bbox_to_anchor=(0.5, 1), ncol=8)
    plt.savefig(args.output[:-len(args.output.split(".")[-1]) - 1] + "-" + str(i) + "." + args.output.split(".")[-1], dpi=300, bbox_inches='tight')

print(table)
