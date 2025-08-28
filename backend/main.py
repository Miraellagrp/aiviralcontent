from fastapi import FastAPI 
from pydantic import BaseModel 
import os 
from dotenv import load_dotenv 
 
load_dotenv() 
 
app = FastAPI(title="AI Viral Content API") 
 
@app.get("/") 
def read_root(): 
