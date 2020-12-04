class InvalidStartSequence(Exception):
    def __init__(self, expected, actual):
        super(InvalidStartSequence, self).__init__(f"the start sequence was not '{expected}' but '{actual}'")


class InvalidVersion(Exception):
    def __init__(self, expected, actual):
        super(InvalidVersion, self).__init__(f"the version sequence was not '{expected}' but '{actual}'")


class InvalidData(Exception):
    def __init__(self, position, expected, actual):
        super(InvalidData, self).__init__(f"the hex sequence at {position} was not '{expected}' but '{actual}'")


class MissingValueInfoException(Exception):
    def __init__(self):
        super(MissingValueInfoException, self).__init__(f"Both scaler and value must be set to be able to compute a value")
