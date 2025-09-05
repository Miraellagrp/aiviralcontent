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
    """Check if video is a YouTube Short (≤60 seconds)"""
    try:
        video_id = extract_youtube_video_id(video_url)
        if not video_id:
            return {"is_short": False, "error": "Invalid YouTube URL", "duration": None}
        
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            # If we don't have API key, we'll assume it's allowed (fallback)
            return {"is_short": True, "error": None, "duration": "unknown"}
        
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
            # Fallback: allow the video if API fails
            return {"is_short": True, "error": "API unavailable", "duration": "unknown"}
        
        data = response.json()
        
        if not data.get("items"):
            return {"is_short": False, "error": "Video not found", "duration": None}
        
        duration_str = data["items"][0]["contentDetails"]["duration"]
        
        # Parse ISO 8601 duration (PT1M30S = 1 minute 30 seconds)
        duration_seconds = parse_youtube_duration(duration_str)
        
        is_short = duration_seconds <= 60
        
        return {
            "is_short": is_short,
            "error": None,
            "duration": duration_seconds,
            "duration_str": duration_str
        }
        
    except Exception as e:
        logger.error(f"Error checking video duration: {str(e)}")
        # Fallback: allow the video if checking fails
        return {"is_short": True, "error": "Duration check failed", "duration": "unknown"}

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
		"checkout_url": "https://buy.stripe.com/test_aEU5lO8Io7CB36E6oo"
	}

# Simple direct-checkout endpoint for connectivity testing
@app.get("/direct-checkout")
async def direct_checkout(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	return {"checkout_url": "https://buy.stripe.com/test_00g5lO2mccUT4ww5kk"}

# Hard-coded test endpoint for Stripe checkout URL
@app.post("/test-checkout")
async def test_checkout(response: Response):
	# Add CORS headers
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	# Return a test checkout URL
	return {
		"checkout_url": "https://buy.stripe.com/test_00g5lO2mccUT4ww5kk",
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
def generate_gemini(request: Request, youtube_url: str = Query(..., description="YouTube video URL")):
    if not GENAI_AVAILABLE:
        logger.error("Google GenAI not available")
        raise HTTPException(status_code=503, detail="Gemini API not available - missing dependency")
    
    # Check rate limiting
    client_ip = get_client_ip(request)
    if not check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429, 
            detail=f"Daily free limit exceeded ({DAILY_FREE_LIMIT} requests per day). Please purchase our lifetime access for unlimited usage at aiviralcontent.io"
        )
    
    # Check if video is a Short (≤60 seconds)
    duration_check = check_video_duration(youtube_url)
    if not duration_check["is_short"]:
        if duration_check["error"]:
            logger.warning(f"Duration check error: {duration_check['error']} for URL: {youtube_url}")
        else:
            logger.warning(f"Video too long ({duration_check['duration']}s) for URL: {youtube_url}")
            raise HTTPException(
                status_code=400,
                detail=f"Only YouTube Shorts (60 seconds or less) are supported in the free tier. This video is {duration_check['duration']} seconds long. Upgrade to lifetime access for full-length videos at aiviralcontent.io"
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
        
        # Create the content with video URL and prompt
        prompt_text = """Please write a 40 character long intriguing title of this video and 10 comma separated hashtags that will be used for youtube shorts. Format the response as a python dictionary {"Description": title of video(not more than 50 characters), "Keywords": comma separated hashtags(10)}"""
        
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
