#!/usr/bin/env python3
"""
Query Analyzer - Request Type/Domain 추출 모듈
사용자 입력을 분석하여 요청 유형과 관련 도메인을 추출하는 역할
"""
import json
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from src.llm_client import LLMClient
from src.prompt_loader import PromptLoader


@dataclass
class EntityExtraction:
    """추출된 엔티티 정보"""
    entity_type: str
    value: str
    confidence: float = 1.0


@dataclass
class RequestAnalysis:
    """요청 분석 결과"""
    request_type: str  # "single_domain" | "multi_domain"
    domains: List[str]  # ["weather", "tv_control", "general_chat", ...]
    confidence: float
    entities: List[EntityExtraction]
    requires_multiple_agents: bool = False
    agent_skills_needed: List[str] = None


class QueryAnalyzer:
    """사용자 쿼리 분석기"""
    
    def __init__(self):
        """초기화"""
        print("🧠 QueryAnalyzer 초기화 중...")
        try:
            self.llm_client = LLMClient()
            self.prompt_loader = PromptLoader("prompt")
            
            # 도메인-스킬 매핑 테이블
            self.domain_to_skill = {
                "weather": "weather_info",
                "tv_control": "tv_control", 
                "general_chat": "chit_chat",
                # 확장 가능: "music": "music_control", "lighting": "light_control" 등
            }
            
            print("✅ QueryAnalyzer 초기화 완료")
        except Exception as e:
            print(f"❌ QueryAnalyzer 초기화 실패: {e}")
            raise

    async def analyze_query(self, user_text: str) -> RequestAnalysis:
        """사용자 쿼리를 분석하여 요청 유형과 도메인을 추출"""
        print(f"🔍 쿼리 분석 시작: '{user_text}'")
        
        try:
            # 1. Request Type & Domains 분류
            request_result = await self._classify_request(user_text)
            
            # 2. Entity 추출
            entities = await self._extract_entities(
                user_text, 
                request_result["request_type"], 
                request_result["domains"]
            )
            
            # 3. 복합 에이전트 필요성 판단
            requires_multiple = self._check_multiple_agents_needed(request_result)
            
            # 4. 필요한 스킬 식별
            skills_needed = self._identify_required_skills(request_result, entities)
            
            result = RequestAnalysis(
                request_type=request_result["request_type"],
                domains=request_result["domains"],
                confidence=request_result["confidence"],
                entities=entities,
                requires_multiple_agents=requires_multiple,
                agent_skills_needed=skills_needed
            )
            
            print(f"✅ 분석 완료: {result}")
            return result
            
        except Exception as e:
            print(f"❌ 쿼리 분석 오류: {e}")
            # 기본값 반환
            return RequestAnalysis(
                request_type="single_domain",
                domains=["general_chat"],
                confidence=0.5,
                entities=[],
                requires_multiple_agents=False,
                agent_skills_needed=["chit_chat"]
            )

    async def _classify_request(self, user_text: str) -> Dict[str, Any]:
        """요청 유형 및 도메인 분류"""
        try:
            prompt_data = self.prompt_loader.load_prompt("main_agent", "intent_classification")
            
            formatted_prompt = prompt_data["user_prompt_template"].format(
                user_input=user_text
            )
            
            response = await self.llm_client.chat_completion(
                system_prompt=prompt_data["system_prompt"],
                user_prompt=formatted_prompt,
                max_tokens=200
            )
            
            # JSON 응답 파싱
            try:
                result = json.loads(response.strip())
                return {
                    "request_type": result.get("request_type", "single_domain"),
                    "domains": result.get("domains", ["general_chat"]),
                    "confidence": result.get("confidence", 0.5)
                }
            except json.JSONDecodeError:
                # LLM 응답이 JSON이 아닌 경우 키워드 기반 분류
                return self._fallback_request_classification(user_text)
                
        except Exception as e:
            print(f"❌ LLM 요청 분류 실패: {e}")
            return self._fallback_request_classification(user_text)

    def _fallback_request_classification(self, user_text: str) -> Dict[str, Any]:
        """키워드 기반 백업 요청 분류"""
        user_lower = user_text.lower()
        domains = []
        
        # 도메인별 키워드 감지
        weather_keywords = ["날씨", "weather", "기온", "온도", "비", "눈", "맑", "흐림"]
        tv_keywords = ["tv", "티비", "텔레비전", "볼륨", "채널", "전원", "켜", "꺼"]
        chat_keywords = ["안녕", "hello", "hi", "고마워", "감사", "도움", "help", "뭐", "뭘"]
        
        if any(keyword in user_lower for keyword in weather_keywords):
            domains.append("weather")
        if any(keyword in user_lower for keyword in tv_keywords):
            domains.append("tv_control")
        if any(keyword in user_lower for keyword in chat_keywords):
            domains.append("general_chat")
        
        # 연결어 감지
        connection_keywords = ["어울리는", "맞는", "적절한", "따라", "기반으로", "맞춰서", "알맞은"]
        has_connection = any(keyword in user_lower for keyword in connection_keywords)
        
        # 도메인이 없으면 기본값
        if not domains:
            domains = ["general_chat"]
        
        # 요청 유형 결정
        if len(domains) > 1 or (len(domains) == 1 and has_connection and "general_chat" not in domains):
            request_type = "multi_domain"
            confidence = 0.85
        else:
            request_type = "single_domain"
            confidence = 0.80
        
        return {
            "request_type": request_type,
            "domains": domains,
            "confidence": confidence
        }

    async def _extract_entities(self, user_text: str, request_type: str, domains: List[str]) -> List[EntityExtraction]:
        """엔티티 추출"""
        entities = []
        
        try:
            prompt_data = self.prompt_loader.load_prompt("main_agent", "entity_extraction")
            
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
            
            # JSON 응답 파싱
            try:
                result = json.loads(response.strip())
                entities_data = result.get("entities", {})
                
                # entities_data가 딕셔너리 형태인 경우 (새로운 포맷)
                if isinstance(entities_data, dict):
                    for entity_type, entity_value in entities_data.items():
                        if entity_value:  # 값이 있는 경우만 추가
                            entities.append(EntityExtraction(
                                entity_type=entity_type,
                                value=str(entity_value),
                                confidence=result.get("confidence", 0.8)
                            ))
                # entities_data가 리스트 형태인 경우 (기존 포맷)
                elif isinstance(entities_data, list):
                    for entity_data in entities_data:
                        entities.append(EntityExtraction(
                            entity_type=entity_data.get("type", "unknown"),
                            value=entity_data.get("value", ""),
                            confidence=entity_data.get("confidence", 0.5)
                        ))
                    
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 키워드 기반 엔티티 추출
                entities = self._fallback_entity_extraction(user_text, request_type, domains)
                
        except Exception as e:
            print(f"❌ LLM 엔티티 추출 실패: {e}")
            entities = self._fallback_entity_extraction(user_text, request_type, domains)
            
        return entities

    def _fallback_entity_extraction(self, user_text: str, request_type: str, domains: List[str]) -> List[EntityExtraction]:
        """키워드 기반 백업 엔티티 추출"""
        entities = []
        user_lower = user_text.lower()
        
        # 날씨 도메인 엔티티
        if "weather" in domains:
            # 지역 추출
            cities = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "seoul", "busan", "daegu"]
            for city in cities:
                if city in user_lower:
                    entities.append(EntityExtraction("location", city, 0.8))
                    break
            
            # 시간 추출
            time_words = ["오늘", "내일", "모레", "이번주", "다음주", "today", "tomorrow"]
            for time_word in time_words:
                if time_word in user_lower:
                    entities.append(EntityExtraction("time", time_word, 0.7))
                    break
            
            # 날씨 맥락 추출 (복합 요청용)
            if request_type == "multi_domain":
                context_words = ["어울리는", "맞는", "적절한", "따라", "기반으로", "맞춰서"]
                for context in context_words:
                    if context in user_lower:
                        entities.append(EntityExtraction("weather_context", context, 0.8))
                        break
        
        # TV 제어 도메인 엔티티
        if "tv_control" in domains:
            # TV 액션 추출
            if any(word in user_lower for word in ["켜", "on", "전원"]):
                entities.append(EntityExtraction("action", "power_on", 0.8))
            elif any(word in user_lower for word in ["꺼", "off"]):
                entities.append(EntityExtraction("action", "power_off", 0.8))
            elif any(word in user_lower for word in ["볼륨", "volume"]):
                if any(word in user_lower for word in ["올려", "up", "크게"]):
                    entities.append(EntityExtraction("action", "volume_up", 0.8))
                elif any(word in user_lower for word in ["내려", "down", "작게"]):
                    entities.append(EntityExtraction("action", "volume_down", 0.8))
                else:
                    entities.append(EntityExtraction("action", "volume_control", 0.6))
            elif any(word in user_lower for word in ["채널", "channel"]):
                entities.append(EntityExtraction("action", "channel_control", 0.8))
        
        # 일반 대화 도메인 엔티티
        if "general_chat" in domains:
            if any(word in user_lower for word in ["안녕", "hello", "hi"]):
                entities.append(EntityExtraction("chat_type", "greeting", 0.9))
            elif any(word in user_lower for word in ["고마워", "감사", "thanks"]):
                entities.append(EntityExtraction("chat_type", "thanks", 0.9))
            elif any(word in user_lower for word in ["도움", "help", "뭐", "뭘"]):
                entities.append(EntityExtraction("chat_type", "help", 0.8))
        
        # 복합 요청 엔티티
        if request_type == "multi_domain":
            entities.append(EntityExtraction("connection_type", "contextual", 0.9))
            entities.append(EntityExtraction("request_scope", "all_domains", 0.9))
                
        return entities

    def _check_multiple_agents_needed(self, request_result: Dict[str, Any]) -> bool:
        """복합 에이전트 필요성 판단"""
        # multi_domain이면 무조건 복합 처리 필요
        if request_result["request_type"] == "multi_domain":
            return True
        
        # single_domain이지만 여러 도메인이 있는 경우
        if len(request_result["domains"]) > 1:
            return True
            
        return False

    def _identify_required_skills(self, request_result: Dict[str, Any], entities: List[EntityExtraction]) -> List[str]:
        """필요한 스킬 식별"""
        skills = set()  # 중복 제거를 위해 set 사용
        
        # 도메인 기반 스킬 식별
        for domain in request_result["domains"]:
            if domain in self.domain_to_skill:
                skills.add(self.domain_to_skill[domain])
        
        # 복합 요청의 경우 orchestration 스킬 추가
        if request_result["request_type"] == "multi_domain":
            skills.add("orchestration")
        
        # Entity 기반 추가 스킬 식별 (백업)
        for entity in entities:
            if entity.entity_type in ["location", "time", "weather_context"]:
                skills.add("weather_info")
            elif entity.entity_type in ["action", "channel", "volume_level", "tv_context"]:
                skills.add("tv_control")
            elif entity.entity_type in ["chat_type", "topic"]:
                skills.add("chit_chat")
            elif entity.entity_type in ["connection_type", "request_scope"]:
                skills.add("orchestration")
                
        return list(skills) 