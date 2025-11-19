import onnxruntime as ort, torch, torchvision.transforms as transforms, numpy as np, cv2, json, os, base64, io
from PIL import Image
from typing import Dict, Any, Optional, List, Union
try:
    from ultralytics import YOLO
    from ultralytics.nn.tasks import DetectionModel
    torch.serialization.add_safe_globals([DetectionModel])
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False

class ModelHandler:
    def __init__(self, data_json_path: str = "data.json", debug: bool = False):
        self.data_json_path = data_json_path
        self.loaded_models = {}
        self.question_mapping = {}
        self.model_settings = {}
        self.debug = debug
        self.load_configuration()

    def _debug_print(self, message: str):
        """Print debug messages if debug mode is enabled"""
        if self.debug:
            print(f"[MODEL HANDLER] {message}")

    def load_configuration(self):
        try:
            if os.path.exists(self.data_json_path):
                with open(self.data_json_path, 'r') as f:
                    data = json.load(f)
                    self.question_mapping = {}
                    for model_file, question in data.items():
                        if model_file.endswith('.onnx'):
                            self.question_mapping[question] = {'model_type': 'onnx', 'model_path': f'models/{model_file}'}
                        elif model_file.endswith('.pt'):
                            self.question_mapping[question] = {'model_type': 'pytorch', 'model_path': f'models/{model_file}'}
                    
                    print(f"Loaded {len(self.question_mapping)} question mappings")
                    
                    if self.debug:
                        print("=" * 80)
                        print("Question to Model Mapping:")
                        for i, (question, info) in enumerate(self.question_mapping.items(), 1):
                            print(f"{i}. '{question}' -> {info['model_path']}")
                        print("=" * 80)
            else:
                print(f"Data file not found: {self.data_json_path}")
        except Exception as e:
            print(f"Error loading configuration: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()

    def get_model_for_question(self, question: str) -> Optional[Dict]:
        if question in self.question_mapping:
            self._debug_print(f"Exact match found for: '{question}'")
            return self.question_mapping[question]
        
        for mapped_question, model_info in self.question_mapping.items():
            if self._questions_similar(question, mapped_question):
                self._debug_print(f"Similar match found:")
                self._debug_print(f"  Challenge: '{question}'")
                self._debug_print(f"  Mapped to: '{mapped_question}'")
                self._debug_print(f"  Model: {model_info['model_path']}")
                return model_info
        
        self._debug_print(f"No model found for: '{question}'")
        return None

    def _questions_similar(self, q1: str, q2: str, threshold: float = 0.5) -> bool:
        q1_words = set(q1.lower().split())
        q2_words = set(q2.lower().split())
        if len(q1_words) == 0 or len(q2_words) == 0:
            return False
        intersection = q1_words.intersection(q2_words)
        union = q1_words.union(q2_words)
        if len(union) == 0:
            return False
        similarity = len(intersection) / len(union)
        return similarity >= threshold

    def load_model(self, model_path: str, model_type: str):
        if model_path in self.loaded_models:
            self._debug_print(f"Using cached model: {model_path}")
            return self.loaded_models[model_path]
        try:
            self._debug_print(f"Loading {model_type} model: {model_path}")
            if model_type == 'onnx':
                session = ort.InferenceSession(model_path)
                self.loaded_models[model_path] = {'session': session, 'type': 'onnx', 'input_name': session.get_inputs()[0].name, 'input_shape': session.get_inputs()[0].shape}
            elif model_type == 'pytorch':
                model = YOLO(model_path)
                self.loaded_models[model_path] = {'model': model, 'type': 'pytorch', 'device': 'cuda' if torch.cuda.is_available() else 'cpu'}
            self._debug_print(f"Successfully loaded: {model_path}")
            return self.loaded_models[model_path]
        except Exception as e:
            print(f"Error loading model {model_path}: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return None

    def preprocess_image(self, image_data: str, model_type: str, input_shape: tuple = None):
        try:
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            self._debug_print(f"Image size: {image.size} (width x height)")
            
            if model_type == 'onnx':
                if input_shape is not None and len(input_shape) >= 3:
                    height, width = input_shape[-2], input_shape[-1]
                else:
                    height, width = 224, 224
                transform = transforms.Compose([transforms.Resize((height, width)), transforms.ToTensor(), transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
                tensor = transform(image)
                tensor = tensor.unsqueeze(0)
                return tensor.numpy(), image
            elif model_type == 'pytorch':
                img_array = np.array(image)
                return img_array, image
        except Exception as e:
            print(f"Error preprocessing image: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return None, None

    def run_inference(self, question: str, image_data: str) -> Optional[Union[List, Dict]]:
        self._debug_print(f"Running inference for: '{question}'")
        
        model_info = self.get_model_for_question(question)
        if model_info is None:
            self._debug_print("No model available for this question")
            return None
        
        model_path = model_info['model_path']
        model_type = model_info['model_type']
        
        loaded_model = self.load_model(model_path, model_type)
        if loaded_model is None:
            self._debug_print("Failed to load model")
            return None
        
        original_image = None
        if model_type == 'onnx':
            processed_image, original_image = self.preprocess_image(image_data, model_type, loaded_model.get('input_shape'))
        else:
            processed_image, original_image = self.preprocess_image(image_data, model_type)
        
        if processed_image is None:
            self._debug_print("Failed to preprocess image")
            return None
        
        try:
            if model_type == 'onnx':
                session = loaded_model['session']
                input_name = loaded_model['input_name']
                outputs = session.run(None, {input_name: processed_image})
                self._debug_print("ONNX inference completed")
                return outputs
            elif model_type == 'pytorch':
                model = loaded_model['model']
                self._debug_print("Running YOLO inference...")
                results = model(processed_image, verbose=False)
                
                coordinates = []
                for r in results:
                    boxes = r.boxes
                    self._debug_print(f"Total detections: {len(boxes)}")
                    
                    if len(boxes) == 0:
                        self._debug_print("WARNING: No objects detected!")
                        return None
                    
                    for idx, box in enumerate(boxes):
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        x_center = float((x1 + x2) / 2)
                        y_center = float((y1 + y2) / 2)
                        width = float(x2 - x1)
                        height = float(y2 - y1)
                        confidence = float(box.conf[0].item()) if hasattr(box, 'conf') else 0.8
                        class_id = int(box.cls[0].item()) if hasattr(box, 'cls') else 0
                        
                        if self.debug:
                            print(f"[MODEL HANDLER] Detection #{idx + 1}:")
                            print(f"  - Bounding Box: [{x1:.1f}, {y1:.1f}, {x2:.1f}, {y2:.1f}]")
                            print(f"  - Center: x={x_center:.1f}, y={y_center:.1f}")
                            print(f"  - Size: {width:.1f}x{height:.1f}")
                            print(f"  - Confidence: {confidence:.3f}")
                            print(f"  - Class ID: {class_id}")
                        
                        coordinates.append({
                            'x': x_center, 
                            'y': y_center, 
                            'confidence': confidence,
                            'class_id': class_id,
                            'bbox': [x1, y1, x2, y2]
                        })
                
                if len(coordinates) == 0:
                    self._debug_print("No valid coordinates extracted")
                    return None
                
                self._debug_print(f"Successfully extracted {len(coordinates)} coordinate(s)")
                return {
                    'type': 'pytorch', 
                    'coordinates': coordinates, 
                    'success': True, 
                    'count': len(coordinates)
                }
        except Exception as e:
            print(f"Error during inference: {e}")
            if self.debug:
                import traceback
                traceback.print_exc()
            return None

    def process_model_output(self, outputs: Union[List, Dict, np.ndarray], model_type: str = 'onnx') -> Dict:
        try:
            if model_type == 'pytorch':
                if isinstance(outputs, dict):
                    if 'coordinates' in outputs and outputs.get('success'):
                        return outputs
                if isinstance(outputs, list) and len(outputs) > 0:
                    if isinstance(outputs[0], dict) and 'x' in outputs[0] and 'y' in outputs[0]:
                        return {'type': 'pytorch', 'coordinates': outputs, 'success': True, 'count': len(outputs)}
            if model_type == 'onnx':
                if isinstance(outputs, (list, tuple)) and len(outputs) > 0:
                    output = outputs[0]
                    if isinstance(output, np.ndarray):
                        if output.ndim == 2 and output.shape[1] >= 2:
                            return {'coordinates': output.tolist(), 'confidence': 0.8}
                        else:
                            return {'scores': output.tolist(), 'confidence': float(np.max(output))}
            return {'error': 'Unable to process model output', 'success': False}
        except Exception as e:
            self._debug_print(f"Error processing model output: {e}")
            return {'error': str(e), 'success': False}

    def is_model_available_for_question(self, question: str) -> bool:
        result = self.get_model_for_question(question)
        is_available = result is not None
        self._debug_print(f"Model available for '{question}': {is_available}")
        return is_available