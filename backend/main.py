
# Simple test endpoint to verify deployment
@app.get("/test")
async def test():
	return {"status": "ok"}




import stripe
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow all origins for testing
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

# Stripe Checkout endpoint
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
							'name': 'AI Viral Content Pro',
							'description': 'Lifetime access',
						},
						'unit_amount': 2999,  # $29.99 in cents
					},
					'quantity': 1,
				},
			],
			mode='payment',
			success_url='https://aiviralcontent-frontend.onrender.com/success.html',
			cancel_url='https://aiviralcontent-frontend.onrender.com/',
		)
		return {"checkout_url": checkout_session.url}
	except Exception as e:
		print(f"Stripe error: {str(e)}")
		return {"error": str(e)}
