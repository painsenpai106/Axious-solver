import tls_client
import re
import asyncio
import json
import os
import random
from typing import Optional
from camoufox.async_api import AsyncCamoufox
from jwt import decode, PyJWTError   # ← FIXED: correct import from pyjwt

# Hardcoded screen sizes (no more import from motion.py)
COMMON_SCREEN_SIZES = [
    (1920, 1080),
    (1366, 768),
    (1536, 864),
    (1440, 900),
    (1280, 720),
    (1600, 900),
    (2560, 1440),
    (1680, 1050)
]

def load_config():
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"proxies": False}

def load_proxies():
    try:
        with open('proxies.txt', 'r') as f:
            lines = f.readlines()
        return [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        return []

def get_random_proxy():
    config = load_config()
    if not config.get("proxies", False):
        return None
    
    proxies = load_proxies()
    if not proxies:
        return None
    
    proxy_string = random.choice(proxies)
    if '@' in proxy_string:
        auth_part, server_part = proxy_string.split('@', 1)
        username, password = auth_part.split(':', 1)
        ip, port = server_part.split(':', 1)
        
        proxy_url = f"http://{username}:{password}@{ip}:{port}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    return None

async def hsw(req: str, site: str, sitekey: str, proxy: Optional[str] = None) -> Optional[str]:
    """
    Generates hCaptcha HSW token using Camoufox browser emulation.
    Fully compatible with current setup - no Multibot dependency.
    """
    try:
        session = tls_client.Session(client_identifier="chrome_130", random_tls_extension_order=True)
        
        if proxy:
            proxy_url = f'http://{proxy}'
            session.proxies = {
                'http': proxy_url,
                'https': proxy_url
            }
        
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        
        session.headers = {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'cache-control': 'no-cache',
            'pragma': 'no-cache',
            'referer': 'https://discord.com/',
            'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'script',
            'sec-fetch-mode': 'no-cors',
            'sec-fetch-site': 'cross-site',
            'user-agent': user_agent,
        }
        
        browser_options = {
            'headless': True,
            'os': 'windows',
            'locale': ['en-US', 'en']
        }
        
        if proxy:
            browser_options['geoip'] = True
            if '@' in proxy:
                auth_part, server_part = proxy.split('@', 1)
                username, password = auth_part.split(':', 1)
                ip, port = server_part.split(':', 1)
                
                browser_options['proxy'] = {
                    'server': f'http://{ip}:{port}',
                    'username': username,
                    'password': password
                }
            else:
                browser_options['proxy'] = {
                    'server': f'http://{proxy}'
                }
        
        async with AsyncCamoufox(**browser_options) as browser:
            screen_size = random.choice(COMMON_SCREEN_SIZES)
            context = await browser.new_context(
                viewport={'width': screen_size[0], 'height': screen_size[1]},
                user_agent=user_agent
            )
            page = await context.new_page()
            
            # Block unnecessary requests to speed up
            await page.route(f"https://{site}/", lambda r: r.fulfill(
                status=200, 
                content_type="text/html",
                body="<html><head></head><body></body></html>"
            ))
            
            await page.goto(f"https://{site}/", wait_until='domcontentloaded', timeout=5000)

            # Fetch hCaptcha API JS and extract version
            js = session.get('https://js.hcaptcha.com/1/api.js').text
            version_match = re.search(r'v1/([A-Za-z0-9]+)/static', js)
            version = version_match.group(1) if version_match else None

            if not version:
                raise Exception("Could not extract hCaptcha version")

            # Get checksiteconfig to retrieve req token
            token_response = session.post('https://api2.hcaptcha.com/checksiteconfig', params={
                'v': version,
                'host': site,
                'sitekey': sitekey,
                'sc': '1',
                'swa': '1',
                'spst': 's',
            })
            
            token_data = token_response.json()
            token = token_data.get("c", {}).get("req")
            
            if not token:
                raise Exception("No req token received from checksiteconfig")

            # Decode token to get hsw.js location
            try:
                decoded_token = decode(token, options={"verify_signature": False})
                if "l" not in decoded_token:
                    raise Exception("JWT token missing 'l' field")
            except PyJWTError as jwt_err:
                raise Exception(f"JWT decode failed: {str(jwt_err)}")
            except Exception as e:
                raise Exception(f"Unexpected error during JWT decode: {str(e)}")

            hsw_url = "https://newassets.hcaptcha.com" + decoded_token["l"] + "/hsw.js"
            hsw_js = session.get(hsw_url).text

            # Spoof webdriver
            await page.evaluate("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
            
            # Inject hsw.js
            try:
                await page.add_script_tag(content=hsw_js)
            except Exception as inject_err:
                print(f"Script tag injection failed: {str(inject_err)}")
                # Fallback injection method
                await page.evaluate(f"""
                    (function() {{
                        const script = document.createElement('script');
                        script.textContent = {json.dumps(hsw_js)};
                        (document.head || document.documentElement).appendChild(script);
                    }})();
                """)
            
            # Wait for hsw function to be available
            max_attempts = 50
            for attempt in range(max_attempts):
                has_hsw = await page.evaluate("typeof hsw === 'function'")
                if has_hsw:
                    break
                await asyncio.sleep(0.02)
            else:
                raise Exception(f"hsw function not available after {max_attempts} attempts")

            # Execute hsw
            result = await page.evaluate("(req) => hsw(req)", req)
            
            print(f"HSW generation successful - result length: {len(result) if result else 0}")
            return result
        
    except Exception as e:
        print(f"HSW generation error: {str(e)}")
        import traceback
        traceback.print_exc()  # better debugging in Railway logs
        return None
