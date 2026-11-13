"""data/ → dist/ 정적 사이트."""
import json
import shutil

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from . import art, compute, content
from .config import BANDS, DATA, DIST, INDICATORS, ROOT, STATIC, TEMPLATES, band_of

WEEKDAYS = "월화수목금토일"


def load():
    idx = pd.read_csv(DATA / "index.csv", index_col=0, parse_dates=True)
    raw = pd.read_csv(DATA / "raw.csv", index_col=0, parse_dates=True)
    meta = json.loads((DATA / "meta.json").read_text(encoding="utf-8"))
    site = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    flows = None
    if (DATA / "flows.csv").exists():
        flows = pd.read_csv(DATA / "flows.csv", index_col=0, parse_dates=True)
    return idx, raw, meta, site, flows


def day_view(idx, raw, date):
    """하루치 화면 자료."""
    row = idx.loc[date]
    pos = idx.index.get_loc(date)
    prev = idx["value"].iloc[pos - 1] if pos else None
    close = raw["close"]
    cpos = close.index.get_loc(date)
    chg = (close.iloc[cpos] / close.iloc[cpos - 1] - 1) * 100
    scores = {i[0]: row[f"s_{i[0]}"] for i in INDICATORS}
    used = {k: v for k, v in scores.items() if v == v}
    w = compute.weights(used.keys())
    comps = []
    for key, name, group, _w, _dir, _unit, desc in INDICATORS:
        if key not in used:
            continue
        s = used[key]
        comps.append({"key": key, "name": name, "group": group, "score": round(s),
                      "level": content.level(s), "color": band_of(min(s, 99.9))["color"],
                      "value": content.fmt_value(key, row[f"v_{key}"]),
                      "weight": f"{w[key] * 100:.1f}", "desc": desc})
    comps.sort(key=lambda c: -c["score"])
    up, down = content.drivers(scores)
    value = float(row["value"])
    return {
        "date": date, "iso": f"{date:%Y-%m-%d}",
        "label": f"{date.year}년 {date.month}월 {date.day}일 ({WEEKDAYS[date.weekday()]})",
        "value": value, "round": round(value), "prev": prev,
        "delta": None if prev is None else round(value - prev, 1),
        "band": band_of(value), "mood": content.MOOD[band_of(value)["key"]],
        "comps": comps, "up": up, "down": down, "n": len(comps),
        "kospi": float(close.iloc[cpos]), "kospi_chg": float(chg),
        "text": content.daily(date, value, prev, scores, float(close.iloc[cpos]), float(chg)),
    }


def period_reports(idx, raw, freq, label_fn, slug_fn):
    out = []
    close = raw["close"]
    sc = idx.filter(like="s_")
    for _p, g in idx.groupby(idx.index.to_period(freq)):
        if len(g) < 3:
            continue
        days = list(zip(g.index, g["value"]))
        before = close[close.index < g.index[0]]
        base = before.iloc[-1] if len(before) else close[g.index[0]]
        ret = (close[g.index[-1]] / base - 1) * 100
        change = (sc.loc[g.index[-1]] - sc.loc[g.index[0]]).rename(lambda c: c[2:]).to_dict()
        label = label_fn(g.index[0], g.index[-1])
        out.append({"slug": slug_fn(g.index[0]), "title": f"{label} 공포수치 리포트", "label": label,
                    "start": g.index[0], "end": g.index[-1], "last": float(g["value"].iloc[-1]),
                    "avg": float(g["value"].mean()), "band": band_of(float(g["value"].iloc[-1])),
                    "kospi_ret": float(ret), "text": content.period(label, days, float(ret), change),
                    "points": [(f"{d:%Y-%m-%d}", float(v)) for d, v in days],
                    "days": [{"iso": f"{d:%Y-%m-%d}", "md": f"{d.month}.{d.day}", "value": round(v),
                              "band": band_of(v)} for d, v in days]})
    return out[::-1]


def build():
    idx, raw, meta, site, flows = load()
    env = Environment(loader=FileSystemLoader(TEMPLATES),
                      autoescape=select_autoescape(["html", "xml"]))
    env.filters["num"] = lambda v, d=0: f"{v:,.{d}f}"
    env.filters["signed"] = lambda v, d=1: f"{v:+,.{d}f}"

    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "archive").mkdir(parents=True)
    (DIST / "report").mkdir()
    shutil.copytree(STATIC, DIST / "static")
    shutil.copy(DATA / "index.csv", DIST / "static" / "index.csv")

    n_ind = int(idx.filter(like="s_").iloc[-1].notna().sum())
    faq = [(q, a.replace("{n}", str(n_ind))) for q, a in content.FAQ]
    base = site.get("base_url", "").rstrip("/")
    common = {"site": site, "meta": meta, "bands": BANDS, "n_ind": n_ind, "base": base,
              "year": pd.Timestamp(meta["date"]).year}
    urls = []

    def render(tpl, path, root, **ctx):
        html = env.get_template(tpl).render(root=root, path=path, **common, **ctx)
        out = DIST / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        urls.append(path)

    # ── 홈 ──
    today = idx.index[-1]
    view = day_view(idx, raw, today)
    half = idx["value"].iloc[-125:]
    stats = {"avg": round(half.mean()), "max": round(half.max()), "max_d": half.idxmax(),
             "min": round(half.min()), "min_d": half.idxmin()}
    sc = idx.filter(like="s_").rename(columns=lambda c: c[2:])
    similar = compute.similar_days(sc, raw["close"].reindex(idx.index))
    for s in similar:
        s["iso"] = f"{s['date']:%Y-%m-%d}"
        s["value"] = round(float(idx.loc[s["date"], "value"]))
        s["band"] = band_of(s["value"])
    bstats = compute.band_stats(idx["value"], raw["close"].reindex(idx.index))
    flow = None
    if flows is not None and today in flows.index:
        f = flows.loc[today]
        mx = max(abs(f)) or 1
        flow = [{"name": n, "v": float(f[k]), "w": round(abs(f[k]) / mx * 100)}
                for n, k in (("개인", "personal"), ("외국인", "foreign"), ("기관", "institution"))]
    timeline = art.timeline_svg([(f"{d:%Y-%m-%d}", float(v)) for d, v in half.items()])
    render("index.html", "index.html", "", v=view, stats=stats, similar=similar, bstats=bstats,
           flow=flow, faq=faq,
           gauge=Markup(art.gauge_svg(view["value"])), timeline=Markup(timeline),
           character=Markup(art.character_html(view["band"]["key"], "")),
           recent=[day_brief(idx, d) for d in idx.index[-8:-1][::-1]])

    # ── 날짜별 기록 ──
    dates = list(idx.index)
    for i, d in enumerate(dates):
        dv = day_view(idx, raw, d)
        render("day.html", f"archive/{dv['iso']}.html", "../", v=dv,
               gauge=Markup(art.gauge_svg(dv["value"])),
               character=Markup(art.character_html(dv["band"]["key"], "../", 150)),
               prev_day=f"{dates[i - 1]:%Y-%m-%d}" if i else None,
               next_day=f"{dates[i + 1]:%Y-%m-%d}" if i + 1 < len(dates) else None)
    months = []
    for p, g in idx.groupby(idx.index.to_period("M")):
        months.append({"label": f"{p.year}년 {p.month}월", "avg": round(g["value"].mean()),
                       "days": [day_brief(idx, d) for d in g.index]})
    render("archive.html", "archive/index.html", "../", months=months[::-1])

    # ── 리포트 ──
    weekly = period_reports(
        idx, raw, "W", lambda a, b: f"{a.year}년 {a.month}월 {a.day}일~{b.month}월 {b.day}일 주간",
        lambda a: f"weekly-{a.isocalendar()[0]}-w{a.isocalendar()[1]:02d}")
    monthly = period_reports(idx, raw, "M", lambda a, b: f"{a.year}년 {a.month}월 월간",
                             lambda a: f"monthly-{a:%Y-%m}")
    for r in weekly + monthly:
        render("report.html", f"report/{r['slug']}.html", "../", r=r,
               timeline=Markup(art.timeline_svg(r["points"])),
               character=Markup(art.character_html(r["band"]["key"], "../", 130)))
    render("reports.html", "report/index.html", "../", weekly=weekly[:26], monthly=monthly)

    # ── 고정 페이지 ──
    w = compute.weights([c["key"] for c in view["comps"]])
    table = [{"name": i[1], "group": i[2], "weight": f"{w[i[0]] * 100:.1f}", "desc": i[6],
              "dir": "클수록 공포" if i[4] > 0 else "작을수록 공포"}
             for i in INDICATORS if i[0] in w.index]
    render("about.html", "about.html", "", table=table, faq=faq,
           first=f"{idx.index[0]:%Y년 %m월}", days=len(idx),
           character=Markup(art.character_html("calm", "", 150)))
    render("privacy.html", "privacy.html", "")

    # ── 검색엔진용 파일 ──
    urls.remove("privacy.html")
    if base:
        items = "".join(
            f"<url><loc>{base}/{'' if u == 'index.html' else u.replace('index.html', '')}</loc>"
            f"<lastmod>{meta['date']}</lastmod></url>" for u in urls)
        (DIST / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>',
            encoding="utf-8")
        feed = env.get_template("feed.xml").render(**common, weekly=weekly[:10], monthly=monthly[:6],
                                                   v=view)
        (DIST / "feed.xml").write_text(feed, encoding="utf-8")
    robots = "User-agent: *\nAllow: /\n" + (f"Sitemap: {base}/sitemap.xml\n" if base else "")
    (DIST / "robots.txt").write_text(robots, encoding="utf-8")
    if site.get("adsense"):
        pub = site["adsense"].replace("ca-", "")
        (DIST / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
    if site.get("domain"):
        (DIST / "CNAME").write_text(site["domain"], encoding="utf-8")
    (DIST / ".nojekyll").write_text("", encoding="utf-8")
    print(f"사이트 생성 완료: {len(urls) + 1}쪽 → {DIST}")


def day_brief(idx, d):
    v = float(idx.loc[d, "value"])
    return {"iso": f"{d:%Y-%m-%d}", "md": f"{d.month}.{d.day}", "value": round(v), "band": band_of(v)}
