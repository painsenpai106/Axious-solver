# api.py
"""
FastAPI server for hCaptcha Solver
- Endpoint: POST /solve
- Expects JSON: {"sitekey": "...", "rqdata": "...", "host": "discord.com", "proxy": "..."}
- Returns solved token or error
"""

import os
import asyncio
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

import tls_client
import re
from colorama import Fore, Style, init

# ────────────────────────────────────────────────────────────────
# FastAPI imports
# ────────────────────────────────────────────────────────────────
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# ────────────────────────────────────────────────────────────────
# Your original imports / modules
# ────────────────────────────────────────────────────────────────
from main import hsw
from motion import motion_data
from agent import AIAgent

init(autoreset=True)

# Debug mode from environment variable (Railway / .env)
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

def debug_print(message: str):
    if DEBUG_MODE:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.WHITE}{ts}{Style.RESET_ALL} │ {Fore.CYAN}SOLVER{Style.RESET_ALL} │ {Fore.WHITE}{message}{Style.RESET_ALL}")

def realtime_print(message: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}{ts}{Style.RESET_ALL} │ {Fore.CYAN}SOLVER{Style.RESET_ALL} │ {Fore.BRIGHT}{Style.BRIGHT}{message}{Style.RESET_ALL}")

# ────────────────────────────────────────────────────────────────
# Your original functions (unchanged)
# ────────────────────────────────────────────────────────────────

def create_session(proxy=None):
    session = tls_client.Session(
        client_identifier="chrome_130",
        random_tls_extension_order=True
    )
    
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
    
    session.headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': user_agent
    }
    
    if proxy:
        proxy_url = f'http://{proxy}' if '@' not in proxy else f'http://{proxy}'
        session.proxies = {'http': proxy_url, 'https': proxy_url}
        debug_print(f"Using proxy: {proxy.split('@')[1] if '@' in proxy else proxy}")
        
        try:
            debug_print("Testing proxy connection...")
            test_response = session.get('https://api.ipify.org?format=json')
            if test_response.status_code == 200:
                ip_info = test_response.json()
                debug_print(f"✓ Proxy working! IP: {ip_info.get('ip')}")
            else:
                debug_print(f"✗ Proxy test failed: status {test_response.status_code}")
        except Exception as e:
            debug_print(f"✗ Proxy connection error: {str(e)}")
    else:
        debug_print("No proxy configured")
    
    return session

def get_hcaptcha_version(proxy=None) -> str:
    try:
        debug_print("Fetching hCaptcha version...")
        session = create_session(proxy)
        api_js = session.get('https://hcaptcha.com/1/api.js?render=explicit&onload=hcaptchaOnLoad').text
        version_matches = re.findall(r'v1/([A-Za-z0-9]+)/static', api_js)
        if len(version_matches) > 1:
            version = version_matches[1]
            debug_print(f"hCaptcha version: {version}")
            return version
        default_version = "c3663008fb8d8104807d55045f8251cbe96a2f84"
        debug_print(f"Using default version: {default_version}")
        return default_version
    except Exception as e:
        debug_print(f"Error fetching version: {str(e)}")
        return "c3663008fb8d8104807d55045f8251cbe96a2f84"

# ────────────────────────────────────────────────────────────────
# Your HCaptchaSolver class (unchanged — copy-paste your version here)
# ────────────────────────────────────────────────────────────────

class HCaptchaSolver:
    def __init__(self, sitekey: str, host: str, rqdata: str = None, proxy: str = None, real_time_mode: bool = False):
        self.sitekey = sitekey
        self.host = host.split("//")[-1].split("/")[0]
        self.rqdata = rqdata
        self.proxy = proxy
        self.session = create_session(proxy)
        self.motion = motion_data(self.session.headers["user-agent"], f"https://{self.host}")
        self.ai_agent = AIAgent()
        self.real_time_mode = real_time_mode
        self.HCAPTCHA_VERSION = get_hcaptcha_version(proxy)
        
        debug_print(f"Initializing HCaptchaSolver:")
        debug_print(f"  Sitekey: {sitekey}")
        debug_print(f"  Host: {self.host}")
        debug_print(f"  RQData: {rqdata[:50] if rqdata else 'None'}...")
        debug_print(f"  Proxy: {proxy.split('@')[1] if proxy and '@' in proxy else proxy if proxy else 'None'}")
        debug_print(f"  Version: {self.HCAPTCHA_VERSION}")
        
        self.stats = {
            'total_attempts': 0,
            'successful_solves': 0,
            'challenge_types': {},
            'start_time': time.time(),
            'last_solve_time': None
        }

    # ... (paste ALL the remaining methods from your original solver.py here:
    # get_site_config, get_hsw_token, fetch_challenge, format_challenge_answers,
    # submit_solution, solve_captcha)

    # Make sure solve_captcha is async and returns dict with 'success', 'token', etc.

# ────────────────────────────────────────────────────────────────
# FastAPI application
# ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Discord hCaptcha Solver API",
    description="Solves hCaptcha challenges using Groq vision + Multibot mouse simulation",
    version="1.0.0"
)

class SolveRequest(BaseModel):
    sitekey: str
    rqdata: Optional[str] = None
    host: str = "discord.com"
    proxy: Optional[str] = None
    real_time_mode: bool = True

@app.post("/solve")
async def solve_endpoint(request: SolveRequest):
    debug_print(f"New solve request received → sitekey={request.sitekey}")

    try:
        solver = HCaptchaSolver(
            sitekey=request.sitekey,
            host=request.host,
            rqdata=request.rqdata,
            proxy=request.proxy,
            real_time_mode=request.real_time_mode
        )

        # Load API keys from environment variables (Railway style)
        solver.GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        solver.MULTIBOT_API_KEY = os.getenv("MULTIBOT_API_KEY")

        if not solver.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY is not set in environment variables")

        result = await solver.solve_captcha()

        if result.get("success"):
            realtime_print(f"Solved → token: {result.get('token', '???')[:35]}...")
            return {
                "status": "success",
                "token": result.get("token"),
                "time_taken": result.get("time_taken", 0),
                "challenges_solved": result.get("challenges_solved", 0),
                "message": result.get("message", "Solved")
            }
        else:
            realtime_print(f"Failed: {result.get('error', 'Unknown error')}")
            raise HTTPException(status_code=500, detail=result.get("error", "Solve failed"))

    except Exception as e:
        import traceback
        error_detail = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc(limit=3)}"
        debug_print(f"Solve endpoint error: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "debug": DEBUG_MODE}

# ────────────────────────────────────────────────────────────────
# Run the server
# ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))  # Railway / Docker uses $PORT
    debug_print(f"Starting API server on port {port}")
    
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=False,           # False = production / Railway
        workers=1,              # Usually 1 is enough for captcha solving
        log_level="info"
    )
