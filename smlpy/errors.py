class SmlReaderException(Exception):
    def __init__(self, message):
        super(SmlReaderException, self).__init__(message)


class InvalidStartSequence(SmlReaderException):
    def __init__(self, expected, actual):
        super(InvalidStartSequence, self).__init__(
            f"the start sequence was not '{expected}' but '{actual}'"
        )


class InvalidVersion(SmlReaderException):
    def __init__(self, expected, actual):
        super(InvalidVersion, self).__init__(
            f"the version sequence was not '{expected}' but '{actual}'"
        )


class InvalidData(SmlReaderException):
    def __init__(self, position, expected, actual):
        super(InvalidData, self).__init__(
            f"the hex sequence at {position} was not '{expected}' but '{actual}'"
        )


class MissingValueInfoException(SmlReaderException):
    def __init__(self):
        super(MissingValueInfoException, self).__init__(
            f"Both scaler and value must be set to be able to compute a value"
        )


class DataMissingException(SmlReaderException):
    def __init__(self, next_pos, len_data):
        super(DataMissingException, self).__init__(
            f"attempted to read position {next_pos}, but the sml file is only {len_data} long"
        )


class NotAListException(SmlReaderException):
    def __init__(self, pos):
        super(NotAListException, self).__init__(f"expected a list at {pos}")
