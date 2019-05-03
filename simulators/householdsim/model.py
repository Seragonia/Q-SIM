"""

"""
import json
import arrow
from utils.communicationLayer import comLayer
import datetime
import importlib

DATE_FORMAT = 'YYYY-MM-DD HH:mm'
"""Date format used to convert strings to dates."""


class HouseModel:
    """The HouseModel processes and prepares the load profiles and their
    associated meta data to allow and easier access to it.

    """
    def __init__(self, data, lv_grid, N, protocol, eve, dr_freq):
        # Process meta data
        assert next(data).startswith('# meta')
        meta = json.loads(next(data))
        self.start = arrow.get(meta['start_date'], DATE_FORMAT)
        """The start date of the profile data."""
        self.resolution = meta['resolution']
        """The time resolution of the data in minutes."""
        self.unit = meta['unit']
        """The unit used for the load profiles (e.g., *W*)."""
        self.num_profiles = meta['num_profiles']
        """The number of load profiles in the file."""

        """ QKD part """
        self.hhrequest = None #data sended to the CC
        self.N = N
        self.data = data
        self.eve = True if eve["type"] == 1 else False
        self.eveP = 0 if self.eve == False else eve["probability"]

        self.protocol = importlib.import_module('utils.'+protocol["crypto"])
        self.qkd = protocol["qkd"]

        """ Demand Response part """
        self.dr_freq = dr_freq
        ''' Consumption that needs to be sent every X times'''
        self.consumption = 0
        self.reponseReceived = 0
        self.next_dr = self.dr_freq

        # Obtain id lists
        assert next(data).startswith('# id_list')
        id_list_lines = []
        for line in data:
            if line.startswith('# attrs'):
                break
            id_list_lines.append(line)
        id_lists = json.loads(''.join(id_list_lines))
        self.node_ids = id_lists[lv_grid]
        """List of power grid node IDs for which to create houses."""

        # Enable pre-processing of the data
        self._data = self._get_line(data)

        # Obtain static attributes and create list of house info dicts
        attrs = {}
        for attr, *vals in self._data:
            if attr.startswith('# profiles'):
                break
            attrs[attr] = [int(val) for val in vals]

        #: List of house info dicts
        self.houses = []
        for i, n in enumerate(self.node_ids):
            p = importlib.import_module('utils.'+protocol["crypto"]).Protocol(N, n, self.eve, self.eveP, protocol["qkd"])
            self.houses.append({
                'num': i + 1,
                'node_id': n,
                'num_hh': attrs['num_hh'][i % self.num_profiles],
                'num_res': attrs['num_residents'][i % self.num_profiles],
                'protocol': p,
                'commLayer': comLayer(p, p.__get_states_mapping__()),
                'hhrequest': None,
            })

        # Helpers for step()
        self._last_date = None
        self._cache = None
        self._wait = False

    def step(self, time, inputs):
        """Get the current load for all houses for *minutes* minutes since
        :attr:`start`.

        If the model uses a 15min resolution and minutes not multiple of 15,
        the next smaller multiple of 15 will be used. For example, if you
        pass ``minutes=23``, you'll get the value for ``15``.

        """
        # Trim "minutes" to multiples of "self.resolution"
        # Example: res=15, minutes=40 -> minutes == 30
        minutes = time // self.resolution * self.resolution
        target_date = self.start.replace(minutes=minutes)
        if time > self.next_dr:
            self.next_dr += self.dr_freq
        if target_date != self._last_date:
            # If target date not already reached, search data until we find it:
            for date, *values in self._data:
                date = arrow.get(date, DATE_FORMAT)
                if date == target_date:
                    # Found target date, cache results:
                    values = list(map(float, values))
                    self._cache = self.compute_step(values, time, inputs)
                    self._last_date = date
                    break
                else:
                # We've reached the end of our data file if the for loop
                # normally finishes.
                    raise IndexError('Target date "%s" (%s minutes from start) '
                                    'out of range.' % (target_date, time))
        elif self._wait == False or time > self.next_dr:
            #QKD
            for i, house in enumerate(self.houses):
                out = self.compute_comm_layer_step(house, minutes, inputs.get('House_'+str(i)))
                if out == -1:
                    self.reponseReceived += 1
                house['hhrequest'] = out if out != -1 else None
            if self.reponseReceived == len(self.houses): #All houses has received a message
                self._wait = True
                self.reponseReceived = 0
        return self._cache

    def compute_step(self, values, time, inputs):
        ret = []
        for i, house in enumerate(self.houses):
            power_consumption = values[i % self.num_profiles]
            data = inputs.get('House_'+str(i))
            out = self.compute_comm_layer_step(house, time, data, power_consumption)
            house['hhrequest'] = out if out != -1 else None
            ret.append(power_consumption)
        return ret

    def compute_comm_layer_step(self, house, time, data, power_consumption = None):
        if power_consumption != None:
            self.consumption += power_consumption
        #Send every `dr_freq` data demand
        if time % self.dr_freq == 0 and self.consumption != 0:
            house['commLayer'].__add_message_to_be_send__(str(self.consumption))
            self.consumption = 0
            self._wait = False
        out = house['commLayer'].__doStep__(data)
        return out


    def get_delta(self, date):
        """Get the amount of minutes between *date* and :attr:`start`.
        The date needs to be a strings formated like :data:`DATE_FORMAT`.
        Raise a :exc:`ValueError` if *date* is smaller than :attr:`start`.
        """
        date = arrow.get(date, DATE_FORMAT)
        if date < self.start:
            raise ValueError('date must >= "%s".' %
                             self.start.format(DATE_FORMAT))
        dt = date - self.start
        seconds = (dt.days * 1440 * 60) + (dt.seconds)
        return seconds

    def _get_line(self, iterator):
        for line in iterator:
            yield [item.strip() for item in line.split(',')]
