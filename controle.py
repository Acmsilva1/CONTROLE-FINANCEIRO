# controle.py (VERSÃO FINAL: GOVERNANÇA, UX E ORDEM DE EXIBIÇÃO CORRIGIDAS + COLORAÇÃO CONDICIONAL + MÉTRICAS NEUTRAS)
import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
# import time as t  # REMOVIDO!
# from streamlit_autorefresh import st_autorefresh # REMOVIDO!

import gspread
from google.oauth2 import service_account

# --- CONFIGURAÇÕES DA PLANILHA ---
SHEET_ID = "1UgLkIHyl1sDeAUeUUn3C6TfOANZFn6KD9Yvd-OkDkfQ" 
ABA_TRANSACOES = "TRANSACOES" 
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
    """
    if value is None or value == 0.0:
        return "R$ 0,00"
        
    valor_str = "{:.2f}".format(value)
    
    # Formata a parte inteira com separador de milhar BR (ponto)
    partes = valor_str.split('.')
    reais = partes[0]
    centavos = partes[1]
    
    reais_formatados = []
    for i in range(len(reais), 0, -3):
        start = max(0, i - 3)
        reais_formatados.insert(0, reais[start:i])
        
    reais_com_ponto = ".".join(reais_formatados)
    
    # Junta tudo com a vírgula decimal
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
        st.error("Erro: Credenciais não encontradas ou inválidas. Verifique st.secrets.")
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
                pass 
            else:
                st.error(f"🚨 Erro fatal ao conectar após {MAX_RETRIES} tentativas. Erro: {e}")
                return None
    return None

@st.cache_data(ttl=10) # TTL de 10 segundos para leitura cacheada
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
        st.success(f"🎉 {dados_do_form['Categoria']} criada com sucesso! Atualizando dados...")
        carregar_dados.clear() # LIMPA O CACHE
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
        carregar_dados.clear() # LIMPA O CACHE
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
        carregar_dados.clear() # LIMPA O CACHE
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
    
if 'id_edicao_ativa' not in st.session_state:
    st.session_state['id_edicao_ativa'] = None

# Conexão
spreadsheet = conectar_sheets_resource()
if spreadsheet is None:
    st.stop() 

# --- BLOCO DE REFRESH MANUAL (Corrigido para dar feedback de UX) ---
with st.sidebar:
    st.markdown("---")
    if st.button("Forçar Atualização Manual 🔄", help="Limpa o cache e busca os dados mais recentes do Google Sheets."):
        carregar_dados.clear() 
        st.success("✅ Cache limpo! Recarregando dados...") 
        st.rerun() 
    st.markdown("---")
    st.info("Atualização: Automática ao salvar/deletar, ou use o botão manual.")

# Carregamento de Dados 
df_transacoes = carregar_dados() 

# === INSERÇÃO DE DADOS (CREATE) - FORMS SEPARADOS ===

st.header("📥 Registrar Novas Transações")

col_rec_form, col_des_form = st.columns(2)

# --- FORMULÁRIO DE RECEITA ---
with col_rec_form:
    st.markdown("##### 🟢 Nova Receita (Entrada Simples)")
    with st.form("form_transacao_receita", clear_on_submit=True):
        
        col_r1, col_r2 = st.columns(2)
        
        mes_atual = MESES_PT.get(datetime.now().month, 'Jan')
        mes_referencia_r = col_r1.selectbox(
            "Mês", 
            options=list(MESES_PT.values()), 
            index=list(MESES_PT.values()).index(mes_atual), 
            key="mes_ref_r"
        )
        
        reais_input_r = col_r2.number_input(
            "Valor (R$ - Reais)", 
            min_value=0, 
            value=None, 
            step=1, 
            format="%d", 
            key="reais_r"
        )
        
        descricao_r = st.text_input("Descrição Detalhada", key="desc_r")

        centavos_input_r = st.number_input(
            "Centavos", 
            min_value=0, 
            max_value=99, 
            value=None, 
            step=1, 
            format="%d", 
            key="centavos_r"
        )
        
        submitted_r = st.form_submit_button("Lançar Receita!")
        
        if submitted_r:
            
            reais_final_r = reais_input_r if reais_input_r is not None else 0
            centavos_final_r = centavos_input_r if centavos_input_r is not None else 0
            
            valor_r = reais_final_r + (centavos_final_r / 100)
            
            if descricao_r and valor_r > 0:
                data_to_save = {
                    "ID Transacao": f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}",
                    "Mês": mes_referencia_r,
                    "Descricao": descricao_r, 
                    "Categoria": 'Receita', 
                    "Valor": valor_r,
                    "Status": STATUS_DEFAULT 
                }
                adicionar_transacao(spreadsheet, data_to_save) 
                st.rerun() 
            else:
                st.warning("Descrição e Valor (deve ser maior que zero) são obrigatórios para Receita.")

# --- FORMULÁRIO DE DESPESA ---
with col_des_form:
    st.markdown("##### 🔴 Nova Despesa (Com Status)")
    with st.form("form_transacao_despesa", clear_on_submit=True):
        
        col_d1, col_d2 = st.columns(2) 

        mes_atual = MESES_PT.get(datetime.now().month, 'Jan')
        mes_referencia_d = col_d1.selectbox(
            "Mês", 
            options=list(MESES_PT.values()), 
            index=list(MESES_PT.values()).index(mes_atual), 
            key="mes_ref_d"
        )
        
        status_select_d = col_d2.selectbox(
            "Status (PAGO / PENDENTE)",
            options=['PAGO', 'PENDENTE'],
            key="status_d"
        )

        reais_input_d = st.number_input(
            "Valor (R$ - Reais)", 
            min_value=0, 
            value=None, 
            step=1, 
            format="%d", 
            key="reais_d"
        )
        
        descricao_d = st.text_input("Descrição Detalhada", key="desc_d")
        
        centavos_input_d = st.number_input(
            "Centavos", 
            min_value=0, 
            max_value=99, 
            value=None, 
            step=1, 
            format="%d", 
            key="centavos_d"
        )
        
        submitted_d = st.form_submit_button("Lançar Despesa!")
        
        if submitted_d:
            
            reais_final_d = reais_input_d if reais_input_d is not None else 0
            centavos_final_d = centavos_input_d if centavos_input_d is not None else 0
            
            valor_d = reais_final_d + (centavos_final_d / 100)
            
            if descricao_d and valor_d > 0:
                data_to_save = {
                    "ID Transacao": f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}",
                    "Mês": mes_referencia_d,
                    "Descricao": descricao_d, 
                    "Categoria": 'Despesa', 
                    "Valor": valor_d,
                    "Status": status_select_d 
                }
                adicionar_transacao(spreadsheet, data_to_save) 
                st.rerun() 
            else:
                st.warning("Descrição e Valor (deve ser maior que zero) são obrigatórios para Despesa.")


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
        
        # Cálculo dos KPIs
        total_receita_bruta = df_filtrado[df_filtrado['Categoria'] == 'Receita']['Valor'].sum()
        total_despesa_bruta = df_filtrado[df_filtrado['Categoria'] == 'Despesa']['Valor'].sum()
        total_receita_paga = df_filtrado[(df_filtrado['Categoria'] == 'Receita') & (df_filtrado['Status'] == 'PAGO')]['Valor'].sum()
        total_despesa_paga = df_filtrado[(df_filtrado['Categoria'] == 'Despesa') & (df_filtrado['Status'] == 'PAGO')]['Valor'].sum()
        margem_liquida_real = total_receita_paga - total_despesa_paga
        total_despesa_pendente = total_despesa_bruta - total_despesa_paga
        # A linha de cor da margem foi desativada, pois usaremos "off" para forçar a cor neutra.
        # margem_delta_color = "inverse" if margem_liquida_real < 0 else "normal" 

        col1, col2, col3, col4, col5 = st.columns(5)
        
        col1.metric("Receitas (Brutas)", format_currency(total_receita_bruta))
        col2.metric("Despesas (Brutas)", format_currency(total_despesa_bruta)) 
        col3.metric("Despesas (PAGAS)", format_currency(total_despesa_paga))
        
        # COLUNA 4: Despesa Pendente (AGORA COM DELTA NEUTRO: delta_color="off")
        col4.metric("Despesas (PENDENTES)", # Título sem emoji de cor
                    format_currency(total_despesa_pendente), 
                    delta="A Pagar", 
                    delta_color="off") # <<< ALTERADO para cor neutra
        
        # COLUNA 5: Lucro Líquido (AGORA COM DELTA NEUTRO: delta_color="off")
        col5.metric("Lucro Líquido", 
                    format_currency(margem_liquida_real), 
                    delta=f"{'PREJUÍZO' if margem_liquida_real < 0 else 'LUCRO'}", 
                    delta_color="off") # <<< ALTERADO para cor neutra

        st.markdown("---")
        
        # === VISUALIZAÇÃO DA TABELA COM BOTÕES DE AÇÃO (EDITAR/EXCLUIR) ===
        
        st.subheader(f"📑 Registros de Transações Detalhadas ({selected_month})")
        
        # 1. Mapeamento para priorizar PENDENTE (1) sobre PAGO (2) nas Despesas
        # 'PENDENTE' vem antes de 'PAGO'
        status_priority_map = {
            'PENDENTE': 1,
            'PAGO': 2
        }
        df_filtrado['Ordem_Status'] = df_filtrado['Status'].map(status_priority_map)
        
        # DataFrame a ser exibido (Ordenado)
        df_display = df_filtrado.copy().sort_values(
            by=['Categoria', 'Ordem_Status', 'Valor'], 
            ascending=[
                False, # Categoria (Receita Z->A) primeiro
                True,  # Ordem_Status (PENDENTE 1->2) segundo
                False  # Valor (Maior->Menor) para desempate
            ]
        )
        
        if df_display.empty:
            st.info(f"Sem transações para o mês de **{selected_month}**.")
        else:
            
            # Cabeçalhos
            cols_header = st.columns([0.4, 0.2, 0.2, 0.1, 0.1])
            cols_header[0].markdown("**Descrição**")
            cols_header[1].markdown("**Categoria**")
            cols_header[2].markdown("**Valor / Status**")
            cols_header[3].markdown(" ") 
            cols_header[4].markdown(" ") 
            st.markdown("---")
            
            # Loop sobre cada transação
            for index, row in df_display.iterrows():
                
                id_transacao = row['ID Transacao']
                
                # 1. Se a linha NÃO está em modo de edição (EXIBIÇÃO NORMAL + BOTÕES)
                if st.session_state.id_edicao_ativa != id_transacao:
                    
                    col_desc, col_cat, col_val_status, col_btn_edit, col_btn_del = st.columns([0.4, 0.2, 0.2, 0.1, 0.1])
                    
                    # === CÓDIGO PARA COLORAÇÃO CONDICIONAL NA TABELA (UX VISUAL) ===
                    if row['Categoria'] == 'Receita':
                        categoria_cor = "green"
                    elif row['Categoria'] == 'Despesa' and row['Status'] == 'PAGO':
                        # Despesa PAGA fica neutra/cinza
                        categoria_cor = "darkgrey" 
                    else:
                        # Despesa PENDENTE (continua vermelho)
                        categoria_cor = "red"
                    # =============================================================
                    
                    col_desc.markdown(f"**<span style='color:{categoria_cor}'>{row['Descricao']}</span>**", unsafe_allow_html=True)
                    col_cat.write(row['Categoria'])
                    col_val_status.write(f"{format_currency(row['Valor'])} ({row['Status']})")

                    if col_btn_edit.button("✍️", key=f'edit_{id_transacao}', help="Editar esta transação"):
                        st.session_state.id_edicao_ativa = id_transacao 
                        st.rerun() 

                    if col_btn_del.button("🗑️", key=f'del_{id_transacao}', help="Excluir esta transação"):
                        deletar_transacao(spreadsheet, id_transacao)
                        st.rerun() 
                
                    st.markdown("---") 
                
                # 2. Se a linha ESTÁ em modo de edição (FORMULÁRIO)
                else: 
                    st.warning(f"📝 Editando Transação: **{row['Descricao']}**")
                    
                    with st.form(key=f"form_update_c_{id_transacao}"):
                        
                        transacao_dados = row 
                        
                        col_upd_1, col_upd_2, col_upd_3 = st.columns(3) 
                        
                        valor_existente = float(transacao_dados['Valor'])
                        reais_existentes = int(valor_existente)
                        centavos_existentes = int(round((valor_existente - reais_existentes) * 100))
                        
                        # INPUTS
                        mes_idx = list(MESES_PT.values()).index(transacao_dados['Mês'])
                        novo_mes = col_upd_1.selectbox("Mês", list(MESES_PT.values()), index=mes_idx, key=f'ut_mes_c_{id_transacao}')
                        cat_index = ["Receita", "Despesa"].index(transacao_dados['Categoria'])
                        novo_categoria = col_upd_2.selectbox("Tipo", ["Receita", "Despesa"], index=cat_index, key=f'ut_tipo_c_{id_transacao}')
                        novo_status_existente = transacao_dados.get('Status', STATUS_DEFAULT) 
                        status_idx = ['PAGO', 'PENDENTE'].index(novo_status_existente)
                        novo_status = col_upd_3.selectbox("Status", ['PAGO', 'PENDENTE'], index=status_idx, key=f'ut_status_c_{id_transacao}')
                        
                        col_upd_v1, col_upd_v2 = st.columns([2, 1])
                        
                        novo_reais_input = col_upd_v1.number_input(
                            "Valor (R$ - Reais)", 
                            min_value=0, 
                            value=reais_existentes, 
                            step=1, 
                            format="%d", 
                            key=f"ut_reais_c_{id_transacao}"
                        )

                        novo_centavos_input = col_upd_v2.number_input(
                            "Centavos", 
                            min_value=0, 
                            max_value=99, 
                            value=centavos_existentes, 
                            step=1, 
                            format="%d", 
                            key=f"ut_centavos_c_{id_transacao}"
                        )
                        
                        novo_descricao = st.text_input(
                            "Descrição", 
                            value=transacao_dados['Descricao'], 
                            key=f'ut_desc_c_{id_transacao}'
                        )
                        
                        # BOTÃO DE SALVAR (DENTRO DO FORM)
                        update_button = st.form_submit_button("✅ Salvar Alterações")

                        if update_button:
                            
                            novo_reais_final = novo_reais_input if novo_reais_input is not None else 0
                            novo_centavos_final = novo_centavos_input if novo_centavos_input is not None else 0
                            novo_valor = novo_reais_final + (novo_centavos_final / 100)
                            
                            if novo_descricao and novo_valor >= 0:
                                dados_atualizados = {
                                    'ID Transacao': id_transacao, 
                                    'Descricao': novo_descricao,
                                    'Valor': novo_valor, 
                                    'Categoria': novo_categoria,
                                    'Mês': novo_mes,
                                    'Status': novo_status
                                }
                                atualizar_transacao(spreadsheet, id_transacao, dados_atualizados) 
                                st.session_state.id_edicao_ativa = None 
                                st.rerun()
                            else:
                                st.warning("Descrição e Valor (deve ser maior ou igual a zero) são obrigatórios na atualização.")

                    # BOTÃO DE CANCELAR (FORA DO FORM)
                    col_dummy_save, col_cancel_out = st.columns([1, 4])
                    if col_cancel_out.button("Cancelar Edição", key=f'cancel_edit_{id_transacao}'):
                        st.session_state.id_edicao_ativa = None
                        st.rerun()

                    st.markdown("---") # Separador para o formulário de edição

    else:
        if selected_month and not df_filtrado.empty:
             st.error("Erro na coluna 'Valor' do DataFrame filtrado. Verifique a planilha.")
        elif selected_month:
             st.info(f"Sem transações para o mês de **{selected_month}**.")


with st.sidebar:
    st.markdown("---")
    st.caption(f"Última leitura de dados (Cache/Sheets): {datetime.now().strftime('%H:%M:%S')}")
