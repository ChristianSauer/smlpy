import json
import pathlib

import pytest

import smlpy
from smlpy import sml_reader

raw_sml = "1b1b1b1b01010101760700110bf402df620062007263010176010107001103c500f50b0901454d4800007514c401016375f3007" \
          "60700110bf402e0620062007263070177010b0901454d4800007514c4070100620affff7262016503c5853c7a77078181c78203" \
          "ff0101010104454d480177070100000009ff010101010b0901454d4800007514c40177070100010800ff6401018201621e52ff5" \
          "600051bdfde0177070100020800ff6401018201621e52ff5600000006070177070100010801ff0101621e52ff5600051bdfde017" \
          "7070100020801ff0101621e52ff5600000006070177070100010802ff0101621e52ff5600000000000177070100020802ff010162" \
          "1e52ff5600000000000177070100100700ff0101621b52ff55000014f40177078181c78205ff010101018302957c486aaf8c92a2" \
          "57ec681e215fddeff32a2dbf2c8a88721777f5f01e5ed5ccaa694dd48c14dc5589d28e0c5b9ce88e01010163b4c800760700110" \
          "bf402e362006200726302017101634e85001b1b1b1b1a000337"


def get_test_files():
    base_dir = "../../libsml-testing"
    data = pathlib.Path(base_dir).resolve()

    files = [x for x in data.iterdir() if x.suffix == ".hex"]
    files = sorted(files)

    return files


test_files = get_test_files()


def test_own_data():
    reader = smlpy.SmlReader(raw_sml)
    reader.read_sml_file()

    assert len(reader.sml_file.data) == 3
    assert isinstance(reader.sml_file.data[0].message_body, sml_reader.SmlPublicOpenRes)
    data = reader.sml_file.data[1].message_body
    assert isinstance(data, sml_reader.SmlGetListRes)
    assert isinstance(reader.sml_file.data[2].message_body, sml_reader.SmlPublicCloseRes)

    assert len(data.val_list) == 10
    assert data.val_list[2].value == 85712862
    assert data.val_list[2].unit == "Wh"
    assert data.val_list[2].scaler == -1
    assert data.val_list[2].obj_name == '1-0.1.8.1'


@pytest.mark.skip("manual only")
@pytest.mark.parametrize("file", test_files, ids=[str(x.name) for x in test_files])
def test_other_power_meters(file):
    """
    Many of these tests fail. Some are most certainly errors in my parser, but a lot of them seem to contain
    incomplete data, e.g. the message ends at position 8192, but the data should be longer than that
    """

    hex_content = file.read_text()

    reader = sml_reader.SmlReader(hex_content)

    reader.read_sml_file()


def test_can_dump():
    reader = smlpy.SmlReader(raw_sml)
    reader.read_sml_file()

    result = reader.sml_file.dump_to_json()
    data = json.loads(result)
    assert len(data["data"]) == 3
    assert data["data"][1]["message_body"]["val_list"][4]["scaled_value"] == 8571286.200000001

