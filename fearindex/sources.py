"""공개 출처에서 원자료를 받아 DataFrame으로 돌려준다. 실패하면 예외를 던진다."""
import io
import re
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
TIMEOUT = 30
_ROW = re.compile(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)')


def _get(url, **kw):
    r = requests.get(url, headers={**UA, **kw.pop("headers", {})}, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def parse_sise(text: str) -> pd.DataFrame:
    rows = [(m[0], *map(float, m[1:])) for m in _ROW.findall(text)]
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    return df.set_index("date")


def naver_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    """네이버 금융 일별 시세 (지수·종목·ETF 공통)."""
    url = ("https://api.finance.naver.com/siseJson.naver"
           f"?symbol={symbol}&requestType=1&startTime={start}&endTime={end}&timeframe=day")
    return parse_sise(_get(url).text)


def naver_stock_list() -> pd.DataFrame:
    """코스피 전 종목(ETF 포함)의 현재가·등락·거래대금."""
    out, page = [], 1
    while True:
        j = _get("https://m.stock.naver.com/api/stocks/marketValue/KOSPI"
                 f"?page={page}&pageSize=100").json()
        for s in j["stocks"]:
            out.append({
                "code": s["itemCode"], "name": s["stockName"], "type": s["stockEndType"],
                "close": float(s["closePriceRaw"]),
                "chg": float(s["compareToPreviousClosePriceRaw"]),
                "value": float(s["accumulatedTradingValueRaw"]),
            })
        if page * 100 >= j["totalCount"] or not j["stocks"]:
            break
        page += 1
    return pd.DataFrame(out)


def naver_closes(codes, start: str, end: str, workers: int = 8) -> pd.DataFrame:
    """여러 종목의 일별 종가를 날짜×종목 표로."""
    def one(code):
        try:
            return code, naver_daily(code, start, end)["close"]
        except Exception:
            return code, None
    with ThreadPoolExecutor(workers) as ex:
        got = dict(ex.map(one, codes))
    return pd.DataFrame({c: s for c, s in got.items() if s is not None and len(s)})


def naver_flows() -> dict:
    """오늘 코스피 투자자별 순매수(억원)."""
    j = _get("https://m.stock.naver.com/api/index/KOSPI/trend").json()
    num = lambda s: float(s.replace(",", "").replace("+", ""))
    return {"date": pd.to_datetime(j["bizdate"], format="%Y%m%d"),
            "personal": num(j["personalValue"]), "foreign": num(j["foreignValue"]),
            "institution": num(j["institutionalValue"])}


def naver_fx(pages: int = 3) -> pd.Series:
    """원/달러 환율 최근값 (네이버)."""
    rows = []
    for p in range(1, pages + 1):
        j = _get("https://api.stock.naver.com/marketindex/exchange/FX_USDKRW/prices"
                 f"?page={p}&pageSize=60").json()
        rows += [(x["localTradedAt"][:10], float(x["closePrice"].replace(",", ""))) for x in j]
    s = pd.Series(dict(rows), dtype=float)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def yahoo_close(symbol: str, rng: str = "10y") -> pd.Series:
    j = _get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
             f"?range={rng}&interval=1d").json()["chart"]["result"][0]
    s = pd.Series(j["indicators"]["quote"][0]["close"],
                  index=pd.to_datetime(j["timestamp"], unit="s").normalize(), dtype=float)
    return s.dropna().groupby(level=0).last()


def cboe_vix() -> pd.Series:
    r = _get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv")
    df = pd.read_csv(io.StringIO(r.text))
    return pd.Series(df["CLOSE"].values, index=pd.to_datetime(df["DATE"]), dtype=float)


def vix() -> pd.Series:
    try:
        return cboe_vix()
    except Exception:
        return yahoo_close("%5EVIX")


def kofia(start: str, end: str) -> pd.DataFrame:
    """금융투자협회: 예탁금·미수금·반대매매·신용융자 (백만원)."""
    def call(obj):
        r = requests.post(
            "https://freesis.kofia.or.kr/meta/getMetaDataList.do", headers=UA, timeout=TIMEOUT,
            json={"dmSearch": {"tmpV40": "1000000", "tmpV41": "1", "tmpV1": "D",
                               "tmpV45": start, "tmpV46": end, "OBJ_NM": obj}})
        r.raise_for_status()
        df = pd.DataFrame(r.json()["ds1"])
        df["date"] = pd.to_datetime(df["TMPV1"], format="%Y%m%d")
        return df.set_index("date").sort_index()
    fund, cred = call("STATSCU0100000060BO"), call("STATSCU0100000070BO")
    out = pd.DataFrame({"deposit": fund["TMPV2"], "misu": fund["TMPV5"],
                        "forced": fund["TMPV6"], "credit": cred["TMPV2"]}).astype(float)
    return out.dropna(how="all")


def ecos_spread(key: str, start: str, end: str) -> pd.Series:
    """한국은행 ECOS: 회사채(AA-, 3년) − 국고채(3년), %p. 무료 인증키가 필요하다."""
    def item(code):
        rows, first = [], 1
        while True:
            j = _get(f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/"
                     f"{first}/{first + 9999}/817Y002/D/{start}/{end}/{code}").json()
            if "StatisticSearch" not in j:
                raise RuntimeError(f"ECOS 응답 오류: {j}")
            part = j["StatisticSearch"]["row"]
            rows += part
            if len(rows) >= j["StatisticSearch"]["list_total_count"] or not part:
                break
            first += 10000
        s = pd.Series({r["TIME"]: float(r["DATA_VALUE"]) for r in rows if r["DATA_VALUE"]})
        s.index = pd.to_datetime(s.index, format="%Y%m%d")
        return s.sort_index()
    return (item("010300000") - item("010200000")).dropna()
