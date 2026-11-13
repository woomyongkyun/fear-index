import numpy as np
import pandas as pd

from fearindex import compute, content
from fearindex.config import INDICATORS, KEYS, MIN_WINDOW, band_of
from fearindex.sources import parse_sise


def test_percentile_of_highest_and_lowest():
    s = pd.Series(np.arange(MIN_WINDOW + 10, dtype=float))
    assert compute.percentile(s).iloc[-1] > 99.8          # 가장 큰 값
    s.iloc[-1] = -1
    assert compute.percentile(s).iloc[-1] < 0.2           # 가장 작은 값


def test_percentile_needs_enough_history():
    s = pd.Series(np.arange(MIN_WINDOW - 1, dtype=float))
    assert np.isnan(compute.percentile(s).iloc[-1])


def test_percentile_ties_get_midrank():
    s = pd.Series([5.0] * (MIN_WINDOW + 1))
    assert compute.percentile(s).iloc[-1] == 50


def test_direction_flips_score():
    n = MIN_WINDOW + 5
    ind = pd.DataFrame({k: np.arange(n, dtype=float) for k in KEYS})
    sc = compute.scores(ind).iloc[-1]
    for key, _n, _g, _w, direction, _u, _d in INDICATORS:
        assert (sc[key] > 99) if direction > 0 else (sc[key] < 1), key


def test_index_reweights_when_indicator_missing():
    sc = pd.DataFrame([{k: 80.0 for k in KEYS}])
    sc["spread"] = np.nan
    assert compute.index_value(sc).iloc[0] == 80.0


def test_index_is_weighted_average():
    sc = pd.DataFrame([{k: 0.0 for k in KEYS}])
    sc["mom_short"] = 100.0
    w = compute.weights()["mom_short"]
    assert abs(compute.index_value(sc).iloc[0] - round(w * 100, 1)) < 0.06


def test_index_blank_when_too_few_indicators():
    sc = pd.DataFrame([{k: np.nan for k in KEYS}])
    sc["vix"] = 50.0
    assert np.isnan(compute.index_value(sc).iloc[0])


def test_weights_sum_to_one():
    assert abs(compute.weights().sum() - 1) < 1e-9
    assert abs(compute.weights(KEYS[:5]).sum() - 1) < 1e-9


def test_bands():
    assert band_of(0)["key"] == "extreme_greed"
    assert band_of(25)["key"] == "greed"
    assert band_of(50)["key"] == "calm"
    assert band_of(74.9)["key"] == "fear"
    assert band_of(100)["key"] == "extreme_fear"


def test_indicators_on_falling_market_read_as_fear():
    n = MIN_WINDOW + 200
    rng = np.random.default_rng(0)
    close = 2500 * np.exp(np.cumsum(rng.normal(0.0004, 0.008, n)))
    close[-15:] = close[-16] * np.cumprod(np.full(15, 0.97))       # 마지막 15일 급락
    idx = pd.bdate_range("2020-01-01", periods=n)
    flat = np.full(n, 100.0)
    raw = pd.DataFrame({"close": close, "vix": 18.0, "fx": 1300.0, "deposit": flat, "credit": flat,
                        "misu": flat, "forced": flat, "adv": 400.0, "dec": 400.0, "nh": 20.0,
                        "nl": 20.0, "lev_val": 1.0, "inv_val": 1.0}, index=idx)
    sc = compute.scores(compute.indicators(raw)).iloc[-1]
    assert sc["mom_short"] > 95 and sc["mom_125"] > 95 and sc["down_vol"] > 95


def test_parse_sise():
    text = """[['날짜', '시가', '고가', '저가', '종가', '거래량', '외국인소진율'],
    ["20261102", 5637.77, 5910.83, 5616.5, 5859.08, 198130, 0.0],
    ["20261103", 5715.19, 5735.92, 5615.8, 5648.79, 207371, 0.0]]"""
    df = parse_sise(text)
    assert len(df) == 2 and df["close"].iloc[-1] == 5648.79
    assert df.index[0] == pd.Timestamp("2026-11-02")


def test_daily_text_mentions_value_and_band():
    scores = {k: 50.0 for k in KEYS}
    scores["vix"] = 95.0
    text = content.daily(pd.Timestamp("2026-11-13"), 69.1, 68.9, scores, 5290.53, -0.98)
    assert "69점" in text[0] and "공포" in text[0] and "거의 같아요" in text[0]
    assert "미국 VIX" in text[2]
