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
from src.dynamic_prompt_manager import DynamicPromptManager
from src.dynamic_query_analyzer import DynamicQueryAnalyzer, RequestAnalysis
from src.extended_agent_card import ExtendedAgentSkill, EntityTypeInfo
from src.context_manager import ContextManager
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
        self.prompt_manager = None  # 나중에 설정됨
        print("✅ AgentRegistry 초기화 완료")
    
    def set_prompt_manager(self, prompt_manager):
        """프롬프트 매니저 설정 (초기화 이후에 설정)"""
        self.prompt_manager = prompt_manager
        print("🔗 AgentRegistry에 PromptManager 연결 완료")

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
            
            # 프롬프트 매니저에 에이전트 등록 알림
            if self.prompt_manager:
                try:
                    await self.prompt_manager.on_agent_registered(agent_card)
                except Exception as e:
                    print(f"⚠️ 프롬프트 업데이트 실패: {e}")
            
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
            self.agent_registry = AgentRegistry() # AgentRegistry 인스턴스 생성
            self.context_manager = ContextManager() # ContextManager 인스턴스 생성
            
            # 동적 프롬프트 시스템 초기화 (skeleton → complete 방식)
            self.prompt_manager = DynamicPromptManager(self.agent_registry)
            self.query_analyzer = DynamicQueryAnalyzer(self.prompt_manager)
            
            # AgentRegistry에 PromptManager 연결
            self.agent_registry.set_prompt_manager(self.prompt_manager)
            
            print("✅ MainAgentExecutor 초기화 완료 (동적 프롬프트 시스템 + ContextManager 적용)")
        except Exception as e:
            print(f"❌ 초기화 실패: {e}")
            raise
    
    def _clean_json_response(self, response: str) -> str:
        """LLM 응답에서 JSON 부분만 추출"""
        response = response.strip()
        
        # ```json 코드 블록 제거
        if response.startswith("```json"):
            response = response[7:]  # ```json 제거
        if response.startswith("```"):
            response = response[3:]  # ``` 제거
        if response.endswith("```"):
            response = response[:-3]  # ``` 제거
        
        return response.strip()
    
    async def _get_entities_from_last_analysis(self, user_query: str) -> List:
        """Agent Card 기반 엔티티 정보 추출"""
        try:
            # Agent Card에서 등록된 엔티티 정보 기반으로 분석
            entities = []
            
            # 등록된 Agent Card에서 엔티티 타입 가져오기
            registered_agents = await self.agent_registry.get_all_agents()
            
            for agent in registered_agents:
                extended_skills = agent.agent_card.get("extended_skills", [])
                for skill in extended_skills:
                    entity_types = skill.get("entity_types", [])
                    for entity_type_info in entity_types:
                        entity_name = entity_type_info.get("name", "")
                        examples = entity_type_info.get("examples", [])
                        
                        # 예시 중 하나가 사용자 쿼리에 포함되어 있는지 확인
                        for example in examples:
                            if example in user_query:
                                entities.append({
                                    "entity_type": entity_name,
                                    "value": example,
                                    "confidence": 0.8
                                })
                                break  # 해당 엔티티 타입에서 첫 번째 매치만 사용
            
            return entities
            
        except Exception as e:
            print(f"❌ Agent Card 기반 엔티티 정보 추출 실패: {e}")
            return []

    async def execute(self, context: RequestContext, queue: EventQueue) -> None:
        """메시지 실행 처리"""
        
        print("\n" + "=" * 60)
        print("🚀 MAIN AGENT 실행 시작")
        print("=" * 60)
        
        session_id = None
        try:
            # 1. 사용자 메시지 추출
            user_text = await self._extract_user_message(context)
            
            if not user_text:
                print("❌ 메시지 추출 실패")
                await self._send_response(context, queue, "안녕하세요! 무엇을 도와드릴까요?")
                return
            
            print(f"✅ 추출된 메시지: '{user_text}'")
            
            # 2. 컨텍스트 세션 생성
            session_id = self.context_manager.create_session(user_text)
            
            # 3. 쿼리 분석 (Intent/Entity 추출)
            analysis = await self.query_analyzer.analyze_query(user_text)
            print(f"🧠 분석 결과: {analysis}")
            
            # 4. 요청 처리 및 응답 (세션 ID 전달)
            response_text = await self._process_analyzed_request(user_text, analysis, session_id)
            
            # 5. 응답 전송
            await self._send_response(context, queue, response_text)
            
            print("✅ 처리 완료!")
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            await self._send_response(context, queue, f"처리 중 오류가 발생했습니다: {str(e)}")
        finally:
            # 세션 정리 (선택사항 - 짧은 세션의 경우)
            if session_id:
                # 단일 요청이므로 즉시 정리 (복합 요청은 유지할 수도 있음)
                self.context_manager.cleanup_session(session_id)

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

    async def _process_analyzed_request(self, user_text: str, analysis: RequestAnalysis, session_id: str) -> str:
        """분석된 요청 처리"""
        print(f"🎯 요청 처리: request_type={analysis.request_type}, domains={analysis.domains}, requires_multiple={analysis.requires_multiple_agents}")
        
        # 1. 복합 도메인 요청 처리
        if analysis.requires_multiple_agents:
            return await self._handle_multi_domain_request(user_text, analysis, session_id)
        
        # 2. 단일 도메인 요청 처리
        elif analysis.agent_skills_needed:
            return await self._handle_single_domain_request(user_text, analysis, session_id)
        
        # 3. 메인 에이전트에서 직접 처리
        else:
            return await self._handle_direct_request(user_text, analysis)

    async def _handle_multi_domain_request(self, user_text: str, analysis: RequestAnalysis, session_id: str) -> str:
        """복합 도메인 요청 처리 (Response Aggregator)"""
        print("🔄 복합 도메인 요청 처리 중...")
        
        try:
            # Main Agent 자신이 처리하는 스킬들 제외
            main_agent_skills = ["orchestration", "chit_chat", "agent_registry"]
            print(f"🔍 원래 필요 스킬: {analysis.agent_skills_needed}")
            agent_skills_needed = [skill for skill in analysis.agent_skills_needed if skill not in main_agent_skills]
            print(f"🔍 에이전트 호출 대상 스킬: {agent_skills_needed}")
            
            if not agent_skills_needed:
                # Main Agent 자신이 처리하는 스킬들만 필요한 경우 직접 처리
                print("💬 Main Agent 자신이 처리하는 스킬들만 필요하므로 직접 처리")
                return await self._handle_direct_request(user_text, analysis)
            
            # Dependency 감지 및 실행 순서 결정
            execution_plan = await self._analyze_execution_dependencies(user_text, analysis, agent_skills_needed)
            
            if execution_plan["is_sequential"]:
                # 순차 실행
                return await self._execute_sequential_agents(user_text, analysis, execution_plan, session_id)
            else:
                # 병렬 실행 (기존 로직)
                return await self._execute_parallel_agents(user_text, analysis, agent_skills_needed, session_id)
            
        except Exception as e:
            print(f"❌ 복합 도메인 요청 처리 실패: {e}")
            return f"복합 요청 처리 중 오류가 발생했습니다: {str(e)}"

    async def _handle_single_domain_request(self, user_text: str, analysis: RequestAnalysis, session_id: str) -> str:
        """단일 도메인 요청 처리"""
        print("🎯 단일 도메인 요청 처리 중...")
        
        try:
            # Main Agent 자신이 처리하는 스킬들 제외
            main_agent_skills = ["orchestration", "chit_chat", "agent_registry"]
            agent_skills_needed = [skill for skill in analysis.agent_skills_needed if skill not in main_agent_skills]
            
            if not agent_skills_needed:
                # Main Agent 자신이 처리하는 스킬인 경우 직접 처리
                return await self._handle_direct_request(user_text, analysis)
            
            skill_id = agent_skills_needed[0]  # 첫 번째 스킬 사용
            agents = await self.agent_registry.discover_agents_by_skill(skill_id)
            
            if not agents:
                return f"'{skill_id}' 스킬을 가진 에이전트를 찾을 수 없습니다."
            
            # 첫 번째로 발견된 에이전트 사용
            selected_agent = agents[0]
            print(f"🎯 선택된 에이전트: {selected_agent.name} ({selected_agent.url})")
            
            response = await self._call_agent(selected_agent, user_text, skill_id)
            
            # 에이전트 응답을 컨텍스트에 저장
            self.context_manager.store_agent_response(session_id, skill_id, response)
            
            return response
            
        except Exception as e:
            print(f"❌ 단일 도메인 요청 처리 실패: {e}")
            return f"요청 처리 중 오류가 발생했습니다: {str(e)}"

    async def _analyze_execution_dependencies(self, user_text: str, analysis: RequestAnalysis, agent_skills_needed: List[str]) -> Dict[str, Any]:
        """실행 dependency 분석 및 순서 결정 (Agent Card 기반)"""
        print("🔍 Dependency 분석 중...")
        
        # Entity 기반 dependency 감지
        connection_type = None
        coordination_type = None
        
        for entity in analysis.entities:
            if entity.entity_type == "connection_type":
                connection_type = entity.value
            elif entity.entity_type == "coordination_type":
                coordination_type = entity.value
        
        print(f"🔗 Connection Type: {connection_type}")
        print(f"🎯 Coordination Type: {coordination_type}")
        
        # Agent Card 기반 dependency 분석
        dependency_info = await self._analyze_agent_dependencies(agent_skills_needed, connection_type, coordination_type)
        
        return {
            "is_sequential": dependency_info["is_sequential"],
            "execution_order": dependency_info["execution_order"],
            "connection_type": connection_type,
            "coordination_type": coordination_type,
            "dependency_reasoning": dependency_info["reasoning"]
        }

    async def _analyze_agent_dependencies(self, agent_skills_needed: List[str], connection_type: str, coordination_type: str) -> Dict[str, Any]:
        """LLM 기반 Agent dependency 분석"""
        print("🔍 LLM 기반 Agent dependency 분석 중...")
        
        # 등록된 Agent들의 확장 정보 가져오기
        registered_agents = await self.agent_registry.get_all_agents()
        
        # 스킬별 Agent 정보 매핑
        skill_to_agent_info = {}
        for agent in registered_agents:
            extended_skills = agent.agent_card.get("extended_skills", [])
            for skill_data in extended_skills:
                skill_id = skill_data.get("id")
                if skill_id in agent_skills_needed:
                    skill_to_agent_info[skill_id] = {
                        "agent_name": agent.name,
                        "domain_category": skill_data.get("domain_category"),
                        "connection_patterns": skill_data.get("connection_patterns", []),
                        "skill_data": skill_data
                    }
        
        print(f"📋 발견된 스킬-Agent 매핑: {list(skill_to_agent_info.keys())}")
        
        # LLM 기반 의존성 분석
        try:
            # 분석용 정보 포맷팅
            agents_info = []
            for skill_id, agent_info in skill_to_agent_info.items():
                agent_name = agent_info.get("agent_name", "Unknown")
                domain_category = agent_info.get("domain_category", "")
                connection_patterns = agent_info.get("connection_patterns", [])
                
                agent_text = f"- {skill_id}: {agent_name}"
                if domain_category:
                    agent_text += f" (도메인: {domain_category})"
                if connection_patterns:
                    agent_text += f" (연결패턴: {', '.join(connection_patterns)})"
                
                agents_info.append(agent_text)
            
            system_prompt = """당신은 멀티 에이전트 시스템의 의존성 분석 전문가입니다.

에이전트 간의 실행 순서와 의존성을 분석해주세요.

분석 기준:
1. coordination_type이 "conditional"인 경우 순차 실행 필요
2. connection_type이 있고 관련 connection_patterns와 매칭되는 경우 순차 실행 필요  
3. 정보 제공 에이전트와 제어 에이전트가 함께 있는 경우 순차 실행 필요
4. 단일 에이전트이거나 독립적인 에이전트들은 병렬 실행 가능

JSON 형식으로 응답해주세요:
{
  "is_sequential": boolean,
  "execution_order": ["skill1", "skill2", ...],
  "reasoning": "분석 근거"
}"""
            
            user_prompt = f"""관련 에이전트/스킬:
{chr(10).join(agents_info)}

coordination_type: {coordination_type}
connection_type: {connection_type}

위 정보를 바탕으로 에이전트 간 의존성을 분석해주세요."""
            
            response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=300
            )
            
            cleaned_response = self._clean_json_response(response)
            result = json.loads(cleaned_response)
            
            is_sequential = result.get("is_sequential", False)
            execution_order = result.get("execution_order", agent_skills_needed)
            reasoning = result.get("reasoning", "LLM 기반 분석")
            
            print(f"📋 LLM 기반 Dependency 분석 결과: {reasoning}")
            
            return {
                "is_sequential": is_sequential,
                "execution_order": execution_order,
                "reasoning": reasoning
            }
            
        except Exception as e:
            print(f"❌ LLM 기반 의존성 분석 실패: {e}")
            # 백업: 기본 병렬 실행
            return {
                "is_sequential": False,
                "execution_order": agent_skills_needed,
                "reasoning": "분석 실패로 인한 병렬 실행"
            }
    
    async def _determine_execution_order_via_llm(self, agent_skills_needed: List[str], skill_to_agent_info: Dict[str, Any]) -> List[str]:
        """LLM 기반 실행 순서 결정"""
        print("🔗 LLM 기반 실행 순서 결정 중...")
        
        try:
            # 스킬 정보 포맷팅
            skills_info = []
            for skill_id in agent_skills_needed:
                agent_info = skill_to_agent_info.get(skill_id, {})
                agent_name = agent_info.get("agent_name", "Unknown")
                domain_category = agent_info.get("domain_category", "")
                
                skill_text = f"- {skill_id}: {agent_name}"
                if domain_category:
                    skill_text += f" (도메인: {domain_category})"
                
                skills_info.append(skill_text)
            
            system_prompt = """당신은 멀티 에이전트 시스템의 실행 순서 결정 전문가입니다.

에이전트들의 실행 순서를 결정해주세요.

순서 결정 기준:
1. 정보 제공 에이전트는 제어 에이전트보다 먼저 실행
2. 데이터 수집 에이전트는 데이터 활용 에이전트보다 먼저 실행
3. 독립적인 에이전트들은 순서 상관없음
4. 종속성이 있는 에이전트들은 의존성 순서대로 실행

JSON 형식으로 응답해주세요:
{
  "execution_order": ["skill1", "skill2", ...],
  "reasoning": "순서 결정 근거"
}"""
            
            user_prompt = f"""실행할 스킬/에이전트:
{chr(10).join(skills_info)}

위 에이전트들의 최적 실행 순서를 결정해주세요."""
            
            response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=200
            )
            
            cleaned_response = self._clean_json_response(response)
            result = json.loads(cleaned_response)
            
            execution_order = result.get("execution_order", agent_skills_needed)
            reasoning = result.get("reasoning", "LLM 기반 순서 결정")
            
            print(f"📋 LLM 기반 실행 순서: {' → '.join(execution_order)} ({reasoning})")
            
            return execution_order
            
        except Exception as e:
            print(f"❌ LLM 기반 실행 순서 결정 실패: {e}")
            # 백업: 원래 순서 유지
            return agent_skills_needed

    async def _execute_sequential_agents(self, user_text: str, analysis: RequestAnalysis, execution_plan: Dict[str, Any], session_id: str) -> str:
        """순차 실행 로직"""
        print("🔄 순차 실행 시작...")
        
        execution_order = execution_plan["execution_order"]
        connection_type = execution_plan.get("connection_type", "")
        
        agents_by_skill = await self.agent_registry.discover_agents_by_skills(execution_order)
        responses = {}
        
        # 순차적으로 각 에이전트 실행
        for i, skill_id in enumerate(execution_order):
            agents = agents_by_skill.get(skill_id, [])
            
            if not agents:
                print(f"⚠️ '{skill_id}' 스킬을 가진 에이전트를 찾을 수 없음")
                responses[skill_id] = f"{skill_id} 처리 중 오류가 발생했습니다."
                continue
            
            selected_agent = agents[0]
            print(f"🎯 순차 실행 {i+1}/{len(execution_order)}: {skill_id} -> {selected_agent.name}")
            
            # ContextManager를 사용한 맥락 정보 포함 요청 생성
            if i > 0:  # 첫 번째 에이전트가 아닌 경우 컨텍스트 포함
                enhanced_request = await self.context_manager.create_contextual_request(
                    session_id, user_text, skill_id, connection_type
                )
                response = await self._call_agent(selected_agent, enhanced_request, skill_id)
            else:
                response = await self._call_agent(selected_agent, user_text, skill_id)
            
            responses[skill_id] = response
            
            # ContextManager에 에이전트 응답 저장 및 맥락 정보 추출
            self.context_manager.store_agent_response(session_id, skill_id, response, i)
            
            # 첫 번째 에이전트 응답에서 맥락 정보 추출
            if i == 0:
                extracted_info = await self.context_manager.extract_contextual_info(
                    session_id, response, skill_id, self.agent_registry
                )
                print(f"💾 첫 번째 에이전트 맥락 정보 추출: {skill_id} -> {extracted_info}")
            
            print(f"✅ {skill_id} 순차 실행 완료")
        
        # 응답 집약
        return await self._aggregate_multi_domain_responses(user_text, analysis, responses)

    async def _execute_parallel_agents(self, user_text: str, analysis: RequestAnalysis, agent_skills_needed: List[str], session_id: str) -> str:
        """병렬 실행 로직 (기존 로직)"""
        print("🔄 병렬 실행 시작...")
        
        # 필요한 스킬별로 에이전트 발견
        agents_by_skill = await self.agent_registry.discover_agents_by_skills(agent_skills_needed)
        
        responses = {}
        tasks = []
        
        # 각 스킬에 대해 병렬로 요청 처리
        for skill_id, agents in agents_by_skill.items():
            if agents:
                # 첫 번째로 발견된 에이전트 사용 (향후 로드 밸런싱 고려 가능)
                selected_agent = agents[0]
                print(f"🎯 병렬 실행: {skill_id} -> {selected_agent.name} ({selected_agent.url})")
                
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
                    
                    # ContextManager에 에이전트 응답 저장
                    self.context_manager.store_agent_response(session_id, skill_id, response)
                    
                    print(f"✅ {skill_id} 병렬 실행 완료")
                except Exception as e:
                    print(f"❌ {skill_id} 응답 실패: {e}")
                    responses[skill_id] = f"{skill_id} 처리 중 오류가 발생했습니다."
        
        # 응답 집약 및 조합
        return await self._aggregate_multi_domain_responses(user_text, analysis, responses)



    async def _handle_direct_request(self, user_text: str, analysis: RequestAnalysis) -> str:
        """메인 에이전트에서 직접 처리"""
        print("💬 메인 에이전트에서 직접 처리...")
        
        # Agent Card 기반 도메인 처리
        primary_domain = analysis.domains[0] if analysis.domains else "unknown"
        
        # Agent Card에서 대화형 도메인 확인
        is_chat_domain = await self._is_chat_domain(primary_domain)
        
        if is_chat_domain:
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
                # Agent Card 기반 동적 기능 설명
                return await self._generate_dynamic_introduction(user_text)
        else:
            return f"죄송합니다. '{user_text}' 요청을 처리할 수 있는 적절한 에이전트를 찾지 못했습니다."
    
    async def _is_chat_domain(self, domain: str) -> bool:
        """Agent Card에서 대화형 도메인인지 확인"""
        try:
            # 등록된 Agent Card에서 대화형 도메인 확인
            registered_agents = await self.agent_registry.get_all_agents()
            
            for agent in registered_agents:
                extended_skills = agent.agent_card.get("extended_skills", [])
                for skill in extended_skills:
                    domain_category = skill.get("domain_category", "")
                    
                    # 도메인이 일치하고 chat 관련 카테고리인지 확인
                    if domain_category == domain:
                        if any(keyword in domain_category.lower() for keyword in ["chat", "conversation", "general"]):
                            return True
            
            # 등록된 Agent가 없거나 unknown 도메인인 경우 대화형으로 처리
            return domain == "unknown"
            
        except Exception as e:
            print(f"❌ 대화형 도메인 확인 실패: {e}")
            # 에러 발생 시 대화형으로 처리
            return True

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
        """복합 도메인 응답 집약 및 조합 (domain agnostic)"""
        print("\n" + "="*60)
        print("🔗 MAIN AGENT 복합 응답 집약 시작")
        print("="*60)
        
        try:
            # LLM 기반 지능형 응답 집약 시도
            return await self._intelligent_response_aggregation(user_text, analysis, responses)
            
        except Exception as e:
            print(f"❌ 지능형 응답 집약 실패: {e}")
            # 백업: 구조화된 응답 조합
            return await self._fallback_response_aggregation(responses)

    async def _intelligent_response_aggregation(self, user_text: str, analysis: RequestAnalysis, responses: Dict[str, str]) -> str:
        """LLM 기반 지능형 응답 집약 (domain agnostic)"""
        print("🧠 LLM 기반 지능형 응답 집약 중...")
        
        # 등록된 Agent 정보 가져오기
        registered_agents = await self.agent_registry.get_all_agents()
        
        # 응답에 관련된 Agent 정보 수집
        agent_info_list = []
        for skill_id, response in responses.items():
            agent_info = self._find_agent_info_by_skill(skill_id, registered_agents)
            if agent_info:
                agent_info_list.append(f"- {agent_info['name']}: {agent_info['description']}")
        
        # 시스템 프롬프트 생성
        system_prompt = f"""당신은 멀티 에이전트 시스템의 응답 집약기입니다.
사용자의 복합 요청에 대해 여러 에이전트의 응답을 종합하여 
자연스럽고 유용한 통합 응답을 생성해주세요.

참여 에이전트:
{chr(10).join(agent_info_list)}

응답 규칙:
1. 각 에이전트의 응답을 논리적으로 연결
2. 사용자의 의도를 고려한 개인화된 제안 포함
3. 친근하고 도움이 되는 톤 사용
4. 구체적이고 실용적인 정보 제공
5. 불필요한 중복 정보 제거"""

        # 사용자 프롬프트 생성
        responses_text = []
        for skill_id, response in responses.items():
            agent_info = self._find_agent_info_by_skill(skill_id, registered_agents)
            agent_name = agent_info['name'] if agent_info else skill_id
            responses_text.append(f"{agent_name}: {response}")
        
        user_prompt = f"""사용자 요청: "{user_text}"
요청 유형: {analysis.request_type}
관련 도메인: {analysis.domains}
추출된 엔티티: {[f"{e.entity_type}: {e.value}" for e in analysis.entities]}

에이전트 응답:
{chr(10).join(responses_text)}

위 정보를 바탕으로 사용자의 복합 요청에 대한 통합된 응답을 생성해주세요."""

        try:
            orchestrated_response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=400
            )
            
            print(f"✅ LLM 기반 지능형 응답 집약 완료")
            return orchestrated_response
                
        except Exception as e:
            print(f"❌ LLM 기반 응답 집약 실패: {e}")
            raise  # 백업 메서드에서 처리하도록 예외 전파
    
    def _find_agent_info_by_skill(self, skill_id: str, registered_agents: List) -> Optional[Dict[str, str]]:
        """스킬 ID로 Agent 정보 찾기"""
        for agent in registered_agents:
            extended_skills = agent.agent_card.get("extended_skills", [])
            for skill_data in extended_skills:
                if skill_data.get("id") == skill_id:
                    return {
                        "name": agent.name,
                        "description": agent.description
                    }
        return None
    
    async def _fallback_response_aggregation(self, responses: Dict[str, str]) -> str:
        """백업 응답 집약 (구조화된 방식)"""
        print("🔄 백업 응답 집약 사용...")
        
        combined_response = "여러 에이전트의 응답을 종합한 결과입니다:\n\n"
        
        for skill_id, response in responses.items():
            skill_name = skill_id.replace("_", " ").title()
            combined_response += f"🔸 **{skill_name}**: {response}\n\n"
        
        combined_response += "위 정보들을 종합하여 요청을 처리해드렸습니다."
        
        return combined_response.strip()

    async def _generate_help_response(self) -> str:
        """LLM 기반 도움말 응답 생성"""
        try:
            # 등록된 에이전트 정보 조회
            stats = await self.agent_registry.get_registry_stats()
            
            # 에이전트 정보 포맷팅
            agents_info = []
            for agent_info in stats['agents']:
                status = "🟢" if agent_info['is_healthy'] else "🔴"
                agents_info.append(f"{status} {agent_info['name']}: {', '.join(agent_info['skills'])}")
            
            # LLM 기반 도움말 생성
            system_prompt = """당신은 멀티 에이전트 시스템의 도움말 생성 전문가입니다.

사용자에게 시스템의 기능을 친근하고 유용하게 설명해주세요.

도움말 구성:
1. 시스템 소개 (멀티 에이전트 시스템임을 명시)
2. 주요 기능 설명 (각 스킬의 용도와 예시)
3. 등록된 에이전트 현황
4. 사용 방법 가이드
5. 친근하고 도움이 되는 톤 사용

마크다운 형식으로 작성해주세요."""
            
            user_prompt = f"""시스템 현황:
- 총 에이전트 수: {stats['total_agents']}개
- 활성 에이전트 수: {stats['healthy_agents']}개
- 사용 가능한 스킬: {', '.join(stats['skills'])}

등록된 에이전트:
{chr(10).join(agents_info)}

위 정보를 바탕으로 사용자에게 유용한 도움말을 생성해주세요."""
            
            response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=500
            )
            
            return response
            
        except Exception as e:
            print(f"❌ LLM 기반 도움말 생성 실패: {e}")
            # 백업: Agent Card 기반 동적 백업 도움말
            return await self._generate_dynamic_fallback_help()

    async def _generate_dynamic_introduction(self, user_text: str) -> str:
        """Agent Card 기반 동적 소개 생성"""
        try:
            # 등록된 에이전트 정보 조회
            stats = await self.agent_registry.get_registry_stats()
            
            # 활성 에이전트들의 기능 정보 수집
            available_functions = []
            for agent_info in stats['agents']:
                if agent_info['is_healthy']:
                    agent_name = agent_info['name']
                    skills = agent_info['skills']
                    available_functions.append(f"• {agent_name}: {', '.join(skills)}")
            
            # LLM 기반 소개 생성
            system_prompt = """당신은 멀티 에이전트 시스템의 소개 전문가입니다.

사용자의 요청에 대해 친근하고 도움이 되는 소개를 생성해주세요.

소개 구성:
1. 멀티 에이전트 시스템 소개
2. 현재 활성화된 에이전트들의 기능 설명
3. 사용자 요청에 대한 이해 표현
4. 다음 단계 안내

친근하고 도움이 되는 톤으로 작성해주세요."""
            
            user_prompt = f"""사용자 요청: "{user_text}"

현재 활성화된 기능:
{chr(10).join(available_functions)}

총 {stats['healthy_agents']}개의 에이전트가 활성 상태입니다.

사용자에게 시스템을 소개하고 요청을 어떻게 처리할지 안내해주세요."""
            
            response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=3000
            )
            
            return response
            
        except Exception as e:
            print(f"❌ 동적 소개 생성 실패: {e}")
            # 백업: 기본 소개
            return f"안녕하세요! 저는 멀티 에이전트 시스템의 오케스트레이터입니다. 현재 {stats.get('healthy_agents', 0)}개의 에이전트가 활성 상태입니다. 무엇을 도와드릴까요?"
    
    async def _generate_dynamic_fallback_help(self) -> str:
        """Agent Card 기반 동적 백업 도움말"""
        try:
            # 등록된 에이전트 정보 조회
            stats = await self.agent_registry.get_registry_stats()
            
            # 활성 에이전트들의 기능 정보 수집
            available_functions = []
            for agent_info in stats['agents']:
                if agent_info['is_healthy']:
                    agent_name = agent_info['name']
                    skills = agent_info['skills']
                    available_functions.append(f"• {agent_name}: {', '.join(skills)}")
            
            if available_functions:
                help_text = f"저는 다양한 에이전트들과 협력하는 오케스트레이터입니다.\n\n"
                help_text += f"현재 활성화된 기능:\n"
                help_text += "\n".join(available_functions)
                help_text += f"\n\n총 {stats['healthy_agents']}개의 에이전트가 도움을 드릴 준비가 되어 있습니다."
            else:
                help_text = "저는 멀티 에이전트 시스템의 오케스트레이터입니다. 현재 등록된 에이전트를 확인 중입니다."
            
            return help_text
            
        except Exception as e:
            print(f"❌ 동적 백업 도움말 생성 실패: {e}")
            # 최종 백업
            return "저는 멀티 에이전트 시스템의 오케스트레이터입니다. 다양한 에이전트들과 협력하여 요청을 처리합니다."

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
            # 확장된 정보를 포함하여 등록
            extended_agent_card = agent_card.model_dump()
            extended_agent_card["extended_skills"] = [
                ExtendedAgentSkill(
                    id="orchestration",
                    name="Orchestration",
                    description="사용자 요청을 분석하고 적절한 에이전트로 라우팅하며 복합 응답을 집약",
                    tags=["orchestration", "routing", "aggregation", "coordination"],
                    domain_category="orchestration",
                    keywords=["조율", "라우팅", "관리", "통합", "처리"],
                    entity_types=[
                        EntityTypeInfo("request_scope", "요청 범위", ["단일", "복합", "전체"]),
                        EntityTypeInfo("coordination_type", "조율 타입", ["sequential", "parallel", "conditional"])
                    ],
                    intent_patterns=["복합 요청", "멀티 도메인", "orchestration"],
                    connection_patterns=["어울리는", "맞는", "적절한", "따라", "기반으로", "맞춰서"]
                ).to_dict(),
                ExtendedAgentSkill(
                    id="chit_chat",
                    name="General Chat",
                    description="일반적인 대화 및 시스템 정보 제공",
                    tags=["chat", "conversation", "help"],
                    domain_category="general_chat",
                    keywords=["안녕", "고마워", "도움", "인사", "기능", "문의", "hello", "help"],
                    entity_types=[
                        EntityTypeInfo("chat_type", "대화 유형", ["greeting", "thanks", "help", "question"]),
                        EntityTypeInfo("topic", "문의 주제", ["기능", "사용법", "도움말", "설명"])
                    ],
                    intent_patterns=["일반 대화", "인사", "도움 요청", "chit chat"],
                    connection_patterns=[]
                ).to_dict(),
                ExtendedAgentSkill(
                    id="agent_registry",
                    name="Agent Registry",
                    description="에이전트 등록 및 발견 서비스 제공",
                    tags=["registry", "discovery", "management"],
                    domain_category="management",
                    keywords=["등록", "관리", "발견", "registry", "discovery"],
                    entity_types=[
                        EntityTypeInfo("agent_operation", "에이전트 작업", ["등록", "해제", "검색", "상태확인"]),
                        EntityTypeInfo("agent_type", "에이전트 타입", ["service", "main", "helper"])
                    ],
                    intent_patterns=["에이전트 관리", "agent management", "registry"],
                    connection_patterns=[]
                ).to_dict()
            ]
            await registry.register_agent(extended_agent_card)
            print("✅ Main Agent 자체 등록 완료")
        except Exception as e:
            print(f"❌ Main Agent 자체 등록 실패: {e}")
    
    print("✅ Main Agent 생성 완료")

    @app.on_event("startup")
    async def startup_event():
        await register_main_agent()
    
    return app