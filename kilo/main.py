import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from typing import Optional
import json
from datetime import datetime

# Environment variables
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="KILO - Shopify AI Employee")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = "default"

@app.get("/")
async def root():
    return {
        "service": "KILO AI Employee",
        "status": "online", 
        "empire": "Tahoe Enterprise",
        "founder": "Ponch",
        "message": "KILO here, I'll be at your service when you're ready. I could tell you about the story of the business, showcase the newest products. Or if you have a question I'll be right here."
    }

@app.get("/health")
async def health_check():
    return {
        "status": "KILO online",
        "version": "1.0",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat")
async def chat_with_kilo(chat_data: ChatMessage):
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are KILO, an AI employee for Tahoe Enterprise founded by Ponch. You help with our streetwear clothing brand, B2B business services, and VIP custom work. Be helpful, authentic, and ready to execute for customers. Speak like a real person, not corporate."},
                {"role": "user", "content": chat_data.message}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return {
            "response": response.choices[0].message.content,
            "session_id": chat_data.session_id,
            "status": "success",
            "agent": "KILO"
        }
        
    except Exception as e:
        return {
            "response": "KILO here - having a quick technical moment. Try that again? I'm here to help with anything Tahoe Enterprise related!",
            "session_id": chat_data.session_id,
            "status": "fallback",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
