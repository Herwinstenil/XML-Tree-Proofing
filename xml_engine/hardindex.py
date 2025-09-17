import re
from typing import Dict, Tuple, List

# Robust tag tokenizer using named groups:
TAG_RE = re.compile(
    r"(?s)"
    r"<!--.*?-->"                                   # comment
    r"|<!\[CDATA\[(?P<cdata>.*?)\]\]>"              # CDATA
    r"|<\?(?P<pi>.*?)\?>"                           # PI
    r"|<(?P<end>/?)(?P<name>[^!\?/\s>][^/\s>]*)\s*(?P<attrs>[^>]*)?(?P<selfclose>/?)>",  # start/end
)

# Capture double/single quoted attr values
ATTR_RE = re.compile(r'([:\w\-\.]+)\s*=\s*("([^"]*)"|\'([^\']*)\')')

def local_name(tag: str) -> str:
    if not tag: return ""
    if "}" in tag: tag = tag.split("}", 1)[1]
    if ":" in tag: tag = tag.split(":", 1)[1]
    return tag

def build_path_key(steps: Tuple[Tuple[str, int], ...]) -> str:
    """Stable key like 'fm[1]/toc[1]/entry-num[12]'."""
    return "/".join(f"{ln}[{idx}]" for ln, idx in steps)

def index_element_text_spans(xml: str) -> Dict[str, Tuple[int, int]]:
    """
    Map: path_key -> (start, end) character offsets for element.text ONLY (not tails).
    We capture the FIRST text segment directly after a start tag, ending before the next '<'.
    CDATA blocks are captured as a whole.
    """
    spans: Dict[str, Tuple[int, int]] = {}

    class Node:
        __slots__ = ("ln", "idx", "has_text")
        def __init__(self, ln: str, idx: int):
            self.ln, self.idx, self.has_text = ln, idx, False

    stack: List[Node] = []
    sib_counts: List[Dict[str, int]] = [{}]

    pos = 0
    for m in TAG_RE.finditer(xml):
        start, end = m.start(), m.end()

        # Text between tokens → element.text if top of stack hasn't got text yet
        if start > pos and stack:
            top = stack[-1]
            if not top.has_text:
                key = build_path_key(tuple((n.ln, n.idx) for n in stack))
                spans[key] = (pos, start)
                top.has_text = True

        # CDATA => treat as element.text if not set
        if m.group("cdata") is not None:
            if stack and not stack[-1].has_text:
                key = build_path_key(tuple((n.ln, n.idx) for n in stack))
                spans[key] = (start, end)   # include whole CDATA block
                stack[-1].has_text = True

        elif m.group("name") is not None:
            is_end = (m.group("end") == "/")
            ln = local_name(m.group("name"))
            selfclose = (m.group("selfclose") == "/")

            if not is_end:
                depth = len(stack)
                if len(sib_counts) <= depth: sib_counts.append({})
                idx = sib_counts[depth].get(ln, 0) + 1
                sib_counts[depth][ln] = idx
                stack.append(Node(ln, idx))

                if selfclose and stack:
                    stack.pop()
                else:
                    # reset counters for next depth
                    if len(sib_counts) <= depth + 1: sib_counts.append({})
                    else: sib_counts[depth + 1] = {}
            else:
                if stack: stack.pop()

        pos = end

    # Trailing text (rare in well-formed XML)
    if pos < len(xml) and stack and not stack[-1].has_text:
        key = build_path_key(tuple((n.ln, n.idx) for n in stack))
        spans[key] = (pos, len(xml))
        stack[-1].has_text = True

    return spans

def index_attribute_value_spans(xml: str) -> Dict[str, Tuple[int, int]]:
    """
    Map: path_key@attrLocalName -> (value_start, value_end) offsets (raw, excluding quotes).
    """
    out: Dict[str, Tuple[int, int]] = {}

    class Node:
        __slots__ = ("ln", "idx")
        def __init__(self, ln: str, idx: int):
            self.ln, self.idx = ln, idx

    stack: List[Node] = []
    sib_counts: List[Dict[str, int]] = [{}]

    for m in TAG_RE.finditer(xml):
        name = m.group("name")
        if name is None:
            continue  # comment, cdata, pi
        ln = local_name(name)
        is_end = (m.group("end") == "/")
        attrs_str = m.group("attrs") or ""
        selfclose = (m.group("selfclose") == "/")

        if not is_end:
            depth = len(stack)
            if len(sib_counts) <= depth: sib_counts.append({})
            idx = sib_counts[depth].get(ln, 0) + 1
            sib_counts[depth][ln] = idx
            stack.append(Node(ln, idx))

            # Attribute scanning inside this tag
            tag_text = m.group(0)           # full "<...>"
            tag_abs_start = m.start()
            if attrs_str:
                attrs_rel_start = tag_text.find(attrs_str)
                if attrs_rel_start != -1:
                    attrs_abs_start = tag_abs_start + attrs_rel_start
                    for am in ATTR_RE.finditer(attrs_str):
                        raw_name = am.group(1)
                        val_span = am.span(3) if am.group(3) is not None else am.span(4)
                        if not val_span: continue
                        val_rel_start, val_rel_end = val_span
                        val_abs_start = attrs_abs_start + val_rel_start
                        val_abs_end   = attrs_abs_start + val_rel_end
                        key = build_path_key(tuple((n.ln, n.idx) for n in stack)) + "@" + local_name(raw_name)
                        out[key] = (val_abs_start, val_abs_end)

            if selfclose and stack:
                stack.pop()
        else:
            if stack: stack.pop()

    return out

def apply_replacements(raw_xml: str, replacements: List[Tuple[int, int, str]]) -> str:
    """
    Apply (start, end, replacement) chunks to raw_xml, in descending start order.
    """
    if not replacements:
        return raw_xml
    replacements = sorted(replacements, key=lambda x: x[0], reverse=True)
    out = raw_xml
    for s, e, rep in replacements:
        if 0 <= s <= e <= len(out):
            out = out[:s] + rep + out[e:]
    return out
