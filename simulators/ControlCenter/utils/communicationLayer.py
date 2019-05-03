class comLayer():
    """
    Module (class) used by each entity to automatically allow the rapid addition of new protocols
    Takes as input the different states of a protocol (its state machine) and the functions associated with these states.
    Is used by simulators to update their status and automatically call the right functions in "step".
    """
    def __init__(self,protocol,states):
        self.__state__ = 0    #0 is always the first state
        self.protocol = protocol
        self.states = states

    def __doStep__(self, data):
        ret, self.__state__ = self.states[self.__state__](data)
        return ret

    def __add_message_to_be_send__(self, message):
        self.protocol.__add_message__(message)
        return
