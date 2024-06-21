import os
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from load_env import load_env_files

load_env_files()

API_URL = os.getenv("API_URL")
security = HTTPBearer()

async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_URL}/users/me?populate=*",
            headers={"Authorization": f"Bearer {token}"}
        )
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = response.json()
        if not user.get("email"):
            raise HTTPException(status_code=401, detail="Invalid token")
        
        tester_response = await client.get(f"{API_URL}/is-tester?email={user['email']}")
        if tester_response.status_code != 200 or not tester_response.json().get("details"):
            raise HTTPException(status_code=401, detail="User is not a tester")
    
    return user