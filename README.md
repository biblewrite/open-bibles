# Open Bibles

**36 Bible translations in 32 languages, as clean JSON.** 1,119,230 verses. No API key, no rate limit, no build step — just files you can fetch.

Every translation here is either public domain or marked redistributable by its publisher. Each one carries its own copyright notice; none of them are relicensed by this repository.

```
https://biblewrite.github.io/open-bibles/translations/eng-kjv2006/books/43-JHN.json
```

That URL is served with `Access-Control-Allow-Origin: *`, so you can fetch it straight from a browser.

There is also a reader at **[biblewrite.github.io/open-bibles](https://biblewrite.github.io/open-bibles/)** — two translations side by side, light / sepia / dark, adjustable type, search, and click-to-copy with the reference. No account, no tracking, nothing stored but your own settings.

---

## Using it

**One book**

```js
const res  = await fetch('https://biblewrite.github.io/open-bibles/translations/eng-kjv2006/books/43-JHN.json');
const john = await res.json();

const ch3  = john.chapters.find(c => c.chapter === 3);
const v16  = ch3.verses.find(v => v.verse === 16);
console.log(v16.text);
// For God so loved the world, that he gave his only begotten Son, …
```

**What translations exist**

```js
const catalog = await (await fetch('https://biblewrite.github.io/open-bibles/catalog.json')).json();
catalog.translations.filter(t => t.language === 'Telugu');
```

**One translation's details** — book list, verse counts, licence:

```
translations/<id>/meta.json
```

---

## Layout

```
catalog.json                        every translation, with licence and counts
translations/
  eng-kjv2006/
    meta.json                       title, language, copyright, per-book counts
    books/
      01-GEN.json
      43-JHN.json
      66-REV.json
tools/
  usfm2json.py                      how the JSON was produced, from USFM
  build_repo.py                     how this repository was assembled
```

Filenames are numbered by canonical order, so a directory listing sorts the way a Bible does. Alphabetically, Genesis would fall between Galatians and Habakkuk.

One file per book rather than one per translation. A whole Bible is 4–12 MB — a slow fetch for someone who wants one chapter, an unreadable diff, and too large for GitHub to render.

## Shape of a book file

```json
{
  "translation": "eng-kjv2006",
  "book": "JHN",
  "name": "John",
  "order": 43,
  "chapters": [
    { "chapter": 1, "verses": [ { "verse": 1, "text": "In the beginning was the Word…" } ] }
  ]
}
```

A verse carries `ref` as well when the source numbered it as a range or segment — `"ref": "1-2"`, `"ref": "3a"` — so nothing is lost to the integer.

---

## Licensing — read this before redistributing

**This repository does not relicense anything.** The tooling in `tools/` is MIT. The scripture texts are not ours to license, and their terms differ:

- **17 translations are public domain** — KJV, WEB, BSB, ASV, Louis Segond 1910, Riveduta 1927, the Russian Synodal text, the Chinese Union Version, Van Dyck Arabic, and others. Use them for anything.
- **The remaining 19 are copyrighted but published as redistributable** by their copyright holders, most of them Bridge Connectivity Solutions (the Indian Revised Version family) and Door43. Redistribution is permitted; relicensing is not.

Each translation's exact notice is in its `meta.json` under `copyright`, carried verbatim from the publisher. Flattening them all into a single repo-wide claim would misstate someone's terms, so this repo deliberately does not.

If you ship a translation in a product, reproduce its notice.

## Where it came from

[eBible.org](https://ebible.org/), which publishes these texts as USFM with per-translation licensing metadata. `catalog.json` records the source archive URL for every translation, so any file here can be traced back and rebuilt.

Sourced from the publisher rather than a third-party mirror on purpose: a repository README calling something "non-copyrighted" is not a grant from the rights holder, and several popular Bible-data repos list copyrighted translations under exactly that heading.

## Known gaps

Three translations are missing a chapter **in the publisher's own source text**. Verified against the original USFM; not an artefact of this conversion, and recorded in each `meta.json` under `knownGaps`:

| Translation | Language | Missing |
|---|---|---|
| `ron1924` | Romanian | John 11 |
| `kor` | Korean | 1 Peter 5 |
| `deuelbbk` | German | Malachi 4 — merged into chapter 3, as German Bibles traditionally do |

Verse totals vary between translations (30,991–31,170) because versification genuinely differs between traditions. That is not an error.

## Rebuilding

```
python3 tools/build_repo.py
```

Downloads the USFM archives from eBible, converts, and writes this tree. The converter strips footnotes and cross-references whole — leaving the markers but keeping their content would splice editorial apparatus into the middle of a verse — and unwraps word-level markup so `\w word|strong="H1234"\w*` becomes `word`.

Validated against the KJV: 66 books, 1,189 chapters, **31,102 verses** — the published figure, matched exactly.
