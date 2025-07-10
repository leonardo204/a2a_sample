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
├── 🌤️ weather 스킬 (통합)
├── 🔄 재시도 메커니즘
└── 📡 Main Agent 자동 등록

📦 TV Agent (포트 18002) → HTTP 등록  
├── 📺 tv 스킬 (통합)
├── 🔄 재시도 메커니즘
└── 📡 Main Agent 자동 등록

📦 Context Manager (Main Agent 내장)
├── 🗂️ Agent Card 기반 맥락 추출
├── 🔄 세션 기반 컨텍스트 관리
└── 🎯 동적 프롬프트 생성
```

### 🔧 **중요한 설계 포인트**
- **Main Agent의 `orchestration` 스킬**: 자기 자신을 호출하지 않도록 스킬 필터링 적용
- **HTTP 기반 등록**: 프로세스 간 Agent 발견 및 통신 안정성 보장
- **재시도 메커니즘**: 네트워크 오류나 시작 순서 문제 해결

## 🎯 주요 기능 및 특징

### 🧠 **Main Agent (Orchestrator)**
- **Agent Card 기반 동적 분석**: 등록된 Agent 정보를 실시간으로 반영한 LLM 프롬프트 생성
- **Intent/Entity 추출**: 사용자 요청을 분석하여 의도와 엔티티 추출
- **Agent Registry**: Service Agent 등록 및 발견 관리  
- **Request Routing**: 적절한 Service Agent로 요청 라우팅
- **Context Management**: 세션 기반 맥락 관리 및 Agent 간 정보 전달
- **Response Aggregation**: 여러 Agent의 응답을 집약하여 통합 응답 생성
- **Chit-chat**: 일반적인 대화 및 시스템 정보 제공
- **Self-invocation 방지**: 복합 요청 시 무한 루프 방지 메커니즘

### 🌤️ **Weather Agent**
- **weather 스킬 (통합)**: 날씨 정보 제공, 예보, 지역/시간 분석 등 모든 날씨 관련 기능 통합
- **Agent Card 기반 엔티티**: location, time 등 실제 처리 가능한 엔티티만 노출
- **맥락 연동**: Context Manager와 연계하여 다른 Agent에 날씨 정보 제공

### 📺 **TV Agent**  
- **tv 스킬 (통합)**: TV 제어, 설정, 명령 분석 등 모든 TV 관련 기능 통합
- **Agent Card 기반 엔티티**: volume_level, channel, power_state 등 실제 처리 가능한 엔티티만 노출
- **맥락 연동**: Context Manager를 통해 다른 Agent의 정보를 반영한 TV 제어

### 🔧 **시스템 특징**
- **HTTP API 기반 등록**: 프로세스 간 Agent 발견 및 통신 안정성
- **재시도 메커니즘**: 네트워크 오류나 시작 순서 문제 자동 해결
- **복합 도메인 처리**: 여러 Service Agent 조합으로 통합 응답 생성
- **실시간 Agent 발견**: 동적 Agent 등록 및 스킬 기반 라우팅

## 🧠 Agent Card 기반 지능형 시스템

본 시스템의 핵심은 **Agent Card**를 기반으로 모든 의사결정이 이루어진다는 점입니다. 이는 A2A 프로토콜의 철학을 충실히 구현한 것으로, 처음 보는 사용자도 쉽게 이해할 수 있도록 설계되었습니다.

### 🎯 **동적 프롬프트 생성**
시스템은 등록된 Agent들의 **Agent Card 정보**를 실시간으로 분석하여 LLM 프롬프트를 자동 생성합니다:

```yaml
# Weather Agent의 Agent Card에서 자동 추출
entity_types:
  - name: "location"
    examples: ["서울", "부산", "대구"]
  - name: "time"  
    examples: ["오늘", "내일", "지금"]

# TV Agent의 Agent Card에서 자동 추출
entity_types:
  - name: "volume_level"
    examples: ["5", "10", "15", "20", "최대"]
  - name: "channel"
    examples: ["1", "2", "3", "MBC", "SBS"]
```

**결과**: LLM이 실제 시스템의 Agent 능력을 정확히 인식하고 분석

### 🗂️ **Context Manager**
복합 요청 처리 시 에이전트 간 정보 전달을 담당하는 전용 모듈:

- **세션 기반 관리**: 각 사용자 요청마다 독립적인 컨텍스트 세션 생성
- **Agent Card 기반 맥락 추출**: 실제 등록된 Agent들의 특성을 반영한 맥락 정보 추출
- **순차/병렬 실행 지원**: 요청 특성에 따른 최적 실행 전략 선택

**예시 시나리오**:
```
사용자: "오늘 서울 날씨 어때? 그리고 날씨에 맞는 TV 채널로 바꿔줘"

1️⃣ Weather Agent 실행 → "서울, 맑음, 22도" 정보 생성
2️⃣ Context Manager가 날씨 정보 추출 → "맑음, 22도"  
3️⃣ TV Agent에 전달 → "맑은 날씨 정보와 함께 TV 채널 변경 요청"
4️⃣ 통합 응답 생성 → 날씨 + TV 조합 응답
```

### 🔍 **A2A 프로토콜 디버깅**
학습 목적으로 모든 LLM 호출의 상세 정보를 로깅:

```bash
# 실행 시 확인할 수 있는 상세 로그
🤖 LLM API 호출 시작
📋 System Prompt: [Agent Card 기반 생성된 프롬프트 전체]
👤 User Prompt: [실제 분석 대상 텍스트]  
🤖 LLM 응답: [JSON 형태의 분석 결과]
📊 토큰 사용량: prompt(150) + completion(50) = total(200)
```

**학습 포인트**: A2A 프로토콜이 어떻게 Agent Card 정보를 활용하여 지능적인 라우팅을 수행하는지 실시간 확인 가능

### 🎨 **확장성 설계**
새로운 Service Agent 추가 시:

1. **자동 감지**: Agent Card의 스킬 정보 자동 인덱싱
2. **프롬프트 업데이트**: 기존 LLM 프롬프트에 새 Agent 정보 자동 반영  
3. **맥락 관리**: 새 Agent의 응답 패턴도 자동으로 맥락 추출 기준에 포함
4. **제로 코드 변경**: Main Agent나 기존 Agent 수정 없이 즉시 사용 가능

**실제 동작**:
```bash
# 새로운 Music Agent 추가 시
echo "🎵 Music Agent가 등록되었습니다"
# → Intent Classification 프롬프트 자동 업데이트
# → Entity Extraction에 음악 관련 엔티티 자동 추가  
# → Context Manager가 음악 정보도 맥락으로 인식
# → 사용자는 즉시 "날씨 좋으니까 신나는 음악 틀어줘" 요청 가능
```

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
├── main.py                           # 시스템 런처 (멀티프로세스)
├── client.py                        # 대화형 테스트 클라이언트
├── kill_ps.sh                       # 프로세스 종료 스크립트
├── src/
│   ├── main_agent.py               # Main Agent (Orchestration + Registry)
│   ├── weather_agent.py            # Weather Service Agent
│   ├── tv_agent.py                 # TV Control Service Agent
│   ├── llm_client.py               # Azure OpenAI 클라이언트 (상세 로깅 포함)
│   ├── prompt_loader.py            # YAML 프롬프트 로더
│   ├── query_analyzer.py           # Intent/Entity 분석기
│   ├── context_manager.py          # 🆕 Agent Card 기반 맥락 관리
│   ├── dynamic_prompt_manager.py   # 🆕 동적 프롬프트 생성기
│   ├── dynamic_query_analyzer.py   # 🆕 동적 쿼리 분석기
│   └── extended_agent_card.py      # 🆕 확장 Agent Card 모델
├── prompt/                         # LLM 프롬프트 템플릿
│   ├── main_agent/
│   │   ├── intent_classification.yaml           # 기본 의도 분류
│   │   ├── intent_classification_skeleton.yaml  # 동적 생성용 뼈대
│   │   ├── intent_classification_complete.yaml  # 완성된 프롬프트
│   │   ├── entity_extraction.yaml              # 기본 엔티티 추출
│   │   ├── entity_extraction_skeleton.yaml     # 동적 생성용 뼈대
│   │   ├── entity_extraction_complete.yaml     # 완성된 프롬프트
│   │   ├── orchestration.yaml                  # 기본 오케스트레이션
│   │   ├── orchestration_skeleton.yaml         # 동적 생성용 뼈대
│   │   ├── orchestration_complete.yaml         # 완성된 프롬프트
│   │   └── chitchat.yaml                       # 일반 대화
│   ├── weather_agent/
│   │   └── weather_response.yaml
│   └── tv_agent/
│       └── tv_control.yaml
├── pyproject.toml                   # 프로젝트 설정
├── uv.lock                         # 의존성 잠금 파일
├── refactorying-plan.md            # 리팩토링 계획서
└── README.md                       # 이 파일
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