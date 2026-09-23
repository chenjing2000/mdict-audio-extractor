from collections import defaultdict
from pathlib import Path

from mdict_utils.base.readmdict import MDD, MDX
from mdict_utils.reader import get_record

from .models import ResourceLocation


def _decode_key(key: bytes | str) -> str:
    if isinstance(key, bytes):
        return key.decode("utf-8", errors="replace")
    return key


def normalize_entry_key(value: str) -> str:
    return value.strip().casefold()


def normalize_resource_key(value: str) -> str:
    value = value.strip().replace("/", "\\")
    return value.lstrip("\\").casefold()


def _read_record_by_index(md, key_index: int):
    offset, key = md._key_list[key_index]

    if key_index + 1 < len(md._key_list):
        length = md._key_list[key_index + 1][0] - offset
    else:
        length = -1

    return get_record(md, key, offset, length)


class MdxIndex:
    def __init__(self, path: Path):
        self._mdx = MDX(str(path))
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

        self._mdds = [MDD(str(path)) for path in paths]
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
