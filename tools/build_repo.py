#!/usr/bin/env python3
"""
Build the repository from the downloaded USFM archives.

Layout, chosen so the files are usable directly over HTTP without a server:

    catalog.json                        every translation, with licence
    translations/<id>/meta.json         one translation's details and counts
    translations/<id>/books/01-GEN.json one book, numbered in canonical order

A book per file rather than a Bible per file: a whole translation is 4–5 MB,
which is a slow fetch for someone who wants one chapter, an unreadable diff,
and a file GitHub will not render. Numbering the filenames by canonical order
means a directory listing sorts the way a Bible does rather than alphabetically,
where Genesis would fall between Galatians and Habakkuk.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from usfm2json import convert_zip, ORDER, NAMES  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / 'repo'
ZIPS = HERE / 'zips'


def main():
    picks = json.loads((HERE / 'picks.json').read_text())
    rows = {r['translationId']: r
            for r in csv.DictReader(open(HERE / 'cat.csv', encoding='utf-8-sig'))}

    (OUT / 'translations').mkdir(parents=True, exist_ok=True)
    catalog, total_bytes = [], 0

    for tid in picks:
        zip_path = ZIPS / f'{tid}_usfm.zip'
        if not zip_path.exists():
            print(f'  {tid:16} SKIPPED (no archive)')
            continue
        meta_row = rows.get(tid, {})
        data = convert_zip(zip_path)
        if not data:
            print(f'  {tid:16} SKIPPED (nothing parsed)')
            continue

        tdir = OUT / 'translations' / tid
        (tdir / 'books').mkdir(parents=True, exist_ok=True)

        books, chapters, verses, size = [], 0, 0, 0
        for code in sorted(data, key=lambda b: ORDER[b]):
            b = data[code]
            fname = f'{ORDER[code]:02d}-{code}.json'
            payload = {
                'translation': tid,
                'book': code,
                'name': b['name'],
                'order': b['order'],
                'chapters': b['chapters'],
            }
            text = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
            (tdir / 'books' / fname).write_text(text, encoding='utf-8')
            size += len(text.encode('utf-8'))
            nch = len(b['chapters'])
            nv = sum(len(c['verses']) for c in b['chapters'])
            chapters += nch
            verses += nv
            books.append({'book': code, 'name': b['name'], 'order': b['order'],
                          'chapters': nch, 'verses': nv, 'file': f'books/{fname}'})

        meta = {
            'id': tid,
            'title': meta_row.get('title', '').strip(),
            'shortTitle': (meta_row.get('shortTitle') or '').strip(),
            'language': meta_row.get('languageNameInEnglish', '').strip(),
            'languageNative': meta_row.get('languageName', '').strip(),
            'languageCode': meta_row.get('languageCode', '').strip(),
            'textDirection': (meta_row.get('textDirection') or 'ltr').strip() or 'ltr',
            # Carried verbatim from the publisher. Several of these texts are
            # copyrighted but redistributable; flattening them all into one
            # repo-wide claim would misstate their terms.
            'copyright': (meta_row.get('Copyright') or '').strip(),
            'redistributable': (meta_row.get('Redistributable') or '').strip().lower() == 'true',
            'source': f'https://ebible.org/Scriptures/{tid}_usfm.zip',
            'sourcePage': (meta_row.get('publicationURL') or f'https://ebible.org/details.php?id={tid}').strip(),
            'counts': {'books': len(books), 'chapters': chapters, 'verses': verses},
            'books': books,
        }
        (tdir / 'meta.json').write_text(
            json.dumps(meta, ensure_ascii=False, indent=1), encoding='utf-8')

        total_bytes += size
        catalog.append({k: meta[k] for k in
                        ('id', 'title', 'language', 'languageNative', 'languageCode',
                         'textDirection', 'copyright', 'redistributable', 'source', 'counts')}
                       | {'path': f'translations/{tid}'})
        print(f'  {tid:16} {meta["language"][:12]:13} '
              f'{len(books):2} books  {chapters:5} ch  {verses:6} v  {size/1048576:5.1f} MB')

    catalog.sort(key=lambda c: (c['language'], c['id']))
    (OUT / 'catalog.json').write_text(json.dumps({
        'name': 'Open Bibles',
        'description': 'Public-domain and freely redistributable Bible translations as JSON.',
        'source': 'https://ebible.org/',
        'translations': catalog,
        'counts': {
            'translations': len(catalog),
            'languages': len({c['language'] for c in catalog}),
            'verses': sum(c['counts']['verses'] for c in catalog),
        },
    }, ensure_ascii=False, indent=1), encoding='utf-8')

    print(f'\n{len(catalog)} translations, '
          f'{len({c["language"] for c in catalog})} languages, '
          f'{sum(c["counts"]["verses"] for c in catalog):,} verses, '
          f'{total_bytes/1048576:.0f} MB')


if __name__ == '__main__':
    main()
