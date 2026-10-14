import pytest
import struct
import zlib
from mdict_utils.base.readmdict import MDD
from mdict_utils.base.writemdict import MDictWriter

from audio_extractor.mdict_index import MddCollection, MdxIndex, _read_record_by_index, _record_blocks


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


@pytest.mark.parametrize("version,compression_type", [("1.2", 0), ("1.2", 2), ("2.0", 2)])
def test_real_multi_block_dictionary_preserves_records(tmp_path, version, compression_type):
    records = {"\\first.mp3": b"FIRST" * 50, "\\middle.mp3": b"MIDDLE" * 100,
               "\\last.mp3": b"LAST" * 75}
    path = tmp_path / "many.mdd"
    writer = MDictWriter(records, "Test", "Multiple blocks", is_mdd=True,
                         block_size=64, version=version, compression_type=compression_type)
    with path.open("wb") as stream:
        writer.write(stream)
    resources = MddCollection([path])
    for key, payload in records.items():
        assert resources.read(resources.find(key)) == payload


def test_real_mdx_preserves_unicode_entry_text(tmp_path):
    path = tmp_path / "dictionary.mdx"
    html = '<span class="phon">/zuˈɒlədʒi/</span>'
    writer = MDictWriter({"zoology": html}, "Test", "Real MDX")
    with path.open("wb") as stream:
        writer.write(stream)
    assert MdxIndex(path).lookup_all("ZOOLOGY")[0].rstrip("\0") == html


def test_v3_record_range_can_span_two_blocks(tmp_path):
    # The installed writer supports only v1/v2; build the v3 record section directly.
    section = struct.pack(">IQ", 2, 0)
    for payload in (b"ABC", b"DEF"):
        compressed = struct.pack("<I", 0) + struct.pack(">I", zlib.adler32(payload)) + payload
        section += struct.pack(">II", len(payload), len(compressed)) + compressed
    path = tmp_path / "record-section.MDD"
    path.write_bytes(section)
    reader = object.__new__(MDD)
    reader._fname = str(path)
    reader._version = 3
    reader._number_format = ">Q"
    reader._number_width = 8
    reader._encrypted_key = None
    reader._record_block_offset = 0
    reader._key_list = [(0, b"first"), (5, b"last")]
    assert _read_record_by_index(reader, 0) == b"ABCDE"
    assert _read_record_by_index(reader, 1) == b"F"


@pytest.mark.parametrize("flags", [3, 0x30])
def test_unsupported_record_flags_become_reportable_dictionary_error(tmp_path, flags):
    path = tmp_path / "bad-flags.mdd"
    write_mdd(path, {"\\test.mp3": b"recording"})
    resources = MddCollection([path])
    reader = resources._mdds[0]
    with path.open("r+b") as stream:
        stream.seek(reader._record_block_offset)
        _, _, position, _ = next(_record_blocks(reader, stream))
        stream.seek(position)
        stream.write(struct.pack("<I", flags))
    with pytest.raises(ValueError, match="bad-flags.mdd"):
        resources.read(resources.find("test.mp3"))
