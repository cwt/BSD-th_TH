#!/usr/bin/env python3
"""
Generate and install th_TH.UTF-8 locale on BSD and macOS systems.

Fetches Thai locale data from Unicode CLDR (Unicode License),
generates a POSIX locale source file, then installs it:
  - BSD:   compiles with system localedef
  - macOS: generates Apple's compiled format directly
           (Apple's localedef crashes on Thai UTF-8)

LC_COLLATE is sourced from the ISO/IEC 14651 Common Template Table
(freely available from ISO's standards portal under ISO's license
for standard electronic inserts).

Usage:
    sudo python3 th_locale.py [options]

Options:
    --dry-run       Generate locale files but don't install
    --verify-only   Only verify existing installation
    --force         Force re-download and re-generate (ignore cache)
    --verbose       Enable verbose output
    --help          Show this help message
"""

import os
import sys
import json
import shutil
import subprocess
import urllib.request
import argparse
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

CLDR_BASE = "https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json"
ISO_CTT_URL = "https://standards.iso.org/iso-iec/14651/ed-6/en/ISO14651_2020_TABLE1_en.txt"
SRC_DIR = Path("/usr/share/locale")
MACOS_DST = Path("/usr/local/share/locale") / "th_TH.UTF-8"
CACHE_DIR = Path.home() / ".cache" / "th_locale"
CACHE_TTL_DAYS = 30

# -- Cache utilities

def cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


def cache_path(url):
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    ext = Path(url).suffix or ".txt"
    return cache_dir() / f"{h}{ext}"


def cache_meta_path(url):
    h = hashlib.sha256(url.encode()).hexdigest()[:16]
    return cache_dir() / f"{h}.meta"


def is_cache_valid(url, force=False):
    if force:
        return False
    meta = cache_meta_path(url)
    if not meta.exists():
        return False
    try:
        cached_time = datetime.fromisoformat(meta.read_text().strip())
        return datetime.now() - cached_time < timedelta(days=CACHE_TTL_DAYS)
    except Exception:
        return False


def save_to_cache(url, data, verbose=False):
    path = cache_path(url)
    meta = cache_meta_path(url)
    path.write_bytes(data) if isinstance(data, bytes) else path.write_text(data, encoding="utf-8")
    meta.write_text(datetime.now().isoformat())
    if verbose:
        print(f"  cached to {path}")


def load_from_cache(url, verbose=False):
    path = cache_path(url)
    if verbose:
        print(f"  using cache: {path}")
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_bytes()


# -- Thai locale data (factual, no single "owner")

TH_MONETARY = {
    "int_curr_symbol": "THB ",
    "currency_symbol": "\u0e3f",
    "mon_decimal_point": ".",
    "mon_thousands_sep": ",",
    "mon_grouping": 3,
    "positive_sign": "",
    "negative_sign": "-",
    "int_frac_digits": 2,
    "frac_digits": 2,
    "p_cs_precedes": 1,
    "p_sep_by_space": 2,
    "n_cs_precedes": 1,
    "n_sep_by_space": 2,
    "p_sign_posn": 4,
    "n_sign_posn": 4,
}

TH_NUMERIC = {
    "decimal_point": ".",
    "thousands_sep": ",",
    "grouping": 3,
}

TH_MESSAGES = {
    "yesexpr": "^[yY]",
    "noexpr": "^[nN]",
}


# -- CLDR fetch

def fetch_json(url, force=False, verbose=False):
    if is_cache_valid(url, force):
        return load_from_cache(url, verbose)
    if verbose:
        print(f"* fetching {url.split('/')[-1]} from CLDR...")
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = resp.read()
    text = data.decode("utf-8")
    save_to_cache(url, text, verbose)
    return json.loads(text)


def fetch_cldr(force=False, verbose=False):
    url = f"{CLDR_BASE}/cldr-dates-full/main/th/ca-gregorian.json"
    data = fetch_json(url, force, verbose)
    cal = data["main"]["th"]["dates"]["calendars"]["gregorian"]

    months = cal["months"]["format"]
    abmon = [months["abbreviated"][str(i)] for i in range(1, 13)]
    mon = [months["wide"][str(i)] for i in range(1, 13)]

    days = cal["days"]["format"]
    keys = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
    abday = [days["short"][k] for k in keys]
    day = [days["wide"][k] for k in keys]

    dp = cal["dayPeriods"]["format"]
    am_pm = ("AM", "PM")
    for style in ("abbreviated", "wide"):
        if style in dp and "am" in dp[style]:
            am_pm = (dp[style]["am"], dp[style]["pm"])
            break

    # Buddhist calendar uses same month/day names as Gregorian in Thailand
    # Buddhist era = Gregorian year + 543
    buddhist_abmon = abmon
    buddhist_mon = mon
    buddhist_abday = abday
    buddhist_day = day
    buddhist_am_pm = am_pm
    buddhist_era = "พ.ศ."

    return (abmon, mon, abday, day, am_pm,
            buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era)


# -- ISO 14651 Common Template Table (LC_COLLATE)

CTT_ACTIVATE = {
    "escape_char /",
    "comment_char %",
    "LC_COLLATE",
    "END LC_COLLATE",
}


def fetch_iso_ctt(force=False, verbose=False):
    if is_cache_valid(ISO_CTT_URL, force):
        if verbose:
            print("* using cached ISO 14651 Common Template Table")
        return load_from_cache(ISO_CTT_URL, verbose).decode("utf-8")
    if verbose:
        print(f"* fetching ISO 14651 Common Template Table...")
    with urllib.request.urlopen(ISO_CTT_URL, timeout=60) as resp:
        data = resp.read()
    text = data.decode("utf-8")
    if verbose:
        print(f"  downloaded {len(data) / 1024:.0f} KB")
    save_to_cache(ISO_CTT_URL, data, verbose)
    return text


def process_iso_ctt(text):
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("% ") and stripped[2:].rstrip() in CTT_ACTIVATE:
            out.append(stripped[2:])
        else:
            out.append(line)
    return "".join(out)


def save_iso_ctt(processed):
    path = Path("iso14651_t1.src")
    path.write_text(processed, encoding="utf-8")
    print(f"* saved {path}")
    return path


def compile_iso_ctt(verbose=False):
    src = Path("iso14651_t1.src")
    if not src.exists():
        print("  ERROR: iso14651_t1.src not found; run fetch first")
        sys.exit(1)
    if not shutil.which("localedef"):
        print("  WARNING: localedef not found, skipping iso14651_t1 compilation")
        return None

    # macOS localedef is ancient — no collating-element or range support.
    # Strip quarantine attr first (macOS blocks localedef on quarantined files).
    if sys.platform == "darwin":
        result = subprocess.run(["xattr", "-d", "com.apple.provenance", str(src)],
                                capture_output=True, text=True)
        if result.returncode != 0 and verbose:
            print(f"  xattr warning: {result.stderr.strip()}")

    outdir = Path("iso14651_t1")
    if outdir.exists():
        shutil.rmtree(outdir)
    cmd = ["localedef", "-u", "UTF-8", "-i", str(src), "iso14651_t1"]
    if verbose:
        print(f"* running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if sys.platform == "darwin":
            print("  NOTE: macOS localedef is too old for ISO 14651 CTT")
            print("  (missing collating-element / range-symbol support)")
        else:
            print(f"  WARNING: localedef for iso14651_t1 failed:\n  {result.stderr.strip()}")
        print("  LC_COLLATE will fall back to system default (en_US / C)")
        return None
    collate_file = outdir / "LC_COLLATE"
    if collate_file.exists():
        if verbose:
            print(f"  compiled LC_COLLATE ({collate_file.stat().st_size} bytes)")
        return collate_file
    return None


# -- POSIX locale source generation

def q(v):
    return f'"{v}"'


def qjoin(vals):
    return ";".join(q(v) for v in vals)


def posix_time(abmon, mon, abday, day, am_pm,
                buddhist_abmon=None, buddhist_mon=None, buddhist_abday=None, buddhist_day=None, buddhist_am_pm=None, buddhist_era=None):
    lines = [
        f"abday   {qjoin(abday)}",
        f"day     {qjoin(day)}",
        f"abmon   {qjoin(abmon)}",
        f"mon     {qjoin(mon)}",
        'd_t_fmt "%a %d %b %Y %H:%M:%S"',
        'd_fmt   "%d/%m/%Y"',
        't_fmt   "%H:%M:%S"',
        f"am_pm   {qjoin(list(am_pm))}",
    ]
    if buddhist_abmon:
        lines.extend([
            f"abmon_buddhist   {qjoin(buddhist_abmon)}",
            f"mon_buddhist     {qjoin(buddhist_mon)}",
            f"abday_buddhist   {qjoin(buddhist_abday)}",
            f"day_buddhist     {qjoin(buddhist_day)}",
            f"am_pm_buddhist   {qjoin(list(buddhist_am_pm))}",
            f"era_buddhist     \"{buddhist_era}\"",
        ])
    return "\n".join(lines)


def posix_monetary():
    lines = []
    for key, val in TH_MONETARY.items():
        if isinstance(val, int):
            lines.append(f"{key:23s}{val}")
        elif val == "":
            lines.append(f"{key:23s}\"\"")
        else:
            lines.append(f"{key:23s}{q(val)}")
    return "\n".join(lines)


def posix_numeric():
    lines = []
    for key, val in TH_NUMERIC.items():
        if isinstance(val, int):
            lines.append(f"{key:23s}{val}")
        else:
            lines.append(f"{key:23s}{q(val)}")
    return "\n".join(lines)


def posix_messages():
    return f'yesexpr "{TH_MESSAGES["yesexpr"]}"\n' \
           f'noexpr  "{TH_MESSAGES["noexpr"]}"'


def gen_posix_source(abmon, mon, abday, day, am_pm,
                     buddhist_abmon=None, buddhist_mon=None, buddhist_abday=None, buddhist_day=None, buddhist_am_pm=None, buddhist_era=None):
    return f"""comment_char %
escape_char /

LC_MONETARY
{posix_monetary()}
END LC_MONETARY

LC_NUMERIC
{posix_numeric()}
END LC_NUMERIC

LC_TIME
{posix_time(abmon, mon, abday, day, am_pm,
            buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era)}
END LC_TIME

LC_MESSAGES
{posix_messages()}
END LC_MESSAGES

LC_COLLATE
copy "iso14651_t1"
END LC_COLLATE
"""


# -- Thai collation data for Apple DARWIN 1.0 LC_COLLATE

import struct

# Thai consonants in Unicode encoding (= dictionary order)
THAI_CONSONANTS = list(range(0x0E01, 0x0E2F))  # U+0E01..U+0E2E

# Thai leading vowels (visual order: before consonant, sort: after consonant)
THAI_LEADING_VOWELS = [0x0E40, 0x0E41, 0x0E42, 0x0E43, 0x0E44]

# Thai dependent vowel signs (placed after consonant in sort)
THAI_VOWEL_SIGNS = [0x0E30, 0x0E31, 0x0E32, 0x0E33, 0x0E34, 0x0E35,
                    0x0E36, 0x0E37, 0x0E38, 0x0E39, 0x0E3A, 0x0E45]

# Thai tone marks and other signs
THAI_SIGNS = [0x0E47, 0x0E48, 0x0E49, 0x0E4A, 0x0E4B, 0x0E4C, 0x0E4D, 0x0E4E]

# Thai punctuation
THAI_PUNCT = [0x0E2F, 0x0E46, 0x0E4F, 0x0E3F]

# Thai digits
THAI_DIGITS = list(range(0x0E50, 0x0E5A))  # U+0E50..U+0E59

PRIMARY_BASE = 500


def gen_macos_collate():
    ref_path = SRC_DIR / "en_US.UTF-8" / "LC_COLLATE"
    with open(ref_path, "rb") as f:
        ref = f.read()

    off = 0
    magic = ref[:12]
    off += 12
    xloc_ver = ref[off:off + 12]
    off += 12

    # Parse header to extract subst table data
    di = struct.unpack_from('<B', ref, off)[0];
    dirs = list(struct.unpack_from('<10B', ref, off + 1))
    chmax = ref[off + 11]
    pri_count = list(struct.unpack_from('<10i', ref, off + 12))
    # Skip flags, chain_count, large_count
    off += 144

    char_table_data = ref[off:off + 256 * 40]
    off += 256 * 40

    # Copy subst tables from en_US (same ASCII/Latin-1 handling)
    subst_tables_data = b""
    ref_sub_counts = list(struct.unpack_from('<10i', ref, 24 + 1 + 10 + 1 + 40 + 4 + 4 + 4))
    for z in range(4):
        sc = ref_sub_counts[z]
        if sc > 0:
            subst_tables_data += ref[off:off + sc * (4 + 24 * 4)]
            off += sc * (4 + 24 * 4)

    # Build large table: Thai characters + Latin supplement from en_US
    ref_large_count = list(struct.unpack_from('<10i', ref, 24 + 1 + 10 + 1 + 40 + 4 + 4))[0]
    ref_chain_count = list(struct.unpack_from('<10i', ref, 24 + 1 + 10 + 1 + 40 + 4))[0]

    ref_large_off = 168 + 256 * 40  # char table end
    for z in range(4):
        sc = ref_sub_counts[z]
        if sc > 0:
            ref_large_off += sc * (4 + 24 * 4)
    if ref_chain_count > 0:
        ref_large_off += ref_chain_count * (24 * 4 + 10 * 4)

    # Build large entries: first include Latin supplement from en_US
    latin_entries = []
    for i in range(ref_large_count):
        ent_off = ref_large_off + i * 44
        cp = struct.unpack_from('<i', ref, ent_off)[0]
        pri = list(struct.unpack_from('<10i', ref, ent_off + 4))
        latin_entries.append((cp, pri))

    # Build Thai large entries
    thai_prim = PRIMARY_BASE
    thai_entries = []

    # Consonants: primary weight = sequence number
    for i, cp in enumerate(THAI_CONSONANTS):
        pri = [thai_prim, 1, 1, cp, 0, 0, 0, 0, 0, 0]
        thai_entries.append((cp, pri))
        thai_prim += 3

    # Vowel signs
    for cp in THAI_VOWEL_SIGNS:
        pri = [thai_prim, 1, 1, cp, 0, 0, 0, 0, 0, 0]
        thai_entries.append((cp, pri))
        thai_prim += 1

    # Tone marks and signs
    for cp in THAI_SIGNS:
        pri = [thai_prim, 1, 1, cp, 0, 0, 0, 0, 0, 0]
        thai_entries.append((cp, pri))
        thai_prim += 1

    # Punctuation
    for cp in THAI_PUNCT:
        pri = [thai_prim, 1, 1, cp, 0, 0, 0, 0, 0, 0]
        thai_entries.append((cp, pri))
        thai_prim += 1

    # Digits
    for cp in THAI_DIGITS:
        pri = [thai_prim, 1, 1, cp, 0, 0, 0, 0, 0, 0]
        thai_entries.append((cp, pri))
        thai_prim += 1

    # Combine and sort by code point (required for binary search)
    all_large = sorted(latin_entries + thai_entries, key=lambda x: x[0])

    # Build chain table for leading vowel reordering (sorted by str for binary search)
    chain_entries = []
    idx = 0
    for vowel in THAI_LEADING_VOWELS:
        for i, cons in enumerate(THAI_CONSONANTS):
            cons_prim = PRIMARY_BASE + i * 3
            wstr = [vowel, cons] + [0] * 22
            pri = [cons_prim, 1, 1, 0xE000 + idx, 0, 0, 0, 0, 0, 0]
            chain_entries.append((wstr, pri))
            idx += 1
    # Sort lexicographically by wchar_t string (required for bsearch)
    chain_entries.sort(key=lambda e: tuple(e[0]))

    # Build header
    new_large_count = len(all_large)
    new_chain_count = len(chain_entries)
    new_chain_max_len = 2 if new_chain_count > 0 else 0

    hdr = bytearray()
    hdr.append(di)
    hdr.extend(dirs)
    hdr.append(new_chain_max_len)
    hdr.extend(struct.pack('<10i', *pri_count))
    hdr.extend(struct.pack('<i', 0))  # flags
    hdr.extend(struct.pack('<i', new_chain_count))
    hdr.extend(struct.pack('<i', new_large_count))

    sub_counts = ref_sub_counts[:10]
    hdr.extend(struct.pack('<10i', *sub_counts))
    hdr.extend(struct.pack('<10i', *[0] * 10))  # undef_pri

    # Build file
    buf = bytearray()
    buf.extend(magic)
    buf.extend(xloc_ver)
    buf.extend(hdr)
    buf.extend(char_table_data)
    buf.extend(subst_tables_data)

    # Chain table
    for wstr, pri in chain_entries:
        buf.extend(struct.pack('<24i', *wstr))
        buf.extend(struct.pack('<10i', *pri))

    # Large table
    for cp, pri in all_large:
        buf.extend(struct.pack('<i', cp))
        buf.extend(struct.pack('<10i', *pri))

    return bytes(buf)


# -- Apple compiled format (macOS)

def apple_monetary():
    fields = [
        TH_MONETARY["int_curr_symbol"],
        TH_MONETARY["currency_symbol"],
        TH_MONETARY["mon_decimal_point"],
        TH_MONETARY["mon_thousands_sep"],
        str(TH_MONETARY["mon_grouping"]),
        "",
        TH_MONETARY["negative_sign"],
        str(TH_MONETARY["int_frac_digits"]),
        str(TH_MONETARY["frac_digits"]),
        str(TH_MONETARY["p_cs_precedes"]),
        str(TH_MONETARY["p_sep_by_space"]),
        str(TH_MONETARY["n_cs_precedes"]),
        str(TH_MONETARY["n_sep_by_space"]),
        str(TH_MONETARY["p_sign_posn"]),
        str(TH_MONETARY["n_sign_posn"]),
    ]
    return "\n".join(fields) + "\n"


def apple_numeric():
    return "\n".join([
        TH_NUMERIC["decimal_point"],
        TH_NUMERIC["thousands_sep"],
        str(TH_NUMERIC["grouping"]),
    ]) + "\n"


def apple_time(abmon, mon, abday, day, am_pm,
               buddhist_abmon=None, buddhist_mon=None, buddhist_abday=None, buddhist_day=None, buddhist_am_pm=None, buddhist_era=None):
    parts = []
    parts.extend(abmon)
    parts.extend(mon)
    parts.extend(abday)
    parts.extend(day)
    parts.append("%H:%M:%S")
    parts.append("%d/%m/%Y")
    parts.append("%a %d %b %Y %H:%M:%S")
    parts.append(am_pm[0])
    parts.append(am_pm[1])
    parts.append("%a %d %b %Y %H:%M:%S %Z")
    parts.extend(mon)
    parts.append("md")
    parts.append("%I:%M:%S %p")
    if buddhist_abmon:
        parts.extend(buddhist_abmon)
        parts.extend(buddhist_mon)
        parts.extend(buddhist_abday)
        parts.extend(buddhist_day)
        parts.append(buddhist_am_pm[0])
        parts.append(buddhist_am_pm[1])
        parts.append(buddhist_era)
    return "\n".join(parts) + "\n"


def apple_messages():
    return (f'{TH_MESSAGES["yesexpr"]}\n'
            f'{TH_MESSAGES["noexpr"]}\n'
            f"yes:y:YES:Y\nno:n:NO:N\n")


def gen_macos_compiled(abmon, mon, abday, day, am_pm,
                       buddhist_abmon=None, buddhist_mon=None, buddhist_abday=None, buddhist_day=None, buddhist_am_pm=None, buddhist_era=None):
    return {
        "LC_MONETARY": apple_monetary(),
        "LC_NUMERIC": apple_numeric(),
        "LC_TIME": apple_time(abmon, mon, abday, day, am_pm,
                              buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era),
        "LC_MESSAGES/LC_MESSAGES": apple_messages(),
    }


# -- Installers

def install_macos(compiled, verbose=False):
    if MACOS_DST.exists():
        if verbose:
            print(f"  removing existing {MACOS_DST}")
        subprocess.run(["sudo", "rm", "-rf", str(MACOS_DST)], capture_output=True, check=True)

    if verbose:
        print(f"  creating {MACOS_DST}/LC_MESSAGES")
    subprocess.run(["sudo", "mkdir", "-p", str(MACOS_DST / "LC_MESSAGES")], capture_output=True, check=True)
    subprocess.run(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(MACOS_DST)],
                   capture_output=True)

    for name, data in compiled.items():
        (MACOS_DST / name).write_text(data, encoding="utf-8")
        if verbose:
            print(f"  wrote {name}")

    collate_bin = gen_macos_collate()
    (MACOS_DST / "LC_COLLATE").write_bytes(collate_bin)
    collate_size = len(collate_bin)
    if verbose:
        print(f"  generated LC_COLLATE ({collate_size} bytes)")

    ctype = SRC_DIR / "C.UTF-8" / "LC_CTYPE"
    (MACOS_DST / "LC_CTYPE").symlink_to(os.fsdecode(ctype))

    print(f"  installed to {MACOS_DST}")


def install_bsd(src_path, ctt_collate, verbose=False):
    if not shutil.which("localedef"):
        print("  ERROR: localedef not found on this system")
        print(f"  POSIX source saved to {src_path}")
        print("  Install locale manually: localedef -u UTF-8 -i th_TH.src th_TH.UTF-8")
        sys.exit(1)

    cmd = ["localedef", "-u", "UTF-8", "-i", str(src_path), "th_TH.UTF-8"]
    if verbose:
        print(f"* running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: localedef failed:\n  {result.stderr.strip()}")
        sys.exit(1)
    if verbose:
        print("  done")


def verify(ctt_ok, verbose=False):
    env = {**os.environ, "LC_ALL": "th_TH.UTF-8"}
    code = """
import locale
locale.setlocale(locale.LC_ALL, 'th_TH.UTF-8')
print('MON_1:  ', locale.nl_langinfo(locale.MON_1))
print('DAY_1:  ', locale.nl_langinfo(locale.DAY_1))
print('ABMON_1:', locale.nl_langinfo(locale.ABMON_1))
print('CRNCY:  ', locale.nl_langinfo(locale.CRNCYSTR))
"""
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, env=env)
    if proc.returncode == 0:
        if verbose:
            print(proc.stdout, end="")
        if ctt_ok:
            print("  LC_COLLATE: ISO 14651 (proper Thai collation)  ✅")
        else:
            print("  LC_COLLATE: system default (basic Unicode order)  ⚠️")
        return True
    if verbose:
        print("verify failed:", proc.stderr.strip())
    else:
        print("  Verification failed (use --verbose for details)")
    return False


def save_source(posix_source):
    path = Path("th_TH.src")
    path.write_text(posix_source, encoding="utf-8")
    print(f"* saved {path}")
    return path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate and install th_TH.UTF-8 locale on BSD and macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python3 th_locale.py              # Install locale
  sudo python3 th_locale.py --dry-run    # Generate files only
  python3 th_locale.py --verify-only     # Verify existing install
  sudo python3 th_locale.py --force      # Force re-download
  python3 th_locale.py --help            # Show this help
"""
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Generate locale files but don't install")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only verify existing installation")
    parser.add_argument("--force", action="store_true",
                        help="Force re-download and re-generate (ignore cache)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    return parser.parse_args()


def verify_only(verbose=False):
    print("== Verifying th_TH.UTF-8 locale ==\n")
    env = {**os.environ, "LC_ALL": "th_TH.UTF-8"}
    code = """
import locale
locale.setlocale(locale.LC_ALL, 'th_TH.UTF-8')
print('MON_1:  ', locale.nl_langinfo(locale.MON_1))
print('DAY_1:  ', locale.nl_langinfo(locale.DAY_1))
print('ABMON_1:', locale.nl_langinfo(locale.ABMON_1))
print('CRNCY:  ', locale.nl_langinfo(locale.CRNCYSTR))
"""
    proc = subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, env=env)
    if proc.returncode == 0:
        print(proc.stdout, end="")
        print("  Locale verified successfully  ✅")
        return True
    print("  Verification failed:", proc.stderr.strip())
    return False


def main():
    args = parse_args()
    verbose = args.verbose

    if args.verify_only:
        if verify_only(verbose):
            print("OK")
        else:
            sys.exit(1)
        return

    print("== th_TH.UTF-8 locale generator ==\n")

    cldr_data = fetch_cldr(args.force, verbose)
    abmon, mon, abday, day, am_pm = cldr_data[:5]
    buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era = cldr_data[5:]

    platform = sys.platform
    print(f"* platform: {platform}")

    if platform == "darwin":
        compiled = gen_macos_compiled(abmon, mon, abday, day, am_pm,
                                      buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era)
        if not args.dry_run:
            install_macos(compiled, verbose)
        ctt_ok = True
    else:
        print()
        raw_ctt = fetch_iso_ctt(args.force, verbose)
        processed_ctt = process_iso_ctt(raw_ctt)
        save_iso_ctt(processed_ctt)
        ctt_collate = compile_iso_ctt(verbose)

        posix_source = gen_posix_source(abmon, mon, abday, day, am_pm,
                                        buddhist_abmon, buddhist_mon, buddhist_abday, buddhist_day, buddhist_am_pm, buddhist_era)
        src_path = save_source(posix_source)
        if not args.dry_run:
            install_bsd(src_path, ctt_collate, verbose)
        ctt_ok = ctt_collate is not None

    print()
    if not args.dry_run:
        if verify(ctt_ok, verbose):
            print("OK. Usage: export LC_ALL=th_TH.UTF-8")
        else:
            sys.exit(1)
    else:
        print("Dry run complete. Files generated but not installed.")


if __name__ == "__main__":
    main()
