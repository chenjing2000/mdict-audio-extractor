from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import struct
import zlib

from mdict_utils.base.readmdict import MDD, MDX


_FORMAT_ERRORS = (struct.error, zlib.error, AssertionError, UnicodeError, KeyError, IndexError)


def _open_mdict(reader, path: Path):
    try:
        return reader(str(path))
    except OSError:
        raise
    except Exception as exc:
        # This dependency also uses plain Exception for unsupported formats.
        raise ValueError(f"词典格式损坏或不受支持：{path}：{exc}") from exc


@dataclass(frozen=True)
class ResourceLocation:
    mdd_index: int
    key_index: int
    original_key: str


def _decode_key(key: bytes | str) -> str:
    if isinstance(key, bytes):
        return key.decode("utf-8", errors="replace")
    return key


def normalize_entry_key(value: str) -> str:
    return value.strip().casefold()


def normalize_resource_key(value: str) -> str:
    return value.strip().replace("/", "\\").lstrip("\\").casefold()


def _read_record_by_index(md, key_index: int):
    offset = md._key_list[key_index][0]
    end = md._key_list[key_index + 1][0] if key_index + 1 < len(md._key_list) else None
    binary = isinstance(md, MDD)
    if end == offset:
        return b"" if binary else ""
    if offset < 0 or (end is not None and end < offset):
        raise ValueError(f"词典记录偏移无效：{md._fname}")
    chunks = []
    try:
        with open(md._fname, "rb") as stream:
            stream.seek(md._record_block_offset)
            for start, size, position, compressed_size in _record_blocks(md, stream):
                if offset >= start + size:
                    continue
                if end is not None and end <= start:
                    break
                stream.seek(position)
                block = stream.read(compressed_size)
                try:
                    decoded = md._decode_block(block, size)
                except Exception as exc:
                    raise ValueError(f"词典记录解码失败：{md._fname}：{exc}") from exc
                if len(decoded) != size:
                    raise ValueError(f"词典记录块长度不符：{md._fname}")
                lower = max(0, offset - start)
                upper = size if end is None else min(size, end - start)
                chunks.append(decoded[lower:upper])
                if end is not None and end <= start + size:
                    break
        payload = b"".join(chunks)
        if end is not None and len(payload) != end - offset:
            raise ValueError(f"词典记录不完整：{md._fname}")
        # Determine record type from the reader, not case-sensitive filenames.
        return payload if binary else payload.decode(md._encoding).strip()
    except _FORMAT_ERRORS as exc:
        raise ValueError(f"词典记录损坏：{md._fname}：{exc}") from exc


def _record_blocks(md, stream):
    """Yield block ranges without reading unrelated compressed recordings."""
    start = 0
    if md._version >= 3:
        count = md._read_int32(stream)
        md._read_number(stream)
        for _ in range(count):
            size = md._read_int32(stream)
            compressed_size = md._read_int32(stream)
            position = stream.tell()
            yield start, size, position, compressed_size
            stream.seek(position + compressed_size)
            start += size
    else:
        count = md._read_number(stream)
        entries = md._read_number(stream)
        info_size = md._read_number(stream)
        md._read_number(stream)
        if entries != md._num_entries or info_size != count * md._number_width * 2:
            raise ValueError(f"词典记录索引无效：{md._fname}")
        sizes = [(md._read_number(stream), md._read_number(stream)) for _ in range(count)]
        position = stream.tell()
        for compressed_size, size in sizes:
            yield start, size, position, compressed_size
            position += compressed_size
            start += size


class MdxIndex:
    def __init__(self, path: Path):
        self._mdx = _open_mdict(MDX, path)
        self._index: dict[str, list[int]] = defaultdict(list)

        for index, (_, raw_key) in enumerate(self._mdx._key_list):
            key = normalize_entry_key(_decode_key(raw_key))
            self._index[key].append(index)

    def lookup_all(self, word: str) -> list[str]:
        records: list[str] = []
        for index in self._index.get(normalize_entry_key(word), []):
            value = _read_record_by_index(self._mdx, index)
            if isinstance(value, str) and value:
                records.append(value)
        return records


class MddCollection:
    def __init__(self, paths: list[Path]):
        if not paths:
            raise ValueError("至少需要一个 MDD 文件。")

        self._mdds = [_open_mdict(MDD, path) for path in paths]
        self._index: dict[str, ResourceLocation] = {}

        for mdd_index, mdd in enumerate(self._mdds):
            for key_index, (_, raw_key) in enumerate(mdd._key_list):
                original_key = _decode_key(raw_key)
                key = normalize_resource_key(original_key)
                self._index.setdefault(
                    key,
                    ResourceLocation(mdd_index, key_index, original_key),
                )

    def find(self, resource: str) -> ResourceLocation | None:
        return self._index.get(normalize_resource_key(resource))

    def read(self, location: ResourceLocation) -> bytes:
        value = _read_record_by_index(
            self._mdds[location.mdd_index],
            location.key_index,
        )
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(f"MDD 资源不是二进制数据：{location.original_key}")
        return bytes(value)


def _numbered_mdds(base_mdd: Path) -> list[Path]:
    paths = [base_mdd]
    stem = base_mdd.with_suffix("")

    index = 1
    while True:
        candidate = Path(f"{stem}.{index}.mdd")
        if not candidate.exists():
            break
        paths.append(candidate)
        index += 1

    return paths


def find_mdd_files(mdx_path: Path, mdd_path: str | Path | None) -> list[Path]:
    """Return the main MDD and contiguous numbered MDD parts."""
    main_mdd = mdx_path.with_suffix(".mdd") if mdd_path is None else Path(mdd_path).expanduser().resolve()
    if not main_mdd.is_file():
        raise FileNotFoundError(f"MDD 文件不存在：{main_mdd}")
    return _numbered_mdds(main_mdd)
