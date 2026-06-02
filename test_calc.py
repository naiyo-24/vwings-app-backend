import requests
import json

# Try to fetch counsellors to get a valid ID
res = requests.get("http://localhost:8000/api/counsellors/get-all")
if res.ok:
    counsellors = res.json()
    if counsellors:
        cid = counsellors[0]["counsellor_id"]
        res_calc = requests.get(f"http://localhost:8000/api/commissions/calculate/{cid}/5/2026")
        print("Calc Status:", res_calc.status_code)
        print("Calc Response:", res_calc.text)
    else:
        print("No counsellors found.")
else:
    print("Failed to get counsellors:", res.status_code, res.text)
