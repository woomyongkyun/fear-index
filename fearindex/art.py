"""SVG 그림: 임시 캐릭터, 게이지, 추이 그래프."""
import math

from .config import BANDS, STATIC, band_of

# 구간별 얼굴: (눈썹 기울기, 눈, 입, 볼 색, 추가 요소)
_FACES = {
    "extreme_greed": dict(
        brows='<path d="M70 86q12-10 24-4M126 82q12-6 24 4"/>',
        eyes='<path d="M72 104q10-14 20 0M128 104q10-14 20 0" fill="none"/>',
        mouth='<path d="M88 128q22 30 44 0z" fill="#8b2c3a"/>',
        extra='<path d="M30 60l4 10 10 4-10 4-4 10-4-10-10-4 10-4zM186 40l3 8 8 3-8 3-3 8-3-8-8-3 8-3z" '
              'fill="#e3b93c" stroke="none"/>'),
    "greed": dict(
        brows='<path d="M70 88q12-6 24 0M126 88q12-6 24 0"/>',
        eyes='<circle cx="82" cy="104" r="5" fill="#2b2433"/><circle cx="138" cy="104" r="5" fill="#2b2433"/>',
        mouth='<path d="M92 130q18 16 36 0" fill="none"/>',
        extra='<path d="M184 62v-18l12-3v16" fill="none"/><circle cx="180" cy="62" r="4" fill="#34406b"/>'
              '<circle cx="192" cy="57" r="4" fill="#34406b"/>'),
    "calm": dict(
        brows='<path d="M70 90h24M126 90h24"/>',
        eyes='<circle cx="82" cy="104" r="5" fill="#2b2433"/><circle cx="138" cy="104" r="5" fill="#2b2433"/>',
        mouth='<path d="M96 134h28" fill="none"/>',
        extra=''),
    "fear": dict(
        brows='<path d="M70 84q12 2 24 8M126 92q12-6 24-8"/>',
        eyes='<path d="M74 106h16M130 106h16" fill="none"/>',
        mouth='<path d="M94 138q16-10 32 0" fill="none"/>',
        extra='<path d="M168 84q8 14 0 20-8-6 0-20z" fill="#7cc4ea"/>'),
    "extreme_fear": dict(
        brows='<path d="M68 80q12 2 26 12M126 92q14-10 26-12"/>',
        eyes='<circle cx="82" cy="106" r="9" fill="#fff"/><circle cx="82" cy="106" r="3" fill="#2b2433"/>'
             '<circle cx="138" cy="106" r="9" fill="#fff"/><circle cx="138" cy="106" r="3" fill="#2b2433"/>',
        mouth='<ellipse cx="110" cy="140" rx="10" ry="14" fill="#8b2c3a"/>',
        extra='<path d="M36 92l-14-6M34 108H18M186 92l14-6M188 108h16" fill="none"/>'),
}


def character_svg(key: str, size: int = 220) -> str:
    """이미지가 오기 전까지 쓰는 임시 캐릭터 (선캡, 꽃무늬 조끼, 장바구니)."""
    f = _FACES[key]
    return f'''<svg viewBox="0 0 220 240" width="{size}" height="{size}" role="img" aria-label="복순 여사" xmlns="http://www.w3.org/2000/svg">
<g stroke="#2b2433" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">
<path d="M52 236q-6-70 58-72 64 2 58 72z" fill="#f4ecdc"/>
<path d="M62 236q-4-56 22-68l8 68zM158 236q4-56-22-68l-8 68z" fill="#a2466e"/>
<g fill="#e3b93c" stroke="none"><circle cx="74" cy="196" r="5"/><circle cx="82" cy="222" r="5"/><circle cx="146" cy="196" r="5"/><circle cx="138" cy="222" r="5"/></g>
<path d="M170 196h34l-5 38h-24z" fill="#d9a56a"/><path d="M178 196q9-22 18 0" fill="none"/>
<path d="M184 196l-4-34M192 196l6-30" stroke="#5c9a45" stroke-width="6" fill="none"/>
<circle cx="52" cy="78" r="17" fill="#6d4a78"/><circle cx="168" cy="78" r="17" fill="#6d4a78"/>
<circle cx="44" cy="106" r="15" fill="#6d4a78"/><circle cx="176" cy="106" r="15" fill="#6d4a78"/>
<circle cx="110" cy="108" r="62" fill="#f6c9a8"/>
<circle cx="70" cy="124" r="10" fill="#f09a8c" stroke="none" opacity=".7"/><circle cx="150" cy="124" r="10" fill="#f09a8c" stroke="none" opacity=".7"/>
<circle cx="64" cy="112" r="2" fill="#2b2433" stroke="none"/>
<path d="M50 74q60-52 120 0z" fill="#6d4a78"/>
<path d="M30 74q80-34 160 0-80-14-160 0z" fill="#8fbf5a"/>
<path d="M54 68q56-44 112 0" fill="#a9d374"/>
{f["brows"]}{f["eyes"]}{f["mouth"]}{f["extra"]}
</g></svg>'''


def character_html(key: str, root: str, size: int = 200) -> str:
    """사용자가 넣은 PNG가 있으면 그것을, 없으면 임시 SVG를 쓴다."""
    if (STATIC / "character" / f"{key}.png").exists():
        return (f'<img src="{root}static/character/{key}.png" width="{size}" height="{size}" '
                f'alt="복순 여사 — {band_name(key)}" loading="lazy">')
    return character_svg(key, size)


def band_name(key):
    return next(b[3] for b in BANDS if b[2] == key)


def _pt(cx, cy, r, value):
    a = math.pi * (1 - value / 100)
    return cx + r * math.cos(a), cy - r * math.sin(a)


def gauge_svg(value: float) -> str:
    cx, cy, r = 160, 160, 130
    arcs = []
    for lo, hi, _k, name, color in BANDS:
        hi = min(hi, 100)
        x1, y1 = _pt(cx, cy, r, lo + 0.6)
        x2, y2 = _pt(cx, cy, r, hi - 0.6)
        arcs.append(f'<path d="M{x1:.1f} {y1:.1f}A{r} {r} 0 0 1 {x2:.1f} {y2:.1f}" stroke="{color}"/>')
        mid = (lo + hi) / 2
        lx, ly = _pt(cx, cy, r + 18, mid)
        anchor = "end" if mid < 40 else "start" if mid > 60 else "middle"
        arcs.append(f'<text x="{lx:.1f}" y="{ly - (8 if anchor == "middle" else 0):.1f}" class="gl" '
                    f'text-anchor="{anchor}">{name}</text>')
    nx, ny = _pt(cx, cy, r - 30, value)
    b = band_of(value)
    return f'''<svg viewBox="-40 -14 400 200" class="gauge" role="img" aria-label="공포수치 {value:.0f}, {b["name"]}" xmlns="http://www.w3.org/2000/svg">
<g fill="none" stroke-width="22" stroke-linecap="butt">{"".join(arcs)}</g>
<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" class="needle"/><circle cx="{cx}" cy="{cy}" r="9" class="hub"/>
<text x="{cx}" y="{cy - 34}" class="gv" fill="{b["color"]}">{value:.0f}</text>
</svg>'''


def timeline_svg(points, w=720, h=240) -> str:
    """points: [(날짜 문자열, 값)]. 위쪽이 공포."""
    if len(points) < 2:
        return ""
    pl, pr, pt, pb = 34, 10, 12, 26
    n = len(points)
    X = lambda i: pl + (w - pl - pr) * i / (n - 1)
    Y = lambda v: pt + (h - pt - pb) * (1 - v / 100)
    bands = "".join(
        f'<rect x="{pl}" y="{Y(min(hi, 100)):.1f}" width="{w - pl - pr}" '
        f'height="{Y(lo) - Y(min(hi, 100)):.1f}" fill="{c}" opacity=".13"/>'
        for lo, hi, _k, _n, c in BANDS)
    grid = "".join(f'<text x="{pl - 6}" y="{Y(v) + 4:.1f}" class="ax" text-anchor="end">{v}</text>'
                   f'<line x1="{pl}" x2="{w - pr}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="gr"/>'
                   for v in (25, 50, 75))
    months, seen = "", None
    for i, (d, _v) in enumerate(points):
        m = d[:7]
        if m != seen:
            if seen is not None:
                months += f'<text x="{X(i):.1f}" y="{h - 8}" class="ax">{int(d[5:7])}월</text>'
            seen = m
    line = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, (_d, v) in enumerate(points))
    lx, ly = X(n - 1), Y(points[-1][1])
    return f'''<svg viewBox="0 0 {w} {h}" class="timeline" role="img" aria-label="공포수치 추이 그래프" xmlns="http://www.w3.org/2000/svg">
{bands}{grid}{months}<polyline points="{line}" class="tl"/><circle cx="{lx:.1f}" cy="{ly:.1f}" r="5" class="dot"/></svg>'''
