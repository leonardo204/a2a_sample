#!/usr/bin/env python3
"""
Dynamic Query Analyzer
동적 프롬프트 기반 쿼리 분석기
"""
import json
from typing import Dict, List, Any
from dataclasses import dataclass
from src.llm_client import LLMClient
from src.dynamic_prompt_manager import DynamicPromptManager
import logging

logger = logging.getLogger(__name__)


@dataclass
class EntityExtraction:
    """엔티티 추출 결과"""
    entity_type: str
    value: str
    confidence: float


@dataclass
class RequestAnalysis:
    """요청 분석 결과"""
    request_type: str
    domains: List[str]
    confidence: float
    entities: List[EntityExtraction]
    requires_multiple_agents: bool
    agent_skills_needed: List[str]


class DynamicQueryAnalyzer:
    """동적 프롬프트 기반 쿼리 분석기"""
    
    def __init__(self, prompt_manager: DynamicPromptManager):
        self.llm_client = LLMClient()
        self.prompt_manager = prompt_manager
        print("🧠 DynamicQueryAnalyzer 초기화 완료")
    
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
    
    async def analyze_query(self, user_text: str) -> RequestAnalysis:
        """동적 프롬프트 기반 쿼리 분석"""
        print(f"🔍 쿼리 분석 시작: '{user_text}'")
        
        # 1. 동적 생성된 Intent Classification 프롬프트 사용
        request_result = await self._classify_request_dynamic(user_text)
        
        # 2. 동적 생성된 Entity Extraction 프롬프트 사용
        entities = await self._extract_entities_dynamic(
            user_text, 
            request_result["request_type"], 
            request_result["domains"]
        )
        
        # 3. 복합 에이전트 필요성 판단
        requires_multiple = self._check_multiple_agents_needed(request_result)
        
        # 4. 필요한 스킬 식별 (Agent Card 정보 기반)
        skills_needed = await self._identify_required_skills_via_llm(
            user_text, request_result, entities
        )
        
        result = RequestAnalysis(
            request_type=request_result["request_type"],
            domains=request_result["domains"],
            confidence=request_result["confidence"],
            entities=entities,
            requires_multiple_agents=requires_multiple,
            agent_skills_needed=skills_needed
        )
        
        print(f"✅ 동적 분석 완료: {result}")
        return result
    
    async def _classify_request_dynamic(self, user_text: str) -> Dict[str, Any]:
        """동적 프롬프트 기반 요청 분류"""
        print("🎯 동적 Intent Classification 수행 중...")
        
        try:
            prompt_data = await self.prompt_manager.get_prompt("intent_classification")
            
            formatted_prompt = prompt_data["user_prompt_template"].format(
                user_input=user_text
            )
            
            response = await self.llm_client.chat_completion(
                system_prompt=prompt_data["system_prompt"],
                user_prompt=formatted_prompt,
                max_tokens=200
            )
            
            cleaned_response = self._clean_json_response(response)
            result = json.loads(cleaned_response)
            print(f"✅ Intent Classification 결과: {result}")
            return result
            
        except Exception as e:
            print(f"❌ Intent Classification 오류: {e}")
            # Agent Card에서 대화형 도메인 찾기
            fallback_domains = await self._get_fallback_domains()
            return {
                "request_type": "single_domain",
                "domains": fallback_domains,
                "confidence": 0.5,
                "reasoning": "분석 실패 - Agent Card 기반 백업"
            }
    
    async def _extract_entities_dynamic(self, user_text: str, request_type: str, domains: List[str]) -> List[EntityExtraction]:
        """동적 프롬프트 기반 엔티티 추출"""
        print("🔍 동적 Entity Extraction 수행 중...")
        
        try:
            prompt_data = await self.prompt_manager.get_prompt("entity_extraction")
            
            formatted_prompt = prompt_data["user_prompt_template"].format(
                user_input=user_text,
                request_type=request_type,
                domains=domains
            )
            
            response = await self.llm_client.chat_completion(
                system_prompt=prompt_data["system_prompt"],
                user_prompt=formatted_prompt,
                max_tokens=300
            )
            
            cleaned_response = self._clean_json_response(response)
            result = json.loads(cleaned_response)
            entities = []
            entities_data = result.get("entities", {})
            
            for entity_type, entity_value in entities_data.items():
                if entity_value:
                    entities.append(EntityExtraction(
                        entity_type=entity_type,
                        value=str(entity_value),
                        confidence=result.get("confidence", 0.8)
                    ))
            
            print(f"✅ Entity Extraction 결과: {len(entities)}개 엔티티")
            return entities
            
        except Exception as e:
            print(f"❌ Entity Extraction 오류: {e}")
            # 백업 분석 대신 빈 리스트 반환
            return []
    
    def _check_multiple_agents_needed(self, request_result: Dict[str, Any]) -> bool:
        """복합 에이전트 필요성 판단"""
        return (
            request_result.get("request_type") == "multi_domain" and
            len(request_result.get("domains", [])) > 1
        )
    
    async def _identify_required_skills_via_llm(self, user_text: str, request_result: Dict[str, Any], entities: List[EntityExtraction]) -> List[str]:
        """LLM 기반 필요 스킬 식별"""
        print("🎯 LLM 기반 스킬 식별 중...")
        
        try:
            # 도메인 정보 포맷팅
            domains = request_result.get("domains", [])
            domain_info = ", ".join(domains) if domains else "없음"
            
            # 엔티티 정보 포맷팅
            entities_info = []
            for entity in entities:
                entities_info.append(f"- {entity.entity_type}: {entity.value}")
            entities_text = "\n".join(entities_info) if entities_info else "없음"
            
            # 복합 요청 여부
            is_multi_domain = self._check_multiple_agents_needed(request_result)
            
            # 실제 등록된 에이전트들의 스킬 정보 가져오기
            available_skills = await self._get_available_skills_info()
            skills_info_text = "\n".join([f"- {skill['id']}: {skill['description']}" for skill in available_skills])
            
            # 동적 시스템 프롬프트 (실제 스킬 정보 포함)
            system_prompt = f"""당신은 멀티 에이전트 시스템의 스킬 식별 전문가입니다.

사용자 요청을 분석하여 필요한 스킬들을 식별해주세요.

등록된 스킬들:
{skills_info_text}

스킬 식별 원칙:
1. 위에 나열된 스킬 ID만 사용해주세요
2. 복합 요청인 경우 orchestration 스킬 포함
3. 일반 대화나 불분명한 요청은 chit_chat 또는 general_chat 스킬 사용
4. 특정 도메인이 명확한 경우 해당 도메인의 실제 스킬 ID 선택
5. 도메인과 스킬 ID가 다를 수 있으므로 도메인 키워드를 기반으로 적절한 스킬 선택

JSON 형식으로 응답해주세요:
{{
  "required_skills": ["skill1", "skill2", ...],
  "reasoning": "선택 근거"
}}"""
            
            user_prompt = f"""사용자 요청: "{user_text}"

분석 결과:
- 요청 유형: {request_result.get("request_type", "unknown")}
- 도메인: {domain_info}
- 복합 요청: {is_multi_domain}

추출된 엔티티:
{entities_text}

위 등록된 스킬 목록에서 적절한 스킬들을 식별해주세요."""
            
            response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=200
            )
            
            cleaned_response = self._clean_json_response(response)
            result = json.loads(cleaned_response)
            
            skills = result.get("required_skills", [])
            print(f"✅ LLM 기반 스킬 식별 완료: {skills}")
            return skills
            
        except Exception as e:
            print(f"❌ LLM 기반 스킬 식별 오류: {e}")
            # Agent Card에서 chit-chat 스킬 찾기
            return await self._get_fallback_skills()
    
    async def _get_available_skills_info(self) -> List[Dict[str, str]]:
        """등록된 에이전트들로부터 사용 가능한 스킬 정보 수집"""
        try:
            skills_info = []
            
            # 프롬프트 매니저를 통해 등록된 Agent 정보 접근
            if hasattr(self.prompt_manager, 'agent_registry') and self.prompt_manager.agent_registry:
                agents = await self.prompt_manager.agent_registry.get_all_agents()
                
                for agent in agents:
                    # 기본 skills에서 정보 수집
                    agent_skills = agent.agent_card.get("skills", [])
                    for skill in agent_skills:
                        skill_info = {
                            "id": skill.get("id", "unknown"),
                            "name": skill.get("name", "Unknown"),
                            "description": skill.get("description", "설명 없음"),
                            "agent": agent.name
                        }
                        skills_info.append(skill_info)
                    
                    # extended_skills에서 추가 정보 수집 (있다면)
                    extended_skills = agent.agent_card.get("extended_skills", [])
                    for skill in extended_skills:
                        # 기본 skills에 없는 추가 스킬이 있다면 추가
                        skill_id = skill.get("id", "unknown")
                        if not any(s["id"] == skill_id for s in skills_info):
                            skill_info = {
                                "id": skill_id,
                                "name": skill.get("name", "Unknown"),
                                "description": skill.get("description", "설명 없음"),
                                "agent": agent.name
                            }
                            skills_info.append(skill_info)
                
                print(f"✅ 사용 가능한 스킬 {len(skills_info)}개 발견")
                return skills_info
            
            print("⚠️ 등록된 에이전트가 없습니다")
            return []
            
        except Exception as e:
            print(f"❌ 스킬 정보 수집 실패: {e}")
            return []

    async def _get_fallback_skills(self) -> List[str]:
        """Agent Card에서 대화형 백업 스킬 찾기"""
        try:
            # 프롬프트 매니저를 통해 등록된 Agent 정보 접근
            if hasattr(self.prompt_manager, 'agent_registry') and self.prompt_manager.agent_registry:
                agents = await self.prompt_manager.agent_registry.get_all_agents()
                
                # 대화형 스킬 찾기 (chat, conversation 관련)
                chat_skills = []
                for agent in agents:
                    extended_skills = agent.agent_card.get("extended_skills", [])
                    for skill in extended_skills:
                        skill_id = skill.get("id", "")
                        domain_category = skill.get("domain_category", "")
                        tags = skill.get("tags", [])
                        
                        # chat, conversation 관련 스킬 식별
                        if (any(keyword in skill_id.lower() for keyword in ["chat", "conversation", "talk"]) or
                            any(keyword in domain_category.lower() for keyword in ["chat", "conversation", "general"]) or
                            any(keyword in str(tags).lower() for keyword in ["chat", "conversation", "talk", "help"])):
                            chat_skills.append(skill_id)
                
                if chat_skills:
                    print(f"✅ Agent Card에서 대화형 스킬 발견: {chat_skills}")
                    return chat_skills[:1]  # 첫 번째 대화형 스킬만 반환
            
            print("⚠️ Agent Card에서 대화형 스킬을 찾을 수 없음")
            return []  # 스킬이 없으면 빈 리스트 반환
            
        except Exception as e:
            print(f"❌ 백업 스킬 검색 실패: {e}")
            return []
    
    async def _get_fallback_domains(self) -> List[str]:
        """Agent Card에서 대화형 백업 도메인 찾기"""
        try:
            # 프롬프트 매니저를 통해 등록된 Agent 정보 접근
            if hasattr(self.prompt_manager, 'agent_registry') and self.prompt_manager.agent_registry:
                agents = await self.prompt_manager.agent_registry.get_all_agents()
                
                # 대화형 도메인 찾기
                chat_domains = []
                for agent in agents:
                    extended_skills = agent.agent_card.get("extended_skills", [])
                    for skill in extended_skills:
                        domain_category = skill.get("domain_category", "")
                        
                        # chat, conversation, general 관련 도메인 식별
                        if any(keyword in domain_category.lower() for keyword in ["chat", "conversation", "general"]):
                            if domain_category not in chat_domains:
                                chat_domains.append(domain_category)
                
                if chat_domains:
                    print(f"✅ Agent Card에서 대화형 도메인 발견: {chat_domains}")
                    return chat_domains[:1]  # 첫 번째 대화형 도메인만 반환
            
            print("⚠️ Agent Card에서 대화형 도메인을 찾을 수 없음")
            return ["unknown"]  # 도메인이 없으면 unknown 반환
            
        except Exception as e:
            print(f"❌ 백업 도메인 검색 실패: {e}")
            return ["unknown"] 