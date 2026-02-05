# api.py - Groq-only version - Multibot completely purged

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

# Your original modules (keep only what's needed)
from main import hsw
from motion import motion_data  # we'll use basic version only
from agent import AIAgent

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
# Session & version (unchanged)
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
# HCaptchaSolver - NO MULTIBOT AT ALL
# ────────────────────────────────────────────────────────────────

class HCaptchaSolver:
    def __init__(self, sitekey: str, host: str, rqdata: str = None, proxy: str = None):
        self.sitekey = sitekey
        self.host = host.split("//")[-1].split("/")[0]
        self.rqdata = rqdata
        self.proxy = proxy
        self.session = create_session(proxy)
        self.ai_agent = AIAgent()
        self.real_time_mode = False  # permanently disabled
        self.HCAPTCHA_VERSION = get_hcaptcha_version(proxy)
        
        debug_print("Running in pure Groq vision mode (Multibot fully removed)")
        debug_print(f"Sitekey: {sitekey} | Host: {self.host} | RQData: {rqdata[:50] if rqdata else 'None'}")
        debug_print(f"Version: {self.HCAPTCHA_VERSION}")

        # Use basic motion only - no Multibot calls
        self.motion = motion_data(self.session.headers["user-agent"], f"https://{self.host}")

        self.stats = {
            'total_attempts': 0,
            'successful_solves': 0,
            'start_time': time.time(),
        }

    # ────────────────────────────────────────────────────────────────
    # PASTE YOUR ORIGINAL METHODS HERE (get_site_config, get_hsw_token, etc.)
    # Make sure to REMOVE any line that mentions "multibot", "motion.check_captcha()", etc.
    # Replace advanced motion calls with basic ones if needed.
    # For example, in submit_solution:
    #   'motionData': json.dumps(self.motion.get_captcha())   ← keep this, it's basic
    # ────────────────────────────────────────────────────────────────

    # Example placeholder for solve_captcha (replace with your real one)
    async def solve_captcha(self) -> Dict:
        debug_print("Starting solve (Groq-only mode)")
        # ... your full solve logic here ...
        # At the end return {"success": True, "token": "..."} or {"success": False, "error": "..."}
        # Make sure no Multibot is called anywhere
        return {"success": False, "error": "solve_captcha not implemented yet"}

# ────────────────────────────────────────────────────────────────
# FastAPI
# ────────────────────────────────────────────────────────────────

app = FastAPI(title="hCaptcha Solver - Groq Only")

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
            raise ValueError("GROQ_API_KEY is missing - required for vision solving")

        result = await solver.solve_captcha()

        if result.get("success"):
            realtime_print(f"Solved → token: {result.get('token', '???')[:35]}...")
            return {
                "status": "success",
                "token": result.get("token"),
                "time_taken": result.get("time_taken", 0),
                "message": "Solved (Groq vision only)"
            }
        else:
            raise HTTPException(500, detail=result.get("error", "Solve failed"))

    except Exception as e:
        debug_print(f"Error: {str(e)}")
        raise HTTPException(500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "Groq-only"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    debug_print(f"Starting server on port {port}")
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False, log_level="info")
