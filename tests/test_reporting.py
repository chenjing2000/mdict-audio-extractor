import pytest

from audio_extractor import reporting


@pytest.mark.parametrize("status", ["audio_write_failed", "unsupported_audio_format"])
def test_reported_dictionary_failure_is_detected(status):
    words = [{"status": "audio_not_extracted", "pronunciations": [{"status": status}]}]
    summary = reporting.summarize_words(words, 0, [], [])
    assert summary["audio_failed"] == 1
    assert summary["audio_missing"] == 0
    assert reporting.has_failures({"words": words, "summary": summary})


def test_missing_audio_is_counted_but_is_not_a_failure():
    words = [{"status": "mdx_entry_not_found", "pronunciations": [
        {"status": "mdx_entry_not_found"}, {"status": "headword_audio_not_found"},
        {"status": "mdd_resource_not_found"}]}]
    summary = reporting.summarize_words(words, 0, [], [])
    assert summary["audio_missing"] == 3
    assert summary["audio_failed"] == 0
    assert not reporting.has_failures({"words": words, "summary": summary})
