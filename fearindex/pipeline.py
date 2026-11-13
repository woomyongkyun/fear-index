"""수집 → 저장 → 계산. data/ 폴더의 CSV가 유일한 저장소다."""
import datetime as dt
import json
import os
import sys

import pandas as pd

from . import compute, sources
from .config import DATA, HISTORY_START

KST = dt.timezone(dt.timedelta(hours=9))
LEV, INV = "122630", "252670"
STOCKS = DATA / "stocks"


def now_kst():
    return dt.datetime.now(KST)


def _read(name):
    p = DATA / name
    return pd.read_csv(p, index_col=0, parse_dates=True) if p.exists() else None


def _warn(msg):
    print(f"[경고] {msg}", file=sys.stderr)


def _try(label, fn, fallback_name=None):
    """수집 실패 시 지난번에 저장한 값을 쓴다."""
    try:
        df = fn()
        if df is None or len(df) == 0:
            raise RuntimeError("빈 응답")
        if fallback_name:
            df.to_csv(DATA / fallback_name)
        return df, True
    except Exception as e:  # noqa: BLE001
        _warn(f"{label} 수집 실패: {e}")
        old = _read(fallback_name) if fallback_name else None
        return old, False


# ── 종목 폭(오른/내린 종목, 52주 신고가/신저가) ─────────────────────────────

def backfill_breadth(end: str):
    """전 종목 일별 종가를 받아 과거 폭 지표와 월별 최고·최저 기록을 만든다. (최초 1회)"""
    lst = sources.naver_stock_list()
    codes = lst[lst["type"] == "stock"]["code"].tolist()
    print(f"종목 {len(codes)}개 과거 시세 수집 중…")
    m = sources.naver_closes(codes, HISTORY_START, end).sort_index()
    chg = m.diff()
    hi = m.rolling(250, min_periods=200).max()
    lo = m.rolling(250, min_periods=200).min()
    b = pd.DataFrame({
        "adv": (chg > 0).sum(axis=1), "dec": (chg < 0).sum(axis=1),
        "nh": ((m >= hi) & hi.notna()).sum(axis=1), "nl": ((m <= lo) & lo.notna()).sum(axis=1),
    })
    b = b.iloc[250:]
    b["final"] = 1
    b.index.name = "date"
    b.to_csv(DATA / "breadth.csv")
    STOCKS.mkdir(exist_ok=True)
    recent = m[m.index >= m.index[-1] - pd.DateOffset(months=14)]
    for month, g in recent.groupby(recent.index.strftime("%Y-%m")):
        pd.DataFrame({"max": g.max(), "min": g.min()}).dropna().rename_axis("code") \
            .to_csv(STOCKS / f"{month}.csv")
    return b


def _bucket_range(date: pd.Timestamp):
    """date가 속한 달과 그 앞 12개 달의 최고·최저."""
    months = [(date - pd.DateOffset(months=i)).strftime("%Y-%m") for i in range(13)]
    frames = [pd.read_csv(STOCKS / f"{m}.csv", dtype={"code": str}).set_index("code")
              for m in months if (STOCKS / f"{m}.csv").exists()]
    if len(frames) < 10:
        raise RuntimeError("월별 기록 부족 — backfill 필요")
    allf = pd.concat(frames)
    return allf.groupby(level=0)["max"].max(), allf.groupby(level=0)["min"].min()


def update_breadth(date: pd.Timestamp, final: bool):
    """최신 거래일의 폭 지표를 종목 목록 한 번 조회로 갱신한다."""
    b = _read("breadth.csv")
    if date in b.index and b.loc[date, "final"] == 1:
        return b
    lst = sources.naver_stock_list()
    st = lst[(lst["type"] == "stock") & (lst["close"] > 0)].set_index("code")
    hi, lo = _bucket_range(date)
    px = st["close"]
    known = px.index.intersection(hi.index)
    b.loc[date, ["adv", "dec", "nh", "nl", "final"]] = [
        int((st["chg"] > 0).sum()), int((st["chg"] < 0).sum()),
        int((px[known] >= hi[known]).sum()), int((px[known] <= lo[known]).sum()), int(final)]
    b = b.sort_index()
    b.to_csv(DATA / "breadth.csv")
    if final:
        f = STOCKS / f"{date:%Y-%m}.csv"
        cur = (pd.read_csv(f, dtype={"code": str}).set_index("code") if f.exists()
               else pd.DataFrame(columns=["max", "min"]).rename_axis("code"))
        both = pd.DataFrame({"max": cur["max"], "min": cur["min"], "px": px})
        out = pd.DataFrame({"max": both[["max", "px"]].max(axis=1),
                            "min": both[["min", "px"]].min(axis=1)}).dropna()
        out.rename_axis("code").to_csv(f)
        _etf_today(lst, date)
    return b


def _etf_today(lst, date):
    """네이버 일별 시세의 당일 거래량이 잘려 나오는 문제를 피하려고 거래대금을 따로 적어 둔다."""
    v = lst.set_index("code")["value"]
    fix = _read("etf_fix.csv")
    fix = fix if fix is not None else pd.DataFrame(columns=["lev_val", "inv_val"])
    fix.loc[date] = [v.get(LEV), v.get(INV)]
    fix.sort_index().rename_axis("date").to_csv(DATA / "etf_fix.csv")


# ── 전체 갱신 ────────────────────────────────────────────────────────────────

def collect(backfill: bool = False):
    DATA.mkdir(exist_ok=True)
    now = now_kst()
    end = now.strftime("%Y%m%d")
    status = {}

    kospi, status["kospi"] = _try("코스피", lambda: sources.naver_daily("KOSPI", HISTORY_START, end),
                                  "kospi.csv")
    if kospi is None:
        raise SystemExit("코스피 시세가 없어 중단합니다.")
    last = kospi.index[-1]
    final = last.date() < now.date() or now.hour >= 16

    if backfill or not (DATA / "breadth.csv").exists():
        breadth = backfill_breadth(end)
    else:
        try:
            breadth = update_breadth(last, final)
            status["breadth"] = True
        except Exception as e:  # noqa: BLE001
            _warn(f"종목 폭 갱신 실패: {e}")
            breadth, status["breadth"] = _read("breadth.csv"), False

    vix, status["vix"] = _try("VIX", lambda: sources.vix().rename("vix").to_frame(), "vix.csv")

    def fx():
        old = _read("fx.csv")
        if old is None or backfill:
            s = sources.yahoo_close("KRW=X")
        else:
            s = old["fx"]
        try:
            n = sources.naver_fx(1)
            s = pd.concat([s[s.index < n.index[0]], n])
        except Exception as e:  # noqa: BLE001
            _warn(f"네이버 환율 실패, 야후로 대체: {e}")
            y = sources.yahoo_close("KRW=X", "3mo")
            s = pd.concat([s[s.index < y.index[0]], y])
        return s.rename("fx").to_frame()
    fxd, status["fx"] = _try("환율", fx, "fx.csv")

    kof, status["kofia"] = _try("금융투자협회", lambda: sources.kofia(HISTORY_START, end), "kofia.csv")

    def etf():
        val = lambda c: (lambda d: d["close"] * d["volume"])(sources.naver_daily(c, HISTORY_START, end))
        df = pd.DataFrame({"lev_val": val(LEV), "inv_val": val(INV)})
        fix = _read("etf_fix.csv")
        if fix is not None:
            df.update(fix)
        if not final or last not in (fix.index if fix is not None else []):
            df = df.drop(index=last, errors="ignore")      # 잘린 당일 값은 쓰지 않는다
        return df
    etfd, status["etf"] = _try("ETF", etf, "etf.csv")

    key = os.environ.get("ECOS_API_KEY", "").strip()
    spread = None
    if key:
        sp, status["spread"] = _try(
            "신용스프레드", lambda: sources.ecos_spread(key, HISTORY_START, end).rename("spread").to_frame(),
            "spread.csv")
        spread = sp
    elif (DATA / "spread.csv").exists():
        spread = _read("spread.csv")

    try:
        f = sources.naver_flows()
        flows = _read("flows.csv")
        flows = flows if flows is not None else pd.DataFrame(columns=["personal", "foreign", "institution"])
        flows.loc[f["date"]] = [f["personal"], f["foreign"], f["institution"]]
        flows.sort_index().rename_axis("date").to_csv(DATA / "flows.csv")
        status["flows"] = True
    except Exception as e:  # noqa: BLE001
        _warn(f"수급 수집 실패: {e}")
        status["flows"] = False

    # ── 거래일 기준으로 정렬 ──
    idx = kospi.index
    raw = pd.DataFrame({"close": kospi["close"]})
    v = vix["vix"].copy()
    v.index = v.index + pd.Timedelta(days=1)          # 한국 장에는 전날 밤 미국 값이 반영된다
    raw["vix"] = v.reindex(idx.union(v.index)).ffill().reindex(idx)
    raw["fx"] = fxd["fx"].reindex(idx.union(fxd.index)).ffill().reindex(idx)
    for k in ("deposit", "credit", "misu", "forced"):
        raw[k] = kof[k].reindex(idx).ffill(limit=5)
    for k in ("adv", "dec", "nh", "nl"):
        raw[k] = breadth[k].reindex(idx)
    for k in ("lev_val", "inv_val"):
        raw[k] = etfd[k].reindex(idx).ffill(limit=3)
    if spread is not None:
        raw["spread"] = spread["spread"].reindex(idx).ffill(limit=5)
    raw.index.name = "date"
    raw.to_csv(DATA / "raw.csv")

    ind = compute.indicators(raw)
    sc = compute.scores(ind)
    value = compute.index_value(sc)
    out = pd.concat([value.rename("value"), sc.add_prefix("s_"), ind.add_prefix("v_")], axis=1)
    out = out[out["value"].notna()]
    out.round(3).to_csv(DATA / "index.csv")

    slot = "아침" if now.hour < 11 else "낮" if now.hour < 16 else "저녁"
    meta = {"updated": now.strftime("%Y-%m-%d %H:%M"), "slot": slot, "final": bool(final),
            "date": last.strftime("%Y-%m-%d"), "status": status,
            "failed": [k for k, ok in status.items() if not ok]}
    (DATA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{meta['date']} 지수 {out['value'].iloc[-1]} · 실패 {meta['failed'] or '없음'}")
    return out
