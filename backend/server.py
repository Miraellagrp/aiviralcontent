from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class TitleRequest(BaseModel):
    topic: str

@app.get("/")
def root():
    return {"message": "AI Viral Content API is LIVE!", "domain": "aiviralcontent.io"}

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

@app.get("/health")
def health():
    return {"status": "healthy"}