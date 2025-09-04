#!/bin/bash
# Quick deployment script for Render

echo "🚀 Preparing deployment to Render..."

# Add all changes
git add .

# Commit with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Update: backend deployment ready - $TIMESTAMP

🔧 Fixed backend errors with code and connection
📦 Updated dependencies and production configuration  
🔒 Enhanced CORS and error handling
✅ Ready for Render deployment

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

echo "📤 Pushing to repository..."
git push origin main

echo "✅ Deployment update pushed!"
echo "🌐 Your API will be available at: https://aiviralcontent-api.onrender.com"
echo "🏥 Health check: https://aiviralcontent-api.onrender.com/health"
echo ""
echo "📋 Next steps:"
echo "1. Check Render dashboard for deployment progress"
echo "2. Verify environment variables are set"
echo "3. Test the endpoints once deployed"