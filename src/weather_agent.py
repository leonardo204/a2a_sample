#!/usr/bin/env python3
"""
Weather Agent - 날씨 정보 제공 전담 에이전트
A2A 프로토콜 기반으로 Main Agent Registry에 자동 등록
"""
import asyncio
import uuid
import json
import httpx
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard, AgentSkill, Message, TextPart, Role
)
from src.llm_client import LLMClient
from src.prompt_loader import PromptLoader
from src.extended_agent_card import ExtendedAgentSkill, EntityTypeInfo
import logging

logger = logging.getLogger(__name__)

class WeatherAgentExecutor(AgentExecutor):
    """날씨 에이전트 실행자"""
    
    def __init__(self):
        """초기화"""
        print("🌤️ WeatherAgentExecutor 초기화...")
        try:
            self.llm_client = LLMClient()
            self.prompt_loader = PromptLoader("prompt")
            print("✅ WeatherAgentExecutor 초기화 완료")
        except Exception as e:
            print(f"❌ WeatherAgentExecutor 초기화 실패: {e}")
            raise

    async def execute(self, context: RequestContext, queue: EventQueue) -> None:
        """메시지 실행 처리"""
        
        print("\n" + "=" * 50)
        print("🌤️ WEATHER AGENT 실행 시작")
        print("=" * 50)
        
        try:
            # 1. 사용자 메시지 추출
            user_text = await self._extract_user_message(context)
            
            if not user_text:
                print("❌ 메시지 추출 실패")
                await self._send_response(context, queue, "안녕하세요! 날씨 정보를 도와드릴 수 있습니다.")
                return
            
            print(f"✅ 추출된 메시지: '{user_text}'")
            
            # 2. Agent 컨텍스트 정보 추출
            agent_contexts = self._extract_agent_contexts(user_text)
            
            # 3. 날씨 정보 처리
            response_text = await self._process_weather_request(user_text, agent_contexts)
            
            # 3. 응답 전송
            await self._send_response(context, queue, response_text)
            
            print("✅ 날씨 정보 처리 완료!")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            await self._send_response(context, queue, f"날씨 정보 처리 중 오류가 발생했습니다: {str(e)}")

    async def _extract_user_message(self, context: RequestContext) -> str:
        """사용자 메시지 추출"""
        print("🔍 메시지 추출 중...")
        
        try:
            message = getattr(context, 'message', None)
            if not message:
                return ""
            
            parts = getattr(message, 'parts', None)
            if not parts:
                return ""
            
            user_text = ""
            for part in parts:
                # 텍스트 추출 시도
                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                    text_value = getattr(part.root, 'text')
                    if text_value:
                        user_text += str(text_value)
                elif hasattr(part, 'model_dump'):
                    part_dict = part.model_dump()
                    if 'root' in part_dict and isinstance(part_dict['root'], dict):
                        if 'text' in part_dict['root']:
                            user_text += str(part_dict['root']['text'])
                            
            return user_text.strip()
            
        except Exception as e:
            print(f"❌ 메시지 추출 실패: {e}")
            return ""

    async def _process_weather_request(self, user_text: str, agent_contexts: list = None) -> str:
        """날씨 요청 처리 - Agent Card 기반 동적 맥락 이해"""
        print(f"🌤️ 날씨 요청 분석 중: '{user_text}'")
        
        try:
            # 다른 Agent 결과가 있으면 LLM으로 동적 해석
            if agent_contexts:
                print(f"🔄 다른 Agent 컨텍스트 감지: {len(agent_contexts)}개")
                result = await self._process_weather_request_with_context(user_text, agent_contexts)
            else:
                # 단순 날씨 정보 요청
                result = await self._process_simple_weather_request(user_text)
            
            return result
            
        except Exception as e:
            print(f"❌ 날씨 요청 처리 실패: {e}")
            return f"죄송합니다. 날씨 정보를 처리하는 중 오류가 발생했습니다."
    
    async def _process_weather_request_with_context(self, user_text: str, agent_contexts: list) -> str:
        """LLM을 사용해 다른 Agent 결과를 동적으로 해석하여 날씨 정보 제공"""
        print("🤖 LLM 기반 동적 컨텍스트 처리 시작")
        
        try:
            # Agent 컨텍스트를 LLM 프롬프트로 구성
            context_prompt = self._build_agent_context_prompt(agent_contexts)
            
            system_prompt = f"""당신은 날씨 정보 전문 에이전트입니다.

사용자의 날씨 정보 요청과 함께 다른 에이전트들의 실행 결과가 제공됩니다.
각 에이전트의 Agent Card 정보(skills, tags, entity_types)를 참고하여
해당 결과가 날씨 정보 제공에 어떻게 활용될 수 있는지 동적으로 판단하세요.

{context_prompt}

응답은 반드시 JSON 형태로 제공해주세요:
{{
    "location_analysis": "위치 정보 분석",
    "context_integration": "다른 Agent 결과를 어떻게 활용할지",
    "weather_data": {{
        "condition": "날씨 상태",
        "temperature": "온도",
        "humidity": "습도"
    }},
    "response": "사용자에게 전달할 최종 응답"
}}"""

            user_prompt = f"""사용자 요청: "{user_text}"

위의 다른 에이전트 결과들을 참고하여 적절한 날씨 정보를 제공하고 자연스러운 응답을 생성해주세요."""

            response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=400,
                response_format={"type": "json_object"}
            )
            
            # JSON 응답 파싱
            try:
                import json
                result = json.loads(response.strip())
                return result.get("response", "날씨 정보를 제공했습니다.")
            except json.JSONDecodeError:
                print(f"❌ JSON 파싱 실패, 원본 응답 사용: {response}")
                return response.strip()
                
        except Exception as e:
            print(f"❌ LLM 컨텍스트 처리 실패: {e}")
            # 백업으로 단순 처리
            return await self._process_simple_weather_request(user_text)

    async def _process_simple_weather_request(self, user_text: str) -> str:
        """단순 날씨 정보 요청 처리"""
        print("🌤️ 단순 날씨 정보 처리")
        
        try:
            # 지역 및 시간 정보 추출
            location = self._extract_location(user_text)
            time_info = self._extract_time_info(user_text)
            
            print(f"📍 추출된 위치: {location}")
            print(f"🕐 추출된 시간: {time_info}")
            
            # LLM을 사용한 자연스러운 날씨 응답 생성
            response = await self._generate_weather_response(user_text, location, time_info)
            return response
            
        except Exception as e:
            print(f"❌ 단순 날씨 처리 실패: {e}")
            return self._generate_fallback_weather_response(location, time_info)

    def _build_agent_context_prompt(self, agent_contexts: list) -> str:
        """Agent Card 정보를 LLM이 이해할 수 있는 프롬프트로 변환"""
        
        if not agent_contexts:
            return "다른 에이전트 실행 결과가 없습니다."
        
        context_sections = []
        
        for context in agent_contexts:
            agent_card = context.get("source_agent_card", {})
            result = context.get("execution_result", {})
            
            section = f"""
[{agent_card.get('name', 'Unknown Agent')} 정보]
- Skills: {json.dumps(agent_card.get('skills', []), ensure_ascii=False)}
- Extended Skills: {json.dumps(agent_card.get('extended_skills', []), ensure_ascii=False)}
- 실행 결과: {json.dumps(result, ensure_ascii=False)}
"""
            context_sections.append(section)
        
        return "\n".join(context_sections)

    def _extract_agent_contexts(self, user_text: str) -> list:
        """메시지에서 Agent 컨텍스트 정보 추출"""
        try:
            # [AGENT_CONTEXT] 섹션이 있는지 확인
            if "[AGENT_CONTEXT]" not in user_text:
                return []
            
            # JSON 형태의 컨텍스트 정보 추출
            lines = user_text.split('\n')
            in_context_section = False
            context_json = ""
            
            for line in lines:
                if "[AGENT_CONTEXT]" in line:
                    in_context_section = True
                    continue
                elif in_context_section and line.strip():
                    if line.strip().startswith('[') or line.strip().startswith('{'):
                        context_json += line.strip()
                    elif context_json and (line.strip().endswith(']') or line.strip().endswith('}')):
                        context_json += line.strip()
                        break
                    elif context_json:
                        context_json += line.strip()
                elif in_context_section and line.strip() == "":
                    break
            
            if context_json:
                import json
                return json.loads(context_json)
                
        except Exception as e:
            print(f"⚠️ Agent 컨텍스트 추출 실패: {e}")
        
        return []

    def _extract_location(self, user_text: str) -> str:
        """지역 정보 추출"""
        user_lower = user_text.lower()
        
        # 주요 도시 목록
        cities = {
            "서울": ["서울", "seoul"],
            "부산": ["부산", "busan"],
            "대구": ["대구", "daegu"],
            "인천": ["인천", "incheon"],
            "광주": ["광주", "gwangju"],
            "대전": ["대전", "daejeon"],
            "울산": ["울산", "ulsan"],
            "제주": ["제주", "jeju"]
        }
        
        for city, keywords in cities.items():
            if any(keyword in user_lower for keyword in keywords):
                return city
                
        return "서울"  # 기본값

    def _extract_time_info(self, user_text: str) -> str:
        """시간 정보 추출"""
        user_lower = user_text.lower()
        
        time_keywords = {
            "오늘": ["오늘", "today"],
            "내일": ["내일", "tomorrow"],
            "모레": ["모레"],
            "이번주": ["이번주", "this week"],
            "다음주": ["다음주", "next week"]
        }
        
        for time_info, keywords in time_keywords.items():
            if any(keyword in user_lower for keyword in keywords):
                return time_info
                
        return "오늘"  # 기본값

    async def _generate_weather_response(self, user_text: str, location: str, time_info: str) -> str:
        """LLM을 사용한 자연스러운 날씨 응답 생성"""
        try:
            prompt_data = self.prompt_loader.load_prompt("weather_agent", "weather_response")
            
            # 백업 날씨 데이터 생성 (실제로는 외부 API에서 가져올 데이터)
            weather_data = self._get_weather_data(location)
            
            formatted_prompt = prompt_data["user_prompt_template"].format(
                original_request=user_text,  # 프롬프트 파일의 변수명에 맞춤
                location=location,
                time_context=time_info,  # 프롬프트 파일의 변수명에 맞춤
                weather_condition=weather_data["condition"],
                temperature=weather_data["temp"],
                humidity=weather_data["humidity"],
                wind_speed=weather_data.get("wind_speed", 5),
                uv_index=weather_data.get("uv_index", 3)
            )
            
            response = await self.llm_client.chat_completion(
                system_prompt=prompt_data["system_prompt"],
                user_prompt=formatted_prompt,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            # JSON 응답 파싱
            try:
                import json
                result = json.loads(response.strip())
                return result.get("response", "날씨 정보를 처리했습니다.")
            except json.JSONDecodeError:
                print(f"❌ JSON 파싱 실패, 원본 응답 사용: {response}")
                return response.strip()
            
        except Exception as e:
            print(f"❌ LLM 날씨 응답 생성 실패: {e}")
            raise

    def _generate_fallback_weather_response(self, location: str, time_info: str) -> str:
        """백업 날씨 응답 생성"""
        weather_data = self._get_weather_data(location)
        
        return f"🌤️ {location}의 {time_info} 날씨는 {weather_data['condition']}이고, 기온은 {weather_data['temp']}도, 습도는 {weather_data['humidity']}% 입니다."

    def _get_weather_data(self, location: str) -> dict:
        """위치별 날씨 데이터 조회 (테스트용 시뮬레이션)"""
        # 테스트용 고정 응답 (실제로는 외부 API 연동)
        weather_data = {
            "서울": {"temp": 22, "condition": "맑음", "humidity": 60, "wind_speed": 8, "uv_index": 5},
            "부산": {"temp": 25, "condition": "구름조금", "humidity": 65, "wind_speed": 12, "uv_index": 6},
            "대구": {"temp": 24, "condition": "맑음", "humidity": 55, "wind_speed": 6, "uv_index": 5},
            "인천": {"temp": 21, "condition": "흐림", "humidity": 70, "wind_speed": 10, "uv_index": 3},
            "광주": {"temp": 26, "condition": "맑음", "humidity": 58, "wind_speed": 7, "uv_index": 6},
            "대전": {"temp": 23, "condition": "구름조금", "humidity": 62, "wind_speed": 9, "uv_index": 4},
            "울산": {"temp": 25, "condition": "맑음", "humidity": 63, "wind_speed": 11, "uv_index": 5},
            "제주": {"temp": 28, "condition": "맑음", "humidity": 72, "wind_speed": 15, "uv_index": 7}
        }
        
        return weather_data.get(location, weather_data["서울"])

    async def _send_response(self, context: RequestContext, queue: EventQueue, text: str):
        """응답 전송"""
        print(f"📤 응답 전송: '{text}'")
        
        try:
            response_message = Message(
                messageId=str(uuid.uuid4()),
                role=Role.agent,
                parts=[TextPart(kind='text', text=text)],
                contextId=context.context_id,
                taskId=context.task_id
            )
            
            await queue.enqueue_event(response_message)
            print("✅ 응답 전송 완료")
            
        except Exception as e:
            print(f"❌ 응답 전송 중 오류: {e}")

    async def cancel(self, context: RequestContext) -> None:
        """실행 취소"""
        print("🛑 Cancel 호출됨")


async def register_to_main_agent(agent_card: dict, main_agent_url: str = "http://localhost:18000") -> bool:
    """Main Agent Registry에 HTTP API를 통해 등록 (재시도 메커니즘 포함)"""
    print(f"📝 Main Agent Registry에 Weather Agent 등록 중...")
    
    max_retries = 5
    retry_delay = 2  # 초
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{main_agent_url}/api/registry/register",
                    headers={"Content-Type": "application/json"},
                    json=agent_card
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        print("✅ Weather Agent Registry 등록 완료")
                        return True
                    else:
                        print(f"❌ Weather Agent Registry 등록 실패: {result.get('message', 'Unknown error')}")
                        return False
                else:
                    print(f"⚠️ 등록 시도 {attempt + 1}/{max_retries} 실패 (HTTP {response.status_code})")
                    if attempt < max_retries - 1:
                        print(f"   {retry_delay}초 후 재시도...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        print(f"❌ Weather Agent Registry 등록 최종 실패")
                        return False
                        
        except Exception as e:
            print(f"⚠️ 등록 시도 {attempt + 1}/{max_retries} 오류: {e}")
            if attempt < max_retries - 1:
                print(f"   {retry_delay}초 후 재시도...")
                await asyncio.sleep(retry_delay)
                continue
            else:
                print(f"❌ Weather Agent Registry 등록 최종 실패: {e}")
                return False
    
    return False


def create_weather_agent():
    """Weather Agent 생성"""
    print("🏗️ Weather Agent 생성...")
    
    agent_card = AgentCard(
        name="Weather Agent",
        description="날씨 정보 제공 전담 에이전트 - A2A 프로토콜 지원",
        version="1.0.0",
        url="http://localhost:18001",
        capabilities={
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="weather",
                name="Weather Service",
                description="날씨 정보 및 예보 제공 통합 서비스",
                tags=["weather", "info", "forecast", "temperature", "condition"]
            )
        ]
    )
    
    executor = WeatherAgentExecutor()
    task_store = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store
    )
    app_builder = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )
    
    app = app_builder.build()
    print("✅ Weather Agent 생성 완료")
    
    # 서버 시작 이벤트에 등록 함수 추가
    @app.on_event("startup")
    async def startup_event():
        # 확장된 정보를 포함하여 등록
        extended_agent_card = agent_card.model_dump()
        extended_agent_card["extended_skills"] = [
            ExtendedAgentSkill(
                id="weather",
                name="Weather Service",
                description="날씨 정보 및 예보 제공 통합 서비스",
                tags=["weather", "info", "forecast", "temperature", "condition"],
                domain_category="weather",
                keywords=["날씨", "weather", "기온", "온도", "비", "눈", "맑음", "흐림", "바람", "습도", "예보"],
                entity_types=[
                    EntityTypeInfo("location", "위치 정보", ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "제주"]),
                    EntityTypeInfo("time", "시간 정보", ["오늘", "내일", "이번주", "다음주", "지금", "현재", "모레", "주말", "평일"])
                ],
                intent_patterns=["날씨 문의", "기상 정보", "날씨 예보", "weather inquiry", "weather forecast"],
                connection_patterns=["어울리는", "맞는", "적절한", "따라", "기반으로", "맞춰서"]
            ).to_dict()
        ]
        await register_to_main_agent(extended_agent_card)
    
    return app