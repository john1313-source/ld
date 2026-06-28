# 미국 배당기업 실시간 트래커

116개 미국 배당기업의 현재 주가 기준 배당률을 정적 JSON으로 갱신하고, GitHub Pages에서 정렬과 필터가 가능한 표로 보여주는 프로젝트입니다.

## 구조

```text
data/
  dividends_seed.json   입력 데이터. 직접 수정하지 않습니다.
  dividends.json        갱신 스크립트가 생성할 출력 데이터입니다.
scripts/
  update_data.py        yfinance로 가격과 배당 정보를 조회해 dividends.json을 생성합니다.
web/
  index.html            정적 프론트엔드 진입점입니다.
  style.css             화면 스타일입니다.
  app.js                데이터 fetch, 정렬, 필터, 검색 로직입니다.
.github/workflows/
  update.yml            GitHub Actions cron 갱신 워크플로입니다.
requirements.txt        Python 의존성입니다.
```

## 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/update_data.py
```

프론트엔드는 빌드 없이 정적 서버에서 `web/index.html`을 열어 확인합니다.

## 데이터 해석

- `live_yield`: 현재 주가 기준 연 배당률입니다. 화면에서는 퍼센트로 표시합니다.
- `live_yield_diff`: `(live_yield - avg_yield_10y) / avg_yield_10y`입니다.
- `live_yield_diff`가 양수이면 현재 배당률이 10년 평균보다 높고, 음수이면 10년 평균보다 낮다는 뜻입니다.

## 배포

GitHub Actions가 정해진 시간에 `scripts/update_data.py`를 실행해 `data/dividends.json`을 갱신하고, GitHub Pages가 `web/`의 정적 파일을 서비스합니다.

### GitHub Actions

- 수동 실행: GitHub 저장소의 Actions 탭에서 `Update dividend data` 워크플로를 선택한 뒤 `Run workflow`를 누릅니다.
- 자동 실행: 평일 UTC 14:00, 17:00, 20:00에 실행합니다.
- 워크플로는 `data/dividends.json`에 변경이 있을 때 자동 커밋합니다.

### GitHub Pages

GitHub 저장소의 Settings > Pages에서 배포 소스를 현재 브랜치의 루트로 설정하면 `index.html`이 `web/index.html`로 이동시킵니다. 프론트엔드는 같은 저장소의 `data/dividends.json`을 읽습니다.
