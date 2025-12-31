# controle.py (FINAL 9: PRESERVAÇÃO DO ESTADO DO FILTRO)
import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import time as t 
from streamlit_autorefresh import st_autorefresh 
import gspread
from google.oauth2 import service_account

# ... (restante das configurações e funções omitidas por brevidade, mas o código completo abaixo)

# =================================================================
# === INTERFACE STREAMLIT (UI) ===
# =================================================================

st.set_page_config(layout="wide", page_title="Controle Financeiro Básico")

st.title("💸 **Controle Financeiro**")

# Inicialização do Estado (A NOVA GOVERNANÇA)
# Define o mês atual como o valor inicial, mas só se o estado ainda não existe.
if 'filtro_mes' not in st.session_state:
    mes_atual = MESES_PT.get(datetime.now().month, 'Jan')
    st.session_state.filtro_mes = mes_atual
    
# Conexão
spreadsheet = conectar_sheets_resource()
if spreadsheet is None:
    st.stop() 

# Auto-Refresh de 20 segundos
st_autorefresh(interval=20000, key="data_refresh_key_simple")
st.sidebar.info("🔄 Atualização automática a cada 20 segundos.")

# Carregamento de Dados
df_transacoes = carregar_dados() 

# === INSERÇÃO DE DADOS (CREATE) ===

st.header("📥 Registrar Nova Transação")

with st.form("form_transacao", clear_on_submit=True):
    col_c1, col_c2, col_c3, col_c4 = st.columns([1, 1, 1.5, 0.5]) 
    
    # MÊS DE REFERÊNCIA: SEMPRE O MÊS ATUAL DO SISTEMA (ISSO FICA FORÇADO, o que é bom para a inserção)
    mes_atual = MESES_PT.get(datetime.now().month, 'Jan')
    mes_referencia_c = col_c1.selectbox(
        "Mês", 
        options=list(MESES_PT.values()), 
        index=list(MESES_PT.values()).index(mes_atual), # Força o Mês Atual
        key="mes_ref_c"
    )
    # ... (restante do form de inserção)
    
# ...

if df_transacoes.empty:
    # ...
else:
    
    # --- FILTROS E DASHBOARD ---
    
    st.sidebar.header("🗓️ Filtro de Período")

    # MUDANÇA CRÍTICA AQUI: O selectbox agora usa a chave e o valor do Session State
    todos_os_meses_pt = list(MESES_PT.values())

    # Usamos o valor do st.session_state.filtro_mes como o valor inicial do selectbox.
    # Quando o usuário muda o filtro, o session_state é atualizado.
    selected_month = st.sidebar.selectbox(
        "Selecione o Mês:", 
        options=todos_os_meses_pt, 
        key='filtro_mes', # Chave que vincula o widget ao st.session_state
        index=todos_os_meses_pt.index(st.session_state.filtro_mes) # Usa o valor do state
    )
    
    # ... (restante do código de dashboard, filtragem e edição)
# ...
