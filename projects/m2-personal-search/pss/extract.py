"""File -> Extracted: cleaned text in UNITS (one per PDF page, one for everything else) + metadata.

Why units: a citation in a personal tool is only useful if you can open the file at the right
place. ragkit's PDF loader joins all pages into one text (good for a company corpus, where the
section is the address); here every PDF page becomes its own unit, so every chunk carries
`page`, and the web UI opens `file.pdf#page=N`.

Formats:
- .md .txt .html .docx  -> ragkit.loaders (boilerplate removal for HTML saves, headings as '#').
- .pdf  -> pypdf, page by page, "plain" extraction + the Hebrew fixes below. A page with almost
           no text is probably a scan: it is rendered (pypdfium2) and OCR'd when OCR is on.
- images -> Tesseract OCR (`tesseract img stdout -l heb+eng`) when installed. Without OCR the
           image is still indexed by its file name, and the result says "no OCR".

Hebrew in PDFs, measured on the sample (Chromium "Print to PDF", like a browser or Word):
- pypdf "layout" mode returns every Hebrew line REVERSED ("םכסה" for "הסכם"). ragkit's PDF
  loader uses layout mode by default (it keeps table rows), so it cannot be used as is here.
- "plain" mode returns Hebrew words in logical order, but a number next to Hebrew text can
  jump to the other end of the line and stick to a word: "שלושה12,600". BM25 would then index
  "שלושה12" and never match "12,600".
So: (1) a line whose words start with final letters (ך ם ן ף ץ) or end with non-final מ נ צ פ כ
is reversed back; (2) a space is forced between Hebrew letters and digits; (3) ligatures that
some PDF fonts use (ﬁ ﬂ) are expanded, or "Netﬂix" never matches "netflix".
"""

from __future__ import annotations

import io
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ragkit.clean import dehyphenate, guess_language, normalize
from ragkit.loaders import load_document

from .scan import IMAGE_EXT, FileEntry

LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
HEB_WORD = re.compile(r"[א-ת]{2,}")
FINALS = set("ךםןףץ")
NONFINAL_AT_END = set("מנצפכ")
LTR_RUN = re.compile(r"[%$€₪]?[A-Za-z0-9][A-Za-z0-9.,:%/+\- ]*[A-Za-z0-9%]|[%$€₪]?[A-Za-z0-9]")
MIRROR = str.maketrans({"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{", "<": ">", ">": "<"})
DATE_IN_NAME = re.compile(r"(?<!\d)(20[1-3]\d)(?:[-_.](0[1-9]|1[0-2])(?:[-_.](0[1-9]|[12]\d|3[01]))?)?(?!\d)")


@dataclass
class Unit:
    page: Optional[int]     # 1-based PDF page, None for formats without pages
    text: str


@dataclass
class Extracted:
    id: str
    title: str
    format: str
    language: str
    date: str               # YYYY-MM-DD (start of the period when the name only says 2026 or 2026-03)
    date_source: str        # filename | metadata | mtime
    units: list[Unit]
    ocr: bool = False
    warnings: list[str] = field(default_factory=list)
    pages: int = 0

    @property
    def text(self) -> str:
        return "\n\n".join(u.text for u in self.units if u.text)


# ------------------------------------------------------------------ Hebrew PDF fixes
def order_evidence(line: str) -> tuple[int, int]:
    """(visual-order evidence, logical-order evidence) for one line with Hebrew words."""
    rev = log = 0
    for w in HEB_WORD.findall(line):
        if w[0] in FINALS:
            rev += 1
        if w[-1] in NONFINAL_AT_END:
            rev += 1
        if w[-1] in FINALS:
            log += 1
    s = line.strip()
    if re.match(r"^[.,:;!?]", s):
        rev += 1                       # the sentence's final period sits at the left end
    if re.search(r"[.,:;!?]$", s):
        log += 1
    return rev, log


def looks_reversed(line: str) -> bool:
    rev, log = order_evidence(line)
    return rev > log


def unreverse(line: str) -> str:
    """Reverse a visual-order line, mirror brackets, then put left-to-right runs (numbers,
    Latin words, "3%", "08:00-18:00") back in their own order."""
    r = line[::-1].translate(MIRROR)
    return LTR_RUN.sub(lambda m: m.group(0)[::-1], r)


def fix_line(line: str, visual: bool) -> str:
    if visual and HEB_WORD.search(line):
        line = unreverse(line)
    elif visual:
        m = re.match(r"^([.,:;!?]+)(\S.*)$", line.strip())
        if m:                              # "10:40." wrapped onto its own line in an RTL page
            line = m.group(2) + m.group(1)
    line = re.sub(r"([א-ת][.,:;)(]?)(\d)", r"\1 \2", line)
    return re.sub(r"(\d)([א-ת])", r"\1 \2", line)


def page_is_visual(lines: list[str]) -> bool:
    """Decide visual vs logical order for the whole PAGE: short lines like "רכשומה .1" carry no
    evidence of their own, but a page has plenty."""
    rev = log = 0
    for line in lines:
        if HEB_WORD.search(line):
            a, b = order_evidence(line)
            rev, log = rev + a, log + b
    return rev > log


def fix_pdf_text(text: str) -> str:
    """One page of raw text, line by line (order fixed, ligatures expanded)."""
    lines = text.translate(LIGATURES).split("\n")
    visual = page_is_visual(lines)
    return dehyphenate("\n".join(fix_line(ln, visual) for ln in lines))


def fix_pdf_boxes(boxes: list[list[str]]) -> str:
    """One page as text boxes (pdfminer's paragraphs), each a list of visual lines. Lines are
    fixed one by one, THEN the wrapped lines of a box are joined into one paragraph, so that
    "...בשעה" + "10:40." becomes one sentence again (an answer cut at a line break loses the time)."""
    boxes = [[ln.translate(LIGATURES) for ln in b] for b in boxes]
    visual = page_is_visual([ln for b in boxes for ln in b])
    paras = []
    for b in boxes:
        lines = [fix_line(ln, visual).strip() for ln in b if ln.strip()]
        if lines:
            paras.append(" ".join(dehyphenate("\n".join(lines)).split("\n")))
    return "\n\n".join(paras)


# ------------------------------------------------------------------ OCR
@lru_cache(maxsize=1)
def tesseract_langs() -> tuple[str, ...]:
    exe = shutil.which("tesseract")
    if not exe:
        return ()
    try:
        out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20)
    except Exception:
        return ()
    lines = (out.stdout + out.stderr).splitlines()
    return tuple(ln.strip() for ln in lines if ln.strip() and " " not in ln.strip() and ":" not in ln)


def ocr_status(mode: str, langs: str) -> tuple[bool, str, list[str]]:
    """(enabled, languages to use, warnings)."""
    if mode == "off":
        return False, "", []
    have = tesseract_langs()
    if not have:
        msg = "OCR: tesseract is not installed (sudo apt install tesseract-ocr tesseract-ocr-heb)"
        if mode == "on":
            raise RuntimeError(msg)
        return False, "", [msg]
    want = [x for x in langs.split("+") if x]
    use = [x for x in want if x in have]
    warn = [f"OCR: language '{x}' is missing (sudo apt install tesseract-ocr-{x})" for x in want if x not in have]
    if not use:
        return False, "", warn
    return True, "+".join(use), warn


def ocr_image(data: bytes, langs: str) -> str:
    exe = shutil.which("tesseract")
    out = subprocess.run([exe, "stdin", "stdout", "-l", langs, "--psm", "4"], input=data,
                         capture_output=True, timeout=120)
    return out.stdout.decode("utf-8", errors="replace")


def render_pdf_page_png(data: bytes, index: int, scale: float = 2.5) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    img = pdf[index].render(scale=scale).to_pil()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ------------------------------------------------------------------ dates
def date_from_name(name: str) -> Optional[str]:
    m = DATE_IN_NAME.search(name)
    if not m:
        return None
    y, mo, d = m.group(1), m.group(2) or "01", m.group(3) or "01"
    return f"{y}-{mo}-{d}"


def pdf_meta_date(reader) -> Optional[str]:
    try:
        raw = str((reader.metadata or {}).get("/CreationDate") or "")
    except Exception:
        return None
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})", raw)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def pick_date(entry: FileEntry, meta_date: Optional[str]) -> tuple[str, str]:
    """The file name wins (people name files after the document date: receipt-2026-03.pdf),
    then the document's own metadata, then the modification time (often just the copy date)."""
    d = date_from_name(entry.path.name)
    if d:
        return d, "filename"
    if meta_date:
        return meta_date, "metadata"
    return datetime.fromtimestamp(entry.mtime, tz=timezone.utc).strftime("%Y-%m-%d"), "mtime"


# ------------------------------------------------------------------ extract
def pdf_page_boxes(data: bytes) -> list[list[list[str]]]:
    """Raw text per page, as boxes of lines. pdfminer.six returns RTL lines in pure visual order
    (every character reversed, numbers in place), which unreverse() turns back into logical
    order exactly. Without pdfminer, pypdf's plain mode is the fallback (one line per box;
    words intact, but numbers next to Hebrew may move)."""
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LAParams, LTTextContainer
    except ImportError:
        from pypdf import PdfReader
        return [[[ln] for ln in (p.extract_text() or "").split("\n")] for p in PdfReader(io.BytesIO(data)).pages]
    pages = []
    for layout in extract_pages(io.BytesIO(data), laparams=LAParams(line_margin=1.0)):
        pages.append([el.get_text().rstrip("\n").split("\n") for el in layout if isinstance(el, LTTextContainer)])
    return pages


def pdf_page_texts(data: bytes) -> list[str]:
    """Raw (unfixed) text per page, for inspection."""
    return ["\n".join(ln for b in page for ln in b) for page in pdf_page_boxes(data)]


def _pdf(entry: FileEntry, ocr_on: bool, langs: str) -> Extracted:
    from pypdf import PdfReader

    data = entry.path.read_bytes()
    reader = PdfReader(io.BytesIO(data))
    units, used_ocr, warnings = [], False, []
    for i, boxes in enumerate(pdf_page_boxes(data)):
        text = normalize(fix_pdf_boxes(boxes))
        if len(text) < 25:
            if ocr_on:
                try:
                    text = normalize(ocr_image(render_pdf_page_png(data, i), langs))
                    used_ocr = True
                except Exception as exc:
                    warnings.append(f"page {i + 1}: OCR failed ({type(exc).__name__})")
            else:
                warnings.append(f"page {i + 1}: almost no text (a scan?) and OCR is off")
        units.append(Unit(page=i + 1, text=text))
    title = ""
    try:
        title = str((reader.metadata or {}).get("/Title") or "")
    except Exception:
        pass
    if not title:
        first = next((u.text for u in units if u.text), "")
        title = first.split("\n")[0][:80] if first else entry.path.stem
    date, src = pick_date(entry, pdf_meta_date(reader))
    full = " ".join(u.text for u in units)
    return Extracted(id=entry.id, title=title, format="pdf", language=guess_language(full), date=date,
                     date_source=src, units=units, ocr=used_ocr, warnings=warnings, pages=len(units))


def _image(entry: FileEntry, ocr_on: bool, langs: str) -> Extracted:
    date, src = pick_date(entry, None)
    if ocr_on:
        text = normalize(ocr_image(entry.path.read_bytes(), langs))
        return Extracted(id=entry.id, title=entry.path.stem, format="image", language=guess_language(text),
                         date=date, date_source=src, units=[Unit(None, text)], ocr=True)
    words = re.sub(r"[-_.]+", " ", entry.path.stem)
    return Extracted(id=entry.id, title=entry.path.stem, format="image", language="", date=date,
                     date_source=src, units=[Unit(None, f"[image, no OCR] {words}")],
                     warnings=["image indexed by file name only (OCR is off or unavailable)"])


def _docx_date(path: Path) -> Optional[str]:
    try:
        import docx

        c = docx.Document(str(path)).core_properties.created
        return c.strftime("%Y-%m-%d") if c else None
    except Exception:
        return None


def extract(entry: FileEntry, *, ocr: str = "auto", ocr_langs: str = "heb+eng") -> Extracted:
    ocr_on, langs, ocr_warn = ocr_status(ocr, ocr_langs) if (entry.ext == ".pdf" or entry.ext in IMAGE_EXT) \
        else (False, "", [])
    if entry.ext == ".pdf":
        ex = _pdf(entry, ocr_on, langs)
    elif entry.ext in IMAGE_EXT:
        ex = _image(entry, ocr_on, langs)
    else:
        doc = load_document(entry.path)
        fmt = doc.meta.get("format") or entry.ext.lstrip(".")
        date, src = pick_date(entry, _docx_date(entry.path) if entry.ext == ".docx" else None)
        ex = Extracted(id=entry.id, title=str(doc.meta.get("title") or entry.path.stem), format=fmt,
                       language=doc.language or guess_language(doc.text), date=date, date_source=src,
                       units=[Unit(None, doc.text)])
    ex.warnings += ocr_warn if (entry.ext in IMAGE_EXT or ex.ocr) else []
    return ex
