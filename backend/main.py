from fastapi import FastAPI, Response, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import logging
from typing import Optional
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logging.warning("Google GenAI not available - install with: pip install google-genai")

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add a test endpoint to verify environment
@app.get("/test-env")
async def test_env():
	return {
		"genai_available": GENAI_AVAILABLE,
		"environment": os.environ.get("ENVIRONMENT", "development"),
		"service_status": "running"
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

# Gemini API endpoint
@app.get("/generate-gemini", response_model=GeminiResponse)
def generate_gemini(youtube_url: str = Query(..., description="YouTube video URL")):
    if not GENAI_AVAILABLE:
        logger.error("Google GenAI not available")
        raise HTTPException(status_code=503, detail="Gemini API not available - missing dependency")
    
    try:
        logger.info(f"Processing Gemini request for URL: {youtube_url[:50]}...")
        client = genai.Client(
            vertexai=True,
            project="gothic-guard-459415-q5",
            location="global",
        )
        msg_video = types.Part.from_uri(
            file_uri=youtube_url,
            mime_type="video/*",
        )
        msg_text = types.Part.from_text(text="You are an expert at creating viral content. Watch the video and write a clickbait, viral, curiosity-driven title (max 40 characters) that would make people want to click instantly. Also, generate 10 highly trending, platform-agnostic hashtags for this video. Format the response as a python dictionary: {\"Description\": viral title, \"Keywords\": comma separated hashtags (10)}")
        model = "gemini-2.5-flash-lite"
        contents = [
            types.Content(
                role="user",
                parts=[msg_video, msg_text]
            )
        ]
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            max_output_tokens=1024,
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
            ],
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        output = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            output += chunk.text
        logger.info(f"Gemini API response received: {len(output)} characters")
        
        # Parse the output as a Python dict
        import ast
        try:
            parsed = ast.literal_eval(output.strip().replace('```json','').replace('```',''))
            description = parsed.get("Description", "")
            keywords = parsed.get("Keywords", "")
            logger.info("Successfully parsed Gemini response")
        except Exception as parse_error:
            logger.warning(f"Failed to parse Gemini response: {parse_error}")
            description = output.strip()
            keywords = ""
        return GeminiResponse(description=description, keywords=keywords)
    except Exception as e:
        logger.error(f"Gemini API error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Gemini API error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
