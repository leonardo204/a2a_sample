"""
Prompt Loader
YAML 형식의 프롬프트 파일들을 로드하고 관리
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class PromptLoader:
    """YAML 프롬프트 파일 로더"""
    
    def __init__(self, prompt_base_dir: str = "prompt"):
        self.base_dir = Path(prompt_base_dir)
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        if not self.base_dir.exists():
            raise FileNotFoundError(f"프롬프트 디렉토리를 찾을 수 없습니다: {self.base_dir}")
        
        logger.info(f"프롬프트 로더 초기화: {self.base_dir}")
    
    def load_prompt(self, agent_name: str, prompt_file: str) -> Dict[str, Any]:
        """
        특정 에이전트의 프롬프트 파일 로드
        
        Args:
            agent_name: 에이전트 이름 (main_agent, weather_agent, tv_agent)
            prompt_file: 프롬프트 파일명 (.yaml 확장자 제외)
        
        Returns:
            프롬프트 딕셔너리
        """
        cache_key = f"{agent_name}_{prompt_file}"
        
        # 캐시에서 확인
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # 파일 경로 구성
        file_path = self.base_dir / agent_name / f"{prompt_file}.yaml"
        
        if not file_path.exists():
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                prompt_data = yaml.safe_load(f)
            
            # 캐시에 저장
            self.cache[cache_key] = prompt_data
            logger.debug(f"프롬프트 파일 로드: {file_path}")
            
            return prompt_data
            
        except yaml.YAMLError as e:
            logger.error(f"YAML 파싱 오류: {file_path} - {e}")
            raise
        except Exception as e:
            logger.error(f"프롬프트 파일 로드 실패: {file_path} - {e}")
            raise
    
    def get_system_prompt(self, agent_name: str, prompt_file: str) -> str:
        """시스템 프롬프트 가져오기"""
        prompt_data = self.load_prompt(agent_name, prompt_file)
        return prompt_data.get("system_prompt", "")
    
    def get_user_prompt_template(self, agent_name: str, prompt_file: str) -> str:
        """사용자 프롬프트 템플릿 가져오기"""
        prompt_data = self.load_prompt(agent_name, prompt_file)
        return prompt_data.get("user_prompt_template", "")
    
    def get_examples(self, agent_name: str, prompt_file: str) -> list:
        """예시 데이터 가져오기"""
        prompt_data = self.load_prompt(agent_name, prompt_file)
        return prompt_data.get("examples", [])
    
    def reload_cache(self):
        """캐시 초기화 (프롬프트 파일 변경 시 사용)"""
        self.cache.clear()
        logger.info("프롬프트 캐시가 초기화되었습니다.")
    
    def list_available_prompts(self, agent_name: str) -> list:
        """특정 에이전트의 사용 가능한 프롬프트 파일 목록"""
        agent_dir = self.base_dir / agent_name
        
        if not agent_dir.exists():
            return []
        
        yaml_files = list(agent_dir.glob("*.yaml"))
        return [f.stem for f in yaml_files]
    
    def validate_prompt_structure(self, agent_name: str, prompt_file: str) -> bool:
        """프롬프트 파일 구조 검증"""
        try:
            prompt_data = self.load_prompt(agent_name, prompt_file)
            
            # 필수 필드 확인
            required_fields = ["system_prompt", "user_prompt_template"]
            for field in required_fields:
                if field not in prompt_data:
                    logger.warning(f"프롬프트 파일에 필수 필드가 없습니다: {field}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"프롬프트 구조 검증 실패: {e}")
            return False


# 전역 프롬프트 로더 인스턴스
_prompt_loader: Optional[PromptLoader] = None


def get_prompt_loader() -> PromptLoader:
    """프롬프트 로더 싱글톤 인스턴스 가져오기"""
    global _prompt_loader
    
    if _prompt_loader is None:
        # 프로젝트 루트에서 prompt 디렉토리 찾기
        current_dir = Path(__file__).parent
        prompt_dir = current_dir.parent / "prompt"
        
        _prompt_loader = PromptLoader(str(prompt_dir))
    
    return _prompt_loader 