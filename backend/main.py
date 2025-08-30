


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import stripe
import os

app = FastAPI()

# Add CORS middleware
app.add_middleware(
	CORSMiddleware,
	allow_origins=["https://aiviralcontent-frontend.onrender.com"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

@app.post("/create-checkout-session")
async def create_checkout_session():
	try:
		YOUR_DOMAIN = "https://aiviralcontent-frontend.onrender.com"
		checkout_session = stripe.checkout.Session.create(
			payment_method_types=['card'],
			line_items=[{
				'price_data': {
					'currency': 'usd',
					'product_data': {
						'name': 'AI Viral Content Pro - Lifetime Access',
						'description': 'Generate unlimited viral titles forever!',
					},
					'unit_amount': 2999,
				},
				'quantity': 1,
			}],
			mode='payment',
			success_url=YOUR_DOMAIN + '/success.html',
			cancel_url=YOUR_DOMAIN + '/',
		)
		return {"checkout_url": checkout_session.url}
	except Exception as e:
		print(f"Stripe error: {str(e)}")
		raise HTTPException(status_code=400, detail=str(e))
