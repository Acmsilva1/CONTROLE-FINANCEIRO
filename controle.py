# controle.py (FINAL, UNIFICADO E CORRIGIDO)
import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import time as t 
from streamlit_autorefresh import st_autorefresh 
import gspread
from google.oauth2 import service_account

# --- CONFIGURAÇÕES DA PLANILHA ---
SHEET_ID = "1UgLkIHyl1sDeAUeUUn3C6TfOANZFn6KD9Yvd-OkDkfQ" 
ABA_TRANSACOES = "TRANSACOES" 
COLUNAS_SIMPLIFICADAS = ['ID Transacao', 'Data', 'Descricao', 'Categoria', 'Valor']

# =================================================================
# === FUNÇÕES DE CONEXÃO E GOVERNANÇA (Integradas aqui) ===
# =================================================================

def get_service_account_credentials():
    """Carrega as credenciais da conta de serviço."""
    try:
        creds_dict = st.secrets["gcp_service_account"] 
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        return creds
    except Exception:
        st.error("Erro: Credenciais não encontradas ou inválidas.")
        return None

@st.cache_resource(ttl=3600) 
def conectar_sheets_resource():
    """Conecta ao Google Sheets."""
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
                t.sleep(2 ** attempt) 
            else:
                st.error(f"🚨 Erro fatal ao conectar após {MAX_RETRIES} tentativas. Erro: {e}")
                return None
    return None

@st.cache_data(ttl=10) 
def carregar_dados(): 
    """Lê a aba TRANSACOES e retorna como DataFrame."""
    spreadsheet = conectar_sheets_resource() 
    if spreadsheet is None:
        return pd.DataFrame()
        
    try:
        df_transacoes = pd.DataFrame(spreadsheet.worksheet(ABA_TRANSACOES).get_all_records())

        if not df_transacoes.empty:
            df_transacoes['Data'] = pd.to_datetime(df_transacoes['Data'], dayfirst=True, errors='coerce')
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
            df_transacoes = df_transacoes.dropna(subset=['Data', 'Valor']).copy() 
        
        return df_transacoes
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


def adicionar_transacao(spreadsheet, dados_do_form):
    """Insere uma nova linha de transação no Sheets."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        nova_linha = [dados_do_form.get(col) for col in COLUNAS_SIMPLIFICADAS]
        sheet.append_row(nova_linha)
        st.success("🎉 Transação criada com sucesso! Atualizando dados...")
        carregar_dados.clear() # Limpa o cache para forçar a releitura
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar transação: {e}")
        return False

def atualizar_transacao(spreadsheet, id_transacao, novos_dados):
    """Atualiza uma transação existente."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        cell = sheet.find(id_transacao) 
        linha_index = cell.row 
        valores_atualizados = [novos_dados.get(col) for col in COLUNAS_SIMPLIFICADAS]

        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Transação {id_transacao[:8]}... atualizada. Atualizando dados...")
        carregar_dados.clear()
        return True
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar a transação: {e}")
        return False

def deletar_transacao(spreadsheet, id_transacao):
    """Remove uma transação."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        cell = sheet.find(id_transacao)
        linha_index = cell.row
        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Transação {id_transacao[:8]}... deletada. Atualizando dados...")
        carregar_dados.clear()
        return True
    except Exception as e:
        st.error(f"🚫 Erro ao deletar a transação: {e}")
        return False

# =================================================================
# === INTERFACE STREAMLIT (UI) ===
# =================================================================

st.set_page_config(layout="wide", page_title="Controle Financeiro Básico")
st.title("💸 Controle Financeiro Básico (CRUD)")

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

st.header("📥 Registrar Nova Transação (Create)")

with st.form("form_transacao", clear_on_submit=True):
    col_c1, col_c2, col_c3 = st.columns(3)
    
    data = col_c1.date_input("Data da Transação", value=date.today(), key="data_c")
    categoria = col_c2.selectbox("Tipo de Transação", options=['Receita', 'Despesa'], key="cat_c")
    valor = col_c3.number_input("Valor (R$)", min_value=0.01, format="%.2f", key="val_c")
    descricao = st.text_input("Descrição Detalhada", key="desc_c")
    
    submitted = st.form_submit_button("Lançar Transação!")
    
    if submitted:
        if descricao and valor:
            data_to_save = {
                "ID Transacao": f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}",
                "Data": data.strftime('%d/%m/%Y'),
                "Descricao": descricao, 
                "Categoria": categoria, 
                "Valor": valor
            }
            adicionar_transacao(spreadsheet, data_to_save)
            t.sleep(1) # Rerenderiza após a inserção
        else:
            st.warning("Descrição e Valor são obrigatórios. Simplifique, mas não tanto.")


st.markdown("---") 

if df_transacoes.empty:
    st.error("Sem dados válidos para análise. Adicione uma transação para começar.")
else:
    
    # --- FILTROS E DASHBOARD ---
    df_transacoes['Ano_Mes'] = df_transacoes['Data'].dt.to_period('M').astype(str)
    
    st.sidebar.header("🗓️ Filtro de Período")
    all_periods = sorted(df_transacoes['Ano_Mes'].unique(), reverse=True)
    selected_period = st.sidebar.selectbox("Selecione o Mês/Ano:", options=all_periods, index=0)
    df_filtrado = df_transacoes[df_transacoes['Ano_Mes'] == selected_period].copy()

    st.header(f"📊 Dashboard Básico ({selected_period})")
        
    total_receita = df_filtrado[df_filtrado['Categoria'] == 'Receita']['Valor'].sum()
    total_despesa = df_filtrado[df_filtrado['Categoria'] == 'Despesa']['Valor'].sum()
    margem_liquida = total_receita - total_despesa
    
    margem_delta_color = "inverse" if margem_liquida < 0 else "normal"

    col1, col2, col3 = st.columns(3)
    
    col1.metric("Total de Receitas", f"R$ {total_receita:,.2f}")
    col2.metric("Total de Despesas", f"R$ {total_despesa:,.2f}")
    col3.metric("Valor Líquido Restante", 
                f"R$ {margem_liquida:,.2f}", 
                delta=f"{'NEGATIVO' if margem_liquida < 0 else 'POSITIVO'}", 
                delta_color=margem_delta_color)

    st.markdown("---")
    
    # === VISUALIZAÇÃO DA TABELA (READ) ===

    st.subheader(f"📑 Registros de Transações ({selected_period})")
    
    df_display = df_filtrado[COLUNAS_SIMPLIFICADAS].copy()
    df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y') 
    
    df_display['Valor'] = df_display.apply(
        lambda row: f"R$ {row['Valor']:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','), axis=1
    )
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.markdown("---") 

    # === SEÇÃO EDIÇÃO E EXCLUSÃO (UPDATE/DELETE) (Corrigida) ===

    st.header("🛠️ Edição e Exclusão (Update/Delete)")
    
    with st.expander("📝 Gerenciar Transação", expanded=True):
        
        transacoes_atuais = df_transacoes['ID Transacao'].tolist()
        
        def formatar_selecao_transacao(id_val):
            # Adiciona try/except caso a linha seja inconsistente
            try:
                df_linha = df_transacoes[df_transacoes['ID Transacao'] == id_val].iloc[0]
                valor_formatado = f"{df_linha['Valor']:,.2f}".replace('.', '#').replace(',', '.').replace('#', ',')
                return f"{df_linha['Descricao']} (R$ {valor_formatado} - {id_val[:4]}...)"
            except:
                return f"ID Inconsistente ({id_val[:4]}...)"


        # O selectbox define a variável
        transacao_selecionada_id = st.selectbox(
            "Selecione a Transação para Ação (Edição/Exclusão):",
            options=transacoes_atuais,
            index=0 if transacoes_atuais else None, # Garante um index inicial
            format_func=formatar_selecao_transacao,
            key='sel_upd_del_c'
        )
    
        # A lógica de UPDATE/DELETE SÓ RODA SE A VARIÁVEL ESTIVER DEFINIDA
        if transacao_selecionada_id:
            # Garante que os dados existem para esta ID
            try:
                transacao_dados = df_transacoes[df_transacoes['ID Transacao'] == transacao_selecionada_id].iloc[0]
            except IndexError:
                st.error("Dados da transação selecionada não encontrados. Tente recarregar.")
                transacao_dados = None
                
            if transacao_dados is not None:

                col_u, col_d = st.columns([4, 1])

                with col_u:
                    st.markdown("##### Atualizar Transação Selecionada")
                    
                    # O formulário com o botão de submit no final
                    with st.form("form_update_transacao_c"):
                        
                        data_existente = pd.to_datetime(transacao_dados['Data']).date()
                        valor_existente = transacao_dados['Valor']
                        categoria_existente = transacao_dados['Categoria']
                        
                        col_upd_1, col_upd_2 = st.columns(2)
                        
                        # Fix de inicialização: Usa try/except para garantir um fallback index
                        try:
                            cat_index = ["Receita", "Despesa"].index(categoria_existente)
                        except ValueError:
                            cat_index = 0 # Default para Receita
                            
                        novo_categoria = col_upd_1.selectbox("Tipo de Transação", ["Receita", "Despesa"], index=cat_index, key='ut_tipo_c')
                        novo_valor = col_upd_2.number_input("Valor (R$)", value=valor_existente, min_value=0.01, format="%.2f", key='ut_valor_c')
                        
                        novo_descricao = st.text_input("Descrição", value=transacao_dados['Descricao'], key='ut_desc_c')
                        
                        novo_data = st.date_input("Data", value=data_existente, key='ut_data_c')
                        
                        # BOTÃO DE SUBMIT NO FINAL DO FORM
                        update_button = st.form_submit_button("Salvar Atualizações (Update)")

                        if update_button:
                            if novo_descricao and novo_valor:
                                dados_atualizados = {
                                    'ID Transacao': transacao_selecionada_id, 
                                    'Descricao': novo_descricao,
                                    'Valor': novo_valor,
                                    'Categoria': novo_categoria,
                                    'Data': novo_data.strftime('%d/%m/%Y'), 
                                }
                                atualizar_transacao(spreadsheet, transacao_selecionada_id, dados_atualizados)
                                t.sleep(1) # Rerenderiza após o update
                            else:
                                st.warning("Descrição e Valor são obrigatórios na atualização.")

                with col_d:
                    st.markdown("##### Excluir")
                    st.warning(f"Excluindo: **{transacao_dados['Descricao']}** (R$ {transacao_dados['Valor']:,.2f})")
                    
                    if st.button("🔴 EXCLUIR TRANSAÇÃO (Delete)", type="primary", key='del_button_c'):
                        deletar_transacao(spreadsheet, transacao_selecionada_id)
                        t.sleep(1) # Rerenderiza após o delete

with st.sidebar:
    st.markdown("---")
    st.caption(f"Última leitura de dados: {datetime.now().strftime('%H:%M:%S')}")
