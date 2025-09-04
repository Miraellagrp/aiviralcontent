# AI Viral Content Setup & Deployment Guide

## 1. Backend Setup

- Create a folder called `backend` inside your project folder.
- Inside `backend`, create a file named `gemini_api.py`.

## 2. Add FastAPI Gemini API Code

Paste this code into `backend/gemini_api.py`:

```python
from fastapi import FastAPI
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI()

class VideoRequest(BaseModel):
    youtube_url: str

@app.post("/generate")
async def generate_title_and_hashtags(request: VideoRequest):
    client = genai.Client(
        vertexai=True,
        project="YOUR_PROJECT_ID",
        location="global",
    )

    msg_video = types.Part.from_uri(
        file_uri=request.youtube_url,
        mime_type="video/*",
    )
    msg_text = types.Part.from_text(text="Please write a 40 character long intriguing title of this video and 10 comma separated hashtags that will be used for youtube shorts. Format the response as a python dictionary {\"Description\": title of video(not more than 50 characters), \"Keywords\": comma separated hashtags(10)}")

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
        max_output_tokens=65535,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    result = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        result += chunk.text

    return {"result": result}
```

## 3. Requirements File

- In `backend`, create a file named `requirements.txt` and add:
```
fastapi
uvicorn
google-generativeai
```

## 4. Frontend Setup

- Create a folder called `frontend` inside your project folder.
- Add your `index.html` and any other frontend files here.

## 5. Deploy to Render

- Set your Render service root directory to `backend`.
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn gemini_api:app --host 0.0.0.0 --port $PORT`

## 6. Connect Frontend to Backend

- In your frontend JavaScript, POST the YouTube URL to:
  ```
  https://aiviralcontent-api.onrender.com/generate
  ```
- Display the returned title and hashtags in your UI.

---

**If you need help with any step, let me know!**