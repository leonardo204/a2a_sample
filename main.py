#!/usr/bin/env python3
"""
A2A Multi-Agent System Launcher
A2A SDK 공식 패턴 사용
"""
import asyncio
import uvicorn
import requests
import time
import signal
import sys
from multiprocessing import Process
from pathlib import Path

# A2A SDK 공식 패턴 에이전트들 import
from src.main_agent import create_main_agent
from src.weather_agent import create_weather_agent  
from src.tv_agent import create_tv_agent

def run_agent(agent_func, host="0.0.0.0", port=18000):
    """개별 에이전트 실행 함수"""
    try:
        print(f"Starting agent on port {port}")
        app = agent_func()
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except Exception as e:
        print(f"Error starting agent on port {port}: {e}")

def check_agent_health(port):
    """에이전트 상태 확인"""
    try:
        response = requests.get(f"http://localhost:{port}/.well-known/agent.json", timeout=5)
        return response.status_code == 200
    except:
        return False

def wait_for_agents(ports, max_wait=30):
    """모든 에이전트가 준비될 때까지 대기"""
    print("🔄 Waiting for agents to start...")
    for port in ports:
        start_time = time.time()
        while time.time() - start_time < max_wait:
            if check_agent_health(port):
                print(f"✅ Agent on port {port} is ready")
                break
            time.sleep(1)
        else:
            print(f"❌ Agent on port {port} failed to start within {max_wait} seconds")
            return False
    return True

def signal_handler(sig, frame):
    """Ctrl+C 핸들러"""
    print("\n🛑 Shutting down all agents...")
    sys.exit(0)

def main():
    """메인 실행 함수"""
    print("🚀 Starting A2A Multi-Agent System...")
    
    # Ctrl+C 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    
    # 에이전트 프로세스 시작
    processes = []
    
    try:
        # Weather Agent (포트 18001)
        weather_process = Process(target=run_agent, args=(create_weather_agent, "0.0.0.0", 18001))
        weather_process.start()
        processes.append(weather_process)
        
        # TV Agent (포트 18002)  
        tv_process = Process(target=run_agent, args=(create_tv_agent, "0.0.0.0", 18002))
        tv_process.start()
        processes.append(tv_process)
        
        # Main Agent (포트 18000) - 마지막에 시작
        main_process = Process(target=run_agent, args=(create_main_agent, "0.0.0.0", 18000))
        main_process.start()
        processes.append(main_process)
        
        # 모든 에이전트가 준비될 때까지 대기
        if not wait_for_agents([18001, 18002, 18000]):
            raise Exception("Failed to start all agents")
        
        # 시스템 상태 출력
        print("\n🔍 System Status:")
        print("=" * 50)
        print("✅ Weather Agent: 포트 18001에서 실행 중")
        print("✅ TV Agent: 포트 18002에서 실행 중") 
        print("✅ Main Agent (Orchestrator): 포트 18000에서 실행 중")
        print("=" * 50)
        print("\n🎉 All agents started successfully!\n")
        print("✨ System is running. Press Ctrl+C to stop.\n")
        
        # 사용 예제 출력
        print("📖 Usage Examples:")
        print("  # JSON-RPC 방식 (올바른 방법)")
        print("  curl -X POST http://localhost:18000/ \\")
        print("    -H 'Content-Type: application/json' \\")
        print("    -d '{")
        print("      \"jsonrpc\": \"2.0\",")
        print("      \"id\": \"test-123\",")
        print("      \"method\": \"message/send\",")
        print("      \"params\": {")
        print("        \"message\": {")
        print("          \"role\": \"user\",")
        print("          \"parts\": [{\"kind\": \"text\", \"text\": \"서울 날씨 어때?\"}],")
        print("          \"messageId\": \"msg-123\"")
        print("        }")
        print("      }")
        print("    }'")
        print()
        print("  # Agent Card 확인")
        print("  curl -s http://localhost:18000/.well-known/agent.json | jq")
        print()
        print("  # 대화형 클라이언트 실행")
        print("  uv run client.py")
        print()
        
        # 메인 프로세스들이 종료될 때까지 대기
        for process in processes:
            process.join()
            
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        # 모든 프로세스 종료
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
        print("✅ All agents stopped.")

if __name__ == "__main__":
    main()