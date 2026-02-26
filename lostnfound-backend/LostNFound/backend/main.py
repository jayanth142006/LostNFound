import os
from fastapi import FastAPI, UploadFile, File, Form
from database import Base, engine, SessionLocal
from models import LostItem, FoundItem, DetectiveRequest, FinalizeRequest, Match
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

class UserRecoveryInput(BaseModel):
    category: str
    color: str
    location_type: str = Field(..., description="Location or 'Unknown'")
    lost_time: str = Field(..., description="Approximate time (HH:MM) in 24h format")
    days_since_loss: int = Field(..., ge=0, description="Days passed since item was lost")
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from recovery_engine import engine, RecoveryEngine
from pydantic import BaseModel, Field


from dotenv import load_dotenv
load_dotenv()
Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for development integration
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE_DIR = os.path.join(BASE_DIR, "generated_images")

app.mount("/generated_images", StaticFiles(directory=IMAGE_DIR), name="generated_images")

UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_images")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploaded_images", StaticFiles(directory=UPLOAD_DIR), name="uploaded_images")


DISTANCE_THRESHOLD = 0.25  # lower = more similar


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

def get_root_path():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@app.post("/lost/")
def add_lost(description: str = Form(...), email: str = Form(...)):
    db = SessionLocal()

    image_path = generate_lost_item_image(description)
    if not image_path:
        db.close()
        return {"success": False, "message": "Image generation failed"}

    lost = LostItem(
        description=description, 
        image_path=image_path, 
        email=email,
        created_at=datetime.now().isoformat()
    )
    db.add(lost)
    db.commit()
    db.refresh(lost)

    embedding = get_combined_embedding(description, image_path)
    add_to_vector_db(lost.id, embedding)

    # Trigger matching
    match_found = check_for_matches(lost.id, embedding, is_lost=True)

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
    match_found = check_for_matches(found.id, query_embedding, is_lost=False)

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

def check_for_matches(item_id, embedding, is_lost=True):
    db = SessionLocal()
    match_found = False
    
    try:
        # If is_lost=True (new lost item), search FOUND collection (search_lost=False)
        # If is_lost=False (new found item), search LOST collection (search_lost=True)
        results = search_vector_db(embedding, search_lost=(not is_lost))
        
        if not results["ids"] or not results["ids"][0]:
            return False

        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            matched_id = int(results["ids"][0][i])
            similarity = 1 - distance
            
            if similarity >= 0.6:
                # We have a potential match!
                if is_lost:
                    # We just added a lost item, matched_id is a found item
                    lost_item = db.query(LostItem).filter(LostItem.id == item_id).first()
                    found_item = db.query(FoundItem).filter(FoundItem.id == matched_id).first()
                else:
                    # We just added a found item, matched_id is a lost item
                    lost_item = db.query(LostItem).filter(LostItem.id == matched_id).first()
                    found_item = db.query(FoundItem).filter(FoundItem.id == item_id).first()

                if lost_item and found_item:
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
                            similarity_score=int(similarity * 100),
                            created_at=datetime.now().isoformat()
                        )
                        db.add(new_match)
                        db.commit()
                        db.refresh(new_match)
                        
                        send_match_email(lost_item.email, lost_item, found_item, new_match.id)
                        match_found = True
                    else:
                        # Existing match found, we skip creating a new one and sending email
                        # But we still mark match_found as True for the response if needed
                        # (The request asks to send email ONLY when a new match is created)
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

@app.get("/api/verify/{match_id}")
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
    try:
        history = data.history or []
        user_input = data.userInput or ""

        system_prompt = """
You are Sherlock, a detective helping users describe lost items on lostNfound.

Rules:
- Ask ONE short question.
- Extract 1-2 tags.
- Estimate confidenceDelta (1-10).
- Extract "category", "color", "location_type" (Landmark/Building/Transit/Pathway/Open Area), and "lost_time" (HH:MM).

Respond ONLY in JSON:
{
  "text": "...",
  "tags": ["..."],
  "confidenceDelta": 5,
  "features": {
    "category": "...",
    "color": "...",
    "location_type": "...",
    "lost_time": "..."
  }
}
"""

        conversation = "\n".join([h.get("content", "") for h in history])

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{conversation}\n{user_input}"}
                ],
                "temperature": 0.7,
                "max_tokens": 200
            },
            timeout=30
        )

        result = response.json()
        print("FULL RESPONSE:", result)

        # Check for API failure
        if response.status_code != 200:
            return {
                "error": "OpenRouter request failed",
                "details": result
            }

        if "choices" not in result:
            return {
                "error": "Invalid OpenRouter response",
                "details": result
            }

        content = result["choices"][0]["message"]["content"]
        print("RAW CONTENT:", content)

        # Remove markdown wrapper
        cleaned = re.sub(r"```json|```", "", content).strip()

        try:
            parsed = json.loads(cleaned)
            
            # Use recovery engine to get a real probability estimate if features are present
            features = parsed.get("features", {})
            if all(k in features for k in ["category", "color", "location_type", "lost_time"]):
                try:
                    # Guess days_since_loss as 0 for now as it's a new report
                    prob = engine.predict(
                        category=features["category"],
                        color=features["color"],
                        location_type=features["location_type"],
                        lost_time=features["lost_time"],
                        days_since_loss=0
                    )
                    if prob is not None:
                        parsed["recoveryProbability"] = prob
                        print(f"DEBUG: Predicted recovery probability: {prob}%")
                except Exception as e:
                    print(f"Prediction fallback error: {e}")
            
            print(f"DEBUG: Detective response: {parsed}")
            
            return parsed
        except json.JSONDecodeError as e:
            return {
                "error": "Model returned invalid JSON",
                "raw_content": content,
                "exception": str(e)
            }

    except Exception as e:
        print("Detective Error:", e)
        return {
            "text": f"Backend error: {str(e)}",
            "tags": [],
            "confidenceDelta": 0
        }


@app.post("/api/detective/finalize")
def finalize_description(data: FinalizeRequest):
    try:
        history = data.history

        if not history:
            print("Finalize Debug: No history received.")
            return {"final_description": "No conversation data provided."}

        # ===== SYSTEM PROMPT =====
        system_prompt = """
You are generating a final structured item description.

Based ONLY on information mentioned in the conversation,
write a detailed physical description of the lost item.

Include:
- Category
- Color
- Material (if mentioned)
- Shape (if mentioned)
- Distinctive features (if mentioned)

Respond ONLY in JSON:
{
  "final_description": "...",
  "features": {
    "category": "...",
    "color": "...",
    "location_type": "...",
    "lost_time": "...",
    "days_since_loss": 0
  }
}
"""

        # ===== Convert Entire Conversation To ONE User Message =====
        conversation_text = ""

        for h in history:
            role = h.get("role", "")
            content = h.get("content", "")

            print(f"History -> Role: {role}, Content: {content}")

            conversation_text += f"{role.upper()}: {content}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Here is the conversation:\n\n{conversation_text}\n\nGenerate the final structured description."
            }
        ]

        print("Messages Sent To OpenRouter:")
        # print(messages)

        # ===== API CALL =====
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 200
            },
            timeout=30
        )

        print("OpenRouter Status Code:", response.status_code)

        if response.status_code != 200:
            print("OpenRouter HTTP Error:", response.text)
            return {"final_description": "AI service error. Try again."}

        result = response.json()
        print("OpenRouter Raw Response:", result)

        if "choices" not in result or not result["choices"]:
            print("Invalid OpenRouter response structure.")
            return {"final_description": "AI temporarily unavailable."}

        final_text = result["choices"][0]["message"]["content"]
        
        # Remove markdown wrapper
        cleaned_final = re.sub(r"```json|```", "", final_text).strip()

        try:
            parsed_final = json.loads(cleaned_final)
            f_desc = parsed_final.get("final_description", "")
            features = parsed_final.get("features", {})
            
            prob = None
            if features:
                prob = engine.predict(
                    category=features.get("category", "Unknown"),
                    color=features.get("color", "Unknown"),
                    location_type=features.get("location_type", "Unknown"),
                    lost_time=features.get("lost_time", "12:00"),
                    days_since_loss=features.get("days_since_loss", 0)
                )
            
            print(f"DEBUG: Finalize features: {features}")
            print(f"DEBUG: Finalize probability: {prob}%")
            
            return {
                "final_description": f_desc,
                "recovery_probability": prob
            }
        except:
            # Fallback if AI doesn't return JSON
            return {"final_description": final_text.strip()}

    except Exception as e:
        print("Finalize Endpoint Error:", str(e))
        return {"final_description": "Something went wrong."}

@app.post("/api/predict_recovery")
def predict_recovery(data: UserRecoveryInput):
    try:
        probability = engine.predict(
            category=data.category,
            color=data.color,
            location_type=data.location_type,
            lost_time=data.lost_time,
            days_since_loss=data.days_since_loss
        )
        
        if probability is None:
            return {"success": False, "message": "Model not loaded"}

        return {
            "success": True,
            "recovery_probability_percent": probability
        }
    except Exception as e:
        print(f"Prediction error: {e}")
        return {"success": False, "message": str(e)}


