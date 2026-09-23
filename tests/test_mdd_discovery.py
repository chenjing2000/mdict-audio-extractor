from mdict_audio_extractor.app import find_mdd_files


def test_finds_numbered_mdd_parts(tmp_path):
    mdx = tmp_path / "Oxford.mdx"
    base = tmp_path / "Oxford.mdd"
    part1 = tmp_path / "Oxford.1.mdd"
    part2 = tmp_path / "Oxford.2.mdd"

    mdx.write_bytes(b"")
    base.write_bytes(b"")
    part1.write_bytes(b"")
    part2.write_bytes(b"")

    assert find_mdd_files(mdx, base) == [base, part1, part2]


def test_uses_mdx_name_when_mdd_is_omitted(tmp_path):
    mdx = tmp_path / "Oxford.mdx"
    base = tmp_path / "Oxford.mdd"

    mdx.write_bytes(b"")
    base.write_bytes(b"")

    assert find_mdd_files(mdx, None) == [base]
