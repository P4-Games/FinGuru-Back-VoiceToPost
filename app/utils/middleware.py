import httpx
from fastapi import HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()

async def check_subscription(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifica si el usuario tiene una suscripción activa.
    """
    token = credentials.credentials
    
    async with httpx.AsyncClient() as client:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get("https://staging.fin.guru/api/subscriptions", headers=headers, timeout=10.0)
            
            if response.status_code == 401:
                raise HTTPException(status_code=401, detail="Token de autorización inválido o expirado")
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Error al verificar la suscripción: {response.text}")
            
            data = response.json()
            if not data.get("hasActivePlan"):
                raise HTTPException(status_code=403, detail="Se requiere una suscripción activa")
            
            plan_slug = data.get("subscription", {}).get("plan", {}).get("slug")
            if plan_slug not in ["top-subscription", "medium-subscription"]:
                raise HTTPException(status_code=403, detail="Se requiere una suscripción válida")
            
            return {"token": token}
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Tiempo de espera agotado al verificar la suscripción")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Error de red al verificar la suscripción: {str(e)}")
        except HTTPException as he:
            raise he
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error inesperado: {str(e)}")