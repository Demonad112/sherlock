#!/usr/bin/env python3
"""Sherlock investigator console.

Sherlock only understands usernames. This console converts emails, first/last
names and Canadian phone numbers into username *candidates*, runs each through
the stock Sherlock engine, and labels every hit with how strong the link to the
original input actually is. Hits are leads, not identity confirmation.

Interactive:      python sherlock_console.py
Non-interactive:  python sherlock_console.py email jane.doe@gmail.com
                  python sherlock_console.py name "Jane Doe" --site GitHub
                  python sherlock_console.py phone "(403) 555-0123"
                  python sherlock_console.py username jdoe
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime

import requests
from colorama import Fore, Style, init as colorama_init

from sherlock_project.notify import QueryNotify
from sherlock_project.result import QueryStatus
from sherlock_project.sherlock import multiple_usernames, sherlock
from sherlock_project.sites import SitesInformation

PKG_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "sherlock_project", "resources", "data.json")

ALBERTA_AREA_CODES = {"403", "587", "825", "368", "780"}

CONF_DIRECT, CONF_HIGH, CONF_MED, CONF_LOW = "direct", "high", "medium", "low"

METHOD_NOTES = {
    "username": "Exact username supplied by the operator.",
    "email": "Username derived from the email local part (medium confidence); "
             "Gravatar hash match is an email-linked hit (high confidence).",
    "name": "Username variants guessed from first/last name. Common names "
            "produce many false positives; treat every hit as unverified.",
    "phone": "Sherlock cannot confirm phone ownership. Digit-based handles "
             "are speculative; use the manual pivots for real attribution.",
}


# --------------------------------------------------------------------------
# Input -> candidate derivation (pure functions)
# --------------------------------------------------------------------------
def _dedupe(items):
    seen, out = set(), []
    for i in items:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


def normalize_phone_ca(raw):
    """Return dict(e164, national, area_code, alberta) or None if not a valid NANP number."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    area, exch = digits[:3], digits[3:6]
    if area[0] in "01" or exch[0] in "01" or area[1:] == "11":
        return None
    return {"e164": "+1" + digits, "national": digits, "area_code": area,
            "alberta": area in ALBERTA_AREA_CODES}


def phone_candidates(raw):
    info = normalize_phone_ca(raw)
    if not info:
        raise ValueError(f"Not a valid North American number: {raw!r}")
    n = info["national"]
    a, b, c = n[:3], n[3:6], n[6:]
    cands = [n, "1" + n, f"{a}-{b}-{c}", f"{a}_{b}_{c}", f"{a}.{b}.{c}"]
    return [(x, CONF_LOW) for x in _dedupe(cands)]


def phone_pivots(raw):
    info = normalize_phone_ca(raw)
    if not info:
        return []
    n, e = info["national"], info["e164"]
    return [
        f"Search engines, exact match: \"{e}\" \"{n}\" \"({n[:3]}) {n[3:6]}-{n[6:]}\"",
        "Carrier / line type: CRTC number-range data or a carrier lookup you are licensed to use",
        "Caller-ID / reverse lookup apps and Truecaller-style sources (manual, ToS applies)",
        "Messaging apps: check whether the number is registered (WhatsApp/Signal/Telegram) manually",
        "Breach corpora you are authorised to query (phone as a field)",
    ]


def email_candidates(email):
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError(f"Not a valid email address: {email!r}")
    local = email.split("@", 1)[0]
    base = local.split("+", 1)[0]
    cands = [local, base, base.replace(".", ""), base.replace(".", "_"), base.replace(".", "-")]
    return [(x, CONF_MED) for x in _dedupe(cands) if len(x) >= 3]


def gravatar_check(email, timeout=15, proxy=None):
    """Return the Gravatar profile URL if the email has a Gravatar, else None."""
    h = hashlib.md5(email.strip().lower().encode()).hexdigest()
    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        r = requests.get(f"https://www.gravatar.com/avatar/{h}?d=404",
                         timeout=timeout, proxies=proxies)
        if r.status_code == 200:
            return f"https://gravatar.com/{h}"
    except requests.RequestException:
        pass
    return None


def name_candidates(full_name, max_variants=12):
    parts = [re.sub(r"[^a-z0-9]", "", p) for p in (full_name or "").lower().split()]
    parts = [p for p in parts if p]
    if len(parts) < 2:
        raise ValueError("Provide a first and last name")
    f, l = parts[0], parts[-1]
    cands = [f + l, f"{f}.{l}", f"{f}_{l}", f"{f}-{l}", f[0] + l, f + l[0],
             l + f, f"{l}.{f}", f"{f[0]}.{l}", f"{f[0]}_{l}", f + "_" + l[0], l + f[0]]
    return [(x, CONF_LOW) for x in _dedupe(cands)[:max_variants]]


def username_candidates(username):
    if "{?}" in username:
        return [(u, CONF_DIRECT) for u in multiple_usernames(username)]
    return [(username, CONF_DIRECT)]


# --------------------------------------------------------------------------
# Engine
# --------------------------------------------------------------------------
class ConsoleNotify(QueryNotify):
    """Silent notifier; the console prints its own progress and results."""

    def update(self, result):
        self.result = result


class Settings:
    def __init__(self):
        self.timeout = 30.0
        self.proxy = None
        self.nsfw = False
        self.sites = []          # empty = all
        self.max_variants = 12
        self.remote = False
        self.gravatar = True
        self.outdir = "results"
        self.color = True


def load_sites(settings):
    if settings.remote:
        sites = SitesInformation(honor_exclusions=True)
    else:
        sites = SitesInformation(PKG_DATA, honor_exclusions=False)
    if not settings.nsfw:
        sites.remove_nsfw_sites(do_not_remove=settings.sites)
    data = {s.name: s.information for s in sites}
    if settings.sites:
        wanted = {w.lower() for w in settings.sites}
        data = {k: v for k, v in data.items() if k.lower() in wanted}
        if not data:
            raise SystemExit(f"No matching sites for: {', '.join(settings.sites)}")
    return data


def paint(text, color, settings):
    return f"{color}{text}{Style.RESET_ALL}" if settings.color else text


def run_candidates(candidates, site_data, settings, interrupted=None):
    """candidates: [(username, confidence)]. Returns list of hit dicts."""
    hits = []
    total = len(candidates)
    for idx, (user, conf) in enumerate(candidates, 1):
        print(paint(f"[{idx}/{total}] {user}", Fore.CYAN, settings), end=" ... ", flush=True)
        try:
            res = sherlock(user, site_data, ConsoleNotify(),
                           proxy=settings.proxy, timeout=settings.timeout)
        except KeyboardInterrupt:
            print("interrupted")
            if interrupted is not None:
                interrupted.append(True)
            break
        found = 0
        for site, r in res.items():
            if r["status"].status == QueryStatus.CLAIMED:
                found += 1
                hits.append({"candidate": user, "confidence": conf, "site": site,
                             "url": r["url_user"], "http_status": r.get("http_status"),
                             "response_time_s": r["status"].query_time})
        print(paint(f"{found} hit(s)", Fore.GREEN if found else Fore.YELLOW, settings))
    return hits


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "query"


def write_reports(kind, value, candidates, hits, extras, settings, partial=False):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    d = os.path.join(settings.outdir, f"{stamp}_{kind}_{slugify(value)}")
    os.makedirs(d, exist_ok=True)
    cols = ["candidate", "confidence", "site", "url", "http_status", "response_time_s"]
    with open(os.path.join(d, "hits.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(hits)
    with open(os.path.join(d, "raw.json"), "w", encoding="utf-8") as fh:
        json.dump({"type": kind, "input": value, "partial": partial,
                   "candidates": candidates, "hits": hits, "extras": extras}, fh, indent=2)
    lines = [f"Sherlock console report  {datetime.now().isoformat(timespec='seconds')}",
             f"Input type : {kind}", f"Input      : {value}",
             f"Method     : {METHOD_NOTES[kind]}",
             f"Candidates : {', '.join(c for c, _ in candidates)}",
             f"Complete   : {'no (interrupted)' if partial else 'yes'}", ""]
    lines += [f"{k}: {v}" for k, v in extras.items() if isinstance(v, str)]
    for k, v in extras.items():
        if isinstance(v, list):
            lines += ["", f"{k}:"] + [f"  - {x}" for x in v]
    lines += ["", f"Hits ({len(hits)}):"]
    for h in sorted(hits, key=lambda x: (x["candidate"], x["site"])):
        lines.append(f"  [{h['confidence']:<6}] {h['candidate']:<24} {h['site']:<22} {h['url']}")
    with open(os.path.join(d, "report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return d


def investigate(kind, value, settings, site_data=None):
    extras = {}
    if kind == "username":
        cands = username_candidates(value)
    elif kind == "email":
        cands = email_candidates(value)
        if settings.gravatar:
            g = gravatar_check(value, proxy=settings.proxy)
            extras["gravatar"] = g or "no Gravatar for this email"
            if g:
                print(paint(f"Gravatar match (high confidence): {g}", Fore.GREEN, settings))
    elif kind == "name":
        cands = name_candidates(value, settings.max_variants)
    elif kind == "phone":
        info = normalize_phone_ca(value)
        cands = phone_candidates(value)
        extras["e164"] = info["e164"]
        extras["region"] = ("Alberta area code " if info["alberta"] else "Area code ") + info["area_code"]
        extras["manual pivots"] = phone_pivots(value)
        print(paint(f"{info['e164']}  ({extras['region']})", Fore.CYAN, settings))
        print(paint(METHOD_NOTES["phone"], Fore.YELLOW, settings))
    else:
        raise ValueError(kind)

    print(f"Candidates: {', '.join(c for c, _ in cands)}")
    site_data = site_data or load_sites(settings)
    print(f"Checking {len(site_data)} sites, timeout {settings.timeout}s\n")
    interrupted = []
    hits = run_candidates(cands, site_data, settings, interrupted)
    if extras.get("gravatar", "").startswith("http"):
        hits.insert(0, {"candidate": value, "confidence": CONF_HIGH, "site": "Gravatar",
                        "url": extras["gravatar"], "http_status": 200, "response_time_s": None})
    outdir = write_reports(kind, value, cands, hits, extras, settings, bool(interrupted))

    print(f"\n{len(hits)} hit(s). " + paint(f"Saved: {outdir}", Fore.CYAN, settings))
    for h in sorted(hits, key=lambda x: (x["candidate"], x["site"])):
        print(f"  [{h['confidence']:<6}] {h['candidate']:<22} {h['site']:<20} {h['url']}")
    if kind == "phone":
        print("\nManual pivots:")
        for p in extras["manual pivots"]:
            print(f"  - {p}")
    return hits


# --------------------------------------------------------------------------
# Interactive menu
# --------------------------------------------------------------------------
def prompt(msg):
    try:
        return input(msg).strip()
    except EOFError:
        return "0"


def settings_menu(s):
    while True:
        print(f"\nSettings\n 1 timeout: {s.timeout}\n 2 proxy: {s.proxy}\n 3 NSFW sites: {s.nsfw}"
              f"\n 4 site subset: {s.sites or 'all'}\n 5 max name variants: {s.max_variants}"
              f"\n 6 manifest: {'remote' if s.remote else 'local'}\n 7 Gravatar check: {s.gravatar}"
              f"\n 0 back")
        c = prompt("> ")
        try:
            if c == "1":
                t = float(prompt("timeout seconds: "))
                if t <= 0:
                    raise ValueError
                s.timeout = t
            elif c == "2":
                s.proxy = prompt("proxy URL (blank = none): ") or None
            elif c == "3":
                s.nsfw = not s.nsfw
            elif c == "4":
                s.sites = [x for x in re.split(r"[,\s]+", prompt("site names (blank = all): ")) if x]
            elif c == "5":
                s.max_variants = max(1, int(prompt("max variants: ")))
            elif c == "6":
                s.remote = not s.remote
            elif c == "7":
                s.gravatar = not s.gravatar
            elif c == "0":
                return
        except ValueError:
            print("Invalid value.")


def batch(settings):
    path = prompt("File (lines like `email:a@b.com`, `name:Jane Doe`, `phone:403...`, `username:x`): ")
    try:
        with open(path, encoding="utf-8") as fh:
            rows = [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    except OSError as e:
        print(e)
        return
    site_data = load_sites(settings)
    for row in rows:
        kind, _, val = row.partition(":")
        if kind not in METHOD_NOTES or not val.strip():
            print(f"Skipping: {row}")
            continue
        print(paint(f"\n=== {kind}: {val.strip()} ===", Fore.MAGENTA, settings))
        try:
            investigate(kind, val.strip(), settings, site_data)
        except ValueError as e:
            print(e)


def menu(settings):
    labels = {"1": ("username", "Username"), "2": ("email", "Email"),
              "3": ("name", "Full name (first last)"), "4": ("phone", "Phone (Canada)")}
    while True:
        print("\n=== Sherlock Investigator Console ===")
        for k, (_, lab) in labels.items():
            print(f" {k}  {lab}")
        print(" 5  Settings\n 6  Batch file\n 0  Exit")
        c = prompt("> ")
        if c == "0":
            return
        if c == "5":
            settings_menu(settings)
        elif c == "6":
            batch(settings)
        elif c in labels:
            kind, lab = labels[c]
            val = prompt(f"{lab}: ")
            if not val:
                continue
            try:
                investigate(kind, val, settings)
            except ValueError as e:
                print(paint(str(e), Fore.RED, settings))


def main():
    p = argparse.ArgumentParser(description="Sherlock investigator console")
    p.add_argument("kind", nargs="?", choices=list(METHOD_NOTES), help="omit for interactive menu")
    p.add_argument("value", nargs="?")
    p.add_argument("--site", action="append", default=[])
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--proxy")
    p.add_argument("--nsfw", action="store_true")
    p.add_argument("--remote", action="store_true", help="use the live manifest instead of the bundled one")
    p.add_argument("--max-variants", type=int, default=12)
    p.add_argument("--no-gravatar", action="store_true")
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--outdir", default="results")
    a = p.parse_args()
    if a.timeout <= 0:
        p.error("--timeout must be positive")

    s = Settings()
    s.timeout, s.proxy, s.nsfw, s.sites = a.timeout, a.proxy, a.nsfw, a.site
    s.remote, s.max_variants, s.gravatar = a.remote, a.max_variants, not a.no_gravatar
    s.outdir, s.color = a.outdir, not a.no_color
    colorama_init(strip=not s.color)

    if not a.kind:
        menu(s)
        return 0
    if not a.value:
        p.error("value required")
    try:
        investigate(a.kind, a.value, s)
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
