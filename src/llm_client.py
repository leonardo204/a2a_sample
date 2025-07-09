"""
Azure OpenAI LLM Client
Azure OpenAI API를 사용한 LLM 통신 클라이언트
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from openai import AsyncAzureOpenAI
from loguru import logger
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()


class AzureLLMClient:
    """Azure OpenAI API 클라이언트"""
    
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION")
        
        if not all([self.endpoint, self.api_key, self.deployment_name, self.api_version]):
            raise ValueError("Azure OpenAI 환경변수가 설정되지 않았습니다. .env 파일을 확인해주세요.")
        
        self.client = AsyncAzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version=self.api_version
        )
        
        logger.info("Azure OpenAI 클라이언트 초기화 완료")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]] = None,
        system_prompt: str = None,
        user_prompt: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Azure OpenAI Chat Completion API 호출
        
        Args:
            messages: 메시지 리스트 [{"role": "system", "content": "..."}, ...] (선택사항)
            system_prompt: 시스템 프롬프트 (선택사항)
            user_prompt: 사용자 프롬프트 (선택사항)
            temperature: 응답의 창의성 (0.0-1.0)
            max_tokens: 최대 토큰 수
            response_format: 응답 형식 지정 (예: {"type": "json_object"})
        
        Returns:
            LLM 응답 텍스트
        """
        try:
            # 메시지 구성 방식 결정
            if messages is not None:
                # 기존 방식: messages 직접 전달
                final_messages = messages
            elif system_prompt or user_prompt:
                # 새 방식: system_prompt, user_prompt 분리 전달
                final_messages = []
                if system_prompt:
                    final_messages.append({"role": "system", "content": system_prompt})
                if user_prompt:
                    final_messages.append({"role": "user", "content": user_prompt})
            else:
                raise ValueError("messages 또는 system_prompt/user_prompt 중 하나는 제공되어야 합니다.")
            
            kwargs = {
                "model": self.deployment_name,
                "messages": final_messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # JSON 형식 응답이 필요한 경우
            if response_format:
                kwargs["response_format"] = response_format
            
            response = await self.client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content
            logger.debug(f"LLM 응답: {content}")
            
            return content.strip()
            
        except Exception as e:
            logger.error(f"Azure OpenAI API 호출 실패: {e}")
            raise
    
    async def get_intent_classification(self, user_input: str, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """의도 분류 요청"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt.format(user_input=user_input)}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {
                "intent": "chit_chat",
                "confidence": 0.5,
                "reasoning": "JSON 파싱 실패로 기본값 반환"
            }
    
    async def get_entity_extraction(
        self, 
        user_input: str, 
        intent: str, 
        system_prompt: str, 
        user_prompt: str
    ) -> Dict[str, Any]:
        """엔티티 추출 요청"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt.format(user_input=user_input, intent=intent)}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {
                "entities": {},
                "extracted_values": [],
                "confidence": 0.5
            }
    
    async def get_orchestration_decision(
        self,
        user_input: str,
        intent: str,
        entities: Dict[str, Any],
        system_prompt: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        """오케스트레이션 결정 요청"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt.format(
                user_input=user_input,
                intent=intent,
                entities=json.dumps(entities, ensure_ascii=False)
            )}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=400,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {
                "routing_decision": "direct_handle",
                "target_agent": None,
                "action_type": "chat",
                "priority": "low",
                "requires_context": False,
                "reasoning": "JSON 파싱 실패로 기본값 반환"
            }
    
    async def get_chitchat_response(
        self,
        user_input: str,
        system_prompt: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        """잡담 응답 생성"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt.format(user_input=user_input)}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            temperature=0.7,
            max_tokens=300,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {
                "response": "죄송합니다. 응답을 생성하는 중 오류가 발생했습니다.",
                "suggest_features": [],
                "tone": "helpful"
            }
    
    async def get_service_response(
        self,
        context: Dict[str, Any],
        system_prompt: str,
        user_prompt: str
    ) -> Dict[str, Any]:
        """서비스 에이전트 응답 생성"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt.format(**context)}
        ]
        
        response = await self.chat_completion(
            messages=messages,
            temperature=0.5,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"JSON 파싱 실패: {response}")
            return {
                "response": "서비스 응답을 생성하는 중 오류가 발생했습니다.",
                "success": False
            }


# LLMClient alias for backward compatibility
LLMClient = AzureLLMClient 