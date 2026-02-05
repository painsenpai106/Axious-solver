import random
import time
from typing import Dict, List, Tuple

# Dummy / fallback utilities (no Multibot)
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

class motion_data:
    """
    Dummy motion data generator - NO Multibot, just random paths
    """
    def __init__(self, user_agent: str, url: str, screen_size: Tuple = None):
        self.user_agent = user_agent
        self.url = url
        
        # Simple random screen size if not provided
        if screen_size is None:
            COMMON_SCREEN_SIZES = [(1920, 1080), (1366, 768), (1440, 900), (1280, 720)]
            screen_size = random.choice(COMMON_SCREEN_SIZES)
        self.screen_size = screen_size
        
        # Generate fake mouse path (random points + timestamps)
        self.data = self._generate_dummy_data()

    def _generate_dummy_data(self) -> Dict:
        """Generate basic random mouse movement data"""
        width, height = self.screen_size
        start_x, start_y = random.randint(0, width//4), random.randint(0, height//4)
        end_x, end_y = random.randint(width//2, width), random.randint(height//2, height)
        
        points = []
        current_time = util.get_ms()
        for i in range(10):  # 10 random points
            x = util.randint(start_x, end_x)
            y = util.randint(start_y, end_y)
            t = current_time + i * random.randint(20, 80)  # ~20-80ms intervals
            points.append([x, y, t])
        
        return {
            'mm': points,  # mouse move
            'mm-mp': util.periods([p[2] for p in points]),
            'md': [[points[-1][0], points[-1][1], util.get_ms()]],  # mouse down
            'mu': [[points[-1][0], points[-1][1], util.get_ms() + 50]],  # mouse up
            'topLevel': {
                'sc': {
                    'width': width,
                    'height': height,
                }
            },
            'v': 1,
            'session': [],
            'href': self.url,
        }

    def get_captcha(self) -> Dict:
        return self.data

    def check_captcha(self) -> Dict:
        return self.data
