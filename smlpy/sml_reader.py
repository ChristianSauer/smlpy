import typing

import yaml
import pathlib
from smlpy import errors, units
from loguru import logger
import datetime

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


class SmlMessageEnvelope:
    def __init__(self):
        self.transaction_id = ""
        self.group_no = ""
        self.message_body: SmlMessageBody = SmlMessageBody()
        self._abort_on_error = ""
        self._crc16 = ""


class SmlMessageBody:
    """purely a dummy"""
    pass


class SmlValListEntry:
    def __init__(self):
        self.obj_name = ""
        self.status = None
        self.val_time = None
        self.unit = None
        self.scaler = None
        self.value = None
        self.value_signature = None

    def get_scaled_value(self):
        if self.value is None or self.scaler is None:
            raise errors.MissingValueInfoException()
        return self.value * 10 ** self.scaler

    def get_obis_explanation(self):
        result = obis_t_kennzahlen.get(self.obj_name, "None")
        return result

    def __repr__(self):
        try:
            value = self.get_scaled_value()
        except errors.MissingValueInfoException:
            value = None

        return f"{self.obj_name} {self.get_obis_explanation()}: {value}  {self.unit}"


class SmlPublicCloseRes:
    def __init__(self):
        self.global_signature = ""


class SmlPublicOpenRes:
    def __init__(self):
        self.codepage = None
        self.client_id = None
        self.req_file_id = ""
        self.server_id = ""
        self.ref_time = None
        self.sml_version = None


class SmlGetListRes:
    def __init__(self):
        self.client_id = None
        self.server_id = None
        self.list_name = None
        self.act_sensor_time = None
        self.val_list = None
        self.list_signature = None
        self.act_gateway_time = None


class SmlTime:
    def __init__(self, dt: datetime.datetime = None, epoch: int = None, elapsed_seconds: int = None):
        if epoch is not None:
            self.datetime = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
        elif dt is not None:
            self.datetime = dt
        elif elapsed_seconds is not None:
            self.datetime = datetime.datetime.utcnow() - datetime.timedelta(seconds=elapsed_seconds)
        else:
            raise AttributeError("choose epoch or datetime")

    def __repr__(self):
        return f"{self.datetime}"


class SmlFile:
    def __init__(self):
        self.data = []

    data: typing.List[SmlMessageEnvelope]

    def __repr__(self):
        return f"SmlFile with {len(self.data)} entries"


class SmlReader:

    def __init__(self, data: str):
        self._data = data
        self._pointer = 0
        self.sml_file = SmlFile()

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

    def _advance_and_compare(self, to_compare: str) -> str:
        data = self._advance(len(to_compare))

        if not data == to_compare:
            raise errors.InvalidData(self._pointer - len(to_compare), to_compare, data)

        return data

    def _peek(self, n_chars: int):
        next_pos = self._pointer + n_chars
        len_data = len(self._data)
        if next_pos > len_data:
            raise Exception(f"attempted to read position {next_pos}, but the sml file is only {len_data} long")
        rv = self._data[self._pointer:next_pos]
        return rv

    def read_sml_file(self):
        if self._pointer != 0:
            raise Exception("can only called once")

        self._advance_and_compare(msg_start)  # start sequence looks ok

        self._advance_and_compare(msg_version_1)  # version sequence looks ok

        while self._peek(1) == "7":  # a list of something
            self._read_message()

        self._advance_and_compare(msg_end)
        # everything else is crc
        self._pointer = len(self._data)

        return self.sml_file

    def get_value_by_obis_id(self, obis_id: str):
        """searches for a val list entry which contains a obis number in the form 1-b:1.8.e
        you can replace b and e with an actual value or keep the placeholders in
        which case you get all matching messages
        """

    def _read_message(self):
        message = SmlMessageEnvelope()
        self.sml_file.data.append(message)

        self._assert_next_element_is_list_of_length(6)

        message.transaction_id = self._handle_value_field()
        message.group_no = self._handle_value_field()
        message.abort_on_error = self._handle_value_field()
        self._read_message_body(message)

        message.crc_16 = self._handle_value_field()
        self._advance_and_compare("00")  # message end

    def _assert_next_element_is_list_of_length(self, n: int):
        self._advance_and_compare("7")  # must be a list
        list_length = hex_to_int(self._advance(1))
        assert list_length == n, f"unexpected length {list_length} should be {n}"

    def _read_message_body(self, message):
        """
        SML_Message.SML_MessageBody is a choice. A choice is represented as a list and has a unsigned int field as
        the first element, showing the choice and the second one is a list containing the choice data
        """

        self._assert_next_element_is_list_of_length(2)

        type_int = self._handle_value_field()
        assert isinstance(type_int, int)

        # table is the bsci document page 20
        if type_int == 256:
            raise NotImplementedError("SML_PublicOpen.Req not implemented")
        if type_int == 257:
            # SML_PublicOpen.Res
            inner_message = SmlPublicOpenRes()
            self._assert_next_element_is_list_of_length(6)
            inner_message.codepage = self._handle_value_field()
            inner_message.client_id = self._handle_value_field()
            inner_message.req_file_id = self._handle_value_field()
            inner_message.server_id = self._handle_value_field()
            inner_message.ref_time = self._handle_sml_time()
            inner_message.sml_version = self._handle_value_field()
            message.message_body = inner_message
            return message

        if type_int == 512:
            raise NotImplementedError("CloseRequest.Res not implemented")
        if type_int == 513:
            inner_message = SmlPublicCloseRes()
            self._assert_next_element_is_list_of_length(1)
            inner_message.global_signature = self._handle_value_field()
            message.message_body = inner_message
            return message

        if type_int == 768:
            raise NotImplementedError("SML_GetProfilePack.Req not implemented")
        if type_int == 769:
            raise NotImplementedError("SML_GetProfilePack.Res not implemented")

        if type_int == 1024:
            raise NotImplementedError("SML_GetProfileList.Req not implemented")
        if type_int == 1025:
            raise NotImplementedError("SML_GetProfileList.Res not implemented")

        if type_int == 1280:
            raise NotImplementedError("SML_GetProcParameter.Req not implemented")
        if type_int == 1281:
            raise NotImplementedError("SML_GetProcParameter.Res not implemented")

        if type_int == 1280:
            raise NotImplementedError("SML_SetProcParameter.Req not implemented")
        if type_int == 1281:
            raise NotImplementedError("SML_SetProcParameter.Res not implemented")

        if type_int == 1792:
            raise NotImplementedError("SML_GetList.Req not implemented")
        if type_int == 1793:
            # SML_GetList.Res
            inner_message = SmlGetListRes()
            self._assert_next_element_is_list_of_length(7)
            inner_message.client_id = self._handle_value_field()
            inner_message.server_id = self._handle_value_field()
            inner_message.list_name = self._handle_value_field()
            inner_message.act_sensor_time = self._handle_sml_time()
            inner_message.val_list = self._handle_val_list()
            inner_message.list_signature = self._handle_value_field()  # even if this has a value its an string
            inner_message.act_gateway_time = self._handle_sml_time()
            message.message_body = inner_message
            return message

        if type_int == 2048:
            raise NotImplementedError("SML_GetCosem.Req not implemented")
        if type_int == 2049:
            raise NotImplementedError("SML_GetCosem.Res not implemented")

        if type_int == 2304:
            raise NotImplementedError("SML_SetCosem.Req not implemented")
        if type_int == 2305:
            raise NotImplementedError("SML_SetCosem.Res not implemented")

        if type_int == 2560:
            raise NotImplementedError("SML_ActionCosem.Req not implemented")
        if type_int == 2561:
            raise NotImplementedError("SML_ActionCosem.Res not implemented")

        if type_int == 65281:
            raise NotImplementedError("SML_Attention.Req not implemented")

        raise Exception(f"unknown type int: {type_int}")

    def _handle_sml_time(self) -> typing.Optional[SmlTime]:
        data = self._advance(2)
        if data == "01":
            return None
        elif data[0] == "7":
            list_length = hex_to_int(data[1])
            assert list_length == 2, "list length should be 2 since this is a choice"
        else:
            raise errors.InvalidData(self._pointer, "'01' or '7x'", data)

        type_int = self._handle_value_field()
        assert isinstance(type_int, int)

        if type_int == 1:
            return SmlTime(elapsed_seconds=self._handle_value_field())
        elif type_int == 2:
            raise NotImplementedError("timestamp")
        elif type_int == 3:
            raise NotImplementedError("localTimestamp")
        else:
            raise Exception(f"unknown type int for SML_Time: {type_int}")

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
            obis = self._hex_to_obis(data)
            return obis
        else:
            value = octet_to_str(data)
            return value

    def _hex_to_obis(self, data):
        obis = f"{hex_to_int(data[0:2])}-{hex_to_int(data[2:4])}.{hex_to_int(data[4:6])}.{hex_to_int(data[6:8])}.{int(hex_to_int(data[8:]) / 255)}"
        return obis

    def __repr__(self):
        if self._pointer > 10:
            return f"{self._data[self._pointer - 10:self._pointer]} || {' '.join(chunks(self._data[self._pointer:], 2))}"
        else:
            return self._data

    def _advance_until_message_end(self):
        data = ""
        while data != "00":
            data = self._advance(2)

    def _handle_val_list(self) -> typing.List[SmlValListEntry]:
        values = []
        list_length = self._expect_list()
        logger.debug(f"List with {list_length} elements")

        for outer in range(list_length):
            inner_length = self._expect_list()
            if inner_length != 7:
                raise Exception(f"valListEntry should have 7 elements, but has {inner_length}")
            logger.debug("processing list element {outer}", outer=outer)

            entry = SmlValListEntry()
            entry.obj_name = self._handle_value_field()
            entry.status = self._handle_status_field()
            entry.val_time = self._handle_value_field()
            entry.unit = self._get_unit_field()
            entry.scaler = self._handle_value_field()
            entry.value = self._handle_value_field()
            entry.value_signature = self._handle_value_field()

            values.append(entry)

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
