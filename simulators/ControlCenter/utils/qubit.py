from random import randint
from math import pow, sqrt
from numpy import matrix


class qubit():
    """
    This class represents a qubit, and is used to run QKD
    """
    def __init__(self,data):
        #the state corresponds to the random "data", not the basis
        #if state == 1, (e_1)^+ = (0, 1)
        #else, (e_0)^+ = (1, 0)
        if data:
            self.state = matrix([[0],[1]])
        else:
            self.state = matrix([[1],[0]])
        #Hadamard value corresponds to the random "basis"
        #The two basis are computed here and will be used to update the state
        self.Hbasis = (1/sqrt(2))*matrix([[1,1],[1,-1]]) #const

    def measure(self, basis):
        #The receiver measures the received qubit after changing its value with
        #its random basis. As a result, he will measure the right bit only if he
        #chose the same basis as the sender. If the basis is different, the measured
        #value will be different.

        #{1,0} + b = 0 -> 0
        #{0,1} + b = 0 -> 1
        #{1/sqrt(2),-1/sqrt(2)} + b = 1 -> 1
        #{1/sqrt(2),1/sqrt(2)} + b = 1 -> 0
        #others : random

        #print(round(self.state.item(0),1))
        if self.state.item(0) == 1 and self.state.item(1) == 0 and basis == 0:
            return 0
        elif self.state.item(0) == 0 and self.state.item(1) == 1 and basis == 0:
            return 1
        elif self.state.item(0) == 0.7 and self.state.item(1) == -0.7 and basis == 1:
            return 1
        elif self.state.item(0) == 0.7 and self.state.item(1) == 0.7 and basis == 1:
            return 0
        else:
            return randint(0,1)

    def readState(self, val1, val2):
        if val1 == 1 and val2 == 0:
            return 0
        if val1 == 0 and val2 == 1:
            return 1
        if val1 == 0.7 and val2 == 0.7:
            return 0
        if val1 == 0.7 and val2 == -0.7:
            return 1

    def hadamard(self):
        self.state = self.Hbasis*self.state

    def serialize(self):
        """This function serialize a qubit as follow :
        {'state' : self.state}
        """
        return {'state': {'0': round(self.state.item(0),1), '1': round(self.state.item(1),1)}}
