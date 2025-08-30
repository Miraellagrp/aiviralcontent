# Simple endpoint for a hardcoded payment link
@app.get("/simple-payment")
async def simple_payment(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	return {"checkout_url": "https://buy.stripe.com/test_aEU5lO8Io7CB36E6oo"}

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import stripe
import os

app = FastAPI()

# Simple payment link endpoint for Stripe
@app.get("/payment-link")
async def payment_link(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	return {
		"checkout_url": "https://buy.stripe.com/test_aEU5lO8Io7CB36E6oo"
	}

# Simple direct-checkout endpoint for connectivity testing
@app.get("/direct-checkout")
async def direct_checkout(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	return {"checkout_url": "https://buy.stripe.com/test_00g5lO2mccUT4ww5kk"}

# Hard-coded test endpoint for Stripe checkout URL
@app.post("/test-checkout")
async def test_checkout(response: Response):
	# Add CORS headers
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	# Return a test checkout URL
	return {
		"checkout_url": "https://buy.stripe.com/test_00g5lO2mccUT4ww5kk",
		"status": "success"
	}

# OPTIONS handler for the test endpoint
@app.options("/test-checkout")
async def test_checkout_options(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	return {}

stripe_key = os.environ.get("STRIPE_SECRET_KEY")
if not stripe_key:
	print("ERROR: No Stripe API key found in environment variables")
	# Optionally, you can raise an error or return a clear message in your endpoints
stripe.api_key = stripe_key

# Add a test endpoint to verify Stripe key presence
@app.get("/test-env")
async def test_env():
	has_stripe_key = bool(os.environ.get("STRIPE_SECRET_KEY"))
	return {
		"stripe_key_exists": has_stripe_key,
		"stripe_key_prefix": os.environ.get("STRIPE_SECRET_KEY", "")[:4] + "..." if has_stripe_key else "Not set"
	}

# Add CORS middleware with specific origins
origins = [
	"https://aiviralcontent-frontend.onrender.com",
	"http://localhost:3000",
	"http://localhost:8000",
	"*"  # For testing only - remove in production
]

app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Add manual CORS headers to the checkout endpoint

@app.post("/create-checkout-session")
async def create_checkout_session(response: Response):
	# Set explicit CORS headers
	response.headers["Access-Control-Allow-Origin"] = "*"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	try:
		# Log the Stripe key prefix (redacted)
		key_prefix = stripe.api_key[:4] if stripe.api_key else "None"
		print(f"Using Stripe key starting with: {key_prefix}...")

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
						'unit_amount': 2999,
					},
					'quantity': 1,
				},
			],
			mode='payment',
			success_url='https://aiviralcontent-frontend.onrender.com/success.html',
			cancel_url='https://aiviralcontent-frontend.onrender.com/',
		)
		print(f"Stripe checkout session created: {checkout_session.id}")
		print(f"Checkout URL: {checkout_session.url}")
		return {
			"checkout_url": checkout_session.url,
			"session_id": checkout_session.id,
			"status": "success"
		}
	except Exception as e:
		print(f"Stripe error: {str(e)}")
		return {"error": str(e), "status": "error"}

# Add an OPTIONS handler for the checkout endpoint
@app.options("/create-checkout-session")
async def create_checkout_session_options(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "https://aiviralcontent-frontend.onrender.com"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	return {}
