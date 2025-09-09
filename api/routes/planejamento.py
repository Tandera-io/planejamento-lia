from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import os
import uuid
import re
import json
import datetime as dt

# Dependência de autenticação (mesmo padrão das outras rotas)
try:
    from api.routes.auth import get_current_user
except Exception:
    async def get_current_user(credentials: HTTPAuthorizationCredentials = None):
        return {}

# Supabase client reutilizando serviço existente
try:
    from services.supabase_service import get_supabase_client
except Exception:
    # Fallback local se import falhar
    from supabase import create_client
    def get_supabase_client():
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL/SUPABASE_KEY não configurados")
        return create_client(url, key)

router = APIRouter(prefix="/api/planejamentos", tags=["planejamentos"])


# ============================
# Modelos Pydantic (Sprint 1)
# ============================
class PlanejamentoCreate(BaseModel):
    titulo: str = Field(..., min_length=3)
    client_project_id: Optional[str] = None
    cliente_id: Optional[str] = None
    projeto_id: Optional[str] = None
    descricao: Optional[str] = None


class PlanejamentoUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    status: Optional[str] = None  # draft | processing | generated | approved | archived
    conteudo: Optional[Dict[str, Any]] = None  # JSON estruturado do planejamento


class ContextoPayload(BaseModel):
    reunioes_ids: Optional[List[str]] = None
    arquivos: Optional[List[Dict[str, Any]]] = None  # [{ bucket, path, name, size, type } ou snapshots de contexto]
    texto_livre: Optional[str] = None


# ============================
# Pré-planejamento (Sprint 3)
# ============================
class PreplanSave(BaseModel):
    resumo_geral: Optional[str] = None
    bulletpoints: Optional[List[str]] = None
    sources: Optional[List[Dict[str, Any]]] = None


# ============================
# Endpoints básicos (Sprint 1)
# ============================
@router.post("/", status_code=201)
async def criar_planejamento(payload: PlanejamentoCreate, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        dados = {
            "titulo": payload.titulo,
            "client_project_id": payload.client_project_id,
            "cliente_id": payload.cliente_id,
            "projeto_id": payload.projeto_id,
            "descricao": payload.descricao,
            "status": "draft",
            "conteudo": {},
        }
        if current_user and isinstance(current_user, dict):
            dados["user_id"] = current_user.get("id")
        result = supabase.table("planejamentos").insert(dados).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Falha ao criar planejamento")
        return {"id": result.data[0].get("id"), "data": result.data[0]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def listar_planejamentos(limit: int = 50, offset: int = 0, status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        query = supabase.table("planejamentos").select("*").order("created_at", desc=True)
        if status:
            query = query.eq("status", status)
        # filtro por usuário quando houver user_id
        if current_user and isinstance(current_user, dict) and current_user.get("id"):
            query = query.eq("user_id", current_user.get("id"))
        result = query.limit(limit).offset(offset).execute()
        return {"data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{planejamento_id}")
async def obter_planejamento(planejamento_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        query = supabase.table("planejamentos").select("*").eq("id", planejamento_id)
        # filtro por usuário quando houver user_id
        if current_user and isinstance(current_user, dict) and current_user.get("id"):
            query = query.eq("user_id", current_user.get("id"))
        result = query.single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        return {"data": result.data}
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{planejamento_id}")
async def atualizar_planejamento(planejamento_id: str, payload: PlanejamentoUpdate, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        dados = payload.dict(exclude_unset=True)
        query = supabase.table("planejamentos").update(dados).eq("id", planejamento_id)
        # filtro por usuário quando houver user_id
        if current_user and isinstance(current_user, dict) and current_user.get("id"):
            query = query.eq("user_id", current_user.get("id"))
        result = query.execute()
        return {"data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# ============================
@router.post("/{planejamento_id}/contexto")
async def adicionar_contexto(planejamento_id: str, payload: ContextoPayload):
    try:
        supabase = get_supabase_client()
        dados = {
            "planejamento_id": planejamento_id,
            "reunioes_ids": payload.reunioes_ids or [],
            "arquivos": payload.arquivos or [],
            "texto_livre": payload.texto_livre,
        }
        result = supabase.table("planejamento_contexto").insert(dados).execute()
        return {"data": result.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/gerar")
async def gerar_planejamento(planejamento_id: str):
    return {"message": "Geração de planejamento em desenvolvimento"}


@router.post("/{planejamento_id}/artefatos")
async def gerar_artefatos(planejamento_id: str):
    return {"message": "Geração de artefatos em desenvolvimento"}


@router.get("/{planejamento_id}/preplanejamento")
async def get_preplanejamento(planejamento_id: str):
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        conteudo = result.data.get('conteudo', {}) if result.data else {}
        preplan = conteudo.get('preplanejamento', {})
        return {"data": preplan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# ============================
class PrepareRequest(BaseModel):
    reunioes_ids: Optional[List[str]] = None
    arquivos: Optional[List[Dict[str, Any]]] = None
    texto_livre: Optional[str] = None


@router.post("/{planejamento_id}/preplanejamento/prepare")
async def prepare_preplanejamento(planejamento_id: str, payload: PrepareRequest):
    try:
        supabase = get_supabase_client()
        
        reunioes_data = []
        if payload.reunioes_ids:
            for reuniao_id in payload.reunioes_ids:
                try:
                    result = supabase.table('transcriptions').select('*').eq('id', reuniao_id).single().execute()
                    if result.data:
                        reunioes_data.append(result.data)
                except:
                    continue
        
        contexto_consolidado = {
            "reunioes": reunioes_data,
            "arquivos": payload.arquivos or [],
            "texto_livre": payload.texto_livre or "",
            "total_reunioes": len(reunioes_data),
            "total_arquivos": len(payload.arquivos or [])
        }
        
        try:
            prompt_contexto = ""
            
            if reunioes_data:
                prompt_contexto += "REUNIÕES ANALISADAS:\n"
                for i, reuniao in enumerate(reunioes_data, 1):
                    prompt_contexto += f"\n{i}. {reuniao.get('title', 'Reunião sem título')}\n"
                    prompt_contexto += f"Cliente: {reuniao.get('client', 'N/A')}\n"
                    prompt_contexto += f"Projeto: {reuniao.get('project', 'N/A')}\n"
                    if reuniao.get('executive_summary'):
                        prompt_contexto += f"Resumo: {reuniao.get('executive_summary')}\n"
                    if reuniao.get('main_points'):
                        prompt_contexto += f"Pontos principais: {', '.join(reuniao.get('main_points', []))}\n"
                    if reuniao.get('action_items'):
                        prompt_contexto += f"Ações: {', '.join(reuniao.get('action_items', []))}\n"
                    prompt_contexto += "\n"
            
            if payload.texto_livre:
                prompt_contexto += f"\nCONTEXTO ADICIONAL:\n{payload.texto_livre}\n"
            
            prompt = f"""
Com base no contexto fornecido, crie um resumo executivo estruturado para planejamento estratégico.

{prompt_contexto}

Gere um resumo que inclua:
1. Situação atual da empresa/projeto
2. Principais desafios identificados
3. Oportunidades de melhoria
4. Objetivos estratégicos sugeridos
5. Próximos passos recomendados

Formato: Texto corrido, máximo 500 palavras, em português brasileiro.
"""
            
            resumo_ia = generate_ai_completion(prompt, max_tokens=1000)
            
            prompt_bullets = f"""
Com base no contexto e resumo:

{prompt_contexto}

RESUMO GERADO:
{resumo_ia}

Extraia os 5-8 pontos mais importantes em formato de bullet points para o planejamento estratégico.
Formato: Lista simples, um ponto por linha, começando com "•"
"""
            
            bullets_ia = generate_ai_completion(prompt_bullets, max_tokens=500)
            bullets_list = [line.strip().replace("•", "").strip() for line in bullets_ia.split("\n") if line.strip() and not line.strip().startswith("•")]
            
        except Exception as e:
            print(f"Erro na geração IA: {e}")
            resumo_ia = "Resumo não pôde ser gerado automaticamente. Por favor, adicione manualmente."
            bullets_list = ["Definir objetivos estratégicos", "Analisar situação atual", "Identificar oportunidades"]
        
        preplan_data = {
            "contexto": contexto_consolidado,
            "resumo_geral": resumo_ia,
            "bulletpoints": bullets_list,
            "sources": {
                "reunioes_ids": payload.reunioes_ids or [],
                "arquivos": payload.arquivos or [],
                "texto_livre": payload.texto_livre or ""
            },
            "status": "prepared",
            "created_at": dt.datetime.now().isoformat()
        }
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        conteudo_atual = result.data.get('conteudo', {}) if result.data else {}
        conteudo_atual['preplanejamento'] = preplan_data
        
        supabase.table('planejamentos').update({
            'conteudo': conteudo_atual,
            'status': 'draft'
        }).eq('id', planejamento_id).execute()
        
        return {"data": preplan_data, "message": "Pré-planejamento preparado com sucesso"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# ============================
class ChatSend(BaseModel):
    message: str

class GerarPerguntasRequest(BaseModel):
    num_perguntas: int = 5

class ProcessAnswersRequest(BaseModel):
    respostas: List[Dict[str, Any]]

class PlanoVersion(BaseModel):
    titulo: str
    conteudo: Dict[str, Any]
    observacoes: Optional[str] = None

class SavePlanoVersionRequest(BaseModel):
    version: PlanoVersion


@router.post("/{planejamento_id}/perguntas/gerar")
async def gerar_perguntas(planejamento_id: str, payload: GerarPerguntasRequest):
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        conteudo = result.data.get('conteudo', {}) if result.data else {}
        preplan = conteudo.get('preplanejamento', {})
        
        try:
            contexto = preplan.get('resumo_geral', '')
            bullets = preplan.get('bulletpoints', [])
            
            prompt = f"""
Com base no contexto do planejamento estratégico:

RESUMO: {contexto}

PONTOS PRINCIPAIS: {', '.join(bullets)}

Gere {payload.num_perguntas} perguntas estratégicas essenciais para aprofundar o planejamento.
As perguntas devem ser:
- Específicas e direcionadas
- Focadas em objetivos, recursos, prazos e resultados
- Que ajudem a definir KPIs e métricas
- Em português brasileiro

Formato: Uma pergunta por linha, numeradas de 1 a {payload.num_perguntas}.
"""
            
            perguntas_ia = generate_ai_completion(prompt, max_tokens=800)
            perguntas_list = []
            
            for line in perguntas_ia.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-')):
                    pergunta = re.sub(r'^\d+\.?\s*', '', line)
                    pergunta = re.sub(r'^-\s*', '', pergunta)
                    if pergunta:
                        perguntas_list.append(pergunta.strip())
            
            while len(perguntas_list) < payload.num_perguntas:
                perguntas_list.append("Qual é o principal objetivo estratégico a ser alcançado?")
            
            perguntas_list = perguntas_list[:payload.num_perguntas]
            
        except Exception as e:
            print(f"Erro na geração de perguntas: {e}")
            perguntas_list = [
                "Qual é o principal objetivo estratégico a ser alcançado?",
                "Quais recursos estão disponíveis para este planejamento?",
                "Qual é o prazo esperado para implementação?",
                "Como será medido o sucesso deste planejamento?",
                "Quais são os principais riscos identificados?"
            ][:payload.num_perguntas]
        
        perguntas_data = []
        for i, pergunta in enumerate(perguntas_list, 1):
            pergunta_obj = {
                "id": str(uuid.uuid4()),
                "planejamento_id": planejamento_id,
                "pergunta": pergunta,
                "ordem": i,
                "created_at": dt.datetime.now().isoformat()
            }
            perguntas_data.append(pergunta_obj)
            
            supabase.table('planejamento_perguntas').insert(pergunta_obj).execute()
        
        return {"data": perguntas_data, "message": f"{len(perguntas_data)} perguntas geradas com sucesso"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# ============================
class FrameworksSave(BaseModel):
    frameworks_escolhidos: List[str]


@router.get("/{planejamento_id}/frameworks")
async def get_frameworks_sugeridos(planejamento_id: str):
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        conteudo = result.data.get('conteudo', {}) if result.data else {}
        preplan = conteudo.get('preplanejamento', {})
        
        try:
            contexto = preplan.get('resumo_geral', '')
            bullets = preplan.get('bulletpoints', [])
            
            prompt = f"""
Com base no contexto do planejamento estratégico:

RESUMO: {contexto}

PONTOS PRINCIPAIS: {', '.join(bullets)}

Sugira 5-7 frameworks de gestão estratégica mais adequados para este contexto.
Para cada framework, forneça:
- Nome do framework
- Breve descrição (1-2 frases)
- Por que é adequado para este caso

Frameworks a considerar: OKR, BSC, SWOT, Canvas, Design Thinking, Lean, Agile, etc.

Formato JSON:
[
  {
    "nome": "Nome do Framework",
    "descricao": "Descrição breve",
    "adequacao": "Por que é adequado"
  }
]
"""
            
            frameworks_ia = generate_ai_completion(prompt, max_tokens=1200)
            
            try:
                frameworks_list = json.loads(frameworks_ia)
            except:
                frameworks_list = [
                    {
                        "nome": "OKR (Objectives and Key Results)",
                        "descricao": "Framework para definir e acompanhar objetivos e resultados-chave",
                        "adequacao": "Ideal para organizações que precisam de clareza em objetivos e métricas"
                    },
                    {
                        "nome": "Balanced Scorecard (BSC)",
                        "descricao": "Sistema de gestão estratégica com perspectivas financeira, cliente, processos e aprendizado",
                        "adequacao": "Adequado para visão holística da performance organizacional"
                    },
                    {
                        "nome": "Análise SWOT",
                        "descricao": "Análise de Forças, Fraquezas, Oportunidades e Ameaças",
                        "adequacao": "Fundamental para diagnóstico estratégico inicial"
                    }
                ]
            
        except Exception as e:
            print(f"Erro na geração de frameworks: {e}")
            frameworks_list = [
                {
                    "nome": "OKR (Objectives and Key Results)",
                    "descricao": "Framework para definir e acompanhar objetivos e resultados-chave",
                    "adequacao": "Ideal para organizações que precisam de clareza em objetivos e métricas"
                },
                {
                    "nome": "Balanced Scorecard (BSC)",
                    "descricao": "Sistema de gestão estratégica com perspectivas financeira, cliente, processos e aprendizado",
                    "adequacao": "Adequado para visão holística da performance organizacional"
                }
            ]
        
        return {"data": frameworks_list}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/respostas/processar")
async def processar_respostas(planejamento_id: str, payload: ProcessAnswersRequest):
    try:
        supabase = get_supabase_client()
        
        for resposta in payload.respostas:
            resposta_obj = {
                "id": str(uuid.uuid4()),
                "planejamento_id": planejamento_id,
                "pergunta_id": resposta.get("pergunta_id"),
                "resposta": resposta.get("resposta"),
                "created_at": dt.datetime.now().isoformat()
            }
            supabase.table('planejamento_respostas').insert(resposta_obj).execute()
        
        # Mantém status permitido pela constraint atual
        supabase.table('planejamentos').update({
            'status': 'draft'
        }).eq('id', planejamento_id).execute()
        
        return {"message": f"{len(payload.respostas)} respostas processadas com sucesso"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/frameworks/save")
async def save_frameworks_escolhidos(planejamento_id: str, payload: FrameworksSave):
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        conteudo = result.data.get('conteudo', {}) if result.data else {}
        conteudo['frameworks_escolhidos'] = payload.frameworks_escolhidos
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"message": "Frameworks salvos com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{planejamento_id}")
async def delete_planejamento(planejamento_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        
        supabase.table('planejamento_contexto').delete().eq('planejamento_id', planejamento_id).execute()
        supabase.table('planejamento_perguntas').delete().eq('planejamento_id', planejamento_id).execute()
        supabase.table('planejamento_respostas').delete().eq('planejamento_id', planejamento_id).execute()
        
        query = supabase.table('planejamentos').delete().eq('id', planejamento_id)
        if current_user and isinstance(current_user, dict) and current_user.get("id"):
            query = query.eq("user_id", current_user.get("id"))
        
        result = query.execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        return {"message": "Planejamento deletado com sucesso"}
        
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/thread")
async def get_or_create_thread(planejamento_id: str):
    try:
        supabase = get_supabase_client()
        pj = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not pj.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = pj.data.get('conteudo', {})
        thread_id = conteudo.get('thread_id')
        
        if not thread_id:
            thread_id = f"thread_{uuid.uuid4()}"
            conteudo['thread_id'] = thread_id
            supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"thread_id": thread_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/preplanejamento/refinar")
async def refinar_preplanejamento(planejamento_id: str, message: str = Body(..., embed=True)):
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        preplan = conteudo.get('preplanejamento', {})
        
        try:
            resumo_atual = preplan.get('resumo_geral', '')
            bullets_atuais = preplan.get('bulletpoints', [])
            
            prompt = f"""
CONTEXTO ATUAL DO PLANEJAMENTO:
Resumo: {resumo_atual}
Pontos principais: {', '.join(bullets_atuais)}

SOLICITAÇÃO DE REFINAMENTO:
{message}

Com base na solicitação, refine o planejamento estratégico mantendo a estrutura mas incorporando as melhorias solicitadas.

Retorne em formato JSON:
{{
  "resumo_geral": "Resumo refinado...",
  "bulletpoints": ["Ponto 1", "Ponto 2", "..."]
}}
"""
            
            refinamento_ia = generate_ai_completion(prompt, max_tokens=1500)
            
            try:
                refinamento_data = json.loads(refinamento_ia)
                novo_resumo = refinamento_data.get('resumo_geral', resumo_atual)
                novos_bullets = refinamento_data.get('bulletpoints', bullets_atuais)
            except:
                novo_resumo = resumo_atual
                novos_bullets = bullets_atuais
            
        except Exception as e:
            print(f"Erro no refinamento IA: {e}")
            novo_resumo = preplan.get('resumo_geral', '')
            novos_bullets = preplan.get('bulletpoints', [])
        
        preplan['resumo_geral'] = novo_resumo
        preplan['bulletpoints'] = novos_bullets
        preplan['last_refined'] = dt.datetime.now().isoformat()
        preplan['refinement_history'] = preplan.get('refinement_history', [])
        preplan['refinement_history'].append({
            'message': message,
            'timestamp': dt.datetime.now().isoformat()
        })
        
        conteudo['preplanejamento'] = preplan
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {
            "data": preplan,
            "message": "Pré-planejamento refinado com sucesso"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/preplanejamento/save")
async def save_preplanejamento(planejamento_id: str, payload: PreplanSave):
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        conteudo = result.data.get('conteudo', {}) if result.data else {}
        
        preplan = conteudo.get('preplanejamento', {})
        if payload.resumo_geral is not None:
            preplan['resumo_geral'] = payload.resumo_geral
        if payload.bulletpoints is not None:
            preplan['bulletpoints'] = payload.bulletpoints
        if payload.sources is not None:
            preplan['sources'] = payload.sources
        
        preplan['last_updated'] = dt.datetime.now().isoformat()
        conteudo['preplanejamento'] = preplan
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"message": "Pré-planejamento salvo com sucesso", "data": preplan}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# ============================

def _get_or_init_plano(planejamento_id: str):
    """Busca ou inicializa estrutura do plano"""
    supabase = get_supabase_client()
    result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
    conteudo = result.data.get('conteudo', {}) if result.data else {}
    
    if 'plano' not in conteudo:
        conteudo['plano'] = {}
    
    return conteudo


@router.get("/{planejamento_id}/plano")
async def get_plano(planejamento_id: str):
    try:
        conteudo = _get_or_init_plano(planejamento_id)
        plano = conteudo.get('plano', {})
        
        return {
            "data": plano,
            "sections_count": len(plano.get('sections', {})),
            "status": plano.get('status', 'not_started')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/plano/versions")
async def save_plano_version(planejamento_id: str, payload: SavePlanoVersionRequest):
    try:
        supabase = get_supabase_client()
        conteudo = _get_or_init_plano(planejamento_id)
        
        version_id = str(uuid.uuid4())
        version_data = {
            "id": version_id,
            "titulo": payload.version.titulo,
            "conteudo": payload.version.conteudo,
            "observacoes": payload.version.observacoes,
            "created_at": dt.datetime.now().isoformat()
        }
        
        if 'versions' not in conteudo['plano']:
            conteudo['plano']['versions'] = []
        
        conteudo['plano']['versions'].append(version_data)
        conteudo['plano']['current_version'] = version_id
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"message": "Versão do plano salva com sucesso", "version_id": version_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_specialized_prompt(section_name: str, context: dict) -> str:
    """Retorna prompt especializado para cada seção do planejamento"""
    
    resumo = context.get('resumo_geral', '')
    bullets = context.get('bulletpoints', [])
    frameworks = context.get('frameworks_escolhidos', [])
    
    PLANNING_SECTIONS = {
        "objetivo_roi": f"""
Como especialista em ROI e objetivos estratégicos, analise o contexto:

RESUMO: {resumo}
PONTOS PRINCIPAIS: {', '.join(bullets)}
FRAMEWORKS: {', '.join(frameworks)}

Defina objetivos SMART com ROI esperado:
1. Objetivo principal (específico, mensurável)
2. ROI esperado (% ou valor)
3. Prazo para alcançar
4. Métricas de acompanhamento
5. Justificativa do ROI

Formato: Texto estruturado, máximo 400 palavras.
""",
        
        "deliverables": f"""
Como especialista em gestão de projetos, defina os deliverables:

CONTEXTO: {resumo}
OBJETIVOS: {', '.join(bullets)}

Liste os principais entregáveis:
1. Deliverables primários (3-5 principais)
2. Deliverables secundários (2-3 de apoio)
3. Cronograma de entregas
4. Critérios de aceitação
5. Responsabilidades

Formato: Lista estruturada com detalhes.
""",
        
        "investimento": f"""
Como especialista financeiro, calcule o investimento necessário:

CONTEXTO: {resumo}
ESCOPO: {', '.join(bullets)}

Estruture o investimento:
1. Investimento inicial (CAPEX)
2. Custos operacionais (OPEX)
3. Recursos humanos
4. Tecnologia e ferramentas
5. Contingência (10-15%)
6. Total estimado

Formato: Tabela com valores e justificativas.
""",
        
        "situacao_atual": f"""
Como analista estratégico, faça diagnóstico da situação atual:

CONTEXTO: {resumo}
PONTOS: {', '.join(bullets)}

Analise:
1. Estado atual dos processos
2. Recursos disponíveis
3. Capacidades existentes
4. Gaps identificados
5. Baseline para medição

Formato: Análise estruturada, máximo 350 palavras.
""",
        
        "pain_points": f"""
Como consultor de processos, identifique pain points:

SITUAÇÃO: {resumo}
CONTEXTO: {', '.join(bullets)}

Mapeie:
1. Principais dores identificadas
2. Impacto de cada pain point
3. Frequência/intensidade
4. Causas raiz
5. Priorização para resolução

Formato: Lista priorizada com análise.
""",
        
        "impacto_negocio": f"""
Como analista de negócios, avalie o impacto:

CONTEXTO: {resumo}
OBJETIVOS: {', '.join(bullets)}

Analise impactos:
1. Impacto financeiro (receita/custos)
2. Impacto operacional
3. Impacto estratégico
4. Impacto no cliente
5. Riscos e oportunidades

Formato: Análise quantitativa e qualitativa.
""",
        
        "metodologia": f"""
Como especialista em metodologias, defina a abordagem:

PROJETO: {resumo}
FRAMEWORKS: {', '.join(frameworks)}

Estruture:
1. Metodologia principal escolhida
2. Fases do projeto
3. Marcos e checkpoints
4. Ferramentas de gestão
5. Processo de governança

Formato: Metodologia detalhada com fases.
""",
        
        "frameworks": f"""
Como consultor estratégico, detalhe os frameworks:

CONTEXTO: {resumo}
FRAMEWORKS ESCOLHIDOS: {', '.join(frameworks)}

Para cada framework:
1. Como será aplicado
2. Benefícios esperados
3. Recursos necessários
4. Timeline de implementação
5. Métricas de sucesso

Formato: Detalhamento por framework.
""",
        
        "benchmarks": f"""
Como analista de mercado, estabeleça benchmarks:

SETOR/CONTEXTO: {resumo}
OBJETIVOS: {', '.join(bullets)}

Defina:
1. Benchmarks de mercado relevantes
2. Melhores práticas do setor
3. KPIs de referência
4. Gaps vs. mercado
5. Metas aspiracionais

Formato: Comparativo com dados de mercado.
""",
        
        "kpis": f"""
Como especialista em métricas, defina KPIs:

OBJETIVOS: {resumo}
METAS: {', '.join(bullets)}

Estruture KPIs:
1. KPIs primários (3-5 principais)
2. KPIs secundários (5-7 de apoio)
3. Frequência de medição
4. Responsáveis pela coleta
5. Targets e thresholds

Formato: Dashboard de KPIs estruturado.
""",
        
        "timeline_resultados": f"""
Como gerente de projetos, crie timeline:

PROJETO: {resumo}
DELIVERABLES: {', '.join(bullets)}

Estruture:
1. Fases do projeto (com durações)
2. Marcos principais
3. Resultados esperados por fase
4. Dependências críticas
5. Cronograma de 12-18 meses

Formato: Cronograma detalhado com marcos.
""",
        
        "roi_calculos": f"""
Como analista financeiro, calcule ROI detalhado:

INVESTIMENTO: {resumo}
BENEFÍCIOS: {', '.join(bullets)}

Calcule:
1. Investimento total detalhado
2. Benefícios quantificados
3. Payback period
4. ROI por ano (3 anos)
5. VPL e TIR
6. Análise de sensibilidade

Formato: Modelo financeiro completo.
""",
        
        "riscos_mitigacao": f"""
Como especialista em riscos, analise:

PROJETO: {resumo}
CONTEXTO: {', '.join(bullets)}

Identifique:
1. Riscos técnicos
2. Riscos de negócio
3. Riscos operacionais
4. Probabilidade x Impacto
5. Planos de mitigação
6. Planos de contingência

Formato: Matriz de riscos com mitigações.
""",
        
        "recursos_necessarios": f"""
Como especialista em recursos, detalhe necessidades:

ESCOPO: {resumo}
ATIVIDADES: {', '.join(bullets)}

Especifique:
1. Recursos humanos (perfis/quantidade)
2. Recursos tecnológicos
3. Recursos financeiros
4. Recursos físicos/infraestrutura
5. Cronograma de alocação

Formato: Plano de recursos detalhado.
""",
        
        "stakeholders": f"""
Como especialista em stakeholders, mapeie:

PROJETO: {resumo}
IMPACTOS: {', '.join(bullets)}

Analise:
1. Stakeholders primários
2. Stakeholders secundários
3. Nível de influência/interesse
4. Estratégias de engajamento
5. Plano de comunicação

Formato: Matriz de stakeholders com estratégias.
""",
        
        "comunicacao": f"""
Como especialista em comunicação, crie plano:

PROJETO: {resumo}
STAKEHOLDERS: {', '.join(bullets)}

Estruture:
1. Objetivos de comunicação
2. Públicos-alvo
3. Mensagens-chave
4. Canais de comunicação
5. Frequência e responsáveis
6. Métricas de efetividade

Formato: Plano de comunicação completo.
""",
        
        "governanca": f"""
Como especialista em governança, defina estrutura:

PROJETO: {resumo}
COMPLEXIDADE: {', '.join(bullets)}

Estabeleça:
1. Estrutura de governança
2. Papéis e responsabilidades
3. Processos de decisão
4. Comitês e fóruns
5. Escalação e aprovações
6. Controles e auditorias

Formato: Modelo de governança detalhado.
""",
        
        "sustentabilidade": f"""
Como especialista em sustentabilidade, analise:

PROJETO: {resumo}
IMPACTOS: {', '.join(bullets)}

Avalie:
1. Impactos ambientais
2. Responsabilidade social
3. Governança corporativa (ESG)
4. Sustentabilidade financeira
5. Indicadores de sustentabilidade
6. Planos de melhoria contínua

Formato: Análise ESG completa.
""",
        
        "inovacao": f"""
Como especialista em inovação, identifique oportunidades:

CONTEXTO: {resumo}
OBJETIVOS: {', '.join(bullets)}

Explore:
1. Oportunidades de inovação
2. Tecnologias emergentes aplicáveis
3. Processos de inovação
4. Parcerias estratégicas
5. Investimento em P&D
6. Roadmap de inovação

Formato: Estratégia de inovação estruturada.
""",
        
        "transformacao_digital": f"""
Como especialista em transformação digital, analise:

SITUAÇÃO ATUAL: {resumo}
OBJETIVOS: {', '.join(bullets)}

Defina:
1. Maturidade digital atual
2. Visão de futuro digital
3. Tecnologias prioritárias
4. Roadmap de transformação
5. Capacitação necessária
6. Métricas de progresso digital

Formato: Plano de transformação digital.
""",
        
        "capacitacao": f"""
Como especialista em desenvolvimento humano, planeje:

PROJETO: {resumo}
NECESSIDADES: {', '.join(bullets)}

Estruture:
1. Gap de competências
2. Plano de capacitação
3. Métodos de treinamento
4. Cronograma de desenvolvimento
5. Avaliação de efetividade
6. Investimento em pessoas

Formato: Plano de desenvolvimento completo.
""",
        
        "monitoramento": f"""
Como especialista em monitoramento, crie sistema:

OBJETIVOS: {resumo}
KPIS: {', '.join(bullets)}

Desenvolva:
1. Sistema de monitoramento
2. Dashboards e relatórios
3. Frequência de acompanhamento
4. Responsáveis por área
5. Processo de revisão
6. Ações corretivas

Formato: Sistema de monitoramento completo.
""",
        
        "melhorias_continuas": f"""
Como especialista em melhoria contínua, estabeleça:

PROCESSOS: {resumo}
OPORTUNIDADES: {', '.join(bullets)}

Defina:
1. Metodologia de melhoria contínua
2. Ciclos de revisão
3. Indicadores de performance
4. Processo de sugestões
5. Implementação de melhorias
6. Cultura de melhoria

Formato: Programa de melhoria contínua.
""",
        
        "conclusoes": f"""
Como consultor sênior, consolide as conclusões:

PROJETO COMPLETO: {resumo}
PRINCIPAIS PONTOS: {', '.join(bullets)}

Sintetize:
1. Resumo executivo do plano
2. Principais recomendações
3. Próximos passos críticos
4. Fatores críticos de sucesso
5. Considerações finais
6. Call to action

Formato: Conclusões executivas estruturadas.
"""
    }
    
    return PLANNING_SECTIONS.get(section_name, f"Analise o contexto: {resumo} e desenvolva conteúdo para a seção {section_name}.")


def generate_with_claude(prompt: str, max_tokens: int = 4000) -> str:
    """Gera conteúdo usando Anthropic Claude"""
    try:
        import anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY não configurada")
        
        client = anthropic.Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=max_tokens,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text
        
    except Exception as e:
        print(f"Erro ao gerar com Claude: {e}")
        raise


def generate_with_gemini(prompt: str, max_tokens: int = 4000) -> str:
    """Gera conteúdo usando Google Gemini"""
    try:
        import google.generativeai as genai
        
        api_key = os.getenv("GOOGLE_AI_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_AI_API_KEY não configurada")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        print(f"Erro ao gerar com Gemini: {e}")
        raise


def get_ai_client_for_planning():
    """Retorna o cliente de IA configurado para planejamento.
    Forçamos Anthropic conforme requisito do projeto."""
    return "anthropic"


def generate_ai_completion(prompt: str, max_tokens: int = 4000) -> str:
    """Gera conteúdo usando apenas Anthropic (sem fallback)."""
    try:
        return generate_with_claude(prompt, max_tokens)
    except Exception as e:
        print(f"Erro na geração de IA (anthropic): {e}")
        raise


PLANNING_SECTIONS = [
    "objetivo_roi", "deliverables", "investimento", "situacao_atual", "pain_points",
    "impacto_negocio", "metodologia", "frameworks", "benchmarks", "kpis",
    "timeline_resultados", "roi_calculos", "riscos_mitigacao", "recursos_necessarios",
    "stakeholders", "comunicacao", "governanca", "sustentabilidade", "inovacao",
    "transformacao_digital", "capacitacao", "monitoramento", "melhorias_continuas", "conclusoes"
]


def generate_specialized_section(section_name: str, context: dict, planejamento_id: str) -> dict:
    """Gera uma seção especializada do planejamento"""
    try:
        prompt = get_specialized_prompt(section_name, context)
        
        content = generate_ai_completion(prompt, max_tokens=4000)
        
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        conteudo = result.data.get('conteudo', {}) if result.data else {}
        
        if 'plano' not in conteudo:
            conteudo['plano'] = {}
        if 'sections' not in conteudo['plano']:
            conteudo['plano']['sections'] = {}
        if 'progress' not in conteudo['plano']:
            conteudo['plano']['progress'] = {}
        
        conteudo['plano']['sections'][section_name] = {
            'content': content,
            'generated_at': dt.datetime.now().isoformat(),
            'status': 'completed'
        }
        
        completed_sections = len([s for s in conteudo['plano']['sections'].values() if s.get('status') == 'completed'])
        total_sections = len(PLANNING_SECTIONS)
        progress_percentage = (completed_sections / total_sections) * 100
        
        conteudo['plano']['progress'] = {
            'completed_sections': completed_sections,
            'total_sections': total_sections,
            'percentage': progress_percentage,
            'current_section': section_name,
            'last_updated': dt.datetime.now().isoformat()
        }
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {
            'section_name': section_name,
            'content': content,
            'status': 'completed',
            'progress': progress_percentage
        }
        
    except Exception as e:
        print(f"Erro ao gerar seção {section_name}: {e}")
        return {
            'section_name': section_name,
            'content': f"Erro ao gerar conteúdo para {section_name}: {str(e)}",
            'status': 'error',
            'error': str(e)
        }


def _get_section_specific_instructions(section_name: str) -> str:
    """Retorna instruções específicas para cada seção"""
    instructions = {
        "objetivo_roi": "Foque em objetivos SMART e cálculos de ROI precisos com métricas quantificáveis.",
        "deliverables": "Liste entregáveis específicos com critérios de aceitação claros e cronograma.",
        "investimento": "Detalhe todos os custos: CAPEX, OPEX, recursos humanos, tecnologia e contingência.",
        "situacao_atual": "Faça diagnóstico preciso da situação atual com baseline para medições futuras.",
        "pain_points": "Identifique dores específicas com impacto quantificado e priorização clara.",
        "impacto_negocio": "Quantifique impactos financeiros, operacionais e estratégicos com dados concretos.",
        "metodologia": "Detalhe a metodologia escolhida com fases, marcos e processo de governança.",
        "frameworks": "Explique como cada framework será aplicado com timeline e métricas de sucesso.",
        "benchmarks": "Use dados de mercado reais e estabeleça comparativos com melhores práticas.",
        "kpis": "Defina KPIs SMART com targets, frequência de medição e responsáveis.",
        "timeline_resultados": "Crie cronograma detalhado com marcos, dependências e resultados esperados.",
        "roi_calculos": "Apresente modelo financeiro completo com VPL, TIR e análise de sensibilidade.",
        "riscos_mitigacao": "Use matriz de riscos com probabilidade x impacto e planos de mitigação.",
        "recursos_necessarios": "Detalhe todos os recursos necessários com cronograma de alocação.",
        "stakeholders": "Mapeie stakeholders com matriz de influência/interesse e estratégias específicas.",
        "comunicacao": "Crie plano de comunicação com públicos, mensagens, canais e frequência.",
        "governanca": "Estabeleça estrutura de governança com papéis, responsabilidades e processos.",
        "sustentabilidade": "Analise impactos ESG com indicadores e planos de melhoria contínua.",
        "inovacao": "Identifique oportunidades de inovação com roadmap e investimentos em P&D.",
        "transformacao_digital": "Avalie maturidade digital e crie roadmap de transformação tecnológica.",
        "capacitacao": "Identifique gaps de competência e crie plano de desenvolvimento estruturado.",
        "monitoramento": "Desenvolva sistema de monitoramento com dashboards e processo de revisão.",
        "melhorias_continuas": "Estabeleça metodologia de melhoria contínua com ciclos e indicadores.",
        "conclusoes": "Sintetize recomendações principais com próximos passos e fatores críticos."
    }
    
    return instructions.get(section_name, "Desenvolva conteúdo detalhado e estruturado para esta seção.")


def consolidate_sections(sections: dict, context: dict) -> str:
    """Consolida todas as seções em um plano estratégico coeso"""
    try:
        consolidated_content = "# PLANO ESTRATÉGICO CONSOLIDADO\n\n"
        
        section_titles = {
            "objetivo_roi": "1. OBJETIVOS E ROI",
            "deliverables": "2. DELIVERABLES",
            "investimento": "3. INVESTIMENTO NECESSÁRIO",
            "situacao_atual": "4. SITUAÇÃO ATUAL",
            "pain_points": "5. PAIN POINTS IDENTIFICADOS",
            "impacto_negocio": "6. IMPACTO NO NEGÓCIO",
            "metodologia": "7. METODOLOGIA",
            "frameworks": "8. FRAMEWORKS APLICADOS",
            "benchmarks": "9. BENCHMARKS DE MERCADO",
            "kpis": "10. INDICADORES (KPIs)",
            "timeline_resultados": "11. CRONOGRAMA E RESULTADOS",
            "roi_calculos": "12. CÁLCULOS DE ROI",
            "riscos_mitigacao": "13. RISCOS E MITIGAÇÃO",
            "recursos_necessarios": "14. RECURSOS NECESSÁRIOS",
            "stakeholders": "15. STAKEHOLDERS",
            "comunicacao": "16. PLANO DE COMUNICAÇÃO",
            "governanca": "17. GOVERNANÇA",
            "sustentabilidade": "18. SUSTENTABILIDADE (ESG)",
            "inovacao": "19. INOVAÇÃO",
            "transformacao_digital": "20. TRANSFORMAÇÃO DIGITAL",
            "capacitacao": "21. CAPACITAÇÃO",
            "monitoramento": "22. MONITORAMENTO",
            "melhorias_continuas": "23. MELHORIA CONTÍNUA",
            "conclusoes": "24. CONCLUSÕES E PRÓXIMOS PASSOS"
        }
        
        for section_name in PLANNING_SECTIONS:
            if section_name in sections:
                title = section_titles.get(section_name, section_name.upper())
                content = sections[section_name].get('content', '')
                consolidated_content += f"\n## {title}\n\n{content}\n\n"
        
        consolidation_prompt = f"""
Como consultor estratégico sênior, revise e melhore este plano estratégico consolidado:

{consolidated_content}

CONTEXTO ORIGINAL:
{context.get('resumo_geral', '')}

Melhore o plano:
1. Garanta coesão entre seções
2. Elimine redundâncias
3. Fortaleça conexões lógicas
4. Melhore clareza e objetividade
5. Mantenha estrutura e conteúdo técnico

Retorne o plano melhorado mantendo toda a estrutura e seções.
"""
        
        improved_plan = generate_ai_completion(consolidation_prompt, max_tokens=4000)
        
        return improved_plan
        
    except Exception as e:
        print(f"Erro na consolidação: {e}")
        return consolidated_content


@router.post("/{planejamento_id}/plano/gerar-multi-agent")
async def gerar_plano_multi_agent(planejamento_id: str):
    """Gera plano estratégico completo usando sistema multi-agent com 24 seções especializadas"""
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        preplan = conteudo.get('preplanejamento', {})
        
        if 'plano' not in conteudo:
            conteudo['plano'] = {}
        
        conteudo['plano']['status'] = 'generating'
        conteudo['plano']['started_at'] = dt.datetime.now().isoformat()
        conteudo['plano']['sections'] = {}
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        generated_sections = {}
        
        for i, section_name in enumerate(PLANNING_SECTIONS, 1):
            try:
                print(f"Gerando seção {i}/24: {section_name}")
                
                conteudo['plano']['progress'] = {
                    'current_section': section_name,
                    'completed_sections': i - 1,
                    'total_sections': len(PLANNING_SECTIONS),
                    'percentage': ((i - 1) / len(PLANNING_SECTIONS)) * 100,
                    'status': f'Gerando {section_name}...'
                }
                supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
                
                section_result = generate_specialized_section(section_name, preplan, planejamento_id)
                generated_sections[section_name] = section_result
                
                import time
                time.sleep(1)
                
            except Exception as section_error:
                print(f"Erro na seção {section_name}: {section_error}")
                generated_sections[section_name] = {
                    'content': f"Erro ao gerar {section_name}: {str(section_error)}",
                    'status': 'error',
                    'error': str(section_error)
                }
        
        print("Consolidando seções...")
        try:
            consolidated_plan = consolidate_sections(generated_sections, preplan)
        except Exception as consolidation_error:
            # Fallback: consolidação básica sem IA para evitar 500 e garantir persistência
            print(f"Erro na consolidação via IA: {consolidation_error}")
            consolidated_parts = []
            for s_name in PLANNING_SECTIONS:
                if s_name in generated_sections:
                    s_content = generated_sections[s_name].get('content', '')
                    consolidated_parts.append(f"## {s_name.replace('_', ' ').title()}\n\n{s_content}")
            consolidated_plan = "\n\n".join(consolidated_parts)
        
        conteudo['plano']['consolidated_content'] = consolidated_plan
        conteudo['plano']['status'] = 'completed'
        conteudo['plano']['completed_at'] = dt.datetime.now().isoformat()
        conteudo['plano']['progress'] = {
            'completed_sections': len(PLANNING_SECTIONS),
            'total_sections': len(PLANNING_SECTIONS),
            'percentage': 100,
            'status': 'Concluído'
        }
        
        # Persistência: atualizar apenas o conteudo (evita violar CHECK do status)
        try:
            supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        except Exception as update_error_2:
            print(f"Falha ao salvar conteúdo do plano no Supabase: {update_error_2}")
        
        return {
            "message": "Plano estratégico gerado com sucesso",
            "sections_generated": len(generated_sections),
            "status": "completed",
            "progress": 100
        }
        
    except Exception as e:
        # Evita 500: salva erro e retorna payload informativo
        try:
            supabase = get_supabase_client()
            result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
            conteudo = result.data.get('conteudo', {}) if result.data else {}

            if 'plano' not in conteudo:
                conteudo['plano'] = {}

            conteudo['plano']['status'] = 'error'
            conteudo['plano']['error'] = str(e)
            conteudo['plano']['error_at'] = dt.datetime.now().isoformat()

            try:
                supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
            except Exception as update_error:
                print(f"Falha ao salvar erro no Supabase: {update_error}")
        except Exception as outer:
            print(f"Erro no handler de exceção: {outer}")

        return {
            "message": "Geração finalizada com erro parcial. Verifique o conteúdo salvo.",
            "status": "error"
        }


@router.get("/{planejamento_id}/plano/progress")
async def get_generation_progress(planejamento_id: str):
    """Retorna o progresso da geração do plano"""
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        plano = conteudo.get('plano', {})
        progress = plano.get('progress', {})
        
        return {
            "data": progress,
            "progress": progress,  # compat com front que espera progress.status
            "status": plano.get('status', 'not_started'),
            "sections_completed": progress.get('completed_sections', 0),
            "total_sections": progress.get('total_sections', len(PLANNING_SECTIONS))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{planejamento_id}/plano/sections")
async def get_planning_sections(planejamento_id: str):
    """Retorna todas as seções do plano com seus conteúdos"""
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        plano = conteudo.get('plano', {})
        sections = plano.get('sections', {})

        # Aliases para compatibilidade com o front (mesmo conteúdo, chaves esperadas)
        alias_map = {
            "objetivo_principal_roi": "objetivo_roi",
            "deliverables_marcos": "deliverables",
            "investimento_timeline": "timeline_resultados",
            "impacto_no_negocio": "impacto_negocio",
            "selecao_de_frameworks": "frameworks",
            "complementaridade": "metodologia",
            "adaptacoes": "riscos_mitigacao",
            "aplicacao_pratica": "deliverables",
            "integracao": "metodologia",
            "sequenciamento": "timeline_resultados"
        }
        aliased_sections = dict(sections)
        for alias_key, source_key in alias_map.items():
            if source_key in sections and alias_key not in aliased_sections:
                aliased_sections[alias_key] = sections[source_key]

        return {
            "data": aliased_sections,
            "consolidated_content": plano.get('consolidated_content', ''),
            "total_sections": len(aliased_sections)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{planejamento_id}/plano/sections/{section_name}")
async def update_section_content(planejamento_id: str, section_name: str, content: str = Body(..., embed=True)):
    """Atualiza o conteúdo de uma seção específica"""
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        
        if 'plano' not in conteudo:
            conteudo['plano'] = {}
        if 'sections' not in conteudo['plano']:
            conteudo['plano']['sections'] = {}
        
        conteudo['plano']['sections'][section_name] = {
            'content': content,
            'updated_at': dt.datetime.now().isoformat(),
            'status': 'manually_updated'
        }
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"message": f"Seção {section_name} atualizada com sucesso"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/plano/consolidar")
async def consolidar_secoes(planejamento_id: str):
    """Reconsolida todas as seções em um plano coeso"""
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        plano = conteudo.get('plano', {})
        sections = plano.get('sections', {})
        preplan = conteudo.get('preplanejamento', {})
        
        consolidated_content = consolidate_sections(sections, preplan)
        
        conteudo['plano']['consolidated_content'] = consolidated_content
        conteudo['plano']['last_consolidated'] = dt.datetime.now().isoformat()
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"message": "Plano reconsolidado com sucesso", "content": consolidated_content}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/plano/regenerate")
async def gerar_plano(planejamento_id: str):
    """Alias para gerar_plano_multi_agent para compatibilidade"""
    return await gerar_plano_multi_agent(planejamento_id)


# ============================
# ============================

class PreApresentacaoSave(BaseModel):
    storyline: Optional[str] = None
    slides_content: Optional[List[Dict[str, Any]]] = None
    observacoes: Optional[str] = None


def _build_pre_apresentacao_prompt(plano_content: str, context: dict) -> str:
    """Constrói prompt para geração da pré-apresentação"""
    
    resumo = context.get('resumo_geral', '')
    bullets = context.get('bulletpoints', [])
    
    return f"""
Como especialista em apresentações executivas, crie uma pré-apresentação estratégica baseada no plano completo.

CONTEXTO ORIGINAL:
{resumo}

PONTOS PRINCIPAIS:
{', '.join(bullets)}

PLANO ESTRATÉGICO COMPLETO:
{plano_content[:3000]}...

Crie uma apresentação executiva com:

1. STORYLINE (narrativa principal):
   - Abertura impactante
   - Desenvolvimento lógico
   - Fechamento com call-to-action

2. ESTRUTURA DE SLIDES (10-15 slides):
   - Slide 1: Título e contexto
   - Slide 2: Situação atual e desafios
   - Slide 3: Objetivos estratégicos
   - Slide 4: Solução proposta
   - Slide 5: Investimento e ROI
   - Slide 6: Timeline e marcos
   - Slide 7: Riscos e mitigações
   - Slide 8: Recursos necessários
   - Slide 9: KPIs e monitoramento
   - Slide 10: Próximos passos
   - Slides adicionais conforme necessário

Para cada slide, forneça:
- Título do slide
- Conteúdo principal (bullet points)
- Elementos visuais sugeridos
- Notas do apresentador

Formato JSON:
{{
  "storyline": "Narrativa principal da apresentação...",
  "slides": [
    {{
      "numero": 1,
      "titulo": "Título do Slide",
      "conteudo": ["Ponto 1", "Ponto 2", "Ponto 3"],
      "elementos_visuais": "Descrição dos elementos visuais",
      "notas_apresentador": "Notas para o apresentador"
    }}
  ]
}}
"""


@router.get("/{planejamento_id}/plano/pre-apresentacao")
async def get_pre_apresentacao(planejamento_id: str):
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        pre_apresentacao = conteudo.get('pre_apresentacao', {})
        
        return {"data": pre_apresentacao}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/plano/pre-apresentacao/save")
async def save_pre_apresentacao(planejamento_id: str, payload: PreApresentacaoSave):
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        conteudo = result.data.get('conteudo', {}) if result.data else {}
        
        pre_apresentacao = conteudo.get('pre_apresentacao', {})
        if payload.storyline is not None:
            pre_apresentacao['storyline'] = payload.storyline
        if payload.slides_content is not None:
            pre_apresentacao['slides_content'] = payload.slides_content
        if payload.observacoes is not None:
            pre_apresentacao['observacoes'] = payload.observacoes
        
        pre_apresentacao['last_updated'] = dt.datetime.now().isoformat()
        conteudo['pre_apresentacao'] = pre_apresentacao
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"message": "Pré-apresentação salva com sucesso"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{planejamento_id}/plano/pre-apresentacao/versoes")
async def create_pre_apresentacao_version(planejamento_id: str, current_user: dict = Depends(get_current_user)):
    try:
        supabase = get_supabase_client()
        pj = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not pj.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = pj.data.get('conteudo', {})
        pre_apresentacao = conteudo.get('pre_apresentacao', {})
        
        version_id = str(uuid.uuid4())
        version_data = {
            "id": version_id,
            "content": pre_apresentacao,
            "created_at": dt.datetime.now().isoformat(),
            "created_by": current_user.get("id") if current_user else None
        }
        
        if 'versions' not in pre_apresentacao:
            pre_apresentacao['versions'] = []
        
        pre_apresentacao['versions'].append(version_data)
        conteudo['pre_apresentacao'] = pre_apresentacao
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        return {"message": "Versão criada com sucesso", "version_id": version_id}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{planejamento_id}/plano/pre-apresentacao/progress")
async def get_pre_apresentacao_progress(planejamento_id: str):
    try:
        supabase = get_supabase_client()
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        pre_apresentacao = conteudo.get('pre_apresentacao', {})
        progress = pre_apresentacao.get('progress', {})
        
        return {
            "data": progress,
            "status": pre_apresentacao.get('status', 'not_started')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================
# ============================

def _generate_prez_storyline(plano_content: str, context: dict) -> str:
    """Gera storyline da apresentação"""
    prompt = f"""
Como storyteller executivo, crie uma narrativa envolvente para apresentação estratégica.

CONTEXTO: {context.get('resumo_geral', '')}
PLANO: {plano_content[:2000]}...

Crie storyline com:
1. Hook inicial (problema/oportunidade)
2. Desenvolvimento (solução/estratégia)  
3. Clímax (resultados/benefícios)
4. Call-to-action (próximos passos)

Máximo 300 palavras, tom executivo e persuasivo.
"""
    
    return generate_ai_completion(prompt, max_tokens=800)


def _generate_prez_section(section_name: str, plano_content: str, context: dict) -> dict:
    """Gera uma seção específica da apresentação"""
    
    section_prompts = {
        "titulo": "Crie título impactante e subtítulo para a apresentação estratégica",
        "situacao_atual": "Resuma situação atual e principais desafios em 3-4 bullet points",
        "objetivos": "Liste objetivos estratégicos principais com métricas específicas",
        "solucao": "Descreva solução proposta de forma clara e convincente",
        "investimento_roi": "Apresente investimento necessário e ROI esperado com dados",
        "timeline": "Mostre cronograma principal com marcos críticos",
        "riscos": "Identifique principais riscos e estratégias de mitigação",
        "recursos": "Liste recursos críticos necessários para sucesso",
        "kpis": "Defina KPIs principais para monitoramento",
        "proximos_passos": "Detalhe próximos passos imediatos e responsáveis"
    }
    
    prompt = f"""
Para seção '{section_name}' da apresentação:

CONTEXTO: {context.get('resumo_geral', '')}
PLANO COMPLETO: {plano_content[:1500]}...

{section_prompts.get(section_name, f'Desenvolva conteúdo para {section_name}')}

Retorne em formato JSON:
{{
  "titulo": "Título da seção",
  "conteudo": ["Ponto 1", "Ponto 2", "Ponto 3"],
  "elementos_visuais": "Sugestões visuais",
  "notas_apresentador": "Notas para apresentação"
}}
"""
    
    try:
        response = generate_ai_completion(prompt, max_tokens=1000)
        return json.loads(response)
    except:
        return {
            "titulo": section_name.replace("_", " ").title(),
            "conteudo": ["Conteúdo a ser desenvolvido"],
            "elementos_visuais": "Gráficos e imagens relevantes",
            "notas_apresentador": "Notas de apresentação"
        }


@router.post("/{planejamento_id}/plano/pre-apresentacao/gerar")
async def gerar_pre_apresentacao(planejamento_id: str):
    """Gera pré-apresentação completa baseada no plano estratégico"""
    try:
        supabase = get_supabase_client()
        
        result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Planejamento não encontrado")
        
        conteudo = result.data.get('conteudo', {})
        plano = conteudo.get('plano', {})
        preplan = conteudo.get('preplanejamento', {})
        
        plano_content = plano.get('consolidated_content', '')
        if not plano_content:
            raise HTTPException(status_code=400, detail="Plano estratégico não foi gerado ainda")
        
        if 'pre_apresentacao' not in conteudo:
            conteudo['pre_apresentacao'] = {}
        
        conteudo['pre_apresentacao']['status'] = 'generating'
        conteudo['pre_apresentacao']['started_at'] = dt.datetime.now().isoformat()
        
        supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        
        storyline = _generate_prez_storyline(plano_content, preplan)
        
        presentation_sections = [
            "titulo", "situacao_atual", "objetivos", "solucao", 
            "investimento_roi", "timeline", "riscos", "recursos", 
            "kpis", "proximos_passos"
        ]
        
        slides = []
        for i, section in enumerate(presentation_sections, 1):
            try:
                progress = (i / len(presentation_sections)) * 100
                conteudo['pre_apresentacao']['progress'] = {
                    'current_section': section,
                    'completed_sections': i - 1,
                    'total_sections': len(presentation_sections),
                    'percentage': progress
                }
                supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
                
                section_data = _generate_prez_section(section, plano_content, preplan)
                
                slide = {
                    "numero": i,
                    "titulo": section_data.get('titulo', section.replace('_', ' ').title()),
                    "conteudo": section_data.get('conteudo', []),
                    "elementos_visuais": section_data.get('elementos_visuais', ''),
                    "notas_apresentador": section_data.get('notas_apresentador', '')
                }
                
                slides.append(slide)
                
            except Exception as section_error:
                print(f"Erro na seção {section}: {section_error}")
                slides.append({
                    "numero": i,
                    "titulo": section.replace('_', ' ').title(),
                    "conteudo": ["Conteúdo a ser desenvolvido"],
                    "elementos_visuais": "Elementos visuais a definir",
                    "notas_apresentador": "Notas a desenvolver"
                })
        
        pre_apresentacao_data = {
            "storyline": storyline,
            "slides": slides,
            "status": "completed",
            "completed_at": dt.datetime.now().isoformat(),
            "total_slides": len(slides),
            "progress": {
                "completed_sections": len(presentation_sections),
                "total_sections": len(presentation_sections),
                "percentage": 100
            }
        }
        
        conteudo['pre_apresentacao'].update(pre_apresentacao_data)
        
        supabase.table('planejamentos').update({
            'conteudo': conteudo,
            'status': 'presentation_ready'
        }).eq('id', planejamento_id).execute()
        
        return {
            "message": "Pré-apresentação gerada com sucesso",
            "slides_generated": len(slides),
            "status": "completed"
        }
        
    except Exception as e:
        try:
            supabase = get_supabase_client()
            result = supabase.table('planejamentos').select('conteudo').eq('id', planejamento_id).single().execute()
            conteudo = result.data.get('conteudo', {}) if result.data else {}
            
            if 'pre_apresentacao' not in conteudo:
                conteudo['pre_apresentacao'] = {}
            
            conteudo['pre_apresentacao']['status'] = 'error'
            conteudo['pre_apresentacao']['error'] = str(e)
            conteudo['pre_apresentacao']['error_at'] = dt.datetime.now().isoformat()
            
            supabase.table('planejamentos').update({'conteudo': conteudo}).eq('id', planejamento_id).execute()
        except:
            pass
        
        raise HTTPException(status_code=500, detail=str(e))
