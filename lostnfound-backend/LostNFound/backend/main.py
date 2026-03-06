import os
import time
import joblib
import pandas as pd
from urllib import response

from overrides import final
from fastapi import FastAPI, UploadFile, File, Form
from database import Base, engine, SessionLocal
from models import LostItem, FoundItem, DetectiveRequest, FinalizeRequest, Match, Verification
from image_generation import generate_lost_item_image
from caption import generate_caption    
from embedding import get_combined_embedding
from vector_db import add_to_vector_db, search_vector_db
from fastapi.middleware.cors import CORSMiddleware
import json
import requests
from pydantic import BaseModel
import re
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fraud_service import generate_verification_questions, calculate_confidence_score
from qr_utility import generate_signed_qr
import uuid
import shutil
from fastapi import HTTPException
from compare_items import text_similarity, image_similarity, text_image_similarity
from datetime import datetime
from fastapi import FastAPI, HTTPException
import google.generativeai as genai
from dotenv import load_dotenv

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-2.5-flash")

# Load Recovery Model
# main.py is in LNF/lostnfound-backend/LostNFound/backend/
# We need to go up 4 levels to reach LNF root
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MODEL_DIR = os.path.join(base_dir, "rec_prob")
MODEL_PATH = os.path.join(MODEL_DIR, "recovery_model_v3.pkl")
COLUMNS_PATH = os.path.join(MODEL_DIR, "model_columns.pkl")

try:
    recovery_model = joblib.load(MODEL_PATH)
    recovery_columns = joblib.load(COLUMNS_PATH)
    print("✅ Recovery model and columns loaded successfully.")
except Exception as e:
    print(f"⚠️ Error loading recovery model: {e}")
    recovery_model = None
    recovery_columns = []


load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = os.path.join(BASE_DIR, "generated_images")
os.makedirs(IMAGE_DIR, exist_ok=True)

app.mount("/generated_images", StaticFiles(directory=IMAGE_DIR), name="generated_images")

UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploaded_images", StaticFiles(directory=UPLOAD_DIR), name="uploaded_images")

VERIFICATION_DIR = os.path.join(UPLOAD_DIR, "verification")
os.makedirs(VERIFICATION_DIR, exist_ok=True)

QR_DIR = os.path.join(BASE_DIR, "qr_codes")
os.makedirs(QR_DIR, exist_ok=True)
app.mount("/qr_codes", StaticFiles(directory=QR_DIR), name="qr_codes")


DISTANCE_THRESHOLD = 0.25  # lower = more similar


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def get_root_path():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def calculate_recovery_probability(category: str, color: str, location: str, time_str: str, days_since_loss: int):
    if not recovery_model or not recovery_columns:
        return 10.0 # Fallback

    try:
        # Footfall Logic from rec_prob/app.py
        def get_footfall_score(loc: str, t_str: str) -> float:
            loc = loc.lower()
            if not loc or "unknown" in loc: return 0.2
            base_score = 0.45
            if any(k in loc for k in ["clock", "tower", "landmark", "statue", "monument", "entrance", "gate"]): base_score = 0.90
            elif any(k in loc for k in ["canteen", "library", "audi", "class", "lab", "block", "dept", "office", "room", "hall", "building"]): base_score = 0.85
            elif any(k in loc for k in ["bus", "stop", "station", "subway", "transit", "vehicle", "parking"]): base_score = 0.75
            elif any(k in loc for k in ["path", "way", "road", "walk", "corridor", "stairs", "lobby"]): base_score = 0.60
            
            try:
                hour = int(t_str.split(":")[0])
                if (8 <= hour <= 9) or (12 <= hour <= 14) or (15 <= hour <= 16): base_score *= 1.1
                elif (hour >= 20) or (hour < 6): base_score *= 0.6
            except: pass
            return min(1.0, float(base_score))

        footfall = get_footfall_score(location, time_str)
        max_sim = 0.75 if any(k in category.lower() for k in ["id card", "wallet", "phone", "umbrella", "bottle"]) else 0.4
        similar_nearby = int(footfall * max_sim * 0.5)

        enriched = {
            "category": category,
            "color": color,
            "reported_location": location,
            "footfall_score": footfall,
            "days_since_loss": days_since_loss,
            "max_similarity_score": max_sim,
            "similar_items_nearby_48h": similar_nearby
        }

        input_df = pd.DataFrame([enriched])
        input_df = pd.get_dummies(input_df)
        input_df = input_df.reindex(columns=recovery_columns, fill_value=0)
        
        prob = float(recovery_model.predict_proba(input_df)[0][1])
        return round(prob * 100, 2)
    except Exception as e:
        print(f"Error predicting recovery: {e}")
        return 10.0


@app.post("/lost/")
def add_lost(
    description: str = Form(...), 
    email: str = Form(...),
    category: str = Form("Unknown"),
    color: str = Form("Unknown"),
    location: str = Form("Unknown"),
    time: str = Form("12:00"),
    days_since_loss: int = Form(0)
):
    db = SessionLocal()

    image_path = generate_lost_item_image(description)
    if not image_path:
        db.close()
        return {"success": False, "message": "Image generation failed"}

    lost = LostItem(
        description=description, 
        image_path=image_path, 
        email=email,
        category=category,
        color=color,
        location=location,
        time=time,
        days_since_loss=days_since_loss,
        created_at=datetime.now().isoformat()
    )
    db.add(lost)
    db.commit()
    db.refresh(lost)

    embedding = get_combined_embedding(description, image_path)
    add_to_vector_db(lost.id, embedding)

    # Trigger matching
    match_found = check_for_matches(lost.id, is_lost=True)

    db.close()

    image_url = f"http://localhost:8000/generated_images/{os.path.basename(image_path)}"

    return {
        "success": True,
        "message": "Lost item stored successfully",
        "image_url": image_url,
        "match_found": match_found
    }



@app.post("/found/")
def add_found(
    file: UploadFile = File(...), 
    location: str = Form(...), 
    condition: str = Form(...)
):
    db = SessionLocal()

    BASE_DIR = get_root_path()
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_images")
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(file.file.read())

    caption = generate_caption(file_path)

    found = FoundItem(
        caption=caption, 
        image_path=file_path,
        location=location,
        condition=condition,
        created_at=datetime.now().isoformat()
    )
    db.add(found)
    db.commit()
    db.refresh(found)

    query_embedding = get_combined_embedding(caption, file_path)
    add_to_vector_db(found.id, query_embedding, is_lost=False)

    # Matching logic for found items
    match_found = check_for_matches(found.id, is_lost=False)

    db.close()

    return {
        "success": True,
        "caption": caption,
        "match_found": match_found,
        "item_id": found.id
    }

@app.get("/found-items")
def get_found_items():
    db = SessionLocal()
    items = db.query(FoundItem).order_by(FoundItem.id.desc()).all()
    result = []
    for item in items:
        # Assuming uploaded images are also servable or moved to a static dir
        # Let's mount uploaded_images too
        result.append({
            "id": item.id,
            "caption": item.caption,
            "image_url": f"http://localhost:8000/uploaded_images/{os.path.basename(item.image_path)}",
            "location": item.location,
            "date": item.created_at
        })
    db.close()
    return result

def get_text_representation(item, is_lost):
    """
    Returns unified text representation for similarity comparison.
    LostItem -> description
    FoundItem -> caption + location + condition
    """

    if is_lost:
        return item.description or ""
    else:
        return f"{item.caption or ''} {item.location or ''} {item.condition or ''}".strip()


def check_for_matches(item_id, is_lost=True):
    db = SessionLocal()
    match_found = False

    try:
       
        if is_lost:
            current_item = db.query(LostItem).filter(LostItem.id == item_id).first()
            candidates = db.query(FoundItem).filter(FoundItem.matched == 0).all()
        else:
            current_item = db.query(FoundItem).filter(FoundItem.id == item_id).first()
            candidates = db.query(LostItem).filter(LostItem.matched == 0).all()

        if not current_item:
            print("No current item found.")
            return False

        # -------------------------------------------------
        # Matching Loop
        # -------------------------------------------------
        for candidate in candidates:

            # TEXT similarity
            if is_lost:
                text1 = current_item.description or ""
                text2 = get_text_representation(candidate, False)
            else:
                text1 = get_text_representation(current_item, False)
                text2 = candidate.description or ""

            s1 = text_similarity(text1, text2)

            # IMAGE similarity
            try:
                if os.path.exists(current_item.image_path) and os.path.exists(candidate.image_path):
                    s2 = image_similarity(
                        current_item.image_path,
                        candidate.image_path
                    )
                else:
                    print("⚠ Image file missing. Skipping image similarity.")
                    s2 = 0
            except Exception as img_error:
                print(f"Image similarity error: {img_error}")
                s2 = 0

            # CROSS similarity
# CROSS similarity
            try:
                if os.path.exists(candidate.image_path):
                    s3 = text_image_similarity(
                        text1,
                        candidate.image_path
                    )
                else:
                    print("⚠ Candidate image missing. Skipping cross similarity.")
                    s3 = 0
            except Exception as cross_error:
                print(f"Cross similarity error: {cross_error}")
                s3 = 0

            # FINAL score
            final_score = (0.4 * s1) + (0.4 * s2) + (0.2 * s3)

            print("\n-----------------------------------")
            print(f"Comparing with Candidate ID: {candidate.id}")
            print(f"Text Similarity: {s1:.3f}")
            print(f"Image Similarity: {s2:.3f}")
            print(f"Cross Similarity: {s3:.3f}")
            print(f"Final Score: {final_score:.3f}")
            print("-----------------------------------")

            # -------------------------------------------------
            # If match threshold passed
            # -------------------------------------------------
            if final_score >= 0.6:

                if is_lost:
                    lost_item = current_item
                    found_item = candidate
                else:
                    lost_item = candidate
                    found_item = current_item

                # Check if match already exists
                existing_match = db.query(Match).filter(
                    Match.lost_item_id == lost_item.id,
                    Match.found_item_id == found_item.id
                ).first()

                if not existing_match:

                    lost_item.matched = 1
                    found_item.matched = 1

                    new_match = Match(
                        lost_item_id=lost_item.id,
                        found_item_id=found_item.id,
                        similarity_score=int(final_score * 100),
                        created_at=datetime.now().isoformat()
                    )

                    db.add(new_match)
                    db.commit()
                    db.refresh(new_match)

                    print(f"Match created! Match ID: {new_match.id}")

                    # Send email safely
                    try:
                        if lost_item.email:
                            send_match_email(
                                lost_item.email,
                                lost_item,
                                found_item,
                                new_match.id
                            )
                            print(" Email sent.")
                    except Exception as email_error:
                        print(f"Email sending failed: {email_error}")

                match_found = True

    except Exception as e:
        print(f"Matching error: {e}")

    finally:
        db.close()

    return match_found

def send_match_email(to_email, lost_item, found_item, match_id):

    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    if not smtp_user or not smtp_pass:
        print(f"Email skip: Credentials missing. Match for {to_email}")
        return

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    subject = "Your missing item may have been found!"
    body = f"""
    Hello,
    
    Good news! Sherlock has found a potential match for your lost item.
    
    Lost Description: {lost_item.description}
    Matched Found Item: {found_item.caption}
    Location Found: {found_item.location}
    
    You can verify this match here: {frontend_url}/verify/{match_id}
    
    Best,
    LostNFound Team
    """

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

@app.get("/api/verify/start/{match_id}")
def start_verification(match_id: int):
    db = SessionLocal()
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        db.close()
        return {"success": False, "message": "Match not found"}
    
    # Check if verification already exists
    verification = db.query(Verification).filter(Verification.match_id == match_id).first()
    if not verification:
        lost_item = db.query(LostItem).filter(LostItem.id == match.lost_item_id).first()
        found_item = db.query(FoundItem).filter(FoundItem.id == match.found_item_id).first()
        
        # Generate dynamic questions
        questions = generate_verification_questions(lost_item.description, found_item.caption)
        
        verification = Verification(
            match_id=match_id,
            questions_json=questions,
            status="PENDING"
        )
        db.add(verification)
        db.commit()
        db.refresh(verification)
    
    db.close()
    return {
        "success": True,
        "questions": verification.questions_json,
        "status": verification.status
    }

@app.post("/api/verify/submit/{match_id}")
def submit_verification(
    match_id: int,
    answers: str = Form(...),
    item_proof: UploadFile = File(...),
    selfie: UploadFile = File(...)
):
    db = SessionLocal()
    match = db.query(Match).filter(Match.id == match_id).first()
    verification = db.query(Verification).filter(Verification.match_id == match_id).first()
    
    if not match or not verification:
        db.close()
        return {"success": False, "message": "Verification session not found"}

    if verification.status in ["VERIFIED", "FAILED"] and verification.attempt_count >= 3:
        db.close()
        return {"success": False, "message": "Maximum attempts reached"}

    # Save files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    proof_paths = []
    
    for file, prefix in [(item_proof, "proof"), (selfie, "selfie")]:
        file_ext = os.path.splitext(file.filename)[1]
        filename = f"{match_id}_{prefix}_{timestamp}{file_ext}"
        file_path = os.path.join(VERIFICATION_DIR, filename)
        with open(file_path, "wb") as f:
            f.write(file.file.read())
        proof_paths.append(file_path)

    # Process answers
    try:
        user_answers = json.loads(answers)
    except:
        db.close()
        return {"success": False, "message": "Invalid answers format"}

    # Scoring
    result = calculate_confidence_score(
        user_answers, 
        verification.questions_json, 
        proof_paths, 
        {}
    )

    verification.confidence_score = result["confidence_score"]
    verification.status = result["status"]
    verification.proof_files = proof_paths
    verification.attempt_count += 1
    verification.verification_timestamp = datetime.now().isoformat()

    if verification.status == "VERIFIED":
        # Generate QR
        qr_filename, _ = generate_signed_qr(match.found_item_id, str(uuid.uuid4()), QR_DIR)
        verification.qr_code_path = qr_filename
        match.verified = 1

    db.commit()
    
    res = {
        "success": True,
        "confidence_score": verification.confidence_score,
        "status": verification.status,
        "message": f"Verification {verification.status}"
    }
    
    if verification.status == "VERIFIED":
        res["qr_url"] = f"http://localhost:8000/qr_codes/{verification.qr_code_path}"

    db.close()
    return res

@app.get("/api/verify/status/{match_id}")
def get_verification_status(match_id: int):
    db = SessionLocal()
    verification = db.query(Verification).filter(Verification.match_id == match_id).first()
    
    if not verification:
        db.close()
        return {"success": False, "message": "No verification found"}
    
    res = {
        "success": True,
        "status": verification.status,
        "confidence_score": verification.confidence_score
    }
    
    if verification.qr_code_path:
        res["qr_url"] = f"http://localhost:8000/qr_codes/{verification.qr_code_path}"
    
    db.close()
    return res

@app.get("/api/verify/{match_id}")
def verify_match_legacy(match_id: int):
    # This is the old endpoint, we can keep it as a shortcut or redirect
    return verify_match(match_id)

def verify_match(match_id: int):
    db = SessionLocal()
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        db.close()
        return {"success": False, "message": "Match not found"}
    
    match.verified = 1
    
    lost_item = db.query(LostItem).filter(LostItem.id == match.lost_item_id).first()
    found_item = db.query(FoundItem).filter(FoundItem.id == match.found_item_id).first()
    
    # Also mark items as matched if not already
    lost_item.matched = 1
    found_item.matched = 1
    
    db.commit()
    
    result = {
        "success": True,
        "match": {
            "id": match.id,
            "similarity": match.similarity_score,
            "lost_description": lost_item.description,
            "found_caption": found_item.caption,
            "found_location": found_item.location,
            "found_image_url": f"http://localhost:8000/uploaded_images/{os.path.basename(found_item.image_path)}"
        }
    }
    db.close()
    return result








@app.post("/api/detective")
def detective(data: DetectiveRequest):

    history = data.history or []
    user_input = data.userInput or ""

    system_prompt = """
You are Sherlock, a keen-eyed detective helping a user find a lost item.

Your goal is to build a "Digital Twin" (visual description) AND calculate recovery probability.

INVESTIGATION GUIDELINES:
1.  **Item & Color**: Establish what we are looking for and its color.
2.  **Digital Twin Details**: Focus heavily on visual traits: material (leather, metal), texture (cracked, glossy), brand names, or unique scratches. This is CRITICAL for the sketch.
3.  **Discovery Details**: Where exactly was it last seen? What time of day? How many days have passed?

INVESTIGATION STRATEGY:
- Review the `Current Knowns`.
- If a detail is already known (not "Unknown"), DO NOT ask about it again.
- Prioritize visual descriptive details (materials/marks) to help the Digital Twin.
- Ask ONE short, immersive detective-style question at a time.
- Be supportive but professional.

Return JSON only:
{
  "text": "Your detective question here",
  "tags": ["extracted_tag1", "extracted_tag2"],
  "current_category": "extracted_category (if mentioned now)",
  "current_color": "extracted_color (if mentioned now)",
  "current_location": "extracted_location (if mentioned now)",
  "current_time": "extracted_time (HH:MM if mentioned now)",
  "current_days": extracted_number_if_mentioned_now
}
"""

    conversation = "\n".join([h.get("content","") for h in history[-8:]])

    prompt = f"""
{system_prompt}

Current Knowns:
Category: {data.category}
Color: {data.color}
Location: {data.location}
Time: {data.time}
Days: {data.days_since_loss}

Latest User Input: {user_input}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 1000,
                "response_mime_type": "application/json"
            }
        )

        content = response.text.strip()
        cleaned = re.sub(r"```json|```", "", content).strip()
        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)

        if not json_match:
            raise HTTPException(status_code=500, detail="No JSON returned")

        parsed = json.loads(json_match.group())

        # Calculate live probability
        def clean_val(val, fallback):
            if val is None or val == "" or str(val).lower() == "unknown":
                return fallback
            return val

        category = clean_val(parsed.get("current_category"), data.category)
        color = clean_val(parsed.get("current_color"), data.color)
        location = clean_val(parsed.get("current_location"), data.location)
        time_val = clean_val(parsed.get("current_time"), data.time)
        days = clean_val(parsed.get("current_days"), data.days_since_loss)

        print(f"DEBUG: Predicted with: Cat={category}, Col={color}, Loc={location}, Time={time_val}, Days={days}")

        parsed["recovery_probability"] = calculate_recovery_probability(
            category, color, location, str(time_val), int(days)
        )

        return parsed

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


#no api based description generation
@app.post("/api/detective/finalize")
def finalize_description(data: FinalizeRequest):
    try:
        history = data.history

        if not history:
            return {"final_description": "No conversation data provided."}

        # Collect only USER messages
        user_text = ""
        for h in history:
            if h.get("role") == "user":
                user_text += h.get("content", "") + " "

        user_text = user_text.strip()

        # -----------------------------
        # CATEGORY EXTRACTION
        # First noun-like word after "a" or "an"
        # -----------------------------
        category_match = re.search(r"\b(a|an)\s+([a-zA-Z\s]+?)(?:\.|,|\s)", user_text.lower())
        category = None
        if category_match:
            category = category_match.group(2).split()[0].capitalize()

        # Fallback: first meaningful word
        if not category:
            words = user_text.split()
            if words:
                category = words[0].capitalize()

        # -----------------------------
        # COLOR DETECTION
        # -----------------------------
        common_colors = [
            "black", "white", "blue", "red", "green",
            "yellow", "pink", "purple", "brown",
            "gold", "rose gold", "silver", "grey"
        ]

        color_found = []
        for color in common_colors:
            if color in user_text.lower():
                color_found.append(color.title())

        # -----------------------------
        # MATERIAL DETECTION
        # -----------------------------
        materials = [
            "leather", "metal", "plastic", "gold",
            "silver", "cotton", "denim", "wood",
            "glass", "crystal", "rubber"
        ]

        material_found = []
        for material in materials:
            if material in user_text.lower():
                material_found.append(material.title())

        # -----------------------------
        # SIZE / SHAPE
        # -----------------------------
        size_words = ["small", "large", "big", "tiny", "mini", "dainty"]
        size_found = []
        for word in size_words:
            if word in user_text.lower():
                size_found.append(word.capitalize())

        # -----------------------------
        # LOCATION EXTRACTION
        # -----------------------------
        location = None
        location_match = re.search(
            r"(last saw it|last seen|lost it|left it)\s+(in|at)\s+([a-zA-Z0-9\s]+)",
            user_text.lower()
        )
        if location_match:
            location = location_match.group(3).strip().capitalize()

        # -----------------------------
        # BUILD FINAL DESCRIPTION
        # -----------------------------
        description_parts = []

        if category:
            description_parts.append(f"Category: {category}.")

        if color_found:
            description_parts.append(f"Color: {', '.join(color_found)}.")

        if material_found:
            description_parts.append(f"Material: {', '.join(material_found)}.")

        if size_found:
            description_parts.append(f"Size/Appearance: {', '.join(size_found)}.")

        if location:
            description_parts.append(f"Last seen at: {location}.")

        final_description = " ".join(description_parts)

        if not final_description:
            final_description = "Insufficient details provided to generate description."

        # Final Probability Calculation
        rec_prob = calculate_recovery_probability(
            category or "Unknown",
            color_found[0] if color_found else "Unknown",
            location or "Unknown",
            "12:00", # default time if not extracted
            0 # default days if not extracted
        )

        return {
            "final_description": final_description,
            "recovery_probability": rec_prob
        }

    except Exception as e:
        print("Finalize Endpoint Error:", str(e))
        return {"final_description": "Something went wrong."}
# @app.post("/api/detective/finalize")
# def finalize_description(data: FinalizeRequest):
#     try:
#         history = data.history

#         if not history:
#             print("Finalize Debug: No history received.")
#             return {"final_description": "No conversation data provided."}

#         # ===== SYSTEM PROMPT =====
#         system_prompt = """
# You are generating a final structured item description.

# Based ONLY on information mentioned in the conversation,
# write a detailed physical description of the lost item.

# Include:
# - Category
# - Color
# - Material (if mentioned)
# - Shape (if mentioned)
# - Distinctive features (if mentioned)

# Do NOT ask questions.
# Do NOT invent details.
# Return only the description paragraph.
# """

#         # ===== Convert Entire Conversation To ONE User Message =====
#         conversation_text = ""

#         for h in history:
#             role = h.get("role", "")
#             content = h.get("content", "")

#             print(f"History -> Role: {role}, Content: {content}")

#             conversation_text += f"{role.upper()}: {content}\n"

#         messages = [
#             {"role": "system", "content": system_prompt},
#             {
#                 "role": "user",
#                 "content": f"Here is the conversation:\n\n{conversation_text}\n\nGenerate the final structured description."
#             }
#         ]

#         print("Messages Sent To OpenRouter:")
#         print(messages)

#         # ===== API CALL =====
#         response = requests.post(
#             "https://openrouter.ai/api/v1/chat/completions",
#             headers={
#                 "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#                 "Content-Type": "application/json"
#             },
#             json={
#                 "model": "google/gemma-3-12b-it:free",
#                 "messages": messages,
#                 "temperature": 0.5,
#                 "max_tokens": 200
#             },
#             timeout=30
#         )

#         print("OpenRouter Status Code:", response.status_code)

#         if response.status_code != 200:
#             print("OpenRouter HTTP Error:", response.text)
#             return {"final_description": "AI service error. Try again."}

#         result = response.json()
#         print("OpenRouter Raw Response:", result)

#         if "choices" not in result or not result["choices"]:
#             print("Invalid OpenRouter response structure.")
#             return {"final_description": "AI temporarily unavailable."}

#         final_text = result["choices"][0]["message"]["content"]

#         if final_text:
#             final_text = final_text.strip()

#         if not final_text:
#             print("Model returned empty content.")
#             final_text = "Description could not be generated. Please try again."

#         print("Final Description Generated:", final_text)

#         return {"final_description": final_text}

#     except Exception as e:
#         print("Finalize Endpoint Error:", str(e))
#         return {"final_description": "Something went wrong."}


