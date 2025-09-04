#!/usr/bin/env python3
"""
Production start script for Render deployment
"""
import os
import uvicorn
from main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    # Production settings
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        workers=1  # Render free tier limitation
    )