# 동네 아줌마 공포수치

코스피 투자 심리를 0(욕심)~100(겁)으로 보여주는 정적 사이트. 평일 08시·12시·17시(KST)에 GitHub Actions가
자료 수집 → 지수 계산 → 글 생성 → 배포를 자동으로 한다.

## 명령

```bash
python run.py all        # 최신 자료로 갱신하고 dist/ 에 사이트 생성
python run.py build      # 저장된 자료로 사이트만 다시 생성
python run.py backfill   # 과거 자료를 처음부터 다시 받음 (수 분)
python -m pytest -q      # 테스트
```

## 구조

| 위치 | 역할 |
|---|---|
| `fearindex/sources.py` | 출처별 수집 (네이버 금융, 금융투자협회, CBOE, 야후, 한국은행) |
| `fearindex/pipeline.py` | 수집 → `data/` 저장 → 지수 계산. 수집 실패 시 직전 값 사용 |
| `fearindex/compute.py` | 지표, 백분위, 가중 평균, 닮은 날, 구간 통계 |
| `fearindex/content.py` | 일간·주간·월간 글과 FAQ 문구 |
| `fearindex/art.py` | 게이지·추이 그래프·임시 캐릭터 SVG |
| `fearindex/build.py`, `templates/`, `static/` | 사이트 생성 |
| `site.json` | 사이트 이름, 주소, 광고·통계·검색 등록 코드 |
| `.github/workflows/update.yml` | 자동 실행 일정 |

## 설정 (`site.json`)

| 항목 | 넣는 값 |
|---|---|
| `base_url` | 사이트 주소 (예: `https://아이디.github.io/저장소`). 넣으면 sitemap.xml·RSS가 생긴다 |
| `domain` | 자체 도메인을 쓸 때만 (예: `example.kr`) |
| `contact_email` | 문의 메일 |
| `ga_id` | 구글 애널리틱스 측정 ID (`G-…`) |
| `adsense` | 애드센스 게시자 ID (`ca-pub-…`). 넣으면 광고 자리와 ads.txt가 생긴다 |
| `google_verify`, `naver_verify` | 검색 등록 인증 코드 |

## 캐릭터 이미지

`static/character/` 에 `extreme_greed.png`, `greed.png`, `calm.png`, `fear.png`, `extreme_fear.png` 를
넣으면 임시 그림 대신 쓰인다. 규격은 `캐릭터 디자인.md` 참고.

## 신용스프레드 지표 켜기 (선택)

한국은행 ECOS(https://ecos.bok.or.kr/api/)에서 무료 인증키를 받아 GitHub 저장소의
Settings → Secrets and variables → Actions 에 `ECOS_API_KEY` 로 등록하면 다음 갱신부터 지표가 15개가 된다.
