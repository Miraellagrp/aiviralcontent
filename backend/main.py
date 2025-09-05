from fastapi import FastAPI, Response, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import logging
from typing import Optional
import json
from datetime import datetime, timedelta
import hashlib
import requests
import re
import hmac
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logging.warning("Google GenAI not available - install with: pip install google-genai")

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Google credentials
if os.path.exists(os.path.join(os.path.dirname(__file__), "google-credentials.json")):
    # Local development with service account file
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(os.path.dirname(__file__), "google-credentials.json")
    logger.info("Using local google-credentials.json file")
else:
    # Production deployment - use environment variable
    google_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON") or os.environ.get("GOOGLE_CREDENTIALS") or os.environ.get("DENTIALS_JSON")
    if google_credentials:
        # Write the credentials to a temporary file
        import tempfile
        import json
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(json.loads(google_credentials), f)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
                logger.info("Using GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in credentials environment variable: {e}")
            logger.info("Continuing without service account credentials")
    else:
        # Try to use API key if available
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
            logger.info("Using GOOGLE_API_KEY environment variable")
        else:
            logger.warning("No Google credentials found - Gemini API will use fallback responses")

# Rate limiting configuration
DAILY_FREE_LIMIT = 3  # Free requests per day per IP
RATE_LIMIT_FILE = "rate_limits.json"
ACCESS_CODES_FILE = "access_codes.json"

# Stripe configuration
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_test_key")  # Set this in your environment

def get_client_ip(request: Request) -> str:
    """Get client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def get_rate_limits() -> dict:
    """Load rate limits from file"""
    if os.path.exists(RATE_LIMIT_FILE):
        try:
            with open(RATE_LIMIT_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_rate_limits(limits: dict):
    """Save rate limits to file"""
    with open(RATE_LIMIT_FILE, 'w') as f:
        json.dump(limits, f)

def check_rate_limit(ip: str) -> bool:
    """Check if IP has exceeded daily limit"""
    limits = get_rate_limits()
    today = datetime.now().strftime("%Y-%m-%d")
    
    if ip not in limits:
        limits[ip] = {}
    
    if today not in limits[ip]:
        limits[ip][today] = 0
    
    # Clean old entries (older than 7 days)
    cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    for user_ip in list(limits.keys()):
        for date in list(limits[user_ip].keys()):
            if date < cutoff_date:
                del limits[user_ip][date]
        if not limits[user_ip]:
            del limits[user_ip]
    
    if limits[ip][today] >= DAILY_FREE_LIMIT:
        return False
    
    limits[ip][today] += 1
    save_rate_limits(limits)
    return True

def get_access_codes() -> dict:
    """Load access codes from file"""
    if os.path.exists(ACCESS_CODES_FILE):
        try:
            with open(ACCESS_CODES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_access_codes(codes: dict):
    """Save access codes to file"""
    with open(ACCESS_CODES_FILE, 'w') as f:
        json.dump(codes, f, indent=2)

def is_premium_user(access_code: str) -> bool:
    """Check if access code is valid for premium access"""
    if not access_code:
        return False
    
    codes = get_access_codes()
    return access_code in codes and codes[access_code].get("active", True)

def generate_access_code() -> str:
    """Generate a unique access code"""
    import secrets
    import string
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))

def verify_stripe_signature(payload: bytes, sig_header: str, webhook_secret: str) -> bool:
    """Verify Stripe webhook signature"""
    try:
        elements = sig_header.split(',')
        timestamp = None
        signatures = []
        
        for element in elements:
            key, value = element.split('=')
            if key == 't':
                timestamp = value
            elif key == 'v1':
                signatures.append(value)
        
        if timestamp is None or not signatures:
            return False
        
        # Create expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_signature = hmac.new(
            webhook_secret.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return any(hmac.compare_digest(expected_signature, signature) for signature in signatures)
    except Exception as e:
        logger.error(f"Error verifying Stripe signature: {str(e)}")
        return False

def get_specialized_prompt(content_type: str) -> str:
    """Generate specialized prompts based on content type"""
    
    if content_type == "professional":
        return """You are a LinkedIn content strategist and business communication expert. Analyze this video and create professional content:

1. Write a COMPELLING professional title (under 50 characters) that:
   - Focuses on business insights, leadership lessons, or industry trends
   - Uses power words like "Strategy", "Leadership", "Innovation", "Growth" 
   - Appeals to executives, entrepreneurs, and professionals
   - Creates curiosity about business value ("The Leadership Lesson That...")

2. Generate 10 professional hashtags mixing:
   - LinkedIn algorithm tags (#Leadership #Innovation #Growth #Strategy)
   - Industry-specific tags (based on video content)
   - Business networking tags (#Entrepreneurship #CEO #Business)

Format: {"Description": "professional_title", "Keywords": "hashtag1,hashtag2,hashtag3,hashtag4,hashtag5,hashtag6,hashtag7,hashtag8,hashtag9,hashtag10"}

Make it something a CEO would share on LinkedIn!"""

    elif content_type == "educational":
        return """You are an educational content expert specializing in tutorials and how-to content. Analyze this video and create educational content:

1. Write a CLEAR educational title (under 50 characters) that:
   - Promises specific learning outcomes ("How to Master...")
   - Uses step-by-step language ("5 Steps to...", "Complete Guide...")
   - Focuses on skills, knowledge, or problem-solving
   - Appeals to learners and students ("Learn X in Y Minutes")

2. Generate 10 educational hashtags mixing:
   - Learning tags (#tutorial #howto #learn #education #tips)
   - Skill-specific tags (based on video content)
   - Student/learner tags (#study #knowledge #skills)

Format: {"Description": "educational_title", "Keywords": "hashtag1,hashtag2,hashtag3,hashtag4,hashtag5,hashtag6,hashtag7,hashtag8,hashtag9,hashtag10"}

Make it irresistible to anyone wanting to learn!"""
    
    else:  # viral content (default)
        return """You are a viral content expert. Analyze this video and create click-worthy content:

1. Write an IRRESISTIBLE title (under 50 characters) that uses psychology to make people click:
   - Use curiosity gaps ("This Changed Everything...")
   - Create urgency ("Before It's Too Late")  
   - Promise transformation ("From Zero to...")
   - Use emotional triggers (shocking, amazing, secret)
   - Include numbers when relevant ("3 Secrets...")

2. Generate 10 trending hashtags mixing:
   - Broad viral tags (#viral #fyp #trending #foryou)
   - Content-specific tags (what's actually in the video)
   - Platform-specific tags (#tiktok #reels #shorts)

Format: {"Description": "viral_title", "Keywords": "hashtag1,hashtag2,hashtag3,hashtag4,hashtag5,hashtag6,hashtag7,hashtag8,hashtag9,hashtag10"}

Make it IRRESISTIBLE - something people MUST click on!"""

def send_access_code_email(email: str, access_code: str) -> bool:
    """Send access code via email (placeholder for now)"""
    # TODO: Integrate with your email service (SendGrid, etc.)
    logger.info(f"Would send access code {access_code} to {email}")
    
    # For now, just store in a file for you to manually send
    try:
        purchase_file = os.path.join(os.path.dirname(__file__), "purchases.txt")
        with open(purchase_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{timestamp}: {email} -> {access_code}\n")
        return True
    except Exception as e:
        logger.error(f"Error storing purchase info: {str(e)}")
        return False

def extract_youtube_video_id(url: str) -> str:
    """Extract video ID from YouTube URL"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com.*[?&]v=([a-zA-Z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def check_video_duration(video_url: str) -> dict:
    """Check if video is 30 seconds or less"""
    try:
        video_id = extract_youtube_video_id(video_url)
        if not video_id:
            return {"is_short": False, "error": "Invalid YouTube URL", "duration": None}
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            # If we don't have API key, reject the request to maintain 30-second limit
            return {"is_short": False, "error": "API key required for duration check", "duration": None}
        
        # YouTube Data API v3 call
        youtube_api_url = f"https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "contentDetails",
            "id": video_id,
            "key": api_key
        }
        
        response = requests.get(youtube_api_url, params=params, timeout=10)
        
        if response.status_code != 200:
            logger.warning(f"YouTube API error: {response.status_code}")
            # Reject the video if API fails to maintain 30-second limit
            return {"is_short": False, "error": "YouTube API unavailable", "duration": None}
        
        data = response.json()
        
        if not data.get("items"):
            return {"is_short": False, "error": "Video not found", "duration": None}
        
        duration_str = data["items"][0]["contentDetails"]["duration"]
        
        # Parse ISO 8601 duration (PT1M30S = 1 minute 30 seconds)
        duration_seconds = parse_youtube_duration(duration_str)
        
        is_short = duration_seconds <= 30
        
        return {
            "is_short": is_short,
            "error": None,
            "duration": duration_seconds,
            "duration_str": duration_str
        }
        
    except Exception as e:
        logger.error(f"Error checking video duration: {str(e)}")
        # Reject the video if checking fails to maintain 30-second limit
        return {"is_short": False, "error": "Duration check failed", "duration": None}

def parse_youtube_duration(duration_str: str) -> int:
    """Parse YouTube API duration string (ISO 8601) to seconds"""
    # PT1M30S -> 90 seconds
    # PT45S -> 45 seconds  
    # PT2M -> 120 seconds
    
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)
    
    if not match:
        return 0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)  
    seconds = int(match.group(3) or 0)
    
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds

app = FastAPI(title="AI Viral Content API", version="1.0.0")

# Pydantic models
class TitleRequest(BaseModel):
    topic: str

class GeminiResponse(BaseModel):
    description: str
    keywords: str

class EmailSubscription(BaseModel):
    email: str

class AccessCodeRequest(BaseModel):
    access_code: str

# Basic endpoints
@app.get("/")
def root():
    return {"message": "AI Viral Content API is LIVE!", "domain": "aiviralcontent.io"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/generate-titles")
def generate_titles(request: TitleRequest):
    titles = [
        f"How {request.topic} Changed My Life Forever",
        f"The Dark Truth About {request.topic}",
        f"I Tried {request.topic} for 30 Days - Shocking Results!",
        f"Why Everyone's Wrong About {request.topic}",
        f"{request.topic}: The Complete Guide You Need"
    ]
    return {"topic": request.topic, "titles": titles}

# Simple payment link endpoint for Stripe
@app.get("/payment-link")
async def payment_link(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	return {
		"checkout_url": "https://buy.stripe.com/fZu00kenx9ZabySdgd9MY00"
	}

# Simple direct-checkout endpoint for connectivity testing
@app.get("/direct-checkout")
async def direct_checkout(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	return {"checkout_url": "https://buy.stripe.com/fZu00kenx9ZabySdgd9MY00"}

# Hard-coded test endpoint for Stripe checkout URL
@app.post("/test-checkout")
async def test_checkout(response: Response):
	# Add CORS headers
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	# Return the production checkout URL
	return {
		"checkout_url": "https://buy.stripe.com/fZu00kenx9ZabySdgd9MY00",
		"status": "success"
	}

# OPTIONS handler for the test endpoint
@app.options("/test-checkout")
async def test_checkout_options(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	return {}

# Email subscription endpoint
@app.post("/subscribe-email")
async def subscribe_email(email_data: EmailSubscription, response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	
	try:
		email = email_data.email.strip().lower()
		
		# Basic email validation
		if not email or "@" not in email or "." not in email.split("@")[1]:
			raise HTTPException(status_code=400, detail="Invalid email address")
		
		# Log the email (for now)
		logger.info(f"New email subscription: {email}")
		
		# Store in a simple file for now (you can upgrade this later)
		import os
		emails_file = os.path.join(os.path.dirname(__file__), "subscriber_emails.txt")
		with open(emails_file, "a", encoding="utf-8") as f:
			from datetime import datetime
			timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
			f.write(f"{timestamp}: {email}\n")
		
		logger.info(f"Email {email} saved to subscriber list")
		
		return {
			"success": True,
			"message": "Successfully subscribed! Check your email for viral templates.",
			"email": email
		}
		
	except Exception as e:
		logger.error(f"Email subscription error: {str(e)}")
		raise HTTPException(status_code=500, detail="Failed to process subscription")

# OPTIONS handler for email endpoint
@app.options("/subscribe-email")
async def subscribe_email_options(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	return {}

# Endpoint to view captured emails (for admin use)
@app.get("/admin/emails")
async def get_emails():
	try:
		emails_file = os.path.join(os.path.dirname(__file__), "subscriber_emails.txt")
		if os.path.exists(emails_file):
			with open(emails_file, "r", encoding="utf-8") as f:
				content = f.read()
			
			# Parse emails into structured format
			lines = content.strip().split('\n')
			emails = []
			for line in lines:
				if line.strip() and ':' in line:
					try:
						timestamp, email = line.split(': ', 1)
						emails.append({
							"timestamp": timestamp,
							"email": email.strip()
						})
					except:
						continue
			
			return {
				"total_emails": len(emails),
				"emails": emails,
				"raw_content": content
			}
		else:
			return {
				"total_emails": 0,
				"emails": [],
				"message": "No emails captured yet"
			}
	except Exception as e:
		logger.error(f"Error reading emails: {str(e)}")
		raise HTTPException(status_code=500, detail="Error reading email file")

# Admin endpoint to generate access codes
@app.post("/admin/generate-code")
async def generate_code(admin_key: str = Query(..., description="Admin key for authentication")):
	# Simple admin authentication (you can make this more secure)
	if admin_key != "admin123":  # Change this to a secure admin key
		raise HTTPException(status_code=401, detail="Unauthorized")
	
	try:
		codes = get_access_codes()
		new_code = generate_access_code()
		
		# Ensure code is unique
		while new_code in codes:
			new_code = generate_access_code()
		
		# Add new code
		from datetime import datetime
		codes[new_code] = {
			"active": True,
			"created_at": datetime.now().isoformat(),
			"used": False
		}
		
		save_access_codes(codes)
		
		return {
			"access_code": new_code,
			"message": "Access code generated successfully",
			"total_codes": len(codes)
		}
	except Exception as e:
		logger.error(f"Error generating access code: {str(e)}")
		raise HTTPException(status_code=500, detail="Error generating access code")

# Admin endpoint to view all access codes
@app.get("/admin/access-codes")
async def get_all_codes(admin_key: str = Query(..., description="Admin key for authentication")):
	if admin_key != "admin123":  # Change this to a secure admin key
		raise HTTPException(status_code=401, detail="Unauthorized")
	
	try:
		codes = get_access_codes()
		return {
			"total_codes": len(codes),
			"codes": codes
		}
	except Exception as e:
		logger.error(f"Error reading access codes: {str(e)}")
		raise HTTPException(status_code=500, detail="Error reading access codes")

# Endpoint to verify access code (for frontend)
@app.post("/verify-access-code")
async def verify_code(code_request: AccessCodeRequest, response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"  
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	
	is_valid = is_premium_user(code_request.access_code)
	
	return {
		"valid": is_valid,
		"message": "Access code verified" if is_valid else "Invalid access code"
	}

# OPTIONS handler for verify access code endpoint
@app.options("/verify-access-code")
async def verify_code_options(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	return {}

# Stripe webhook endpoint
@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
	try:
		payload = await request.body()
		sig_header = request.headers.get("stripe-signature", "")
		
		# Verify webhook signature
		if not verify_stripe_signature(payload, sig_header, STRIPE_WEBHOOK_SECRET):
			logger.warning("Invalid Stripe webhook signature")
			raise HTTPException(status_code=400, detail="Invalid signature")
		
		# Parse the webhook event
		try:
			event = json.loads(payload.decode("utf-8"))
		except json.JSONDecodeError:
			logger.error("Invalid JSON in webhook payload")
			raise HTTPException(status_code=400, detail="Invalid JSON")
		
		# Handle successful payment
		if event["type"] == "checkout.session.completed":
			session = event["data"]["object"]
			customer_email = session.get("customer_details", {}).get("email")
			
			if customer_email:
				logger.info(f"Processing successful payment for {customer_email}")
				
				# Generate access code
				codes = get_access_codes()
				new_code = generate_access_code()
				
				# Ensure code is unique
				while new_code in codes:
					new_code = generate_access_code()
				
				# Save the access code
				codes[new_code] = {
					"active": True,
					"created_at": datetime.now().isoformat(),
					"customer_email": customer_email,
					"stripe_session_id": session["id"],
					"auto_generated": True
				}
				
				save_access_codes(codes)
				
				# Send access code (for now, stores in file for manual sending)
				send_access_code_email(customer_email, new_code)
				
				logger.info(f"Generated access code {new_code} for {customer_email}")
			else:
				logger.warning("No customer email in Stripe session")
		
		return {"status": "success"}
		
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Error processing Stripe webhook: {str(e)}")
		raise HTTPException(status_code=500, detail="Webhook processing failed")

# Admin endpoint to view purchases
@app.get("/admin/purchases")
async def get_purchases(admin_key: str = Query(..., description="Admin key for authentication")):
	if admin_key != "admin123":  # Change this to a secure admin key
		raise HTTPException(status_code=401, detail="Unauthorized")
	
	try:
		purchase_file = os.path.join(os.path.dirname(__file__), "purchases.txt")
		if os.path.exists(purchase_file):
			with open(purchase_file, "r", encoding="utf-8") as f:
				content = f.read()
			
			# Parse purchases into structured format
			lines = content.strip().split('\n')
			purchases = []
			for line in lines:
				if line.strip() and ':' in line and ' -> ' in line:
					try:
						timestamp, email_code = line.split(': ', 1)
						email, code = email_code.split(' -> ')
						purchases.append({
							"timestamp": timestamp,
							"email": email.strip(),
							"access_code": code.strip()
						})
					except:
						continue
			
			return {
				"total_purchases": len(purchases),
				"purchases": purchases,
				"raw_content": content
			}
		else:
			return {
				"total_purchases": 0,
				"purchases": [],
				"message": "No purchases yet"
			}
	except Exception as e:
		logger.error(f"Error reading purchases: {str(e)}")
		raise HTTPException(status_code=500, detail="Error reading purchase file")

# Add a test endpoint to verify environment
@app.get("/test-env")
async def test_env():
	credentials_status = "none"
	if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
		credentials_status = "file_set"
	if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
		credentials_status = "env_var_set"
	
	return {
		"genai_available": GENAI_AVAILABLE,
		"environment": os.environ.get("ENVIRONMENT", "development"),
		"service_status": "running",
		"credentials_status": credentials_status,
		"project_id": os.environ.get("GOOGLE_CLOUD_PROJECT", "not_set")
	}

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
    
    # Check rate limiting (skip for premium users)
    if not is_premium:
        client_ip = get_client_ip(request)
        if not check_rate_limit(client_ip):
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=429, 
                detail=f"Daily free limit exceeded ({DAILY_FREE_LIMIT} requests per day). Please purchase our lifetime access for unlimited usage at aiviralcontent.io"
            )
    
    # Check video duration (skip for premium users)
    if not is_premium:
        duration_check = check_video_duration(youtube_url)
        if not duration_check["is_short"]:
            if duration_check["error"]:
                logger.warning(f"Duration check error: {duration_check['error']} for URL: {youtube_url}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Unable to verify video duration. Only short videos (30 seconds or less) are supported in the free tier. Please use a valid YouTube video URL or upgrade to lifetime access at aiviralcontent.io"
                )
            else:
                logger.warning(f"Video too long ({duration_check['duration']}s) for URL: {youtube_url}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Only short videos (30 seconds or less) are supported in the free tier. This video is {duration_check['duration']} seconds long. Upgrade to lifetime access for full-length videos at aiviralcontent.io"
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
