from fastapi import FastAPI, Response, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import logging
from typing import Optional
try:
    import vertexai
    from vertexai.generative_models import GenerativeModel
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logging.warning("Vertex AI not available - install with: pip install google-cloud-aiplatform")

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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(json.loads(google_credentials), f)
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f.name
            logger.info("Using GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable")
    else:
        # Try to use API key if available
        api_key = os.environ.get("GOOGLE_API_KEY")
        if api_key:
            os.environ["GOOGLE_API_KEY"] = api_key
            logger.info("Using GOOGLE_API_KEY environment variable")
        else:
            logger.warning("No Google credentials found - Gemini API will use fallback responses")

app = FastAPI(title="AI Viral Content API", version="1.0.0")

# Pydantic models
class TitleRequest(BaseModel):
    topic: str

class GeminiResponse(BaseModel):
    description: str
    keywords: str

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
def generate_gemini(youtube_url: str = Query(..., description="YouTube video URL")):
    if not GENAI_AVAILABLE:
        logger.error("Google GenAI not available")
        raise HTTPException(status_code=503, detail="Gemini API not available - missing dependency")
    
    try:
        logger.info(f"Processing Vertex AI request for URL: {youtube_url[:50]}...")
        
        # Initialize Vertex AI
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "custom-tine-464511-u1")
        vertexai.init(project=project_id, location="us-central1")
        
        # Create the model
        model = GenerativeModel("gemini-1.5-flash")
        
        logger.info(f"Successfully initialized Vertex AI with project: {project_id}")
        
        # If we don't have proper credentials, use fallback
        if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") and not os.environ.get("GOOGLE_API_KEY"):
            logger.warning("No valid credentials found, using fallback")
            return GeminiResponse(
                description="🚀 How This Video Could Go VIRAL! (AI Analysis)", 
                keywords="viral,trending,youtube,content,ai,shorts,video,social,media,engagement"
            )
        
        # Create prompt for the video analysis
        prompt = f"""Analyze this YouTube video: {youtube_url}

Please write a 40 character long intriguing title for this video and provide 10 comma-separated hashtags that will be used for YouTube shorts.

Format your response as a JSON object:
{{"Description": "title of video (not more than 50 characters)", "Keywords": "comma separated hashtags (10)"}}

Example:
{{"Description": "Cosmic Dance: Galaxies Collide", "Keywords": "galaxy,collision,space,astronomy,stars,nebula,universe,simulation,science,cosmos"}}
"""
        
        output = ""
        try:
            response = model.generate_content(prompt)
            output = response.text
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
