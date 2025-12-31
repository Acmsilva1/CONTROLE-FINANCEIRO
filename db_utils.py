# db_utils.py (SIMPLIFICADO)
import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import uuid
import time as t

# --- CONFIGURAÇÃO DA PLANILHA ---
SHEET_ID = "1UgLkIHyl1sDeAUeUUn3C6TfOANZFn6KD9Yvd-OkDkfQ" # MANTIDO
ABA_TRANSACOES = "TRANSACOES" 

# --- GOVERNANÇA: FUNÇÃO DE AUTENTICAÇÃO ---

def get_service_account_credentials():
    """Carrega as credenciais da conta de serviço."""
    try:
        creds_dict = st.secrets["gcp_service_account"] 
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return creds
    except KeyError:
        st.error("Erro: 'gcp_service_account' não encontrado nos Streamlit Secrets.")
        return None
    except Exception as e:
        st.error(f"Erro Crítico de Autenticação: {e}")
        return None

@st.cache_resource(ttl=3600) 
def conectar_sheets_resource():
    """Tenta conectar ao Google Sheets com lógica de Retentativa."""
    MAX_RETRIES = 3
    creds = get_service_account_credentials()
    if not creds: return None

    for attempt in range(MAX_RETRIES):
        try:
            gc = gspread.authorize(creds)
            spreadsheet = gc.open_by_key(SHEET_ID)
            st.sidebar.success("✅ Conexão com Google Sheets estabelecida.")
            return spreadsheet
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                st.sidebar.warning(f"⚠️ Falha de conexão momentânea (Tentativa {attempt + 1}/{MAX_RETRIES}). Retentando em {wait_time}s...")
                t.sleep(wait_time) 
            else:
                st.error(f"🚨 Erro fatal ao conectar após {MAX_RETRIES} tentativas. Erro: {e}")
                return None
    return None

# --- FUNÇÕES CORE: CRUD e Limpeza (SIMPLIFICADAS) ---

@st.cache_data(ttl=10) # Cache de dados para a UI
def carregar_dados(): 
    """Lê a aba TRANSACOES e aplica limpeza de dados e formatação."""
    spreadsheet = conectar_sheets_resource() 
    
    if spreadsheet is None:
        return pd.DataFrame()
        
    try:
        df_transacoes = pd.DataFrame(spreadsheet.worksheet(ABA_TRANSACOES).get_all_records())

        # Limpeza e Tipagem de Dados (Governança!)
        if not df_transacoes.empty:
            # LER: dayfirst=True para formato brasileiro DD/MM/YYYY
            df_transacoes['Data'] = pd.to_datetime(df_transacoes['Data'], dayfirst=True, errors='coerce')
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
            
            # Limpar (DROP) quaisquer linhas que ainda tenham datas ou valores inválidos
            df_transacoes = df_transacoes.dropna(subset=['Data', 'Valor']).copy() 
        
        return df_transacoes
        
    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Erro: A aba {ABA_TRANSACOES} não foi encontrada.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


def adicionar_transacao(spreadsheet, dados_do_form):
    """Insere uma nova linha de transação no Sheets."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        
        # Colunas na ordem: ID Transacao, Data, Descricao, Categoria, Valor
        nova_linha = [
            dados_do_form.get('ID Transacao'),
            dados_do_form.get('Data'), 
            dados_do_form.get('Descricao'),
            dados_do_form.get('Categoria'),
            dados_do_form.get('Valor')
        ]
        
        sheet.append_row(nova_linha)
        st.success("🎉 Transação criada com sucesso! Atualizando dados...")
        carregar_dados.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar transação: {e}")
        return False

# U (Update) - Atualiza uma transação existente
def atualizar_transacao(spreadsheet, id_transacao, novos_dados):
    """Busca a linha pelo ID e atualiza os dados da linha."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        cell = sheet.find(id_transacao) 
        linha_index = cell.row 

        valores_atualizados = [
            novos_dados['ID Transacao'],
            novos_dados['Data'],
            novos_dados['Descricao'],
            novos_dados['Categoria'],
            novos_dados['Valor']
        ]

        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Transação {id_transacao[:8]}... atualizada. Atualizando dados...")
        carregar_dados.clear()
        return True

    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Transação '{id_transacao[:8]}...' não encontrado.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar a transação: {e}")
        return False

# D (Delete) - Remove uma transação
def deletar_transacao(spreadsheet, id_transacao):
    """Busca a linha pelo ID e a deleta."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        cell = sheet.find(id_transacao)
        linha_index = cell.row

        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Transação {id_transacao[:8]}... deletada. Atualizando dados...")
        carregar_dados.clear()
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Transação '{id_transacao[:8]}...' não encontrado. Impossível apagar algo que não existe.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao deletar a transação: {e}")
        return False
