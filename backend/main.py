


from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import stripe
import os

app = FastAPI()

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
	response.headers["Access-Control-Allow-Origin"] = "https://aiviralcontent-frontend.onrender.com"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	try:
		stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
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
		return {"checkout_url": checkout_session.url}
	except Exception as e:
		print(f"Stripe error: {str(e)}")
		return {"error": str(e)}

# Add an OPTIONS handler for the checkout endpoint
@app.options("/create-checkout-session")
async def create_checkout_session_options(response: Response):
	response.headers["Access-Control-Allow-Origin"] = "https://aiviralcontent-frontend.onrender.com"
	response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
	response.headers["Access-Control-Allow-Headers"] = "Content-Type"
	return {}
