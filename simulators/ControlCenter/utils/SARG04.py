from utils.qubit import qubit
import random
from numpy import matrix
from math import pow, sqrt
import sys

INFO = False
DEBUG = False
VERIFICATION = 10

class Protocol():
    def __init__(self, N, eid, eve=False, eveP=0):
        self.eid = eid
        self.N = N                #N is the number of qubit exchanged each QKD round
        self.isSender = True      #Needed to know if the current QKD
                                  #is for receiving or sending information
        self.senderData = {
            "data": [],           #Received qubit
            "basis": [],          #Random Basis used by the receiver for a given sender
            "data2": [],          #Second possibility of qubit
            "basis2": []          #Basis for the second possibility of qubit
        }

        self.receiverData = {
            "received-qubits": [],  #Received qubit
            "computed-basis": [],   #Random Basis used by the receiver for a given sender
            "measurements" : []    #qubits measured by the receiver with his random basis
        }
        #Common values :
        self.commonQubits = []
        self.key = [] #secret shared
        self.error = False #Set to true if Eve is present
        return

    def __debug_print__(self, msg):
        if DEBUG is True:
            print('[DEBUG] : ' + msg, file=sys.stdout, flush=True)
        return

    def __info_print__(self, msg):
        if INFO is True:
            print('[INFO] : ' + msg, file=sys.stdout, flush=True)
        return

    def __get_states_mapping__(self):
        """
        State, used to know what to do when receiving data.
        """
        return { 0:  self.__IDLE__,
                 1:  self.__start_receiver__,
                 2:  self.__start_sender__,
                 12: self.__comparison_with_measurements__,
                 13: self.__waiting_synchro__,
                 21: self.__sending_possibilities__,
                 22: self.__results_reception__,
                 3:  self.__done__,
                 4: self.__error__ }

    def __get_data__(self):
        """
        Returns self.receiverData or self.senderData based on self.isSender value
        """
        if self.isSender:
            return self.senderData
        else:
            return self.receiverData

    def __generate_random_bits__(self, N):
        """ This function generates a list of N random bits.
        """
        aux = list()
        for i in range(N):
            aux.append(random.randint(0,1))
        return aux

    def __compute_photons__(self, data, basis):
        """
        This function is used to calculate the photons to be sent
        over the network.
        """
        assert len(data) == len(basis), "Basis and data must be the same length!"
        message = list()
        for i in range(len(data)):
            if not basis[i]:
                #Base computacional
                if not data[i]:
                    message.append(qubit(0).serialize())
                else:
                    message.append(qubit(1).serialize())
            else:
                #Base Hadamard
                if not data[i]:
                    tmp = qubit(0)
                else:
                    tmp = qubit(1)
                tmp.hadamard()
                message.append(tmp.serialize())
        return message

    def __deserialize__(self, data, basis):
        """This function deserialize a list of serialized qubit into a list
        of qubit object, and use a basis to change their value accordingly"""
        out = list()
        i = 0
        for value in data:
            q = qubit(0)
            #Deserializing qubit...
            q.state = matrix([[value['state']['0']], [value['state']['1']]])
            #add basis
            if not basis[i]:
                mes = q.measure(0)
                out.append(mes)
            else:
                mes = q.measure(1)
                out.append(mes)
            i = i+1
        return out

    def __IDLE__(self, data=None):
        """
        If data is true, then QKD will (re)start as the receiver.
        If data is false, QKD will start as the sender of the secret.
        Return next step to do
        """
        self.key = []
        self.sync = 0
        self.error = False
        if data != None:
            self.isSender = False
            return self.__start_receiver__(data)
        else:
            return self.__start_sender__(data)

    def __start_receiver__(self, data):
        self.__debug_print__('\x1b[0;33;40m' + 'CC Received Qubits -> ' + str(data) + '\x1b[0m')
        #Compute the random basis to interprete incoming qubits
        self.receiverData["computed-basis"] = self.__generate_random_bits__(self.N)
        self.__debug_print__('\x1b[0;33;40m' + 'Computed basis : ' + str(self.receiverData["computed-basis"]) + '\x1b[0m')
        #Receive qubits and compute the right result with the previous random basis
        self.receiverData["received-qubits"] = self.__deserialize__(data, self.receiverData["computed-basis"])
        self.__debug_print__('\x1b[0;33;40m' + 'Measured bits : ' + str(self.receiverData["received-qubits"]) + '\x1b[0m')
        #Compute the list of qubits measured with the received qubits and the computed basis
        self.receiverData["measurements"] = self.__compute_photons__(self.receiverData["received-qubits"],self.receiverData["computed-basis"]);
        self.__debug_print__('\x1b[0;33;40m' + 'Measured photons : ' + str(self.receiverData["measurements"]) + '\x1b[0m')
        return self.receiverData["computed-basis"], 12

    def __start_sender__(self, data):
        self.senderData["data"]  = self.__generate_random_bits__(self.N)
        self.senderData["basis"] = self.__generate_random_bits__(self.N)
        ret = self.__compute_photons__(self.senderData["data"], self.senderData["basis"])
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' -> CC : ' + str(ret) + '\x1b[0m')
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' random key : ' + str(self.senderData["data"]) + '\x1b[0m')
        #return value to the simulator, and next step value
        return ret, 21

    def __compare_qbits__(self, measure, value):
        """
        This function compares the qubit list with the possible qubit couple
        list and puts a '1' in the validation list if they are different (and
        an 'x' if not).
        """
        validation = list()
        i = 0
        for i in range(len(value)):
            if measure[i] != value[i][0] and measure[i] != value[i][1]:
                validation.append(1)
            else:
                validation.append('x')
        return validation

    def __compute_secret__(self, data, basis, decision):
        """
        This function compute the secret key from the list of qubits
        possibilities and the decision list according to SARG04 protocol
        """
        out = list()
        for i, d in enumerate(decision):
            qubitMeasured = []
            if d == 1:
                #If used basis is Hadamard, then choose the photon
                #in normal basis
                if basis[i] == 1:
                    #if normal basis, choose this one, else the other
                    if data[i][0]['state']['0'] in [0,1]:
                        qubitMeasured = [data[i][0]['state']['0'], data[i][0]['state']['1']]
                    else:
                        qubitMeasured = [data[i][1]['state']['0'], data[i][1]['state']['1']]
                    q = qubit(0)
                    bit = q.readState(qubitMeasured[0], qubitMeasured[1])
                    out.append(bit)
                #if not hadamard basis, then choose the photon in hadamard
                #basis
                else:
                    if data[i][0]['state']['0'] not in [0,1]:
                        qubitMeasured = [data[i][0]['state']['0'], data[i][0]['state']['1']]
                    else:
                        qubitMeasured = [data[i][1]['state']['0'], data[i][1]['state']['1']]
                    q = qubit(0)
                    bit = q.readState(qubitMeasured[0], qubitMeasured[1])
                    out.append(bit)
        return out

    def __store_key__(self, data):
        key = list()
        for i in range (len(data)):
            key.append(data[i])
        return key

    def __comparison_with_measurements__(self,data):   #1.2 (second step receiver)
        self.__debug_print__('\x1b[0;33;40m' + 'CC Received possibilities -> ' + str(data) + '\x1b[0m')
        #Compare the measured qubits with the 2 possibilities for each proposed by the sender
        self.receiverData["validation"] = self.__compare_qbits__(self.receiverData["measurements"],data)
        ret = self.receiverData["validation"]
        self.__debug_print__('\x1b[0;33;40m' + 'Decision : ' + str(self.receiverData["validation"]) + '\x1b[0m')
        test = self.receiverData["measurements"]
        #compute the secret key from the receiver's side
        key = self.__compute_secret__(data,self.receiverData["computed-basis"], self.receiverData["validation"])
        #store the key in self.key
        self.key = self.__store_key__(key)
        if len(self.key) > 2:
            s = hex(int(''.join(map(str, self.key)), 2))
        else:
            s = str(self.key)
        self.__info_print__('\x1b[0;33;40m' + 'Secret Key : ' + s + '\x1b[0m')
        return ret, 13

    def __waiting_synchro__(self, data):
        return None,3

    def __reverse_basis__(self, basis):
        """
        This function is used to reverse the basis to create the basis for the
        second possibility of qubit according to the protocol SARG04"
        """
        newBasis = list()
        for i in range(len(basis)):
            if basis[i] == 0:
                newBasis.append(1)
            else:
                newBasis.append(0)
        return newBasis

    def __list_of_possibilities__(self, value1, value2):
        """
        This function creates the list containing the possibility pair for each
        qubit using the two input lists.
        """
        assert len(value1) == len(value2)
        possibilities = list()
        tmp = list()
        #Create the possibility list with a pair of value for each qubit
        for i in range(len(value1)):
            possibilities.append([value1[i],value2[i]])
            tmp.append([value1[i],value2[i]])
        #Shuffle the position of the value for each pair
        for k in range(len(possibilities)):
            random.Random(11).shuffle(possibilities[k],random.random)
        return possibilities

    def __sending_possibilities__(self,data):      #2.1 (second step sender)
        self.senderData["data2"] = self.__generate_random_bits__(self.N)
        self.senderData["basis2"] = self.__reverse_basis__(self.senderData["basis"])
        #Create the first list of possibilities of qubits
        ret = self.__compute_photons__(self.senderData["data"],self.senderData["basis"])
        #Create the second list of possibilities of qubits
        ret2 = self.__compute_photons__(self.senderData["data2"],self.senderData["basis2"])
        #Create the list with the couple of possibilities ret and ret2
        ret3 = self.__list_of_possibilities__(ret,ret2)
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' -> CC : ' + str(ret3) + '\x1b[0m')
        return ret3, 22

    def __create_shared_key__(self, key, decision):
        """
        This function creat the shared key between the sender and the receiver
        by dropping or validating the key elements using the decision list.
        """
        assert len(key) == len(decision)
        sharedKey = list()
        for i in range (len(key)):
            if decision[i]  != 'x':
                sharedKey.append(key[i])
        return sharedKey

    def __results_reception__(self,data): #2.2 (third step sender)
        #get the info and the name of sender
        info = next(iter(data))
        name = next(iter(data[info]))
        #then get rid of the info and the name
        data = data[info][name]
        self.__debug_print__('\x1b[0;31;40m CC -> ' + str(self.eid) + ': ' + str(data) + '\x1b[0m')
        #Compute the Shared key between the sender and the receiver
        self.key = self.__create_shared_key__(self.senderData["data"],data)
        if len(self.key) > 2:
            s = hex(int(''.join(map(str, self.key)), 2))
        else:
            s = str(self.key)
        self.__info_print__('\x1b[0;31;40m' + str(self.eid) + ' Secret Key : ' + s + '\x1b[0m')
        return None, 3

    def __done__(self, data):
        return None, 3

    def __error__(self, data):
        return None, 4
