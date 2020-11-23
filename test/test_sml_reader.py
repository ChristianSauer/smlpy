import pytest

from smlpy import sml_reader
from smlpy import errors

test_sml = "1b1b1b1b01010101760700110bf402df620062007263010176010107001103c500f50b0901454d4800007514c401016375f300760700110bf402e0620062007263070177010b0901454d4800007514c4070100620affff7262016503c5853c7a77078181c78203ff0101010104454d480177070100000009ff010101010b0901454d4800007514c40177070100010800ff6401018201621e52ff5600051bdfde0177070100020800ff6401018201621e52ff5600000006070177070100010801ff0101621e52ff5600051bdfde0177070100020801ff0101621e52ff5600000006070177070100010802ff0101621e52ff5600000000000177070100020802ff0101621e52ff5600000000000177070100100700ff0101621b52ff55000014f40177078181c78205ff010101018302957c486aaf8c92a257ec681e215fddeff32a2dbf2c8a88721777f5f01e5ed5ccaa694dd48c14dc5589d28e0c5b9ce88e01010163b4c800760700110bf402e362006200726302017101634e85001b1b1b1b1a000337"


def test_aborts_if_no_start_sequence():
    reader = sml_reader.SmlReader("A"*sml_reader.DATA_MIN_LEN)
    with pytest.raises(errors.InvalidStartSequence):
        reader.read()


def test_works_on_basic():
    reader = sml_reader.SmlReader("1b1b1b1b0101010171011b1b1b1b1a000337") # list with one empty element
    states= [sml_reader.SmlState.VERSION, sml_reader.SmlState.MSB_BODY, sml_reader.SmlState.MESSAGE, sml_reader.SmlState.CLOSED]

    def helper(state, data):
        assert states[0] == state, data
        states.pop(0)

    reader.call_on_state_change = helper
    reader.read()
    assert reader._pointer == len(sml_reader.msg_start) + len(sml_reader.msg_version_1) + 1
    assert reader._state == sml_reader.SmlState.CLOSED


def test_aborts_if_invalid_version():
    reader = sml_reader.SmlReader("1b1b1b1b020101011b1b1b1b1a000337")

    with pytest.raises(errors.InvalidVersion):
        reader.read()