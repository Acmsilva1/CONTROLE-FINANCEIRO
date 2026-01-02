# controle.py (VERSÃO FINAL: GOVERNANÇA COMPLETA & STATUS)
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
# >>> MUDANÇA 1: Adicionar 'Status' à lista de colunas
COLUNAS_SIMPLIFICADAS = ['ID Transacao', 'Mês', 'Descricao', 'Categoria', 'Valor', 'Status']
# STATUS_DEFAULT é a nova "fonte da verdade" quando o campo não é aplicável ou inserido
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
        # LÊ O VALOR PURO (UNFORMATTED_VALUE) - FIX DE LEITURA
        # Importante: O Sheets deve ter a nova coluna 'Status' na linha de cabeçalho
        records = spreadsheet.worksheet(ABA_TRANSACOES).get_all_records(
             value_render_option='UNFORMATTED_VALUE', 
             head=1 
        )
        df_transacoes = pd.DataFrame(records)

        if not df_transacoes.empty:
            
            # Garante que a coluna Status exista (para dados antigos que não a tinham)
            if 'Status' not in df_transacoes.columns:
                df_transacoes['Status'] = '' # Cria uma coluna vazia se não existir
            
            # Converte para numérico, corrigindo a coluna 'Valor'
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
            
            # Preenche Status vazio em Despesas com o Default para consistência na UI (opcional)
            df_transacoes['Status'] = df_transacoes.apply(
                lambda row: STATUS_DEFAULT if (row['Categoria'] == 'Despesa' or pd.isna(row['Status']) or row['Status'] == '') else row['Status'], 
                axis=1
            )
            
            df_transacoes = df_transacoes.dropna(subset=['Mês', 'Valor']).copy() 
            df_transacoes['Mes_Num'] = df_transacoes['Mês'].map({v: k for k, v in MESES_PT.items()})

        return df_transacoes
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()


def adicionar_transacao(spreadsheet, dados_do_form):
    """Insere uma nova linha de transação no Sheets. ENVIA O VALOR FLOAT PURO com USER_ENTERED."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        
        # >>> MUDANÇA 2: Assegurar que a nova linha inclua o Status
        # Garantir que a ordem segue COLUNAS_SIMPLIFICADAS, inclusive o novo 'Status'
        # O valor do Status virá do formulário, ou será STATUS_DEFAULT (para despesas)
        nova_linha = [dados_do_form.get(col) for col in COLUNAS_SIMPLIFICADAS]
        
        # USER_ENTERED interpreta o float corretamente conforme o Locale do Sheets (BR).
        sheet.append_row(nova_linha, value_input_option='USER_ENTERED') # FIX DE ESCRITA
        st.success("🎉 Transação criada com sucesso! Atualizando dados...")
        carregar_dados.clear() 
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar transação: {e}")
        return False

def atualizar_transacao(spreadsheet, id_transacao, novos_dados):
    """Atualiza uma transação existente. ENVIA O VALOR FLOAT PURO com USER_ENTERED."""
    try:
        sheet = spreadsheet.worksheet(ABA_TRANSACOES)
        cell = sheet.find(id_transacao) 
        linha_index = cell.row 
        
        # Garantir que a ordem segue COLUNAS_SIMPLIFICADAS
        valores_atualizados = [novos_dados.get(col) for col in COLUNAS_SIMPLIFICADAS]

        # A célula inicial da linha é A{linha_index}, e a última é a da coluna 'Status'
        sheet.update(f'A{linha_index}', [valores_atualizados], value_input_option='USER_ENTERED') # FIX DE ESCRITA
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

# Inicialização do Estado (PARA PRESERVAR O FILTRO DE MÊS NO REFRESH)
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
    
    # MÊS DE REFERÊNCIA: SEMPRE O MÊS ATUAL DO SISTEMA
    mes_atual = MESES_PT.get(datetime.now().month, 'Jan')
    mes_referencia_c = col_c1.selectbox(
        "Mês", 
        options=list(MESES_PT.values()), 
        index=list(MESES_PT.values()).index(mes_atual), # Força o Mês Atual
        key="mes_ref_c"
    )
    categoria = col_c2.selectbox("Tipo de Transação", options=['Receita', 'Despesa'], key="cat_c")
    
    # >>> MUDANÇA 3: Adicionar Status condicionalmente
    status_select = STATUS_DEFAULT
    if categoria == 'Receita':
        status_select = col_c3.selectbox(
            "Status da Receita (Apenas para Receitas)",
            options=['PENDENTE', 'PAGO'],
            key="status_c"
        )
    else:
        # Garante que, para Despesa, a coluna de Status seja PAGO (ou um valor neutro)
        # O componente é ocultado, mas precisamos do valor para o `submitted`
        status_select = STATUS_DEFAULT
        col_c3.markdown("Status: **Pago** (padrão para despesas)")
    
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
        
        # Trata o valor None como 0 para o cálculo
        reais_final = reais_input if reais_input is not None else 0
        centavos_final = centavos_input if centavos_input is not None else 0
        
        # Reconstrução do valor float (A fonte da verdade)
        valor = reais_final + (centavos_final / 100)
        
        if descricao and valor > 0:
            data_to_save = {
                "ID Transacao": f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}",
                "Mês": mes_referencia_c,
                "Descricao": descricao, 
                "Categoria": categoria, 
                "Valor": valor, # Enviando o float (ex: 11.56)
                "Status": status_select # >>> NOVO CAMPO
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
        
        # A Margem Líquida agora deve considerar apenas Receitas PAGO - Despesas
        total_receita_bruta = df_filtrado[df_filtrado['Categoria'] == 'Receita']['Valor'].sum()
        total_despesa = df_filtrado[df_filtrado['Categoria'] == 'Despesa']['Valor'].sum()
        
        # Receita Realizada (APENAS PAGO) para uma análise mais "séria"
        total_receita_realizada = df_filtrado[
            (df_filtrado['Categoria'] == 'Receita') & 
            (df_filtrado['Status'] == 'PAGO')
        ]['Valor'].sum()

        margem_liquida = total_receita_realizada - total_despesa
        
        margem_delta_color = "inverse" if margem_liquida < 0 else "normal"

        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric("Total de Receitas (Brutas)", format_currency(total_receita_bruta))
        col2.metric("Total de Receitas (PAGAS)", format_currency(total_receita_realizada))
        col3.metric("Total de Despesas", format_currency(total_despesa))
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
        
        # >>> MUDANÇA 4: Adicionar Status apenas nas receitas
        DISPLAY_COLUMNS_RECEITA = ['Descricao', 'Status', 'Valor_Formatado']
        DISPLAY_COLUMNS_DESPESA = ['Descricao', 'Valor_Formatado']


        col_rec, col_des = st.columns(2)

        with col_rec:
            st.markdown("##### 🟢 Receitas (Entradas)")
            if df_receitas.empty:
                st.info("Nenhuma Receita registrada para este mês.")
            else:
                st.dataframe(
                    df_receitas[DISPLAY_COLUMNS_RECEITA].rename(columns={'Valor_Formatado': 'Valor'}),
                    use_container_width=True, 
                    hide_index=True
                )

        with col_des:
            st.markdown("##### 🔴 Despesas (Saídas)")
            if df_despesas.empty:
                st.info("Nenhuma Despesa registrada para este mês.")
            else:
                st.dataframe(
                    df_despesas[DISPLAY_COLUMNS_DESPESA].rename(columns={'Valor_Formatado': 'Valor'}),
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
                    # Inclui o status na exibição de seleção para receitas
                    status_info = f" | Status: {df_linha['Status']}" if df_linha['Categoria'] == 'Receita' else ""
                    return f"{df_linha['Descricao']} ({df_linha['Mês']} | {valor_formatado}{status_info})"
                except:
                    return f"ID Inconsistente ({id_val[:4]}...)"

            transacao_selecionada_id = st.selectbox(
                "Selecione a Transação para Ação (Edição/Exclusão):",
                options=transacoes_atuais,
                index=0 if transacoes_atuais else None,
                format_func=formatar_selecao_transacao,
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
                        
                        with st.form("form_update_transacao_c"):
                            
                            categoria_existente = transacao_dados['Categoria']
                            mes_existente = transacao_dados['Mês']
                            
                            try:
                                valor_existente = float(transacao_dados['Valor']) 
                                reais_existentes = int(valor_existente)
                                centavos_existentes = int(round((valor_existente - reais_existentes) * 100))
                            except (ValueError, TypeError):
                                reais_existentes = None
                                centavos_existentes = None
                            
                            col_upd_1, col_upd_2, col_upd_3 = st.columns(3) # Três colunas para os campos de topo
                            
                            try:
                                mes_idx = list(MESES_PT.values()).index(mes_existente)
                            except ValueError:
                                mes_idx = 0 
                                
                            novo_mes = col_upd_1.selectbox(
                                "Mês", 
                                list(MESES_PT.values()), 
                                index=mes_idx, 
                                key='ut_mes_c'
                            )

                            try:
                                cat_index = ["Receita", "Despesa"].index(categoria_existente)
                            except ValueError:
                                cat_index = 0
                                
                            novo_categoria = col_upd_2.selectbox("Tipo de Transação", ["Receita", "Despesa"], index=cat_index, key='ut_tipo_c')
                            
                            # >>> MUDANÇA 5: Campo Status na Edição (Condicional)
                            novo_status = transacao_dados.get('Status', STATUS_DEFAULT) # Pega o valor existente

                            if novo_categoria == 'Receita':
                                try:
                                    status_idx = ['PENDENTE', 'PAGO'].index(novo_status)
                                except ValueError:
                                    status_idx = 0 

                                novo_status = col_upd_3.selectbox(
                                    "Status", 
                                    ['PENDENTE', 'PAGO'], 
                                    index=status_idx, 
                                    key='ut_status_c'
                                )
                            else:
                                novo_status = STATUS_DEFAULT
                                col_upd_3.markdown("Status: **Pago** (padrão para despesas)")

                            # CAMPOS DE EDIÇÃO
                            col_upd_v1, col_upd_v2 = st.columns([2, 1])
                            
                            novo_reais_input = col_upd_v1.number_input(
                                "Valor (R$ - Reais)", 
                                min_value=0, 
                                value=reais_existentes, 
                                step=1, 
                                format="%d", 
                                key="ut_reais_c"
                            )

                            novo_centavos_input = col_upd_v2.number_input(
                                "Centavos", 
                                min_value=0, 
                                max_value=99, 
                                value=centavos_existentes, 
                                step=1, 
                                format="%d", 
                                key="ut_centavos_c"
                            )
                            
                            novo_descricao = st.text_input("Descrição", value=transacao_dados['Descricao'], key='ut_desc_c')
                            
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
                                        'Status': novo_status # >>> NOVO CAMPO
                                    }
                                    atualizar_transacao(spreadsheet, transacao_selecionada_id, dados_atualizados) 
                                    t.sleep(1)
                                else:
                                    st.warning("Descrição e Valor (deve ser maior ou igual a zero) são obrigatórios na atualização.")

                    with col_d:
                        st.markdown("##### Excluir")
                        status_info_del = f" (Status: {transacao_dados.get('Status', 'N/A')})" if transacao_dados['Categoria'] == 'Receita' else ""
                        st.warning(f"Excluindo: **{transacao_dados['Descricao']}** ({format_currency(transacao_dados['Valor'])}){status_info_del}")
                        
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
