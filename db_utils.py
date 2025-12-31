# db_utils.py (CORRIGIDO)
import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account
from datetime import datetime
import uuid
import time as t

# --- CONFIGURAÇÃO DA PLANILHA ---
SHEET_ID = "1UgLkIHyl1sDeAUeUUn3C6TfOANZFn6KD9Yvd-OkDkfQ"
PLANILHA_NOME = "CONTROLE FINANCEIRO" 
ABA_TRANSACOES = "TRANSACOES"
ABA_CATEGORIAS = "CATEGORIAS"

# --- GOVERNANÇA: FUNÇÃO DE AUTENTICAÇÃO COM CACHE E RETENTATIVA ---

def get_service_account_credentials():
    """Carrega as credenciais da conta de serviço."""
    try:
        # Usamos o 'gcp_service_account' conforme o fluxo anterior deste app
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

@st.cache_resource(ttl=3600) # Cache para a conexão principal (Correto para recursos não-hashable)
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

# --- FUNÇÕES CORE: CRUD e Limpeza ---

@st.cache_data(ttl=30) # Cache de dados para a UI
def carregar_dados(): # <--- PARÂMETRO 'spreadsheet' REMOVIDO AQUI
    """Lê todas as abas e aplica limpeza de dados e formatação."""
    # OBTÉM A CONEXÃO DENTRO DA FUNÇÃO PARA EVITAR O ERRO UnhashableParamError
    spreadsheet = conectar_sheets_resource() 
    
    if spreadsheet is None:
        return pd.DataFrame(), pd.DataFrame()
        
    try:
        df_transacoes = pd.DataFrame(spreadsheet.worksheet(ABA_TRANSACOES).get_all_records())
        df_categorias = pd.DataFrame(spreadsheet.worksheet(ABA_CATEGORIAS).get_all_records())

        # Limpeza e Tipagem de Dados (Governança!)
        if not df_transacoes.empty:
            # LER: dayfirst=True para formato brasileiro DD/MM/YYYY
            df_transacoes['Data'] = pd.to_datetime(df_transacoes['Data'], dayfirst=True, errors='coerce')
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
            
            # Limpar (DROP) quaisquer linhas que ainda tenham datas inválidas (NaT)
            df_transacoes = df_transacoes.dropna(subset=['Data']).copy() 
        
        return df_transacoes, df_categorias
        
    except gspread.exceptions.WorksheetNotFound as e:
        st.error(f"Erro: Uma das abas (TRANSACOES ou CATEGORIAS) não foi encontrada: {e}")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(), pd.DataFrame()


def adicionar_transacao(spreadsheet, dados_do_form):
    """Insere uma nova linha de transação no Sheets."""
    
    # O resto das funções CRUD continuam recebendo 'spreadsheet' pois elas NÃO são cacheadas
    # e precisam da conexão para ESCREVER (WRITE) na planilha.
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        
        nova_linha = [
            dados_do_form.get('id_transacao'),
            dados_do_form.get('Data'), 
            dados_do_form.get('Descricao'),
            dados_do_form.get('Valor'),
            dados_do_form.get('Tipo'),
            dados_do_form.get('Categoria'),
            dados_do_form.get('Subcategoria'),
            dados_do_form.get('Conta/Meio'),
            dados_do_form.get('Status')
        ]
        
        sheet.append_row(nova_linha)
        st.success("🎉 Transação criada com sucesso! Atualizando dados...")
        carregar_dados.clear() # Limpa o cache para forçar o recarregamento
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
            novos_dados['id_transacao'],
            novos_dados['Data'],
            novos_dados['Descricao'],
            novos_dados['Valor'],
            novos_dados['Tipo'],
            novos_dados['Categoria'],
            novos_dados['Subcategoria'],
            novos_dados['Conta/Meio'],
            novos_dados['Status']
        ]

        # Atualiza a linha completa a partir da coluna A
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
