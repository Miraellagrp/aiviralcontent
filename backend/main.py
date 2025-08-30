
import stripe
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="AI Viral Content API")

# Enable CORS for payment processing
app.add_middleware(
	CORSMiddleware,
	allow_origins=["https://aiviralcontent-frontend.onrender.com"],  # Your frontend URL
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Stripe configuration
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

# Your domain - UPDATE THIS with your actual URL
YOUR_DOMAIN = "https://aiviralcontent-frontend.onrender.com"  # Change this to your real domain
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="AI Viral Content API")

@app.get("/")
def read_root():
	return {"message": "Welcome to AI Viral Content API"}

# Payment endpoint
@app.post("/create-checkout-session")
async def create_checkout_session():
	try:
		checkout_session = stripe.checkout.Session.create(
			payment_method_types=['card'],
			line_items=[
				{
					'price_data': {
						'currency': 'usd',
						'product_data': {
							'name': 'AIViralContent Pro - Lifetime Access',
							'description': 'Generate unlimited viral titles forever!',
						},
						'unit_amount': 2999,  # $29.99 in cents
					},
					'quantity': 1,
				},
			],
			mode='payment',
			success_url=YOUR_DOMAIN + '/success.html',
			cancel_url=YOUR_DOMAIN + '/',
		)
		return {"checkout_url": checkout_session.url}
	except Exception as e:
		print(f"Stripe error: {str(e)}")
		raise HTTPException(status_code=400, detail=str(e))
