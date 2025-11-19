import json
import base64
import httpx
import re
import requests
import time
import asyncio
from typing import Dict, Any
from datetime import datetime
from colorama import Fore, Style

class AIAgent:
    def __init__(self):
        with open('config.json', 'r') as f:
            config = json.load(f)
        self.api_key = config['GROQ_API_KEY']
        self.multibot_api_key = config.get('MULTIBOT_API_KEY', '')
        self.vision_model = config['models']['vision_model']
        self.fallback_model = config['models']['fallback_model']
        self.debug = config.get('debug', False)
        self.groq_counter = 0
        self.multibot_enabled = bool(self.multibot_api_key and self.multibot_api_key != 'YOUR_MULTIBOT_API_KEY')
        
        if self.debug:
            self._debug_print("Initialized")
            self._debug_print(f"Multibot API: {'Enabled' if self.multibot_enabled else 'Disabled (using Groq only)'}")
    
    def _debug_print(self, message: str):
        if self.debug:
            timestamp = datetime.now().strftime("%H:%M:%S")
            timestamp_colored = f"{Fore.WHITE}{timestamp}{Style.RESET_ALL}"
            separator = f"{Fore.WHITE}│{Style.RESET_ALL}"
            name_colored = f"{Fore.MAGENTA}{'AGENT':<6}{Style.RESET_ALL}"
            message_colored = f"{Fore.WHITE}{message}{Style.RESET_ALL}"
            print(f"{timestamp_colored} {separator} {name_colored} {separator} {message_colored}")
        
    def get_image_base64(self, image_url: str, challenge_name: str = None) -> str:
        try:
            if image_url.startswith('data:image/'):
                parts = image_url.split(',')
                if len(parts) > 1:
                    return parts[1]
            
            response = requests.get(image_url, timeout=10)
            if response.status_code == 200:
                return base64.b64encode(response.content).decode('utf-8')
        except Exception as e:
            self._debug_print(f"Error fetching image: {e}")
        return None
    
    async def solve_with_multibot(self, challenge_data: Dict) -> Dict:
        try:
            self._debug_print("Using Multibot API for solving")
            
            task_data = {
                "clientKey": self.multibot_api_key,
                "type": "hCaptchaRequester",
                "task": {
                    "request_type": challenge_data.get('request_type'),
                    "requester_question": challenge_data.get('requester_question', {}),
                    "requester_question_example": challenge_data.get('requester_question_example', []),
                    "tasklist": challenge_data.get('tasklist', [])
                }
            }
            
            self._debug_print("Creating multibot task...")
            create_response = requests.post(
                'http://api.multibot.in/createTask',
                headers={'content-type': 'application/json'},
                json=task_data,
                timeout=30
            )
            
            if create_response.status_code != 200:
                self._debug_print(f"Multibot createTask failed with status: {create_response.status_code}")
                return None
            
            create_result = create_response.json()
            
            if create_result.get('errorId') != 0:
                self._debug_print(f"Multibot task creation error: {create_result}")
                return None
            
            task_id = create_result.get('taskId')
            if not task_id:
                self._debug_print("No taskId returned from multibot")
                return None
            
            self._debug_print(f"Task created with ID: {task_id}")
            
            max_attempts = 30
            poll_interval = 2
            
            for attempt in range(max_attempts):
                await asyncio.sleep(poll_interval)
                
                self._debug_print(f"Polling for result (attempt {attempt + 1}/{max_attempts})...")
                
                result_response = requests.post(
                    'http://api.multibot.in/getTaskResult',
                    headers={'content-type': 'application/json'},
                    json={
                        "clientKey": self.multibot_api_key,
                        "taskId": task_id
                    },
                    timeout=10
                )
                
                if result_response.status_code != 200:
                    self._debug_print(f"Multibot getTaskResult failed with status: {result_response.status_code}")
                    continue
                
                result = result_response.json()
                
                if result.get('errorId') != 0:
                    self._debug_print(f"Multibot task error: {result}")
                    return None
                
                status = result.get('status')
                
                if status == 'ready':
                    answers = result.get('answers')
                    spent_time = result.get('spentTime', 0)
                    self._debug_print(f"Task completed in {spent_time}s")
                    
                    return {'answers': answers, 'multibot_format': True}
                
                elif status == 'error':
                    self._debug_print("Multibot task failed")
                    return None
                
                elif status == 'processing':
                    self._debug_print("Task still processing...")
                    continue
            
            self._debug_print("Multibot task timed out")
            return None
            
        except Exception as e:
            self._debug_print(f"Exception in solve_with_multibot: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
        return None
        
    async def solve_challenge(self, challenge_data: Dict) -> Dict:
        try:
            request_type = challenge_data.get('request_type')
            question = challenge_data.get('requester_question', {}).get('en', 'Unknown')
            tasklist = challenge_data.get('tasklist', [])
            
            if self.debug:
                self._debug_print("Solving challenge")
                self._debug_print(f"Type: {request_type}")
                self._debug_print(f"Question: {question}")
                self._debug_print(f"Tasklist length: {len(tasklist)}")
            
            if not tasklist:
                return self._get_fallback_answer(request_type)
            
            if self.multibot_enabled:
                multibot_result = await self.solve_with_multibot(challenge_data)
                if multibot_result and multibot_result.get('answers'):
                    self._debug_print("Successfully solved with Multibot API")
                    return multibot_result
                else:
                    self._debug_print("Multibot API failed, falling back to Groq")
            
            return await self._solve_with_groq_vision(challenge_data)
            
        except Exception as e:
            self._debug_print(f"Exception in solve_challenge: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return self._get_fallback_answer(request_type, tasklist[0] if tasklist else None)
    
    async def _solve_with_groq_vision(self, challenge_data: Dict) -> Dict:
        request_type = challenge_data.get('request_type')
        question = challenge_data.get('requester_question', {}).get('en', 'Unknown')
        tasklist = challenge_data.get('tasklist', [])
        
        if request_type == 'image_label_binary':
            all_answers = []
            
            for i, task in enumerate(tasklist):
                image_url = task.get('datapoint_uri')
                
                if not image_url:
                    continue
                
                image_base64 = self.get_image_base64(image_url)
                if not image_base64:
                    continue
                
                single_result = await self._solve_single_image_groq(question, image_base64, i)
                if single_result:
                    all_answers.append({'x': i % 3, 'y': i // 3})
            
            return {'answers': all_answers}
        
        elif request_type == 'image_label_area_select':
            all_answers = []
            
            for i, task in enumerate(tasklist):
                image_url = task.get('datapoint_uri')
                
                if not image_url:
                    all_answers.append({'x': 200, 'y': 150})
                    continue
                
                image_base64 = self.get_image_base64(image_url)
                if not image_base64:
                    all_answers.append({'x': 200, 'y': 150})
                    continue
                
                groq_result = await self._solve_with_groq(question, image_base64, request_type, task)
                if groq_result.get('answers') and len(groq_result['answers']) > 0:
                    all_answers.append(groq_result['answers'][0])
                else:
                    all_answers.append({'x': 200, 'y': 150})
            
            return {'answers': all_answers}
        
        elif request_type == 'image_drag_drop':
            main_task = tasklist[0] if tasklist else {}
            image_url = main_task.get('datapoint_uri')
            entities = main_task.get('entities', [])
            
            if self.debug:
                self._debug_print("Drag-Drop challenge")
                self._debug_print(f"Entities count: {len(entities)}")
                for idx, entity in enumerate(entities):
                    self._debug_print(f"Entity {idx}: {entity.get('entity_id')}")
            
            if not image_url or not entities:
                self._debug_print("Missing image_url or entities, using fallback")
                return self._get_fallback_answer(request_type, main_task)
            
            image_base64 = self.get_image_base64(image_url)
            if not image_base64:
                self._debug_print("Failed to get image base64, using fallback")
                return self._get_fallback_answer(request_type, main_task)
            
            return await self._solve_with_groq(question, image_base64, request_type, main_task)
        
        else:
            main_task = tasklist[0]
            image_url = main_task.get('datapoint_uri')
            
            if not image_url:
                return self._get_fallback_answer(request_type)
            
            challenge_name = self._generate_challenge_name(question, request_type)
            image_base64 = self.get_image_base64(image_url, challenge_name)
            if not image_base64:
                return self._get_fallback_answer(request_type)
            
            return await self._solve_with_groq(question, image_base64, request_type, main_task)
    
    async def _solve_with_groq(self, question: str, image_base64: str, request_type: str, main_task: Dict) -> Dict:
        try:
            self._debug_print("Using Groq API for inference")
            prompt = self._get_prompt_for_challenge(request_type, question, main_task)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.1
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    self._debug_print(f"Groq API failed with status: {response.status_code}")
                    return self._get_fallback_answer(request_type, main_task)
                
                result = response.json()
            
            content = result["choices"][0]["message"]["content"]
            self._debug_print(f"Groq response: {content[:200]}...")
            
            json_blocks = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content)
            
            for json_block in json_blocks:
                try:
                    parsed = json.loads(json_block)
                    if 'answers' in parsed and isinstance(parsed['answers'], list) and parsed['answers']:
                        self.groq_counter += 1
                        self._debug_print(f"Successfully parsed Groq response: {parsed}")
                        return parsed
                except Exception as e:
                    continue
            
            self._debug_print("Failed to parse Groq response, using fallback")
            return self._get_fallback_answer(request_type, main_task)
            
        except Exception as e:
            self._debug_print(f"Exception in _solve_with_groq: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return self._get_fallback_answer(request_type, main_task)
    
    async def _solve_single_image_groq(self, question: str, image_base64: str, index: int) -> bool:
        try:
            prompt = f"Does this image contain {question}? Answer only 'yes' or 'no'."
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.vision_model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 10,
                "temperature": 0.1
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result["choices"][0]["message"]["content"].lower()
                    return 'yes' in answer or 'true' in answer
            
            return False
            
        except Exception as e:
            self._debug_print(f"Exception in _solve_single_image_groq: {e}")
            return False
    
    def _get_prompt_for_challenge(self, request_type: str, question: str, main_task: Dict) -> str:
        if request_type == 'image_label_binary':
            return f"""You are analyzing an image for a CAPTCHA challenge.
Question: {question}

The image is a 3x3 grid (9 tiles total). Each tile is numbered:
0 1 2
3 4 5
6 7 8

Return a JSON object with an "answers" array containing the grid positions (x, y) of tiles that match the question.
Format: {{"answers": [{{"x": 0, "y": 0}}, {{"x": 1, "y": 1}}]}}
where x is column (0-2) and y is row (0-2)."""
            
        elif request_type == 'image_label_area_select':
            return f"""You are analyzing an image for a CAPTCHA challenge.
Question: {question}

You need to click on the exact location where the requested object/feature is visible.
The image dimensions are approximately 400x300 pixels.

Return a JSON object with an "answers" array containing the x,y coordinates where you would click.
Format: {{"answers": [{{"x": 200, "y": 150}}]}}
Provide precise pixel coordinates."""
            
        elif request_type == 'image_drag_drop':
            entities = main_task.get('entities', [])
            num_objects = len(entities)
            
            if num_objects > 1:
                return f"""You are analyzing an image for a CAPTCHA challenge.
Question: {question}

There are {num_objects} objects that need to be placed at specific locations.
The image dimensions are approximately 400x300 pixels.

Return a JSON object with an "answers" array containing where each object should be dropped.
Format: {{"answers": [{{"to_x": 150, "to_y": 120}}, {{"to_x": 200, "to_y": 180}}]}}
Provide {num_objects} drop coordinates in the correct order."""
            else:
                return f"""You are analyzing an image for a CAPTCHA challenge.
Question: {question}

There is one object that needs to be placed at a specific location.
The image dimensions are approximately 400x300 pixels.

Return a JSON object with an "answers" array containing where the object should be dropped.
Format: {{"answers": [{{"to_x": 150, "to_y": 150}}]}}
Provide precise pixel coordinates."""
        
        return f"Analyze this image: {question}\nReturn JSON with answers array."
    
    def _get_fallback_answer(self, request_type: str, main_task: Dict = None) -> Dict:
        import random
        
        self._debug_print(f"Using fallback answer for {request_type}")
        
        if request_type == 'image_label_binary':
            patterns = [
                [{"x": 1, "y": 1}],
                [{"x": 0, "y": 0}, {"x": 2, "y": 2}],
                [{"x": 0, "y": 1}, {"x": 1, "y": 1}, {"x": 2, "y": 1}],
                [{"x": 1, "y": 0}, {"x": 1, "y": 1}],
            ]
            selected = random.choice(patterns)
            return {"answers": selected}
            
        elif request_type == 'image_label_area_select':
            similarity_coords = [
                [{"x": 180, "y": 160}, {"x": 320, "y": 180}],
                [{"x": 150, "y": 140}, {"x": 280, "y": 250}],
                [{"x": 200, "y": 120}, {"x": 250, "y": 280}],
            ]
            selected = random.choice(similarity_coords)
            return {"answers": selected}
            
        elif request_type == 'image_drag_drop':
            entities = main_task.get('entities', []) if main_task else []
            num_objects = len(entities) if entities else 1
            
            answers = []
            if num_objects > 1:
                drag_patterns = [
                    [{"to_x": 150, "to_y": 120}, {"to_x": 150, "to_y": 200}],
                    [{"to_x": 180, "to_y": 140}, {"to_x": 180, "to_y": 260}],
                ]
                selected = random.choice(drag_patterns)
            else:
                drag_patterns = [
                    [{"to_x": 150, "to_y": 150}],
                    [{"to_x": 180, "to_y": 200}],
                ]
                selected = random.choice(drag_patterns)
            
            for i, entity in enumerate(entities):
                if i < len(selected):
                    answers.append({
                        'entity_id': entity.get('entity_id'),
                        'to_x': selected[i]['to_x'],
                        'to_y': selected[i]['to_y']
                    })
            
            self._debug_print(f"Fallback answers: {answers}")
            return {"answers": answers}
        
        return {"answers": []}
    
    def _generate_challenge_name(self, question: str, request_type: str) -> str:
        words = re.findall(r'\b\w+\b', question.lower())
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'all', 'images', 'containing', 'click', 'select', 'place', 'objects', 'correct'}
        meaningful_words = [word for word in words if word not in stop_words and len(word) > 2]
        name_words = meaningful_words[:4]
        
        if name_words:
            challenge_name = '_'.join(name_words)
        else:
            challenge_name = request_type
        
        return challenge_name
    
    async def _process_challenge_entities(self, challenge_data: Dict, challenge_name: str, question: str):
        pass
