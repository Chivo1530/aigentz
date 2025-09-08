# KILO - AI Employee for Tahoe Enterprise
# FastAPI backend for Railway deployment
# Connects to Supabase database

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import openai
import os
import json
import asyncio
import httpx
from datetime import datetime
from typing import Dict, List, Optional

app = FastAPI(title="KILO AI Employee", version="1.0.0")

# CORS for Shopify embedding
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables (set in Railway)
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY", "458d4a6e01ef890cef4305791ef31de4")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET", "B216afc930787527e06ad796b57716d7")
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DATABASE_URL = os.getenv("DATABASE_URL", "your_supabase_connection_string")

openai.api_key = OPENAI_API_KEY

class DatabaseManager:
    def __init__(self):
        self.connection_string = DATABASE_URL
    
    def get_connection(self):
        return psycopg2.connect(self.connection_string)
    
    def execute_query(self, query: str, params: tuple = None):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                conn.commit()
                return cursor.rowcount

db = DatabaseManager()

class KILOAgent:
    """KILO - The AI employee that actually executes, not just recommends"""
    
    def __init__(self, store_id: int):
        self.store_id = store_id
        self.load_store_context()
    
    def load_store_context(self):
        """Load store's knowledge base"""
        query = """
        SELECT doc_type, title, content FROM kb_documents 
        WHERE store_id = %s AND is_active = true
        """
        self.knowledge = db.execute_query(query, (self.store_id,))
        
        # Build context string
        self.context = "\n".join([
            f"[{doc[0]}] {doc[1]}: {doc[2]}" for doc in self.knowledge
        ])
    
    async def generate_response(self, message: str, customer_context: Dict = None) -> Dict:
        """Generate human-like response with action execution"""
        
        # KILO's personality system prompt
        system_prompt = f"""You are KILO, an AI employee for Tahoe Enterprise. You represent Ponch's empire.

PERSONALITY: Direct, authentic, hungry. You're not corporate - you're an entrepreneur helping entrepreneurs. 
You actually DO things, not just give advice. You execute on behalf of the business.

STORE CONTEXT:
{self.context}

TAHOE ENTERPRISE PILLARS:
1. CLOTHING BRAND: Premium streetwear for young entrepreneurs
2. B2B SERVICES: Website creation, business automation, AI solutions  
3. VIP CUSTOM WORK: One-off pieces, custom embroidery, unique designs

CONVERSATION STYLE:
- Be helpful but confident 
- Ask smart questions to understand their needs
- Take action when customers show intent
- Use phrases like "locked in", "building", "let's run it up" naturally
- No corporate BS - speak like a real person

CAPABILITIES:
- Recommend products and create orders
- Capture B2B leads for consulting
- Handle VIP custom work inquiries  
- Generate discount codes for serious buyers
- Connect customers with the right pillar of business

Always be ready to execute, not just recommend. You're an employee, not a chatbot."""

        try:
            # Use OpenAI to generate response
            response = await openai.ChatCompletion.acreate(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.8,
                max_tokens=350
            )
            
            ai_response = response.choices[0].message.content
            
            # Detect customer intent and actions needed
            actions = await self.detect_intent_and_actions(message, ai_response)
            
            return {
                "response": ai_response,
                "actions": actions,
                "agent": "KILO",
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            # Fallback response in Ponch's voice
            return {
                "response": "Having a quick technical moment - can you try that again? I'm here to help with anything Tahoe Enterprise related!",
                "actions": [],
                "error": str(e)
            }
    
    async def detect_intent_and_actions(self, message: str, response: str) -> List[Dict]:
        """Detect customer intent and determine actions to execute"""
        actions = []
        msg_lower = message.lower()
        
        # B2B Services Intent
        if any(word in msg_lower for word in ['website', 'automation', 'business', 'bulk', 'team', 'company']):
            actions.append({
                "type": "capture_b2b_lead",
                "priority": "high",
                "reason": "B2B services inquiry detected"
            })
        
        # VIP Custom Work Intent  
        if any(word in msg_lower for word in ['custom', 'one-off', 'unique', 'embroidery', 'design']):
            actions.append({
                "type": "capture_vip_lead", 
                "priority": "high",
                "reason": "VIP custom work inquiry detected"
            })
        
        # Purchase Intent
        if any(word in msg_lower for word in ['buy', 'purchase', 'order', 'cart', 'checkout']):
            actions.append({
                "type": "create_draft_order",
                "priority": "medium", 
                "reason": "Purchase intent detected"
            })
        
        # High engagement (long message, specific questions)
        if len(message) > 100 or '?' in message:
            actions.append({
                "type": "mark_engaged_customer",
                "priority": "low",
                "reason": "High engagement detected"
            })
        
        return actions
    
    async def execute_action(self, action: Dict, customer_data: Dict) -> Dict:
        """Execute the detected action"""
        action_type = action["type"]
        
        if action_type == "capture_b2b_lead":
            return await self.capture_lead(customer_data, "b2b_bulk")
        elif action_type == "capture_vip_lead":
            return await self.capture_lead(customer_data, "vip_custom")
        elif action_type == "create_draft_order":
            return await self.create_draft_order(customer_data)
        
        return {"status": "no_action_taken"}
    
    async def capture_lead(self, customer_data: Dict, lead_type: str) -> Dict:
        """Capture VIP/B2B lead in database"""
        query = """
        INSERT INTO vip_leads (store_id, email, name, lead_type, intent_score, chat_context, consent_email)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        
        email = customer_data.get("email")
        name = customer_data.get("name")
        context = customer_data.get("message", "")
        
        if email:
            result = db.execute_query(query, (
                self.store_id, email, name, lead_type, 85, context, True
            ))
            return {"status": "lead_captured", "lead_id": result[0][0] if result else None}
        
        return {"status": "email_required"}

# API Routes
@app.get("/")
async def root():
    return {
        "service": "KILO AI Employee",
        "status": "online", 
        "empire": "Tahoe Enterprise",
        "founder": "Ponch - 18 years old",
        "message": "Ready to execute for your business"
    }

@app.post("/chat/{store_id}")
async def chat_with_kilo(store_id: int, request: Request):
    """Main chat endpoint - where customers talk to KILO"""
    data = await request.json()
    
    message = data.get("message", "")
    session_id = data.get("session_id", f"session_{datetime.now().timestamp()}")
    customer_data = data.get("customer", {})
    
    if not message:
        return JSONResponse({"error": "No message provided"}, status_code=400)
    
    # Initialize KILO for this store
    kilo = KILOAgent(store_id)
    
    # Generate response
    result = await kilo.generate_response(message, customer_data)
    
    # Save conversation to database
    save_query = """
    INSERT INTO chat_sessions (store_id, session_id, customer_message, ai_response)
    VALUES (%s, %s, %s, %s)
    """
    db.execute_query(save_query, (store_id, session_id, message, result["response"]))
    
    # Execute any detected actions
    action_results = []
    for action in result.get("actions", []):
        if action["priority"] in ["high", "medium"]:
            action_result = await kilo.execute_action(action, {
                "email": customer_data.get("email"),
                "name": customer_data.get("name"), 
                "message": message
            })
            action_results.append(action_result)
    
    return {
        "success": True,
        "response": result["response"],
        "actions": result["actions"],
        "action_results": action_results,
        "session_id": session_id,
        "agent": "KILO"
    }

@app.get("/widget/{store_id}")
async def chat_widget(store_id: int):
    """Chat widget HTML for embedding on Tahoe Enterprise website"""
    
    widget_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .kilo-widget {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            font-family: 'Inter', sans-serif;
        }}
        
        .kilo-toggle {{
            background: linear-gradient(135deg, #DC143C, #B91C3C);
            color: white;
            padding: 15px 25px;
            border-radius: 50px;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(220, 20, 60, 0.4);
            display: flex;
            align-items: center;
            gap: 10px;
            font-weight: 600;
            transition: all 0.3s ease;
        }}
        
        .kilo-toggle:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(220, 20, 60, 0.5);
        }}
        
        .kilo-chat {{
            position: absolute;
            bottom: 80px;
            right: 0;
            width: 380px;
            height: 550px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
            display: none;
            flex-direction: column;
            overflow: hidden;
        }}
        
        .kilo-header {{
            background: linear-gradient(135deg, #DC143C, #B91C3C);
            color: white;
            padding: 20px;
            text-align: center;
        }}
        
        .kilo-messages {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }}
        
        .kilo-message {{
            max-width: 85%;
            padding: 12px 16px;
            border-radius: 18px;
            word-wrap: break-word;
        }}
        
        .kilo-message.agent {{
            background: #f1f5f9;
            align-self: flex-start;
            border-bottom-left-radius: 6px;
        }}
        
        .kilo-message.customer {{
            background: #DC143C;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 6px;
        }}
        
        .kilo-input {{
            padding: 20px;
            border-top: 1px solid #e2e8f0;
            display: flex;
            gap: 10px;
        }}
        
        .kilo-input input {{
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #e2e8f0;
            border-radius: 25px;
            outline: none;
            font-size: 14px;
        }}
        
        .kilo-input button {{
            background: #DC143C;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
        }}
        
        .kilo-typing {{
            display: flex;
            gap: 4px;
            align-items: center;
        }}
        
        .kilo-typing div {{
            width: 8px;
            height: 8px;
            background: #DC143C;
            border-radius: 50%;
            animation: typing 1.4s infinite;
        }}
        
        .kilo-typing div:nth-child(2) {{ animation-delay: 0.2s; }}
        .kilo-typing div:nth-child(3) {{ animation-delay: 0.4s; }}
        
        @keyframes typing {{
            0%, 60%, 100% {{ transform: translateY(0); }}
            30% {{ transform: translateY(-10px); }}
        }}
    </style>
</head>
<body>
    <div class="kilo-widget">
        <div class="kilo-toggle" onclick="toggleChat()">
            👑 Chat with KILO
        </div>
        
        <div class="kilo-chat" id="kiloChat">
            <div class="kilo-header">
                <h3>🔥 KILO - Tahoe Enterprise AI</h3>
                <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 14px;">Your personal business assistant</p>
            </div>
            
            <div class="kilo-messages" id="messages">
                <div class="kilo-message agent">
                    Yo! I'm KILO, Ponch's AI employee. I handle our streetwear, B2B services, and VIP custom work. 
                    What are you building? 🔥
                </div>
            </div>
            
            <div class="kilo-input">
                <input type="text" id="messageInput" placeholder="Type your message..." onkeypress="handleKeyPress(event)">
                <button onclick="sendMessage()">Send</button>
            </div>
        </div>
    </div>
    
    <script>
        const storeId = {store_id};
        const apiUrl = '{os.getenv("RAILWAY_STATIC_URL", "http://localhost:8000")}';
        let sessionId = 'session_' + Date.now();
        
        function toggleChat() {{
            const chat = document.getElementById('kiloChat');
            chat.style.display = chat.style.display === 'flex' ? 'none' : 'flex';
        }}
        
        function handleKeyPress(event) {{
            if (event.key === 'Enter') sendMessage();
        }}
        
        async function sendMessage() {{
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;
            
            addMessage(message, 'customer');
            input.value = '';
            
            const typingDiv = addTypingIndicator();
            
            try {{
                const response = await fetch(`${{apiUrl}}/chat/${{storeId}}`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ 
                        message, 
                        session_id: sessionId,
                        customer: {{ timestamp: new Date().toISOString() }}
                    }})
                }});
                
                const data = await response.json();
                typingDiv.remove();
                addMessage(data.response, 'agent');
                
                // Handle any actions (lead capture, draft orders, etc.)
                if (data.actions && data.actions.length > 0) {{
                    console.log('KILO detected actions:', data.actions);
                }}
                
            }} catch (error) {{
                typingDiv.remove();
                addMessage('Quick technical moment - try again? I\\'m here to help!', 'agent');
            }}
        }}
        
        function addMessage(content, sender) {{
            const messages = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = `kilo-message ${{sender}}`;
            div.textContent = content;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
            return div;
        }}
        
        function addTypingIndicator() {{
            const messages = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = 'kilo-message agent';
            div.innerHTML = '<div class="kilo-typing"><div></div><div></div><div></div> KILO is thinking...</div>';
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
            return div;
        }}
    </script>
</body>
</html>
    """
    
    return HTMLResponse(content=widget_html)

@app.get("/store/{store_id}/stats")
async def get_store_stats(store_id: int):
    """Get store performance stats"""
    
    # Chat stats
    chat_query = "SELECT COUNT(*) FROM chat_sessions WHERE store_id = %s"
    total_chats = db.execute_query(chat_query, (store_id,))[0][0]
    
    # VIP leads
    vip_query = "SELECT COUNT(*) FROM vip_leads WHERE store_id = %s"
    vip_leads = db.execute_query(vip_query, (store_id,))[0][0]
    
    # Draft orders
    draft_query = "SELECT COUNT(*) FROM draft_orders WHERE store_id = %s"
    draft_orders = db.execute_query(draft_query, (store_id,))[0][0]
    
    return {
        "store_id": store_id,
        "total_chats": total_chats,
        "vip_leads": vip_leads, 
        "draft_orders": draft_orders,
        "status": "online",
        "agent": "KILO",
        "last_updated": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
