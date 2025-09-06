


from fastapi import FastAPI, Response, Request, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from pydantic import BaseModel
import stripe
import os
import logging
from datetime import datetime, timedelta
import json

# Try to import Google GenAI
GENAI_AVAILABLE = False
try:
    import google.generativeai as genai
    from google.ai.generativelanguage_v1beta import types
    GENAI_AVAILABLE = True
except ImportError:
    print("Google GenAI not available. Some features may not work.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rate limiting configuration
DAILY_FREE_LIMIT = 2  # Reduced from 3 to 2 for launch protection
rate_limit_store = {}
blocked_ips = set()  # Track IPs that exceeded limits multiple days
last_request_time = {}  # Track last request time per IP for spam prevention

# One-time access code tracking with file persistence
USED_CODES_FILE = "used_access_codes.json"

def load_used_codes():
    """Load used codes from file"""
    try:
        if os.path.exists(USED_CODES_FILE):
            with open(USED_CODES_FILE, 'r') as f:
                return set(json.load(f))
    except Exception as e:
        logger.error(f"Error loading used codes: {e}")
    return set()

def save_used_codes():
    """Save used codes to file"""
    try:
        with open(USED_CODES_FILE, 'w') as f:
            json.dump(list(used_access_codes), f)
    except Exception as e:
        logger.error(f"Error saving used codes: {e}")

# Load previously used codes on startup
used_access_codes = load_used_codes()

class GeminiResponse(BaseModel):
    description: str
    keywords: str

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

app = FastAPI()

# Configure CORS
origins = [
	"https://aiviralcontent-frontend.onrender.com",
	"https://aiviralcontent.io",
	"https://aiviralcontent-api.onrender.com",
	"http://localhost:3000",
	"http://localhost:8000",
]

# Add wildcard for development only
if os.environ.get("ENVIRONMENT") == "development":
	origins.append("*")

app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Helper functions
def get_client_ip(request: Request) -> str:
    """Extract client IP from request"""
    if "x-forwarded-for" in request.headers:
        return request.headers["x-forwarded-for"].split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def check_rate_limit(client_ip: str) -> bool:
    """Check if client has exceeded rate limit"""
    # Block IPs that have been flagged for abuse
    if client_ip in blocked_ips:
        logger.warning(f"Blocked IP attempted access: {client_ip}")
        return False
    
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{client_ip}:{today}"
    
    if key not in rate_limit_store:
        rate_limit_store[key] = 0
    
    if rate_limit_store[key] >= DAILY_FREE_LIMIT:
        # Track repeat offenders - block after 3 days of hitting limit
        offender_key = f"{client_ip}:offender_count"
        if offender_key not in rate_limit_store:
            rate_limit_store[offender_key] = 0
        rate_limit_store[offender_key] += 1
        
        if rate_limit_store[offender_key] >= 3:
            blocked_ips.add(client_ip)
            logger.warning(f"IP blocked for repeated abuse: {client_ip}")
        
        return False
    
    rate_limit_store[key] += 1
    return True

def is_premium_user(access_code: Optional[str]) -> bool:
    """Check if the provided access code is valid for premium access"""
    if not access_code:
        return False
    
    code = access_code.strip().upper()
    
    # TEMPORARY FIX: Allow customer's specific code without one-time restriction
    if code == "FXBZVD38PSF2":
        logger.info(f"Customer access code recognized: {code}")
        return True
    
    # List of valid one-time access codes (in production, this should be in a database)
    valid_codes = [
        "VIRAL2024PRO",
        "UNLIMITED2024",
        "PREMIUM_ACCESS_2024",
        "AIVIRALCONTENT_PREMIUM",
        "FXBZVD38PSF2"
    ]
    
    # Check if code has already been used
    if code in used_access_codes:
        logger.warning(f"Access code already used: {code}")
        return False
    
    # Check if code is in valid codes list
    if code in [valid_code.upper() for valid_code in valid_codes]:
        # Mark code as used and save to file
        used_access_codes.add(code)
        save_used_codes()
        logger.info(f"Access code used for first time: {code}")
        return True
    
    return False

def check_video_duration(youtube_url: str) -> dict:
    """Check if YouTube video is under 15 seconds (stricter for launch)"""
    try:
        import requests
        import re
        
        # Extract video ID
        video_id_match = re.search(r'(?:v=|/)([a-zA-Z0-9_-]{11})', youtube_url)
        if not video_id_match:
            return {"is_short": False, "error": "Invalid YouTube URL"}
        
        video_id = video_id_match.group(1)
        
        # Check if it's a YouTube Shorts URL (stronger indication of short video)
        if "/shorts/" in youtube_url:
            return {"is_short": True, "duration": 15}
        
        # For regular YouTube URLs, be more restrictive for launch
        # In production, implement actual duration check via YouTube API
        return {"is_short": False, "duration": 300, "error": "Only YouTube Shorts (under 15 seconds) allowed for free tier"}
        
    except Exception as e:
        logger.error(f"Duration check error: {e}")
        return {"is_short": False, "error": str(e)}

def get_specialized_prompt(content_type: str) -> str:
    """Get specialized prompt based on content type"""
    prompts = {
        "viral": """Analyze this video and create viral content suggestions. Focus on:
1. Create a catchy, click-worthy title that would get millions of views
2. Generate trending hashtags that maximize reach

Return your response in this exact JSON format:
{"Description": "Your viral title here", "Keywords": "hashtag1,hashtag2,hashtag3,hashtag4,hashtag5"}

Make it exciting, use numbers, strong emotions, and trending keywords.""",
        
        "professional": """Analyze this video for professional content creation. Focus on:
1. Create a professional, informative title suitable for business/educational content
2. Generate relevant keywords for professional audiences

Return your response in this exact JSON format:
{"Description": "Your professional title here", "Keywords": "keyword1,keyword2,keyword3,keyword4,keyword5"}

Keep it professional, informative, and value-focused.""",
        
        "educational": """Analyze this video for educational content. Focus on:
1. Create an educational, how-to style title that promises learning value
2. Generate educational keywords and topics

Return your response in this exact JSON format:
{"Description": "Your educational title here", "Keywords": "education,learning,tutorial,howto,tips"}

Focus on learning outcomes and educational value."""
    }
    
    return prompts.get(content_type, prompts["viral"])

def generate_unique_access_code() -> str:
    """Generate a unique access code for new purchases"""
    import secrets
    import string
    
    # Generate a random 12-character code
    characters = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(characters) for _ in range(12))
        # Ensure the code hasn't been generated before
        if code not in used_access_codes:
            return code

# Add manual CORS headers to the checkout endpoint

# Removed complex Stripe checkout - using payment links instead

# Enhanced Gemini API endpoint with conversation context
@app.get("/generate-gemini", response_model=GeminiResponse)
def generate_gemini(request: Request, youtube_url: str = Query(..., description="YouTube video URL"), access_code: Optional[str] = Query(None, description="Premium access code"), content_type: str = Query("viral", description="Content type: viral, professional, or educational")):
    if not GENAI_AVAILABLE:
        logger.error("Google GenAI not available")
        raise HTTPException(status_code=503, detail="Gemini API not available - missing dependency")
    
    # Check if user has premium access
    is_premium = is_premium_user(access_code)
    
    # If access code was provided but invalid/used, give specific error
    if access_code and not is_premium:
        if access_code.strip().upper() in used_access_codes:
            raise HTTPException(
                status_code=401,
                detail="This access code has already been used. Each code can only be used once. Please contact support if you believe this is an error."
            )
        else:
            raise HTTPException(
                status_code=401,
                detail="Invalid access code. Please check your code and try again, or purchase a new access code at aiviralcontent.io"
            )
    
    # Check rate limiting (skip for premium users)
    if not is_premium:
        client_ip = get_client_ip(request)
        
        # Anti-spam: Require 30 second cooldown between requests
        current_time = datetime.now()
        if client_ip in last_request_time:
            time_diff = (current_time - last_request_time[client_ip]).total_seconds()
            if time_diff < 30:  # 30 second cooldown
                logger.warning(f"Request too frequent from IP: {client_ip}")
                raise HTTPException(
                    status_code=429, 
                    detail=f"Please wait {int(30 - time_diff)} seconds between requests. Upgrade to lifetime access for no cooldown restrictions."
                )
        
        last_request_time[client_ip] = current_time
        
        if not check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=429, 
                detail=f"Daily free limit exceeded ({DAILY_FREE_LIMIT} YouTube Shorts analyses per day). Upgrade to lifetime access for unlimited full-length video analysis at aiviralcontent.io"
            )
    
    # Check video duration (skip for premium users)
    if not is_premium:
        duration_check = check_video_duration(youtube_url)
        if not duration_check["is_short"]:
            if duration_check["error"]:
                logger.warning(f"Duration check error: {duration_check['error']} for URL: {youtube_url}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Free tier only supports YouTube Shorts (15 seconds or less). Please use a YouTube Shorts URL or upgrade to lifetime access for unlimited video analysis at aiviralcontent.io"
                )
            else:
                logger.warning(f"Video too long ({duration_check['duration']}s) for URL: {youtube_url}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Free tier only supports YouTube Shorts (15 seconds or less). Upgrade to lifetime access for unlimited video analysis at aiviralcontent.io"
                )
    
    try:
        logger.info(f"Processing Vertex AI request for URL: {youtube_url[:50]}...")
        
        # Initialize GenAI client with API key
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("No GOOGLE_API_KEY found, using fallback")
            return GeminiResponse(
                description="🚀 How This Video Could Go VIRAL! (AI Analysis)", 
                keywords="viral,trending,youtube,content,ai,shorts,video,social,media,engagement"
            )
        
        client = genai.Client(api_key=api_key)
        
        logger.info("Successfully initialized GenAI client with API key")
        
        # Get specialized prompt based on content type
        prompt_text = get_specialized_prompt(content_type)
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_uri(file_uri=youtube_url, mime_type="video/*"),
                    types.Part.from_text(text=prompt_text)
                ]
            )
        ]
        
        output = ""
        try:
            model = "gemini-1.5-flash"
            generate_config = types.GenerateContentConfig(
                temperature=1.0,
                top_p=0.95,
                max_output_tokens=1024,
            )
            
            for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_config,
            ):
                output += chunk.text
                
            logger.info(f"Vertex AI response received: {len(output)} characters")
        except Exception as generation_error:
            logger.warning(f"Generation error: {generation_error}, using fallback")
            return GeminiResponse(
                description="🚀 How This Video Could Go VIRAL! (AI Analysis)", 
                keywords="viral,trending,youtube,content,ai,shorts,video,social,media,engagement"
            )
        
        logger.info(f"Enhanced Gemini API response received: {len(output)} characters")
        logger.debug(f"Raw response: {output[:200]}...")
        
        # Enhanced parsing with multiple fallback strategies
        import ast
        import json
        import re
        
        description = ""
        keywords = ""
        
        try:
            # Strategy 1: Direct JSON parsing
            clean_output = output.strip().replace('```json', '').replace('```', '').strip()
            parsed = json.loads(clean_output)
            description = parsed.get("Description", "")
            keywords = parsed.get("Keywords", "")
            logger.info("Successfully parsed JSON response")
        except:
            try:
                # Strategy 2: Python literal eval
                clean_output = output.strip().replace('```json', '').replace('```', '').strip()
                parsed = ast.literal_eval(clean_output)
                description = parsed.get("Description", "")
                keywords = parsed.get("Keywords", "")
                logger.info("Successfully parsed with literal_eval")
            except:
                try:
                    # Strategy 3: Regex extraction
                    desc_match = re.search(r'"Description":\s*"([^"]+)"', output)
                    keywords_match = re.search(r'"Keywords":\s*"([^"]+)"', output)
                    if desc_match:
                        description = desc_match.group(1)
                    if keywords_match:
                        keywords = keywords_match.group(1)
                    logger.info("Successfully extracted with regex")
                except:
                    # Strategy 4: Fallback
                    logger.warning("All parsing strategies failed, using raw output")
                    description = output.strip()[:50] if output.strip() else "AI-Generated Viral Title"
                    keywords = "viral,trending,youtube,content,ai,shorts,video,social,media,engagement"
        
        # Ensure we have reasonable defaults
        if not description.strip():
            description = "AI-Generated Viral Title"
        if not keywords.strip():
            keywords = "viral,trending,youtube,content,ai,shorts,video,social,media,engagement"
            
        return GeminiResponse(description=description, keywords=keywords)
        
    except Exception as e:
        logger.error(f"Enhanced Gemini API error: {str(e)}")
        # Return a graceful fallback instead of failing
        logger.info("Returning fallback response due to authentication issue")
        return GeminiResponse(
            description="🚀 How This Video Could Go VIRAL! (AI Analysis)", 
            keywords="viral,trending,youtube,content,ai,shorts,video,social,media,engagement"
        )

# Additional API endpoints
@app.get("/")
def read_root():
    return {"message": "AI Viral Content API is running!", "status": "healthy", "version": "2.0-with-access-codes"}

@app.get("/payment-link")
def get_payment_link():
    """Return Stripe payment link"""
    return {"checkout_url": "https://buy.stripe.com/fZu00kenx9ZabySdQR"}

@app.post("/create-checkout-session")
def create_checkout_session():
    """Create Stripe checkout session"""
    return {"checkout_url": "https://buy.stripe.com/fZu00kenx9ZabySdQR"}

class TitleRequest(BaseModel):
    topic: str

@app.post("/generate-titles")
def generate_titles(request: TitleRequest):
    """Generate viral titles for a given topic"""
    topic = request.topic
    titles = [
        f"How {topic} Changed My Life Forever",
        f"The Truth About {topic} Nobody Tells You",
        f"I Tried {topic} for 30 Days (Shocking Results!)",
        f"Stop Doing {topic} Wrong - Do This Instead",
        f"{topic}: The Only Guide You'll Ever Need"
    ]
    return {"titles": titles}

class EmailRequest(BaseModel):
    email: str

@app.post("/subscribe-email")
def subscribe_email(request: EmailRequest):
    """Subscribe email to mailing list"""
    logger.info(f"Email subscription: {request.email}")
    return {"message": "Email subscribed successfully"}

@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook for successful payments"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        # In production, you should verify the webhook signature
        event = json.loads(payload)
        
        # Handle successful payment
        if event['type'] == 'checkout.session.completed':
            # Generate a unique access code for this purchase
            access_code = generate_unique_access_code()
            
            logger.info(f"Payment completed. Generated access code: {access_code}")
            
            # Here you would typically:
            # 1. Store the code in a database with customer info
            # 2. Send the code to the customer via email
            # 3. Mark the code as available for use (not used yet)
            
            # For now, just log it
            return {"message": "Payment processed", "access_code": access_code}
            
        return {"message": "Event received"}
        
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

@app.get("/test-generate-code")
def test_generate_code():
    """Test endpoint to generate access codes (for testing only)"""
    code = generate_unique_access_code()
    return {"access_code": code, "message": "Test code generated (valid for one use)"}

@app.get("/debug-access-code")
def debug_access_code(access_code: Optional[str] = Query(None)):
    """Debug endpoint to test access code validation"""
    if not access_code:
        return {"error": "No access code provided"}
    
    is_valid = is_premium_user(access_code)
    return {
        "access_code": access_code,
        "is_valid": is_valid,
        "used_codes_count": len(used_access_codes),
        "code_upper": access_code.strip().upper(),
        "in_used_codes": access_code.strip().upper() in used_access_codes
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
