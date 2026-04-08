# TradingAgents Web Interface

TradingAgents 코어를 감싸는 웹 인터페이스입니다. 기존 코어를 **단 한 줄도 수정하지 않고** FastAPI + Next.js로 구현되었습니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  Next.js Frontend (Port 3000)                               │
│  - 한국어 UI                                                │
│  - 실시간 진행률 표시 (SSE)                                  │
│  - 반응형 디자인                                            │
└─────────────────────────┬───────────────────────────────────┘
                          │ SSE (Server-Sent Events)
┌─────────────────────────▼───────────────────────────────────┐
│  FastAPI Backend (Port 8000)                                │
│  - TradingAgentsGraph 래퍼                                  │
│  - 한국어 번역 레이어                                        │
│  - 진행 상태 추적                                           │
└─────────────────────────┬───────────────────────────────────┘
                          │ Python Import (Zero Modification)
┌─────────────────────────▼───────────────────────────────────┐
│  TradingAgents Core (Locked)                                │
│  - tradingagents/graph/trading_graph.py                     │
│  - tradingagents/agents/                                    │
│  - tradingagents/dataflows/                                 │
└─────────────────────────────────────────────────────────────┘
```

## 한국어 지원

이미 TradingAgents 코어에 한국어 템플릿이 내장되어 있습니다:

```python
config = DEFAULT_CONFIG.copy()
config["language"] = "한국어"  # 모든 보고서 한국어 출력
```

## 빠른 시작

### 1. 환경 변수 설정

```bash
# .env 파일 생성
export OPENAI_API_KEY=your_api_key_here
```

### 2. Docker로 실행 (권장)

```bash
# 한 번에 모든 서비스 실행
docker-compose up --build

# 접속
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### 3. 개발 모드로 실행

```bash
# Terminal 1: Backend
python -m web_api.main

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

## API 엔드포인트

### 분석 실행 (SSE 스트리밍)
```
GET /analyze/{ticker}?date=YYYY-MM-DD&analysts=market,social,news,fundamentals
```

실시간으로 진행 상태를 스트리밍하고 최종 결과를 반환합니다.

### 상태 확인
```
GET /health
```

### 분석가 목록
```
GET /analysts
```

### 결정 유형
```
GET /decisions
```

## 디렉토리 구조

```
tradingagents-core/
├── tradingagents/          # 🔒 코어 (수정 금지)
│   ├── graph/
│   ├── agents/
│   └── ...
├── web_api/                # FastAPI 래퍼
│   ├── main.py            # 메인 API
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # Next.js
│   ├── app/
│   ├── components/
│   └── Dockerfile
└── docker-compose.yml      # 통합 배포
```

## 기능

- ✅ 실시간 진행률 표시 (12개 에이전트 상태 추적)
- ✅ 한국어 보고서 생성
- ✅ 5단계 투자 결정 (매수/비중확대/보유/비중축소/매도)
- ✅ 4가지 분석 유형 선택 (시장/소셜/뉴스/펀더멘털)
- ✅ 토론 내용 상세 조회
- ✅ 반응형 모바일 지원

## 코어 수정 없음 확인

```bash
# tradingagents/ 디렉토리의 변경사항 확인
git status tradingagents/
# 변경사항 없음 (No changes)
```

## 배포

### Railway (권장)

```bash
railway login
railway init
railway up
```

### 수동 배포

```bash
# Build
docker-compose build

# Push to registry
docker tag tradingagents-api your-registry/tradingagents-api
docker push your-registry/tradingagents-api
```

## 라이선스

TradingAgents 코어와 동일한 라이선스를 따릅니다.
