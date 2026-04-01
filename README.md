# Fund Quiz Service

OpenDART 공시 문서를 바탕으로 금융상품 퀴즈를 자동 생성하는 API 서비스입니다.
문서 수집 → 텍스트 파싱 → 핵심 사실 추출 → 객관식 퀴즈 생성/채점 흐름을 하나의 백엔드로 제공합니다.

---

## ✨ What this project does

- **공시 기반 데이터 수집**
  - OpenDART `list.json`, `document.xml`를 통해 최신 공시를 수집합니다.
- **문서 파싱/정규화**
  - ZIP/XML/HTML 응답을 파싱해 문서 블록으로 저장합니다.
- **퀴즈 자동 생성**
  - 규칙 기반 + LLM(Gemini/OpenAI 키 연동) 방식으로 퀴즈를 생성합니다.
- **근거 중심 UX**
  - 퀴즈 결과에서 공시 링크로 바로 이동해 문서 원문을 확인할 수 있습니다.
- **운영 자동화 친화적 구조**
  - Cloud Run 배포, GitHub Actions 배치 수집, GitHub Pages 프론트 배포를 지원합니다.

---

## 🧱 Tech Stack

- **Backend**: FastAPI, SQLAlchemy, Pydantic
- **Storage**: SQLite (기본) / PostgreSQL(확장)
- **Queue/Infra**: Redis(옵션), Cloud Run
- **Parsing**: lxml, BeautifulSoup
- **LLM (optional)**: Gemini API, OpenAI API
- **CI/CD & Ops**: GitHub Actions, GitHub Pages

---

## 📦 Project Structure

```bash
app/
  api/                # public/admin API
  agents/             # fact 추출, quiz 생성/검증
  clients/            # OpenDART client
  core/               # settings, logging
  db/                 # model/session
  services/           # pipeline orchestration
  parsers/            # zip/xml/html parser
scripts/
tests/
.github/workflows/    # (추가) 배치 수집, pages 배포
```

---

## 🚀 Quick Start

### 1) Install

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

### 2) Run API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### 3) Open

- Local: `http://localhost:8080`
- Health: `http://localhost:8080/health`

---

## ⚙️ Environment Variables

핵심 변수들:

- `OPENDART_API_KEY` : OpenDART 인증키
- `GEMINI_API_KEY` : Gemini 퀴즈 생성용 (선택)
- `OPENAI_API_KEY` : OpenAI 연동용 (선택)
- `ADMIN_TOKEN` : admin API 보호용 토큰
- `DATABASE_URL` : DB 연결 문자열
- `AUTO_AI_GENERATE_COUNT` : 초기 자동 LLM 퀴즈 생성 개수 (기본 1)
- `CORS_ALLOW_ORIGINS` : 허용 Origin (예: `https://<username>.github.io`)

예시:

```env
OPENDART_API_KEY=...
ADMIN_TOKEN=...
GEMINI_API_KEY=...
DATABASE_URL=sqlite:///./fund_quiz.db
AUTO_AI_GENERATE_COUNT=1
CORS_ALLOW_ORIGINS=https://<username>.github.io
```

---

## 🌐 Deploy: Cloud Run

```bash
gcloud builds submit --tag gcr.io/<PROJECT_ID>/fund-quiz-api .

gcloud run deploy fund-quiz-api \
  --image gcr.io/<PROJECT_ID>/fund-quiz-api \
  --region asia-northeast3 \
  --allow-unauthenticated \
  --set-env-vars OPENDART_API_KEY=<KEY>,ADMIN_TOKEN=<TOKEN>,AUTO_AI_GENERATE_COUNT=1
```

---

## 📅 GitHub Actions: Daily Data Batch

이 저장소에는 매일 공시 데이터를 동기화하는 워크플로우가 포함됩니다.

워크플로우 파일: `.github/workflows/daily-sync.yml`

필요한 Repository Secrets:

- `API_BASE_URL` (예: `https://fund-quiz-api-xxxxx.run.app`)
- `ADMIN_TOKEN`
- `CORP_CODES` (쉼표 구분, 예: `00267526,00260453`)

동작:

- 스케줄 실행(UTC 기준)
- corp_code별 `/admin/disclosures/backfill` 호출
- 필요 시 수동 실행 가능 (`workflow_dispatch`)

---

## 🧩 GitHub Pages Frontend

정적 프론트는 `docs/` 폴더를 사용하며 GitHub Pages로 배포할 수 있습니다.

워크플로우 파일: `.github/workflows/pages.yml`

기능:

- GitHub Pages에서 API Base URL 입력
- 운용사/펀드 조회
- 퀴즈 생성/채점
- 결과에서 공시 링크 이동

설정 포인트:

1. GitHub Pages Source를 **GitHub Actions**로 선택
2. API 서버 `CORS_ALLOW_ORIGINS`에 Pages 도메인 추가

---

## 🔌 Public API (핵심)

- `GET /api/funds`
- `GET /api/funds/search?q=`
- `GET /api/funds/{fund_id}`
- `GET /api/funds/{fund_id}/quiz`
- `POST /api/funds/{fund_id}/quiz/generate`
- `POST /api/quiz-attempts`
- `GET /api/funds/{fund_id}/document-preview`

관리자 API (토큰 필요):

- `POST /admin/disclosures/backfill`
- `POST /admin/manager/sync`

---

## 🧪 Test

```bash
pytest -q
```

---

## 📄 License

If you plan to open-source this project, add a license file (`MIT`, `Apache-2.0`, etc.).
