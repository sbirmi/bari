class Dirty7Exception(Exception):
    pass

class InvalidPlayException(Exception):
    def __init__(self, data):
        """data : str"""
        Exception.__init__(self, data)
        self.data = data

    def toJmsg(self):
        return [self.data]
