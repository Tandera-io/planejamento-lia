from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from typing import Optional

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer()

# Configuração do Supabase
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET')

def verify_token(token: str) -> dict:
    """Verifica e decodifica o token JWT do Supabase"""
    try:
        if not SUPABASE_JWT_SECRET:
            raise HTTPException(status_code=500, detail="Configuração de autenticação não encontrada")
            
        # Decodificar o token JWT
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=["HS256"],
            audience="authenticated"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependência para obter o usuário atual autenticado"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Token de autenticação necessário")
    
    token = credentials.credentials
    payload = verify_token(token)
    
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role", "user"),
        "user_metadata": payload.get("user_metadata", {}),
        "app_metadata": payload.get("app_metadata", {})
    }

@router.get("/me")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Retorna informações do usuário logado"""
    return {
        "user": current_user,
        "message": "Autenticação funcionando!"
    }

@router.get("/status") 
async def auth_status():
    """Verifica se o sistema de autenticação está configurado"""
    return {
        "auth_enabled": bool(SUPABASE_JWT_SECRET),
        "message": "Sistema de autenticação disponível" if SUPABASE_JWT_SECRET else "Configuração pendente"
    }
