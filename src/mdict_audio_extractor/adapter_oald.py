from urllib.parse import unquote

from bs4 import BeautifulSoup

from .models import PronunciationCandidate


def _resource_from_href(href: str) -> str | None:
    prefix = "sound://"
    if not href.lower().startswith(prefix):
        return None

    value = unquote(href[len(prefix):]).strip()
    return value or None


def _detect_accent(anchor) -> str | None:
    classes = {str(x).casefold() for x in anchor.get("class", [])}

    # OALD explicitly marks headword pronunciation buttons this way.
    if "pron-uk" in classes:
        return "uk"
    if "pron-us" in classes:
        return "us"

    # Secondary structural signal in the supplied OALD entries.
    parent = anchor.find_parent("div")
    if parent is not None:
        geo = str(parent.get("geo", "")).casefold()
        if geo in {"br", "gb", "uk"}:
            return "uk"
        if geo in {"n_am", "us", "am"}:
            return "us"

    return None


def parse_headword_pronunciations(html: str) -> list[PronunciationCandidate]:
    """
    Parse only the headword pronunciation area.

    This intentionally ignores <audio-wr> sentence recordings and other
    sound:// links elsewhere in the entry.
    """
    soup = BeautifulSoup(html, "html.parser")

    entry = soup.select_one("div.entry") or soup

    # In the supplied OALD data the desired sound buttons live inside the
    # first webtop/headword phonetics span.
    phonetics = entry.select_one("div.webtop span.phonetics")
    if phonetics is None:
        phonetics = entry.select_one("span.phonetics")
    if phonetics is None:
        return []

    candidates: list[PronunciationCandidate] = []
    seen: set[tuple[str, str]] = set()

    for anchor in phonetics.find_all("a", href=True):
        href = str(anchor.get("href", ""))
        resource = _resource_from_href(href)
        if resource is None:
            continue

        accent = _detect_accent(anchor)
        if accent is None:
            continue

        ipa = None
        container = anchor.find_parent("div")
        if container is not None:
            phon = container.find("span", class_="phon")
            if phon is not None:
                text = phon.get_text(" ", strip=True)
                ipa = text or None

        sig = (accent, resource.casefold())
        if sig in seen:
            continue
        seen.add(sig)

        candidates.append(
            PronunciationCandidate(
                accent=accent,
                resource=resource,
                ipa=ipa,
            )
        )

    return candidates
