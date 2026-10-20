#!/usr/bin/env python3
"""
USFM → JSON.

USFM is a typesetting format, not a data format: the same file carries the
scripture text, footnotes, cross references, section headings, poetry
indentation and word-level lemma tags, all as backslash markers. Pulling clean
verse text out of it means knowing which markers wrap content to discard and
which merely decorate content to keep.

The distinction that matters:

  \\f … \\f*  and  \\x … \\x*     footnotes and cross references — the content
                                 between them is editorial apparatus, not
                                 scripture, and must be removed WHOLE. Stripping
                                 only the markers would splice a footnote into
                                 the middle of a verse.

  \\w word|strong="H1234"\\w*     word-level markup — the word IS the text. Keep
                                 what is before the pipe, drop the attributes.

  \\add \\wj \\nd \\qt …          character styling — unwrap, keep the text.

  \\p \\q1 \\m \\b …              paragraph and poetry breaks — structural, drop
                                 the marker but keep what follows on the line,
                                 because a verse often continues across one.

Verse numbers can be ranges (\\v 1-2) or segments (\\v 1a). The leading integer
is taken as the verse number and the original string is preserved alongside, so
nothing is silently lost.
"""

import json
import re
import sys
import zipfile
from pathlib import Path

# Canonical order and English names, keyed by USFM book id.
BOOKS = [
    ('GEN', 'Genesis'), ('EXO', 'Exodus'), ('LEV', 'Leviticus'), ('NUM', 'Numbers'),
    ('DEU', 'Deuteronomy'), ('JOS', 'Joshua'), ('JDG', 'Judges'), ('RUT', 'Ruth'),
    ('1SA', '1 Samuel'), ('2SA', '2 Samuel'), ('1KI', '1 Kings'), ('2KI', '2 Kings'),
    ('1CH', '1 Chronicles'), ('2CH', '2 Chronicles'), ('EZR', 'Ezra'), ('NEH', 'Nehemiah'),
    ('EST', 'Esther'), ('JOB', 'Job'), ('PSA', 'Psalms'), ('PRO', 'Proverbs'),
    ('ECC', 'Ecclesiastes'), ('SNG', 'Song of Solomon'), ('ISA', 'Isaiah'), ('JER', 'Jeremiah'),
    ('LAM', 'Lamentations'), ('EZK', 'Ezekiel'), ('DAN', 'Daniel'), ('HOS', 'Hosea'),
    ('JOL', 'Joel'), ('AMO', 'Amos'), ('OBA', 'Obadiah'), ('JON', 'Jonah'),
    ('MIC', 'Micah'), ('NAM', 'Nahum'), ('HAB', 'Habakkuk'), ('ZEP', 'Zephaniah'),
    ('HAG', 'Haggai'), ('ZEC', 'Zechariah'), ('MAL', 'Malachi'),
    ('MAT', 'Matthew'), ('MRK', 'Mark'), ('LUK', 'Luke'), ('JHN', 'John'),
    ('ACT', 'Acts'), ('ROM', 'Romans'), ('1CO', '1 Corinthians'), ('2CO', '2 Corinthians'),
    ('GAL', 'Galatians'), ('EPH', 'Ephesians'), ('PHP', 'Philippians'), ('COL', 'Colossians'),
    ('1TH', '1 Thessalonians'), ('2TH', '2 Thessalonians'), ('1TI', '1 Timothy'),
    ('2TI', '2 Timothy'), ('TIT', 'Titus'), ('PHM', 'Philemon'), ('HEB', 'Hebrews'),
    ('JAS', 'James'), ('1PE', '1 Peter'), ('2PE', '2 Peter'), ('1JN', '1 John'),
    ('2JN', '2 John'), ('3JN', '3 John'), ('JUD', 'Jude'), ('REV', 'Revelation'),
]
ORDER = {code: n + 1 for n, (code, _) in enumerate(BOOKS)}
NAMES = dict(BOOKS)

# Footnotes and cross references, removed whole. Non-greedy so adjacent notes
# do not collapse into one giant match.
NOTES = re.compile(r'\\(f|fe|x|ef|ex)\b.*?\\\1\*', re.S)
# A note left unclosed at end of line still has to go.
NOTE_OPEN = re.compile(r'\\(f|fe|x|ef|ex)\b.*?$', re.M)
# \w word|lemma="x"\w*  →  word     (also \+w, \rb, \qt-s etc. with attributes)
ATTRIBUTED = re.compile(r'\\\+?(?:w|rb|qt-s|qt-e)\b\s*([^|\\]*?)(?:\|[^\\]*?)?\\\+?(?:w|rb|qt-s|qt-e)\*')
# Any remaining marker: \p, \q1, \add, \add*, \wj*, \+nd …
MARKER = re.compile(r'\\\+?[a-zA-Z][a-zA-Z0-9-]*\*?')
WS = re.compile(r'[ \t\u00a0]+')


def clean(text: str) -> str:
    """Scripture text with the apparatus removed and the words kept."""
    text = NOTES.sub(' ', text)
    text = NOTE_OPEN.sub(' ', text)
    text = ATTRIBUTED.sub(r'\1', text)
    text = MARKER.sub(' ', text)
    text = text.replace('//', ' ')            # optional line break
    # The pilcrow is a paragraph mark some editions carry as literal text. It
    # is typography, not scripture, and would otherwise open John 3:16 with a
    # stray glyph in every consumer of this data.
    text = text.replace('\u00b6', ' ')
    text = WS.sub(' ', text)
    # Tidy spacing the markers left behind, without touching the words.
    text = re.sub(r'\s+([,.;:!?])', r'\1', text)
    return text.strip()


def parse_usfm(src: str):
    """(book_id, [{chapter, verses:[{verse, text}]}]) from one USFM file."""
    m = re.search(r'^\\id\s+(\w+)', src, re.M)
    if not m:
        return None, [], None
    book = m.group(1).upper()

    # The book's name in its own language. \toc1 is the long form a table of
    # contents uses, \h the running header; most texts carry at least one.
    # Without this a Telugu or Arabic reader is shown "Genesis".
    local = None
    # \h (running header) before \toc1: both carry the book's name, but in
    # some editions \toc1 is the long ceremonial title — the KJV's is "The
    # First Book of Moses, called Genesis" where \h is simply "Genesis".
    # \toc2 is sometimes an abbreviation, so it ranks below both.
    for marker in (r'\\h', r'\\toc1', r'\\toc2', r'\\mt1'):
        lm = re.search(marker + r'\s+(.+)$', src, re.M)
        if lm:
            cand = clean(lm.group(1))
            if cand:
                local = cand
                break

    chapters, chapter, verses = [], None, []
    cur_num, cur_raw, cur_parts = None, None, []

    def flush_verse():
        if cur_num is None:
            return
        text = clean(' '.join(cur_parts))
        if text:
            v = {'verse': cur_num, 'text': text}
            if cur_raw != str(cur_num):
                v['ref'] = cur_raw          # '1-2' or '1a' — kept, not discarded
            verses.append(v)

    def flush_chapter():
        flush_verse()
        if chapter is not None and verses:
            chapters.append({'chapter': chapter, 'verses': list(verses)})

    for line in src.split('\n'):
        line = line.rstrip()
        cm = re.match(r'^\\c\s+(\d+)', line)
        if cm:
            flush_chapter()
            chapter, verses[:] = int(cm.group(1)), []
            cur_num, cur_raw, cur_parts = None, None, []
            continue
        # A line may hold several verses: \v 1 text \v 2 text
        if '\\v ' in line:
            pieces = re.split(r'\\v\s+', line)
            head = pieces[0]
            if cur_num is not None and head.strip():
                cur_parts.append(head)
            for piece in pieces[1:]:
                vm = re.match(r'^([0-9]+[0-9a-zA-Z\-–]*)\s*(.*)$', piece, re.S)
                if not vm:
                    continue
                flush_verse()
                cur_raw = vm.group(1)
                cur_num = int(re.match(r'\d+', cur_raw).group(0))
                cur_parts = [vm.group(2)]
            continue
        # Any other line continues the verse in progress (paragraph breaks,
        # poetry lines). Headings and titles are not verse text.
        if re.match(r'^\\(id|ide|h|toc\d?|mt\d?|ms\d?|s\d?|sp|r|d|cl|cp|rem|sts|iot|io\d?|ip|imt\d?)\b', line):
            continue
        if cur_num is not None:
            cur_parts.append(line)

    flush_chapter()
    chapters.sort(key=lambda c: c['chapter'])
    return book, chapters, local


def convert_zip(zip_path: Path):
    """{book_id: {...}} for every canonical book in the archive."""
    out = {}
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if not name.lower().endswith(('.usfm', '.sfm')):
                continue
            try:
                raw = z.read(name).decode('utf-8-sig')
            except UnicodeDecodeError:
                raw = z.read(name).decode('utf-8', 'replace')
            book, chapters, local = parse_usfm(raw)
            if not book or book not in ORDER or not chapters:
                continue
            out[book] = {
                'book': book,
                'name': NAMES[book],
                'localName': local or NAMES[book],
                'order': ORDER[book],
                'chapters': chapters,
            }
    return out


if __name__ == '__main__':
    data = convert_zip(Path(sys.argv[1]))
    print(json.dumps({k: {'chapters': len(v['chapters']),
                          'verses': sum(len(c['verses']) for c in v['chapters'])}
                      for k in sorted(data, key=lambda b: ORDER[b])
                      for v in [data[k]]}, indent=1)[:1200])
