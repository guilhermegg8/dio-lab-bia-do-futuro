import json
import os
from pathlib import Path
import pandas as pd
import requests
import streamlit as st

# ============ CONFIGURAÇÃO DE PÁGINA ============
st.set_page_config(
    page_title="Edu - Educador Financeiro Inteligente",
    page_icon="🎓",
    layout="wide"
)

# ============ CAMINHOS E CARREGAMENTO DE DADOS ============
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

@st.cache_data
def carregar_dados():
    with open(DATA_DIR / "perfil_investidor.json", "r", encoding="utf-8") as f:
        perfil = json.load(f)
    
    transacoes = pd.read_csv(DATA_DIR / "transacoes.csv")
    historico = pd.read_csv(DATA_DIR / "historico_atendimento.csv")
    
    with open(DATA_DIR / "produtos_financeiros.json", "r", encoding="utf-8") as f:
        produtos = json.load(f)
        
    return perfil, transacoes, historico, produtos

perfil, transacoes, historico, produtos = carregar_dados()

# ============ MONTAR CONTEXTO ============
contexto = f"""
CLIENTE: {perfil['nome']}, {perfil['idade']} anos, perfil {perfil['perfil_investidor']}
OBJETIVO: {perfil['objetivo_principal']}
PATRIMÔNIO: R$ {perfil['patrimonio_total']} | RESERVA ATUAL: R$ {perfil['reserva_emergencia_atual']}

TRANSAÇÕES RECENTES:
{transacoes.to_string(index=False)}

ATENDIMENTOS ANTERIORES:
{historico.to_string(index=False)}

PRODUTOS DISPONÍVEIS:
{json.dumps(produtos, indent=2, ensure_ascii=False)}
"""

# ============ SYSTEM PROMPT ============
SYSTEM_PROMPT = """Você é o Edu, um educador financeiro amigável e didático.

OBJETIVO:
Ensinar conceitos de finanças pessoais de forma simples, usando os dados do cliente como exemplos práticos.

REGRAS:
- NUNCA recomende investimentos específicos, apenas explique como funcionam;
- JAMAIS responda a perguntas fora do tema ensino de finanças pessoais. Quando ocorrer, responda lembrando o seu papel de educador financeiro;
- Use os dados fornecidos para dar exemplos personalizados;
- Linguagem simples, como se explicasse para um amigo;
- Se não souber algo, admita: "Não tenho essa informação, mas posso explicar...";
- Sempre pergunte se o cliente entendeu;
- Responda de forma sucinta e direta, com no máximo 3 parágrafos.
"""

# ============ FUNÇÃO DE COMUNICAÇÃO COM O LLM ============
def chamar_llm(mensagem, provedor, url, modelo):
    """
    Função preparada para conectar com LM Studio ou Ollama.
    """
    prompt_completo = f"""{SYSTEM_PROMPT}

CONTEXTO DO CLIENTE:
{contexto}

Pergunta do usuário: {mensagem}
Resposta do Edu:"""

    try:
        base = url.rstrip('/')

        if provedor == "LM Studio":
            # Normaliza endpoint para /v1/chat/completions
            if base.endswith('/v1'):
                endpoint = f"{base}/chat/completions"
            else:
                endpoint = f"{base}/v1/chat/completions"

            payload = {
                "model": modelo,
                "messages": [
                    {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nCONTEXTO DO CLIENTE:\n{contexto}"},
                    {"role": "user", "content": mensagem}
                ],
                "temperature": 0.7
            }
            resposta = requests.post(endpoint, json=payload, timeout=60)
            resposta.raise_for_status()
            dados = resposta.json()
            return dados["choices"][0]["message"]["content"]

        elif provedor == "Ollama":
            if base.endswith('/v1'):
                base = base[:-3]
            endpoint = f"{base}/api/generate"
            payload = {
                "model": modelo,
                "prompt": prompt_completo,
                "stream": False
            }
            resposta = requests.post(endpoint, json=payload, timeout=60)
            resposta.raise_for_status()
            return resposta.json().get("response", "Nenhuma resposta retornada pelo Ollama.")

    except requests.exceptions.ConnectionError:
        return f"⚠️ Erro de Conexão: Não foi possível conectar ao {provedor} em `{url}`. Verifique se o servidor está rodando."
    except Exception as e:
        return f"⚠️ Ocorreu um erro ao consultar o {provedor}: {str(e)}"

# ============ BARRA LATERAL (SIDEBAR) ============
with st.sidebar:
    st.header("👤 Perfil do Cliente")
    st.markdown(f"**Nome:** {perfil['nome']}")
    st.markdown(f"**Idade:** {perfil['idade']} anos")
    st.markdown(f"**Perfil:** `{perfil['perfil_investidor'].capitalize()}`")
    st.markdown(f"**Objetivo:** {perfil['objetivo_principal']}")
    
    st.metric(
        label="Reserva de Emergência", 
        value=f"R$ {perfil['reserva_emergencia_atual']:,.2f}",
        delta=f"Meta: R$ {perfil['metas'][0]['valor_necessario']:,.2f}"
    )
    
    st.divider()
    
    st.header("⚙️ Conexão LLM")
    provedor = st.selectbox("Escolha o Provedor:", ["LM Studio", "Ollama"], index=0)
    
    if provedor == "LM Studio":
        llm_url = st.text_input("URL do LM Studio:", value="http://localhost:1234/v1")
        
        # Auto-detecção de modelos no LM Studio
        modelos_detectados = []
        try:
            base_test = llm_url.rstrip('/')
            models_endpoint = f"{base_test}/models" if base_test.endswith('/v1') else f"{base_test}/v1/models"
            resp_m = requests.get(models_endpoint, timeout=2)
            if resp_m.status_code == 200:
                data_m = resp_m.json().get("data", [])
                modelos_detectados = [m["id"] for m in data_m if "embedding" not in m.get("id", "").lower()]
        except Exception:
            pass

        if modelos_detectados:
            modelo_nome = st.selectbox("Modelo detectado:", modelos_detectados, index=0)
            st.success(f"Conectado ao LM Studio! ✅")
        else:
            modelo_nome = st.text_input("Nome do Modelo:", value="mistralai/ministral-3-3b")
            st.info("Servidor do LM Studio ativo na porta 1234.")
    else:
        llm_url = st.text_input("URL do Ollama:", value="http://localhost:11434")
        modelo_nome = st.text_input("Modelo do Ollama:", value="gpt-oss")
        st.caption("Execute `ollama serve` e certifique-se de ter baixado o modelo.")

# ============ INTERFACE PRINCIPAL DO CHAT ============
st.title("🎓 Edu - Educador Financeiro Inteligente")
st.caption("Tire suas dúvidas conceituais de finanças com exemplos práticos baseados no seu perfil.")

# Inicializa histórico de mensagens no estado da sessão
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": f"Olá, {perfil['nome']}! Sou o Edu, seu educador financeiro. Estou aqui para descomplicar finanças, explicar conceitos de investimentos e ajudar a analisar seus gastos. Como posso te ajudar hoje?"
        }
    ]

# Exibe mensagens do histórico
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrada de pergunta pelo usuário
if pergunta_usuario := st.chat_input("Ex: O que é CDI? Ou onde estou gastando mais?"):
    # Mostra mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": pergunta_usuario})
    with st.chat_message("user"):
        st.markdown(pergunta_usuario)

    # Gera resposta com indicador de carregamento
    with st.chat_message("assistant"):
        with st.spinner("Edu está pensando..."):
            resposta_edu = chamar_llm(pergunta_usuario, provedor, llm_url, modelo_nome)
            st.markdown(resposta_edu)
            st.session_state.messages.append({"role": "assistant", "content": resposta_edu})
