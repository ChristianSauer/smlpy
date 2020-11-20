import typing

from smlpy import errors
from enum import Enum
from loguru import logger
msg_start = "1b1b1b1b"
msg_end = "1b1b1b1b"
msg_version_1 = "01010101"

DATA_MIN_LEN = len(msg_start) + len(msg_version_1) + len(msg_end) + 8  # crc length etc.


class SmlState(Enum):
    START_SEQUENCE = 0
    VERSION = 1
    MSB_BODY = 2
    LIST = 3
    END_SEQUENCE = 98
    END_MSG = 99
    CLOSED = 100


class SmlReader:

    def __init__(self, data: str):
        self._data = data
        self._pointer = 0
        self._state = SmlState.START_SEQUENCE
        self.call_on_state_change = lambda state, dt: logger.info(f"State change: {dt} -> {state}")
        self._payload = {}
        if len(data) < DATA_MIN_LEN:
            raise AttributeError("data is to short!")

    def _advance(self, n_bytes: int) -> str:
        next_pos = self._pointer + n_bytes
        rv = self._data[self._pointer:next_pos]
        self._pointer = next_pos
        return rv

    def read(self):
        data = ""
        while True:
            data += self._advance(1)

            new_state, payload = self.handle_state(data, self._state)

            if new_state is not None and new_state != self._state:
                self.call_on_state_change(new_state, data)
                data = ""
                self._state = new_state
                self._payload = payload

            if self._state == SmlState.CLOSED:
                logger.info("sml parsing finished")
                break

    def handle_state(self, data: str, _state: SmlState, payload: typing.Dict) -> (SmlState, typing.Dict[str, object]):
        len_data = len(data)
        if _state == SmlState.START_SEQUENCE:
            if len_data == len(msg_start):
                if data == msg_start:
                    return SmlState.VERSION, {}
                else:
                    raise errors.InvalidStartSequence(msg_start, data)

        elif _state == SmlState.VERSION:
            if len_data == len(msg_version_1):
                if data == msg_version_1:
                    return SmlState.MSB_BODY, {}
                else:
                    raise errors.InvalidVersion(msg_version_1, data)

        elif _state == SmlState.MSB_BODY:
            # we expect a list first, indicated by "7"
            if data == "7":
                return SmlState.MSB_BODY, {}
            if len(data) == 2:
                expected_entries = int(data[1]) #  todo hex to int?
                return SmlState.LIST, {"expected_entries": expected_entries}
            else:
                raise Exception(f"unable to handle body: {data} from position {self._pointer}")
            # todo handle 8 special case
        elif _state == SmlState.LIST:
            if len(data) == 2:
                # first byte included the size
                length = int(data) # todo hex to int?
                logger.debug(f"{self._pointer} list entry with {length} bytes")

        else:
            raise Exception(f"unknown state {_state} from position {self._pointer}")

        return None, {}


