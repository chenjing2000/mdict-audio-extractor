from dataclasses import dataclass


@dataclass(frozen=True)
class PronunciationCandidate:
    accent: str
    resource: str
    ipa: str | None = None


@dataclass(frozen=True)
class ResourceLocation:
    mdd_index: int
    key_index: int
    original_key: str
