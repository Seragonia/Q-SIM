import sys
import importlib

INFO = True
DEBUG = True

class Protocol():
    """This class is used to run OTP. It uses a given QKD protocol to
    send a message, and manages the multiple run of this protocol to
    to have a secret of the given length

    Each core method returns a tuple (return value, next step).
    Return values:
    not None: to be sent over the network
    None: nothing to send
    -1: Message received"""

    def __init__(self, N, eid, eve=False, eveP=0, qkd=''):
        """
        @N : Number of qubit exchanged each second
        @protocol : Protocol of QKD to use.
        """
        self.protocol = importlib.import_module('utils.'+qkd).Protocol(N, eid, eve, eveP)
        self.isSender = False
        self.eid = eid
        self.N = N
        self.QKD = self.protocol.__get_states_mapping__()
        self.state = 0
        #A dictionary of all messages to send
        self.sD = []
        #A dictionary of all messages received
        self.rD = []
        #Shared secret stack
        self.secret = []
        self.outputs = {
            "n1": 0,
            "n2": 0,
            "n3": 0,
            "n4": 0,
            "n5": 0,
            'n6': 3600, #Min latency Time (second) per round of message sending
            'n7': 0, #Max latency Time (second) per round of message sending
        }
        self.eve = eve
        self.eveP = eveP
        self.elapsed_time = 0
        return

    def __get_states_mapping__(self):
        """
        State, used to know what to do when receiving data.
        """
        return { 0:  self.__IDLE__,
                 1:  self.__start_receiver__, #Receiver : receive a message indicating to start key sharing process
                 2:  self.__start_sender__, #Sender : Need to send a message and start to send a first QKD exchange
                 12: self.__secret_gen__,   #setup the secret (receiver of qkd loop)
                 22: self.__qkd_loop__,     #run qkd loop to create a secret
                 13: self.__receive_message__, #Receive the message and decrypt it with the secret
                 23: self.__send_message__, #Send the message using the shared secret
                 3:  self.__done__ }

    def __debug_print__(self, msg):
        if DEBUG is True:
            print('[DEBUG] : ' + msg, file=sys.stdout, flush=True)
        return

    def __info_print__(self, msg):
        if INFO is True:
            print('[INFO] : ' + msg, file=sys.stdout, flush=True)
        return

    def __update_outputs__(self, error = 0):
        self.outputs["n1"] += 3
        self.outputs["n4"] += self.N
        self.outputs["n5"] += (self.N - len(self.protocol.key))
        self.outputs["n2"] += error
        self.outputs["n6"] = min(self.elapsed_time, self.outputs["n6"])
        self.outputs["n7"] = max(self.elapsed_time, self.outputs["n7"])
        return
    def __update_undetected_error__(self, message):
        '''
        Checks whether the message is a valid float or not.
        Used for simulation outputs
        '''
        try:
            float(message)
            return
        except ValueError:
            self.outputs["n3"] += 1
            return

    def __add_message__(self, message):
        self.__info_print__(str(self.eid) + ' add message to be send: ' + message)
        self.sD.append({"msg": message, "length": len(message)})
        return

    def __str_to_bits__(self, text):
        bits = bin(int.from_bytes(text.encode(), 'big'))[2:]
        return list(map(int, bits.zfill(8 * ((len(bits) + 7) // 8))))

    def __str_from_bits__(self, bits):
        if len(bits) == 1:
            return bits[0]
        elif len(bits) == 0:
            return ''
        n = int(''.join(map(str, bits)), 2)
        return n.to_bytes((n.bit_length() + 7) // 8, 'big').decode('latin-1')

    def __Encryption__(self, message, key):
        out = []
        for msg, k in zip(message, key):
            out.append(int(msg)^int(k))
        return out

    def __get_message_or_response__(self, data):
        '''
        Since every response message looks like {'response': {'Entity': ...}}
        We need to have an abstract method to retrieve these messages
        '''
        if data and 'response' in data:
            name = next(iter(data['response']))
            return data['response'][name]
        else:
            return data

    def __IDLE__(self, data=None):
        """
        If data exists, then OTP will (re)start as the receiver.
        If data is None, OTP will start as the sender of the secret.
        Return next step to do
        """
        self.outputs["n6"] = 3600
        self.outputs["n7"] = 0
        if len(self.sD) != 0:
            return self.__start_sender__(data)
        else:
            return self.__start_receiver__(data)

    def __qkd__(self, data): #runs next step of bb84
        ret, self.state = self.QKD[self.state](data)
        return ret

    def __start_receiver__(self, data):
        """
        @data : encapsulated message with QKD request.
        """
        self.isSender = False
        self.state = 0
        self.elapsed_time += 1
        self.rD.append({"msg": '', "length": data['otpl']})
        if len(self.secret) >= data['otpl']*8:
            return self.__receive_message__(data)
        else:
            qkd = self.__qkd__(data['qkd'])
            return {"otp": "", "qkd": qkd}, 12 #__secret_gen__

    def __start_sender__(self, data):
        """
        @data : message to send
        """
        #Send the first message via classical channel
        #Send the length N of a message plus the first round of QKD
        """
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        | Length N of the message |  First round of QKD |
        +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
        """
        self.isSender = True
        self.state = 0
        self.elapsed_time += 1
        if len(self.secret) >= len(self.sD[0]['msg'])*8:
            return self.__send_message__(None) #Send message directly
        else:
            qkd = self.__qkd__(data)
            return {"otpl": len(self.sD[0]['msg']), "qkd": qkd}, 22 #__qkd_loop__

    def __secret_gen__(self, data):
        self.elapsed_time += 1
        if self.state == 3:
            self.secret.extend(self.protocol.key)
            self.__update_outputs__()
        #If an error occured, we do not store this secret
        if self.state == 4:
            self.__update_outputs__(1)
        if self.state in [3,4] and len(self.secret)/8 < self.rD[0]["length"]: #end of QKD process
            if data is None:
                return {"otp": '', "qkd": ''}, 12 #__secret_gen__
            self.state = 0
            qkd = self.__qkd__(self.__get_message_or_response__(data)['qkd'])
            return {"otp": '', "qkd": qkd}, 12 #__secret_gen__

        elif self.state > 10: #intermediate states are over 10
            qkd = self.__qkd__(self.__get_message_or_response__(data)['qkd'])
            return {"otp": '', "qkd": qkd}, 12 #__secret_gen__
        else:
            return None, 13 #__receive_message__


    def __qkd_loop__(self, data):
        """
        Do QKD until the shared secret stack is large enough to perform OTP
        """
        self.elapsed_time += 1
        if self.state == 3:
            self.secret.extend(self.protocol.key)
            self.__update_outputs__()
        #If an error occured, we do not store this secret
        if self.state == 4:
            self.__update_outputs__(1)
        if self.state in [3,4] and len(self.secret)/8 < len(self.sD[0]['msg']):
            self.state = 0
            qkd = self.__qkd__(None) #to start QKD as sender
            return {"otp": 1, "qkd": qkd}, 22 #__qkd_loop__
        elif self.state > 10: #intermediate states are over 10
            qkd = self.__qkd__({'response': {self.eid: self.__get_message_or_response__(data)['qkd']}})
            return {"otp": 0, "qkd": qkd}, 22 #__qkd_loop__
        else:
            return None, 23 #__send_message__

    def __send_message__(self, data):
        """
        Use the shared secret to perform OTP over the message to be sent
        First convert the message into binary format, then xor it using the secret
        """
        self.elapsed_time += 1
        msg = self.sD.pop(0)
        bits = self.__str_to_bits__(msg['msg'])
        otp = self.__Encryption__(bits, self.secret)
        #We need to delete the part of the shared secret stack used
        self.secret = self.secret[len(bits):]
        self.state = 0
        #Sending encrypted message
        return {"otpl": len(otp)/8, "otp": otp, "control": -2}, 3

    def __receive_message__(self, data):
        self.elapsed_time += 1
        #If data is None, wait until data is received
        if data is None:
            return None, 13
        #First decrypt the message
        data = self.__get_message_or_response__(data)
        self.rD[0]['msg'] = self.__str_from_bits__(self.__Encryption__(data['otp'], self.secret))
        #Then delete shared key used
        self.secret = self.secret[len(data['otp']):]
        self.__info_print__(str(self.eid) + ' received message: ' + str(self.rD[0]['msg']))
        #check if it is an undetected error by checking if this message is a valid float
        self.__update_undetected_error__(self.rD[0]['msg'])
        #remove the first received message
        self.rD.pop(0)
        #resetting the Quantum Protocol state
        self.state = 0
        return -1, 3 #Message received.

    def __done__(self, data):
        self.elapsed_time = 0
        if data and 'response' in data or data and 'otpl' in data: #restart as a receiver
            return self.__start_receiver__(self.__get_message_or_response__(data))
        elif len(self.sD) >0: #restart as sender
            return self.__start_sender__(None)
        return None,3
