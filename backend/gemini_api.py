from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
import uvicorn

app = FastAPI()

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class GeminiResponse(BaseModel):
    description: str
    keywords: str

@app.get("/generate-gemini", response_model=GeminiResponse)
def generate_gemini(youtube_url: str = Query(..., description="YouTube video URL")):
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
    print("[Gemini raw output]", output)  # Debug: print raw Gemini output to server log
    # Try to parse the output as a Python dict
    import ast
    try:
        parsed = ast.literal_eval(output.strip().replace('```json','').replace('```',''))
        description = parsed.get("Description", "")
        keywords = parsed.get("Keywords", "")
    except Exception:
        description = output.strip()
        keywords = ""
    return GeminiResponse(description=description, keywords=keywords)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
