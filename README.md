# Fund Quiz Service

OpenDART 공시 문서를 기반으로 금융상품 이해도를 검증할 수 있는 퀴즈를 자동 생성하는 서비스입니다.
공시 데이터를 구조화하고, 핵심 내용을 문제 형태로 변환하여 사용자가 문서를 보다 쉽게 이해할 수 있도록 돕는 것을 목표로 합니다.

---

## Demo

* 서비스: [https://hyeonseo2.github.io/fund-quiz/](https://hyeonseo2.github.io/fund-quiz/)

<img width="962" height="881" alt="image" src="https://github.com/user-attachments/assets/5af32024-6309-46e0-983b-d8a4149b2ab5" />

---

## Overview

이 프로젝트는 금융상품 공시 문서를 **사용자의 이해를 확인할 수 있는 인터랙티브한 콘텐츠(퀴즈)**로 변환합니다.

주요 흐름은 다음과 같습니다:

```
공시 수집 → 문서 파싱 → 핵심 정보 추출 → 퀴즈 생성 → 사용자 풀이 및 채점
```

---

## Key Features

* **공시 데이터 기반 수집**

  * OpenDART API를 활용하여 최신 공시 문서를 수집

* **문서 구조화 및 파싱**

  * XML/HTML 형태의 공시 데이터를 정제하여 분석 가능한 형태로 변환

* **퀴즈 자동 생성**

  * 규칙 기반 + LLM을 활용하여 객관식 문제 생성

* **근거 기반 검증**

  * 퀴즈 결과와 함께 원문 공시 링크 제공


---

## Architecture

```
OpenDART API
    ↓
Document Parser (XML / HTML)
    ↓
Fact Extraction
    ↓
Quiz Generator (Rule + LLM)
    ↓
API / Static JSON
    ↓
Frontend (GitHub Pages)
```

---

## Tech Stack

| Category       | Stack                       |
| -------------- | --------------------------- |
| Backend        | FastAPI, SQLAlchemy         |
| Database       | SQLite / PostgreSQL         |
| Parsing        | lxml, BeautifulSoup         |
| LLM (Optional) | OpenAI, Gemini              |
| Infra          | Cloud Run, Redis (optional) |
| CI/CD          | GitHub Actions              |
| Frontend       | GitHub Pages                |

---

## Getting Started

### Install

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Access

* [http://localhost:8080](http://localhost:8080)
* [http://localhost:8080/health](http://localhost:8080/health)

---

## Environment Variables

| Variable               | Description       |
| ---------------------- | ----------------- |
| OPENDART_API_KEY       | OpenDART 인증 키     |
| OPENAI_API_KEY         | OpenAI API 키 (선택) |
| GEMINI_API_KEY         | Gemini API 키 (선택) |
| ADMIN_TOKEN            | 관리자 API 보호        |
| DATABASE_URL           | DB 연결 문자열         |
| AUTO_AI_GENERATE_COUNT | 자동 생성 퀴즈 수        |

---

## Deployment

### Cloud Run

```bash
gcloud builds submit --tag gcr.io/<PROJECT_ID>/fund-quiz-api

gcloud run deploy fund-quiz-api \
  --image gcr.io/<PROJECT_ID>/fund-quiz-api \
  --region asia-northeast3 \
  --allow-unauthenticated
```

---

## Static Mode (GitHub Pages)

GitHub Actions를 통해 데이터를 주기적으로 생성하고
정적 JSON 기반으로 서비스를 운영할 수 있습니다.

* 데이터: `docs/data/funds.json`
* 워크플로우: `.github/workflows/daily-sync.yml`

---

## API

### Public

* `GET /api/funds`
* `GET /api/funds/{fund_id}`
* `GET /api/funds/{fund_id}/quiz`
* `POST /api/funds/{fund_id}/quiz/generate`

### Admin

* `POST /admin/disclosures/backfill`
* `POST /admin/manager/sync`

---

## Notes

* 본 프로젝트는 금융상품 정보를 제공하며 투자 판단에 대한 책임은 사용자에게 있습니다.
* OpenDART 데이터 사용 정책을 준수해야 합니다.
