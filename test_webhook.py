import hmac
import hashlib
import time
import httpx
import json

secret = "mysecretkey123"
payload = json.dumps({
    "type": "payment_intent.succeeded",
    "data": {"object": {
        "amount": 5000,
        "currency": "usd",
        "receipt_email": "adhirajmohanchanana@gmail.com"
    }}
})

ts = str(int(time.time()))
signed_payload = f"{ts}.".encode() + payload.encode()
sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()

r = httpx.post(
    "https://bountiful-elegance-production-cf42.up.railway.app/webhook/stripe",
    content=payload,
    headers={
        "Stripe-Signature": f"t={ts},v1={sig}",
        "Content-Type": "application/json"
    }
)
print(r.status_code, r.json())