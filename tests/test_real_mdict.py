import pytest
from mdict_utils.base.writemdict import MDictWriter

from audio_extractor.mdict_index import MddCollection


def write_mdd(path, records):
    writer = MDictWriter(records, "Test", "Tiny real MDD", is_mdd=True)
    with path.open("wb") as stream:
        writer.write(stream)


@pytest.mark.parametrize("suffix", [".mdd", ".MDD"])
def test_binary_mdd_read_does_not_depend_on_extension_case(tmp_path, suffix):
    path = tmp_path / f"dictionary{suffix}"
    payload = b"\x00\xff recording \r\n"
    write_mdd(path, {"\\test.mp3": payload})
    resources = MddCollection([path])
    assert resources.read(resources.find("test.mp3")) == payload


def test_empty_mdd_resource_does_not_borrow_next_recording(tmp_path):
    path = tmp_path / "dictionary.mdd"
    write_mdd(path, {"\\empty.mp3": b"", "\\other.mp3": b"OTHER-RECORDING"})
    resources = MddCollection([path])
    assert resources.read(resources.find("empty.mp3")) == b""
    assert resources.read(resources.find("other.mp3")) == b"OTHER-RECORDING"
