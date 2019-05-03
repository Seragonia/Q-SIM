import random
import datetime
from mosaik.util import connect_randomly, connect_many_to_one
import mosaik


sim_config = {
    'CSV': {
        'python': 'mosaik_csv:CSV',
    },
    'DB': {
        'cmd': 'mosaik-hdf5 %(addr)s',
    },
    'HouseholdSim': {
        'cmd': 'python simulators/householdsim/HouseholdSim.py %(addr)s',
    },
    'PyPower': {
        'cmd': 'mosaik-pypower %(addr)s',
    },
    'WebVis': {
        'cmd': 'python simulators/mosaik_web/MosaikWeb.py -s 0.0.0.0:8000 %(addr)s',
    },
    'ControlCenter': {
        'cmd': 'python simulators/ControlCenter/CC.py %(addr)s',
    },
}

START = '2014-01-01 00:00:00'
START_REAL_TIME = datetime.datetime.now().strftime("%I-%M-%S_%B-%d-%Y")
END = 60*60*4000  # 10 hours
PV_DATA = 'data/pv_30kw.csv'
PROFILE_FILE = 'data/profiles.data.gz'
GRID_NAME = 'demo_lv_grid'
GRID_FILE = 'data/%s.json' % GRID_NAME

'''
 TOPOLOGY
'''
RESIDENTIAL_AREA = 1
MIN_NUMBER_OF_HOUSE_PER_RA = 1
MIN_NUMBER_OF_HOUSE_PER_RA = 37

'''
 QUANTUM PART
'''
NQUBIT          = 100 #number of qubit exchanged in each QKD process
PROTOCOLS       = {1: {"qkd": "BB84", "crypto": "OTP"},   #OPT cryptosystem using BB84 protocol
                   2: {"qkd": "BB84", "crypto": "AES"},   #AES cryptosystem using BB84 protocol
                   3: {"qkd": "SARG04", "crypto": "OTP"}, #OPT cryptosystem using SARG04 protocol
                   4: {"qkd": "SARG04", "crypto": "AES"}, #AES cryptosystem using SARG04 protocol
                   5: {"qkd": "KMB09", "crypto": "OTP"},  #OTP cryptosystem using KMB09 protocol
                   6: {"qkd": "KMB09", "crypto": "AES"}}  #AES cryptosystem using KMB09 protocol
PROTOCOL_USED   = 1
EVE_ATTACK_PROBABILITY = 0.1
EVE_SIMULATION = {"type": 1, "probability": EVE_ATTACK_PROBABILITY} #0 = no Eve
                                                 #1 = Eve within each House simulator

SIMULATION_OUTPUT = False

'''
 DEMAND RESPONSE
'''
DEMAND_FREQUENCY = 60 #in minutes every hour

def main():
    global NQUBIT
    global PROTOCOL_USED
    random.seed(23)
    if SIMULATION_OUTPUT == True:
        for i in range(5, 300, 15): #NQUBIT
            for j in range(0,10,2):
                NQUBIT = i
                print('NQUBITS = ', i, 'Attack probability = ', j)
                EVE_ATTACK_PROBABILITY = j/10
                EVE_SIMULATION['probability'] = EVE_ATTACK_PROBABILITY
                world = mosaik.World(sim_config)
                create_scenario(world)
                world.run(until=END)

    else:
        world = mosaik.World(sim_config)
        create_scenario(world)
        world.run(until=END)  # As fast as possilbe
    # world.run(until=END, rt_factor=1/60)  # Real-time 1min -> 1sec


def create_scenario(world):
    # Start simulators
    pypower = world.start('PyPower', step_size=15*60)
    hhsim = []
    for i in range(0, RESIDENTIAL_AREA):
        hhsim.append(world.start('HouseholdSim', N=NQUBIT, protocol=PROTOCOLS[PROTOCOL_USED], Eve=EVE_SIMULATION, drFreq=DEMAND_FREQUENCY))
    pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    cc = world.start('ControlCenter', step_size=1, N=NQUBIT, protocol=PROTOCOLS[PROTOCOL_USED], Eve=EVE_SIMULATION, simulationNumber=START_REAL_TIME, simulation=SIMULATION_OUTPUT, drFreq=DEMAND_FREQUENCY*60)

    # Instantiate models
    grid = pypower.Grid(gridfile=GRID_FILE).children
    houses = []
    for i in range(0, RESIDENTIAL_AREA):
        houses.append(hhsim[i].ResidentialLoads(sim_start=START,
                                        profile_file=PROFILE_FILE,
                                        grid_name=GRID_NAME).children)
    pvs = pvsim.PV.create(12)
    controlCenter = cc.CC()

    # Connect entities
    for i in range(0, RESIDENTIAL_AREA):
        connect_buildings_to_grid(world, houses[i], grid)
    # Connect to the Control Center
    for i in range(0, RESIDENTIAL_AREA):
        connect_many_to_one(world, houses[i], controlCenter, ('hhrequest', 'ccresponse'), async_requests=True)
    connect_randomly(world, pvs, [e for e in grid if 'node' in e.eid], 'P')

    # Database
    if SIMULATION_OUTPUT == False:
        nodes = [e for e in grid if e.type in ('RefBus, PQBus')]
        branches = [e for e in grid if e.type in ('Transformer', 'Branch')]
        # Web visualization
        webvis = world.start('WebVis', start_date=START, step_size=120)
        webvis.set_config(ignore_types=['Topology', 'ResidentialLoads', 'Grid',
                                        'Database'])
        vis_topo = webvis.Topology()

        connect_many_to_one(world, nodes, vis_topo, 'P', 'Vm')
        webvis.set_etypes({
            'RefBus': {
                'cls': 'refbus',
                'attr': 'P',
                'unit': 'P [W]',
                'default': 0,
                'min': 0,
                'max': 30000,
            },
            'PQBus': {
                'cls': 'pqbus',
                'attr': 'Vm',
                'unit': 'U [V]',
                'default': 230,
                'min': 0.99 * 230,
                'max': 1.01 * 230,
            },
        })
        for i in range(0, RESIDENTIAL_AREA):
            connect_many_to_one(world, houses[i], vis_topo, 'P_out', 'hhrequest')
        webvis.set_etypes({
            'House': {
                'cls': 'load',
                'attr': 'P_out',
                'unit': 'P [W]',
                'default': 0,
                'min': 0,
                'max': 3000,
            },
        })

        connect_many_to_one(world, pvs, vis_topo, 'P')
        webvis.set_etypes({
            'PV': {
                'cls': 'gen',
                'attr': 'P',
                'unit': 'P [W]',
                'default': 0,
                'min': -10000,
                'max': 0,
            },
        })

        world.connect(controlCenter, vis_topo, 'ccresponse')
        webvis.set_etypes({
            'CC': {
                'cls': 'cc',
                'attr': 'ccresponse',
                'unit': 'Qubits [S]',
                'default': 0,
                'min': 0,
                'max': 1000,
            },
        })

def connect_buildings_to_grid(world, houses, grid):
    buses = filter(lambda e: e.type == 'PQBus', grid)
    buses = {b.eid.split('-')[1]: b for b in buses}
    house_data = world.get_data(houses, 'node_id')
    for house in houses:
        node_id = house_data[house]['node_id']
        world.connect(house, buses[node_id], ('P_out', 'P'))


if __name__ == '__main__':
    main()
