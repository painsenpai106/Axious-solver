import tls_client, re, json, asyncio, time, os
from typing import Dict, Any, Optional, List
from colorama import Fore, Style, Back, init
from datetime import datetime
from main import hsw
from motion import motion_data
from agent import AIAgent

init(autoreset=True)
DEBUG_MODE = False
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
        DEBUG_MODE = config.get('debug', False)
except:
    DEBUG_MODE = False

def debug_print(message: str):
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        timestamp_colored = f"{Fore.WHITE}{timestamp}{Style.RESET_ALL}"
        separator = f"{Fore.WHITE}│{Style.RESET_ALL}"
        name_colored = f"{Fore.CYAN}{'SOLVER':<6}{Style.RESET_ALL}"
        message_colored = f"{Fore.WHITE}{message}{Style.RESET_ALL}"
        print(f"{timestamp_colored} {separator} {name_colored} {separator} {message_colored}")

def realtime_print(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    timestamp_colored = f"{Fore.WHITE}{timestamp}{Style.RESET_ALL}"
    separator = f"{Fore.WHITE}│{Style.RESET_ALL}"
    name_colored = f"{Fore.CYAN}{'SOLVER':<6}{Style.RESET_ALL}"
    message_colored = f"{Fore.WHITE}{Style.BRIGHT}{message}{Style.RESET_ALL}"
    print(f"{timestamp_colored} {separator} {name_colored} {separator} {message_colored}")

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
        if '@' in proxy:
            proxy_url = f'http://{proxy}'
        else:
            proxy_url = f'http://{proxy}'
            
        session.proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
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
            
            debug_print(f"Request URL: https://api2.hcaptcha.com/checksiteconfig")
            debug_print(f"Request Params: {json.dumps(params, indent=2)}")
            
            response = self.session.post(
                "https://api2.hcaptcha.com/checksiteconfig",
                params=params
            )
            
            debug_print(f"Response Status: {response.status_code}")
            debug_print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                try:
                    config = response.json()
                    debug_print(f"Response JSON: {json.dumps(config, indent=2)}")
                    
                    if 'rqdata' in config and not self.rqdata:
                        self.rqdata = config['rqdata']
                        debug_print(f"Updated rqdata from config: {self.rqdata[:50]}...")
                    
                    if 'c' in config:
                        debug_print(f"Config 'c' field present: {list(config['c'].keys())}")
                    else:
                        debug_print("WARNING: No 'c' field in config!")
                    
                    return config
                except json.JSONDecodeError as e:
                    debug_print(f"JSON Decode Error: {str(e)}")
                    debug_print(f"Raw Response: {response.text}")
                    return None
            else:
                debug_print(f"Failed with status {response.status_code}")
                debug_print(f"Response Text: {response.text}")
                return None
                
        except Exception as e:
            debug_print(f"EXCEPTION in get_site_config: {str(e)}")
            import traceback
            debug_print(f"Traceback: {traceback.format_exc()}")
            return None

    async def get_hsw_token(self, req_token: str) -> Optional[str]:
        try:
            debug_print(f"Getting HSW token for req: {req_token[:30]}...")
            token = await hsw(req_token, self.host, self.sitekey, self.proxy)
            if token:
                debug_print(f"HSW token obtained: {token[:30]}...")
            else:
                debug_print("HSW token generation failed!")
            return token
        except Exception as e:
            debug_print(f"EXCEPTION in get_hsw_token: {str(e)}")
            return None

    async def fetch_challenge(self, config: Dict) -> Optional[Dict]:
        try:
            debug_print("Fetching challenge")
            
            if 'c' not in config:
                debug_print("ERROR: No 'c' field in config!")
                return None
            
            if 'req' not in config['c']:
                debug_print("ERROR: No 'req' field in config['c']!")
                debug_print(f"Config['c'] contents: {config['c']}")
                return None
            
            hsw_token = await self.get_hsw_token(config['c']['req'])
            if not hsw_token:
                debug_print("Failed to get HSW token, cannot fetch challenge")
                return None
            
            challenge_data = {
                'v': self.HCAPTCHA_VERSION,
                'sitekey': self.sitekey,
                'host': self.host,
                'hl': 'en-US',
                'motionData': json.dumps(self.motion.get_captcha()),
                'n': hsw_token,
                'c': json.dumps(config['c'])
            }
            
            if self.rqdata:
                challenge_data['rqdata'] = self.rqdata
            
            debug_print(f"Challenge Request URL: https://api.hcaptcha.com/getcaptcha/{self.sitekey}")
            debug_print(f"Challenge Data Keys: {list(challenge_data.keys())}")
            
            response = self.session.post(
                f"https://api.hcaptcha.com/getcaptcha/{self.sitekey}",
                data=challenge_data
            )
            
            debug_print(f"Challenge Response Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    challenge = response.json()
                    debug_print(f"Challenge Response JSON (keys): {list(challenge.keys())}")
                    
                    if 'success' in challenge and challenge['success'] == False:
                        debug_print(f"⚠ CHALLENGE MARKED AS UNSUCCESSFUL!")
                        debug_print(f"   Error codes: {challenge.get('error-codes', [])}")
                        debug_print(f"   This usually means hCaptcha rejected the request")
                        return None
                    
                    if 'generated_pass_UUID' in challenge:
                        debug_print(f"PASSIVE PASS RECEIVED: {challenge['generated_pass_UUID'][:30]}...")
                    
                    if 'tasklist' in challenge:
                        debug_print(f"Tasklist length: {len(challenge['tasklist'])}")
                        debug_print(f"Request type: {challenge.get('request_type')}")
                        debug_print(f"Question: {challenge.get('requester_question', {}).get('en', 'N/A')}")
                    else:
                        debug_print(f"WARNING: NO TASKLIST IN CHALLENGE!")
                        debug_print(f"Challenge keys present: {list(challenge.keys())}")
                    
                    if 'rqdata' in challenge and not self.rqdata:
                        self.rqdata = challenge['rqdata']
                        debug_print(f"Updated rqdata from challenge: {self.rqdata[:50]}...")
                    
                    return challenge
                except json.JSONDecodeError as e:
                    debug_print(f"JSON Decode Error: {str(e)}")
                    debug_print(f"Raw Response: {response.text}")
                    return None
            else:
                debug_print(f"Failed with status {response.status_code}")
                debug_print(f"Response Text: {response.text}")
                return None
                
        except Exception as e:
            debug_print(f"EXCEPTION in fetch_challenge: {str(e)}")
            import traceback
            debug_print(f"Traceback: {traceback.format_exc()}")
            return None

    def format_challenge_answers(self, ai_result: Dict, challenge: Dict) -> Dict:
        debug_print("Formatting answers")
        
        request_type = challenge.get('request_type')
        tasklist = challenge.get('tasklist', [])
        ai_answers = ai_result.get('answers', [])
        answers = {}
        
        debug_print(f"Request Type: {request_type}")
        debug_print(f"Tasklist length: {len(tasklist)}")
        debug_print(f"AI Answers: {json.dumps(ai_answers, indent=2)}")
        
        if ai_result.get('multibot_format') and isinstance(ai_answers, dict):
            debug_print("Using multibot format directly (no conversion needed)")
            return ai_answers
        
        if request_type == 'image_label_binary':
            selected_indices = set()
            for answer in ai_answers:
                x, y = answer.get('x', 0), answer.get('y', 0)
                grid_index = y * 3 + x
                if 0 <= grid_index < len(tasklist):
                    selected_indices.add(grid_index)
            
            debug_print(f"Selected indices: {selected_indices}")
            
            for i, task in enumerate(tasklist):
                task_key = task['task_key']
                is_selected = "true" if i in selected_indices else "false"
                answers[task_key] = is_selected
        
        elif request_type == 'image_label_area_select':
            for i, task in enumerate(tasklist):
                task_key = task['task_key']
                if i < len(ai_answers):
                    x = int(ai_answers[i].get('x', 200))
                    y = int(ai_answers[i].get('y', 150))
                else:
                    x, y = 200, 150
                answers[task_key] = [{"entity_name": 0, "entity_type": "default", "entity_coords": [x, y]}]
        
        elif request_type == 'image_drag_drop':
            main_task = tasklist[0] if tasklist else {}
            task_key = main_task.get('task_key')
            entities = main_task.get('entities', [])
            
            for i, answer in enumerate(ai_answers):
                if i < len(entities):
                    entity_id = answer.get('entity_id') or entities[i].get('entity_id')
                    to_x = int(answer.get('to_x', 150))
                    to_y = int(answer.get('to_y', 150))
                    
                    if entity_id:
                        if task_key not in answers:
                            answers[task_key] = []
                        answers[task_key].append({
                            "entity_name": entity_id,
                            "entity_type": "default",
                            "entity_coords": [to_x, to_y]
                        })
        
        debug_print(f"Formatted Answers: {json.dumps(answers, indent=2)}")
        return answers

    async def submit_solution(self, challenge: Dict, answers: Dict) -> Dict:
        try:
            debug_print("Submitting solution")
            
            hsw_token = await self.get_hsw_token(challenge['c']['req'])
            if not hsw_token:
                debug_print("Failed to get HSW token for submission")
                return {"success": False, "error": "HSW token failed", "retry": True}
            
            endpoint = f"https://api.hcaptcha.com/checkcaptcha/{self.sitekey}/{challenge['key']}"
            
            submission_data = {
                'v': self.HCAPTCHA_VERSION,
                'sitekey': self.sitekey,
                'serverdomain': self.host,
                'job_mode': challenge['request_type'],
                'motionData': json.dumps(self.motion.check_captcha()),
                'n': hsw_token,
                'c': json.dumps(challenge['c']),
                'answers': answers
            }
            
            if self.rqdata:
                submission_data['rqdata'] = self.rqdata
            
            headers = {
                'accept': '*/*',
                'accept-encoding': 'gzip, deflate, br, zstd',
                'accept-language': 'en-US,en;q=0.9',
                'content-type': 'application/json;charset=UTF-8',
                'origin': 'https://newassets.hcaptcha.com',
                'referer': 'https://newassets.hcaptcha.com/',
                'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-fetch-dest': 'empty',
                'sec-fetch-mode': 'cors',
                'sec-fetch-site': 'same-site',
                'user-agent': self.session.headers['user-agent']
            }
            
            debug_print(f"Submission URL: {endpoint}")
            
            payload_str = json.dumps(submission_data)
            response = self.session.post(endpoint, data=payload_str, headers=headers)
            
            debug_print(f"Submission Response Status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    debug_print(f"Submission Response JSON: {json.dumps(result, indent=2)}")
                    
                    if result.get('pass') is True:
                        token = result.get('generated_pass_UUID')
                        debug_print(f"SOLUTION ACCEPTED! Token: {token[:30]}...")
                        return {"success": True, "token": token, "message": "Challenge solved!"}
                    else:
                        debug_print(f"Solution rejected: {result}")
                        return {"success": False, "error": f"Rejected", "retry": True}
                except json.JSONDecodeError as e:
                    debug_print(f"JSON Decode Error: {str(e)}")
                    debug_print(f"Raw Response: {response.text}")
                    return {"success": False, "error": f"Invalid response", "retry": True}
            else:
                debug_print(f"Failed with status {response.status_code}")
                debug_print(f"Response Text: {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}", "retry": True}
                
        except Exception as e:
            debug_print(f"EXCEPTION in submit_solution: {str(e)}")
            import traceback
            debug_print(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "error": str(e), "retry": True}

    async def solve_captcha(self) -> Dict:
        debug_print("Starting captcha solve")
        
        config = self.get_site_config()
        if not config or 'c' not in config:
            debug_print("Site configuration failed - aborting")
            return {"success": False, "error": "Site configuration failed"}
        
        max_attempts = 15
        challenges_solved = 0
        start_time = time.time()
        
        for attempt in range(1, max_attempts + 1):
            try:
                debug_print(f"Attempt #{attempt}/{max_attempts}")
                
                self.stats['total_attempts'] += 1
                
                challenge = await self.fetch_challenge(config)
                if not challenge:
                    if self.real_time_mode:
                        realtime_print(f"Failed to fetch challenge [attempt: {attempt}]")
                    else:
                        debug_print(f"Failed to fetch challenge on attempt {attempt}")
                    
                    if attempt >= 3 and self.proxy:
                        debug_print("Multiple failures with proxy - proxy may be blocked by hCaptcha")
                    
                    debug_print("Attempting to refresh site config...")
                    config = self.get_site_config()
                    if not config or 'c' not in config:
                        debug_print("Config refresh failed")
                    continue
                
                if challenge.get('generated_pass_UUID'):
                    self.stats['successful_solves'] += 1
                    self.stats['last_solve_time'] = time.time()
                    elapsed_time = round(time.time() - start_time, 2)
                    token = challenge['generated_pass_UUID']
                    if self.real_time_mode:
                        realtime_print(f"Hcaptcha Solved Successfully [token: {token[:15]}..., Time: {elapsed_time}s]")
                    else:
                        debug_print(f"PASSIVE PASS - Success!")
                    return {
                        "success": True,
                        "token": token,
                        "message": "Passive pass received",
                        "challenges_solved": challenges_solved,
                        "time_taken": elapsed_time
                    }
                
                if 'tasklist' not in challenge:
                    if self.real_time_mode:
                        realtime_print(f"No tasklist in challenge [attempt: {attempt}]")
                    else:
                        debug_print(f"No tasklist in challenge on attempt {attempt}")
                    continue
                
                question = challenge.get('requester_question', {}).get('en', 'Unknown question')
                if self.real_time_mode:
                    realtime_print(f"Question: {question}")
                
                request_type = challenge.get('request_type')
                debug_print(f"Challenge Type: {request_type}")
                
                if request_type in ['image_label_binary', 'image_label_area_select', 'image_drag_drop']:
                    debug_print("Solving with AI agent...")
                    ai_result = await self.ai_agent.solve_challenge(challenge)
                    
                    if not ai_result.get('answers'):
                        debug_print("AI agent returned no answers, using fallback")
                        ai_result = {"answers": [{"x": 200, "y": 150, "to_x": 150, "to_y": 150}]}
                    
                    formatted_answers = self.format_challenge_answers(ai_result, challenge)
                else:
                    debug_print(f"Unsupported request type: {request_type}")
                    continue
                
                if not formatted_answers:
                    if self.real_time_mode:
                        realtime_print(f"No formatted answers [attempt: {attempt}]")
                    else:
                        debug_print(f"No formatted answers on attempt {attempt}")
                    continue
                
                result = await self.submit_solution(challenge, formatted_answers)
                
                if result.get("success"):
                    challenges_solved += 1
                    self.stats['successful_solves'] += 1
                    self.stats['last_solve_time'] = time.time()
                    elapsed_time = round(time.time() - start_time, 2)
                    token = result.get("token", "")
                    if self.real_time_mode:
                        realtime_print(f"Hcaptcha Solved Successfully [token: {token[:15]}..., Time: {elapsed_time}s]")
                    else:
                        debug_print(f"CHALLENGE SOLVED! Total challenges: {challenges_solved}")
                    return {
                        "success": True,
                        "token": token,
                        "message": f"Solved {challenges_solved} challenge(s)",
                        "challenges_solved": challenges_solved,
                        "time_taken": elapsed_time
                    }
                else:
                    if self.real_time_mode:
                        realtime_print(f"Failed to solve [attempt: {attempt}]")
                    else:
                        debug_print(f"Solution rejected on attempt {attempt}: {result.get('error')}")
                    
                    debug_print("Refreshing site config after failed attempt...")
                    config = self.get_site_config()
                    if not config:
                        debug_print("Config refresh failed")
                        return {"success": False, "error": "Config refresh failed"}
                    
            except Exception as e:
                if self.real_time_mode:
                    realtime_print(f"Exception [attempt: {attempt}]: {str(e)}")
                else:
                    debug_print(f"EXCEPTION on attempt {attempt}: {str(e)}")
                    import traceback
                    debug_print(f"Traceback: {traceback.format_exc()}")
                continue
        
        elapsed_time = round(time.time() - start_time, 2)
        debug_print(f"Failed after {max_attempts} attempts")
        return {
            "success": False,
            "error": f"Failed after {max_attempts} attempts",
            "challenges_solved": challenges_solved,
            "time_taken": elapsed_time
        }

async def main():
    os.system('cls' if os.name == 'nt' else 'clear')
    try:
        DISCORD_SITEKEY = "a9b5fb07-92ff-493f-86fe-352a2803b3df"
        DISCORD_HOST = "discord.com"
        
        print(f"{Fore.CYAN}{Style.BRIGHT}Solver for {DISCORD_SITEKEY}{Style.RESET_ALL}")
        print()
        
        solver = HCaptchaSolver(
            DISCORD_SITEKEY,
            DISCORD_HOST,
            real_time_mode=True
        )
        
        result = await solver.solve_captcha()
        
        if not solver.real_time_mode:
            if result.get('success'):
                token = result.get('token', 'N/A')
                time_taken = result.get('time_taken', 0)
                print(f"\n{Fore.GREEN}{Style.BRIGHT}Hcaptcha Solved Successfully [token: {token[:15]}..., Time: {time_taken}s]{Style.RESET_ALL}")
            else:
                time_taken = result.get('time_taken', 0)
                print(f"\n{Fore.RED}{Style.BRIGHT}Failed to solve - {result.get('error', 'Unknown error')}{Style.RESET_ALL}")
            
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Fatal error: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Runtime error: {e}")
