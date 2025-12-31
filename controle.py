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
        # Tenta carregar as credenciais da seção 'gcp_service_account'
        creds_dict = st.secrets["gcp_service_account"]
        
        # Escopos de acesso necessários
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return creds
    except KeyError:
        st.error("Erro de Credenciais: A seção 'gcp_service_account' não foi encontrada nos Streamlit Secrets. Verifique o secrets.toml.")
        return None
    except Exception as e:
        st.error(f"Erro Crítico: Não foi possível autenticar a Conta de Serviço. Detalhes: {e}")
        return None

@st.cache_data(ttl=600) # Cache para não sobrecarregar a API do Sheets a cada clique
def load_data_from_gsheets():
    """
    Conecta ao Google Sheets e lê as abas 'Transacoes' e 'Categorias'.
    """
    creds = get_service_account_credentials()
    if not creds: return pd.DataFrame(), pd.DataFrame()
        
    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        
        df_transacoes = pd.DataFrame(sh.worksheet("Transacoes").get_all_records())
        df_categorias = pd.DataFrame(sh.worksheet("Categorias").get_all_records())
        
        # Limpeza e Tipagem de Dados (Governança!)
        if not df_transacoes.empty:
            df_transacoes['Data'] = pd.to_datetime(df_transacoes['Data'], format='%Y-%m-%d', errors='coerce')
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
        
        return df_transacoes, df_categorias
        
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Erro: Planilha '{PLANILHA_NOME}' não encontrada ou permissões insuficientes. Compartilhe com o email da Conta de Serviço.")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        st.error(f"Ocorreu um erro na conexão com o Google Sheets: {e}")
        return pd.DataFrame(), pd.DataFrame()

def save_transaction_to_gsheets(data_dict):
    """Insere um novo registro na aba 'Transacoes'."""
    creds = get_service_account_credentials()
    if not creds: return False

    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        transacoes_sheet = sh.worksheet("Transacoes")
        
        # Gera o ID Único (Governança!)
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
        
        # Limpa o cache para que o dashboard seja atualizado na próxima leitura
        load_data_from_gsheets.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao salvar a transação no Sheets: {e}")
        return False
