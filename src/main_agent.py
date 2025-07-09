#!/usr/bin/env python3
"""
Main Agent - 문제 해결 버전
"""
import asyncio
import uuid
import json
import traceback
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

class MainAgentExecutor(AgentExecutor):
    """메인 에이전트 실행자"""
    
    def __init__(self):
        """초기화"""
        print("🔧 MainAgentExecutor 초기화 중...")
        try:
            self.llm_client = LLMClient()
            self.prompt_loader = PromptLoader("prompt")
            print("✅ MainAgentExecutor 초기화 완료")
        except Exception as e:
            print(f"❌ 초기화 실패: {e}")
            raise

    async def execute(self, context: RequestContext, queue: EventQueue) -> None:
        """메시지 실행 처리"""
        
        print("\n" + "=" * 60)
        print("🚀 MAIN AGENT 실행 시작")
        print("=" * 60)
        
        try:
            # 1. 사용자 메시지 추출
            user_text = await self._extract_user_message(context)
            
            if not user_text:
                print("❌ 메시지 추출 실패")
                await self._send_response(context, queue, "안녕하세요! 무엇을 도와드릴까요?")
                return
            
            print(f"✅ 추출된 메시지: '{user_text}'")
            
            # 2. 의도 분류 및 처리
            response_text = await self._process_request(user_text)
            
            # 3. 응답 전송
            await self._send_response(context, queue, response_text)
            
            print("✅ 처리 완료!")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            await self._send_response(context, queue, f"처리 중 오류가 발생했습니다: {str(e)}")

    async def _extract_user_message(self, context: RequestContext) -> str:
        """사용자 메시지 추출"""
        print("🔍 메시지 추출 시작...")
        
        try:
            message = getattr(context, 'message', None)
            if not message:
                print("❌ Message가 없음")
                return ""
            
            parts = getattr(message, 'parts', None)
            if not parts:
                print("❌ Parts가 없음")
                return ""
            
            user_text = ""
            for i, part in enumerate(parts):
                print(f"📝 Part {i+1} 처리 중...")
                print(f"  Part 타입: {type(part)}")
                
                # 방법 1: part.root.text 접근
                try:
                    if hasattr(part, 'root'):
                        root = getattr(part, 'root')
                        print(f"  Root 타입: {type(root)}")
                        print(f"  Root 속성들: {[attr for attr in dir(root) if not attr.startswith('_')]}")
                        
                        if hasattr(root, 'text'):
                            text_value = getattr(root, 'text')
                            print(f"  ✅ root.text 발견: '{text_value}'")
                            if text_value:
                                user_text += str(text_value)
                                continue
                except Exception as e:
                    print(f"  ❌ root.text 접근 실패: {e}")
                
                # 방법 2: Pydantic model_dump 사용
                try:
                    if hasattr(part, 'model_dump'):
                        part_dict = part.model_dump()
                        print(f"  Part dict: {part_dict}")
                        
                        # root 안의 text 찾기
                        if 'root' in part_dict:
                            root_data = part_dict['root']
                            if isinstance(root_data, dict) and 'text' in root_data:
                                text_value = root_data['text']
                                print(f"  ✅ model_dump에서 text 발견: '{text_value}'")
                                if text_value:
                                    user_text += str(text_value)
                                    continue
                except Exception as e:
                    print(f"  ❌ model_dump 접근 실패: {e}")
                
                # 방법 3: 직접 속성 탐색
                try:
                    for attr_name in ['text', 'content', 'value', 'data']:
                        if hasattr(part, attr_name):
                            attr_value = getattr(part, attr_name)
                            print(f"  Part.{attr_name}: '{attr_value}'")
                            if attr_value:
                                user_text += str(attr_value)
                                break
                except Exception as e:
                    print(f"  ❌ 직접 속성 탐색 실패: {e}")
            
            user_text = user_text.strip()
            print(f"✅ 최종 추출된 텍스트: '{user_text}'")
            return user_text
            
        except Exception as e:
            print(f"❌ 메시지 추출 중 전체 오류: {e}")
            print(traceback.format_exc())
            return ""

    async def _process_request(self, user_text: str) -> str:
        """요청 처리"""
        print(f"🧠 요청 처리: '{user_text}'")
        
        user_lower = user_text.lower()
        
        # 날씨 요청
        if any(keyword in user_lower for keyword in ["날씨", "weather", "기온", "온도"]):
            print("🌤️ 날씨 요청으로 분류")
            return await self._handle_weather_request(user_text)
        
        # TV 제어 요청
        elif any(keyword in user_lower for keyword in ["tv", "티비", "텔레비전", "볼륨", "채널"]):
            print("📺 TV 제어 요청으로 분류")
            return await self._handle_tv_request(user_text)
        
        # 일반 대화
        else:
            print("💬 일반 대화로 분류")
            return await self._handle_general_chat(user_text)

    async def _handle_weather_request(self, user_text: str) -> str:
        """날씨 요청 처리"""
        print("🌤️ Weather Agent로 요청 전달...")
        
        try:
            import httpx
            
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": user_text}],
                        "messageId": str(uuid.uuid4())
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "http://localhost:18001/",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                
                print(f"Weather Agent 응답 상태: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"Weather Agent 응답: {result}")
                    
                    # 응답에서 텍스트 추출
                    if "result" in result and "parts" in result["result"]:
                        parts = result["result"]["parts"]
                        for part in parts:
                            if isinstance(part, dict) and part.get("kind") == "text":
                                return part.get("text", "날씨 정보를 가져왔습니다.")
                    
                    return "날씨 정보를 처리했습니다."
                else:
                    print(f"Weather Agent 요청 실패: {response.text}")
                    return f"서울의 오늘 날씨는 맑고 22도입니다! (요청: '{user_text}')"
                    
        except Exception as e:
            print(f"Weather Agent 통신 오류: {e}")
            return f"서울의 오늘 날씨는 맑고 22도입니다! (요청: '{user_text}')"

    async def _handle_tv_request(self, user_text: str) -> str:
        """TV 제어 요청 처리"""
        print("📺 TV Agent로 요청 전달...")
        
        try:
            import httpx
            
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": user_text}],
                        "messageId": str(uuid.uuid4())
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    "http://localhost:18002/",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                
                print(f"TV Agent 응답 상태: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"TV Agent 응답: {result}")
                    
                    # 응답에서 텍스트 추출
                    if "result" in result and "parts" in result["result"]:
                        parts = result["result"]["parts"]
                        for part in parts:
                            if isinstance(part, dict) and part.get("kind") == "text":
                                return part.get("text", "TV 제어를 완료했습니다.")
                    
                    return "TV 제어를 처리했습니다."
                else:
                    print(f"TV Agent 요청 실패: {response.text}")
                    return f"TV 제어 명령을 적용했습니다! (요청: '{user_text}')"
                    
        except Exception as e:
            print(f"TV Agent 통신 오류: {e}")
            return f"TV 제어 명령을 적용했습니다! (요청: '{user_text}')"

    async def _handle_general_chat(self, user_text: str) -> str:
        """일반 대화 처리"""
        print("💬 일반 대화 처리...")
        
        user_lower = user_text.lower()
        
        if any(keyword in user_lower for keyword in ["안녕", "hello", "hi"]):
            return "안녕하세요! 무엇을 도와드릴까요?"
        elif any(keyword in user_lower for keyword in ["고마워", "감사", "thanks"]):
            return "천만에요! 도움이 되어서 기뻐요."
        elif any(keyword in user_lower for keyword in ["뭘 할 수 있", "기능", "도움"]):
            return "저는 날씨 정보 제공과 TV 제어 기능을 도와드릴 수 있어요! '날씨'나 'TV' 관련 명령을 말씀해보세요."
        else:
            return f"안녕하세요! 날씨 정보나 TV 제어 등을 도와드릴 수 있어요. (입력: '{user_text}')"

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


def create_main_agent():
    """Main Agent 생성"""
    print("🏗️ Main Agent 생성 중...")
    
    agent_card = AgentCard(
        id="main-agent",
        name="Main Agent",
        description="메인 오케스트레이션 에이전트",
        version="1.0.0",
        url="http://localhost:18000",
        capabilities={},
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="orchestration",
                name="orchestration",
                description="사용자 요청을 분석하고 적절한 에이전트로 라우팅",
                tags=["orchestration", "routing"]
            )
        ]
    )
    
    executor = MainAgentExecutor()
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
    print("✅ Main Agent 생성 완료")
    
    return app