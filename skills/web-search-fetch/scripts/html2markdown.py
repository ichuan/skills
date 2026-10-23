"""Convert HTML to readable Markdown using only Python's standard library."""

import re
import textwrap
from html.parser import HTMLParser
from urllib.parse import urljoin


def html2markdown(source, base_url="", body_width=0, main_content=False):
    """Convert HTML to readable (CommonMark / GFM flavoured) Markdown.

    source      str, bytes/bytearray (charset is sniffed), None, or anything
                ``str()`` accepts.  Broken, partial or deeply nested HTML is fine.
    base_url    used to resolve relative links and images (``<base href>`` in
                the document is honoured too).
    body_width  wrap paragraphs to this many columns; 0 disables wrapping.
    main_content  drop page chrome (navigation, share buttons, related/popular
                lists, promos, cookie banners, comments, hidden elements) and keep
                only the main article.  A pruning step that would remove almost
                everything is undone, so non-article pages degrade gracefully.

    Never raises: if something unexpected happens it degrades to plain text.
    """
    # ------------------------------------------------------------------ input
    if source is None:
        return ""
    if isinstance(source, (bytes, bytearray, memoryview)):
        raw_bytes, enc = bytes(source), None
        for bom, name in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
            if raw_bytes.startswith(bom):
                enc = name
                break
        if enc is None:
            try:
                source = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                m = re.search(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([\w.:-]+)", raw_bytes[:4096], re.I)
                enc = m.group(1).decode("ascii", "ignore") if m else "cp1252"
                if enc.lower().startswith(("utf-16", "utf16", "utf-8", "utf8")):
                    enc = "utf-8"
        if enc is not None:
            try:
                source = raw_bytes.decode(enc, "replace")
            except LookupError:
                source = raw_bytes.decode("cp1252", "replace")
    elif not isinstance(source, str):
        source = str(source)
    # \x00 / \x01 are used internally as break markers; HTML forbids them anyway.
    source = source.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    source = source.replace("\x00", "").replace("\x01", "")
    try:
        width = max(0, int(body_width or 0))
    except (TypeError, ValueError):
        width = 0

    # ------------------------------------------------------------ tag tables
    HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
    BLOCK = frozenset(HEADINGS) | frozenset((
        "address article aside blockquote body caption center details dialog dd dir div dl dt "
        "fieldset figcaption figure footer form header hgroup hr html legend li listing main menu "
        "nav ol p plaintext pre search section summary table tbody td tfoot th thead tr ul xmp"
    ).split())
    VOID = frozenset("area base br col embed hr img input keygen link meta param source track wbr".split())
    SKIP = frozenset("head title script style template svg canvas noscript datalist".split())
    HEAD_OK = frozenset("head base link meta title style script noscript template".split())
    P_CLOSERS = (BLOCK - {"body", "html", "caption", "td", "th", "tr", "tbody", "thead", "tfoot", "legend"}) | {"li", "dd", "dt"}
    SCOPE = frozenset("table td th caption html template object marquee applet".split())
    TABLE_PARTS = frozenset("table caption thead tbody tfoot tr td th".split())
    PRE_TAGS = frozenset(("pre", "listing", "xmp", "plaintext"))
    LINK_DENSITY = 0.8  # blocks with >= 3 links whose text is this much link text are menus/lists
    MAX_DEPTH = 150  # deeper nesting is flattened, so rendering can never hit RecursionError

    WS = re.compile(r"[ \t\n\r\f]+")
    ESC = re.compile(r"[\\`*\[\]~]|(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])|<(?=[A-Za-z/!?])|&(?=#?\w+;)")
    LINE_ESC1 = re.compile(r"(?:#{1,6}|[-+])(?=[ \t]|$)|>|[-=]+[ \t]*$")
    LINE_ESC2 = re.compile(r"\d{1,9}(?=[.)](?:[ \t]|$))")
    BREAKS = re.compile(r"( *[\x00\x01][ \x00\x01]*)")
    SPACES, TICKS, URL_WS = re.compile(" {2,}"), re.compile("`+"), re.compile(r"[\t\n\r]")
    NOISE = re.compile(
        r"(?i)(?:^|[\s_-])(?:share|sharing|social|related|recommend\w*|popular|trending|newsletter|subscri\w*|"
        r"signup|promo\w*|sponsor\w*|advert\w*|ads?|banner|cookie\w*|consent|gdpr|breadcrumbs?|sidebar|widget|"
        r"footer|masthead|navbar|nav|navigation|menu|comments?|disqus|outbrain|taboola|paywall|modal|popup|"
        r"toolbar|loading|loader|spinner|skeleton|tags?|topics?|keywords|most-?read|read-?more|also-?read|"
        r"more-?(?:stories|articles|news)|recirc\w*|you-?may|next-?(?:article|post)|pagination|pager|"
        r"author-?bio|bio|rss)(?=$|[\s_-])")
    BOILER = re.compile(
        r"(?i)(?:advertisement|ad|sponsored( content)?|continue reading( the main story)?|story continues below"
        r"( advertisement)?|read more|related( articles| stories| posts| content)?|share( this)?( article| story)?"
        r"|copy (share )?link|loading( the next article)?|error loading( article)?|skip to (main )?content)\W*")
    PLAYER = re.compile(r"(?i)youtube|youtu\.be|vimeo|dailymotion|player\.|/video|soundcloud|spotify|twitch")
    MAIN = re.compile(r"(?i)(?:^|[\s_-])(?:(?:article|post|entry|story|main|page)[-_]?(?:body|content|text)|articlebody)(?=$|[\s_-])")
    SHARE = re.compile(
        r"(?i)facebook\.com/(?:sharer|share\.php|dialog/(?:share|feed))|(?:twitter|x)\.com/(?:intent/|share)|"
        r"linkedin\.com/(?:shareArticle|sharing/|cws/share)|reddit\.com/submit|pinterest\.[a-z.]+/pin/create|"
        r"t\.me/share|wa\.me/\?|whatsapp\.com/send|whatsapp://send|news\.ycombinator\.com/submitlink|"
        r"getpocket\.com/(?:save|edit)|flipboard\.com/bookmarklet|tumblr\.com/(?:share|widgets/share)|"
        r"^\s*(?:mailto|sms):\?|/cdn-cgi/l/email-protection")
    LANG = re.compile(r"(?:^|\s)(?:lang(?:uage)?-|highlight-(?:source-)?)([\w+#.-]+)")

    # ------------------------------------------------------- build the tree
    # element = [tag, attrs, children, has_block_descendant, skipped, text_len, link_text_len, n_links]
    root = ["#root", {}, [], False, False, 0, 0, 0]
    stack = [root]
    found_base, found_title = [], []

    def find(names, barriers):
        for i in range(len(stack) - 1, 0, -1):
            t = stack[i][0]
            if t in names:
                return i
            if t in barriers:
                return 0
        return 0

    def close_at(i):
        if i:
            del stack[i:]

    class TreeBuilder(HTMLParser):
        in_head = False

        def handle_starttag(self, tag, attrs):
            self.start(tag, attrs, False)

        def handle_startendtag(self, tag, attrs):
            self.start(tag, attrs, True)  # XHTML style <x/>: treat as empty element

        def leave_head(self):
            if self.in_head:
                close_at(find(("head",), ()))
                self.in_head = False

        def start(self, tag, attrs, self_closing):
            if self.in_head and tag not in HEAD_OK and stack[-1][0] == "head":
                self.leave_head()
            if tag in P_CLOSERS:
                close_at(find(("p",), SCOPE | {"button"}))
            if tag == "li":
                close_at(find(("li",), SCOPE | {"ul", "ol", "menu", "dir"}))
            elif tag in ("dt", "dd"):
                close_at(find(("dt", "dd"), SCOPE | {"dl"}))
            elif tag in ("td", "th"):
                close_at(find(("td", "th"), ("tr", "table")))
            elif tag == "tr":
                close_at(find(("tr",), ("table",)))
            elif tag in ("thead", "tbody", "tfoot"):
                close_at(find(("thead", "tbody", "tfoot"), ("table",)))
            elif tag == "a":
                close_at(find(("a",), SCOPE))
            elif tag in HEADINGS and stack[-1][0] in HEADINGS:
                close_at(len(stack) - 1)
            elif tag in ("option", "optgroup") and stack[-1][0] == "option":
                close_at(len(stack) - 1)
            a = {}
            for k, v in attrs:
                if k and k not in a:
                    a[k] = v if v is not None else ""
            parent = stack[-1]
            el = [tag, a, [], False, parent[4] or tag in SKIP, 0, 0, 0]
            parent[2].append(el)
            if tag == "head":
                self.in_head = True
            elif tag == "base" and a.get("href") and not found_base:
                found_base.append(a["href"])
            elif tag == "title" and self.in_head and not found_title:
                found_title.append(el)
            if tag in BLOCK:
                for anc in reversed(stack):
                    if anc[3]:
                        break
                    anc[3] = True
            if tag not in VOID and not self_closing and (len(stack) < MAX_DEPTH or el[4]):
                stack.append(el)

        def handle_endtag(self, tag):
            if tag in VOID:
                if tag == "br":  # browsers treat </br> as <br>
                    self.start("br", [], True)
                return
            if tag in ("html", "body"):
                return  # content after </body> is still body content
            if tag in TABLE_PARTS:
                barriers = () if tag == "table" else ("table",)
            elif tag == "li":
                barriers = SCOPE | {"ul", "ol", "menu", "dir"}
            elif tag in ("dt", "dd"):
                barriers = SCOPE | {"dl"}
            else:
                barriers = SCOPE - {tag}
            i = find((tag,), barriers)
            if i:
                if tag == "head":
                    self.in_head = False
                close_at(i)

        def handle_data(self, data):
            if self.in_head and data.strip() and stack[-1][0] == "head":
                self.leave_head()
            stack[-1][2].append(data)

        def unknown_decl(self, data):
            pass

    # ------------------------------------------------------------- helpers
    base = base_url or ""

    def esc(s, cell):
        s = ESC.sub(r"\\\g<0>", s)
        return s.replace("|", r"\|") if cell else s

    def esc_line(line):
        if LINE_ESC1.match(line):
            return "\\" + line
        m = LINE_ESC2.match(line)
        return line[:m.end()] + "\\" + line[m.end():] if m else line

    def resolve(u):
        u = URL_WS.sub("", u or "").strip()
        if u and base:
            try:
                u = urljoin(base, u)
            except ValueError:  # e.g. malformed IPv6 host
                pass
        return u

    def dest(u, cell):
        u = u.replace(" ", "%20").replace("<", "%3C").replace(">", "%3E")
        if u.count("(") != u.count(")"):
            u = u.replace("(", "%28").replace(")", "%29")
        return u.replace("|", "%7C") if cell else u

    def title_part(t, cell):
        t = WS.sub(" ", t or "").strip().replace("\\", "\\\\").replace('"', '\\"')
        if cell:
            t = t.replace("|", r"\|")
        return f' "{t}"' if t else ""

    def num(value, default):
        m = re.match(r"\s*([+-]?\d{1,12})", value or "")
        return int(m.group(1)) if m else default

    def split_ws(s):
        """Return (leading, core, trailing), moving spaces/breaks out of markup."""
        core = s.strip(" \x00\x01")
        if not core:
            return s, "", ""
        i = s.index(core)
        return s[:i], core, s[i + len(core):]

    def raw_text(el):
        """Text with whitespace preserved (for <pre>); <br> and blocks become newlines."""
        out = []

        def walk(node):
            for k in node[2]:
                if type(k) is str:
                    out.append(k)
                elif k[4]:
                    continue
                elif k[0] == "br":
                    out.append("\n")
                elif k[0] in BLOCK:
                    if out and not out[-1].endswith("\n"):
                        out.append("\n")
                    walk(k)
                    if out and not out[-1].endswith("\n"):
                        out.append("\n")
                else:
                    walk(k)

        walk(el)
        return "".join(out)

    def contains(el, tags):
        todo = list(el[2])
        while todo:
            k = todo.pop()
            if type(k) is list and not k[4]:
                if k[0] in tags:
                    return True
                todo.extend(k[2])
        return False

    def code_span(text, cell):
        text = WS.sub(" ", text)
        lead, core, trail = split_ws(text)
        if not core:
            return text
        ticks = "`" * (max(map(len, TICKS.findall(core)), default=0) + 1)
        pad = " " if core[0] == "`" or core[-1] == "`" else ""
        s = f"{ticks}{pad}{core}{pad}{ticks}"
        return lead + (s.replace("|", r"\|") if cell else s) + trail

    # --------------------------------------------------------- inline layer
    def inline(nodes, ctx):
        cell = ctx["cell"]
        return "".join(esc(WS.sub(" ", n), cell) if type(n) is str else inline_el(n, ctx) for n in nodes)

    def emphasis(el, ctx, key, mark):
        if ctx.get(key):  # <b><b>x</b></b> must not produce ****x****
            return inline(el[2], ctx)
        lead, core, trail = split_ws(inline(el[2], {**ctx, key: True}))
        return f"{lead}{mark}{core}{mark}{trail}" if core else lead

    def link(el, ctx, text=None):
        a, cell = el[1], ctx["cell"]
        nested = ctx.get("a")
        if text is None:
            text = inline(el[2], ctx if nested else {**ctx, "a": True})
        href = a.get("href")
        if href is None or nested:
            return text
        squashed = re.sub(r"[\s\x00-\x1f]", "", href).lower()
        if squashed in ("", "#") or squashed.startswith(("javascript:", "vbscript:")):
            return text
        u = resolve(href)
        lead, core, trail = split_ws(text)
        tip = a.get("title")
        if not core:
            label = WS.sub(" ", a.get("aria-label") or a.get("title") or "").strip()
            if label:
                core, tip = esc(label, cell), None
            elif re.match(r"(?i)(?:https?|ftp|mailto):", u):
                core = esc(u, cell)
            else:
                return text
        return f"{lead}[{core}]({dest(u, cell)}{title_part(tip, cell)}){trail}"

    def image(a, ctx):
        cell = ctx["cell"]
        src = a.get("src") or ""
        lazy = a.get("data-src") or a.get("data-original") or a.get("data-lazy-src")
        if lazy and (not src.strip() or src.strip().startswith("data:")):
            src = lazy
        if not src.strip() and a.get("srcset"):
            first = a["srcset"].strip().split(",")[0].split()
            src = first[0] if first else ""
        alt = esc(WS.sub(" ", a.get("alt") or "").strip(), cell)
        u = resolve(src)
        return f"![{alt}]({dest(u, cell)}{title_part(a.get('title'), cell)})" if u else alt

    def inline_el(el, ctx):
        tag, a, kids = el[0], el[1], el[2]
        if el[4]:
            return ""
        if tag == "br":
            return "\x00"
        if tag in ("strong", "b"):
            return emphasis(el, ctx, "b", "**")
        if tag in ("em", "i", "cite", "dfn", "var"):
            return emphasis(el, ctx, "i", "*")
        if tag in ("del", "s", "strike"):
            return emphasis(el, ctx, "s", "~~")
        if tag in ("code", "kbd", "samp", "tt"):
            cell, parts, buf = ctx["cell"], [], []
            for k in kids + [None]:  # links inside code keep their URL: `a` [`b`](url)
                if k is None or (type(k) is list and k[0] == "a" and k[1].get("href") and not ctx.get("a")):
                    parts.append(code_span("".join(buf), cell))
                    buf = []
                    if k is not None:
                        parts.append(link(k, ctx, code_span(raw_text(k), cell)))
                else:
                    buf.append(k if type(k) is str else raw_text(["", {}, [k]]))
            return "".join(parts)
        if tag in ("sup", "sub"):
            lead, core, trail = split_ws(inline(kids, ctx))
            return f"{lead}<{tag}>{core}</{tag}>{trail}" if core else lead
        if tag == "q":
            return '"' + inline(kids, ctx) + '"'
        if tag == "a":
            return link(el, ctx)
        if tag == "img":
            return image(a, ctx)
        if tag == "input":
            if (a.get("type") or "").lower() == "checkbox":
                return "[x] " if "checked" in a else "[ ] "
            return ""
        if tag in ("iframe", "video", "audio", "embed"):
            src = a.get("src") or next((k[1].get("src") for k in kids if type(k) is list and k[0] == "source" and k[1].get("src")), "")
            if not src.strip():
                return inline(kids, ctx)
            label = esc(WS.sub(" ", a.get("title") or tag).strip(), ctx["cell"])
            return f"[{label}]({dest(resolve(src), ctx['cell'])})"
        if tag in PRE_TAGS:
            lines = [code_span(ln, ctx["cell"]) for ln in raw_text(el).split("\n") if ln.strip()]
            return "\x01" + "\x01".join(lines) + "\x01"
        if tag in ("td", "th", "button", "label"):
            return " " + inline(kids, ctx) + " "
        if tag in BLOCK or tag == "option":
            return "\x01" + inline(kids, ctx) + "\x01"
        return inline(kids, ctx)

    def finalize(s, ctx):
        """Inline string -> list of paragraph strings (handles breaks, escaping, wrapping)."""
        parts = BREAKS.split(SPACES.sub(" ", s))
        paras = [[]]
        for i, p in enumerate(parts):
            if i % 2:
                if p.count("\x00") >= 2:  # <br><br> = paragraph break
                    paras.append([])
            else:
                p = p.strip(" ")
                if p:
                    paras[-1].append(p)
        paras = [p for p in paras if p]
        if ctx["cell"]:
            return ["<br>".join("<br>".join(p) for p in paras)] if paras else []
        if ctx.get("h"):
            return [" ".join(" ".join(p) for p in paras)] if paras else []
        w = ctx["w"]
        result = []
        for p in paras:
            lines = []
            for seg in p:
                wrapped = textwrap.wrap(seg, w, break_long_words=False, break_on_hyphens=False) if w and len(seg) > w else [seg]
                lines.append("\n".join(esc_line(x) for x in (wrapped or [seg])))
            result.append("  \n".join(lines))
        return result

    # ---------------------------------------------------------- block layer
    def blocks(nodes, ctx, out):
        run = []
        for n in nodes:
            if type(n) is list:
                if n[4]:
                    continue
                if n[0] in BLOCK or (n[3] and n[0] != "a"):
                    paragraph(run, ctx, out)
                    run = []
                    block(n, ctx, out)
                    continue
            run.append(n)
        paragraph(run, ctx, out)
        return out

    def paragraph(run, ctx, out):
        if run:
            out.extend(("p", p) for p in finalize(inline(run, ctx), ctx))

    def join(out, tight=False):
        res, prev = [], None
        for kind, text in out:
            if not text:
                continue
            if res:
                # only a non-empty bullet item or an item numbered 1 may interrupt a paragraph
                snug = tight and prev == "p" and kind[:2] in ("ul", "ol") and re.match(r"(?:[-*]|1[.)]) \S", text)
                res.append("\n" if snug else "\n\n")
            res.append(text)
            prev = kind
        return "".join(res)

    def narrower(ctx, by):
        return {**ctx, "w": max(20, ctx["w"] - by) if ctx["w"] else 0}

    def block(el, ctx, out):
        tag, a, kids = el[0], el[1], el[2]
        cell = ctx["cell"]
        if tag in HEADINGS:
            text = " ".join(finalize(inline(kids, ctx), {**ctx, "h": True}))
            if not text:
                return
            if cell:
                out.append(("p", f"**{text}**"))
                return
            text = "\\" + text if re.fullmatch(r"#+", text) else re.sub(r"(\s)(#+)$", r"\1\\\2", text)
            out.append(("h", "#" * HEADINGS[tag] + " " + text))
        elif tag == "hr":
            if not cell:
                out.append(("hr", "---"))
        elif tag in PRE_TAGS:
            text = raw_text(el)
            if text.startswith("\n"):
                text = text[1:]  # HTML ignores the newline right after <pre>
            text = text.rstrip()
            if not text.strip():
                return
            if cell:
                out.append(("p", "<br>".join(code_span(ln, True) for ln in text.split("\n") if ln.strip())))
                return
            m = LANG.search(a.get("class", "")) or next(
                (LANG.search(k[1].get("class", "")) for k in kids if type(k) is list and k[0] == "code" and LANG.search(k[1].get("class", ""))), None)
            fence = "`" * max(3, max(map(len, TICKS.findall(text)), default=0) + 1)
            out.append(("pre", f"{fence}{m.group(1) if m else ''}\n{text}\n{fence}"))
        elif tag == "blockquote":
            text = join(blocks(kids, narrower(ctx, 2), []))
            if text:
                out.append(("p", text) if cell else ("quote", "\n".join("> " + ln if ln else ">" for ln in text.split("\n"))))
        elif tag in ("ul", "ol", "menu", "dir"):
            render_list(el, ctx, out)
        elif tag == "dl":
            render_dl(el, ctx, out)
        elif tag == "table":
            render_table(el, ctx, out)
        else:  # div, p, section, li/td outside their parents, inline tags wrapping blocks, ...
            blocks(kids, ctx, out)

    def render_list(el, ctx, out):
        ordered = el[0] == "ol"
        kind = "ol" if ordered else "ul"
        if out and out[-1][0] == kind:  # adjacent lists would merge: switch marker style
            kind += ")" if ordered else "*"
        items = []
        for k in el[2]:
            if type(k) is list and k[0] == "li" and not k[4]:
                items.append((k, list(k[2])))
            elif type(k) is str and not k.strip() or type(k) is list and k[4]:
                continue
            elif items:
                items[-1][1].append(k)  # stray content inside <ul>: keep it with the previous item
            else:
                items.append((None, [k]))
        if not items:
            return
        step = -1 if ordered and "reversed" in el[1] else 1
        n = num(el[1].get("start"), len(items) if step < 0 else 1)
        rendered = []
        for li, nodes in items:
            if ordered and li is not None and li[1].get("value"):
                n = num(li[1]["value"], n)
            if ordered:
                marker = f"{min(max(n, 0), 999999999)}{')' if kind.endswith(')') else '.'}"
            else:
                marker = "*" if kind.endswith("*") else "-"
            pad = " " * (len(marker) + 1)
            body = join(blocks(nodes, narrower(ctx, len(pad)), []), tight=True).split("\n")
            lines = [marker + (" " + body[0] if body[0] else "")]
            lines += [pad + ln if ln else "" for ln in body[1:]]
            rendered.append("\n".join(lines))
            n += step
        out.append((kind, "\n".join(rendered)))

    def render_dl(el, ctx, out):
        seq = []
        for k in el[2]:
            if type(k) is list and k[0] == "div" and not k[4]:
                seq.extend(k[2])  # HTML5 allows <dl><div><dt>..</dt><dd>..</dd></div></dl>
            else:
                seq.append(k)
        parts, run = [], []
        for k in seq + [None]:
            if k is not None and not (type(k) is list and k[0] in ("dt", "dd")):
                run.append(k)
                continue
            if run:
                parts.extend(blocks(run, ctx, []))
                run = []
            if k is None or k[4]:
                continue
            if k[0] == "dt":
                text = " ".join(finalize(inline(k[2], ctx), {**ctx, "h": True}))
                if text:
                    parts.append(("dt", f"**{text}**"))
            else:
                sub = blocks(k[2], narrower(ctx, 2), [])
                body = join(sub).split("\n")
                if body[0]:
                    # ": " is not a CommonMark container, so only a paragraph may share its line
                    head = [": " + body[0]] if sub[0][0] == "p" else [":", "", "  " + body[0]]
                    parts.append(("dd", "\n".join(head + ["  " + ln if ln else "" for ln in body[1:]])))
        text, prev = [], None
        for kind, t in parts:
            if text:
                text.append("\n" if kind == "dd" or (prev == "dt" and kind == "dt") else "\n\n")
            text.append(t)
            prev = kind
        if text:
            out.append(("dl", "".join(text)))

    def render_table(el, ctx, out):
        rows, captions, stray = [], [], []

        def walk(node):
            for k in node[2]:
                if type(k) is str:
                    if k.strip():
                        stray.append(k)
                elif k[4] or k[0] in ("colgroup", "col"):
                    continue
                elif k[0] == "tr":
                    cells = []
                    for c in k[2]:
                        if type(c) is list and c[0] in ("td", "th"):
                            cells.append(c)
                        elif type(c) is list and not c[4] or type(c) is str and c.strip():
                            stray.append(c)
                    rows.append(cells)
                elif k[0] in ("td", "th"):
                    rows.append([k])
                elif k[0] == "caption":
                    captions.append(k)
                elif k[0] in ("thead", "tbody", "tfoot", "form"):
                    walk(k)
                else:
                    stray.append(k)  # browsers "foster-parent" such content before the table

        walk(el)
        blocks(stray, ctx, out)
        for c in captions:
            blocks(c[2], ctx, out)
        rows = [r for r in rows if r]
        ncols = max((sum(min(max(num(c[1].get("colspan"), 1), 1), 100) for c in r) for r in rows), default=0)
        cells_all = [c for r in rows for c in r]
        layout = (
            ctx["cell"] or ncols == 0 or (len(rows) == 1 and ncols == 1)
            or any(contains(c, ("table",)) for c in cells_all)
            or (len(rows) == 1 and any(contains(c, PRE_TAGS) for c in cells_all))
        )
        if layout:  # layout table: emit cell contents as ordinary blocks
            for c in cells_all:
                blocks(c[2], ctx, out)
            return
        cctx = {**ctx, "cell": True, "w": 0}
        grid, pending, aligns = [], {}, {}
        for ri, r in enumerate(rows):
            line, col = [], 0
            for c in r:
                while pending.get(col, 0) > 0:
                    line.append("")
                    pending[col] -= 1
                    col += 1
                text = "<br>".join(ln.strip() for ln in join(blocks(c[2], cctx, [])).split("\n") if ln.strip())
                span = min(max(num(c[1].get("colspan"), 1), 1), 100)
                rspan = num(c[1].get("rowspan"), 1)
                rspan = len(rows) - ri if rspan == 0 else min(max(rspan, 1), len(rows) - ri)
                if ri == 0:
                    al = (c[1].get("align") or "").lower()
                    m = re.search(r"text-align\s*:\s*(left|right|center)", c[1].get("style", ""), re.I)
                    aligns[col] = m.group(1).lower() if m else al
                for j in range(span):
                    line.append(text if j == 0 else "")
                    if rspan > 1:
                        pending[col] = rspan - 1
                    col += 1
            while pending.get(col, 0) > 0:
                line.append("")
                pending[col] -= 1
                col += 1
            for k in pending:
                if k >= col and pending[k] > 0:
                    pending[k] -= 1
            grid.append(line)
        n = max(map(len, grid))
        grid = [g + [""] * (n - len(g)) for g in grid]
        grid = grid[:1] + [g for g in grid[1:] if any(g)]
        rule = [{"left": ":---", "center": ":---:", "right": "---:"}.get(aligns.get(i, ""), "---") for i in range(n)]
        lines = ["| " + " | ".join(g) + " |" for g in [grid[0], rule] + grid[1:]]
        out.append(("table", "\n".join(lines)))

    # ------------------------------------------------- main-content extraction
    def measure(el, linked=False):
        """Fill text / link-text / link counts for el's visible subtree."""
        is_link = el[0] == "a" and el[1].get("href") is not None
        inside, t, l, n = linked or is_link, 0, 0, int(is_link)
        for k in el[2]:
            if type(k) is str:
                c = len(k.strip())
                t += c
                l += c if inside else 0
            elif not k[4]:
                measure(k, inside)
                t, l, n = t + k[5], l + k[6], n + k[7]
        el[5], el[6], el[7] = t, l, n

    def elements(el):
        return [k for k in el[2] if type(k) is list and not k[4]]

    def labels(a):
        """class + id; long ids are usually heading slugs ("sharing-with-a-team"), not labels."""
        ident = a.get("id", "")
        return a.get("class", "") + " " + (ident if ident.count("-") + ident.count("_") <= 2 else "")

    def is_main_candidate(e):
        a = e[1]
        return (e[0] in ("article", "main") or (a.get("role") or "").lower() == "main"
                or (a.get("itemprop") or "").lower() == "articlebody"
                or bool(MAIN.search(labels(a)))) and not NOISE.search(labels(a))

    def outermost_candidates(cur, need):
        found, todo = [], elements(cur)
        while todo:
            e = todo.pop()
            if e[5] >= need and is_main_candidate(e):
                found.append(e)
            elif e[5] >= need:  # smaller subtrees cannot hold a big enough candidate
                todo.extend(elements(e))
        return found

    def first(el, tag):
        todo = elements(el)[::-1]
        while todo:
            e = todo.pop()
            if e[0] == tag:
                return e
            todo.extend(elements(e)[::-1])
        return None

    def is_noise(e, limit):
        tag, a = e[0], e[1]
        if tag == "a":
            return bool(SHARE.search(a.get("href") or ""))
        if tag == "iframe":
            return not PLAYER.search(a.get("src") or "")
        if tag in BLOCK and e[5] < 60 and BOILER.fullmatch(WS.sub(" ", raw_text(e)).strip()):
            return True
        role = (a.get("role") or "").lower()
        style = (a.get("style") or "").replace(" ", "").lower()
        bad = (
            "hidden" in a or (a.get("aria-hidden") or "").lower() == "true"
            or "display:none" in style or "visibility:hidden" in style
            or tag in ("nav", "aside", "footer", "form", "button", "dialog", "header")
            or role in ("navigation", "contentinfo", "complementary", "search", "dialog",
                        "alertdialog", "menu", "menubar", "toolbar", "banner")
            or bool(NOISE.search(labels(a)))
        )
        # size guard: never drop something holding a big share of the content or the title
        return bad and e[5] <= limit and not contains(e, ("h1",))

    def is_link_farm(e, limit):
        tag, t, l, n = e[0], e[5], e[6], e[7]
        if tag in PRE_TAGS or tag in TABLE_PARTS and tag != "table" or not (tag in BLOCK or e[3]):
            return False
        if n >= 3 and l >= LINK_DENSITY * t:  # menus, tag clouds, "most popular"/"related" lists
            return not contains(e, ("h1",))
        if n >= 3 and l >= 0.4 * t and t <= limit:  # teaser grids: >= 3 headings that are nothing but a link
            todo, linked = elements(e), 0
            while todo and linked < 3:
                k = todo.pop()
                if k[0] in HEADINGS:
                    linked += k[0] != "h1" and k[5] > 0 and k[6] >= 0.9 * k[5]
                else:
                    todo.extend(elements(k))
            if linked >= 3:
                return True
        return t == 0 and tag != "hr" and not contains(e, ("img", "picture", "video", "audio", "iframe", "embed"))

    def extract_main():
        """Mark noise as skipped; return (element to render, title element/text or None)."""
        measure(root)
        total, scope = root[5], root
        tops = outermost_candidates(root, 0.2 * total)
        while len(tops) == 1:  # descend while one nested candidate keeps most of the text
            scope = tops[0]
            tops = outermost_candidates(scope, 0.8 * scope[5])
        marked = []

        def kill(e):
            e[4] = True
            marked.append(e)

        def is_heading(e):
            kids = elements(e)
            return e[0] in HEADINGS or (len(kids) == 1 and kids[0][0] in HEADINGS
                                        and not any(type(x) is str and x.strip() for x in e[2]))

        def prune(el, test):
            killed = set()
            for k in elements(el):
                if test(k):
                    kill(k)
                    killed.add(id(k))
                else:
                    prune(k, test)
            head = gone = None  # drop a heading whose whole section was removed ("## Most Popular")
            for k in el[2] + [None] if killed else ():
                if type(k) is str and not k.strip() or type(k) is list and k[4] and id(k) not in killed:
                    continue
                if type(k) is str:
                    head = None
                elif k is None or is_heading(k):
                    if head is not None and gone:
                        kill(head)
                    head, gone = k, False
                elif id(k) in killed:
                    gone = True
                else:
                    head = None

        def stage(test):  # prune; undo this stage alone if it wiped out the content
            n0, before = len(marked), scope[5]
            prune(scope, test)
            measure(scope)
            if scope[5] < min(200, 0.5 * before):
                for e in marked[n0:]:
                    e[4] = False
                del marked[n0:]
                measure(scope)

        limit = 0.4 * scope[5]
        stage(lambda e: is_noise(e, limit))
        stage(lambda e: is_link_farm(e, limit))
        title = None
        if first(scope, "h1") is None:
            title = first(root, "h1") or (found_title and WS.sub(" ", "".join(
                k for k in found_title[0][2] if type(k) is str)).strip()) or None
        return scope, title

    # ----------------------------------------------------------------- run
    try:
        parser = TreeBuilder(convert_charrefs=True)
        parser.feed(source)
        parser.close()
        if found_base:
            base = resolve(found_base[0]) if base else found_base[0].strip()
        ctx0, out = {"cell": False, "w": width}, []
        if not main_content:
            return join(blocks(root[2], ctx0, out)).strip("\n")
        scope, title = extract_main()
        if type(title) is list:
            block(title, ctx0, out)
        elif title:
            out.append(("h", "# " + esc(title, False)))
        return join(blocks(root[2] if scope is root else [scope], ctx0, out)).strip("\n")
    except Exception:  # last-resort safety net: never lose the text
        from html import unescape
        text = re.sub(r"(?is)<(script|style|head|template)\b.*?</\1\s*>|<!--.*?-->", " ", source)
        text = re.sub(r"(?i)<(?:br|/p|/div|/h\d|/li|/tr)\b[^>]*>", "\n", text)
        text = unescape(re.sub(r"<[^>]*>", " ", text))
        return "\n".join(ln for ln in (WS.sub(" ", x).strip() for x in text.split("\n")) if ln)
