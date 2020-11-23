import typing

import yaml
import pathlib
from smlpy import errors
from enum import Enum
from loguru import logger

OPEN_RESPONSE = "630101"

msg_start = "1b1b1b1b"
msg_end = "1b1b1b1b"
msg_version_1 = "01010101"

DATA_MIN_LEN = len(msg_start) + len(msg_version_1) + len(msg_end) + 8  # crc length etc.

obis_path = pathlib.Path(__file__).parent / "obis_t_kennzahlen.yaml"

with obis_path.open() as f:
    obis_t_kennzahlen = yaml.safe_load(f)["kennzahlen"]


class SmlState(Enum):
    START_SEQUENCE = 0
    VERSION = 1
    MSB_BODY = 2
    MESSAGE = 3
    PublicOpenResponse = 4
    END_SEQUENCE = 98
    END_MSG = 99
    CLOSED = 100


class SmlFile:
    def __init__(self):
        self.data = []

    data: typing.List[dict]


class SmlReader:

    def __init__(self, data: str):
        self._data = data
        self._pointer = 0
        self._state = SmlState.START_SEQUENCE
        self.call_on_state_change = lambda state, dt: logger.info(f"State change: {dt} -> {state}")
        self._payload = {}
        self.result = {}
        self.has_public_open_response_data = False
        self.message = SmlFile()

        if len(data) < DATA_MIN_LEN:
            raise AttributeError("data is to short!")

    def _advance(self, n_chars: int) -> str:
        next_pos = self._pointer + n_chars
        len_data = len(self._data)
        if next_pos > len_data:
            raise Exception(f"attempted to read position {next_pos}, but the sml file is only {len_data} long")
        rv = self._data[self._pointer:next_pos]
        self._pointer = next_pos
        return rv

    def read2(self):
        while self._state != SmlState.CLOSED:
            new_state = self.handle_state2()

    def handle_state2(self):
        if self._state == SmlState.START_SEQUENCE:
            data = self._advance(len(msg_start))
            if data == msg_start:
                self._state = SmlState.VERSION
            else:
                raise errors.InvalidStartSequence(msg_start, data)

        elif self._state == SmlState.VERSION:
            data = self._advance(len(msg_version_1))
            if data == msg_version_1:
                self._state = SmlState.MSB_BODY
            else:
                raise errors.InvalidVersion(msg_version_1, data)

        elif self._state == SmlState.MSB_BODY:
            # we expect a message body
            data = self._advance(2)
            if data.startswith("76"):
                self._state = SmlState.MESSAGE
            else:
                raise Exception(f"unable to handle body: {data} from position {self._pointer}")
            # todo handle 8 special case
        elif self._state == SmlState.MESSAGE:
            # first byte included the size
            # a message has transactionId, groupNo, abortOnError, messagebody, crc16, endOfSmlMsg ,
            # see https://www.bsi.bund.de/SharedDocs/Downloads/DE/BSI/Publikationen/TechnischeRichtlinien/TR03109/TR-03109-1_Anlage_Feinspezifikation_Drahtgebundene_LMN-Schnittstelle_Teilb.pdf?__blob=publicationFile page17

            len_transaction_id = hex_to_int_byte(
                self._advance(2)) - 2  # -2 because the first byte is included in the length
            self._advance(len_transaction_id)

            self._advance(4)  # ignore groupNo
            self._advance(4)  # ignore abortOnError

            data = self._advance(2)

            if data != "72":  # messagebody
                raise Exception("invalid state, should be messagebody")

            data = self._advance(len(OPEN_RESPONSE))

            # if data != OPEN_RESPONSE:
            #    raise Exception("invalid state, should be OPEN_RESPONSE")

            data = self._advance(1)

            self._state = SmlState.PublicOpenResponse if not self.has_public_open_response_data else SmlState.MESSAGE  # todo correct?

            if data == "7" and self._state == SmlState.PublicOpenResponse:
                self.handle_public_open_response()
                self._state = SmlState.MSB_BODY
            elif data == "7":
                next_list = {}
                self.message.data.append(next_list)
                self.handle_list(next_list)
            else:
                raise Exception("invalid state, should be OPEN LIST")
        else:
            raise Exception(f"unknown state {self._state} from position {self._pointer}")

        return None

    def handle_public_open_response(self):
        """
        public open response is a weird mandatory header message
        :return:
        """
        length_info = self._advance(1)  # second nibble contains the length of the entry:
        length_info = hex_to_int(length_info)  # in elements
        logger.debug(f"List with {length_info} elements")
        if length_info != 6:
            raise Exception("public open response should have length 6")
            # empty entry, ignore
        else:
            data = {}
            self._advance(4)  # skipping to optional fields
            entry = self._advance(2)
            length = hex_to_int_byte(entry)
            req_file_id = self._advance(length - 2)

            entry = self._advance(2)
            length = hex_to_int_byte(entry)
            server_id = self._advance(length - 2)

            data["reqFileId"] = octet_to_str(req_file_id)
            data["serverId"] = octet_to_str(server_id)

            self._advance_until_message_end()
            self.message.data.append(data)

        self.has_public_open_response_data = True

    def handle_list(self, data_container: dict, length_info: typing.Optional[str] = None, ):
        if not length_info:
            length_info = self._advance(1)  # second nibble contains the length of the entry:

        length_info = hex_to_int(length_info)  # in elements
        logger.debug(f"List with {length_info} elements")
        if length_info <= 1:
            logger.info("list empty")
            # empty entry, ignore
        if length_info == 2:
            # special case: runtime! e.g. time this thing runs
            self._extract_runtime_information(data_container)
        else:
            for i in range(length_info):
                entry = self._advance(2)

                if entry == "01":  # optional / empty entry
                    continue
                elif entry in ["62", "63", "65", "69"]:  # unsigned int
                    advance = {
                        "62": 1,
                        "63": 2,
                        "65": 3,
                        "69": 4
                    }
                    data = self._advance(advance[entry])
                    value = int.from_bytes(bytes.fromhex(data), "big", signed=False)
                    data_container[str(i)] = value
                elif entry in ["52", "53", "55", "59"]:  # int
                    raise NotImplementedError()
                elif entry in ["42"]:  # bool
                    raise NotImplementedError()
                elif entry[0] == "7":  # list
                    inner_data = {}
                    data_container[str(i)] = inner_data
                    self.handle_list(inner_data, entry[1])
                else:
                    # octet
                    length = hex_to_int_byte(entry)
                    data = self._advance(length - 2)
                    data_container[str(i)] = octet_to_str(data)

    def _extract_runtime_information(self, data_container: dict):
        self._advance(4)  # ignore secIndex for now, always assume a linux timestamp
        type_info = self._advance(2)
        if type_info != "65":
            raise Exception(f"{self._pointer}: here should be a uint32 (hex: 65) but it is {type_info}")
        data = self._advance(4*2)
        value = int.from_bytes(bytes.fromhex(data), "big", signed=False)
        runtime_days = value / 60 / 60 / 24

        data_container["runtime_days"] = runtime_days
        data_container["runtime_seconds"] = value

    def __repr__(self):
        if self._pointer > 10:
            return f"{self._data[self._pointer - 10:self._pointer]} || {' '.join(chunks(self._data[self._pointer:], 2))}"
        else:
            return self._data

    def _advance_until_message_end(self):
        data = ""
        while data != "00":
            data = self._advance(2)


def hex_to_int_byte(byte: str) -> int:
    return hex_to_int(byte) * 2


def hex_to_int(byte: str) -> int:
    return int(byte, 16)


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def octet_to_str(bytes: str) -> str:
    return "".join([chr(int(x, 16)) for x in chunks(bytes, 2)])
