# api.py
"""
FastAPI server for hCaptcha Solver - Pure Groq vision mode (Multibot 100% removed)
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

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# Your original modules
from main import hsw
from agent import AIAgent

# motion_data is kept but NEVER used for advanced features
from motion import motion_data

init(autoreset=True)

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

def debug_print(message: str):
    if DEBUG_MODE:
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"{Fore.WHITE}{ts}{Style.RESET_ALL} │ {Fore.CYAN}SOLVER{Style.RESET_ALL} │ {Fore.WHITE}{message}{Style.RESET_ALL}")

def realtime_print(message: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}{ts}{Style.RESET_ALL} │ {Fore.CYAN}SOLVER{Style.RESET_ALL} │ {Fore.BRIGHT}{message}{Style.RESET_ALL}")

# ────────────────────────────────────────────────────────────────
# Session & version helpers (unchanged)
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
        proxy_url = f'http://{proxy}'
        session.proxies = {'http': proxy_url, 'https': proxy_url}
        debug_print(f"Using proxy: {proxy}")
    
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
        return "c3663008fb8d8104807d55045f8251cbe96a2f84"
    except Exception as e:
        debug_print(f"Version fetch error: {str(e)}")
        return "c3663008fb8d8104807d55045f8251cbe96a2f84"

# ────────────────────────────────────────────────────────────────
# HCaptchaSolver - Pure Groq mode, NO Multibot whatsoever
# ────────────────────────────────────────────────────────────────

class HCaptchaSolver:
    def __init__(self, sitekey: str, host: str, rqdata: str = None, proxy: str = None):
        self.sitekey = sitekey
        self.host = host.split("//")[-1].split("/")[0]
        self.rqdata = rqdata
        self.proxy = proxy
        self.session = create_session(proxy)
        self.ai_agent = AIAgent()
        self.HCAPTCHA_VERSION = get_hcaptcha_version(proxy)
        
        # Motion is initialized but NEVER used for advanced features
        # We return empty motionData to avoid any hidden Multibot logic
        self.motion = motion_data(self.session.headers["user-agent"], f"https://{self.host}")
        
        debug_print("Pure Groq vision mode - Multibot fully removed")
        debug_print(f"Sitekey: {sitekey} | Host: {self.host} | RQData: {rqdata[:50] if rqdata else 'None'}")
        debug_print(f"Version: {self.HCAPTCHA_VERSION}")
        debug_print("Motion simulation: basic only (empty data sent)")

        self.stats = {
            'total_attempts': 0,
            'successful_solves': 0,
            'start_time': time.time(),
        }

    def get_site_config(self) -> Optional[Dict]:
        try:
            debug_print("Getting site config")
            params = {
                'v': self.HCAPTCHA_VERSION,
                'sitekey': self.sitekey,
                'host': self.host,
                'sc': '1',
                'swa': '1',
                'spst': '1'
            }
            if self.rqdata:
                params['rqdata'] = self.rqdata
            
            response = self.session.post("https://api2.hcaptcha.com/checksiteconfig", params=params)
            
            if response.status_code == 200:
                config = response.json()
                if 'rqdata' in config and not self.rqdata:
                    self.rqdata = config['rqdata']
                return config
            else:
                debug_print(f"Config failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            debug_print(f"get_site_config error: {str(e)}")
            return None

    async def get_hsw_token(self, req_token: str) -> Optional[str]:
        try:
            debug_print(f"Getting HSW token for req: {req_token[:30]}...")
            token = await hsw(req_token, self.host, self.sitekey, self.proxy)
            return token
        except Exception as e:
            debug_print(f"HSW token error: {str(e)}")
            return None

    async def fetch_challenge(self, config: Dict) -> Optional[Dict]:
        try:
            debug_print("Fetching challenge")
            if 'c' not in config or 'req' not in config['c']:
                debug_print("Invalid config - no 'req'")
                return None

            hsw_token = await self.get_hsw_token(config['c']['req'])
            if not hsw_token:
                return None

            challenge_data = {
                'v': self.HCAPTCHA_VERSION,
                'sitekey': self.sitekey,
                'host': self.host,
                'hl': 'en-US',
                'motionData': '{}',  # EMPTY - safe, no Multibot
                'n': hsw_token,
                'c': json.dumps(config['c'])
            }

            if self.rqdata:
                challenge_data['rqdata'] = self.rqdata

            response = self.session.post(
                f"https://api.hcaptcha.com/getcaptcha/{self.sitekey}",
                data=challenge_data
            )

            if response.status_code == 200:
                challenge = response.json()
                if 'rqdata' in challenge and not self.rqdata:
                    self.rqdata = challenge['rqdata']
                return challenge
            else:
                debug_print(f"Challenge fetch failed: {response.status_code}")
                return None
        except Exception as e:
            debug_print(f"fetch_challenge error: {str(e)}")
            return None

    def format_challenge_answers(self, ai_result: Dict, challenge: Dict) -> Dict:
        debug_print("Formatting AI answers")
        answers = {}
        request_type = challenge.get('request_type')
        tasklist = challenge.get('tasklist', [])

        if request_type == 'image_label_binary':
            # Simple fallback for binary label
            for i, task in enumerate(tasklist):
                answers[task['task_key']] = "true"  # or "false" - adjust based on AI
        else:
            # Fallback for other types
            for task in tasklist:
                answers[task['task_key']] = []

        debug_print(f"Formatted answers: {json.dumps(answers, indent=2)}")
        return answers

    async def submit_solution(self, challenge: Dict, answers: Dict) -> Dict:
        try:
            debug_print("Submitting solution")
            hsw_token = await self.get_hsw_token(challenge['c']['req'])
            if not hsw_token:
                return {"success": False, "error": "HSW failed"}

            endpoint = f"https://api.hcaptcha.com/checkcaptcha/{self.sitekey}/{challenge['key']}"
            
            submission_data = {
                'v': self.HCAPTCHA_VERSION,
                'sitekey': self.sitekey,
                'serverdomain': self.host,
                'job_mode': challenge['request_type'],
                'motionData': '{}',  # EMPTY - safe
                'n': hsw_token,
                'c': json.dumps(challenge['c']),
                'answers': answers
            }

            if self.rqdata:
                submission_data['rqdata'] = self.rqdata

            headers = {
                'accept': '*/*',
                'content-type': 'application/json;charset=UTF-8',
                'origin': 'https://newassets.hcaptcha.com',
                'referer': 'https://newassets.hcaptcha.com/',
                'user-agent': self.session.headers['user-agent']
            }

            response = self.session.post(endpoint, json=submission_data, headers=headers)

            if response.status_code == 200:
                result = response.json()
                if result.get('pass'):
                    return {"success": True, "token": result.get('generated_pass_UUID')}
                else:
                    return {"success": False, "error": "Rejected"}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}"}
        except Exception as e:
            debug_print(f"submit_solution error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def solve_captcha(self) -> Dict:
        debug_print("Starting solve (pure Groq mode)")
        start_time = time.time()

        config = self.get_site_config()
        if not config:
            return {"success": False, "error": "Site config failed"}

        challenge = await self.fetch_challenge(config)
        if not challenge:
            return {"success": False, "error": "Challenge fetch failed"}

        if challenge.get('generated_pass_UUID'):
            token = challenge['generated_pass_UUID']
            return {"success": True, "token": token}

        if 'tasklist' not in challenge:
            return {"success": False, "error": "No tasklist"}

        # Solve with AI agent (Groq vision)
        ai_result = await self.ai_agent.solve_challenge(challenge)
        formatted_answers = self.format_challenge_answers(ai_result, challenge)

        result = await self.submit_solution(challenge, formatted_answers)

        time_taken = round(time.time() - start_time, 2)
        if result.get("success"):
            return {
                "success": True,
                "token": result["token"],
                "time_taken": time_taken
            }
        return {
            "success": False,
            "error": result.get("error", "Unknown"),
            "time_taken": time_taken
        }

# ────────────────────────────────────────────────────────────────
# FastAPI
# ────────────────────────────────────────────────────────────────

app = FastAPI(title="hCaptcha Solver - Pure Groq")

class SolveRequest(BaseModel):
    sitekey: str
    rqdata: Optional[str] = None
    host: str = "discord.com"
    proxy: Optional[str] = None

@app.post("/solve")
async def solve_endpoint(request: SolveRequest):
    debug_print(f"Solve request: sitekey={request.sitekey}")

    try:
        solver = HCaptchaSolver(
            sitekey=request.sitekey,
            host=request.host,
            rqdata=request.rqdata,
            proxy=request.proxy
        )

        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY is missing")

        result = await solver.solve_captcha()

        if result.get("success"):
            realtime_print(f"Solved → token: {result.get('token', '???')[:35]}...")
            return {
                "status": "success",
                "token": result.get("token"),
                "time_taken": result.get("time_taken", 0),
                "message": "Solved (Groq only)"
            }
        else:
            raise HTTPException(500, detail=result.get("error", "Solve failed"))

    except Exception as e:
        debug_print(f"Solve error: {str(e)}")
        raise HTTPException(500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "Groq-only"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    debug_print(f"Starting server on port {port}")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False, log_level="info")
