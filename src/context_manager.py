#!/usr/bin/env python3
"""
Context Manager
멀티 에이전트 시스템의 컨텍스트 관리 전담 모듈
"""
import json
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from src.llm_client import LLMClient
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContextData:
    """컨텍스트 데이터 구조"""
    session_id: str
    user_request: str
    agents_responses: Dict[str, str] = field(default_factory=dict)  # skill_id -> response
    extracted_info: Dict[str, str] = field(default_factory=dict)   # skill_id -> extracted_info
    execution_order: List[str] = field(default_factory=list)       # 실행 순서
    metadata: Dict[str, Any] = field(default_factory=dict)         # 추가 메타데이터
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class AgentExecutionContext:
    """에이전트 실행 컨텍스트"""
    skill_id: str
    agent_name: str
    request_text: str
    response_text: str = ""
    extracted_context: str = ""
    execution_index: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ContextManager:
    """멀티 에이전트 시스템 컨텍스트 관리자"""
    
    def __init__(self):
        """초기화"""
        self.contexts: Dict[str, ContextData] = {}  # session_id -> ContextData
        self.llm_client = LLMClient()
        print("🗂️ ContextManager 초기화 완료")
    
    # === 현재 구현 기능 ===
    
    def create_session(self, user_request: str) -> str:
        """새로운 컨텍스트 세션 생성"""
        session_id = str(uuid.uuid4())
        self.contexts[session_id] = ContextData(
            session_id=session_id,
            user_request=user_request
        )
        print(f"📝 새 컨텍스트 세션 생성: {session_id[:8]}")
        return session_id
    
    async def create_contextual_request(
        self, 
        session_id: str,
        original_request: str, 
        skill_id: str, 
        connection_type: str = ""
    ) -> str:
        """맥락 정보를 포함한 요청 생성"""
        if session_id not in self.contexts:
            print(f"⚠️ 세션 {session_id[:8]}을 찾을 수 없음 - 원본 요청 반환")
            return original_request
        
        context_data = self.contexts[session_id]
        
        # 이전 에이전트 응답이 있는지 확인
        if not context_data.agents_responses:
            print(f"💭 첫 번째 에이전트 요청 - 원본 요청 사용")
            return original_request
        
        # 가장 최근 에이전트 정보 가져오기
        if context_data.execution_order:
            last_skill = context_data.execution_order[-1]
            last_response = context_data.agents_responses.get(last_skill, "")
            extracted_info = context_data.extracted_info.get(last_skill, "")
            
            # 맥락 정보 포함 요청 생성
            contextual_request = f"""{original_request}

[이전 에이전트 정보]
처리 에이전트: {last_skill}
추출된 정보: {extracted_info}

위 정보를 참고하여 요청을 처리해주세요."""
            
            print(f"🔗 맥락 정보 포함된 요청 생성 (세션: {session_id[:8]})")
            return contextual_request
        
        return original_request
    
    async def extract_contextual_info(
        self, 
        session_id: str,
        agent_response: str, 
        skill_id: str,
        agent_registry
    ) -> str:
        """LLM 기반 에이전트 응답에서 맥락 정보 추출 (Agent Card 기반 동적 프롬프트)"""
        try:
            # Agent Card 기반 동적 프롬프트 생성
            system_prompt = await self._build_dynamic_context_extraction_prompt(agent_registry)
            
            user_prompt = f"""에이전트 ID: {skill_id}
에이전트 응답: "{agent_response}"

위 응답에서 다음 에이전트가 활용할 수 있는 핵심 맥락 정보를 추출해주세요."""
            
            response = await self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=200
            )
            
            cleaned_response = self._clean_json_response(response)
            result = json.loads(cleaned_response)
            
            extracted_info = result.get("extracted_info", "")
            confidence = result.get("confidence", 0.0)
            
            print(f"🔍 맥락 정보 추출 완료 (세션: {session_id[:8]}, 신뢰도: {confidence}): {extracted_info}")
            
            # 컨텍스트에 저장
            if session_id in self.contexts:
                self.contexts[session_id].extracted_info[skill_id] = extracted_info
                self.contexts[session_id].updated_at = datetime.now()
            
            return extracted_info if extracted_info else agent_response[:100] + "..."
            
        except Exception as e:
            print(f"❌ 맥락 정보 추출 실패 (세션: {session_id[:8]}): {e}")
            # 에러 시 응답 요약만 반환
            summary = agent_response[:100] + "..." if len(agent_response) > 100 else agent_response
            
            if session_id in self.contexts:
                self.contexts[session_id].extracted_info[skill_id] = summary
                self.contexts[session_id].updated_at = datetime.now()
            
            return summary
    
    async def _build_dynamic_context_extraction_prompt(self, agent_registry) -> str:
        """Agent Card 기반 동적 맥락 정보 추출 프롬프트 생성"""
        print("🧠 Agent Card 기반 맥락 추출 프롬프트 생성 중...")
        
        try:
            # 등록된 모든 에이전트 정보 수집
            agents = await agent_registry.get_all_agents()
            
            # 각 도메인별 맥락 정보 유형 수집
            context_categories = {
                "수치_정보": set(),
                "상태_정보": set(), 
                "조건_정보": set(),
                "객체_정보": set()
            }
            
            for agent in agents:
                extended_skills = agent.agent_card.get("extended_skills", [])
                for skill in extended_skills:
                    # Entity Types에서 맥락 정보 유형 추출
                    entity_types = skill.get("entity_types", [])
                    for entity_type in entity_types:
                        entity_name = entity_type.get("name", "")
                        examples = entity_type.get("examples", [])
                        
                        # 카테고리별 분류
                        if any(keyword in entity_name.lower() for keyword in ["level", "number", "count", "량", "수"]):
                            context_categories["수치_정보"].update(examples[:3])  # 최대 3개 예시
                        elif any(keyword in entity_name.lower() for keyword in ["상태", "status", "condition", "mode"]):
                            context_categories["상태_정보"].update(examples[:3])
                        elif any(keyword in entity_name.lower() for keyword in ["시간", "time", "날짜", "date", "조건"]):
                            context_categories["조건_정보"].update(examples[:3])
                        else:
                            context_categories["객체_정보"].update(examples[:3])
            
            # 동적 프롬프트 생성
            context_examples = []
            if context_categories["수치_정보"]:
                examples = ", ".join(list(context_categories["수치_정보"])[:5])
                context_examples.append(f"1. 수치 정보 ({examples} 등)")
            
            if context_categories["상태_정보"]:
                examples = ", ".join(list(context_categories["상태_정보"])[:5])
                context_examples.append(f"2. 상태 정보 ({examples} 등)")
            
            if context_categories["조건_정보"]:
                examples = ", ".join(list(context_categories["조건_정보"])[:5])
                context_examples.append(f"3. 조건 정보 ({examples} 등)")
            
            if context_categories["객체_정보"]:
                examples = ", ".join(list(context_categories["객체_정보"])[:5])
                context_examples.append(f"4. 객체 정보 ({examples} 등)")
            
            system_prompt = f"""당신은 멀티 에이전트 시스템의 맥락 정보 추출 전문가입니다.

에이전트 응답에서 다음 에이전트가 활용할 수 있는 핵심 맥락 정보를 추출해주세요.

현재 시스템의 에이전트 기반 추출 기준:
{chr(10).join(context_examples)}

추출 우선순위:
1. 객관적이고 구체적인 정보 우선
2. 다음 에이전트 작업에 직접적으로 도움이 되는 정보
3. 주관적이거나 불필요한 정보 제외
4. 50자 이내로 핵심만 추출

JSON 형식으로 응답해주세요:
{{
  "extracted_info": "핵심 맥락 정보 (50자 이내)",
  "confidence": 0.0-1.0,
  "reasoning": "추출 근거"
}}"""
            
            print(f"✅ 동적 맥락 추출 프롬프트 생성 완료 (카테고리: {len(context_examples)}개)")
            return system_prompt
            
        except Exception as e:
            print(f"❌ 동적 프롬프트 생성 실패: {e}")
            raise  # Agent Card 기반으로만 동작하므로 예외 전파
    

    
    def store_agent_response(
        self, 
        session_id: str, 
        skill_id: str, 
        response: str,
        execution_index: int = None
    ):
        """에이전트 응답 저장"""
        if session_id not in self.contexts:
            print(f"⚠️ 세션 {session_id[:8]}을 찾을 수 없음")
            return
        
        context_data = self.contexts[session_id]
        context_data.agents_responses[skill_id] = response
        
        # 실행 순서 업데이트
        if skill_id not in context_data.execution_order:
            context_data.execution_order.append(skill_id)
        
        context_data.updated_at = datetime.now()
        print(f"💾 에이전트 응답 저장 (세션: {session_id[:8]}, 스킬: {skill_id})")
    
    def get_context_data(self, session_id: str) -> Optional[ContextData]:
        """컨텍스트 데이터 조회"""
        return self.contexts.get(session_id)
    
    def get_agents_responses(self, session_id: str) -> Dict[str, str]:
        """에이전트 응답들 조회"""
        if session_id in self.contexts:
            return self.contexts[session_id].agents_responses.copy()
        return {}
    
    def get_execution_summary(self, session_id: str) -> Dict[str, Any]:
        """실행 요약 정보 조회"""
        if session_id not in self.contexts:
            return {}
        
        context_data = self.contexts[session_id]
        return {
            "session_id": session_id,
            "user_request": context_data.user_request,
            "execution_order": context_data.execution_order,
            "agents_count": len(context_data.agents_responses),
            "extracted_info": context_data.extracted_info,
            "created_at": context_data.created_at.isoformat(),
            "updated_at": context_data.updated_at.isoformat()
        }
    
    def cleanup_session(self, session_id: str):
        """세션 정리"""
        if session_id in self.contexts:
            del self.contexts[session_id]
            print(f"🗑️ 세션 정리 완료: {session_id[:8]}")
    
    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """오래된 세션들 정리"""
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        sessions_to_remove = []
        for session_id, context_data in self.contexts.items():
            if context_data.updated_at < cutoff_time:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            del self.contexts[session_id]
        
        if sessions_to_remove:
            print(f"🗑️ {len(sessions_to_remove)}개 오래된 세션 정리 완료")
    
    # === 향후 확장 기능 인터페이스 ===
    
    async def add_external_resource(
        self, 
        session_id: str, 
        resource_type: str, 
        resource_data: Any
    ):
        """외부 리소스 추가 (향후 구현)"""
        print(f"🔧 외부 리소스 추가 기능 - 향후 구현 예정 (타입: {resource_type})")
        
        # 향후 구현:
        # - API 호출 결과 저장
        # - 파일 업로드 정보 저장
        # - 웹 스크래핑 결과 저장
        pass
    
    async def add_chat_history(
        self, 
        session_id: str, 
        message: Dict[str, Any]
    ):
        """채팅 히스토리 추가 (향후 구현)"""
        print(f"🔧 채팅 히스토리 기능 - 향후 구현 예정")
        
        # 향후 구현:
        # - 대화 이력 저장
        # - 사용자 선호도 학습
        # - 컨텍스트 연결 강화
        pass
    
    async def call_external_tool(
        self, 
        session_id: str,
        tool_name: str, 
        params: Dict[str, Any]
    ) -> Any:
        """외부 도구 호출 (향후 구현)"""
        print(f"🔧 외부 도구 호출 기능 - 향후 구현 예정 (도구: {tool_name})")
        
        # 향후 구현:
        # - API 호출
        # - 데이터베이스 쿼리
        # - 파일 시스템 작업
        # - 웹 서비스 연동
        return None
    
    async def analyze_context_patterns(self, session_id: str) -> Dict[str, Any]:
        """컨텍스트 패턴 분석 (향후 구현)"""
        print(f"🔧 컨텍스트 패턴 분석 기능 - 향후 구현 예정")
        
        # 향후 구현:
        # - 사용자 행동 패턴 분석
        # - 에이전트 협업 패턴 분석
        # - 성능 최적화 제안
        return {}
    
    # === 유틸리티 메서드 ===
    
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
    
    def get_stats(self) -> Dict[str, Any]:
        """컨텍스트 매니저 통계"""
        total_sessions = len(self.contexts)
        active_sessions = sum(1 for ctx in self.contexts.values() 
                            if (datetime.now() - ctx.updated_at).seconds < 3600)
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_agent_responses": sum(len(ctx.agents_responses) for ctx in self.contexts.values()),
            "average_agents_per_session": sum(len(ctx.agents_responses) for ctx in self.contexts.values()) / max(total_sessions, 1)
        } 