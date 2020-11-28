import typing

import yaml
import pathlib
from smlpy import errors, units
from enum import Enum
from loguru import logger

OPEN_RESPONSE = "630101"

msg_start = "1b1b1b1b"
msg_end = "1b1b1b1b"
msg_version_1 = "01010101"

DATA_MIN_LEN = len(msg_start) + len(msg_version_1) + len(msg_end) + 8  # crc length etc.

obis_path = pathlib.Path(__file__).parent / "../obis_t_kennzahlen.yaml"

with obis_path.open() as f:
    obis_t_kennzahlen = yaml.safe_load(f)["kennzahlen"]

# from the type-length definition, first tuple is byte length, second is signed
_integer_hex_marker = {
                "62": (1, False),
                "63": (2, False),
                "65": (4, False),
                "69": (8, False),
                "52": (1, True),
                "53": (2, True),
                "55": (4, True),
                "56": (5, True),  # this unit is not described by the current standards, but my ehz-k reports them
                "59": (8, True),
            }


class SmlState(Enum):
    START_SEQUENCE = 0
    VERSION = 1
    MSB_BODY = 2
    MESSAGE = 3
    PublicOpenResponse = 4
    END_SEQUENCE = 98
    END_MSG = 99
    CLOSED = 100


class SmlMessage:
    def __init__(self, type: str):
        self.type = type
        self.data = []

    def __repr__(self):
        return f"{self.type} with {len(self.data)} entries"


class SmlFile:
    def __init__(self):
        self.data = []

    data: typing.List[SmlMessage]

    def __repr__(self):
        return f"SmlFile with {len(self.data)} entries"


class SmlReader:

    def __init__(self, data: str):
        self._data = data
        self._pointer = 0
        self._state = SmlState.START_SEQUENCE
        self.call_on_state_change = lambda state, dt: logger.info(f"State change: {dt} -> {state}")
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
            self.handle_state2()

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
                next_list = SmlMessage("SML_GetList.Res")
                self.message.data.append(next_list)
                # self.handle_list(next_list)
                self.handle_getlist(next_list)
                self._handle_value_field()  # listSignature
                self._handle_value_field()  # actGatewayTime
                self._advance_until_message_end() # todo this is WRONG to do,
                self._state = SmlState.MSB_BODY
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
        list_length = self._advance(1)  # second nibble contains the length of the entry:
        list_length = hex_to_int(list_length)  # in elements
        logger.debug(f"List with {list_length} elements")
        if list_length != 6:
            raise Exception("public open response should have length 6")
            # empty entry, ignore
        else:
            data = SmlMessage("SML_PublicOpen.Res")

            for i in range(list_length):
                self._handle_data_field(data)

            self._advance_until_message_end()
            self.message.data.append(data)

        self.has_public_open_response_data = True

    def handle_list(self, data_container: SmlMessage, list_length: typing.Optional[str] = None, ):
        if not list_length:
            list_length = self._advance(1)  # second nibble contains the length of the entry:

        list_length = hex_to_int(list_length)  # in elements
        logger.debug(f"List with {list_length} elements")
        if list_length <= 1:
            logger.info("list empty")
            # empty entry, ignore
        if list_length == 2:
            # special case: runtime! e.g. time this thing runs
            data_container.type = "SML_Time"
            self._extract_runtime_information(data_container)
        else:
            for _ in range(list_length):
                self._handle_data_field(data_container)

    def _handle_data_field(self, data_container):
        entry = self._advance(2)

        if entry == "01":  # optional / empty entry
            data_container.data.append(None)
        elif entry in ["62", "63", "65", "69"]:  # unsigned int
            advance = {
                "62": 1,
                "63": 2,
                "65": 3,
                "69": 4
            }
            data = self._advance(advance[entry])
            value = int.from_bytes(bytes.fromhex(data), "big", signed=False)
            data_container.data.append(value)
        elif entry in ["52", "53", "55", "59"]:  # int
            raise NotImplementedError()
        elif entry in ["42"]:  # bool
            raise NotImplementedError()
        elif entry[0] == "7":  # list
            inner_data = SmlMessage("SML_GetList.Res")
            data_container.data.append(inner_data)
            self.handle_list(inner_data, entry[1])
        else:
            # octet

            string = self._handle_octet_string(entry)
            data_container.data.append(string)

    def _handle_value_field(self):
        entry = self._advance(2)

        if entry == "01":  # optional / empty entry
            return None
        elif entry in _integer_hex_marker.keys():  # integer
            length, signed = _integer_hex_marker[entry]
            data = self._advance(length * 2)
            value = int.from_bytes(bytes.fromhex(data), "big", signed=signed)
            return value
        elif entry in ["42"]:  # bool
            raise NotImplementedError()
        elif entry[0] == "7":  # list
            raise Exception("unexpected")
        else:
            # octet
            string = self._handle_octet_string(entry)
            return string

    def _handle_octet_string(self, entry) -> typing.Optional[str]:
        if entry == "01":  # optional / empty entry
            return None

        if leading_bit_set(entry[0]):  # significant bit set
            next_byte = self._advance(2)
            first = hex_to_binary_with_leading_zeroes(entry[1])
            second = hex_to_binary_with_leading_zeroes(str(int(next_byte)))
            binary = f"{first}{second}"
            length = int(binary, 2)
            data = self._advance(length * 2 - 4)
        else:
            length = hex_to_int_byte(entry)
            data = self._advance(length - 2)

        if data.lower().endswith("ff") and len(data) == 12:
            # most likely a weird obis number
            obis = f"{hex_to_int(data[0:2])}-{hex_to_int(data[2:4])}.{hex_to_int(data[4:6])}.{hex_to_int(data[6:8])}.{int(hex_to_int(data[8:]) / 255)}"
            return obis
        else:
            value = octet_to_str(data)
            return value

    def _extract_runtime_information(self, data_container: SmlMessage):
        data = self._advance(4)  # ignore secIndex for now, always assume a linux timestamp
        data_container.data.append(data)
        type_info = self._advance(2)
        if type_info != "65":
            raise Exception(f"{self._pointer}: here should be a uint32 (hex: 65) but it is {type_info}")
        data = self._advance(4 * 2)
        value = int.from_bytes(bytes.fromhex(data), "big", signed=False)
        # runtime_days = value / 60 / 60 / 24

        # data_container.data["runtime_days"] = runtime_days
        # data_container.data["runtime_seconds"] = value
        data_container.data.append(value)

    def __repr__(self):
        if self._pointer > 10:
            return f"{self._data[self._pointer - 10:self._pointer]} || {' '.join(chunks(self._data[self._pointer:], 2))}"
        else:
            return self._data

    def _advance_until_message_end(self):
        data = ""
        while data != "00":
            data = self._advance(2)

    def handle_getlist(self, next_list):
        list_length = self._advance(1)  # second nibble contains the length of the entry:
        if list_length != "7":
            raise Exception("unexpected length!")

        client_id = self._handle_octet_string(self._advance(2))
        server_id = self._handle_octet_string(self._advance(2))
        list_name = self._handle_octet_string(self._advance(2))

        next_list.data.append(client_id)
        next_list.data.append(server_id)
        next_list.data.append(list_name)

        data = self._advance(2)
        if data != "72":
            raise Exception("unexpected fierld, should be actSensorTime!")

        data_container = SmlMessage("SML_Time")
        self._extract_runtime_information(data_container)
        next_list.data.append(data_container)

        values = self._handle_val_list()
        next_list.data.append(values)

    def _handle_val_list(self):
        values = []
        list_length = self._expect_list()
        logger.debug(f"List with {list_length} elements")

        for outer in range(list_length):
            inner_length = self._expect_list()
            if inner_length != 7:
                raise Exception(f"valListEntry should have 7 elements, but has {inner_length}")
            logger.debug("processing list element {outer}", outer=outer)

            obj_name = self._handle_value_field()
            status = self._handle_status_field()
            val_time = self._handle_value_field()
            unit = self._get_unit_field()
            scaler = self._handle_value_field()
            value = self._handle_value_field()
            value_signature = self._handle_value_field()

            values.append({
                "obj_name": obj_name,
                "status": status,
                "val_time": val_time,
                "unit": unit,
                "scaler": scaler,
                "value": value,
                "value_signature": value_signature
            })

        return values

    def _get_unit_field(self):
        field = self._handle_value_field()
        return units.units.get(str(field), "no unit")

    def _expect_list(self):
        entry = self._advance(1)
        if entry != "7":
            raise Exception("expected a list")
        list_length = self._advance(1)  # second nibble contains the length of the entry:
        list_length = hex_to_int(list_length)  # in elements
        return list_length

    def _handle_status_field(self) -> typing.Optional[str]:
        """
        This is a vers weird case, see https://www.schatenseite.de/tag/sml/ for a possible explanation
        :return:
        """
        data = self._advance(2)
        if data == "01":
            return None
        length = hex_to_int(data[1])
        return self._advance((length - 1) * 2)


def hex_to_int_byte(byte: str) -> int:
    return hex_to_int(byte) * 2


def hex_to_int(byte: str) -> int:
    return int(byte, 16)


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def hex_to_binary_with_leading_zeroes(hex: str):
    return bin(int('1' + hex, 16))[3:]


def hex_to_binary_without_leading_zeroes(hex: str) -> str:
    return bin(int(hex, 16))[2:]


def leading_bit_set(hex: str):
    binary = hex_to_binary_without_leading_zeroes(hex)
    return binary[0] == "1"


def octet_to_str(bytes: str) -> str:
    return "".join([chr(int(x, 16)) for x in chunks(bytes, 2)])
