import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import stripe
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

app = FastAPI()

# Allow CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class PaymentRequest(BaseModel):
    amount: int  # amount in cents
    currency: str = "usd"

@app.get("/")
async def root():
    return {"message": "Stripe payment server running"}

@app.post("/create-payment-intent")
async def create_payment_intent(payment: PaymentRequest):
    if payment.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    try:
        intent = stripe.PaymentIntent.create(
            amount=payment.amount,
            currency=payment.currency,
        )
        return {"clientSecret": intent.client_secret}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
