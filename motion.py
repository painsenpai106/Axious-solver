import requests
import json
import time
import random
import string
from typing import Dict, List, Tuple
from datetime import datetime
from colorama import Fore, Style

class util:
    @staticmethod
    def randint(a: int, b: int) -> int:
        return random.randint(min(a, b), max(a, b))

    @staticmethod
    def get_ms() -> int:
        return int(time.time() * 1000)

    @staticmethod
    def get_random_point(bbox: Tuple) -> Tuple:
        x1, y1 = int(bbox[0][0]), int(bbox[0][1])
        x2, y2 = int(bbox[1][0]), int(bbox[1][1])
        return util.randint(x1, x2), util.randint(y1, y2)

    @staticmethod
    def periods(timestamps: List) -> float:
        periods = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        return sum(periods) / len(periods) if periods else 0

class rectangle:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def get_dimensions(self) -> Tuple:
        return self.width, self.height

    def get_box(self, rel_x: int, rel_y: int) -> Tuple:
        rel_x = int(rel_x)
        rel_y = int(rel_y)
        return (rel_x, rel_y), (rel_x + self.width, rel_y + self.height)

    def get_corners(self, rel_x: int = 0, rel_y: int = 0) -> List:
        rel_x = int(rel_x)
        rel_y = int(rel_y)
        return [(rel_x, rel_y), (rel_x + self.width, rel_y), (rel_x, rel_y + self.height), (rel_x + self.width, rel_y + self.height)]

class widget_check:
    def __init__(self, rel_position: Tuple) -> None:
        self.widget = rectangle(300, 75)
        self.check_box = rectangle(28, 28)
        self.rel_position = rel_position

    def get_check(self) -> Tuple:
        return self.check_box.get_box(16 + self.rel_position[0], 23 + self.rel_position[1])

    def get_closest(self, position: Tuple) -> Tuple:
        corners = self.widget.get_corners(self.rel_position[0], self.rel_position[1])
        import math
        sorted_corners = sorted(corners, key=lambda c: math.sqrt((c[0] - position[0])**2 + (c[1] - position[1])**2))
        return sorted_corners[0], sorted_corners[1]

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

COMMON_CORE_COUNTS = [4, 8, 6, 12, 2, 16]
COMMON_COLOR_DEPTHS = [24, 30]
COMMON_LANGUAGES = [
    ('en-US', ['en-US', 'en']),
    ('en-GB', ['en-GB', 'en']),
    ('en', ['en']),
    ('es-ES', ['es-ES', 'es']),
    ('fr-FR', ['fr-FR', 'fr']),
    ('de-DE', ['de-DE', 'de']),
    ('ja-JP', ['ja-JP', 'ja']),
    ('zh-CN', ['zh-CN', 'zh']),
]

class MultibotMotionGenerator:
    
    def __init__(self):
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
            self.api_key = config.get('MULTIBOT_API_KEY', '')
            self.enabled = bool(self.api_key and self.api_key != 'YOUR_MULTIBOT_API_KEY')
            self.debug = config.get('debug', False)
        except Exception:
            self.api_key = ''
            self.enabled = False
            self.debug = False
        
        if not self.enabled:
            raise Exception("MULTIBOT_API_KEY not configured. Mouse movement requires multibot.in API.")
    
    def _debug_print(self, message: str):
        if self.debug:
            timestamp = datetime.now().strftime("%H:%M:%S")
            timestamp_colored = f"{Fore.WHITE}{timestamp}{Style.RESET_ALL}"
            separator = f"{Fore.WHITE}│{Style.RESET_ALL}"
            name_colored = f"{Fore.YELLOW}{'MOTION':<6}{Style.RESET_ALL}"
            message_colored = f"{Fore.WHITE}{message}{Style.RESET_ALL}"
            print(f"{timestamp_colored} {separator} {name_colored} {separator} {message_colored}")
    
    def generate_movement(self, start: Tuple[int, int], end: Tuple[int, int]) -> List[List[int]]:
        
        try:
            self._debug_print(f"Generating movement: {start} -> {end}")
            
            task_data = {
                "clientKey": self.api_key,
                "type": "humanMove",
                "task": [
                    {
                        "type": "move",
                        "patch": [list(start), list(end)]
                    }
                ]
            }
            
            create_response = requests.post(
                'http://api.multibot.in/createTask',
                headers={'content-type': 'application/json'},
                json=task_data,
                timeout=10
            )
            
            if create_response.status_code != 200:
                raise Exception(f"Multibot create task failed with status: {create_response.status_code}")
            
            result = create_response.json()
            
            if result.get('errorId') != 0:
                raise Exception(f"Multibot task creation error: {result}")
            
            task_id = result.get('taskId')
            if not task_id:
                raise Exception("No taskId returned from multibot")
            
            max_attempts = 20
            for attempt in range(max_attempts):
                time.sleep(0.5)
                
                result_response = requests.post(
                    'http://api.multibot.in/getTaskResult',
                    headers={'content-type': 'application/json'},
                    json={
                        "clientKey": self.api_key,
                        "taskId": task_id
                    },
                    timeout=10
                )
                
                if result_response.status_code != 200:
                    continue
                
                result = result_response.json()
                
                if result.get('errorId') != 0:
                    raise Exception(f"Multibot task error: {result}")
                
                status = result.get('status')
                
                if status == 'ready':
                    answers = result.get('answers', [])
                    if answers and len(answers) > 0:
                        path = answers[0].get('path', [])
                        if path and len(path) > 0:
                            self._debug_print(f"Got movement path with {len(path)} points")
                            return path
                    raise Exception("No valid path returned from multibot")
                
                elif status == 'error':
                    raise Exception("Multibot task failed with error status")
                
                elif status == 'processing':
                    self._debug_print(f"Task processing... (attempt {attempt + 1}/{max_attempts})")
                    continue
            
            raise Exception("Multibot task timed out after polling")
            
        except Exception as e:
            self._debug_print(f"CRITICAL ERROR in generate_movement: {e}")
            raise

class get_cap:
    
    def __init__(self, user_agent: str, href: str, screen_size: Tuple = None) -> None:
        self.user_agent = user_agent
        if screen_size is None:
            screen_size = random.choice(COMMON_SCREEN_SIZES)
        self.screen_size = screen_size
        self.color_depth = random.choice(COMMON_COLOR_DEPTHS)
        self.hardware_concurrency = random.choice(COMMON_CORE_COUNTS)
        self.language, self.languages = random.choice(COMMON_LANGUAGES)
        
        widget_id = '0' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        random_point = util.get_random_point(((0, 0), (screen_size[0] - 150, screen_size[1] - 38)))
        self.widget = widget_check(random_point)
        self.position = util.get_random_point(((0, 0), screen_size))
        
        self.motion_gen = MultibotMotionGenerator()
        
        self.data = {
            'st': util.get_ms(),
            'mm': [],
            'mm-mp': 0,
            'md': [],
            'md-mp': 0,
            'mu': [],
            'mu-mp': 0,
            'v': 1,
            'topLevel': self.top_level(),
            'session': [],
            'widgetList': [widget_id],
            'widgetId': widget_id,
            'href': href,
            'prev': {
                'escaped': False,
                'passed': False,
                'expiredChallenge': False,
                'expiredResponse': False
            }
        }

        goal = util.get_random_point(self.widget.get_check())
        
        self.mouse_movement = self.motion_gen.generate_movement(self.position, goal)
        
        self.data['mm'] = [[x - random_point[0], y - random_point[1], t] for x, y, t in self.mouse_movement]
        self.data['mm-mp'] = util.periods([x[-1] for x in self.mouse_movement])
        self.data['md'].append(self.data['mm'][-1][:-1] + [util.get_ms()])
        time.sleep(1 / util.randint(3, 7))
        self.data['mu'].append(self.data['mm'][-1][:-1] + [util.get_ms()])

    def top_level(self) -> dict:
        taskbar_height = random.choice([0, 30, 40, 48])
        avail_height = max(1, self.screen_size[1] - taskbar_height)
        
        data = {
            'inv': False,
            'st': util.get_ms(),
            'sc': {
                'availWidth': self.screen_size[0],
                'availHeight': avail_height,
                'width': self.screen_size[0],
                'height': self.screen_size[1],
                'colorDepth': self.color_depth,
                'pixelDepth': self.color_depth,
                'top': 0,
                'left': 0,
                'availTop': 0,
                'availLeft': 0,
                'mozOrientation': 'landscape-primary',
                'onmozorientationchange': None
            },
            'nv': {
                'permissions': {},
                'pdfViewerEnabled': True,
                'doNotTrack': random.choice(['unspecified', None, '1', '0']),
                'maxTouchPoints': 0,
                'mediaCapabilities': {},
                'vendor': 'Google Inc.',
                'vendorSub': '',
                'cookieEnabled': True,
                'mediaDevices': {},
                'serviceWorker': {},
                'credentials': {},
                'clipboard': {},
                'mediaSession': {},
                'webdriver': False,
                'hardwareConcurrency': self.hardware_concurrency,
                'geolocation': {},
                'userAgent': self.user_agent,
                'language': self.language,
                'languages': self.languages,
                'locks': {},
                'onLine': True,
                'storage': {},
                'plugins': ['internal-pdf-viewer'] if random.random() > 0.3 else []
            },
            'dr': '',
            'exec': False,
            'wn': [[self.screen_size[0], self.screen_size[1], 1, util.get_ms()]],
            'wn-mp': 0,
            'xy': [[0, 0, 1, util.get_ms()]],
            'xy-mp': 0,
            'mm': [],
            'mm-mp': 0
        }

        position = tuple(int(val) for val in self.position)
        goal = util.get_random_point(self.widget.get_closest(position))
        
        mouse_movement = self.motion_gen.generate_movement(position, goal)
        
        self.position = tuple(int(val) for val in goal)
        data['mm'] = mouse_movement
        data['mm-mp'] = util.periods([x[-1] for x in mouse_movement])

        return data

class motion_data:
    
    def __init__(self, user_agent: str, url: str, screen_size: Tuple = None) -> None:
        self.user_agent = user_agent
        self.url = url
        self.get_captcha_motion_data = get_cap(self.user_agent, self.url, screen_size)

    def get_captcha(self) -> dict:
        return self.get_captcha_motion_data.data

    def check_captcha(self) -> dict:
        return self.get_captcha_motion_data.data
