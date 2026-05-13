#!/usr/bin/env python3
"""
Generate and install th_TH.UTF-8 locale on BSD and macOS systems.

Fetches Thai locale data from Unicode CLDR (Unicode License),
generates a POSIX locale source file, then installs it:
  - BSD:   compiles with system localedef
  - macOS: generates Apple's compiled format directly
           (Apple's localedef crashes on Thai UTF-8)

Usage:
    sudo python3 th_locale.py
    export LC_ALL=th_TH.UTF-8
    cal
"""

import os
import sys
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

CLDR_BASE = "https://raw.githubusercontent.com/unicode-org/cldr-json/main/cldr-json"
SRC_DIR = Path("/usr/share/locale")
MACOS_DST = Path("/usr/local/share/locale") / "th_TH.UTF-8"

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

def fetch_json(url):
    print(f"* fetching {url.split('/')[-1]} from CLDR...")
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_cldr():
    url = f"{CLDR_BASE}/cldr-dates-full/main/th/ca-gregorian.json"
    data = fetch_json(url)
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
    for style in ("wide", "abbreviated"):
        if style in dp and "am" in dp[style]:
            am_pm = (dp[style]["am"], dp[style]["pm"])
            break

    return abmon, mon, abday, day, am_pm


# -- POSIX locale source generation

def q(v):
    return f'"{v}"'


def qjoin(vals):
    return ";".join(q(v) for v in vals)


def posix_time(abmon, mon, abday, day, am_pm):
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


def gen_posix_source(abmon, mon, abday, day, am_pm):
    return f"""comment_char %
escape_char /

LC_MONETARY
{posix_monetary()}
END LC_MONETARY

LC_NUMERIC
{posix_numeric()}
END LC_NUMERIC

LC_TIME
{posix_time(abmon, mon, abday, day, am_pm)}
END LC_TIME

LC_MESSAGES
{posix_messages()}
END LC_MESSAGES
"""


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


def apple_time(abmon, mon, abday, day, am_pm):
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
    return "\n".join(parts) + "\n"


def apple_messages():
    return (f'{TH_MESSAGES["yesexpr"]}\n'
            f'{TH_MESSAGES["noexpr"]}\n'
            f"yes:y:YES:Y\nno:n:NO:N\n")


def gen_macos_compiled(abmon, mon, abday, day, am_pm):
    return {
        "LC_MONETARY": apple_monetary(),
        "LC_NUMERIC": apple_numeric(),
        "LC_TIME": apple_time(abmon, mon, abday, day, am_pm),
        "LC_MESSAGES/LC_MESSAGES": apple_messages(),
    }


# -- Installers

def install_macos(compiled):
    if MACOS_DST.exists():
        subprocess.run(["sudo", "rm", "-rf", str(MACOS_DST)], capture_output=True, check=True)

    subprocess.run(["sudo", "mkdir", "-p", str(MACOS_DST / "LC_MESSAGES")], capture_output=True, check=True)
    subprocess.run(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", str(MACOS_DST)],
                   capture_output=True)

    for name, data in compiled.items():
        (MACOS_DST / name).write_text(data, encoding="utf-8")

    for f in ("LC_COLLATE",):
        src = SRC_DIR / "en_US.UTF-8" / f
        (MACOS_DST / f).write_bytes(src.read_bytes())

    ctype = SRC_DIR / "C.UTF-8" / "LC_CTYPE"
    (MACOS_DST / "LC_CTYPE").symlink_to(os.fsdecode(ctype))

    print(f"  installed to {MACOS_DST}")


def install_bsd(src_path):
    if not shutil.which("localedef"):
        print("  ERROR: localedef not found on this system")
        print(f"  POSIX source saved to {src_path}")
        print("  Install locale manually: localedef -u UTF-8 -i th_TH.src th_TH.UTF-8")
        sys.exit(1)

    cmd = ["localedef", "-u", "UTF-8", "-i", str(src_path), "th_TH.UTF-8"]
    print(f"* running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: localedef failed:\n  {result.stderr.strip()}")
        sys.exit(1)
    print("  done")


def verify():
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
        return True
    print("verify failed:", proc.stderr)
    return False


def save_source(posix_source):
    path = Path("th_TH.src")
    path.write_text(posix_source, encoding="utf-8")
    print(f"* saved {path}")
    return path


def main():
    print("== th_TH.UTF-8 locale generator ==\n")

    abmon, mon, abday, day, am_pm = fetch_cldr()
    posix_source = gen_posix_source(abmon, mon, abday, day, am_pm)
    src_path = save_source(posix_source)

    platform = sys.platform
    print(f"* platform: {platform}")

    if platform == "darwin":
        compiled = gen_macos_compiled(abmon, mon, abday, day, am_pm)
        install_macos(compiled)
    else:
        install_bsd(src_path)

    print()
    if verify():
        print("OK. Usage: export LC_ALL=th_TH.UTF-8")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
