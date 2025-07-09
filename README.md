# A2A Multi-Agent System

A2A 프로토콜 기반의 간단한 멀티 에이전트 시스템입니다. Main Agent가 orchestration과 registry 기능을 담당하며, 여러 Service Agent들과 협력하여 다양한 서비스를 제공합니다.

## 🏗️ 시스템 구조

```
📦 Main Agent (포트 18000)
├── 🧠 Orchestration (요청 분석 및 라우팅)
│   ├── 🔍 Intent/Entity 분석
│   ├── 🎯 Multi-domain 요청 처리
│   └── 🔄 Self-invocation 방지 메커니즘
├── 📋 Registry (Service Agent 등록/발견)
│   ├── 🌐 HTTP API (/api/registry/*)
│   └── 🔄 재시도 메커니즘
└── 💬 Chit-chat (일반 대화)

📦 Weather Agent (포트 18001) → HTTP 등록
├── 🌤️ weather_info 스킬
├── 🔄 재시도 메커니즘
└── 📡 Main Agent 자동 등록

📦 TV Agent (포트 18002) → HTTP 등록  
├── 📺 tv_control 스킬
├── 🔄 재시도 메커니즘
└── 📡 Main Agent 자동 등록
```

### 🔧 **중요한 설계 포인트**
- **Main Agent의 `orchestration` 스킬**: 자기 자신을 호출하지 않도록 스킬 필터링 적용
- **HTTP 기반 등록**: 프로세스 간 Agent 발견 및 통신 안정성 보장
- **재시도 메커니즘**: 네트워크 오류나 시작 순서 문제 해결

## 🎯 주요 기능 및 특징

### 🧠 **Main Agent (Orchestrator)**
- **Intent/Entity 추출**: 사용자 요청을 분석하여 의도와 엔티티 추출
- **Agent Registry**: Service Agent 등록 및 발견 관리  
- **Request Routing**: 적절한 Service Agent로 요청 라우팅
- **Response Aggregation**: 여러 Agent의 응답을 집약하여 통합 응답 생성
- **Chit-chat**: 일반적인 대화 및 시스템 정보 제공
- **Self-invocation 방지**: 복합 요청 시 무한 루프 방지 메커니즘

### 🌤️ **Weather Agent**
- **날씨 정보 제공**: 지역별 현재 날씨 정보 조회
- **날씨 예보**: 미래 날씨 예측 (테스트용 고정 응답)
- **지역/시간 추출**: 사용자 입력에서 위치와 시간 정보 추출

### 📺 **TV Agent**
- **TV 제어**: 전원, 볼륨, 채널, 입력 소스 제어
- **TV 설정**: 설정 변경 및 관리 (테스트용 시뮬레이션)
- **명령 분석**: 자연어 TV 제어 명령 해석

### 🔧 **시스템 특징**
- **HTTP API 기반 등록**: 프로세스 간 Agent 발견 및 통신 안정성
- **재시도 메커니즘**: 네트워크 오류나 시작 순서 문제 자동 해결
- **복합 도메인 처리**: 여러 Service Agent 조합으로 통합 응답 생성
- **실시간 Agent 발견**: 동적 Agent 등록 및 스킬 기반 라우팅

## 🔧 기술 스택

- **Python 3.11+**
- **A2A SDK**: Agent-to-Agent 프로토콜 구현
- **FastAPI/Starlette**: HTTP 서버 및 API
- **Azure OpenAI**: LLM 기반 의도 분석 및 응답 생성
- **httpx**: 비동기 HTTP 클라이언트
- **uv**: Python 패키지 매니저

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd a2a-sample

# uv를 사용한 의존성 설치
uv sync
```

### 2. 환경변수 설정

`.env` 파일을 생성하고 Azure OpenAI 설정을 추가하세요:

```env
AZURE_OPENAI_ENDPOINT=your_endpoint
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-05-01-preview
```

### 3. 시스템 실행

```bash
# 모든 Agent 실행 (멀티프로세스)
python main.py
```

실행 후 다음과 같은 서비스가 시작됩니다:
- **Main Agent**: http://localhost:18000
- **Weather Agent**: http://localhost:18001  
- **TV Agent**: http://localhost:18002

### 4. 클라이언트 테스트

```bash
# 대화형 클라이언트 실행
uv run client.py
```

## 📖 사용 예시

### 1. 날씨 문의
```
사용자: "오늘 서울 날씨 어때?"
시스템: 🌤️ 서울의 오늘 날씨는 맑음이고, 기온은 22도, 습도는 60% 입니다.
```

### 2. TV 제어
```
사용자: "TV 볼륨 올려줘"
시스템: 🔊 볼륨을 올렸습니다.
```

### 3. 복합 요청 (Main Agent 오케스트레이션)
```
사용자: "오늘같은 날씨에 어울리는 채널로 변경해줘"
시스템: 🌤️ 날씨 정보: 서울의 오늘 날씨는 맑음이고 기온은 22도입니다.
        📺 TV 제어: 채널을 날씨에 어울리는 7번 채널로 변경했습니다.
        💡 통합 제안: 맑은 날씨에 어울리는 스포츠 채널로 설정했습니다.
```

### 4. 일반 대화 (Chit-chat)
```
사용자: "안녕하세요"
시스템: 안녕하세요! 저는 A2A 멀티 에이전트 시스템입니다. 
        날씨 정보나 TV 제어를 도와드릴 수 있습니다.
```

## 🧪 테스트 기능

### 복합 도메인 테스트
`client.py`의 **메뉴 4번**을 통해 복합 도메인 처리 성능을 종합적으로 테스트할 수 있습니다:

```bash
python client.py
# 4. 🌈 복합 도메인 테스트 선택
```

**테스트 시나리오**:
- "오늘같은 날씨에 어울리는 채널로 변경해줘"
- "날씨에 맞는 볼륨으로 조절해줘"
- "오늘 날씨에 따라 적절한 방송으로 해줘"
- "날씨 보고 TV 설정 바꿔줘"

**자동 평가 항목**:
- ✅ 날씨 정보 포함 여부
- ✅ TV 제어 정보 포함 여부  
- ✅ 통합 오케스트레이션 응답 품질
- ✅ 전체 복합 응답 완성도

## 🛠️ API 참조

### Main Agent API

#### Agent Card 조회
```bash
curl -s http://localhost:18000/.well-known/agent.json | jq
```

#### 메시지 전송 (JSON-RPC)
```bash
curl -X POST http://localhost:18000/ \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-123", 
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "오늘 날씨 어때?"}],
        "messageId": "msg-123"
      }
    }
  }'
```

#### Registry API

**등록된 Agent 목록 조회**
```bash
curl -s http://localhost:18000/api/registry/agents | jq
```

**Service Agent 등록** (내부용)
```bash
curl -X POST http://localhost:18000/api/registry/register \
  -H 'Content-Type: application/json' \
  -d '{ "name": "Test Agent", "url": "http://localhost:8001", ... }'
```

## 📁 프로젝트 구조

```
a2a-sample/
├── main.py                 # 시스템 런처 (멀티프로세스)
├── client.py              # 대화형 테스트 클라이언트
├── kill_ps.sh             # 프로세스 종료 스크립트
├── src/
│   ├── main_agent.py      # Main Agent (Orchestration + Registry)
│   ├── weather_agent.py   # Weather Service Agent
│   ├── tv_agent.py        # TV Control Service Agent
│   ├── llm_client.py      # Azure OpenAI 클라이언트
│   ├── prompt_loader.py   # YAML 프롬프트 로더
│   └── query_analyzer.py  # Intent/Entity 분석기
├── prompt/                # LLM 프롬프트 템플릿
│   ├── main_agent/
│   │   ├── intent_classification.yaml
│   │   ├── entity_extraction.yaml
│   │   ├── orchestration.yaml
│   │   └── chitchat.yaml
│   ├── weather_agent/
│   │   └── weather_response.yaml
│   └── tv_agent/
│       └── tv_control.yaml
├── pyproject.toml         # 프로젝트 설정
├── uv.lock               # 의존성 잠금 파일
└── README.md             # 이 파일
```

### 🔧 유틸리티 스크립트

**프로세스 종료**
```bash
# 모든 Agent 프로세스 종료
./kill_ps.sh

# 또는 직접 실행
chmod +x kill_ps.sh
./kill_ps.sh
```


## 🤔 문제 해결

### 복합 도메인 요청 관련 문제

#### 무한 루프 또는 응답 지연
**증상**: Main Agent가 복합 요청 시 응답이 매우 느리거나 멈춤
**해결**:
1. 시스템 재시작: `python main.py`
2. 복합 도메인 테스트로 동작 확인:
   ```bash
   python client.py
   # 메뉴 4번 선택: 복합 도메인 테스트
   ```

#### 복합 응답 품질 문제
**증상**: 날씨+TV 조합 요청 시 한쪽 정보만 포함되거나 통합이 안 됨
**해결**:
1. 각 Service Agent가 정상 등록되었는지 확인
2. Agent 연결 상태 확인:
   ```bash
   python client.py
   # 메뉴 1번 선택: 모든 Agent Card 보기
   ```

### Agent 등록 문제
1. Main Agent가 완전히 시작되었는지 확인
2. Service Agent 로그에서 등록 재시도 메시지 확인
3. 포트 충돌이 없는지 확인 (18000, 18001, 18002)

### LLM 응답 오류
1. `.env` 파일의 Azure OpenAI 설정 확인
2. API 키와 엔드포인트가 유효한지 확인
3. 프롬프트 파일이 올바르게 로드되는지 확인

### 네트워크 연결 문제
1. 방화벽 설정 확인
2. 각 Agent의 health check 엔드포인트 테스트:
   ```bash
   curl http://localhost:18000/.well-known/agent.json
   curl http://localhost:18001/.well-known/agent.json
   curl http://localhost:18002/.well-known/agent.json
   ```

## 📞 참고자료

- [A2A 프로토콜 공식 문서](https://github.com/a2aproject/a2a-python)
- [Azure OpenAI API 문서](https://docs.microsoft.com/en-us/azure/cognitive-services/openai/)
- [FastAPI 문서](https://fastapi.tiangolo.com/)

## 🤝 기여하기

1. 이슈를 생성하여 개선사항 제안
2. Fork 후 feature 브랜치 생성
3. 변경사항 구현 및 테스트
4. Pull Request 제출

---

**Made with ❤️ using A2A Protocol** 