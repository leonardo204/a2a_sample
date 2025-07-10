#!/usr/bin/env python3
"""
Dynamic Prompt Manager
Agent Card 기반 동적 프롬프트 생성 및 관리
"""
import yaml
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.extended_agent_card import ExtendedAgentSkill, EntityTypeInfo
import logging

logger = logging.getLogger(__name__)


class DynamicPromptManager:
    """동적 프롬프트 관리자"""
    
    def __init__(self, agent_registry):
        self.agent_registry = agent_registry
        self.memory_cache = {}
        self.prompt_dir = Path("prompt/main_agent")
        print("🔄 DynamicPromptManager 초기화 완료")
    
    async def on_agent_registered(self, agent_card: dict):
        """Agent 등록 시 complete 프롬프트 재생성"""
        print(f"🔄 Agent 등록으로 인한 프롬프트 재생성: {agent_card.get('name')}")
        await self.rebuild_complete_prompts()
    
    async def rebuild_complete_prompts(self):
        """모든 등록된 Agent 기반으로 complete 프롬프트 재생성"""
        print("🔄 Complete 프롬프트 전체 재생성 시작...")
        
        try:
            registered_agents = await self.agent_registry.get_all_agents()
            print(f"📋 등록된 Agent 수: {len(registered_agents)}")
            
            for prompt_type in ["intent_classification", "entity_extraction", "orchestration"]:
                try:
                    # 1) skeleton 로드
                    skeleton = await self.load_skeleton(prompt_type)
                    
                    # 2) Agent Card들 기반으로 완성
                    complete_prompt = await self.build_complete_prompt(skeleton, registered_agents, prompt_type)
                    
                    # 3) 파일 저장 + 메모리 캐시
                    await self.save_complete_prompt(prompt_type, complete_prompt)
                    
                except Exception as e:
                    print(f"❌ {prompt_type} 프롬프트 재생성 실패: {e}")
                    continue
                    
            print("✅ Complete 프롬프트 전체 재생성 완료")
            
        except Exception as e:
            print(f"❌ 프롬프트 재생성 중 오류: {e}")
    
    async def get_prompt(self, prompt_type: str) -> dict:
        """Complete 프롬프트 조회"""
        cache_key = f"{prompt_type}_complete"
        
        if cache_key not in self.memory_cache:
            # 파일에서 로드 또는 skeleton 사용
            complete_prompt = await self.load_complete_prompt(prompt_type)
            self.memory_cache[cache_key] = complete_prompt
        
        return self.memory_cache[cache_key]
    
    async def build_complete_prompt(self, skeleton: dict, agents: List, prompt_type: str) -> dict:
        """Agent Card 기반으로 완성 프롬프트 생성"""
        if prompt_type == "intent_classification":
            return await self.build_intent_classification(skeleton, agents)
        elif prompt_type == "entity_extraction":
            return await self.build_entity_extraction(skeleton, agents)
        elif prompt_type == "orchestration":
            return await self.build_orchestration(skeleton, agents)
        else:
            return skeleton
    
    async def build_intent_classification(self, skeleton: dict, agents: List) -> dict:
        """Intent Classification 완성 프롬프트 생성"""
        print("🎯 Intent Classification 프롬프트 생성 중...")
        
        # Agent Card에서 도메인 정보 수집
        agent_domains = []
        connection_patterns = set()
        
        for agent in agents:
            # 확장된 스킬 정보 처리
            extended_skills = agent.agent_card.get("extended_skills", [])
            if not extended_skills:
                continue
                
            for skill_data in extended_skills:
                domain_category = skill_data.get("domain_category")
                keywords = skill_data.get("keywords", [])
                patterns = skill_data.get("connection_patterns", [])
                description = skill_data.get("description", "")
                
                if domain_category and keywords:
                    keyword_str = ", ".join(keywords)
                    agent_domains.append(f"- {domain_category}: {description} ({keyword_str})")
                
                connection_patterns.update(patterns)
        
        # 템플릿 치환
        system_prompt = skeleton["system_prompt"].replace(
            "{{AGENT_DOMAINS}}", "\n".join(agent_domains) if agent_domains else "- 등록된 도메인이 없어 일반 대화만 가능"
        ).replace(
            "{{CONNECTION_PATTERNS}}", f"연결어 존재: {', '.join(sorted(connection_patterns))}" if connection_patterns else "연결어 없음"
        )
        
        user_prompt_template = skeleton["user_prompt_template"].replace(
            "{{CLASSIFICATION_RULES}}", """분류 규칙:
1. 하나의 도메인만 관련: single_domain
2. 여러 도메인이 연결됨: multi_domain
3. 복합 요청 감지 시 연결어와 도메인 키워드 동시 확인"""
        )
        
        return {
            "system_prompt": system_prompt,
            "user_prompt_template": user_prompt_template,
            "examples": skeleton.get("examples", [])
        }
    
    async def build_entity_extraction(self, skeleton: dict, agents: List) -> dict:
        """Entity Extraction 완성 프롬프트 생성"""
        print("🔍 Entity Extraction 프롬프트 생성 중...")
        
        # 엔티티 추출 규칙 확장
        entity_rules = skeleton.get("entity_extraction_rules", [])
        
        # 동적 엔티티 규칙 추가
        if self.agent_registry:
            agents = await self.agent_registry.get_all_agents()
            
            # 에이전트별 엔티티 규칙 추가
            for agent in agents:
                extended_skills = agent.agent_card.get("extended_skills", [])
                for skill in extended_skills:
                    entity_types = skill.get("entity_types", [])
                    for entity_type in entity_types:
                        entity_rules.append(f"- {entity_type.get('name', 'unknown')}: {entity_type.get('description', '')}")
            
            # 연결 패턴 정보 추가
            connection_patterns = set()
            for agent in agents:
                extended_skills = agent.agent_card.get("extended_skills", [])
                for skill in extended_skills:
                    patterns = skill.get("connection_patterns", [])
                    connection_patterns.update(patterns)
            
            if connection_patterns:
                entity_rules.append(f"- connection_type: 연결 관계 ({', '.join(list(connection_patterns)[:5])})")  # 최대 5개만 표시
        
        # Agent Card가 등록되지 않은 경우 chit-chat 전용 엔티티만 사용
        if not entity_rules:
            entity_rules = [
                "- chat_type: 대화 유형 (인사, 감사, 질문, 도움 요청)",
                "- topic: 문의 주제 (기능, 사용법, 도움말, 설명)",
                "- intent: 대화 의도 (greeting, help, question, thanks)"
            ]
        
        user_prompt_template = skeleton["user_prompt_template"].replace(
            "{{ENTITY_EXTRACTION_RULES}}", "\n".join(entity_rules) if entity_rules else "엔티티 추출 규칙이 없습니다."
        )
        
        return {
            "system_prompt": skeleton["system_prompt"],
            "user_prompt_template": user_prompt_template,
            "examples": skeleton.get("examples", [])
        }
    
    async def build_orchestration(self, skeleton: dict, agents: List) -> dict:
        """Orchestration 완성 프롬프트 생성"""
        print("🎭 Orchestration 프롬프트 생성 중...")
        
        # 가용 에이전트 정보 수집
        available_agents = []
        for agent in agents:
            if agent.name == "Main Agent":
                continue  # Main Agent는 오케스트레이터이므로 제외
                
            agent_info = f"- {agent.name}: {agent.description}"
            
            # 확장된 스킬 정보 처리
            extended_skills = agent.agent_card.get("extended_skills", [])
            if extended_skills:
                skills_info = []
                for skill_data in extended_skills:
                    skill_name = skill_data.get("name", skill_data.get("id", "Unknown"))
                    skills_info.append(skill_name)
                agent_info += f" (Skills: {', '.join(skills_info)})"
            
            available_agents.append(agent_info)
        
        system_prompt = skeleton["system_prompt"].replace(
            "{{AVAILABLE_AGENTS}}", "\n".join(available_agents) if available_agents else "사용 가능한 에이전트가 없습니다."
        )
        
        return {
            "system_prompt": system_prompt,
            "user_prompt_template": skeleton["user_prompt_template"],
            "examples": skeleton.get("examples", [])
        }
    
    async def load_skeleton(self, prompt_type: str) -> dict:
        """Skeleton 프롬프트 로드"""
        file_path = self.prompt_dir / f"{prompt_type}_skeleton.yaml"
        
        if not file_path.exists():
            raise FileNotFoundError(f"Skeleton 파일을 찾을 수 없습니다: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    async def save_complete_prompt(self, prompt_type: str, complete_prompt: dict):
        """Complete 프롬프트 파일 저장 및 메모리 캐시"""
        file_path = self.prompt_dir / f"{prompt_type}_complete.yaml"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(complete_prompt, f, allow_unicode=True, indent=2)
        
        cache_key = f"{prompt_type}_complete"
        self.memory_cache[cache_key] = complete_prompt
        print(f"✅ Complete 프롬프트 저장: {file_path}")
    
    async def load_complete_prompt(self, prompt_type: str) -> dict:
        """Complete 프롬프트 파일 로드"""
        file_path = self.prompt_dir / f"{prompt_type}_complete.yaml"
        
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            # complete 파일이 없으면 skeleton 사용
            print(f"⚠️ Complete 파일 없음, skeleton 사용: {prompt_type}")
            return await self.load_skeleton(prompt_type)
    
    async def build_dependency_analysis_prompt(self, user_query: str, agent_cards_info: List[Dict], entities: List) -> Dict[str, str]:
        """Agent Card 기반 dependency 분석 프롬프트 생성"""
        print("🔗 Dependency 분석 프롬프트 생성 중...")
        
        # Agent Cards 정보 포맷팅
        agents_info = []
        for agent_info in agent_cards_info:
            agent_name = agent_info.get("name", "Unknown")
            agent_desc = agent_info.get("description", "")
            domain_category = agent_info.get("domain_category", "")
            connection_patterns = agent_info.get("connection_patterns", [])
            
            agent_text = f"- {agent_name}: {agent_desc}"
            if domain_category:
                agent_text += f" (도메인: {domain_category})"
            if connection_patterns:
                agent_text += f" (연결패턴: {', '.join(connection_patterns)})"
            
            agents_info.append(agent_text)
        
        # Entity 정보 포맷팅
        entities_info = []
        for entity in entities:
            entities_info.append(f"- {entity.entity_type}: {entity.value} (신뢰도: {entity.confidence})")
        
        system_prompt = """당신은 멀티 에이전트 시스템의 실행 dependency 분석 전문가입니다.

사용자 요청과 관련 에이전트들의 정보를 바탕으로 에이전트 간의 실행 순서와 dependency를 분석해주세요.

분석 기준:
1. 정보 제공 에이전트는 제어 에이전트보다 먼저 실행되어야 함
2. connection_patterns가 사용자 요청에 포함된 경우 순차 실행 고려
3. coordination_type이 conditional인 경우 순차 실행 필요
4. 에이전트 간 데이터 의존성이 있는 경우 순차 실행 필요

JSON 형식으로 응답해주세요:
{
  "is_sequential": boolean,
  "execution_order": ["skill1", "skill2", ...],
  "reasoning": "분석 근거"
}"""
        
        user_prompt = f"""사용자 요청: "{user_query}"

관련 에이전트 정보:
{chr(10).join(agents_info)}

추출된 엔티티:
{chr(10).join(entities_info)}

위 정보를 바탕으로 에이전트 간 실행 dependency를 분석해주세요."""
        
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
    
    async def build_context_extraction_prompt(self, agent_response: str, source_skill: str, target_skill: str, agent_cards_info: List[Dict]) -> Dict[str, str]:
        """맥락 정보 추출 프롬프트 생성"""
        print("🔍 맥락 정보 추출 프롬프트 생성 중...")
        
        # Target Agent 정보 찾기
        target_agent_info = None
        for agent_info in agent_cards_info:
            if agent_info.get("skill_id") == target_skill:
                target_agent_info = agent_info
                break
        
        target_desc = target_agent_info.get("description", "다음 에이전트") if target_agent_info else "다음 에이전트"
        
        system_prompt = f"""당신은 멀티 에이전트 시스템의 맥락 정보 추출 전문가입니다.

이전 에이전트의 응답에서 다음 에이전트가 활용할 수 있는 핵심 맥락 정보를 추출해주세요.

추출 기준:
1. 다음 에이전트의 작업에 도움이 되는 구체적인 정보
2. 수치, 상태, 조건 등 객관적 데이터 우선
3. 너무 긴 정보는 요약하여 핵심만 추출
4. 관련 없는 정보는 제외

JSON 형식으로 응답해주세요:
{{
  "extracted_context": "추출된 맥락 정보",
  "relevance_score": 0.0-1.0,
  "reasoning": "추출 근거"
}}"""
        
        user_prompt = f"""이전 에이전트: {source_skill}
이전 에이전트 응답: "{agent_response}"

다음 에이전트: {target_skill}
다음 에이전트 역할: {target_desc}

다음 에이전트가 활용할 수 있는 맥락 정보를 추출해주세요."""
        
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
    
    async def build_skill_selection_prompt(self, user_query: str, available_agents: List[Dict], entities: List) -> Dict[str, str]:
        """Agent Card 기반 스킬 선택 프롬프트 생성"""
        print("🎯 스킬 선택 프롬프트 생성 중...")
        
        # 사용 가능한 Agent/Skill 정보 포맷팅
        available_skills = []
        for agent in available_agents:
            extended_skills = agent.agent_card.get("extended_skills", [])
            for skill_data in extended_skills:
                skill_id = skill_data.get("id")
                skill_name = skill_data.get("name", skill_id)
                skill_desc = skill_data.get("description", "")
                domain_category = skill_data.get("domain_category", "")
                keywords = skill_data.get("keywords", [])
                
                skill_text = f"- {skill_id}: {skill_name} - {skill_desc}"
                if domain_category:
                    skill_text += f" (도메인: {domain_category})"
                if keywords:
                    skill_text += f" (키워드: {', '.join(keywords[:5])})"  # 최대 5개
                
                available_skills.append(skill_text)
        
        # Entity 정보 포맷팅
        entities_info = []
        for entity in entities:
            entities_info.append(f"- {entity.entity_type}: {entity.value}")
        
        system_prompt = """당신은 멀티 에이전트 시스템의 스킬 선택 전문가입니다.

사용자 요청을 분석하여 필요한 스킬들을 선택해주세요.

선택 기준:
1. 사용자 요청의 키워드와 각 스킬의 키워드 매칭
2. 도메인 카테고리와 요청 내용의 연관성
3. 추출된 엔티티와 스킬의 적합성
4. 복합 요청인 경우 orchestration 스킬 포함

JSON 형식으로 응답해주세요:
{
  "required_skills": ["skill1", "skill2", ...],
  "reasoning": "선택 근거",
  "confidence": 0.0-1.0
}"""
        
        user_prompt = f"""사용자 요청: "{user_query}"

사용 가능한 스킬:
{chr(10).join(available_skills)}

추출된 엔티티:
{chr(10).join(entities_info)}

사용자 요청에 필요한 스킬들을 선택해주세요."""
        
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
    
    def clear_cache(self):
        """메모리 캐시 클리어"""
        self.memory_cache.clear()
        print("�� 프롬프트 캐시 클리어 완료") 