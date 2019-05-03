import logging

import mosaik_api

import model as HouseModel


logger = logging.getLogger('householdsim')

meta = {
    'models': {
        'ResidentialLoads': {
            'public': True,
            'params': [
                'sim_start',  # The start time for the simulation:
                              # 'YYYY-MM-DD HH:ss'
                'profile_file',  # Name of file with household data
                'grid_name',  # Name of the grid to load
            ],
            'attrs': [],
        },
        'House': {
            'public': False,
            'params': [],
            'attrs': [
                'P_out',  # Active power [W]
                'num',  # House number starting at 1
                'node_id',  # ID of node the house has to be connected to
                'num_hh',  # Number of separate households within the house
                'num_res',  # Number of residents per household
                'hhrequest', #Quantum request outputs
            ],
        },
    },
}


def eid(hid):
    return 'House_%s' % hid


class HouseholdSim(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(meta)

        self.model = None
        self.houses_by_eid = {}
        self.pos_loads = None
        self._file_cache = {}
        self._offset = 0
        self._cache = {}

        #Quantum part
        self.N = 10         # Default value
        self.protocol = None
        self.hhrequest = None

    def init(self, sid, N, protocol, Eve, drFreq = 60, pos_loads=True):
        """
        @N : number of qubit exchanged each round
        @protocol : BB84, KMB09, ...
        """
        logger.debug('Loads will be %s numbers.' %
                     ('positive' if pos_loads else 'negative'))
        self.pos_loads = 1 if pos_loads else -1
        self.N = N
        self.sid = sid
        self.eve = Eve
        self.protocol = protocol
        self.dr_freq = drFreq
        return self.meta

    def create(self, num, model, sim_start, profile_file, grid_name):

        if num != 1 or self.model:
            raise ValueError('Can only create one set of houses.')

        logger.info('Creating houses for %s from "%s"' %
                    (grid_name, profile_file))

        if profile_file.endswith('gz'):
            import gzip
            pf = gzip.open(profile_file, 'rt')
        else:
            pf = open(profile_file, 'rt')

        try:
            self.model = HouseModel.HouseModel(pf, grid_name, self.N, self.protocol, self.eve, self.dr_freq)
            self.houses_by_eid = {
                eid(i): house for i, house in enumerate(self.model.houses)
                #eid(i): self.model.houses[i] for i in range(0, 2)
            }
        except KeyError:
            raise ValueError('Invalid grid name "%s".' % grid_name)

        # A time offset in minutes from the simulation start to the start
        # of the profiles.
        self._offset = self.model.get_delta(sim_start)

        return [{
            'eid': 'resid_0',
            'type': 'ResidentialLoads',
            'rel': [],
            'children': [{'eid': eid(i), 'type': 'House', 'rel': []}
                         for i, _ in enumerate(self.model.houses)],
        }]

    def step(self, time, inputs=None):
        # "time" is in seconds. Convert to minutes and add the offset
        # if sim start > start date of the profiles.
        minutes = time // 60
        minutes_offset = minutes + self._offset
        cache = {}
        data = self.model.step(minutes_offset, inputs)
        if time % 60 == 0:
            for hid, d in enumerate(data):
                d *= self.pos_loads  # Flip sign if necessary
                cache[eid(hid)] = d
                self._cache = cache
        #self.model.resolution is the step size value for the simulation
        if self.model._wait == True:
            return (minutes + self.model.resolution) * 60
        else:
            return time+1 #simulate each second



    def get_data(self, outputs):
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:

                if attr == 'P_out':
                    val = self._cache[eid]
                else:
                    val = self.houses_by_eid[eid][attr]
                data[eid][attr] = val
        return data


def main():
    return mosaik_api.start_simulation(HouseholdSim(), 'Household simulation')

if __name__ == '__main__':
    main()
