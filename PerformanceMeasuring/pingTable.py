import argparse

parser = argparse.ArgumentParser()
parser.add_argument("input_file", nargs='+', type=argparse.FileType('r'), help="Input ping log")

args = parser.parse_args()

table = "\\begin{tabular}{|l|c|c|}\n" + \
        "\\hline\n" + \
        " & ".join([f"\\textbf{{{label}}}" for label in ["Segment", "Avg. Latency", "Latency std dev."]]) + "\\\\\n" + \
        "\\hline\n"
for f in args.input_file:
    filename = f.name
    filename = filename[filename.rfind('/') + 1:]
    if '.' in filename:
        filename = filename[:filename.rfind('.')]
    escaped_filename = filename.replace('_', '\\_')
    lines = f.readlines()
    stats = lines[-1].strip()
    stats = stats.split('=')[1].strip()
    stats = stats.split(' ')[0].strip()
    stats = stats.split('/')
    table += f"\\hline\n{escaped_filename} & {stats[1]} & {stats[3]}\\\\\n"
table += "\\hline\n\\end{tabular}\n"
print(table)
