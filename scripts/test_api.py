import requests
import json

url = "http://localhost:8000/api/v1/dashboard/auth/login"
data = {"password": "changeme"}
headers = {"Content-Type": "application/json"}

try:
    response = requests.post(url, json=data, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        token = response.json().get("token")
        print(f"Token: {token}")
        
        # Test a protected endpoint
        summary_url = "http://localhost:8000/api/v1/dashboard/summary"
        summary_headers = {"Authorization": f"Bearer {token}"}
        summary_response = requests.get(summary_url, headers=summary_headers)
        print(f"Summary Status Code: {summary_response.status_code}")
        # print(f"Summary Response: {summary_response.text[:200]}...")
except Exception as e:
    print(f"Error: {e}")
