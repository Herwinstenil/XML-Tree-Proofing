import re
import html
import unicodedata

# Escape stray & that are not a valid entity
ENTITY_PATTERN = re.compile(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9A-Fa-f]+;)')

def preprocess_xml(s: str) -> str:
    return ENTITY_PATTERN.sub('&amp;', s)

def decode_entities_aggressively(s: str) -> str:
    prev = None
    curr = s
    for _ in range(2):
        prev, curr = curr, html.unescape(curr)
        if curr == prev:
            break
    return curr

def normalize_text_for_diff(s: str) -> str:
    if s is None:
        return ""
    s = decode_entities_aggressively(s)
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
