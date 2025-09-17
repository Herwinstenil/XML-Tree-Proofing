# diff.py
from lxml import etree as LET
from .normalize import preprocess_xml, normalize_text_for_diff
from .utils import build_path, local_name
import re
from collections import Counter
from typing import Optional

# duplicate 
WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)

def _token_spans(s: str):
    return [(m.group(0), m.start(), m.end()) for m in WORD_RE.finditer(s or "")]

def _key(w: str) -> str:
    return (w or "").casefold()

def _highlight_tokens(text: str, keys: set[str]) -> Optional[str]:
    """Highlight ALL occurrences of any key in `keys`."""
    if not text or not keys:
        return None
    toks = _token_spans(text)
    if not toks:
        return None
    out, last, hit = [], 0, False
    for w, s, e in toks:
        out.append(text[last:s])
        if _key(w) in keys:
            out.append(f'<span class="editNewInline">{w}</span>')
            hit = True
        else:
            out.append(w)
        last = e
    out.append(text[last:])
    return "".join(out) if hit else None

# duplicate 

def parse_tree(xml_string: str) -> LET.ElementTree:
    parser = LET.XMLParser(recover=True, remove_blank_text=False)
    root = LET.fromstring(preprocess_xml(xml_string).encode("utf-8"), parser=parser)
    return LET.ElementTree(root)

def looks_gibberish(s: str) -> bool:
    if not s: return False
    t = s.strip()
    if len(t) < 2: return False
    vowels = len(re.findall(r"[AEIOUaeiou]", t))
    letters = len(re.findall(r"[A-Za-z]", t))
    if letters and vowels / letters < 0.15 and letters > 12:
        return True
    if re.search(r"(.)\1{3,}", t):
        return True
    if re.search(r"[A-Z]{5,}", t):
        return True
    if re.search(r"[A-Za-z]{6,}\d{2,}", t):
        return True
    if re.search(r"([A-Z]{3,}).*?\1", t):
        return True
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{6,}", t.lower()):
        return True
    return False

# def find_duplicate_blocks(root):
#     issues = []
#     for parent in root.iter():
#         if not isinstance(parent.tag, str): continue
#         texts = []
#         for i, child in enumerate(parent):
#             if not isinstance(child.tag, str): continue
#             ln = local_name(child.tag)
#             if ln not in ("para", "p", "title", "entry-title"): continue  # extend as needed
#             txt = (child.text or "").strip()
#             if not txt: continue
#             norm = normalize_text_for_diff(txt)
#             texts.append((i, child, norm, txt))
#         seen = {}
#         for idx, elem, norm, raw in texts:
#             if norm in seen and idx - seen[norm][0] <= 2:
#                 issues.append({
#                     "kind": "duplicate",
#                     "steps": build_path(elem),
#                     "old": raw,
#                     "new": seen[norm][1], 
#                 })
#             seen[norm] = (idx, raw)
#             print(issues)
#     return issues

# ---------- fast, kind-specific scanners ----------
_FOOTNOTE_TAGS = {"footnote", "fn", "footnote-ref", "fn-ref"}

def compute_gibberish_issues(left_tree, right_tree):
    out = []
    L = (e for e in left_tree.getroot().iter()  if isinstance(e.tag, str))
    R = (e for e in right_tree.getroot().iter() if isinstance(e.tag, str))
    for l_elem, r_elem in zip(L, R):
        if local_name(l_elem.tag) != local_name(r_elem.tag): 
            continue
        lt = l_elem.text or ""
        rt = r_elem.text or ""
        if looks_gibberish(lt) and lt != rt:
            print({"kind": "gibberish", "steps": build_path(l_elem), "old": lt, "new": rt})
            out.append({"kind": "gibberish", "steps": build_path(l_elem), "old": lt, "new": rt})
            print(out)
    return out



def compute_footnote_issues(left_tree, right_tree):
    out = []
    L = (e for e in left_tree.getroot().iter()  if isinstance(e.tag, str))
    R = (e for e in right_tree.getroot().iter() if isinstance(e.tag, str))
    for l_elem, r_elem in zip(L, R):
        if local_name(l_elem.tag) != local_name(r_elem.tag):
            continue
        if local_name(l_elem.tag) not in _FOOTNOTE_TAGS:
            continue
        l_attrs = {k.split(":")[-1]: v for k, v in l_elem.attrib.items()}
        r_attrs = {k.split(":")[-1]: v for k, v in r_elem.attrib.items()}
        for k in (set(l_attrs) | set(r_attrs)):
            lv, rv = l_attrs.get(k, ""), r_attrs.get(k, "")
            if lv != rv:
                out.append({
                    "kind": "footnote",
                    "steps": build_path(l_elem),
                    "steps_right": build_path(r_elem),
                    "attr": k,
                    "old": lv,
                    "new": rv
                })
    
    return out

def compute_duplicate_issues(left_tree, right_tree):
    """
    Compare aligned elements.
    If a word appears >=2 times on one side and more than on the other side,
    highlight ALL its occurrences on that side.
    """
    issues = []
    L = (e for e in left_tree.getroot().iter()  if isinstance(e.tag, str))
    R = (e for e in right_tree.getroot().iter() if isinstance(e.tag, str))

    for l_elem, r_elem in zip(L, R):
        if local_name(l_elem.tag) != local_name(r_elem.tag):
            continue
        if local_name(l_elem.tag) not in ("para", "p", "title", "entry-title"):
            continue

        lt = (l_elem.text or "").strip()
        rt = (r_elem.text or "").strip()
        if not lt and not rt:
            continue

        # counts (case-insensitive)
        lc = Counter(_key(w) for w,_,_ in _token_spans(lt))
        rc = Counter(_key(w) for w,_,_ in _token_spans(rt))

        # words to highlight on each side
        right_keys = {k for k, c in rc.items() if c >= 2 and c > lc.get(k, 0)}
        left_keys  = {k for k, c in lc.items() if c >= 2 and c > rc.get(k, 0)}

        right_high = _highlight_tokens(rt, right_keys) if right_keys else None
        left_high  = _highlight_tokens(lt, left_keys)  if left_keys  else None

        if right_high or left_high:
            issues.append({
                "kind": "duplicate",
                "steps": build_path(l_elem),           # keep LEFT steps for /apply
                "steps_right": build_path(r_elem),     # right steps for render
                "old": lt,
                "new": rt,
                "right_highlight": right_high,
                "left_highlight": left_high,
            })
    return issues

def compute_issues(left_tree, right_tree, only=None):
    if only == "gibberish":
        return compute_gibberish_issues(left_tree, right_tree)
    if only == "duplicate":
        return compute_duplicate_issues(left_tree, right_tree)   # <-- changed
    if only == "footnote":
        return compute_footnote_issues(left_tree, right_tree)

    out = []
    out += compute_gibberish_issues(left_tree, right_tree)
    out += compute_footnote_issues(left_tree, right_tree)
    out += compute_duplicate_issues(left_tree, right_tree)       # <-- changed
    return out
