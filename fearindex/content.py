"""그날 숫자로 채우는 글. 같은 입력이면 항상 같은 글이 나온다."""
from .config import INDICATORS, band_of

NAMES = {i[0]: i[1] for i in INDICATORS}

MOOD = {
    "extreme_greed": ("동네가 온통 주식 얘기예요", "복순 여사도 계좌를 텄대요. 다들 들떠 있을 때일수록 한 박자 쉬어 가요."),
    "greed": ("슬슬 주식 얘기가 들려요", "반찬가게 앞에서도 종목 이름이 오가요. 분위기는 좋지만 욕심이 붙는 구간이에요."),
    "calm": ("동네가 조용해요", "주식 얘기도, 한숨도 없는 평범한 날이에요. 내 계좌 균형을 점검하기 좋아요."),
    "fear": ("한숨 소리가 늘었어요", "복순 여사가 시세를 실눈으로 봐요. 겁이 퍼지는 구간이라 서두르지 않는 게 좋아요."),
    "extreme_fear": ("주식 얘기만 나오면 손사래예요", "\"주식은 쳐다도 안 본다\"는 말이 나와요. 투매가 나오는 극단 구간이에요."),
}

LEVEL = [(80, "공포"), (60, "불안"), (40, "보통"), (20, "잔잔"), (-1, "아주 잔잔")]


def level(score):
    return next(name for lo, name in LEVEL if score > lo)


def fmt_value(key, v):
    unit = next(i[5] for i in INDICATORS if i[0] == key)
    if v != v:
        return "-"
    if unit == "억원":
        return f"{v:,.0f}억원"
    if unit == "배":
        return f"{v:.2f}배"
    if unit == "pt":
        return f"{v:.1f}pt"
    if unit == "%p":
        return f"{v:.2f}%p"
    return f"{v:+.1f}%" if key not in ("down_vol", "real_vol", "inverse", "fx_shock") else f"{v:.1f}%"


def drivers(scores: dict, n=3):
    have = {k: v for k, v in scores.items() if v == v}
    ranked = sorted(have, key=have.get, reverse=True)
    return [NAMES[k] for k in ranked[:n]], [NAMES[k] for k in ranked[-2:][::-1]]


def join(names):
    return ", ".join(names)


def _josa(word, a, b):
    """받침 유무에 맞는 조사."""
    c = ord(word[-1])
    has = 0xAC00 <= c <= 0xD7A3 and (c - 0xAC00) % 28 != 0
    return a if has else b


def daily(date, value, prev, scores, kospi, kospi_chg):
    b = band_of(value)
    up, down = drivers(scores)
    d = value - prev if prev is not None else 0
    move = ("전 거래일과 거의 같아요" if abs(d) < 0.5 else
            f"전 거래일보다 {abs(d):.0f}점 {'올라 겁이 커졌어요' if d > 0 else '내려 겁이 누그러졌어요'}")
    return [
        f"{date.month}월 {date.day}일 동네 아줌마 공포수치는 {value:.0f}점, '{b['name']}' 구간이에요. {move}.",
        f"이날 코스피는 {kospi:,.2f}로 마감해 하루 사이 {kospi_chg:+.2f}% 움직였어요.",
        f"수치를 끌어올린 쪽은 {join(up)}{_josa(up[-1], '이었고', '였고')}, "
        f"{join(down)}{_josa(down[-1], '은', '는')} 비교적 잔잔했어요.",
        MOOD[b["key"]][1],
    ]


def period(label, days, kospi_ret, score_change):
    """주간·월간 리포트 본문. days: [(date, value)], score_change: {key: 변화}."""
    vals = [v for _d, v in days]
    first, last = vals[0], vals[-1]
    avg = sum(vals) / len(vals)
    hi = max(days, key=lambda x: x[1])
    lo = min(days, key=lambda x: x[1])
    b = band_of(last)
    trend = ("거의 제자리였어요" if abs(last - first) < 2 else
             f"{abs(last - first):.0f}점 {'올랐어요(겁이 커짐)' if last > first else '내렸어요(겁이 줄어듦)'}")
    ch = {k: v for k, v in score_change.items() if v == v}
    rose = sorted(ch, key=ch.get, reverse=True)[:2]
    fell = sorted(ch, key=ch.get)[:2]
    ps = [
        f"{label} 공포수치는 {first:.0f}점에서 시작해 {last:.0f}점('{b['name']}')으로 끝났고, 그 사이 {trend}. "
        f"평균은 {avg:.0f}점이에요.",
        f"가장 겁이 컸던 날은 {hi[0].month}월 {hi[0].day}일({hi[1]:.0f}점), "
        f"가장 들떴던 날은 {lo[0].month}월 {lo[0].day}일({lo[1]:.0f}점)이에요.",
        f"같은 기간 코스피는 {kospi_ret:+.1f}% 움직였어요.",
    ]
    if rose and fell:
        ps.append(f"지표별로 보면 {join([NAMES[k] for k in rose])} 쪽에서 겁이 커졌고, "
                  f"{join([NAMES[k] for k in fell])} 쪽은 누그러졌어요.")
    ps.append("이 글은 공개 시장 자료를 자동으로 요약한 참고 자료이며 투자 권유가 아니에요.")
    return ps


FAQ = [
    ("동네 아줌마 공포수치가 뭔가요?",
     "코스피 시장에 겁이 얼마나 퍼져 있는지를 0부터 100까지 숫자 하나로 보여주는 지표예요. "
     "100에 가까울수록 겁(공포)이 크고, 0에 가까울수록 욕심(탐욕)이 큰 상태예요."),
    ("숫자가 높으면 좋은 건가요, 나쁜 건가요?",
     "좋고 나쁨이 아니라 분위기를 재는 온도계예요. 높으면 사람들이 겁먹고 파는 중이고, "
     "낮으면 너도나도 사려는 중이에요. 어느 쪽이든 극단일 때 내 판단을 한 번 더 돌아보는 용도로 써요."),
    ("어떻게 계산하나요?",
     "시장 지표 {n}개를 각각 '지난 4년 중 오늘이 몇 번째로 겁나는 날인가'(백분위)로 바꾼 뒤, "
     "정해 둔 비중으로 평균을 내요. 계산식과 비중은 '지수 설명' 페이지에 모두 공개해 두었어요."),
    ("미국 CNN 공포·탐욕 지수와 뭐가 다른가요?",
     "CNN 지수는 미국 시장 기준이고 0이 공포, 100이 탐욕이에요. 이 수치는 코스피 기준이고 이름 그대로 "
     "'공포'를 재기 때문에 방향이 반대예요(100이 공포). 신용융자·예탁금·반대매매 같은 국내 수급 자료를 써요."),
    ("언제 갱신되나요?",
     "평일 아침 8시, 낮 12시, 저녁 5시(한국 시간)에 자동으로 갱신돼요. 주말과 휴장일에는 마지막 거래일 값이 유지돼요."),
    ("겁이 클 때 사면 정말 오르나요?",
     "그렇다고 말할 수 없어요. 이 사이트는 같은 구간이었던 과거 날들의 이후 수익률을 그대로 보여주지만, "
     "표본이 적고 과거가 반복된다는 보장이 없어요. 예측이 아니라 참고 자료로만 봐 주세요."),
    ("자료는 어디서 가져오나요?",
     "네이버 금융(코스피·종목 시세, 투자자별 매매), 금융투자협회 통계(예탁금·신용융자·미수금·반대매매), "
     "미국 시카고옵션거래소(VIX) 등 공개된 자료를 써요."),
    ("투자 조언인가요?",
     "아니에요. 공개된 시장 자료를 요약한 참고용 콘텐츠이고, '복순 여사'는 가상의 캐릭터예요. "
     "투자 결정과 그 결과는 본인 책임이에요."),
]
