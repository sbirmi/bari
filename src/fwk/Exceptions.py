class InvalidDataException(Exception):
    def __init__(self, explanation, data):
        Exception.__init__(self, explanation + ": " + str(data))
        self.explanation = explanation
        self.data = data

    def toJmsg(self):
        return [self.explanation, str(self.data)]
