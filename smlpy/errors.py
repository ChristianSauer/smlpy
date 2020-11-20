class InvalidStartSequence(Exception):
    def __init__(self, expected, actual):
        super(InvalidStartSequence, self).__init__(f"the start sequence was not '{expected}' but '{actual}'")


class InvalidVersion(Exception):
    def __init__(self, expected, actual):
        super(InvalidVersion, self).__init__(f"the version sequence was not '{expected}' but '{actual}'")
