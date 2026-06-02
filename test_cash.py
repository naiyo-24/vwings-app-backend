import requests

url = "http://localhost:8000/api/fees/add-cash-payment"
payload = {
    "student_id": "STUDENT123", # Assuming a dummy ID will just fail with 404 or something, but we just want to see if 422/500 happens
    "payment_type": "installment",
    "installment_no": 2,
    "amount": 50000
}
try:
    res = requests.post(url, json=payload)
    print("Status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)
