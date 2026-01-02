# controle.py (VERSÃO FINAL: GOVERNANÇA COMPLETA & BUG FIX)
import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import time as t 
from streamlit_autorefresh import st_autorefresh 
import gspread
from google.oauth2 import service_account

# --- CONFIGURAÇÕES DA PLANILHA ---
SHEET_ID = "1UgLkIHyl1sDeAUeUUn3C6TfOANZFn6KD9Yvd-OkDkfQ" 
ABA_TRANSACOES = "TRANSACOES" 
# COLUNAS_SIMPLIFICADAS agora inclui 'Status'
COLUNAS_SIMPLIFICADAS = ['ID Transacao', 'Mês', 'Descricao', 'Categoria', 'Valor', 'Status']
STATUS_DEFAULT = 'PAGO' 

# Lista de meses em português para uso na UI e como chave de ordenação
MESES_PT = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 
    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 
    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}

# =================================================================
# === FUNÇÕES DE FORMATAÇÃO E PARSING ===
# =================================================================

def format_currency(value):
    """
    Formata um float (ex: 11.56) para string monetária BR (R$ 11,56).
    (Usada apenas para exibição no Streamlit)
    """
    if value is None or value == 0.0:
        return "R$ 0,00"
        
    valor_str = "{:.2f}".format(value)
    
    # 1. Separa e formata a parte inteira com separador de milhar BR (ponto)
    partes = valor_str.split('.')
    reais = partes[0]
    centavos = partes[1]
    
    reais_formatados = []
    for i in range(len(reais), 0, -3):
        start = max(0, i - 3)
        reais_formatados.insert(0, reais[start:i])
        
    reais_com_ponto = ".".join(reais_formatados)
    
    # 2. Junta tudo com a vírgula decimal
    valor_final = f"{reais_com_ponto},{centavos}"
    
    return f"R$ {valor_final}"

# =================================================================
# === FUNÇÕES DE CONEXÃO E GOVERNANÇA ===
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
    """Lê a aba TRANSACOES forçando a leitura do valor puro (UNFORMATTED_VALUE)."""
    spreadsheet = conectar_sheets_resource() 
    if spreadsheet is None:
        return pd.DataFrame()
        
    try:
        records = spreadsheet.worksheet(ABA_TRANSACOES).get_all_records(
             value_render_option='UNFORMATTED_VALUE', 
             head=1 
        )
        df_transacoes = pd.DataFrame(records)

        if not df_transacoes.empty:
            
            if 'Status' not in df_transacoes.columns:
                df_transacoes['Status'] = STATUS_DEFAULT 
            
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
            
            df_transacoes['Status'] = df_transacoes['Status'].fillna(STATUS_DEFAULT)
            df_transacoes.loc[df_transacoes['Status'] == '', 'Status'] = STATUS_DEFAULT
            
            df_transacoes = df_transacoes.dropna(subset=['Mês', 'Valor']).copy() 
            df_transacoes['Mes_Num'] = df_transacoes['Mês'].map({v: k for k, v in MESES_PT.items()})

        return df_transacoes
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


def adicionar_transacao(spreadsheet, dados_do_form):
    """Insere uma nova linha de transação no Sheets."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        
        nova_linha = [dados_do_form.get(col) for col in COLUNAS_SIMPLIFICADAS]
        
        sheet.append_row(nova_linha, value_input_option='USER_ENTERED')
        st.success("🎉 Transação criada com sucesso! Atualizando dados...")
        carregar_dados.clear() 
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

        sheet.update(f'A{linha_index}', [valores_atualizados], value_input_option='USER_ENTERED')
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

st.title("💸 **Controle Financeiro**")

# Inicialização do Estado
if 'filtro_mes' not in st.session_state:
    mes_atual_init = MESES_PT.get(datetime.now().month, 'Jan')
    st.session_state.filtro_mes = mes_atual_init
    
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
    col_c1, col_c2, col_c3 = st.columns([1, 1, 1]) 
    
    # MÊS DE REFERÊNCIA
    mes_atual = MESES_PT.get(datetime.now().month, 'Jan')
    mes_referencia_c = col_c1.selectbox(
        "Mês", 
        options=list(MESES_PT.values()), 
        index=list(MESES_PT.values()).index(mes_atual), 
        key="mes_ref_c"
    )
    categoria = col_c2.selectbox("Tipo de Transação", options=['Receita', 'Despesa'], key="cat_c")
    
    # Status sempre visível
    status_select = col_c3.selectbox(
        "Status (PAGO / PENDENTE)",
        options=['PAGO', 'PENDENTE'],
        key="status_c"
    )
    
    # ENTRADAS: Reais/Centavos
    col_v1, col_v2 = st.columns([1.5, 0.5])

    reais_input = col_v1.number_input(
        "Valor (R$ - Reais)", 
        min_value=0, 
        value=None, 
        step=1, 
        format="%d", 
        key="reais_c"
    )
    
    centavos_input = col_v2.number_input(
        "Centavos", 
        min_value=0, 
        max_value=99, 
        value=None, 
        step=1, 
        format="%d", 
        key="centavos_c"
    )
    
    descricao = st.text_input("Descrição Detalhada", key="desc_c")
    
    submitted = st.form_submit_button("Lançar Transação!")
    
    if submitted:
        
        reais_final = reais_input if reais_input is not None else 0
        centavos_final = centavos_input if centavos_input is not None else 0
        
        valor = reais_final + (centavos_final / 100)
        
        if descricao and valor > 0:
            data_to_save = {
                "ID Transacao": f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}",
                "Mês": mes_referencia_c,
                "Descricao": descricao, 
                "Categoria": categoria, 
                "Valor": valor, 
                "Status": status_select
            }
            adicionar_transacao(spreadsheet, data_to_save) 
            t.sleep(1) 
        else:
            st.warning("Descrição e Valor (deve ser maior que zero) são obrigatórios. Não complique.")


st.markdown("---") 

if df_transacoes.empty:
    st.error("Sem dados válidos para análise. Adicione uma transação para começar.")
else:
    
    # --- FILTROS E DASHBOARD ---
    
    st.sidebar.header("🗓️ Filtro de Período")

    todos_os_meses_pt = list(MESES_PT.values())

    selected_month = st.sidebar.selectbox(
        "Selecione o Mês:", 
        options=todos_os_meses_pt, 
        key='filtro_mes', 
    )

    if selected_month and 'Mês' in df_transacoes.columns:
        df_filtrado = df_transacoes[df_transacoes['Mês'] == selected_month].copy()
    else:
        df_filtrado = pd.DataFrame() 


    st.header(f"📊 Dashboard Básico ({selected_month or 'Nenhum Mês Selecionado'})")
    
    if not df_filtrado.empty and 'Valor' in df_filtrado.columns:
        
        total_receita_bruta = df_filtrado[df_filtrado['Categoria'] == 'Receita']['Valor'].sum()
        total_despesa_bruta = df_filtrado[df_filtrado['Categoria'] == 'Despesa']['Valor'].sum()
        
        total_receita_realizada = df_filtrado[
            (df_filtrado['Categoria'] == 'Receita') & 
            (df_filtrado['Status'] == 'PAGO')
        ]['Valor'].sum()
        
        total_despesa_realizada = df_filtrado[
            (df_filtrado['Categoria'] == 'Despesa') & 
            (df_filtrado['Status'] == 'PAGO')
        ]['Valor'].sum()

        margem_liquida = total_receita_realizada - total_despesa_realizada
        
        margem_delta_color = "inverse" if margem_liquida < 0 else "normal"

        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric("Total Receitas (Brutas)", format_currency(total_receita_bruta))
        col2.metric("Total Despesas (Brutas)", format_currency(total_despesa_bruta))
        col3.metric("Líquido (RECEITAS PAGAS)", format_currency(total_receita_realizada))
        col4.metric("Valor Líquido (Realizado)", 
                    format_currency(margem_liquida), 
                    delta=f"{'NEGATIVO' if margem_liquida < 0 else 'POSITIVO'}", 
                    delta_color=margem_delta_color)

        st.markdown("---")
        
        # === VISUALIZAÇÃO DA TABELA (READ) - DUAS TABELAS SEPARADAS ===

        st.subheader(f"📑 Registros de Transações Detalhadas ({selected_month})")
        
        df_base_display = df_filtrado.copy()
        df_base_display['Valor_Formatado'] = df_base_display['Valor'].apply(format_currency)
        
        df_receitas = df_base_display[df_base_display['Categoria'] == 'Receita']
        df_despesas = df_base_display[df_base_display['Categoria'] == 'Despesa']
        
        DISPLAY_COLUMNS = ['Descricao', 'Status', 'Valor_Formatado']

        col_rec, col_des = st.columns(2)

        with col_rec:
            st.markdown("##### 🟢 Receitas (Entradas)")
            if df_receitas.empty:
                st.info("Nenhuma Receita registrada para este mês.")
            else:
                st.dataframe(
                    df_receitas[DISPLAY_COLUMNS].rename(columns={'Valor_Formatado': 'Valor'}),
                    use_container_width=True, 
                    hide_index=True
                )

        with col_des:
            st.markdown("##### 🔴 Despesas (Saídas)")
            if df_despesas.empty:
                st.info("Nenhuma Despesa registrada para este mês.")
            else:
                st.dataframe(
                    df_despesas[DISPLAY_COLUMNS].rename(columns={'Valor_Formatado': 'Valor'}),
                    use_container_width=True, 
                    hide_index=True
                )
        
        st.markdown("---") 

        # === SEÇÃO EDIÇÃO E EXCLUSÃO (UPDATE/DELETE) ===

        st.header("🛠️ Edição e Exclusão")
        
        with st.expander("📝 Gerenciar Transação", expanded=True):
            
            transacoes_atuais = df_filtrado['ID Transacao'].tolist()
            
            def formatar_selecao_transacao(id_val):
                try:
                    df_linha = df_transacoes[df_transacoes['ID Transacao'] == id_val].iloc[0] 
                    valor_formatado = format_currency(df_linha['Valor'])
                    status_info = f" | Status: {df_linha.get('Status', STATUS_DEFAULT)}" 
                    return f"{df_linha['Descricao']} ({df_linha['Mês']} | {valor_formatado}{status_info})"
                except:
                    return f"ID Inconsistente ({id_val[:4]}...)"

            transacao_selecionada_id = st.selectbox(
                "Selecione a Transação para Ação (Edição/Exclusão):",
                options=transacoes_atuais,
                index=0 if transacoes_atuais else None,
                format_func=formatar_selecao_transacao,
                # Chave fixa aqui é OK, pois esta selectbox CONTROLA o estado da transação
                key='sel_upd_del_c' 
            )
        
            if transacao_selecionada_id:
                try:
                    transacao_dados = df_transacoes[df_transacoes['ID Transacao'] == transacao_selecionada_id].iloc[0]
                except IndexError:
                    st.error("Dados da transação selecionada não encontrados.")
                    transacao_dados = None
                    
                if transacao_dados is not None:

                    col_u, col_d = st.columns([4, 1])

                    with col_u:
                        st.markdown("##### Atualizar Transação Selecionada")
                        
                        # >>> APLICANDO O FIX: O ID da Transação é anexado ao Form Key para forçar o re-render
                        # O ID é único, então quando o ID muda, o Streamlit vê um "novo formulário"
                        with st.form(f"form_update_transacao_c_{transacao_selecionada_id}"): 
                            
                            categoria_existente = transacao_dados['Categoria']
                            mes_existente = transacao_dados['Mês']
                            
                            try:
                                valor_existente = float(transacao_dados['Valor']) 
                                reais_existentes = int(valor_existente)
                                centavos_existentes = int(round((valor_existente - reais_existentes) * 100))
                            except (ValueError, TypeError):
                                reais_existentes = None
                                centavos_existentes = None
                            
                            col_upd_1, col_upd_2, col_upd_3 = st.columns(3) 
                            
                            try:
                                mes_idx = list(MESES_PT.values()).index(mes_existente)
                            except ValueError:
                                mes_idx = 0 
                                
                            novo_mes = col_upd_1.selectbox(
                                "Mês", 
                                list(MESES_PT.values()), 
                                index=mes_idx, 
                                # FIX APLICADO AQUI
                                key=f'ut_mes_c_{transacao_selecionada_id}'
                            )

                            try:
                                cat_index = ["Receita", "Despesa"].index(categoria_existente)
                            except ValueError:
                                cat_index = 0
                                
                            novo_categoria = col_upd_2.selectbox(
                                "Tipo de Transação", 
                                ["Receita", "Despesa"], 
                                index=cat_index, 
                                # FIX APLICADO AQUI
                                key=f'ut_tipo_c_{transacao_selecionada_id}'
                            )
                            
                            novo_status_existente = transacao_dados.get('Status', STATUS_DEFAULT) 
                            try:
                                # O Streamlit prefere PAGO como index 0, PENDENTE como index 1
                                status_idx = ['PAGO', 'PENDENTE'].index(novo_status_existente)
                            except ValueError:
                                status_idx = 0 

                            novo_status = col_upd_3.selectbox(
                                "Status", 
                                ['PAGO', 'PENDENTE'], 
                                index=status_idx, 
                                # FIX APLICADO AQUI
                                key=f'ut_status_c_{transacao_selecionada_id}'
                            )
                            
                            # CAMPOS DE EDIÇÃO
                            col_upd_v1, col_upd_v2 = st.columns([2, 1])
                            
                            novo_reais_input = col_upd_v1.number_input(
                                "Valor (R$ - Reais)", 
                                min_value=0, 
                                value=reais_existentes, 
                                step=1, 
                                format="%d", 
                                # FIX APLICADO AQUI
                                key=f"ut_reais_c_{transacao_selecionada_id}"
                            )

                            novo_centavos_input = col_upd_v2.number_input(
                                "Centavos", 
                                min_value=0, 
                                max_value=99, 
                                value=centavos_existentes, 
                                step=1, 
                                format="%d", 
                                # FIX APLICADO AQUI
                                key=f"ut_centavos_c_{transacao_selecionada_id}"
                            )
                            
                            novo_descricao = st.text_input(
                                "Descrição", 
                                value=transacao_dados['Descricao'], 
                                # FIX APLICADO AQUI
                                key=f'ut_desc_c_{transacao_selecionada_id}'
                            )
                            
                            update_button = st.form_submit_button("Salvar Atualizações (Update)")

                            if update_button:
                                
                                novo_reais_final = novo_reais_input if novo_reais_input is not None else 0
                                novo_centavos_final = novo_centavos_input if novo_centavos_input is not None else 0
                                
                                novo_valor = novo_reais_final + (novo_centavos_final / 100)
                                
                                if novo_descricao and novo_valor >= 0:
                                    dados_atualizados = {
                                        'ID Transacao': transacao_selecionada_id, 
                                        'Descricao': novo_descricao,
                                        'Valor': novo_valor, 
                                        'Categoria': novo_categoria,
                                        'Mês': novo_mes,
                                        'Status': novo_status
                                    }
                                    atualizar_transacao(spreadsheet, transacao_selecionada_id, dados_atualizados) 
                                    t.sleep(1)
                                else:
                                    st.warning("Descrição e Valor (deve ser maior ou igual a zero) são obrigatórios na atualização.")

                    with col_d:
                        st.markdown("##### Excluir")
                        status_info_del = f" (Status: {transacao_dados.get('Status', 'N/A')})"
                        st.warning(f"Excluindo: **{transacao_dados['Descricao']}** ({format_currency(transacao_dados['Valor'])}){status_info_del}")
                        
                        # Chave fixa para o botão é OK, pois ele apenas dispara uma ação.
                        if st.button("🔴 EXCLUIR TRANSAÇÃO", type="primary", key='del_button_c'): 
                            deletar_transacao(spreadsheet, transacao_selecionada_id)
                            t.sleep(1)
    else:
        if selected_month and not df_filtrado.empty:
             st.error("Erro na coluna 'Valor' do DataFrame filtrado. Verifique a planilha.")
        elif selected_month:
             st.info(f"Sem transações para o mês de **{selected_month}**.")


with st.sidebar:
    st.markdown("---")
    st.caption(f"Última leitura de dados: {datetime.now().strftime('%H:%M:%S')}")
