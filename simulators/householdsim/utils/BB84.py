from utils.qubit import qubit
import random
from numpy import matrix
from math import pow
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
            "basis": []           #Random Basis used by the receiver for a given sender
        }

        self.receiverData = {
            "received-qubits": [], #Received qubit
            "computed-basis": []  #Random Basis used by the receiver for a given sender
        }
        #Common values :
        self.commonQubits = []
        self.key = [] #secret shared
        self.eve = eve
        self.eveP = eveP
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
                 12: self.__common_basis_wait__,
                 21: self.__basis_wait__,
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

    def __compare_basis__(self, basis):
        """
        Compares basis and compute secret key
        """
        ret = list()
        i = 0
            #if CC basis = 0 and House basis = 0 -> 0
            #if CC basis = 1 and House basis = 1 -> 1
            #if CC basis = 0 and House basis = 1 -> x
            #if CC basis = 1 and House basis = 0 -> x
        for value in basis['response']:
            if value != self.senderData["basis"][i]:
                ret.append('x')
            else:
                ret.append(value)
                self.key.append(self.senderData["data"][i])
            i = i+1
        return ret

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

    def __shared_key__(self, data, common):
        key = list()
        for i in range(len(data)):
            if common[i] != 'x':
                key.append(data[i])
        return key

    def __IDLE__(self, data=None):
        """
        If data is true, then QKD will (re)start as the receiver.
        If data is false, QKD will start as the sender of the secret.
        Return next step to do
        """
        self.key = []
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
        return self.receiverData["computed-basis"], 21

    def __start_sender__(self, data):
        self.senderData["data"]  = self.__generate_random_bits__(self.N)
        self.senderData["basis"] = self.__generate_random_bits__(self.N)
        ret = self.__compute_photons__(self.senderData["data"], self.senderData["basis"])
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' -> CC : ' + str(ret) + '\x1b[0m')
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' random key : ' + str(self.senderData["data"]) + '\x1b[0m')
        #return value to the simulator, and next step value
        return ret, 12

    def __get_verification_length__(self, keyLength):
        val = (VERIFICATION*keyLength)/100
        if val < 1:
            return 1
        else:
            return int(val)

    def __common_basis_wait__(self, data):
        assert data and 'response' in data #should never be false
        #get the name of sender
        name = next(iter(data['response']))
        #then get rid of the name
        data['response'] = data['response'][name]
        self.commonQubits = self.__compare_basis__(data)
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' Basis : ' + str(self.senderData["basis"]) + '\x1b[0m')
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' Common basis -> CC : ' + str(self.commonQubits) + '\x1b[0m')
        verif = self.__get_verification_length__(len(self.key))
        ret = {'common': self.commonQubits, 'key-verification': self.key[:verif], 'id': self.eid}

        #If Eve, change the secret key value with eveP probability
        #This step allows you to change the value of the start of the key to be sent,
        #and to change the secret key value
        if self.eve == True:
            if random.random()<self.eveP:
                self.key = self.__generate_random_bits__(len(self.key))
                tmp = ret['key-verification'] #used to check if the new key is different
                ret['key-verification'] = self.__generate_random_bits__(verif)
                self.__debug_print__('\x1b[0;33;31m' + str(self.eid) + ' Eve interception : ' + str(ret) + '\x1b[0m')
                if tmp != ret['key-verification']:
                    self.error = True

        #key is the last n-VERIFICATION bits of the initial key:
        self.key = self.key[verif:]
        if len(self.key) > 2:
            s = hex(int(''.join(map(str, self.key)), 2))
        else:
            s = str(self.key)
        self.__debug_print__('\x1b[0;31;40m' + str(self.eid) + ' Secret Key : ' + s + '\x1b[0m')
        if not self.error:
            return ret, 3
        else:
            return ret, 4

    def __basis_wait__(self, data):
        if data is None:
            return None, 3
        #here, we just received common basis, need to check
        self.commonQubits = data['common']
        #compute the shared key using this information
        self.key = self.__shared_key__(self.receiverData["received-qubits"], self.commonQubits)
        keyVerif = data['key-verification']
        verif = self.__get_verification_length__(len(self.key))
        key = self.key[:verif]
        self.key = self.key[verif:]
        if key == keyVerif and not self.error:
            if len(self.key) > 2:
                s = hex(int(''.join(map(str, self.key)), 2))
            else:
                s = str(self.key)
            self.__info_print__('\x1b[0;33;40m' + data['id'] + ' Secret key ('+ str(100*(pow(0.75, verif))) + '% chance that there was a MITM), ('+ str(len(self.key)) +' bits): ' + s + '\x1b[0m')
            return None, 3
        else:
            if len(self.key) > 1:
                val = hex(int(''.join(map(str, self.key)), 2))
            else:
                val = '0x'
            self.__info_print__('\x1b[0;33;40m' + data['id'] + ' Key is invalid! MITM detected ('+ str(100*(1-pow(0.75, verif))) + '% sure): '+ val +' \x1b[0m')
            return None, 4

    def __done__(self, data):
        return None, 3

    def __error__(self, data):
        return None, 4
