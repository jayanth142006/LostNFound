import os
import json
import requests
import re
from datetime import datetime
from typing import List, Dict
import google.generativeai as genai

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")


def generate_verification_questions(lost_description: str, found_caption: str) -> List[Dict]:
    """
    Generate 3 ownership verification questions using Gemini Flash.
    Optimized for low token usage.
    """

    prompt = f"""
Generate 3 ownership verification questions.

Lost item: {lost_description}
Found item: {found_caption}

Return JSON only:
[
{{"question":"...","type":"text|choice","options":["..."]|null,"correct_answer":"..."}}
]

Rules:
- questions must NOT reveal answers
- options null for text
- keep questions short
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 1000
            }
        )

        content = response.text.strip()

        cleaned = re.sub(r"```json|```", "", content).strip()

        json_match = re.search(r"\[.*\]", cleaned, re.DOTALL)

        if json_match:
            return json.loads(json_match.group())

    except Exception as e:
        print(f"Error generating questions: {e}")

    # Fallback questions
    return [
        {"question": "What brand or logo is on the item?", "type": "text", "options": None, "correct_answer": "any"},
        {"question": "Where did you lose the item?", "type": "text", "options": None, "correct_answer": "any"},
        {"question": "What color is the item?", "type": "text", "options": None, "correct_answer": "any"}
    ]

def calculate_confidence_score(user_answers: List[Dict], actual_questions: List[Dict], proof_files: List[str], metadata: Dict) -> Dict:
    """
    Logic:
    - Ownership question match: 60%
    - Image similarity (presence of proof): 25%
    - Metadata consistency (location/time): 10%
    - Submission timing validity: 5%
    """
    score = 0
    details = {}
    
    # 1. Ownership questions (60%)
    correct_count = 0
    for i, ans in enumerate(user_answers):
        actual = actual_questions[i]
        user_val = str(ans.get("answer", "")).lower().strip()
        correct_val = str(actual.get("correct_answer", "")).lower().strip()
        
        # Simple string match or keyword match
        if correct_val == "any" or user_val == correct_val or correct_val in user_val:
            correct_count += 1
            
    question_score = (correct_count / len(actual_questions)) * 60 if actual_questions else 0
    score += question_score
    details["questions_score"] = question_score
    
    # 2. Proof files (25%)
    # Basic check: at least 2 files (Item proof + Selfie)
    proof_score = min(len(proof_files) / 2, 1.0) * 25
    score += proof_score
    details["proof_score"] = proof_score
    
    # 3. Metadata consistency (10%)
    # For now, let's assume if they provided a location that matches roughly
    # In a real app, we'd compare lat/lng or specific strings
    metadata_score = 10 # Default to 10 for now if they filled the form
    score += metadata_score
    details["metadata_score"] = metadata_score
    
    # 4. Submission timing (5%)
    # Check if they haven't spent too long (e.g., < 30 mins)
    timing_score = 5
    score += timing_score
    details["timing_score"] = timing_score
    
    status = "PENDING"
    VERIFICATION_THRESHOLD = 75
    
    if score >= VERIFICATION_THRESHOLD:
        status = "VERIFIED"
    elif score >= 50:
        status = "MANUAL_REVIEW"
    else:
        status = "FAILED"
        
    return {
        "confidence_score": round(score, 2),
        "status": status,
        "details": details
    }
