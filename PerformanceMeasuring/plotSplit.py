import argparse
import json
import numpy as np
from matplotlib import pyplot as plt, patches as mpatches, colors as mcolors
from scipy.signal import savgol_filter


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
parser.add_argument("input_file", nargs='+', type=argparse.FileType('r'), help="Input result file")
parser.add_argument('-o', '--output', default='plot.png', help='Output filename')
parser.add_argument('-x', '--color_offset', type=int, default=0, help='Offset of label colors list')
parser.add_argument('-nt', '--no-types', action='store_true', help='Do not differentiate request types')
parser.add_argument('-t', '--type', type=int, nargs="*", help='Select only requests of the specified type', choices=range(1, len(requests) + 1))
parser.add_argument('-f', '--filter-percentile', type=float, default=100, help='Filter out the highest latencies')
parser.add_argument('-s', '--stats-only', action='store_true', help='Only print stats')
parser.add_argument('-c', '--compact', action='store_true', help='Legend on top')

args = parser.parse_args()
types = range(0, len(requests))
if args.type is not None and args.no_types:
    print("Cannot use both --type and --no-types")
    exit(1)
if args.type is not None:
    types = [i - 1 for i in args.type]
if args.no_types:
    types = [0]

all_results = []
for f in args.input_file:
    try:
        all_results.append(json.load(f))
    except json.decoder.JSONDecodeError as e:
        print("JSONDecodeError: " + str(e))
        exit(1)

colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

plt.rcParams.update({'font.size': 12 / 0.6})
plt.rcParams.update({'font.family': 'serif'})
# comment to print without LaTeX installed
plt.rcParams.update({'text.usetex': True})
plt.rcParams.update({'figure.subplot.wspace': 0.5})
bar_width = 1 / (len(args.input_file) + 1)
alpha = 0.3

labels = []
for n, file in enumerate(args.input_file):
    filename = file.name
    filename = filename[filename.rfind('/') + 1:]
    if '.' in filename:
        filename = filename[:filename.rfind('.')]
    color = colors[(n + args.color_offset) % len(colors)]
    labels.append((mpatches.Patch(color=color), filename))

table = "\\begin{tabular}{|l|c|c|c|c|}\n" + \
        "\\hline\n" + \
        " & ".join([f"\\textbf{{{label}}}" for label in ["Method", "Total Requests", "Avg. Latency", "Latency std dev.", "Avg. Client Latency"]]) + "\\\\\n" + \
        "\\hline\n"
for n, results in enumerate(all_results):
    premultiplied_color = np.array(mcolors.to_rgba(colors[(n + args.color_offset) % len(colors)])) * alpha + (1 - alpha)
    filename = args.input_file[n].name
    results = [res for res in results if res["total_latency"] > 0]
    total = len(results)
    failed = len([res for res in results if res["fail"]])
    print(f"{filename}: \ttotal requests: {total}, failed: {failed}")
    if failed != 0:
        print("\033[1;33m" + filename + ": some errors present in requests, results may be inaccurate\033[0m")
    latencies = list([res["total_latency"] * 1000 for res in results])
    client_latencies = [(res["total_latency"] - res["request_latency"]) * 1000 for res in results]
    per_request_latencies = list(chunks(latencies, len(requests) if not args.no_types else 1))
    if len(per_request_latencies[-1]) != len(per_request_latencies[0]):  # Remove last loop if it was cut off by the timer
        per_request_latencies = per_request_latencies[:-1]
    per_request_latencies = np.array(per_request_latencies).transpose().tolist()
    per_request_latencies = [per_request_latencies[i] for i in types]
    if args.filter_percentile != 100:
        for prl in per_request_latencies:
            percentile_value = np.percentile(prl, args.filter_percentile)
            prl[:] = [latency for latency in prl if latency <= percentile_value]
    latencies = [lat for prl in per_request_latencies for lat in prl]
    if not args.stats_only:
        plt.figure(1)
        plt.subplot(1, len(all_results), n + 1)
        plt.xticks([])
        plt.xlabel(labels[n][1])
        v = plt.violinplot(latencies, [n], showmedians=False, showextrema=True, quantiles=[[0.25, 0.5, 0.75, 0.99] if args.filter_percentile == 100 else [0.25, 0.5, 0.75]])
        v['bodies'][0].set_alpha(1)
        v['bodies'][0].set_facecolor(premultiplied_color)
        v['bodies'][0].set_edgecolor(colors[(n + args.color_offset) % len(colors)])
        v['bodies'][0].set_linewidth(0.5)
        v['cmins'].set_segments([])
        v['cmaxes'].set_segments([])
        v['cbars'].set_linewidth(1)
        v['cbars'].set_color(colors[(n + args.color_offset) % len(colors)])
        v['cbars'].set_alpha(0.8)
        v['cquantiles'].set_color('black')
        v['cquantiles'].set_linewidths(0.5)
        v['cquantiles'].set_alpha(0.8)
        segments = np.array(v['cquantiles'].get_segments())
        scales = np.array([2, 3, 2, 1] if args.filter_percentile == 100 else [2, 3, 2])
        segments[:, :, 0] = np.array([np.average(segments[:, :, 0], axis=1) - 0.125 * scales, np.average(segments[:, :, 0], axis=1) + 0.125 * scales]).T
        v['cquantiles'].set_segments(segments)
        plt.ylim(bottom=0, top=max(max(latencies), plt.ylim()[1]))
        plt.figure(2)
        for i, prl in enumerate(per_request_latencies):
            plt.boxplot(prl, positions=[i + bar_width * (n + 1) - 0.5], widths=bar_width, showfliers=True, patch_artist=True, boxprops=dict(facecolor=premultiplied_color, edgecolor=colors[(n + args.color_offset) % len(colors)], linewidth=0.5), medianprops=dict(color='black', linewidth=0.5), whiskerprops=dict(color=colors[(n + args.color_offset) % len(colors)]), capprops=dict(color=colors[(n + args.color_offset) % len(colors)]), flierprops=dict(marker='o', markerfacecolor=colors[(n + args.color_offset) % len(colors)], markersize=1.5, markeredgecolor='none', alpha=alpha))
        # plt.boxplot(np.array(per_request_latencies), positions=np.arange(len(requests)) + bar_width * (n + 1) - 0.5, widths=bar_width, showfliers=True, patch_artist=True, boxprops=dict(facecolor=premultiplied_color, edgecolor=colors[(n + args.color_offset)%len(colors)], linewidth=0.5), medianprops=dict(color='black', linewidth=0.5), whiskerprops=dict(color=colors[(n + args.color_offset)%len(colors)]), capprops=dict(color=colors[(n + args.color_offset)%len(colors)]), flierprops=dict(marker='o', markerfacecolor=colors[(n + args.color_offset)%len(colors)], markersize=1.5, markeredgecolor='none', alpha=alpha))
        if args.filter_percentile != 100:
            print("\033[1;33mFiltering enabled, skipping speed and peak latency plots\033[0m")
        else:
            plt.figure(3)
            timestamps = np.cumsum(latencies)
            requests_per_second = []
            for min_timestamp in np.arange(timestamps[0], timestamps[-1], 1000):
                requests_per_second.append(len([t for t in timestamps if min_timestamp <= t < min_timestamp + 1000]))
            window_seconds = 2
            smoothed_requests_per_second = savgol_filter(requests_per_second, window_seconds, 1)
            plt.plot(smoothed_requests_per_second, label=filename, color=colors[(n + args.color_offset) % len(colors)])
            plt.plot(np.arange(len(requests_per_second)), [np.average(requests_per_second)] * len(requests_per_second), color=colors[(n + args.color_offset) % len(colors)], alpha=0.5, linewidth=1)
            plt.ylim(bottom=0, top=max(max(requests_per_second), plt.ylim()[1]))
            plt.figure(4)
            maxes = 10
            near = 50
            idxs = list(np.argpartition(latencies, -maxes)[-maxes:])
            idxs.sort()
            for j, idx1 in enumerate(idxs):
                for idx2 in idxs[j + 1:]:
                    if abs(idx1 - idx2) < near:
                        # print(f"Removing {idx2}")
                        idxs.remove(idx2)
            print("Highest latencies and indexes:\n" + "\n".join([f"{round(latencies[idx])}ms ({idx})" for idx in idxs]) + "\n")
            important = []
            for idx in idxs:
                important += latencies[max(idx - near, 0):idx + near] + [0] * 20
            plt.plot(important, label=filename, color=colors[(n + args.color_offset) % len(colors)], marker=".", markeredgecolor='none', markersize=1, linestyle="-", linewidth=0.1)
            plt.gca().set_aspect(0.5)

    filename = filename[filename.rfind('/') + 1:]
    if '.' in filename:
        filename = filename[:filename.rfind('.')]
    escaped_filename = filename.replace('_', '\\_')
    table += f"\\hline\n{escaped_filename} & {total} & {round(np.average(latencies), 2)} & {round(np.std(latencies), 2)} & {round(np.average(client_latencies), 2)}\\\\\n"
table += "\\hline\n" + \
         "\\end{tabular}"

plt.figure(1)
plt.subplot(1, len(all_results), 1)
plt.ylabel("Latency (ms)")
plt.figure(2)
plt.xlabel("Request type")
plt.ylabel("Latency (ms)")
plt.xticks(np.arange(len(types)), [i + 1 for i in types])
plt.tick_params(axis='x', which='both', bottom=False, top=False, labelbottom=True)
for i in range(1, len(types)):
    plt.axvline(x=i - 0.5, color='black', linewidth=0.5)
plt.xlim(left=-0.5, right=len(types) - 0.5)
if 3 in plt.get_fignums():
    plt.figure(3)
    plt.xlabel("Time (s)")
    plt.ylabel("Requests per second")

for i in plt.get_fignums():
    plt.figure(i)
    bottom = plt.ylim()[0]
    if bottom / plt.ylim()[1] < 0.25:
        bottom = 0
    plt.ylim(bottom=bottom, top=plt.ylim()[1] * 1.02)
    if i != 1:
        if args.compact:
            plt.legend(*zip(*labels), loc='lower center', bbox_to_anchor=(0.5, 1), ncol=2)
        else:
            plt.legend(*zip(*labels), loc='upper left', bbox_to_anchor=(1, 1), ncol=1)
    plt.savefig(args.output[:-len(args.output.split(".")[-1]) - 1] + "-" + str(i) + "." + args.output.split(".")[-1], dpi=900 if i == 4 else 300, bbox_inches='tight')

print(table)
