import random
import time
from typing import Dict, List, Tuple

# Simple dummy utilities (no Multibot needed)
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
        if len(timestamps) < 2:
            return 0.0
        periods = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        return sum(periods) / len(periods)

# No longer used — kept for compatibility if needed elsewhere
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

class motion_data:
    """
    Simple random motion data generator - NO Multibot, NO external API calls
    Generates fake mouse movement that should be acceptable for hCaptcha
    """
    def __init__(self, user_agent: str, url: str, screen_size: Tuple = None):
        self.user_agent = user_agent
        self.url = url
        
        # Choose screen size
        if screen_size is None:
            screen_size = random.choice(COMMON_SCREEN_SIZES)
        self.screen_size = screen_size
        
        # Generate basic fake motion data
        self.data = self._generate_dummy_motion()

    def _generate_dummy_motion(self) -> Dict:
        """Generate random mouse path + timestamps + basic events"""
        width, height = self.screen_size
        
        # Start position (somewhere left/top)
        start_x = random.randint(50, width // 3)
        start_y = random.randint(50, height // 3)
        
        # End position (somewhere right/bottom)
        end_x = random.randint(width // 2, width - 50)
        end_y = random.randint(height // 2, height - 50)
        
        # Create 8–15 random points between start and end
        num_points = random.randint(8, 15)
        points = []
        current_time = util.get_ms()
        
        for i in range(num_points):
            progress = i / (num_points - 1)
            x = int(start_x + (end_x - start_x) * progress) + random.randint(-30, 30)
            y = int(start_y + (end_y - start_y) * progress) + random.randint(-30, 30)
            t = current_time + i * random.randint(30, 120)  # 30–120 ms intervals
            points.append([x, y, t])
        
        # Mouse down/up events at the end
        last_point = points[-1]
        md_time = last_point[2] + random.randint(50, 150)
        mu_time = md_time + random.randint(80, 200)
        
        return {
            'mm': points,                     # mouse move points
            'mm-mp': util.periods([p[2] for p in points]),  # average move period
            'md': [[last_point[0], last_point[1], md_time]],  # mouse down
            'mu': [[last_point[0], last_point[1], mu_time]],  # mouse up
            'v': 1,
            'session': [],
            'href': self.url,
            'topLevel': {
                'sc': {
                    'width': width,
                    'height': height,
                }
            }
        }

    def get_captcha(self) -> Dict:
        return self.data

    def check_captcha(self) -> Dict:
        return self.data
