from dataclasses import dataclass
from urllib.parse import unquote

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class PronunciationCandidate:
    accent: str
    resource: str
    ipa: str | None = None


def _resource_from_href(href: str) -> str | None:
    prefix = "sound://"
    if not href.lower().startswith(prefix):
        return None

    value = unquote(href[len(prefix):]).strip()
    return value or None


def _detect_accent(anchor) -> str | None:
    classes = {str(value).casefold() for value in anchor.get("class", [])}
    if "pron-uk" in classes:
        return "uk"
    if "pron-us" in classes:
        return "us"

    parent = anchor.find_parent("div")
    if parent is not None:
        geo = str(parent.get("geo", "")).casefold()
        if geo in {"br", "gb", "uk"}:
            return "uk"
        if geo in {"n_am", "us", "am"}:
            return "us"

    return None


def parse_headword_pronunciations(html: str) -> list[PronunciationCandidate]:
    """Parse headword UK/US pronunciation links and IPA from an OALD entry."""
    soup = BeautifulSoup(html, "html.parser")
    entry = soup.select_one("div.entry") or soup
    phonetics = entry.select_one("div.webtop span.phonetics")
    if phonetics is None:
        phonetics = entry.select_one("span.phonetics")
    if phonetics is None:
        return []

    candidates: list[PronunciationCandidate] = []
    seen: set[tuple[str, str]] = set()

    for anchor in phonetics.find_all("a", href=True):
        resource = _resource_from_href(str(anchor.get("href", "")))
        accent = _detect_accent(anchor)
        if resource is None or accent is None:
            continue

        ipa = None
        container = anchor.find_parent("div")
        if container is not None:
            phon = container.find("span", class_="phon")
            if phon is not None:
                text = phon.get_text(" ", strip=True)
                ipa = text or None

        key = (accent, resource.casefold())
        if key in seen:
            continue
        seen.add(key)
        candidates.append(PronunciationCandidate(accent, resource, ipa))

    return candidates
