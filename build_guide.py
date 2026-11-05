#!/usr/bin/env python3
"""Build an XMLTV guide for the iptv-org India playlist.

Downloads the live iptv-org India playlist and two public epgshare01 India XMLTV
feeds, then rewrites the guide's <channel id> values to the playlist's tvg-id
values so Kodi's IPTV Simple Client matches them exactly. Output:
docs/guide_in.xml.gz (served by GitHub Pages).
"""
import gzip, html, pathlib, re, sys, urllib.request

UA = {"User-Agent": "Mozilla/5.0 (ccgtv-epg; +https://github.com/Agpulkit95/ccgtv-epg)"}
PLAYLIST = "https://iptv-org.github.io/iptv/countries/in.m3u"
SOURCES = [  # (url, priority: lower wins)
    ("https://epgshare01.online/epgshare01/epg_ripper_IN4.xml.gz", 0),
    ("https://epgshare01.online/epgshare01/epg_ripper_IN1.xml.gz", 1),
]
OUT = pathlib.Path(__file__).resolve().parent / "docs" / "guide_in.xml.gz"


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def norm(s: str) -> str:
    s = re.sub(r"\s*\(\d+[pi]\)\s*$", "", s)
    return re.sub(r"[^a-z0-9]", "", s.lower())


def norm_id(i: str) -> str:
    return norm(re.sub(r"\.[a-z]{2}$", "", i))


def main() -> int:
    m3u = get(PLAYLIST).decode("utf-8", "ignore")
    entries = re.findall(r"#EXTINF:-1([^\n]*),([^\n]*)\n", m3u)
    chans = []
    for attrs, title in entries:
        m = re.search(r'tvg-id="([^"]*)"', attrs)
        tv = m.group(1) if m else ""
        if tv:
            chans.append((tv, norm_id(tv.split("@")[0]), norm(title)))

    src = {}  # normalised key -> (source channel id, programmes, priority)
    for url, prio in SOURCES:
        try:
            xml = gzip.decompress(get(url)).decode("utf-8", "ignore")
        except Exception as e:  # keep going with the other feed
            print(f"WARN {url}: {e}", file=sys.stderr)
            continue
        progs = {}
        for m in re.finditer(r'<programme ([^>]*channel="([^"]+)"[^>]*)>(.*?)</programme>', xml, re.S):
            progs.setdefault(m.group(2), []).append((m.group(1), m.group(3)))
        for cid, body in re.findall(r'<channel id="([^"]+)">(.*?)</channel>', xml, re.S):
            plist = progs.get(cid)
            if not plist:
                continue
            names = re.findall(r"<display-name[^>]*>([^<]+)</display-name>", body)
            keys = {norm_id(cid)} | {norm(html.unescape(n)) for n in names}
            for k in keys:
                if k and (k not in src or prio < src[k][2]):
                    src[k] = (cid, plist, prio)

    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="ccgtv-epg">']
    used = {}
    for tv, kid, kname in chans:
        hit = src.get(kid) or src.get(kname)
        if not hit:
            continue
        cid, plist, _ = hit
        out.append(f'  <channel id="{html.escape(tv)}"><display-name>{html.escape(cid)}</display-name></channel>')
        used[tv] = plist
    nprog = 0
    for tv, plist in used.items():
        for attrs, body in plist:
            attrs2 = re.sub(r'channel="[^"]+"', f'channel="{html.escape(tv)}"', attrs)
            out.append(f"  <programme {attrs2}>{body}</programme>")
            nprog += 1
    out.append("</tv>")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wb", compresslevel=9) as f:
        f.write("\n".join(out).encode("utf-8"))
    print(f"channels in playlist: {len(chans)}  with guide: {len(used)}  programmes: {nprog}  -> {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0 if used else 1


if __name__ == "__main__":
    sys.exit(main())
