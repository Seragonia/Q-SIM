import json
from argparse import ArgumentParser
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Polygon


parser = ArgumentParser()
parser.add_argument("-f", "--file", dest="filename",
                    help="Output simulation file to open", metavar="FILE")
parser.add_argument("-o", "--overlap",action='store_true')
parser.add_argument("-l", "--lines",action='store_true')
parser.add_argument("-t", "--type",  dest="type", required=True,
                    help="You have to specify a simulation type.")

args = parser.parse_args()
print('output/'+args.filename)

class DATA():
    def __init__(self, N, probability):
        self.N = N
        self.probability = probability
        self.n1 = []
        self.n2 = []
        self.n3 = []
        self.n4 = []
        self.n5 = []
        self.n6 = []
        self.n7 = []
        return

GRAPH_NUMBER = int(args.type)
GRAPHS = {
    0: {
        "name": "n2",
        "bigtitle": 'Number of quantum exchanges detected as having undergone a man-in-the-middle',
        "x": 'Number of Qubit exchanged per second',
        "y": 'Detected MITM rate',
        "title": 'Simulation of 37 houses for 30 minutes',
        "ymax": 160
    },
    1: {
        "name": "n4",
        "bigtitle": 'Validated qubit rate',
        "x": 'Number of Qubit exchanged per second',
        "y": 'Validated qubit rate',
        "title": 'Simulation of 37 houses for 30 minutes',
        "ymax": 6000
    },
    2: {
        "name": "n3",
        "bigtitle": 'Number of quantum exchanges not detected as having undergone a man-in-the-middle',
        "x": 'Number of Qubit exchanged per second',
        "y": 'Undetected MITM rate',
        "title": 'Simulation of 37 houses for 30 minutes',
        "ymax": 11
    },
    3: {
        "name": "n5",
        "bigtitle": 'Number of qubits dropped',
        "x": 'Number of Qubit exchanged per second',
        "y": 'Number of dropped qubits after 30 minutes',
        "title": 'Simulation of 37 houses for 30 minutes',
        "ymax": 11
    },
    4: {
        "name": "n1",
        "bigtitle": 'Number of qubits exchanged',
        "x": 'Number of Qubit exchanged per second',
        "y": 'Number of dropped exchanged to share a secret',
        "title": 'Simulation of 37 houses for 30 minutes',
        "ymax": 250
    },
    5: {
        "name": "n6",
        "bigtitle": 'Number of qubits exchanged',
        "x": 'Number of Qubit exchanged per second',
        "y": 'Number of dropped exchanged to share a secret',
        "title": 'Simulation of 37 houses for 30 minutes',
        "ymax": 250
    },
    6: {
        "name": "n7",
        "bigtitle": 'Number of qubits exchanged',
        "x": 'Number of Qubit exchanged per second',
        "y": 'Latency (s)',
        "title": 'Simulation of 37 houses for 30 minutes',
        "ymax": 250
    },
}
data = {}
simulation = {}

#Parse file
with open('./output/'+args.filename) as f:
    for line in f:
        d = json.loads(line)
        key = next(iter(d))
        strN, strAttackProbability = key.split("-")
        N = int(strN) #Number of Qubits/second
        AttackProbability = float(strAttackProbability) #Probability of Eve attack
        if not key in data:
            data[key] = DATA(N, AttackProbability)
        data[key].n1.append(d[key]["n1"])
        data[key].n2.append(d[key]["n2"])
        data[key].n3.append(d[key]["n3"])
        data[key].n4.append(d[key]["n4"])
        data[key].n5.append(d[key]["n5"])
        data[key].n6.append(d[key]["n6"])
        data[key].n7.append(d[key]["n7"])

list = {}
list2 = {}

#If no lines, get all vectors for each probability
for key, value in data.items():
    if not str(data[key].probability) in list:
        list[str(data[key].probability)] = []
    list[str(data[key].probability)].append(getattr(data[key], GRAPHS[GRAPH_NUMBER]["name"]))

LEN = len(list)

#If no lines, get all vectors for each probability
for key, value in data.items():
    if not str(data[key].probability) in list2:
        list2[str(data[key].probability)] = []
    list2[str(data[key].probability)].append(getattr(data[key], GRAPHS[4]["name"]))

LEN = len(list)


if args.lines is True:
    for key, value in list2.items():
        meanList = []
        for vector in value:
            meanList.append(sum(vector) / float(len(vector))) #mean value)
        list2[key] = meanList

if args.lines is True:
    for key, value in list.items():
        meanList = []
        for vector in value:
            meanList.append( 100 * (sum(vector) / float(len(vector))) / (sum(list2[key]) / float(len(list2[key])))    ) #mean value)
        list[key] = meanList

print(list)
print(list2)

# Output as PNG file
mpl.use('agg')

if args.overlap is True:
    fig = plt.figure(1, figsize=(15, 10))

colors = ['#8e8e93', '#4cd964', '#007aff', '#ff9500', '#ffcc00', '#4cd964', '#5ac8fa', '#34aadc', '#007aff', '#5856d6']
i = 0

if args.lines is True:
    #One output for each probability
    for key, value in list.items():
        plt.rcParams.update({'font.size': 15})
        print("Creating plot for ", key, " attack probability...")
        # Create a figure instance
        if args.overlap is False:
            fig = plt.figure(str(key), figsize=(10, 10))
        #plt.suptitle(GRAPHS[GRAPH_NUMBER]["bigtitle"], fontsize=20, fontweight='bold')
        plt.xlabel(GRAPHS[GRAPH_NUMBER]["x"], fontsize=20)
        plt.ylabel(GRAPHS[GRAPH_NUMBER]["y"], fontsize=20)
        plt.xlim([5,5+len(value)])
        if args.overlap is False:
            plt.ylim([0,GRAPHS[GRAPH_NUMBER]["ymax"]])
        plt.xticks(np.arange(5, 305, step=15))
        plt.plot(np.arange(5,300,15), np.array(value), color=colors[i], marker=".", label="p="+str(key))
        plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0., prop={'size': 20})
        # Save the figure
        if args.overlap is False:
            fig.savefig('output/'+GRAPHS[GRAPH_NUMBER]["name"]+'-fig'+str(key)+'.png', bbox_inches='tight', positions=range(5, 5+len(list)))
        i += 1
else:
    #One output for each probability
    for key, value in list.items():
        print("Creating plot for ", key, " attack probability...")
        # Create a figure instance
        if args.overlap is False:
            fig = plt.figure(str(key), figsize=(30, 10))
            fig.suptitle(GRAPHS[GRAPH_NUMBER]["bigtitle"] + ' p='+str(key), fontsize=14, fontweight='bold')
        else:
            fig.suptitle(GRAPHS[GRAPH_NUMBER]["bigtitle"], fontsize=14, fontweight='bold')
        # Create an axes instance
        ax = fig.add_subplot(111)
        print(max(max(value)))
        plt.xticks(np.arange(5, 305, step=15))
        if args.overlap is False:
            ax.set_ylim([0,GRAPHS[GRAPH_NUMBER]["ymax"]])
        ax.set_xlabel(GRAPHS[GRAPH_NUMBER]["x"])
        ax.set_ylabel(GRAPHS[GRAPH_NUMBER]["y"])
        ax.set_title(GRAPHS[GRAPH_NUMBER]["title"])
        plt.setp(ax.get_xticklabels(), rotation=45, horizontalalignment='right')
        # Create the boxplot
        bp = ax.boxplot(value)
        # Save the figure
        if args.overlap is False:
            fig.savefig('output/'+GRAPHS[GRAPH_NUMBER]["name"]+'-fig'+str(key)+'.png', bbox_inches='tight', positions=range(5, 5+LEN))
        i += 1

if args.overlap is True:
    fig.savefig('output/'+GRAPHS[GRAPH_NUMBER]["name"]+'-out.png', bbox_inches='tight', positions=range(5, 5+len(list)))
