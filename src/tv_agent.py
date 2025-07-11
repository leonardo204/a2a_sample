#!/usr/bin/env python3
"""
TV Agent - TV 제어 전담 에이전트
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

class TVAgentExecutor(AgentExecutor):
    """TV 에이전트 실행자"""
    
    def __init__(self):
        """초기화"""
        print("📺 TVAgentExecutor 초기화...")
        try:
            self.llm_client = LLMClient()
            self.prompt_loader = PromptLoader("prompt")
            print("✅ TVAgentExecutor 초기화 완료")
        except Exception as e:
            print(f"❌ TVAgentExecutor 초기화 실패: {e}")
            raise

    async def execute(self, context: RequestContext, queue: EventQueue) -> None:
        """메시지 실행 처리"""
        
        print("\n" + "=" * 50)
        print("📺 TV AGENT 실행 시작")
        print("=" * 50)
        
        try:
            # 1. 사용자 메시지 추출
            user_text = await self._extract_user_message(context)
            
            if not user_text:
                print("❌ 메시지 추출 실패")
                await self._send_response(context, queue, "안녕하세요! TV 제어를 도와드릴 수 있습니다.")
                return
            
            print(f"✅ 추출된 메시지: '{user_text}'")
            
            # 2. Agent 컨텍스트 정보 추출
            agent_contexts = self._extract_agent_contexts(user_text)
            
            # 3. TV 제어 요청 처리
            response_text = await self._process_tv_request(user_text, agent_contexts)
            
            # 3. 응답 전송
            await self._send_response(context, queue, response_text)
            
            print("✅ TV 제어 처리 완료!")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            await self._send_response(context, queue, f"TV 제어 처리 중 오류가 발생했습니다: {str(e)}")

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

    async def _process_tv_request(self, user_text: str, agent_contexts: list = None) -> str:
        """TV 제어 요청 처리 - Agent Card 기반 동적 맥락 이해"""
        print(f"📺 TV 제어 요청 분석 중: '{user_text}'")
        
        try:
            # 다른 Agent 결과가 있으면 LLM으로 동적 해석
            if agent_contexts:
                print(f"🔄 다른 Agent 컨텍스트 감지: {len(agent_contexts)}개")
                result = await self._process_tv_request_with_context(user_text, agent_contexts)
            else:
                # 단순 TV 제어 요청
                result = await self._process_simple_tv_request(user_text)
            
            return result
            
        except Exception as e:
            print(f"❌ TV 제어 요청 처리 실패: {e}")
            return f"죄송합니다. TV 제어 처리 중 오류가 발생했습니다."
    
    async def _process_tv_request_with_context(self, user_text: str, agent_contexts: list) -> str:
        """LLM을 사용해 다른 Agent 결과를 동적으로 해석하여 TV 제어"""
        print("🤖 LLM 기반 동적 컨텍스트 처리 시작")
        
        try:
            # Agent 컨텍스트를 LLM 프롬프트로 구성
            context_prompt = self._build_agent_context_prompt(agent_contexts)
            
            system_prompt = f"""당신은 TV 제어 전문 에이전트입니다.

사용자의 TV 제어 요청과 함께 다른 에이전트들의 실행 결과가 제공됩니다.
각 에이전트의 Agent Card 정보(skills, tags, entity_types)를 참고하여
해당 결과가 TV 제어에 어떻게 활용될 수 있는지 동적으로 판단하세요.

{context_prompt}

응답은 반드시 JSON 형태로 제공해주세요:
{{
    "action_analysis": "수행할 TV 액션 분석",
    "context_integration": "다른 Agent 결과를 어떻게 활용할지",
    "response": "사용자에게 전달할 최종 응답"
}}"""

            user_prompt = f"""사용자 요청: "{user_text}"

위의 다른 에이전트 결과들을 참고하여 적절한 TV 제어를 수행하고 자연스러운 응답을 생성해주세요."""

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
                return result.get("response", "TV 제어를 완료했습니다.")
            except json.JSONDecodeError:
                print(f"❌ JSON 파싱 실패, 원본 응답 사용: {response}")
                return response.strip()
                
        except Exception as e:
            print(f"❌ LLM 컨텍스트 처리 실패: {e}")
            # 백업으로 단순 처리
            return await self._process_simple_tv_request(user_text)

    async def _process_simple_tv_request(self, user_text: str) -> str:
        """단순 TV 제어 요청 처리"""
        print("📺 단순 TV 제어 처리")
        
        try:
            # TV 액션 분석
            action_info = self._analyze_tv_action(user_text)
            print(f"🎯 분석된 액션: {action_info}")
            
            # LLM을 사용한 자연스러운 응답 생성
            response = await self._generate_simple_tv_response(action_info, user_text)
            return response
            
        except Exception as e:
            print(f"❌ 단순 TV 처리 실패: {e}")
            return self._generate_fallback_tv_response(action_info.get("action_type", "unknown"), {})

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

    async def _generate_simple_tv_response(self, action_info: dict, user_text: str) -> str:
        """단순 TV 제어를 위한 LLM 응답 생성"""
        try:
            prompt_data = self.prompt_loader.load_prompt("tv_agent", "tv_control")
            
            # 시뮬레이션된 현재 TV 상태
            current_channel = 1
            current_volume = 20
            
            formatted_prompt = prompt_data["user_prompt_template"].format(
                original_request=user_text,
                action=action_info["action_type"],
                parameters=json.dumps(action_info.get("parameters", {}), ensure_ascii=False),
                current_channel=current_channel,
                current_volume=current_volume
            )
            
            response = await self.llm_client.chat_completion(
                system_prompt=prompt_data["system_prompt"],
                user_prompt=formatted_prompt,
                max_tokens=300
            )
            
            # JSON 응답 파싱 시도
            try:
                response_clean = response.strip()
                if response_clean.startswith('```json'):
                    response_clean = response_clean[7:]
                if response_clean.endswith('```'):
                    response_clean = response_clean[:-3]
                response_clean = response_clean.strip()
                
                parsed_response = json.loads(response_clean)
                return parsed_response.get("response", response_clean)
                
            except json.JSONDecodeError:
                print(f"⚠️ JSON 파싱 실패, 원본 응답 사용: {response}")
                return response.strip()
            
        except Exception as e:
            print(f"❌ 단순 TV 응답 생성 실패: {e}")
            return self._generate_fallback_tv_response(action_info["action_type"], action_info.get("parameters", {}))

    def _analyze_tv_action(self, user_text: str) -> dict:
        """TV 액션 분석"""
        user_lower = user_text.lower()
        
        action_info = {
            "action_type": "unknown",
            "parameters": {},
            "device": "main_tv"
        }
        
        # 전원 제어
        if any(word in user_lower for word in ["켜", "on", "전원 켜"]):
            action_info["action_type"] = "power_on"
        elif any(word in user_lower for word in ["꺼", "off", "전원 꺼"]):
            action_info["action_type"] = "power_off"
        
        # 볼륨 제어
        elif any(word in user_lower for word in ["볼륨", "volume"]):
            if any(word in user_lower for word in ["올려", "up", "크게", "키워"]):
                action_info["action_type"] = "volume_up"
                # 숫자 추출 시도
                volume_level = self._extract_volume_level(user_text)
                if volume_level:
                    action_info["parameters"]["level"] = volume_level
            elif any(word in user_lower for word in ["내려", "down", "작게", "줄여"]):
                action_info["action_type"] = "volume_down"
                volume_level = self._extract_volume_level(user_text)
                if volume_level:
                    action_info["parameters"]["level"] = volume_level
            else:
                action_info["action_type"] = "volume_control"
        
        # 채널 제어
        elif any(word in user_lower for word in ["채널", "channel", "방송"]):
            if any(word in user_lower for word in ["바꿔", "변경", "돌려", "적절한", "어울리는"]):
                action_info["action_type"] = "channel_control"
                channel_num = self._extract_channel_number(user_text)
                if channel_num:
                    action_info["parameters"]["channel"] = channel_num
            elif any(word in user_lower for word in ["올려", "다음"]):
                action_info["action_type"] = "channel_up"
            elif any(word in user_lower for word in ["내려", "이전"]):
                action_info["action_type"] = "channel_down"
        
        # 입력 소스 변경
        elif any(word in user_lower for word in ["hdmi", "입력", "소스"]):
            action_info["action_type"] = "input_change"
            if "hdmi" in user_lower:
                hdmi_num = self._extract_hdmi_number(user_text)
                if hdmi_num:
                    action_info["parameters"]["input"] = f"HDMI{hdmi_num}"
        
        # 음소거
        elif any(word in user_lower for word in ["음소거", "mute", "조용히"]):
            action_info["action_type"] = "mute_toggle"
        
        return action_info

    def _extract_volume_level(self, text: str) -> int:
        """볼륨 레벨 추출"""
        import re
        numbers = re.findall(r'\b(\d+)\b', text)
        if numbers:
            level = int(numbers[0])
            return min(max(level, 0), 100)  # 0-100 범위 제한
        return None

    def _extract_channel_number(self, text: str) -> int:
        """채널 번호 추출"""
        import re
        numbers = re.findall(r'\b(\d+)\b', text)
        if numbers:
            return int(numbers[0])
        return None

    def _extract_hdmi_number(self, text: str) -> int:
        """HDMI 번호 추출"""
        import re
        hdmi_match = re.search(r'hdmi\s*(\d+)', text.lower())
        if hdmi_match:
            return int(hdmi_match.group(1))
        return 1  # 기본값





    def _generate_fallback_tv_response(self, action_type: str, parameters: dict) -> str:
        """백업 TV 제어 응답 생성"""        
        responses = {
            "power_on": "📺 TV 전원을 켰습니다.",
            "power_off": "📺 TV 전원을 껐습니다.",
            "volume_up": f"🔊 볼륨을 올렸습니다{(' (' + str(parameters.get('level', '기본')) + ' 수준으로)') if parameters.get('level') else ''}.",
            "volume_down": f"🔉 볼륨을 내렸습니다{(' (' + str(parameters.get('level', '기본')) + ' 수준으로)') if parameters.get('level') else ''}.",
            "volume_control": "🔊 볼륨을 조절했습니다.",
            "channel_change": f"📺 채널을 변경했습니다{(' (' + str(parameters.get('channel', '')) + '번으로)') if parameters.get('channel') else ''}.",
            "channel_up": "📺 다음 채널로 변경했습니다.",
            "channel_down": "📺 이전 채널로 변경했습니다.",
            "input_change": f"📺 입력을 변경했습니다{(' (' + str(parameters.get('input', '')) + '으로)') if parameters.get('input') else ''}.",
            "mute_toggle": "🔇 음소거를 전환했습니다.",
            "unknown": "📺 TV 제어 명령을 처리했습니다."
        }
        
        return responses.get(action_type, responses["unknown"])

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
    print(f"📝 Main Agent Registry에 TV Agent 등록 중...")
    
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
                        print("✅ TV Agent Registry 등록 완료")
                        return True
                    else:
                        print(f"❌ TV Agent Registry 등록 실패: {result.get('message', 'Unknown error')}")
                        return False
                else:
                    print(f"⚠️ 등록 시도 {attempt + 1}/{max_retries} 실패 (HTTP {response.status_code})")
                    if attempt < max_retries - 1:
                        print(f"   {retry_delay}초 후 재시도...")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        print(f"❌ TV Agent Registry 등록 최종 실패")
                        return False
                        
        except Exception as e:
            print(f"⚠️ 등록 시도 {attempt + 1}/{max_retries} 오류: {e}")
            if attempt < max_retries - 1:
                print(f"   {retry_delay}초 후 재시도...")
                await asyncio.sleep(retry_delay)
                continue
            else:
                print(f"❌ TV Agent Registry 등록 최종 실패: {e}")
                return False
    
    return False


def create_tv_agent():
    """TV Agent 생성"""
    print("🏗️ TV Agent 생성...")
    
    agent_card = AgentCard(
        name="TV Agent",
        description="TV 제어 전담 에이전트 - A2A 프로토콜 지원",
        version="1.0.0",
        url="http://localhost:18002",
        capabilities={
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": False
        },
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="tv",
                name="TV Control Service",
                description="TV 제어 및 설정 통합 서비스",
                tags=["tv", "control", "settings", "power", "volume", "channel", "remote"]
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
    
    # 서버 시작 이벤트에 등록 함수 추가
    @app.on_event("startup")
    async def startup_event():
        # 확장된 정보를 포함하여 등록
        extended_agent_card = agent_card.model_dump()
        extended_agent_card["extended_skills"] = [
            ExtendedAgentSkill(
                id="tv",
                name="TV Control Service",
                description="TV 제어 및 설정 통합 서비스",
                tags=["tv", "control", "settings", "power", "volume", "channel", "remote"],
                domain_category="tv",
                keywords=["TV", "티비", "텔레비전", "볼륨", "채널", "켜기", "끄기", "음량", "소리", "방송", "리모컨", "설정", "세팅"],
                entity_types=[
                    EntityTypeInfo("action", "TV 동작", ["volume_up", "volume_down", "channel_control", "power_on", "power_off"]),
                    EntityTypeInfo("channel", "채널 번호", ["1", "2", "3", "7", "9", "11", "MBC", "SBS", "KBS", "tvN"]),
                    EntityTypeInfo("volume_level", "볼륨 수준", ["5", "10", "15", "20", "최대", "최소", "크게", "작게"]),
                    EntityTypeInfo("setting_type", "설정 타입", ["화질", "음질", "밝기", "명암", "색상"]),
                    EntityTypeInfo("setting_value", "설정 값", ["높음", "중간", "낮음", "자동", "수동"])
                ],
                intent_patterns=["TV 제어", "리모컨 조작", "방송 조작", "TV 설정", "설정 변경", "tv control", "tv settings"],
                connection_patterns=["어울리는", "맞는", "적절한", "조절", "기반으로", "맞춰서"]
            ).to_dict()
        ]
        await register_to_main_agent(extended_agent_card)
    
    return app