#!/usr/bin/env python3
"""
Main Agent - A2A 프로토콜 기반 오케스트레이션 에이전트
Registry 기능 통합
"""
import asyncio
import uuid
import json
import traceback
import httpx
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
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
from src.query_analyzer import QueryAnalyzer, RequestAnalysis
import logging

logger = logging.getLogger(__name__)


@dataclass
class RegisteredAgent:
    """등록된 에이전트 정보"""
    agent_id: str
    name: str
    description: str
    url: str
    agent_card: Dict[str, Any]
    skills: List[Dict[str, Any]]
    registered_at: datetime
    last_health_check: Optional[datetime] = None
    is_healthy: bool = True


class AgentRegistry:
    """에이전트 등록소 - Main Agent 내부 모듈"""
    
    def __init__(self):
        """초기화"""
        print("📋 AgentRegistry 초기화 중...")
        self.agents: Dict[str, RegisteredAgent] = {}
        self.skill_to_agents: Dict[str, List[str]] = {}  # skill_id -> [agent_id]
        print("✅ AgentRegistry 초기화 완료")

    async def register_agent(self, agent_card: Dict[str, Any]) -> bool:
        """에이전트 등록"""
        try:
            # A2A AgentCard에는 id 필드가 없으므로 URL과 name으로 고유 식별자 생성
            url = agent_card.get("url")
            name = agent_card.get("name", "Unknown")
            
            if not url:
                print("❌ Agent URL이 없습니다")
                return False
            
            # URL에서 포트 번호를 추출하여 agent_id로 사용
            import re
            port_match = re.search(r':(\d+)', url)
            if port_match:
                port = port_match.group(1)
                agent_id = f"{name.lower().replace(' ', '-')}-{port}"
            else:
                # 포트가 없으면 name만 사용
                agent_id = name.lower().replace(' ', '-')
            
            print(f"📝 에이전트 등록 중: {agent_id} ({name})")
            
            # Agent Card 유효성 검증
            if not self._validate_agent_card(agent_card):
                print(f"❌ 유효하지 않은 Agent Card: {agent_id}")
                return False
            
            # 등록된 에이전트 정보 생성
            registered_agent = RegisteredAgent(
                agent_id=agent_id,
                name=agent_card.get("name", "Unknown"),
                description=agent_card.get("description", ""),
                url=agent_card.get("url", ""),
                agent_card=agent_card,
                skills=agent_card.get("skills", []),
                registered_at=datetime.now(),
                is_healthy=True
            )
            
            # 에이전트 등록
            self.agents[agent_id] = registered_agent
            
            # 스킬 인덱스 업데이트
            self._update_skill_index(agent_id, agent_card.get("skills", []))
            
            print(f"✅ 에이전트 등록 완료: {agent_id} ({registered_agent.name})")
            return True
            
        except Exception as e:
            print(f"❌ 에이전트 등록 실패: {e}")
            return False

    async def discover_agents_by_skill(self, skill_id: str) -> List[RegisteredAgent]:
        """스킬 ID로 에이전트 발견"""
        try:
            agent_ids = self.skill_to_agents.get(skill_id, [])
            agents = []
            
            for agent_id in agent_ids:
                if agent_id in self.agents and self.agents[agent_id].is_healthy:
                    agents.append(self.agents[agent_id])
            
            print(f"🔍 스킬 '{skill_id}'로 {len(agents)}개 에이전트 발견")
            return agents
            
        except Exception as e:
            print(f"❌ 스킬 기반 에이전트 발견 실패: {e}")
            return []

    async def discover_agents_by_skills(self, skill_ids: List[str]) -> Dict[str, List[RegisteredAgent]]:
        """여러 스킬 ID로 에이전트 발견"""
        result = {}
        
        for skill_id in skill_ids:
            result[skill_id] = await self.discover_agents_by_skill(skill_id)
            
        return result

    async def get_all_agents(self) -> List[RegisteredAgent]:
        """모든 등록된 에이전트 조회"""
        return list(self.agents.values())

    async def get_registry_stats(self) -> Dict[str, Any]:
        """등록소 통계 정보 조회"""
        try:
            total_agents = len(self.agents)
            healthy_agents = sum(1 for agent in self.agents.values() if agent.is_healthy)
            skills = list(self.skill_to_agents.keys())
            
            agents_info = []
            for agent in self.agents.values():
                agents_info.append({
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "url": agent.url,
                    "skills": [skill.get("id", "unknown") for skill in agent.skills],
                    "is_healthy": agent.is_healthy,
                    "registered_at": agent.registered_at.isoformat()
                })
            
            return {
                "total_agents": total_agents,
                "healthy_agents": healthy_agents,
                "skills": skills,
                "agents": agents_info
            }
            
        except Exception as e:
            print(f"❌ 등록소 통계 조회 실패: {e}")
            return {
                "total_agents": 0,
                "healthy_agents": 0,
                "skills": [],
                "agents": [],
                "error": str(e)
            }

    def _validate_agent_card(self, agent_card: Dict[str, Any]) -> bool:
        """Agent Card 유효성 검증"""
        required_fields = ["name", "description", "url", "skills"]
        
        for field in required_fields:
            if field not in agent_card:
                print(f"❌ 필수 필드 누락: {field}")
                return False
                
        if not isinstance(agent_card.get("skills"), list):
            print("❌ skills 필드는 리스트여야 합니다")
            return False
            
        return True

    def _update_skill_index(self, agent_id: str, skills: List[Dict[str, Any]]):
        """스킬 인덱스 업데이트"""
        for skill in skills:
            skill_id = skill.get("id")
            if skill_id:
                if skill_id not in self.skill_to_agents:
                    self.skill_to_agents[skill_id] = []
                if agent_id not in self.skill_to_agents[skill_id]:
                    self.skill_to_agents[skill_id].append(agent_id)


class MainAgentExecutor(AgentExecutor):
    """메인 에이전트 실행자"""
    
    def __init__(self):
        """초기화"""
        print("🔧 MainAgentExecutor 초기화 중...")
        try:
            self.llm_client = LLMClient()
            self.prompt_loader = PromptLoader("prompt")
            self.query_analyzer = QueryAnalyzer()
            self.agent_registry = AgentRegistry() # AgentRegistry 인스턴스 생성
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
            
            # 2. 쿼리 분석 (Intent/Entity 추출)
            analysis = await self.query_analyzer.analyze_query(user_text)
            print(f"🧠 분석 결과: {analysis}")
            
            # 3. 요청 처리 및 응답
            response_text = await self._process_analyzed_request(user_text, analysis)
            
            # 4. 응답 전송
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
                
                # 방법 1: part.root.text 접근
                try:
                    if hasattr(part, 'root'):
                        root = getattr(part, 'root')
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

    async def _process_analyzed_request(self, user_text: str, analysis: RequestAnalysis) -> str:
        """분석된 요청 처리"""
        print(f"🎯 요청 처리: request_type={analysis.request_type}, domains={analysis.domains}, requires_multiple={analysis.requires_multiple_agents}")
        
        # 1. 복합 도메인 요청 처리
        if analysis.requires_multiple_agents:
            return await self._handle_multi_domain_request(user_text, analysis)
        
        # 2. 단일 도메인 요청 처리
        elif analysis.agent_skills_needed:
            return await self._handle_single_domain_request(user_text, analysis)
        
        # 3. 메인 에이전트에서 직접 처리
        else:
            return await self._handle_direct_request(user_text, analysis)

    async def _handle_multi_domain_request(self, user_text: str, analysis: RequestAnalysis) -> str:
        """복합 도메인 요청 처리 (Response Aggregator)"""
        print("🔄 복합 도메인 요청 처리 중...")
        
        try:
            # orchestration 스킬은 Main Agent 자신이 처리하므로 제외
            print(f"🔍 원래 필요 스킬: {analysis.agent_skills_needed}")
            agent_skills_needed = [skill for skill in analysis.agent_skills_needed if skill != "orchestration"]
            print(f"🔍 에이전트 호출 대상 스킬: {agent_skills_needed}")
            
            if not agent_skills_needed:
                # orchestration만 필요한 경우 직접 처리
                print("💬 orchestration만 필요하므로 Main Agent에서 직접 처리")
                return await self._handle_direct_request(user_text, analysis)
            
            # 필요한 스킬별로 에이전트 발견
            agents_by_skill = await self.agent_registry.discover_agents_by_skills(agent_skills_needed)
            
            responses = {}
            tasks = []
            
            # 각 스킬에 대해 병렬로 요청 처리
            for skill_id, agents in agents_by_skill.items():
                if agents:
                    # 첫 번째로 발견된 에이전트 사용 (향후 로드 밸런싱 고려 가능)
                    selected_agent = agents[0]
                    print(f"🎯 {skill_id} -> {selected_agent.name} ({selected_agent.url})")
                    
                    task = self._call_agent(selected_agent, user_text, skill_id)
                    tasks.append((skill_id, task))
                else:
                    print(f"⚠️ '{skill_id}' 스킬을 가진 에이전트를 찾을 수 없음")
            
            # 모든 에이전트 응답 대기
            if tasks:
                for skill_id, task in tasks:
                    try:
                        response = await task
                        responses[skill_id] = response
                        print(f"✅ {skill_id} 응답 완료")
                    except Exception as e:
                        print(f"❌ {skill_id} 응답 실패: {e}")
                        responses[skill_id] = f"{skill_id} 처리 중 오류가 발생했습니다."
            
            # 응답 집약 및 조합
            return await self._aggregate_multi_domain_responses(user_text, analysis, responses)
            
        except Exception as e:
            print(f"❌ 복합 도메인 요청 처리 실패: {e}")
            return f"복합 요청 처리 중 오류가 발생했습니다: {str(e)}"

    async def _handle_single_domain_request(self, user_text: str, analysis: RequestAnalysis) -> str:
        """단일 도메인 요청 처리"""
        print("🎯 단일 도메인 요청 처리 중...")
        
        try:
            # orchestration 스킬은 Main Agent 자신이 처리하므로 제외
            agent_skills_needed = [skill for skill in analysis.agent_skills_needed if skill != "orchestration"]
            
            if not agent_skills_needed:
                # orchestration만 필요한 경우 직접 처리
                return await self._handle_direct_request(user_text, analysis)
            
            skill_id = agent_skills_needed[0]  # 첫 번째 스킬 사용
            agents = await self.agent_registry.discover_agents_by_skill(skill_id)
            
            if not agents:
                return f"'{skill_id}' 스킬을 가진 에이전트를 찾을 수 없습니다."
            
            # 첫 번째로 발견된 에이전트 사용
            selected_agent = agents[0]
            print(f"🎯 선택된 에이전트: {selected_agent.name} ({selected_agent.url})")
            
            response = await self._call_agent(selected_agent, user_text, skill_id)
            return response
            
        except Exception as e:
            print(f"❌ 단일 도메인 요청 처리 실패: {e}")
            return f"요청 처리 중 오류가 발생했습니다: {str(e)}"

    async def _handle_direct_request(self, user_text: str, analysis: RequestAnalysis) -> str:
        """메인 에이전트에서 직접 처리"""
        print("💬 메인 에이전트에서 직접 처리...")
        
        # 도메인 기반 처리
        primary_domain = analysis.domains[0] if analysis.domains else "general_chat"
        
        if primary_domain == "general_chat":
            # 채팅 타입 엔티티 확인
            chat_type = None
            for entity in analysis.entities:
                if entity.entity_type == "chat_type":
                    chat_type = entity.value
                    break
            
            if chat_type == "greeting":
                return "안녕하세요! 저는 멀티 에이전트 시스템의 오케스트레이터입니다. 무엇을 도와드릴까요?"
            elif chat_type == "thanks":
                return "천만에요! 도움이 되어서 기뻐요. 다른 도움이 필요하시면 언제든 말씀해주세요."
            elif chat_type == "help":
                return await self._generate_help_response()
            else:
                return f"안녕하세요! 저는 다양한 서비스 에이전트들과 협력하여 업무를 처리하는 오케스트레이터입니다. 현재 날씨 정보 제공과 TV 제어 기능을 지원합니다. (입력: '{user_text}')"
        else:
            return f"죄송합니다. '{user_text}' 요청을 처리할 수 있는 적절한 에이전트를 찾지 못했습니다."

    async def _call_agent(self, agent: RegisteredAgent, user_text: str, skill_context: str = "") -> str:
        """에이전트 호출"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": user_text}],
                        "messageId": str(uuid.uuid4())
                    },
                    "metadata": {
                        "skill_context": skill_context,
                        "orchestrator": "main-agent"
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{agent.url}/",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                
                print(f"📡 {agent.name} 응답 상태: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # 응답에서 텍스트 추출
                    if "result" in result:
                        result_data = result["result"]
                        
                        # Direct message response
                        if result_data.get("kind") == "message" and "parts" in result_data:
                            for part in result_data["parts"]:
                                if isinstance(part, dict) and part.get("kind") == "text":
                                    return part.get("text", f"{agent.name}에서 응답을 받았습니다.")
                        
                        # Task response with artifacts
                        elif "artifacts" in result_data:
                            artifacts = result_data["artifacts"]
                            for artifact in artifacts:
                                if "parts" in artifact:
                                    for part in artifact["parts"]:
                                        if isinstance(part, dict) and part.get("kind") == "text":
                                            return part.get("text", f"{agent.name}에서 응답을 받았습니다.")
                        
                        # Task response with direct parts
                        elif "parts" in result_data:
                            for part in result_data["parts"]:
                                if isinstance(part, dict) and part.get("kind") == "text":
                                    return part.get("text", f"{agent.name}에서 응답을 받았습니다.")
                    
                    return f"{agent.name}에서 응답을 처리했습니다."
                else:
                    print(f"❌ {agent.name} 요청 실패: {response.text}")
                    return f"{agent.name} 요청이 실패했습니다. (상태: {response.status_code})"
                    
        except Exception as e:
            print(f"❌ {agent.name} 통신 오류: {e}")
            return f"{agent.name}와의 통신 중 오류가 발생했습니다."

    async def _aggregate_multi_domain_responses(self, user_text: str, analysis: RequestAnalysis, responses: Dict[str, str]) -> str:
        """복합 도메인 응답 집약 및 조합"""
        print("🔗 복합 도메인 응답 집약 중...")
        
        try:
            # 특별한 도메인 조합 처리
            if "weather" in analysis.domains and "tv_control" in analysis.domains:
                return await self._handle_weather_tv_combo(user_text, analysis, responses)
            
            # 일반적인 응답 조합
            combined_response = "여러 도메인의 응답을 종합한 결과입니다:\n\n"
            
            for skill_id, response in responses.items():
                skill_name = skill_id.replace("_", " ").title()
                combined_response += f"🔸 {skill_name}: {response}\n"
            
            return combined_response.strip()
            
        except Exception as e:
            print(f"❌ 복합 도메인 응답 집약 실패: {e}")
            return f"응답 집약 중 오류가 발생했습니다: {str(e)}"

    async def _handle_weather_tv_combo(self, user_text: str, analysis: RequestAnalysis, responses: Dict[str, str]) -> str:
        """날씨-TV 복합 요청 처리"""
        print("🌤️📺 날씨-TV 복합 요청 처리...")
        
        weather_response = responses.get("weather_info", "날씨 정보를 가져올 수 없습니다.")
        tv_response = responses.get("tv_control", "TV 제어 기능이 현재 사용할 수 없습니다.")
        
        # LLM을 사용해서 더 자연스러운 응답 생성
        try:
            # orchestration prompt 사용 또는 간단한 복합 응답 프롬프트 생성
            system_prompt = """당신은 멀티 에이전트 시스템의 응답 집약기입니다.
사용자의 복합 요청에 대해 날씨 에이전트와 TV 에이전트의 응답을 종합하여 
자연스럽고 유용한 통합 응답을 생성해주세요.

응답 규칙:
1. 날씨 정보와 TV 제어 결과를 자연스럽게 연결
2. 사용자의 의도를 고려한 개인화된 제안 포함
3. 친근하고 도움이 되는 톤 사용
4. 구체적이고 실용적인 정보 제공"""

            user_prompt = f"""사용자 요청: "{user_text}"
요청 유형: {analysis.request_type}
관련 도메인: {analysis.domains}
추출된 엔티티: {[f"{e.entity_type}: {e.value}" for e in analysis.entities]}

날씨 에이전트 응답: {weather_response}
TV 에이전트 응답: {tv_response}

위 정보를 바탕으로 사용자의 복합 요청에 대한 통합된 응답을 생성해주세요."""

            orchestrated_response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=400
            )
            
            print(f"✅ LLM 기반 복합 응답 생성 완료")
            return orchestrated_response
                
        except Exception as e:
            print(f"❌ LLM 기반 오케스트레이션 실패: {e}")
            # 백업 응답: 구조화된 응답
            pass
        
        # 백업 응답: 키워드 기반 맞춤형 응답
        user_lower = user_text.lower()
        
        # 채널 변경 관련 요청
        if any(word in user_lower for word in ["채널", "channel", "방송"]):
            return f"""🌤️ **오늘 날씨 정보**
{weather_response}

📺 **TV 채널 설정**
{tv_response}

💡 **추천 사항**
현재 날씨가 좋으니 가족과 함께 즐길 수 있는 예능이나 여행 프로그램을 시청해보시는 것은 어떨까요?"""

        # 볼륨 조절 관련 요청
        elif any(word in user_lower for word in ["볼륨", "volume", "소리"]):
            return f"""🌤️ **오늘 날씨 정보**
{weather_response}

📺 **TV 볼륨 설정**
{tv_response}

💡 **추천 사항**
좋은 날씨에는 창문을 열어두시는 경우가 많으니, 외부 소음을 고려해서 적절한 볼륨으로 조절하시면 좋겠어요!"""

        # 일반적인 복합 응답
        else:
            return f"""🌤️ **날씨 정보**
{weather_response}

📺 **TV 제어 결과**
{tv_response}

💡 **종합 제안**
현재 날씨를 고려하여 TV 설정을 조정해드렸습니다. 편안한 시청 환경을 즐기세요!"""

    async def _generate_help_response(self) -> str:
        """도움말 응답 생성"""
        try:
            # 등록된 에이전트 정보 조회
            stats = await self.agent_registry.get_registry_stats()
            
            help_text = "🤖 **멀티 에이전트 시스템 도움말**\n\n"
            help_text += f"현재 {stats['healthy_agents']}개의 에이전트가 활성 상태입니다.\n\n"
            help_text += "**사용 가능한 기능:**\n"
            
            # 스킬별 기능 설명
            skills_info = {
                "weather_info": "🌤️ 날씨 정보 조회 (예: '오늘 서울 날씨 어때?')",
                "tv_control": "📺 TV 제어 (예: 'TV 볼륨 올려줘', '채널 바꿔줘')",
                "orchestration": "🔗 복합 기능 (예: '오늘 날씨에 어울리는 볼륨으로 조절해줄래?')"
            }
            
            for skill_id in stats['skills']:
                if skill_id in skills_info:
                    help_text += f"• {skills_info[skill_id]}\n"
            
            help_text += "\n**등록된 에이전트:**\n"
            for agent_info in stats['agents']:
                status = "🟢" if agent_info['is_healthy'] else "🔴"
                help_text += f"{status} {agent_info['name']}: {', '.join(agent_info['skills'])}\n"
            
            return help_text
            
        except Exception as e:
            print(f"❌ 도움말 생성 실패: {e}")
            return "저는 다양한 에이전트들과 협력하는 오케스트레이터입니다. 날씨 정보, TV 제어 등의 기능을 제공합니다."

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

    async def get_registry_info(self) -> Dict[str, Any]:
        """레지스트리 정보 조회 (API 용도)"""
        return await self.agent_registry.get_registry_stats()


def create_main_agent():
    """Main Agent 생성"""
    print("🏗️ Main Agent 생성...")
    
    agent_card = AgentCard(
        name="Main Agent",
        description="A2A 프로토콜 기반 메인 오케스트레이션 에이전트",
        version="1.0.0",
        url="http://localhost:18000",
        capabilities={
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": True
        },
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="orchestration",
                name="Orchestration",
                description="사용자 요청을 분석하고 적절한 에이전트로 라우팅하며 복합 응답을 집약",
                tags=["orchestration", "routing", "aggregation", "coordination"]
            ),
            AgentSkill(
                id="agent_registry",
                name="Agent Registry",
                description="에이전트 등록 및 발견 서비스 제공",
                tags=["registry", "discovery", "management"]
            ),
            AgentSkill(
                id="chit_chat",
                name="General Chat",
                description="일반적인 대화 및 시스템 정보 제공",
                tags=["chat", "conversation", "help"]
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
    
    # Starlette 방식으로 API 엔드포인트 추가
    from starlette.routing import Route
    from starlette.responses import JSONResponse
    from starlette.requests import Request
    
    async def register_service_agent(request: Request):
        """Service Agent 등록 API"""
        try:
            agent_data = await request.json()
            print(f"📝 Service Agent 등록 요청: {agent_data.get('name', 'Unknown')}")
            
            registry = executor.agent_registry
            success = await registry.register_agent(agent_data)
            
            if success:
                print(f"✅ Service Agent 등록 성공: {agent_data.get('name', 'Unknown')}")
                return JSONResponse({"success": True, "message": "Agent registered successfully"})
            else:
                print(f"❌ Service Agent 등록 실패: {agent_data.get('name', 'Unknown')}")
                return JSONResponse({"success": False, "message": "Agent registration failed"})
                
        except Exception as e:
            print(f"❌ Service Agent 등록 오류: {e}")
            return JSONResponse({"success": False, "message": f"Registration error: {str(e)}"})
    
    async def get_registered_agents(request: Request):
        """등록된 에이전트 목록 조회 API"""
        try:
            registry = executor.agent_registry
            agents = await registry.get_all_agents()
            
            agents_info = []
            for agent in agents:
                agents_info.append({
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "description": agent.description,
                    "url": agent.url,
                    "skills": [skill.get("id", "unknown") for skill in agent.skills],
                    "is_healthy": agent.is_healthy,
                    "registered_at": agent.registered_at.isoformat()
                })
                
            return JSONResponse({"agents": agents_info, "count": len(agents_info)})
            
        except Exception as e:
            print(f"❌ 등록된 에이전트 조회 오류: {e}")
            return JSONResponse({"agents": [], "count": 0, "error": str(e)})
    
    # 라우터에 엔드포인트 추가
    app.router.routes.extend([
        Route("/api/registry/register", register_service_agent, methods=["POST"]),
        Route("/api/registry/agents", get_registered_agents, methods=["GET"])
    ])
    
    async def register_main_agent():
        """Main Agent 자기 자신을 registry에 등록"""
        try:
            registry = executor.agent_registry
            await registry.register_agent(agent_card.model_dump())
            print("✅ Main Agent 자체 등록 완료")
        except Exception as e:
            print(f"❌ Main Agent 자체 등록 실패: {e}")
    
    print("✅ Main Agent 생성 완료")

    @app.on_event("startup")
    async def startup_event():
        await register_main_agent()
    
    return app