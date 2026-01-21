from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import os
import uuid
import re
from pathlib import Path
from datetime import datetime
import torch
from PIL import Image
import io
import base64
import requests
from typing import List, Dict, Any
import logging

from config.config import (
    MODELS_CONFIG, UPLOAD_CONFIG, SESSION_CONFIG, 
    TEMP_DIR, BASE_DIR, LANGUAGES
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

with open(BASE_DIR / "prompts" / "prompts.json", "r") as f:
    PROMPTS = json.load(f)

class ModelManager:
    def __init__(self):
        self.qwen3_vl = None
        self.medgemma = None
        self.loaded = False
    
    def load_models(self):
        try:
            logger.info("Loading models...")
            
            if MODELS_CONFIG["qwen3_vl"]["enabled"]:
                logger.info("Qwen3-VL will be called via Ollama API")
                self.qwen3_vl = "ollama"
            
            if MODELS_CONFIG["medgemma"]["enabled"]:
                logger.info("Loading MedGemma from HuggingFace...")
                try:
                    self.medgemma = "pending"
                    logger.info("MedGemma will be loaded on first use")
                except Exception as e:
                    logger.error(f"Error preparing MedGemma: {str(e)}")
                    self.medgemma = None
            
            self.loaded = True
            logger.info("All models ready")
        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            import traceback
            traceback.print_exc()
            self.loaded = False
    
    def get_medgemma_pipeline(self):
        if self.medgemma == "pending":
            try:
                from transformers import pipeline
                
                model_name = MODELS_CONFIG["medgemma"]["model_name"]
                logger.info(f"Lazy loading MedGemma: {model_name}")
                
                self.medgemma = pipeline(
                    "text-generation",
                    model=model_name,
                    device_map=MODELS_CONFIG["medgemma"]["device_map"],
                    torch_dtype=torch.bfloat16
                )
                logger.info("MedGemma loaded successfully")
            except Exception as e:
                logger.error(f"Error lazy loading MedGemma: {str(e)}")
                self.medgemma = None
                raise
        
        return self.medgemma

models = ModelManager()
sessions: Dict[str, Dict[str, Any]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Server starting...")
    models.load_models()
    logger.info("Server ready!")
    yield
    # Shutdown
    logger.info("Server shutting down...")
    if models.medgemma:
        del models.medgemma
    logger.info("Cleanup complete")

app = FastAPI(title="Medral AI Healthcare Platform", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

def create_session() -> str:
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "created_at": datetime.now(),
        "results": {},
        "files": {}
    }
    logger.info(f"Session created: {session_id}")
    return session_id

def save_uploaded_file(file: UploadFile) -> str:
    if not file.filename:
        raise ValueError("No filename provided")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in UPLOAD_CONFIG["allowed_extensions"]:
        raise ValueError(f"File type {file_ext} not allowed")
    
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = Path(TEMP_DIR) / unique_filename
    
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    
    return str(file_path)

async def call_qwen3_vl(image_path: str, prompt: str) -> Dict[str, Any]:
    """Call Qwen3-VL via Ollama API"""
    try:
        # Read image and encode to base64 cauz Ollama needs that
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        url = f"{MODELS_CONFIG['qwen3_vl']['base_url']}/api/generate"
        
        payload = {
            "model": MODELS_CONFIG["qwen3_vl"]["model_name"],
            "prompt": prompt,
            "images": [image_data],
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        raw_response = result.get("response", "")
        
        # Extract JSON from response (handles any extra text)
        clean_response = extract_json_from_response(raw_response)
        
        return {
            "status": "success",
            "response": clean_response,
            "model": "qwen3-vl"
        }
    except Exception as e:
        logger.error(f"Error calling Qwen3-VL: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "model": "qwen3-vl"
        }

async def call_qwen3_vl_text(prompt: str) -> Dict[str, Any]:
    try:
        url = f"{MODELS_CONFIG['qwen3_vl']['base_url']}/api/generate"
        
        payload = {
            "model": MODELS_CONFIG["qwen3_vl"]["model_name"],
            "prompt": prompt,
            "stream": False
        }
        
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        raw_response = result.get("response", "")
        
        clean_response = extract_json_from_response(raw_response)
        
        return {
            "status": "success",
            "response": clean_response,
            "model": "qwen3-vl"
        }
    except Exception as e:
        logger.error(f"Error calling Qwen3-VL (text): {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "model": "qwen3-vl"
        }

def extract_json_from_response(response_text: str) -> str:
    if not response_text:
        return "{}"
    
    text = response_text.strip()
    
    if text.startswith("thought\n"):
        text = text[8:]
    
    text = re.sub(r'^[^{\[]*', '', text, flags=re.DOTALL).strip()
    
    if '{' in text:
        last_close = text.rfind('}')
        if last_close != -1:
            text = text[:last_close + 1]
    elif '[' in text:
        last_close = text.rfind(']')
        if last_close != -1:
            text = text[:last_close + 1]
    
    return text.strip()

def parse_json_strict(text: str) -> dict | list | None:
    if not text:
        return None
    
    text = text.strip()
    
    if text.startswith("thought\n"):
        text = text[8:]
    
    text = text.strip()
    
    # Direct parse
    try:
        return json.loads(text)
    except:
        pass
    
    # Clean and retry parse. works?
    text_clean = re.sub(r'^[^{\[]*', '', text, flags=re.DOTALL).strip()
    try:
        return json.loads(text_clean)
    except:
        pass
    
    # Strategy 3: Extract innermost JSON. backup code 
    text_clean = extract_json_from_response(text)
    try:
        return json.loads(text_clean)
    except:
        pass
    
    return None

def flatten_nested_json(data):
    """Flatten nested raw_response fields"""
    if isinstance(data, dict):
        # If this dict has a raw_response key, try to parse it cauz the model nested JSON
        if "raw_response" in data and len(data) == 1:
            try:
                parsed = json.loads(data["raw_response"])
                return flatten_nested_json(parsed)
            except:
                return data
            
        # Otherwise process all values
        return {k: flatten_nested_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        result = []
        for item in data:
            flattened = flatten_nested_json(item)
            # If item was a raw_response dict that got parsed into a list, extend
            if isinstance(flattened, list):
                result.extend(flattened)
            else:
                result.append(flattened)
        return result
    else:
        return data

def parse_medicines_list(response_text: str) -> list:
    if not response_text or not response_text.strip():
        return []
    
    text = response_text.strip()
    # TODO: need to fix it as its not parsing properly sometimes
    parsed = parse_json_strict(text)
    if isinstance(parsed, list) and len(parsed) > 0:
        flattened = flatten_nested_json(parsed)
        return flattened if isinstance(flattened, list) else [flattened]
    elif isinstance(parsed, dict) and parsed:
        flattened = flatten_nested_json(parsed)
        return [flattened] if flattened else []
    
    # looks json using patterns
    array_pattern = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
    if array_pattern:
        try:
            result = json.loads(array_pattern.group(0))
            if isinstance(result, list):
                return result
        except:
            pass
    
    # sometimes returns multiple json objects based on order of medicines/ need to fix it or standardize it
    object_pattern = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    if object_pattern:
        results = []
        for obj_str in object_pattern:
            try:
                obj = json.loads(obj_str)
                if obj and isinstance(obj, dict):
                    results.append(obj)
            except:
                continue
        if results:
            return results
    
    return []

def parse_safety_analysis(response_text: str) -> dict:
    parsed = parse_json_strict(response_text)
    
    if isinstance(parsed, dict):
        # Remove any nested raw_response or analysis wrappers
        flattened = flatten_nested_json(parsed)
        if isinstance(flattened, dict):
            return flattened
        return {"analysis": str(flattened)}
    
    return {"analysis": response_text}

def parse_triage_result(response_text: str) -> dict:
    """Parse triage analysis response"""
    parsed = parse_json_strict(response_text)
    
    if isinstance(parsed, dict):
        return parsed
    
    return {"analysis": response_text}

def parse_test_results(response_text: str) -> list:
    if not response_text or not response_text.strip():
        return []
    
    text = response_text.strip()
    
    # TODO: need to fix it as its not parsing properly sometimes
    parsed = parse_json_strict(text)
    if isinstance(parsed, list) and len(parsed) > 0:
        flattened = flatten_nested_json(parsed)
        return flattened if isinstance(flattened, list) else [flattened]
    elif isinstance(parsed, dict) and parsed:
        return [flatten_nested_json(parsed)]
    
    
    array_pattern = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
    if array_pattern:
        try:
            result = json.loads(array_pattern.group(0))
            if isinstance(result, list):
                return result
        except:
            pass
    
    object_pattern = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
    if object_pattern:
        results = []
        for obj_str in object_pattern:
            try:
                obj = json.loads(obj_str)
                if obj and isinstance(obj, dict):
                    results.append(obj)
            except:
                continue
        if results:
            return results
    
    return []

def parse_explanation(response_text: str) -> dict:
    parsed = parse_json_strict(response_text)
    
    if isinstance(parsed, dict):
        return flatten_nested_json(parsed)
    
    return {"analysis": response_text}
    
def call_medgemma(text_input: str, system_prompt: str = "") -> Dict[str, Any]:
    """Call MedGemma for text processing"""
    try:
        # Lazy load pipeline if needed
        medgemma_pipe = models.get_medgemma_pipeline()
        
        if not medgemma_pipe:
            return {"status": "error", "error": "MedGemma not available"}
        
        full_prompt = f"{system_prompt}\n\n{text_input}" if system_prompt else text_input
        
        # Use pipeline with proper message format
        messages = [
            {"role": "user", "content": full_prompt}
        ]
        
        output = medgemma_pipe(messages, max_new_tokens=512)
        
        # Extract the response text from pipeline output
        response_text = output[0]['generated_text'][-1]['content']
        
        # Extract JSON from response (handles thinking text)
        clean_response = extract_json_from_response(response_text)
        
        return {
            "status": "success",
            "response": clean_response,
            "model": "medgemma"
        }
    except Exception as e:
        logger.error(f"Error calling MedGemma: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e),
            "model": "medgemma"
        }

@app.get("/health")
async def health_check():
    """Check server and model status"""
    return {
        "status": "running",
        "models_loaded": models.loaded,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/session/create")
async def create_new_session():
    """Create a new session"""
    session_id = create_session()
    return {"session_id": session_id, "timestamp": datetime.now().isoformat()}

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session data"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]

# ==================== TRIAGE ENDPOINT ====================
@app.post("/api/triage/process")
async def process_triage(files: List[UploadFile] = File(...), session_id: str = None):
    try:
        if not session_id or session_id not in sessions:
            session_id = create_session()
        
        if len(files) != 2:
            raise HTTPException(status_code=400, detail="Upload exactly 2 images: vitals slip + patient photo")
        
        # Save files
        file_paths = []
        for file in files:
            path = save_uploaded_file(file)
            file_paths.append(path)
        
        vitals_image = file_paths[0]  # First image: vitals slip
        patient_image = file_paths[1]  # Second image: patient photo
        
        # Step 1: Extract vitals from slip using Qwen3-VL
        logger.info("Extracting vitals from slip image...")
        qwen_vitals = await call_qwen3_vl(
            vitals_image,
            PROMPTS["triage"]["qwen3_vl"]
        )
        
        if qwen_vitals["status"] != "success":
            raise HTTPException(status_code=500, detail="Failed to extract vitals from slip")
        
        # Parse vitals
        vitals_data = parse_explanation(qwen_vitals["response"])
        logger.info(f"Extracted vitals: {vitals_data}")
        
        # Step 2: Assess patient physical condition from photo
        logger.info("Assessing patient physical condition...")
        physical_assessment_prompt = """You are a Medical Vision Specialist. Analyze this patient photo for visible signs of distress or condition.

Look for: 1) Skin color (pale, flushed, cyanotic), 2) Breathing pattern (labored, shallow, normal), 3) Posture/positioning, 4) Consciousness level, 5) Visible distress signs (sweating, grimacing, restlessness).

Output a JSON object: {"physical_condition": "description", "distress_level": "None/Mild/Moderate/Severe", "visible_signs": ["sign1", "sign2"], "breathing_assessment": "description", "consciousness": "alert/drowsy/unresponsive"}"""
        
        qwen_physical = await call_qwen3_vl(
            patient_image,
            physical_assessment_prompt
        )
        
        if qwen_physical["status"] != "success":
            logger.warning("Physical assessment failed, proceeding with vitals only")
            physical_data = {"physical_condition": "Unable to assess from image", "distress_level": "Unknown"}
        else:
            physical_data = parse_explanation(qwen_physical["response"])
            logger.info(f"Physical assessment: {physical_data}")
        
        # Step 3: Combined triage analysis using both vitals and physical assessment
        logger.info("Performing combined triage analysis...")
        combined_triage_prompt = f"""You are a Triage Nurse using Indian PHC guidelines. Make a triage decision based on BOTH vitals and physical assessment.

VITALS DATA: {json.dumps(vitals_data)}

PHYSICAL ASSESSMENT: {json.dumps(physical_data)}

Assign priority based on COMBINED analysis:
- RED: Life-threatening (severe vital signs + severe distress)
- YELLOW: Urgent care needed (abnormal vitals or moderate distress)
- GREEN: Stable (normal/mild findings)

Output ONLY this JSON format with NO extra text:
{{"priority": "RED or YELLOW or GREEN", "justification_english": "Combined assessment reasoning in simple English", "justification_hindi": "सरल हिंदी में कारण", "key_vital_flags": ["concerning findings"], "physical_flags": ["physical concerns"], "recommended_action": "immediate action for nurse", "assessment_basis": "vitals and physical combined"}}"""
        
        # Use the vitals image for the API call (Qwen can work with text prompts too)
        qwen_triage = await call_qwen3_vl(
            vitals_image,
            combined_triage_prompt
        )
        
        if qwen_triage["status"] != "success":
            raise HTTPException(status_code=500, detail="Triage decision analysis failed")
        
        # Parse triage decision
        triage_result = parse_triage_result(qwen_triage["response"])
        logger.info(f"Triage decision: {triage_result}")
        
        result = {
            "status": "success",
            "session_id": session_id,
            "tab": "triage",
            "vitals_extraction": vitals_data,
            "physical_assessment": physical_data,
            "triage_analysis": triage_result,
            "timestamp": datetime.now().isoformat()
        }
        
        sessions[session_id]["results"]["triage"] = result
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Triage error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reports/process")
async def process_reports(files: List[UploadFile] = File(...), session_id: str = None):
    try:
        if not session_id or session_id not in sessions:
            session_id = create_session()
        
        if len(files) == 0 or len(files) > UPLOAD_CONFIG["max_files_per_request"]:
            raise HTTPException(status_code=400, detail=f"Upload 1-{UPLOAD_CONFIG['max_files_per_request']} images")
        
        # Save files
        file_paths = []
        for file in files:
            path = save_uploaded_file(file)
            file_paths.append(path)
        
        extracted_tests = []
        
        for idx, file_path in enumerate(file_paths):
            logger.info(f"Processing image {idx+1}/{len(file_paths)} for test extraction")
            qwen_response = await call_qwen3_vl(
                file_path,
                PROMPTS["reports"]["qwen3_vl"]
            )
            
            if qwen_response["status"] == "success":
                response_text = qwen_response["response"].strip()
                logger.info(f"Raw Qwen response for tests: {response_text[:200]}...")
                
                # Parse using dedicated function
                parsed_tests = parse_test_results(response_text)
                
                if parsed_tests and len(parsed_tests) > 0:
                    extracted_tests.extend(parsed_tests)
                    logger.info(f"Successfully parsed {len(parsed_tests)} tests from image {idx+1}")
                else:
                    logger.warning(f"No tests extracted from image {idx+1}. Raw response: {response_text[:100]}...")
        
        logger.info(f"Total tests extracted: {len(extracted_tests)}")
        
        # Step 2: Get explanations using Qwen3-VL for analysis
        explanation_prompt = f"""As a Patient Health Educator, explain these lab results in simple terms for a non-medical person.

Lab Results: {json.dumps(extracted_tests)}

Output ONLY this JSON format with NO thinking or extra text:
{{"explanations": [{{"test_name": "name", "simple_explanation": "2 sentences", "status": "Normal/Concerning", "analogy": "simple comparison"}}], "next_steps": ["action1", "action2"], "warning_signs": "if any"}}"""
        
        qwen_explanation = await call_qwen3_vl(
            file_paths[0],
            explanation_prompt
        )
        
        # Parse explanation response
        explanations = None
        response_text = qwen_explanation["response"].strip()
        
        # Try multiple parsing strategies
        try:
            explanations = json.loads(response_text)
        except:
            pass
        
        if not explanations:
            try:
                clean_text = extract_json_from_response(response_text)
                explanations = json.loads(clean_text)
            except:
                pass
        
        if not explanations:
            try:
                match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if match:
                    explanations = json.loads(match.group(0))
            except:
                pass
        
        if not explanations:
            explanations = {"analysis": response_text}
        
        result = {
            "status": "success",
            "session_id": session_id,
            "tab": "reports",
            "extracted_tests": extracted_tests,
            "patient_explanations": explanations,
            "timestamp": datetime.now().isoformat()
        }
        
        sessions[session_id]["results"]["reports"] = result
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reports error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== SCRIBE ENDPOINT ====================
@app.post("/api/scribe/process")
async def process_scribe(files: List[UploadFile] = File(...), session_id: str = None):
    """
    Process handwritten doctor notes
    Input: 1-2 images (doctor notes, paper records)
    """
    try:
        if not session_id or session_id not in sessions:
            session_id = create_session()
        
        if len(files) == 0 or len(files) > 2:
            raise HTTPException(status_code=400, detail="Upload 1-2 images")
        
        # Save files
        file_paths = []
        for file in files:
            path = save_uploaded_file(file)
            file_paths.append(path)
        
        # Step 1: Transcribe from Qwen3-VL
        qwen_response = await call_qwen3_vl(
            file_paths[0],
            PROMPTS["scribe"]["qwen3_vl"]
        )
        
        if qwen_response["status"] != "success":
            raise HTTPException(status_code=500, detail="Vision model failed")
        
        # Parse transcription with multiple strategies
        transcribed_notes = None
        response_text = qwen_response["response"].strip()
        
        try:
            transcribed_notes = json.loads(response_text)
        except:
            pass
        
        if not transcribed_notes:
            try:
                clean_text = extract_json_from_response(response_text)
                transcribed_notes = json.loads(clean_text)
            except:
                pass
        
        if not transcribed_notes:
            try:
                match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if match:
                    transcribed_notes = json.loads(match.group(0))
            except:
                pass
        
        if not transcribed_notes:
            transcribed_notes = {"raw_response": response_text}
        
        summary_prompt = f"""As a Clinical Registrar, create a 3-bullet Executive Summary for the physician.

Patient History: {json.dumps(transcribed_notes)}

Highlight the most critical complaint first. Output ONLY this JSON format with NO thinking or extra text:
{{"executive_summary": ["critical point 1", "point 2", "point 3"], "critical_flags": ["flag1"], "doctor_focus_time": "Under 10 seconds"}}"""
        
        qwen_summary = await call_qwen3_vl(
            file_paths[0],
            summary_prompt
        )
        
        # Parse summary with multiple strategies
        summary = None
        response_text = qwen_summary["response"].strip()
        
        try:
            summary = json.loads(response_text)
        except:
            pass
        
        if not summary:
            try:
                clean_text = extract_json_from_response(response_text)
                summary = json.loads(clean_text)
            except:
                pass
        
        if not summary:
            try:
                match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if match:
                    summary = json.loads(match.group(0))
            except:
                pass
        
        if not summary:
            summary = {"analysis": response_text}
        
        result = {
            "status": "success",
            "session_id": session_id,
            "tab": "scribe",
            "transcribed_notes": transcribed_notes,
            "doctor_summary": summary,
            "timestamp": datetime.now().isoformat()
        }
        
        sessions[session_id]["results"]["scribe"] = result
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/translator/process")
async def process_translator(file: UploadFile = File(None), session_id: str = None, text_input: str = None):
    try:
        if not session_id or session_id not in sessions:
            session_id = create_session()
        
        file_path = None
        
        # Step 1: Get translation
        if file:
            # Extract text from image
            file_path = save_uploaded_file(file)
            qwen_response = await call_qwen3_vl(
                file_path,
                PROMPTS["translator"]["qwen3_vl"]
            )
        elif text_input:
            # Use provided text directly - create a prompt that doesn't require an image
            detection_prompt = f"""Detect language and translate this medical text to English:

Text: {text_input}

Output ONLY this JSON format with NO extra text:
{{"detected_language": "code", "original_text": "{text_input}", "english_translation": "translation", "language_name": "name", "is_medicine_instruction": true/false, "dosage_info": "if any", "confidence": "high/medium/low"}}"""
            
            # Call Qwen via direct API (not file-based)
            qwen_response = await call_qwen3_vl_text(detection_prompt)
        else:
            raise HTTPException(status_code=400, detail="Provide either file or text_input")
        
        if qwen_response["status"] != "success":
            raise HTTPException(status_code=500, detail="Translation extraction failed")
        
        # Parse translation
        translation_data = parse_explanation(qwen_response["response"])
        
        # Step 2: Validate translation with Qwen3-VL (text-only)
        validation_prompt = f"""Review this medical translation for accuracy:

{json.dumps(translation_data)}

Check for mistranslations and clarity. Output ONLY this JSON format with NO extra text:
{{"validation_status": "Valid/Needs Review", "accuracy_check": ["check1"], "potential_issues": ["issue1"], "clarified_meaning": "meaning", "patient_safe_version": "final translation"}}"""
        
        qwen_validation = await call_qwen3_vl_text(validation_prompt)
        
        # Parse validation
        validation = parse_explanation(qwen_validation["response"])
        
        result = {
            "status": "success",
            "session_id": session_id,
            "tab": "translator",
            "translation": translation_data,
            "validation": validation,
            "timestamp": datetime.now().isoformat()
        }
        
        sessions[session_id]["results"]["translator"] = result
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Translator error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/polypharmacy/process")
async def process_polypharmacy(files: List[UploadFile] = File(...), session_id: str = None):
    try:
        if not session_id or session_id not in sessions:
            session_id = create_session()
        
        if len(files) == 0 or len(files) > UPLOAD_CONFIG["max_files_per_request"]:
            raise HTTPException(status_code=400, detail=f"Upload 1-{UPLOAD_CONFIG['max_files_per_request']} images")
        
        # Save files
        file_paths = []
        for file in files:
            path = save_uploaded_file(file)
            file_paths.append(path)
        
        medicines_list = []
        
        for idx, file_path in enumerate(file_paths):
            logger.info(f"Processing image {idx+1}/{len(file_paths)} for medicine extraction")
            qwen_response = await call_qwen3_vl(
                file_path,
                PROMPTS["polypharmacy"]["qwen3_vl"]
            )
            
            if qwen_response["status"] == "success":
                response_text = qwen_response["response"].strip()
                logger.info(f"Raw Qwen response for medicines: {response_text[:200]}...")
                
                # Use dedicated parser for medicines
                medicines = parse_medicines_list(response_text)
                
                if medicines and len(medicines) > 0:
                    medicines_list.extend(medicines)
                    logger.info(f"Successfully parsed {len(medicines)} medicines from image {idx+1}")
                else:
                    logger.warning(f"No medicines extracted from image {idx+1}. Raw response: {response_text[:100]}...")
        
        logger.info(f"Total medicines extracted: {len(medicines_list)}")
        
        # Step 2: Safety check with Qwen3-VL
        safety_prompt = f"""You are a Clinical Safety Monitor specializing in polypharmacy. Review these medicines: {json.dumps(medicines_list)}

Check for: 1) Drug interactions, 2) Duplicate medications, 3) Dangerous combinations, 4) Safety warnings.

Output ONLY this JSON format with NO thinking or extra text:
{{"medicines_list": [{{"name": "med", "category": "class"}}], "drug_interactions": ["interaction: description"], "duplicate_medications": ["dup1"], "safety_warnings": ["warning1"], "recommendation": "action", "urgency": "Low/Medium/High"}}"""
        
        qwen_safety = await call_qwen3_vl(
            file_paths[0],
            safety_prompt
        )
        
        # Use dedicated parser for safety analysis
        safety_analysis = parse_safety_analysis(qwen_safety["response"])
        
        result = {
            "status": "success",
            "session_id": session_id,
            "tab": "polypharmacy",
            "medicines_extracted": medicines_list,
            "safety_analysis": safety_analysis,
            "timestamp": datetime.now().isoformat()
        }
        
        sessions[session_id]["results"]["polypharmacy"] = result
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Polypharmacy error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
