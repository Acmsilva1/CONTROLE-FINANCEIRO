# db_utils.py
import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import uuid

# --- CONFIGURAÇÃO DA PLANILHA ---
SHEET_ID = "1UgLkIHyl1sDeAUeUUn3C6TfOANZFn6KD9Yvd-OkDkfQ" 
PLANILHA_NOME = "CONTROLE FINANCEIRO" 

def get_service_account_credentials():
    """
    Carrega as credenciais da conta de serviço a partir de st.secrets.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return creds
    except KeyError:
        st.error("Erro de Credenciais: A seção 'gcp_service_account' não foi encontrada nos Streamlit Secrets.")
        return None
    except Exception as e:
        st.error(f"Erro Crítico de Autenticação: Não foi possível autenticar a Conta de Serviço. Detalhes: {e}")
        return None

@st.cache_data(ttl=600) # Cache para não sobrecarregar a API do Sheets
def load_data_from_gsheets():
    """
    Conecta ao Google Sheets e lê as abas 'TRANSACOES' e 'CATEGORIAS'.
    """
    creds = get_service_account_credentials()
    if not creds: return pd.DataFrame(), pd.DataFrame()
        
    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        
        # Leitura com nome de aba corrigido (em MAIÚSCULAS)
        df_transacoes = pd.DataFrame(sh.worksheet("TRANSACOES").get_all_records())
        df_categorias = pd.DataFrame(sh.worksheet("CATEGORIAS").get_all_records())
        
        # Limpeza e Tipagem de Dados (Governança!)
        if not df_transacoes.empty:
            # CORREÇÃO CRÍTICA: dayfirst=True para formato brasileiro DD/MM/YYYY
            df_transacoes['Data'] = pd.to_datetime(df_transacoes['Data'], dayfirst=True, errors='coerce')
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
        
        return df_transacoes, df_categorias
        
    except gspread.exceptions.WorksheetNotFound:
        st.error("Erro: Uma das abas (TRANSACOES ou CATEGORIAS) não foi encontrada na planilha. Verifique o nome exato.")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro na conexão com o Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()

def save_transaction_to_gsheets(data_dict):
    """Insere um novo registro na aba 'TRANSACOES'."""
    creds = get_service_account_credentials()
    if not creds: return False

    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        transacoes_sheet = sh.worksheet("TRANSACOES") 
        
        new_id = f"TRX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4]}"

        # Ordem das colunas: ID Transacao, Data, Descricao, Valor, Tipo, Categoria, Subcategoria, Conta/Meio, Status
        row_to_append = [
            new_id,
            data_dict["Data"], 
            data_dict["Descricao"],
            data_dict["Valor"],
            data_dict["Tipo"],
            data_dict["Categoria"],
            data_dict.get("Subcategoria", ""),
            data_dict["Conta/Meio"],
            data_dict["Status"]
        ]
        
        transacoes_sheet.append_row(row_to_append, value_input_option='USER_ENTERED')
        
        # Limpa o cache para que o dashboard seja atualizado
        load_data_from_gsheets.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao salvar a transação no Sheets: {e}")
        return False
