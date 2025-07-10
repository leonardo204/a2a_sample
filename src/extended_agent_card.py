#!/usr/bin/env python3
"""
Extended Agent Card
A2A 멀티 에이전트 시스템을 위한 확장된 Agent Card 구조
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime


@dataclass
class EntityTypeInfo:
    """엔티티 타입 정보"""
    name: str                              # 엔티티 타입명
    description: str                       # 설명
    examples: List[str]                    # 예시 값들


@dataclass
class ExtendedAgentSkill:
    """확장된 Agent Skill 정보"""
    id: str
    name: str
    description: str
    tags: List[str]
    
    # 새로 추가할 필드들
    domain_category: str                   # 도메인 분류 (weather, tv_control 등)
    keywords: List[str]                    # 스킬 식별 키워드
    entity_types: List[EntityTypeInfo]     # 처리 가능한 엔티티
    intent_patterns: List[str]             # 의도 패턴
    connection_patterns: List[str]         # 복합 요청 연결어
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 형태로 변환"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "domain_category": self.domain_category,
            "keywords": self.keywords,
            "entity_types": [
                {
                    "name": entity.name,
                    "description": entity.description,
                    "examples": entity.examples
                }
                for entity in self.entity_types
            ],
            "intent_patterns": self.intent_patterns,
            "connection_patterns": self.connection_patterns
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtendedAgentSkill":
        """딕셔너리에서 객체 생성"""
        entity_types = []
        for entity_data in data.get("entity_types", []):
            entity_types.append(EntityTypeInfo(
                name=entity_data["name"],
                description=entity_data["description"],
                examples=entity_data["examples"]
            ))
        
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            tags=data.get("tags", []),
            domain_category=data.get("domain_category", "general"),
            keywords=data.get("keywords", []),
            entity_types=entity_types,
            intent_patterns=data.get("intent_patterns", []),
            connection_patterns=data.get("connection_patterns", [])
        )


@dataclass
class ExtendedRegisteredAgent:
    """확장된 등록 Agent 정보"""
    agent_id: str
    name: str
    description: str
    url: str
    agent_card: Dict[str, Any]
    skills: List[ExtendedAgentSkill]
    registered_at: datetime
    last_health_check: Optional[datetime] = None
    is_healthy: bool = True 