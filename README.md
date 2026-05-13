th_TH.UTF-8 locale for BSD and macOS
======================================

Generate and install the `th_TH.UTF-8` locale on systems where it's not
available out of the box (macOS, FreeBSD, NetBSD, OpenBSD, DragonFly BSD).

Locale data comes from the [Unicode CLDR][] (Unicode License) — month names,
day names, AM/PM strings. Monetary and numeric formatting values are standard
for the Thai locale (factual data).

[Unicode CLDR]: https://github.com/unicode-org/cldr


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
locale source contains actual Thai UTF-8 characters. This script works
around that bug by generating Apple's compiled locale format directly
(simple text files — reverse-engineered from the system's existing locale
data under `/usr/share/locale/`).

Installation goes to `/usr/local/share/locale/` (writable with `sudo`,
not SIP-protected). macOS libc scans this directory at runtime, so no
`LOCPATH` hacks needed.

### BSD notes

All four BSDs ship `localedef` in the base system. The script generates a
standard POSIX locale source file (`th_TH.src`) and compiles it with:

    localedef -u UTF-8 -i th_TH.src th_TH.UTF-8

Run with `sudo` or `doas` to install system-wide into `/usr/share/locale/`.


Requirements
------------

- Python 3.8+
- Internet connection (fetches CLDR JSON on first run)
- `sudo` access for installation


Usage
-----

    sudo python3 th_locale.py

This will:

1. Fetch Thai locale data from Unicode CLDR
2. Save a POSIX locale definition as `th_TH.src`
3. Install the locale (platform-specific method)
4. Verify it works

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

| File           | Description                           |
|----------------|---------------------------------------|
| `th_locale.py` | The installer script                  |
| `th_TH.src`    | POSIX locale source (for inspection / BSD localedef) |


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
