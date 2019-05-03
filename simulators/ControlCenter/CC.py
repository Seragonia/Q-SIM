"""
Control center simulator
"""
import mosaik_api
from utils.communicationLayer import comLayer
import importlib
import json
import logging
logger = logging.getLogger('controlcenter')

META = {
    'models': {
        'CC': {
            'public': True,
            'params': [],
            'attrs': ['ccresponse'],
        },
    },
}

class CC(mosaik_api.Simulator):
    def __init__(self):
        super().__init__(META)
        self.eid = 'CC'
        self.step_size = None
        self.HouseDict = {}
        self.N = 10         # Default value
        self.ccresponse = []
        self.responded = 0

    def init(self, sid, step_size, N, protocol, Eve, simulationNumber = 0, simulation=False, drFreq=3600):
        self.eve = Eve
        self.step_size = step_size
        self.N = N
        self.protocol = importlib.import_module('utils.'+protocol["crypto"])
        self.qkd = protocol["qkd"]
        self.simulationFile = str(simulationNumber) + '-CC.json'
        self.simulation = simulation
        self.drFreq = drFreq
        self.next_step = self.drFreq
        return self.meta

    def create(self, num, model):
        if num > 1:
            raise RuntimeError('Can only create one instance of CC.')
        return [{'eid': self.eid, 'type': model}]

    def step(self, time, input):
        #Compute next hour time after
        if time > self.next_step:
            self.next_step += self.drFreq
        wait_until_next_DR = False
        for key, value in input.items():
            for key2, value2 in value.items():
                for key3, value3 in value2.items():
                    self.check_HouseDictionary(key3, value3)
                    ret = self.HouseDict[key3]["commLayer"].__doStep__(value3)
                    if type(ret) is dict:
                        if 'control' in ret and ret['control'] == -2:
                            self.responded += 1
                            if self.responded == len(self.HouseDict): #detect the end of responses
                                wait_until_next_DR = True
                                self.responded = 0
                            val = {self.eid+'.': {key3: {'response': ret}}}
                            yield self.mosaik.set_data(val)
                        else:
                            val = {self.eid+'.': {key3: {'response': ret}}}
                            yield self.mosaik.set_data(val)
                    elif ret == -1: #reponse value
                        self.HouseDict[key3]["commLayer"].__add_message_to_be_send__('0.2')
                    #Output Simulation part
                    if time and time % 10800 == 0 and self.simulation == True:
                        logger.info(self.HouseDict[key3]["protocol"].outputs)
                        #resetting outputs values
                        with open('output/'+self.simulationFile, 'a+') as file:
                            file.write(json.dumps({str(self.N)+'-'+str(self.eve["probability"]): self.HouseDict[key3]["protocol"].outputs})+'\n')
                            file.flush()

        if wait_until_next_DR == True:
            return time + (self.next_step - time)
        else:
            return time + self.step_size

    def check_HouseDictionary(self, key, initialValue):
        """
        This function is used to add an entry in the self.HouseDict dictionary.
        Instantiates a new Protocol object for each house.
        """
        if key in self.HouseDict:
          return
        else:
          protocol = self.protocol.Protocol(self.N, self.eid, False, 0, self.qkd)
          self.HouseDict[key] = {"commLayer": comLayer(protocol, protocol.__get_states_mapping__()),
                                 "protocol": protocol}

    def get_data(self, outputs):
        self.ccresponse = []
        for key, val in self.HouseDict.items():
            self.ccresponse.append(json.dumps(self.HouseDict[key]["protocol"].outputs))
        data = {}
        for eid, attrs in outputs.items():
            data[eid] = {}
            for attr in attrs:
                data[eid][attr] = self.ccresponse
        return data

if __name__ == '__main__':
    mosaik_api.start_simulation(CC())
