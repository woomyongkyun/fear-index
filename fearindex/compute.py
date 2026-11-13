"""원자료 → 지표 → 백분위 점수 → 지수. 네트워크를 쓰지 않는 순수 계산."""
import numpy as np
import pandas as pd

from .config import INDICATORS, KEYS, MIN_WINDOW, WINDOW, band_of


def indicators(raw: pd.DataFrame) -> pd.DataFrame:
    """raw: 거래일 인덱스. close, vix, fx, deposit, credit, misu, forced, adv, dec, nh, nl,
    lev_val, inv_val, (spread) 열."""
    c = raw["close"]
    r = c.pct_change()
    out = pd.DataFrame(index=raw.index)
    out["mom_short"] = r.ewm(span=5, adjust=False).mean() * 100
    out["mom_125"] = (c / c.rolling(125).mean() - 1) * 100
    out["down_vol"] = np.sqrt((r.clip(upper=0) ** 2).rolling(20).mean() * 252) * 100
    out["real_vol"] = r.rolling(20).std() * np.sqrt(252) * 100
    out["vix"] = raw["vix"]
    out["fx_chg"] = raw["fx"].pct_change(20) * 100
    out["fx_shock"] = out["fx_chg"].abs()
    for k in ("deposit", "credit", "misu"):
        out[k] = raw[k].pct_change(20) * 100
    out["forced"] = raw["forced"].rolling(5).mean() / 100          # 백만원 → 억원
    out["adr"] = raw["adv"].rolling(5).sum() / raw["dec"].rolling(5).sum()
    out["hilo"] = (raw["nh"].rolling(5).sum() + 1) / (raw["nl"].rolling(5).sum() + 1)
    tot = raw["lev_val"] + raw["inv_val"]
    out["inverse"] = (raw["inv_val"] / tot * 100).rolling(5).mean()
    out["spread"] = raw["spread"] if "spread" in raw else np.nan
    return out[KEYS]


def _pct_last(a: np.ndarray) -> float:
    x = a[-1]
    if np.isnan(x):
        return np.nan
    v = a[~np.isnan(a)]
    if len(v) < MIN_WINDOW:
        return np.nan
    return ((v < x).sum() + 0.5 * (v == x).sum()) / len(v) * 100


def percentile(s: pd.Series, window: int = WINDOW) -> pd.Series:
    """각 날짜의 값이 직전 window 거래일(당일 포함) 안에서 몇 번째 백분위인지."""
    return s.rolling(window, min_periods=1).apply(_pct_last, raw=True)


def scores(ind: pd.DataFrame) -> pd.DataFrame:
    """지표별 공포 점수(0 잔잔 ~ 100 공포)."""
    out = pd.DataFrame(index=ind.index)
    for key, _n, _g, _w, direction, _u, _d in INDICATORS:
        p = percentile(ind[key])
        out[key] = p if direction > 0 else 100 - p
    return out


def weights(available=None) -> pd.Series:
    w = pd.Series({i[0]: i[3] for i in INDICATORS})
    if available is not None:
        w = w[[k for k in w.index if k in available]]
    return w / w.sum()


def index_value(sc: pd.DataFrame, min_count: int = 10) -> pd.Series:
    """있는 지표만으로 비중을 다시 맞춘 가중 평균."""
    w = pd.Series({i[0]: i[3] for i in INDICATORS})[sc.columns]
    have = sc.notna()
    val = sc.fillna(0).mul(w, axis=1).sum(axis=1) / have.mul(w, axis=1).sum(axis=1)
    return val.where(have.sum(axis=1) >= min_count).round(1)


def similar_days(sc: pd.DataFrame, close: pd.Series, top: int = 3,
                 horizon: int = 60, gap: int = 20):
    """오늘의 지표 점수 패턴과 가장 닮은 과거 날. 그 뒤 horizon 거래일 코스피 수익률."""
    today = sc.iloc[-1]
    cols = today.dropna().index
    past = sc[cols].iloc[:-horizon].dropna()
    if past.empty:
        return []
    rmse = np.sqrt(((past - today[cols]) ** 2).mean(axis=1)).sort_values()
    fwd = (close.shift(-horizon) / close - 1) * 100
    picked = []
    for d, e in rmse.items():
        if all(abs((d - p["date"]).days) > gap * 1.5 for p in picked):
            picked.append({"date": d, "similarity": round(100 - e, 1),
                           "fwd": round(float(fwd[d]), 1)})
        if len(picked) == top:
            break
    return picked


def band_stats(idx: pd.Series, close: pd.Series):
    """오늘과 같은 구간이었던 날들의 이후 수익률과, 아무 날이나 샀을 때의 비교값."""
    b = band_of(idx.iloc[-1])
    res = {"band": b}
    v = idx.dropna()
    for h in (20, 60):
        fwd = ((close.shift(-h) / close - 1) * 100).reindex(v.index).dropna()
        same = fwd[(v.reindex(fwd.index) >= b["lo"]) & (v.reindex(fwd.index) < b["hi"] + 1e-9)]
        res[f"n{h}"] = int(len(same))
        res[f"avg{h}"] = round(float(same.mean()), 1) if len(same) else None
        res[f"win{h}"] = round(float((same > 0).mean() * 100)) if len(same) else None
        res[f"base{h}"] = round(float(fwd.mean()), 1) if len(fwd) else None
    res["years"] = round(len(v) / 244, 1)
    return res
