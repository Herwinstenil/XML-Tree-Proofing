from lxml import etree as LET
import html, re, difflib

# ---------- tag / path helpers ----------

def local_name(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:       # {ns}local
        tag = tag.split("}", 1)[1]
    if ":" in tag:       # prefix:local
        tag = tag.split(":", 1)[1]
    return tag

def _index_in_parent(elem: LET._Element) -> int:
    parent = elem.getparent()
    if parent is None:
        return 1
    ln = local_name(elem.tag)
    same = [e for e in parent if isinstance(e.tag, str) and local_name(e.tag) == ln]
    return same.index(elem) + 1

def build_path(elem: LET._Element):
    """Return tuple of (localName, 1-based index) steps from root to elem."""
    steps = []
    cur = elem
    while cur is not None and isinstance(cur.tag, str):
        steps.append((local_name(cur.tag), _index_in_parent(cur)))
        cur = cur.getparent()
    return tuple(reversed(steps))

# ---------- HTML escaping ----------

def escape_xml(s: str) -> str:
    """Escape for HTML display (don’t change quotes handling of inner HTML we build)."""
    return html.escape(s, quote=False)

# ---------- token-level inline diff (for display only) ----------

TOKEN_RE = re.compile(r'[\w\-]+|[^\s\w]+|\s+')

def split_tokens(s: str):
    return TOKEN_RE.findall(s) or [s]

def token_diff_html(old_text: str, new_text: str):
    """
    Returns a pair (left_html, right_html) highlighting:
      - deletions in LEFT with .editOldInline
      - insertions in RIGHT with .editNewInline
    """
    a = split_tokens(old_text or "")
    b = split_tokens(new_text or "")

    def keyify(tokens):
        out = []
        for t in tokens:
            out.append(" " if t.isspace() else t.casefold())
        return out

    sm = difflib.SequenceMatcher(a=keyify(a), b=keyify(b), autojunk=False)
    L, R = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        a_seg = "".join(a[i1:i2])
        b_seg = "".join(b[j1:j2])
        if tag == "equal":
            L.append(escape_xml(a_seg))
            R.append(escape_xml(b_seg))
        elif tag == "delete":
            L.append(f'<span class="editOldInline">{escape_xml(a_seg)}</span>')
        elif tag == "insert":
            R.append(f'<span class="editNewInline">{escape_xml(b_seg)}</span>')
        elif tag == "replace":
            L.append(f'<span class="editOldInline">{escape_xml(a_seg)}</span>')
            R.append(f'<span class="editNewInline">{escape_xml(b_seg)}</span>')
    return "".join(L), "".join(R)

# ---------- tree rendering with injected focus ----------

def render_full_tree_with_injected(root: LET._Element, steps, injected_html: str, kind: str = "text", attr: str = None):
    """
    Render the entire XML tree to HTML, escaping tags, and:
      - if kind == "text": wrap the target element's .text with
        <span id="focusAnchor" class="focusTarget"> {injected_html} </span>
      - if kind == "attr": wrap ONLY the specified attribute value on that element
        with the same anchor span (value is HTML-escaped).

    Parameters:
      root:  lxml element (root)
      steps: tuple of (localName, index) path to the target element
      injected_html: already-diffed HTML fragment to place for the text case
      kind: "text" or "attr"
      attr: attribute name (local) when kind == "attr"
    """
    target_attr_local = (attr or "").split(":")[-1] if attr else None

    def render_elem(elem: LET._Element):
        if not isinstance(elem.tag, str):
            return ""
        # Build path to decide if this is the target element
        cur = elem
        tmp = []
        while cur is not None and isinstance(cur.tag, str):
            tmp.append((local_name(cur.tag), _index_in_parent(cur)))
            cur = cur.getparent()
        is_target = (tuple(reversed(tmp)) == steps)

        # Render attributes (escape values), and inject focus if kind == "attr" and is_target
        attr_items = []
        for k, v in elem.attrib.items():
            ln = k.split(":")[-1]
            if is_target and kind == "attr" and target_attr_local == ln:
                val_html = f'<span id="focusAnchor" class="focusTarget">{html.escape(v, quote=True)}</span>'
            else:
                val_html = html.escape(v, quote=True)
            attr_items.append(f'{k}="{val_html}"')
        attrs = " ".join(attr_items)

        open_tag  = f"&lt;{local_name(elem.tag)}{(' ' + attrs) if attrs else ''}&gt;"
        close_tag = f"&lt;/{local_name(elem.tag)}&gt;"

        inner = ""
        if elem.text:
            if is_target and kind == "text":
                # Inject the provided diff HTML for this element’s text
                inner += f'<span id="focusAnchor" class="focusTarget">{injected_html}</span>'
            else:
                inner += escape_xml(elem.text)

        for child in elem:
            inner += render_elem(child)
            if child.tail:
                inner += escape_xml(child.tail)

        return open_tag + inner + close_tag

    return render_elem(root)
