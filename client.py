#!/usr/bin/env python3
"""
A2A Interactive Client
A2A 에이전트와 대화할 수 있는 대화형 클라이언트
"""
import asyncio
import json
import uuid
from typing import Dict, Any, Optional
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import print as rprint

class A2AClient:
    """A2A 프로토콜 클라이언트"""
    
    def __init__(self, base_url: str = "http://localhost:18000"):
        self.base_url = base_url.rstrip('/')
        self.console = Console()
        # 모든 에이전트 URL 정의
        self.agent_urls = {
            "Main Agent (Orchestrator)": "http://localhost:18000",
            "Weather Agent": "http://localhost:18001", 
            "TV Agent": "http://localhost:18002"
        }
        
    async def get_agent_card(self, url: str = None) -> Optional[Dict[str, Any]]:
        """Agent Card 조회"""
        if url is None:
            url = self.base_url
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/.well-known/agent.json")
                if response.status_code == 200:
                    return response.json()
                else:
                    self.console.print(f"[red]Agent Card 조회 실패 ({url}): {response.status_code}[/red]")
                    return None
        except Exception as e:
            self.console.print(f"[red]연결 오류 ({url}): {e}[/red]")
            return None
    
    async def get_all_agent_cards(self) -> Dict[str, Dict[str, Any]]:
        """모든 에이전트의 Agent Card 조회"""
        agent_cards = {}
        for name, url in self.agent_urls.items():
            card = await self.get_agent_card(url)
            if card:
                agent_cards[name] = card
        return agent_cards
    
    async def send_message(self, text: str, show_raw: bool = False) -> Optional[Dict[str, Any]]:
        """메시지 전송"""
        try:
            message_id = str(uuid.uuid4())
            request_id = str(uuid.uuid4())
            
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": text}],
                        "messageId": message_id
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if show_raw:
                        self.console.print("\n[dim]Raw Response:[/dim]")
                        self.console.print(json.dumps(result, indent=2, ensure_ascii=False))
                    return result
                else:
                    self.console.print(f"[red]요청 실패: {response.status_code}[/red]")
                    self.console.print(response.text)
                    return None
                    
        except Exception as e:
            self.console.print(f"[red]메시지 전송 오류: {e}[/red]")
            return None
    
    def display_agent_card(self, agent_cards: Dict[str, Dict[str, Any]]):
        """Agent Card들 예쁘게 출력"""
        for agent_name, agent_card in agent_cards.items():
            table = Table(title=f"🤖 {agent_name}")
            table.add_column("속성", style="cyan", width=20)
            table.add_column("값", style="white")
            
            table.add_row("이름", agent_card.get("name", "N/A"))
            table.add_row("설명", agent_card.get("description", "N/A"))
            table.add_row("버전", agent_card.get("version", "N/A"))
            table.add_row("프로토콜 버전", agent_card.get("protocolVersion", "N/A"))
            table.add_row("URL", agent_card.get("url", "N/A"))
            table.add_row("입력 모드", ", ".join(agent_card.get("defaultInputModes", [])))
            table.add_row("출력 모드", ", ".join(agent_card.get("defaultOutputModes", [])))
            
            self.console.print(table)
            
            # Skills 표시
            skills = agent_card.get("skills", [])
            if skills:
                skills_table = Table(title=f"🔧 {agent_name} Skills")
                skills_table.add_column("ID", style="cyan")
                skills_table.add_column("이름", style="yellow")
                skills_table.add_column("설명", style="white")
                skills_table.add_column("태그", style="green")
                
                for skill in skills:
                    tags = ", ".join(skill.get("tags", []))
                    skills_table.add_row(
                        skill.get("id", "N/A"),
                        skill.get("name", "N/A"),
                        skill.get("description", "N/A"),
                        tags
                    )
                
                self.console.print(skills_table)
            
            self.console.print()  # 빈 줄 추가
    
    def extract_response_text(self, response: Dict[str, Any]) -> str:
        """응답에서 텍스트 추출"""
        try:
            result = response.get("result", {})
            parts = result.get("parts", [])
            
            full_text = ""
            for part in parts:
                if part.get("kind") == "text":
                    text = part.get("text", "")
                    full_text += text
            
            # JSON으로 감싸진 응답인지 확인
            if full_text.strip().startswith("```json") and full_text.strip().endswith("```"):
                # JSON 블록에서 실제 JSON 추출
                json_content = full_text.strip()[7:-3].strip()  # ```json과 ``` 제거
                try:
                    parsed = json.loads(json_content)
                    if isinstance(parsed, dict) and "response" in parsed:
                        return parsed["response"]
                except:
                    pass
            
            return full_text
            
        except Exception as e:
            return f"응답 파싱 오류: {e}"
    
    def display_response(self, response: Dict[str, Any]):
        """응답 예쁘게 출력"""
        if "result" in response:
            text = self.extract_response_text(response)
            
            panel = Panel(
                Text(text, style="white"),
                title="🤖 Agent Response",
                title_align="left",
                border_style="blue"
            )
            self.console.print(panel)
            
            # 메타데이터 표시
            result = response.get("result", {})
            self.console.print(f"[dim]Message ID: {result.get('messageId', 'N/A')}[/dim]")
            self.console.print(f"[dim]Task ID: {result.get('taskId', 'N/A')}[/dim]")
        else:
            self.console.print("[red]응답에 result가 없습니다.[/red]")
    
    async def interactive_menu(self):
        """대화형 메뉴"""
        self.console.print("\n[bold blue]🚀 A2A Interactive Client[/bold blue]")
        self.console.print(f"[dim]Connected to: {self.base_url}[/dim]\n")
        
        # 연결 테스트
        agent_card = await self.get_agent_card()
        if not agent_card:
            self.console.print("[red]❌ 에이전트에 연결할 수 없습니다. main.py가 실행 중인지 확인하세요.[/red]")
            return
        
        self.console.print("[green]✅ 에이전트 연결 성공![/green]\n")
        
        while True:
            self.console.print("\n[bold yellow]📋 메뉴를 선택하세요:[/bold yellow]")
            self.console.print("1. 📋 모든 Agent Card 보기")
            self.console.print("2. 🌤️  날씨 문의 테스트 (→ Weather Agent)")
            self.console.print("3. 📺 TV 제어 테스트 (→ TV Agent)")
            self.console.print("4. 💬 일반 대화 테스트 (Main Agent)")
            self.console.print("5. ✏️  직접 메시지 입력")
            self.console.print("6. 🔧 Raw 응답 보기 ON/OFF")
            self.console.print("7. 🌐 다른 Agent에 직접 연결")
            self.console.print("0. 🚪 종료")
            
            choice = self.console.input("\n[cyan]선택 (0-7): [/cyan]").strip()
            
            if choice == "0":
                self.console.print("[yellow]👋 안녕히 가세요![/yellow]")
                break
            elif choice == "1":
                await self.show_agent_card()
            elif choice == "2":
                await self.test_weather()
            elif choice == "3":
                await self.test_tv_control()
            elif choice == "4":
                await self.test_general_chat()
            elif choice == "5":
                await self.custom_message()
            elif choice == "6":
                self.toggle_raw_mode()
            elif choice == "7":
                await self.direct_agent_connection()
            else:
                self.console.print("[red]잘못된 선택입니다.[/red]")
    
    async def show_agent_card(self):
        """모든 Agent Card 표시"""
        self.console.print("\n[bold]🤖 모든 Agent Card 조회 중...[/bold]")
        agent_cards = await self.get_all_agent_cards()
        if agent_cards:
            self.display_agent_card(agent_cards)
            
            # 연결 상태 요약
            self.console.print("[bold]📊 연결 상태 요약:[/bold]")
            status_table = Table()
            status_table.add_column("에이전트", style="cyan")
            status_table.add_column("상태", style="white")
            status_table.add_column("URL", style="dim")
            
            for name, url in self.agent_urls.items():
                if name in agent_cards:
                    status_table.add_row(name, "[green]✅ 연결됨[/green]", url)
                else:
                    status_table.add_row(name, "[red]❌ 연결 실패[/red]", url)
            
            self.console.print(status_table)
        else:
            self.console.print("[red]❌ 모든 에이전트 연결에 실패했습니다.[/red]")
    
    async def test_weather(self):
        """날씨 테스트"""
        weather_queries = [
            "오늘 날씨 어때?",
            "서울 날씨 알려줘",
            "내일 비 와?",
            "날씨 좋아?"
        ]
        
        self.console.print("\n[bold]🌤️ 날씨 문의 테스트[/bold]")
        for i, query in enumerate(weather_queries, 1):
            self.console.print(f"\n[cyan]{i}. {query}[/cyan]")
            
            response = await self.send_message(query, getattr(self, 'show_raw', False))
            if response:
                self.display_response(response)
            
            if i < len(weather_queries):
                self.console.input("\n[dim]다음 테스트를 위해 Enter를 눌러주세요...[/dim]")
    
    async def test_tv_control(self):
        """TV 제어 테스트"""
        tv_commands = [
            "TV 볼륨 올려줘",
            "채널 7번으로 바꿔줘",
            "TV 꺼줘",
            "볼륨 내려줘"
        ]
        
        self.console.print("\n[bold]📺 TV 제어 테스트[/bold]")
        for i, command in enumerate(tv_commands, 1):
            self.console.print(f"\n[cyan]{i}. {command}[/cyan]")
            
            response = await self.send_message(command, getattr(self, 'show_raw', False))
            if response:
                self.display_response(response)
            
            if i < len(tv_commands):
                self.console.input("\n[dim]다음 테스트를 위해 Enter를 눌러주세요...[/dim]")
    
    async def test_general_chat(self):
        """일반 대화 테스트"""
        chat_messages = [
            "안녕하세요",
            "고마워요",
            "뭘 할 수 있어?",
            "도움이 필요해"
        ]
        
        self.console.print("\n[bold]💬 일반 대화 테스트[/bold]")
        for i, message in enumerate(chat_messages, 1):
            self.console.print(f"\n[cyan]{i}. {message}[/cyan]")
            
            response = await self.send_message(message, getattr(self, 'show_raw', False))
            if response:
                self.display_response(response)
            
            if i < len(chat_messages):
                self.console.input("\n[dim]다음 테스트를 위해 Enter를 눌러주세요...[/dim]")
    
    async def custom_message(self):
        """사용자 정의 메시지"""
        self.console.print("\n[bold]✏️ 직접 메시지 입력[/bold]")
        
        while True:
            message = self.console.input("[cyan]메시지를 입력하세요 (빈 줄로 돌아가기): [/cyan]").strip()
            
            if not message:
                break
            
            self.console.print(f"\n[dim]전송: {message}[/dim]")
            response = await self.send_message(message, getattr(self, 'show_raw', False))
            if response:
                self.display_response(response)
    
    async def direct_agent_connection(self):
        """다른 Agent에 직접 연결"""
        self.console.print("\n[bold]🌐 직접 Agent 연결[/bold]")
        
        # 사용 가능한 에이전트 목록 표시
        self.console.print("사용 가능한 에이전트:")
        for i, (name, url) in enumerate(self.agent_urls.items(), 1):
            self.console.print(f"{i}. {name} ({url})")
        
        choice = self.console.input("\n[cyan]연결할 에이전트 번호 (빈 줄로 돌아가기): [/cyan]").strip()
        
        if not choice:
            return
        
        try:
            agent_index = int(choice) - 1
            agent_names = list(self.agent_urls.keys())
            
            if 0 <= agent_index < len(agent_names):
                selected_name = agent_names[agent_index]
                selected_url = self.agent_urls[selected_name]
                
                self.console.print(f"\n[bold]📡 {selected_name}에 연결 중...[/bold]")
                
                # Agent Card 확인
                agent_card = await self.get_agent_card(selected_url)
                if not agent_card:
                    self.console.print(f"[red]❌ {selected_name}에 연결할 수 없습니다.[/red]")
                    return
                
                self.console.print(f"[green]✅ {selected_name} 연결 성공![/green]")
                
                # 직접 대화
                while True:
                    message = self.console.input(f"\n[cyan]{selected_name}에게 메시지 (빈 줄로 돌아가기): [/cyan]").strip()
                    
                    if not message:
                        break
                    
                    # 선택된 Agent로 직접 요청
                    response = await self.send_message_to_agent(message, selected_url)
                    if response:
                        self.display_response(response)
            else:
                self.console.print("[red]잘못된 에이전트 번호입니다.[/red]")
                
        except ValueError:
            self.console.print("[red]숫자를 입력해주세요.[/red]")
    
    async def send_message_to_agent(self, text: str, agent_url: str, show_raw: bool = False) -> Optional[Dict[str, Any]]:
        """특정 Agent에 메시지 전송"""
        try:
            message_id = str(uuid.uuid4())
            request_id = str(uuid.uuid4())
            
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"kind": "text", "text": text}],
                        "messageId": message_id
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{agent_url}/",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if show_raw or getattr(self, 'show_raw', False):
                        self.console.print(f"\n[dim]Raw Response from {agent_url}:[/dim]")
                        self.console.print(json.dumps(result, indent=2, ensure_ascii=False))
                    return result
                else:
                    self.console.print(f"[red]요청 실패 ({agent_url}): {response.status_code}[/red]")
                    self.console.print(response.text)
                    return None
                    
        except Exception as e:
            self.console.print(f"[red]메시지 전송 오류 ({agent_url}): {e}[/red]")
            return None
    
    def toggle_raw_mode(self):
        """Raw 모드 토글"""
        self.show_raw = not getattr(self, 'show_raw', False)
        status = "ON" if self.show_raw else "OFF"
        self.console.print(f"\n[yellow]🔧 Raw 응답 표시: {status}[/yellow]")

async def main():
    """메인 함수"""
    client = A2AClient()
    await client.interactive_menu()

if __name__ == "__main__":
    asyncio.run(main())