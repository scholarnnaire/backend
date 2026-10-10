import requests
from app.core.security import create_access_token
token = create_access_token({"sub": "2"})
print("Token:", token)
res = requests.get("http://localhost:8000/api/team/school/members", headers={"Authorization": f"Bearer {token}"})
print(res.status_code)
print(res.json())
