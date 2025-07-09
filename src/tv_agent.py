#!/usr/bin/env python3
"""
TV Agent - 메시지 추출 문제 해결 버전
"""
import asyncio
import uuid
import json
import re
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

class TVAgentExecutor(AgentExecutor):
    """TV 에이전트 실행자"""
    
    def __init__(self):
        """초기화"""
        print("📺 TVAgentExecutor 초기화...")
        self.llm_client = LLMClient()
        self.prompt_loader = PromptLoader("prompt")
        print("✅ TVAgentExecutor 초기화 완료")

    async def execute(self, context: RequestContext, queue: EventQueue) -> None:
        """TV 제어 요청 처리"""
        print("\n" + "=" * 50)
        print("📺 TV AGENT 실행 시작")
        print("=" * 50)
        
        try:
            # 사용자 메시지 추출
            user_text = await self._extract_user_message(context)
            
            if not user_text:
                print("❌ TV Agent: 메시지 추출 실패")
                await self._send_response(context, queue, "TV 제어가 필요하시면 명령을 말씀해 주세요.")
                return
            
            print(f"✅ TV Agent 메시지: '{user_text}'")
            
            # TV 제어 응답 생성
            tv_response = await self._generate_tv_response(user_text)
            
            # 응답 전송
            await self._send_response(context, queue, tv_response)
            
            print("✅ TV Agent 처리 완료!")
            
        except Exception as e:
            print(f"❌ TV Agent 오류: {e}")
            await self._send_response(context, queue, f"TV 제어 중 오류가 발생했습니다: {str(e)}")

    async def _extract_user_message(self, context: RequestContext) -> str:
        """사용자 메시지 추출 (Main Agent와 동일한 방식)"""
        print("🔍 TV Agent 메시지 추출...")
        
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
                            print(f"  ✅ TV root.text: '{text_value}'")
                            if text_value:
                                user_text += str(text_value)
                except Exception as e:
                    print(f"  ❌ TV root.text 접근 실패: {e}")
                
                # Pydantic model_dump 방법
                try:
                    if hasattr(part, 'model_dump'):
                        part_dict = part.model_dump()
                        if 'root' in part_dict and isinstance(part_dict['root'], dict):
                            if 'text' in part_dict['root']:
                                text_value = part_dict['root']['text']
                                print(f"  ✅ TV model_dump text: '{text_value}'")
                                if text_value:
                                    user_text += str(text_value)
                except Exception as e:
                    print(f"  ❌ TV model_dump 접근 실패: {e}")
            
            user_text = user_text.strip()
            print(f"✅ TV 최종 텍스트: '{user_text}'")
            return user_text
            
        except Exception as e:
            print(f"❌ TV 메시지 추출 오류: {e}")
            return ""

    async def _generate_tv_response(self, user_text: str) -> str:
        """TV 제어 응답 생성"""
        print(f"📺 TV 응답 생성: '{user_text}'")
        
        try:
            # 액션 및 매개변수 추출
            action, parameters = self._extract_tv_action(user_text)
            print(f"  액션: {action}, 매개변수: {parameters}")
            
            # 현재 TV 상태 (테스트용)
            current_state = {
                "power": "on",
                "channel": 7,
                "volume": 25,
                "max_volume": 50
            }
            
            # 새로운 상태 계산
            new_state = self._calculate_new_state(action, parameters, current_state)
            print(f"  현재 상태: {current_state}")
            print(f"  새 상태: {new_state}")
            
            # LLM을 사용한 응답 생성 시도
            try:
                tv_context = {
                    "original_request": user_text,
                    "action": action,
                    "parameters": parameters,
                    "current_channel": current_state["channel"],
                    "current_volume": current_state["volume"]
                }
                
                prompt_data = self.prompt_loader.load_prompt("tv_agent", "tv_control")
                system_prompt = prompt_data.get("system_prompt", "")
                user_prompt_template = prompt_data.get("user_prompt_template", "{user_input}")
                
                user_prompt = user_prompt_template.format(**tv_context)
                
                response = await self.llm_client.chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.5,
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
                        print(f"  ✅ TV LLM JSON 파싱 성공: {final_response}")
                        return final_response
                    else:
                        print(f"  ⚠️ JSON에 response 필드 없음: {json_response}")
                        return clean_response
                except json.JSONDecodeError:
                    print(f"  ⚠️ JSON 파싱 실패, 원문 사용: {response}")
                    return response
                    
            except Exception as e:
                print(f"  ❌ LLM 호출 실패: {e}")
            
            # 대체 응답 생성 (LLM 실패시)
            fallback_response = self._generate_fallback_response(action, parameters, current_state, new_state)
            print(f"  ✅ 대체 응답 생성")
            return fallback_response
            
        except Exception as e:
            print(f"❌ TV 응답 생성 오류: {e}")
            return f"TV 제어 명령을 적용했습니다! (요청: '{user_text}')"

    def _extract_tv_action(self, user_text: str) -> tuple[str, dict]:
        """사용자 입력에서 TV 액션과 매개변수 추출"""
        user_lower = user_text.lower()
        parameters = {}
        
        # 볼륨 제어
        if any(keyword in user_lower for keyword in ["볼륨", "음량", "소리"]):
            if any(keyword in user_lower for keyword in ["올려", "높여", "크게", "up"]):
                return "volume_up", parameters
            elif any(keyword in user_lower for keyword in ["내려", "낮춰", "작게", "down"]):
                return "volume_down", parameters
            elif any(keyword in user_lower for keyword in ["음소거", "mute"]):
                return "mute", parameters
            else:
                # 숫자 추출
                numbers = re.findall(r'\d+', user_text)
                if numbers:
                    parameters["volume_level"] = int(numbers[0])
                    return "volume_set", parameters
                return "volume_up", parameters
        
        # 채널 제어
        elif any(keyword in user_lower for keyword in ["채널", "번", "channel"]):
            numbers = re.findall(r'\d+', user_text)
            if numbers:
                parameters["channel"] = int(numbers[0])
                return "channel_set", parameters
            elif any(keyword in user_lower for keyword in ["올려", "다음", "up"]):
                return "channel_up", parameters
            elif any(keyword in user_lower for keyword in ["내려", "이전", "down"]):
                return "channel_down", parameters
            else:
                return "channel_up", parameters
        
        # 전원 제어
        elif any(keyword in user_lower for keyword in ["켜", "on", "전원"]):
            return "power_on", parameters
        elif any(keyword in user_lower for keyword in ["꺼", "off"]):
            return "power_off", parameters
        
        # 기본값
        else:
            return "general_control", parameters

    def _calculate_new_state(self, action: str, parameters: dict, current_state: dict) -> dict:
        """새로운 TV 상태 계산"""
        new_state = current_state.copy()
        
        if action == "volume_up":
            new_state["volume"] = min(current_state["volume"] + 5, current_state["max_volume"])
        elif action == "volume_down":
            new_state["volume"] = max(current_state["volume"] - 5, 0)
        elif action == "volume_set" and "volume_level" in parameters:
            new_state["volume"] = min(max(parameters["volume_level"], 0), current_state["max_volume"])
        elif action == "channel_set" and "channel" in parameters:
            new_state["channel"] = max(parameters["channel"], 1)
        elif action == "channel_up":
            new_state["channel"] = current_state["channel"] + 1
        elif action == "channel_down":
            new_state["channel"] = max(current_state["channel"] - 1, 1)
        elif action == "power_off":
            new_state["power"] = "off"
        elif action == "power_on":
            new_state["power"] = "on"
        
        return new_state

    def _generate_fallback_response(self, action: str, parameters: dict, current_state: dict, new_state: dict) -> str:
        """대체 응답 생성"""
        if action == "volume_up":
            return f"📺 TV 볼륨을 {current_state['volume']}에서 {new_state['volume']}으로 올렸습니다! 🔊"
        elif action == "volume_down":
            return f"📺 TV 볼륨을 {current_state['volume']}에서 {new_state['volume']}으로 내렸습니다! 🔉"
        elif action == "volume_set":
            return f"📺 TV 볼륨을 {new_state['volume']}으로 설정했습니다! 🔊"
        elif action == "channel_set":
            return f"📺 TV 채널을 {current_state['channel']}번에서 {new_state['channel']}번으로 변경했습니다! 📡"
        elif action == "channel_up":
            return f"📺 TV 채널을 {current_state['channel']}번에서 {new_state['channel']}번으로 올렸습니다! 📡"
        elif action == "channel_down":
            return f"📺 TV 채널을 {current_state['channel']}번에서 {new_state['channel']}번으로 내렸습니다! 📡"
        elif action == "power_on":
            return f"📺 TV를 켰습니다! 현재 {new_state['channel']}번 채널, 볼륨 {new_state['volume']}입니다. ⚡"
        elif action == "power_off":
            return f"📺 TV를 껐습니다! 좋은 시간 되세요. 💤"
        elif action == "mute":
            return f"📺 TV 음소거를 설정했습니다! 🔇"
        else:
            return f"📺 TV 제어 명령을 적용했습니다! 모든 설정이 완료되었습니다. ✅"

    async def _send_response(self, context: RequestContext, queue: EventQueue, text: str):
        """응답 전송"""
        print(f"📤 TV 응답 전송: '{text[:50]}...'")
        
        try:
            response_message = Message(
                messageId=str(uuid.uuid4()),
                role=Role.agent,
                parts=[TextPart(kind='text', text=text)],
                contextId=context.context_id,
                taskId=context.task_id
            )
            
            await queue.enqueue_event(response_message)
            print("✅ TV 응답 전송 완료")
            
        except Exception as e:
            print(f"❌ TV 응답 전송 오류: {e}")

    async def cancel(self, context: RequestContext) -> None:
        """실행 취소"""
        print("🛑 TV Agent 취소")


def create_tv_agent():
    """TV Agent 생성"""
    print("🏗️ TV Agent 생성...")
    
    agent_card = AgentCard(
        id="tv-agent",
        name="TV Agent",
        description="TV 제어 에이전트",
        version="1.0.0",
        url="http://localhost:18002",
        capabilities={},
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="tv_control",
                name="tv_control",
                description="TV 전원, 채널, 볼륨 제어",
                tags=["tv", "control", "power", "volume"]
            ),
            AgentSkill(
                id="channel_management",
                name="channel_management",
                description="채널 변경 및 관리",
                tags=["tv", "channel", "management"]
            )
        ]
    )
    
    executor = TVAgentExecutor()
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
    print("✅ TV Agent 생성 완료")
    
    return app