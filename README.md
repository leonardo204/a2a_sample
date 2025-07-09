# A2A Multi-Agent System Sample

a2a-sdk를 사용한 간단한 멀티 에이전트 시스템 예제입니다.

## 프로젝트 구조

```
a2a-sample/
├── src/                    # 소스 코드
│   ├── main_agent.py      # 메인 오케스트레이터 에이전트
│   ├── weather_agent.py   # 날씨 서비스 에이전트
│   ├── tv_agent.py        # TV 제어 에이전트
│   ├── llm_client.py      # Azure OpenAI LLM 클라이언트
│   └── prompt_loader.py   # YAML 프롬프트 로더
├── prompt/                # 에이전트별 프롬프트 파일
│   ├── main_agent/       # 메인 에이전트 프롬프트
│   ├── weather_agent/    # 날씨 에이전트 프롬프트  
│   └── tv_agent/         # TV 에이전트 프롬프트
├── main.py               # 시스템 실행 스크립트
├── client.py            # 대화형 테스트 클라이언트
└── pyproject.toml       # 프로젝트 설정 및 의존성
```

## 목적

- **메인 에이전트**: 사용자 의도를 분류하고 적절한 서비스 에이전트로 요청을 라우팅
- **날씨 에이전트**: 날씨 관련 문의에 대한 응답 (테스트용, 실제로는 항상 맑음 반환)
- **TV 에이전트**: TV 제어 관련 요청 처리 (테스트용, 항상 성공 응답)

## 사용한 라이브러리

### 주요 의존성
- **a2a-sdk[sqlite]** >= 0.2.0 - A2A 프로토콜 SDK
- **uvicorn[standard]** >= 0.18.0 - ASGI 서버
- **openai** >= 1.0.0 - Azure OpenAI API 클라이언트
- **pydantic** >= 2.0.0 - 데이터 검증
- **pyyaml** >= 6.0.0 - YAML 파일 처리

### 기타 의존성
- **requests** >= 2.28.0 - HTTP 클라이언트
- **asyncio-mqtt** >= 0.13.0 - 비동기 MQTT
- **uvloop** >= 0.17.0 - 고성능 이벤트 루프
- **loguru** >= 0.7.0 - 로깅
- **python-dotenv** >= 1.0.0 - 환경변수 관리
- **rich** >= 14.0.0 - 터미널 UI

## 환경 설정

1. `.env` 파일 생성:
```bash
AZURE_OPENAI_ENDPOINT=your-endpoint
AZURE_OPENAI_API_KEY=your-api-key  
AZURE_OPENAI_DEPLOYMENT_NAME=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

2. 의존성 설치 (uv 사용):
```bash
uv sync
```

## 실행 방법

### 1. 시스템 시작
```bash
uv run main.py
```
- 3개의 에이전트가 각각 다른 포트에서 실행됩니다:
  - Main Agent: 포트 18000 (오케스트레이터)
  - Weather Agent: 포트 18001
  - TV Agent: 포트 18002

### 2. 대화형 클라이언트 실행
```bash
uv run client.py
```
- 메뉴 방식의 사용자 친화적 테스트 인터페이스
- 각 에이전트별 개별 테스트 가능

### 3. curl로 직접 테스트
```bash
# 날씨 문의
curl -X POST http://localhost:18000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-123",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "서울 날씨 어때?"}],
        "messageId": "msg-123"
      }
    }
  }'

# TV 제어
curl -X POST http://localhost:18000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-456",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "TV 볼륨 올려줘"}],
        "messageId": "msg-456"
      }
    }
  }'
```

## 테스트 방법

### 지원하는 요청 유형

1. **날씨 문의**
   - "오늘 날씨 어때?", "서울 날씨", "비 와?" 등
   - Weather Agent (포트 18001)로 라우팅

2. **TV 제어**
   - "TV 켜줘", "볼륨 올려", "채널 바꿔" 등
   - TV Agent (포트 18002)로 라우팅

3. **일반 대화**
   - "안녕하세요", "고마워요", "뭘 할 수 있어?" 등
   - Main Agent에서 직접 처리

### Agent Card 확인
```bash
# 각 에이전트의 정보 확인
curl -s http://localhost:18000/.well-known/agent.json | jq
curl -s http://localhost:18001/.well-known/agent.json | jq  
curl -s http://localhost:18002/.well-known/agent.json | jq
```

## 참고사항

- 이 프로젝트는 a2a-sdk 사용법을 보여주는 샘플입니다
- 날씨 및 TV 제어는 실제 기능 구현이 아닌 테스트용 시뮬레이션입니다
- Azure OpenAI 설정이 필요합니다 (GPT 모델 사용) 