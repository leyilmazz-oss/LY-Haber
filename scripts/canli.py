#!/usr/bin/env python3
"""LY Haber canlı veri toplayıcı.

Her 30 dakikada bir GitHub Actions tarafından çalışır.
- Türkçe haber kaynaklarının RSS akışlarından son dakika başlıklarını toplar.
- Piyasa verilerini (BIST 100, dolar, euro, gram altın, Brent, Bitcoin, Ethereum) çeker.
Sonucu data/canli.json dosyasına yazar. Yalnızca Python standart kütüphanesi kullanır.
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from html import unescape

TR = timezone(timedelta(hours=3))
UA = "Mozilla/5.0 (compatible; LYHaber/1.0; +https://github.com/leyilmazz-oss/ly-haber)"

# (kaynak adı, kategori, adres)
FEEDS = [
    ("NTV", "turkiye", "https://www.ntv.com.tr/turkiye.rss"),
    ("NTV", "gundem", "https://www.ntv.com.tr/son-dakika.rss"),
    ("NTV", "dunya", "https://www.ntv.com.tr/dunya.rss"),
    ("NTV", "ekonomi", "https://www.ntv.com.tr/ekonomi.rss"),
    ("NTV", "spor", "https://www.ntv.com.tr/spor.rss"),
    ("AA", "gundem", "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
    ("AA", "ekonomi", "https://www.aa.com.tr/tr/rss/default?cat=ekonomi"),
    ("AA", "dunya", "https://www.aa.com.tr/tr/rss/default?cat=dunya"),
    ("AA", "spor", "https://www.aa.com.tr/tr/rss/default?cat=spor"),
    ("BBC Türkçe", "dunya", "https://feeds.bbci.co.uk/turkce/rss.xml"),
    ("Bloomberg HT", "finans", "https://www.bloomberght.com/rss"),
    ("Cointelegraph TR", "kripto", "https://tr.cointelegraph.com/rss"),
    ("Investing.com", "kripto", "https://tr.investing.com/rss/news_301.rss"),
    ("NTV Spor", "spor", "https://www.ntvspor.net/rss"),
]

KRIPTO = re.compile(r"bitcoin|kripto|ethereum|btc\b|blockchain|stablecoin|altcoin", re.I)
SEKTOR = re.compile(r"lastik|kamyon|\btır\b|çekici|akaryakıt|motorin|mazot|benzin|otomotiv|otomobil|filo|lojistik|nakliye|taşımacılık|karayol|trafik|kış lastiği|kauçuk|odmd|osd\b", re.I)
FINANS = re.compile(r"borsa|bist|hisse|dolar|euro|altın|faiz|tahvil|merkez bankası|tcmb|fed\b|petrol|brent|piyasa", re.I)


def get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(3_000_000)
    return data


def clean(text):
    text = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        d = parsedate_to_datetime(value)
    except Exception:
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def parse_feed(xml_bytes, source, category):
    items = []
    root = ET.fromstring(xml_bytes)
    for node in root.iter():
        name = local(node.tag)
        if name not in ("item", "entry"):
            continue
        title = link = date = summary = ""
        for ch in node:
            n = local(ch.tag)
            if n == "title":
                title = clean(ch.text)
            elif n == "link":
                link = ch.get("href") or (ch.text or "").strip() or link
            elif n in ("pubdate", "published", "updated", "date") and not date:
                date = ch.text or ""
            elif n in ("description", "summary") and not summary:
                summary = clean(ch.text)[:240]
        d = parse_date(date)
        if not (title and link.startswith("http") and d):
            continue
        cat = category
        if KRIPTO.search(title):
            cat = "kripto"
        elif category in ("gundem", "ekonomi") and FINANS.search(title):
            cat = "finans" if category == "ekonomi" else category
        items.append({
            "baslik": title,
            "ozet": summary,
            "url": link,
            "kaynak": source,
            "kategori": cat,
            "zaman": d.astimezone(TR).isoformat(timespec="minutes"),
            "sektor": bool(SEKTOR.search(title + " " + summary)),
        })
    return items


def news():
    all_items, ok = [], []
    for source, cat, url in FEEDS:
        try:
            all_items += parse_feed(get(url), source, cat)
            ok.append(source + ":" + cat)
        except Exception as e:  # bir kaynak çökse de diğerleri devam eder
            print("RSS hata", url, e, file=sys.stderr)
    now = datetime.now(TR)
    seen, out = set(), []
    for it in sorted(all_items, key=lambda x: x["zaman"], reverse=True):
        key = re.sub(r"[^a-z0-9çğıöşü]", "", it["baslik"].lower())[:70]
        if key in seen:
            continue
        if datetime.fromisoformat(it["zaman"]) < now - timedelta(hours=36):
            continue
        if datetime.fromisoformat(it["zaman"]) > now + timedelta(minutes=10):
            continue
        seen.add(key)
        out.append(it)
    return out[:150], ok


def yahoo(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
    meta = json.loads(get(url))["chart"]["result"][0]["meta"]
    price = float(meta["regularMarketPrice"])
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    return price, (float(prev) if prev else None)


def tr_num(v, dec):
    s = f"{v:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def row(ad, deger, pct, birim_on="", birim_son=""):
    if deger is None:
        return {"ad": ad, "deger": "—", "degisim": "", "yon": ""}
    item = {"ad": ad, "deger": deger, "degisim": "", "yon": ""}
    if pct is not None:
        item["degisim"] = ("+" if pct >= 0 else "−") + "%" + tr_num(abs(pct), 2)
        item["yon"] = "up" if pct >= 0 else "down"
    return item


def pct(p, prev):
    return (p - prev) / prev * 100 if prev else None


def market():
    rows = []
    usd = None
    # BIST 100
    try:
        p, prev = yahoo("XU100.IS"); rows.append(row("BIST 100", tr_num(p, 2), pct(p, prev)))
    except Exception as e:
        print("BIST", e, file=sys.stderr); rows.append(row("BIST 100", None, None))
    # Dolar / Euro
    for ad, sym, key in (("Dolar/TL", "TRY=X", "USD"), ("Euro/TL", "EURTRY=X", "EUR")):
        try:
            p, prev = yahoo(sym)
            if key == "USD":
                usd = p
            rows.append(row(ad, tr_num(p, 2), pct(p, prev)))
        except Exception as e:
            print(ad, e, file=sys.stderr)
            try:
                fx = json.loads(get(f"https://api.frankfurter.app/latest?from={key}&to=TRY"))
                v = float(fx["rates"]["TRY"])
                if key == "USD":
                    usd = v
                rows.append(row(ad, tr_num(v, 2), None))
            except Exception as e2:
                print(ad, "yedek", e2, file=sys.stderr); rows.append(row(ad, None, None))
    # Gram altın (TL) = ons altın (USD) * dolar / 31,1035
    try:
        p, prev = yahoo("GC=F")
        if usd:
            rows.append(row("Gram altın", tr_num(p * usd / 31.1035, 0) + " ₺", pct(p, prev)))
        else:
            rows.append(row("Ons altın", tr_num(p, 0) + " $", pct(p, prev)))
    except Exception as e:
        print("altın", e, file=sys.stderr); rows.append(row("Gram altın", None, None))
    # Brent
    try:
        p, prev = yahoo("BZ=F"); rows.append(row("Brent", tr_num(p, 2) + " $", pct(p, prev)))
    except Exception as e:
        print("Brent", e, file=sys.stderr); rows.append(row("Brent", None, None))
    # Bitcoin / Ethereum
    try:
        cg = json.loads(get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"))
        rows.append(row("Bitcoin", tr_num(cg["bitcoin"]["usd"], 0) + " $", cg["bitcoin"].get("usd_24h_change")))
        rows.append(row("Ethereum", tr_num(cg["ethereum"]["usd"], 0) + " $", cg["ethereum"].get("usd_24h_change")))
    except Exception as e:
        print("kripto", e, file=sys.stderr)
        for ad, sym in (("Bitcoin", "BTC-USD"), ("Ethereum", "ETH-USD")):
            try:
                p, prev = yahoo(sym); rows.append(row(ad, tr_num(p, 0) + " $", pct(p, prev)))
            except Exception:
                rows.append(row(ad, None, None))
    return rows


def main(path):
    items, ok = news()
    data = {
        "guncelleme": datetime.now(TR).isoformat(timespec="minutes"),
        "piyasa": market(),
        "sonDakika": items,
        "kaynaklar": ok,
    }
    # Hiç haber gelmediyse eski dosyadaki başlıkları koru
    if not items:
        try:
            with open(path, encoding="utf-8") as f:
                data["sonDakika"] = json.load(f).get("sonDakika", [])
        except Exception:
            pass
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"{len(items)} başlık, {len(ok)} kaynak")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/canli.json")
