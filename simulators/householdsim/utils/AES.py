from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from base64 import b64encode, b64decode
from Crypto.Util.Padding import pad, unpad
import sys
import importlib

INFO = False
DEBUG = False

class Protocol():
    """This class is used to run AES. It uses a given QKD protocol to
    send a message, and manages the multiple run of this protocol to
    to have a secret of 128 bits

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
        self.BLOCK_SIZE = 64
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
            print('\x1b[0;31;40m' + '[DEBUG] : ' + msg + '\x1b[0m', file=sys.stdout, flush=True)
        return

    def __info_print__(self, msg):
        if INFO is True:
            print('\x1b[0;31;40m' + '[INFO] : ' + msg + '\x1b[0m', file=sys.stdout, flush=True)
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
        self.sD.append({"msg": message, "length": len(message)})
        return

    def __str_from_bits__(self, bits):
        if len(bits) == 1:
            return bits[0]
        elif len(bits) == 0:
            return ''
        n = int(''.join(map(str, bits)), 2)
        return n.to_bytes((n.bit_length() + 7) // 8, 'big').decode('latin-1')

    def bitsToBytes(self, a):
        a = [0] * (8 - len(a) % 8) + a # adding in extra 0 values to make a multiple of 8 bits
        s = ''.join(str(x) for x in a)[::-1] # reverses and joins all bits
        returnInts = []
        for i in range(0,len(s),8):
            returnInts.append(bytes([int(s[i:i+8],2)])) # goes 8 bits at a time to save as ints
        return returnInts

    def __Encryption__(self, message, bits):
        k = b''.join(self.bitsToBytes(bits[:255]))
        cipher = AES.new(k, AES.MODE_ECB)
        ciphertext = cipher.encrypt(pad(str.encode(message),self.BLOCK_SIZE))
        return b64encode(ciphertext).decode('utf-8')

    def __Decryption__(self, ciphertext, bits):
        k = b''.join(self.bitsToBytes(bits[:255]))
        cipher = AES.new(k, AES.MODE_ECB)
        try:
            plaintext = unpad(cipher.decrypt(b64decode(ciphertext)),self.BLOCK_SIZE)
            p = plaintext.decode('utf-8')
        except ValueError:
            #bad message received, update the output value accordingly
            self.outputs["n3"] += 1
            p = 'error'
        return p


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
        If data exists, then AES will (re)start as the receiver.
        If data is None, AES will start as the sender of the secret.
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
        self.elapsed_time += 1
        self.isSender = False
        self.state = 0
        self.rD.append({"msg": '', "length": data['aesl']})
        if len(self.secret) >= 255:
            return self.__receive_message__(data)
        else:
            qkd = self.__qkd__(data['qkd'])
            return {"aes": "", "qkd": qkd}, 12 #__secret_gen__

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
        self.elapsed_time += 1
        self.isSender = True
        self.state = 0

        if len(self.secret) >= 255:
            return self.__send_message__(None) #Send message directly
        else:
            qkd = self.__qkd__(data)
            return {"aesl": len(self.sD[0]['msg']), "qkd": qkd}, 22 #__qkd_loop__

    def __secret_gen__(self, data):
        self.elapsed_time += 1
        if self.state == 3:
            self.secret.extend(self.protocol.key)
            self.__update_outputs__()
        #If an error occured, we do not store this secret
        if self.state == 4:
            self.__update_outputs__(1)
        if self.state in [3,4] and len(self.secret) < 255: #end of QKD process
            if data is None:
                return {"aes": '', "qkd": ''}, 12
            self.state = 0
            qkd = self.__qkd__(self.__get_message_or_response__(data)['qkd'])
            return {"aes": '', "qkd": qkd}, 12 #__secret_gen__

        elif self.state > 10:
            qkd = self.__qkd__(self.__get_message_or_response__(data)['qkd'])
            return {"aes": '', "qkd": qkd}, 12 #__secret_gen__
        else:
            return None, 13 #__receive_message__


    def __qkd_loop__(self, data):
        """
        Do QKD until the shared secret stack is large enough to perform AES
        """
        self.elapsed_time += 1
        if self.state == 3:
            self.secret.extend(self.protocol.key)
            self.__update_outputs__()
        #If an error occured, we do not store this secret
        if self.state == 4:
            self.__update_outputs__(1)
        if self.state in [3,4] and len(self.secret) < 255:
            self.state = 0
            qkd = self.__qkd__(None) #to start BB84 as sender
            return {"aes": 1, "qkd": qkd}, 22 #__qkd_loop__
        elif self.state > 10:
                qkd = self.__qkd__({'response': {self.eid: self.__get_message_or_response__(data)['qkd']}})
                return {"aes": 0, "qkd": qkd}, 22 #__qkd_loop__
        else:
            return None, 23 #__send_message__

    def __send_message__(self, data):
        """
        Use the shared secret to perform AES over the message to be sent
        """
        self.elapsed_time += 1
        msg = self.sD.pop(0)
        aes = self.__Encryption__(msg['msg'], self.secret)
        #We need to delete the part of the shared secret stack used
        self.secret = self.secret[255:]
        self.state = 0
        #Sending encrypted message
        return {"aesl": len(msg['msg']), "aes": aes, "control": -2}, 3

    def __receive_message__(self, data):
        self.elapsed_time += 1
        #If dara is None, wait until data is received
        if data is None:
            return None, 13
        #First decrypt the message
        data = self.__get_message_or_response__(data)
        self.rD[0]['msg'] = self.__Decryption__(data['aes'], self.secret)
        #Then delete shared key used
        self.secret = self.secret[255:]
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
        if data and 'response' in data or data and 'aesl' in data: #restart as a receiver
            return self.__start_receiver__(self.__get_message_or_response__(data))
        elif len(self.sD) >0: #restart as sender
            return self.__start_sender__(None)
        return None,3
