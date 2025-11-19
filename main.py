import tls_client, re, asyncio, json, os, random
from camoufox.async_api import AsyncCamoufox
from motion import COMMON_SCREEN_SIZES
import jwt

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

async def hsw(req: str, site: str, sitekey: str, proxy: str = None) -> str:
    try:
        session = tls_client.Session(client_identifier="chrome_130", random_tls_extension_order=True)
        
        if proxy:
            if '@' in proxy:
                proxy_url = f"http://{proxy}"
            else:
                proxy_url = f"http://{proxy}"
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
            
            await page.route(f"https://{site}/", lambda r: r.fulfill(
                status=200, 
                content_type="text/html",
                body="<html><head></head><body></body></html>"
            ))
            
            await page.goto(f"https://{site}/", wait_until='domcontentloaded', timeout=5000)

            js = session.get('https://js.hcaptcha.com/1/api.js').text
            version = re.findall(r'v1\/([A-Za-z0-9]+)\/static', js)[1]

            token = session.post('https://api2.hcaptcha.com/checksiteconfig', params={
                'v': version,
                'host': site,
                'sitekey': sitekey,
                'sc': '1',
                'swa': '1',
                'spst': 's',
            }).json()["c"]["req"]

            decoded_token = jwt.decode(token, options={"verify_signature": False})
            url = "https://newassets.hcaptcha.com" + decoded_token["l"] + "/hsw.js"
            hsw_js = session.get(url).text

            await page.evaluate("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
            
            try:
                await page.add_script_tag(content=hsw_js)
            except Exception:
                await page.evaluate(f"""
                    (function() {{
                        const script = document.createElement('script');
                        script.textContent = {json.dumps(hsw_js)};
                        (document.head || document.documentElement).appendChild(script);
                    }})();
                """)
            
            try:
                has_hsw = await page.evaluate("typeof hsw === 'function'")
                if has_hsw:
                    pass
                else:
                    max_wait_attempts = 50
                    for attempt in range(max_wait_attempts):
                        try:
                            has_hsw = await page.evaluate("typeof hsw === 'function'")
                            if has_hsw:
                                break
                        except Exception:
                            pass
                        if attempt < 5:
                            await asyncio.sleep(0.01)
                        else:
                            await asyncio.sleep(0.02)
                    else:
                        has_hsw = False
            except Exception:
                has_hsw = False
            
            if not has_hsw:
                try:
                    await page.evaluate(hsw_js)
                    await asyncio.sleep(0.05)
                    has_hsw_retry = await page.evaluate("typeof hsw === 'function'")
                    if not has_hsw_retry:
                        raise Exception("hsw function not available after all injection attempts")
                except Exception as e:
                    raise Exception(f"hsw function not available: {e}")
            
            result = await page.evaluate("(req) => hsw(req)", req)
            
            return result
        
    except Exception as e:
        print(f"HSW generation error: {e}")
        return None