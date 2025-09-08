import os
from supabase import create_client, Client
from typing import Optional, List, Dict, Any

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", SUPABASE_KEY)

def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL e SUPABASE_KEY devem estar configurados")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def get_supabase_admin() -> Client:
    """Cliente Supabase com privilégios administrativos (bypass RLS)"""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar configurados")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

def insert_transcription(data: dict):
    supabase = get_supabase_client()
    return supabase.table("transcriptions").insert(data).execute()

def update_transcription(id: str, data: dict):
    supabase = get_supabase_client()
    return supabase.table("transcriptions").update(data).eq("id", id).execute()

def get_transcriptions():
    supabase = get_supabase_client()
    return supabase.table("transcriptions").select("*").order("created_at", desc=True).execute()

def get_transcription_by_id(id: str):
    supabase = get_supabase_client()
    return supabase.table("transcriptions").select("*").eq("id", id).single().execute()

def get_recent_transcriptions_by_client_project(
    client: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Busca transcrições recentes por cliente e/ou projeto
    
    Args:
        client: Nome do cliente (opcional)
        project: Nome do projeto (opcional)
        limit: Número máximo de transcrições a retornar (padrão: 3)
    
    Returns:
        Lista de transcrições ordenadas por data (mais recente primeiro)
    """
    try:
        supabase = get_supabase_client()
        
        # Construir query base
        query = supabase.table("transcriptions").select(
            "id, created_at, title, client, project, executive_summary, action_items, status"
        )
        
        # Adicionar filtros se fornecidos
        if client and client != 'N/A':
            query = query.eq("client", client)
        
        if project and project != 'N/A':
            query = query.eq("project", project)
        
        # Só transcrições completadas
        query = query.eq("status", "completed")
        
        # Ordenar por data (mais recente primeiro) e limitar
        result = query.order("created_at", desc=True).limit(limit).execute()
        
        return result.data if result.data else []
        
    except Exception as e:
        print(f"[ERROR] Erro ao buscar transcrições anteriores: {e}")
        return []
