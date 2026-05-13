th_TH.UTF-8 locale for BSD and macOS
======================================

Generate and install the `th_TH.UTF-8` locale on systems where it's not
available out of the box (macOS, FreeBSD, NetBSD, OpenBSD, DragonFly BSD).

Locale data comes from the [Unicode CLDR][] (Unicode License) — month names,
day names, AM/PM strings. Monetary and numeric formatting values are standard
for the Thai locale (factual data).

Collation (LC_COLLATE) comes from the ISO/IEC 14651 Common Template Table
(freely available from ISO's portal — BSD-native format via `localedef`,
macOS via direct Python generation of Apple's DARWIN 1.0 binary format).

[Unicode CLDR]: https://github.com/unicode-org/cldr
[ISO 14651]: https://standards.iso.org/iso-iec/14651/


Platform support
----------------

| System      | Install method                        | Path                         |
|-------------|---------------------------------------|------------------------------|
| macOS       | Generate Apple compiled format direct | `/usr/local/share/locale/`   |
| FreeBSD     | `localedef` from base system          | `/usr/share/locale/`         |
| NetBSD      | `localedef` from base system          | `/usr/share/locale/`         |
| OpenBSD     | `localedef` from base system          | `/usr/share/locale/`         |
| DragonFly   | `localedef` from base system          | `/usr/share/locale/`         |

### macOS notes

Apple ships `/usr/bin/localedef` but it **crashes (SIGKILL)** when the
locale source contains actual Thai UTF-8 characters, and its parser is
too old for modern POSIX LC_COLLATE features (no `collating-element` or
`collating-symbol` range support). This script works around both bugs:

- Text categories (LC_TIME, LC_MONETARY, etc.) are generated as simple
  text files, reverse-engineered from the system's existing locale data
  under `/usr/share/locale/`.
- LC_COLLATE is generated as Apple's native "DARWIN 1.0" binary format
  directly — no dependency on `localedef`. Includes the full ISO 14651
  Common Template Table plus Thai leading-vowel chain reordering.

Installation goes to `/usr/local/share/locale/` (writable with `sudo`,
not SIP-protected). macOS libc scans this directory at runtime, so no
`LOCPATH` hacks needed.

### BSD notes

All four BSDs ship `localedef` in the base system (Illumos-derived,
supporting full POSIX LC_COLLATE syntax including `collating-element`
and collating-symbol ranges). The script:

1. Downloads the ISO/IEC 14651 Common Template Table from ISO's portal
   and saves it as `iso14651_t1.src`
2. Compiles it: `localedef -u UTF-8 -i iso14651_t1.src iso14651_t1`
3. Generates `th_TH.src` with `copy "iso14651_t1"` in LC_COLLATE
4. Compiles the Thai locale: `localedef -u UTF-8 -i th_TH.src th_TH.UTF-8`

Run with `sudo` or `doas` to install system-wide into `/usr/share/locale/`.


Requirements
------------

- Python 3.8+
- Internet connection (fetches CLDR JSON and ISO 14651 CTT on first run)
- `sudo` access for installation


Usage
-----

    sudo python3 th_locale.py

This will:

1. Fetch Thai locale data from Unicode CLDR
2. Fetch the ISO/IEC 14651 Common Template Table for collation
3. Save a POSIX locale definition as `th_TH.src` (and `iso14651_t1.src`)
4. Install the locale (platform-specific method)
5. Verify it works

After installation, set the locale in your shell:

    export LC_ALL=th_TH.UTF-8

Or for just one command:

    LC_ALL=th_TH.UTF-8 cal
    LC_ALL=th_TH.UTF-8 date

Verify from Python:

    python3 -c "
    import locale
    locale.setlocale(locale.LC_ALL, 'th_TH.UTF-8')
    print(locale.nl_langinfo(locale.MON_1))  # มกราคม
    "


Generated files
---------------

| File               | Description                                           |
|--------------------|-------------------------------------------------------|
| `th_locale.py`     | The installer script                                  |
| `th_TH.src`        | POSIX locale source (for inspection / BSD localedef)  |
| `iso14651_t1.src`  | ISO/IEC 14651 Common Template Table (BSD LC_COLLATE)  |


How it works
------------

The Thai GLibc locale source (`th_TH` from `bminor/glibc`) is GPL-licensed.
This project avoids GPL code entirely by sourcing all locale data from the
Unicode CLDR (Unicode License), and the format/structuring code in
`th_locale.py` is original.

Month names, day names, and AM/PM strings are parsed from
[CLDR JSON](https://github.com/unicode-org/cldr-json).

Monetary values (currency symbol, grouping rules, sign position) and numeric
formatting (decimal/group separators) are standard factual data for the Thai
locale, included directly in the script.

### LC_COLLATE

The ISO/IEC 14651 Common Template Table (CTT) defines Unicode collation
weights for all characters following the Unicode Collation Algorithm.
It already includes:

- Thai consonants in correct dictionary order (Unicode encodes them in
  the Royal Institute order: ก, ข, ฃ, ค, ฅ, ... ฮ)
- `collating-element` declarations for leading-vowel reordering
  (e.g., เ + ก sorts at ก's position, not after ฮ)

On **BSD**, the CTT is compiled via `localedef` and referenced from
`th_TH.src` with `copy "iso14651_t1"`.

On **macOS**, the script generates Apple's DARWIN 1.0 binary format
directly in Python:
- Latin‑1 char table and substitution tables copied from en_US
- 230 chain-table entries for leading-vowel + consonant pairs
- 80 large-table entries for Thai consonants, vowels, tone marks,
  punctuation, and digits
- All tables sorted for binary search (matching libc's expectations)
