#!/usr/bin/env python3
"""
Weather Agent - 메시지 추출 문제 해결 버전
"""
import asyncio
import uuid
import json
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
import logging

logger = logging.getLogger(__name__)

class WeatherAgentExecutor(AgentExecutor):
    """날씨 에이전트 실행자"""
    
    def __init__(self):
        """초기화"""
        print("🌤️ WeatherAgentExecutor 초기화...")
        self.llm_client = LLMClient()
        self.prompt_loader = PromptLoader("prompt")
        print("✅ WeatherAgentExecutor 초기화 완료")

    async def execute(self, context: RequestContext, queue: EventQueue) -> None:
        """날씨 정보 요청 처리"""
        print("\n" + "=" * 50)
        print("🌤️ WEATHER AGENT 실행 시작")
        print("=" * 50)
        
        try:
            # 사용자 메시지 추출
            user_text = await self._extract_user_message(context)
            
            if not user_text:
                print("❌ Weather Agent: 메시지 추출 실패")
                await self._send_response(context, queue, "날씨 정보가 필요하시면 지역명을 말씀해 주세요.")
                return
            
            print(f"✅ Weather Agent 메시지: '{user_text}'")
            
            # 날씨 응답 생성
            weather_response = await self._generate_weather_response(user_text)
            
            # 응답 전송
            await self._send_response(context, queue, weather_response)
            
            print("✅ Weather Agent 처리 완료!")
            
        except Exception as e:
            print(f"❌ Weather Agent 오류: {e}")
            await self._send_response(context, queue, f"날씨 정보를 가져오는 중 오류가 발생했습니다: {str(e)}")

    async def _extract_user_message(self, context: RequestContext) -> str:
        """사용자 메시지 추출 (Main Agent와 동일한 방식)"""
        print("🔍 Weather Agent 메시지 추출...")
        
        try:
            message = getattr(context, 'message', None)
            if not message:
                return ""
            
            parts = getattr(message, 'parts', None)
            if not parts:
                return ""
            
            user_text = ""
            for i, part in enumerate(parts):
                print(f"  Part {i+1}: {type(part)}")
                
                # part.root.text 접근
                try:
                    if hasattr(part, 'root'):
                        root = getattr(part, 'root')
                        if hasattr(root, 'text'):
                            text_value = getattr(root, 'text')
                            print(f"  ✅ Weather root.text: '{text_value}'")
                            if text_value:
                                user_text += str(text_value)
                except Exception as e:
                    print(f"  ❌ Weather root.text 접근 실패: {e}")
                
                # Pydantic model_dump 방법
                try:
                    if hasattr(part, 'model_dump'):
                        part_dict = part.model_dump()
                        if 'root' in part_dict and isinstance(part_dict['root'], dict):
                            if 'text' in part_dict['root']:
                                text_value = part_dict['root']['text']
                                print(f"  ✅ Weather model_dump text: '{text_value}'")
                                if text_value:
                                    user_text += str(text_value)
                except Exception as e:
                    print(f"  ❌ Weather model_dump 접근 실패: {e}")
            
            user_text = user_text.strip()
            print(f"✅ Weather 최종 텍스트: '{user_text}'")
            return user_text
            
        except Exception as e:
            print(f"❌ Weather 메시지 추출 오류: {e}")
            return ""

    async def _generate_weather_response(self, user_text: str) -> str:
        """날씨 응답 생성"""
        print(f"🌤️ 날씨 응답 생성: '{user_text}'")
        
        try:
            # 지역 추출
            location = "서울"  # 기본값
            if "부산" in user_text:
                location = "부산"
            elif "대구" in user_text:
                location = "대구"
            elif "인천" in user_text:
                location = "인천"
            elif "광주" in user_text:
                location = "광주"
            elif "대전" in user_text:
                location = "대전"
            
            # 시간 컨텍스트
            time_context = "오늘"
            if "내일" in user_text:
                time_context = "내일"
            elif "모레" in user_text:
                time_context = "모레"
            
            print(f"  지역: {location}, 시간: {time_context}")
            
            # 날씨 데이터 (테스트용)
            weather_data = {
                "original_request": user_text,
                "location": location,
                "time_context": time_context,
                "weather_condition": "맑음",
                "temperature": 22,
                "humidity": 65,
                "wind_speed": 5,
                "uv_index": 6
            }
            
            # LLM을 사용한 응답 생성 시도
            try:
                prompt_data = self.prompt_loader.load_prompt("weather_agent", "weather_response")
                system_prompt = prompt_data.get("system_prompt", "")
                user_prompt_template = prompt_data.get("user_prompt_template", "{user_input}")
                
                user_prompt = user_prompt_template.format(**weather_data)
                
                response = await self.llm_client.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=300
                )
                
                # JSON 응답 파싱 시도
                try:
                    # ```json 코드 블록 제거
                    clean_response = response.strip()
                    if clean_response.startswith("```json"):
                        clean_response = clean_response[7:]  # ```json 제거
                    if clean_response.endswith("```"):
                        clean_response = clean_response[:-3]  # ``` 제거
                    clean_response = clean_response.strip()
                    
                    json_response = json.loads(clean_response)
                    if isinstance(json_response, dict) and "response" in json_response:
                        final_response = json_response["response"]
                        print(f"  ✅ LLM JSON 파싱 성공: {final_response}")
                        return final_response
                    else:
                        print(f"  ⚠️ JSON에 response 필드 없음: {json_response}")
                        return clean_response
                except json.JSONDecodeError:
                    print(f"  ⚠️ JSON 파싱 실패, 원문 사용: {response}")
                    return response
                    
            except Exception as e:
                print(f"  ❌ LLM 호출 실패: {e}")
            
            # 대체 응답 (LLM 실패시)
            fallback_response = f"{location}의 {time_context} 날씨를 알려드릴게요!\n\n" \
                              f"🌤️ 날씨: 맑음\n" \
                              f"🌡️ 기온: 22°C\n" \
                              f"💧 습도: 65%\n" \
                              f"🌪️ 바람: 5km/h\n\n" \
                              f"외출하기 좋은 날씨네요!"
            
            print(f"  ✅ 대체 응답 생성")
            return fallback_response
            
        except Exception as e:
            print(f"❌ 날씨 응답 생성 오류: {e}")
            return f"{user_text.split()[0] if user_text else '서울'}의 오늘 날씨는 맑고 22도입니다! 외출하기 좋은 날씨예요."

    async def _send_response(self, context: RequestContext, queue: EventQueue, text: str):
        """응답 전송"""
        print(f"📤 Weather 응답 전송: '{text[:50]}...'")
        
        try:
            response_message = Message(
                messageId=str(uuid.uuid4()),
                role=Role.agent,
                parts=[TextPart(kind='text', text=text)],
                contextId=context.context_id,
                taskId=context.task_id
            )
            
            await queue.enqueue_event(response_message)
            print("✅ Weather 응답 전송 완료")
            
        except Exception as e:
            print(f"❌ Weather 응답 전송 오류: {e}")

    async def cancel(self, context: RequestContext) -> None:
        """실행 취소"""
        print("🛑 Weather Agent 취소")


def create_weather_agent():
    """Weather Agent 생성"""
    print("🏗️ Weather Agent 생성...")
    
    agent_card = AgentCard(
        id="weather-agent",
        name="Weather Agent",
        description="날씨 정보 제공 에이전트",
        version="1.0.0",
        url="http://localhost:18001",
        capabilities={},
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="weather_info",
                name="weather_info",
                description="지역별 날씨 정보 제공",
                tags=["weather", "info", "current"]
            ),
            AgentSkill(
                id="weather_forecast",
                name="weather_forecast",
                description="날씨 예보 정보 제공",
                tags=["weather", "forecast", "prediction"]
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
    
    return app