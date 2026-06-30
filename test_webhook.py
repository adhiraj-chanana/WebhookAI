import hmac, hashlib, time, httpx, json
from dotenv import load_dotenv
import os

load_dotenv()

secret = os.getenv("STRIPE_WEBHOOK_SECRET")
payload = json.dumps({
    "type": "payment_intent.succeeded",
    "data": {"object": {
        "amount": 5000,
        "currency": "usd",
        "receipt_email": "adhirajmohanchanana@gmail.com"
    }}
})
ts = str(int(time.time()))
# REPLACE with this:
signed_payload = f"{ts}.".encode() + payload.encode()
sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

r = httpx.post(
    "http://localhost:8000/webhook/stripe",
    content=payload,
    headers={
        "Stripe-Signature": f"t={ts},v1={sig}",
        "Content-Type": "application/json"
    }
)
print(r.status_code, r.json())
