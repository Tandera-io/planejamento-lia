import os
import openai
import tempfile
import json
import logging
from openai import OpenAI

# Configurar logger
logger = logging.getLogger(__name__)

# Removido inicialização global para evitar crash no Railway
def _get_client():
    """Retorna cliente OpenAI com lazy loading"""
    # Tentar múltiplas formas de obter a API key
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY_RAILWAY")
    
    if not api_key:
        api_key = os.getenv("RAILWAY_OPENAI_API_KEY")
    
    if not api_key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            api_key = os.getenv("OPENAI_API_KEY")
        except ImportError:
            pass
    
    if not api_key:
        logger.error("❌ OPENAI_API_KEY não encontrada")
        raise ValueError("OPENAI_API_KEY deve estar configurado")
    
    logger.info(f"✅ OpenAI API Key encontrada: {api_key[:10]}...")
    org_raw = os.getenv("OPENAI_ORG") or os.getenv("OPENAI_ORGANIZATION") or os.getenv("OPENAI_ORGANIZATION_ID")

    # Sanitização: enviar apenas organization quando for um ID válido; NÃO enviar header de project
    org = org_raw if (org_raw and org_raw.startswith("org_")) else None
    if org_raw and not org:
        logger.warning(f"Ignorando OPENAI_ORG inválida: {org_raw}")

    kwargs = {"api_key": api_key}
    if org:
        kwargs["organization"] = org
    logger.info(f"OpenAI client init -> org={org or 'none'} (sem project header)")
    return OpenAI(**kwargs)

def gpt_4_completion(prompt: str, max_tokens=512):
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()

def gpt_3_5_completion(prompt: str, max_tokens=512):
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.2,
    )
    return response.choices[0].message.content.strip()
