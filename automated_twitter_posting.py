# Automated Twitter Posting for AI Viral Content
# Requirements: pip install tweepy schedule
import tweepy
import random
import schedule
import time
from datetime import datetime

# Twitter API credentials (replace with your own)
CONSUMER_KEY = 'YOUR_CONSUMER_KEY'
CONSUMER_SECRET = 'YOUR_CONSUMER_SECRET'
ACCESS_TOKEN = 'YOUR_ACCESS_TOKEN'
ACCESS_SECRET = 'YOUR_ACCESS_SECRET'

auth = tweepy.OAuthHandler(CONSUMER_KEY, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

# Sample viral titles
viral_titles = [
    "I tried this AI title generator and my engagement went up 300%",
    "This tool is replacing $500/month social media managers",
    "How to never run out of content ideas (using AI)",
    "I generated 100 viral titles in 5 minutes with this tool"
]

# Add link to your app
APP_LINK = "https://aiviralcontent.io"

def post_tweet():
    title = random.choice(viral_titles)
    tweet = f"{title}\n\nTry it yourself: {APP_LINK}"
    api.update_status(tweet)
    print(f"Posted at {datetime.now()}: {title}")

# Schedule posts
schedule.every().day.at("10:00").do(post_tweet)
schedule.every().day.at("15:00").do(post_tweet)
schedule.every().day.at("19:00").do(post_tweet)

# Run continuously
if __name__ == "__main__":
    print("Starting automated Twitter posting...")
    while True:
        schedule.run_pending()
        time.sleep(60)
