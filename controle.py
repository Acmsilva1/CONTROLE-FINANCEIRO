# controle.py (FINAL, VALOR MONETÁRIO COM PARSING CORRIGIDO PARA VÍRGULA DECIMAL BRASILEIRA)
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
COLUNAS_SIMPLIFICADAS = ['ID Transacao', 'Mês', 'Descricao', 'Categoria', 'Valor']

# Lista de meses em português para uso na UI e como chave de ordenação
MESES_PT = {
    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 
    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago', 
    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
}

# =================================================================
# === FUNÇÃO DE PARSING REFORÇADA (Onde a Mágica Acontece) ===
# =================================================================

def parse_valor_monetario(valor_input):
    """
    Função de governança para converter strings monetárias (BR) em float (Python).
    Lógica: Limpa a string e garante que a vírgula (decimal) seja convertida em ponto.
    Ex: '1.235,50' -> 1235.50
    """
    if not valor_input or valor_input.strip() == "":
        raise ValueError("Campo de valor vazio.")
        
    # 1. Remove caracteres não numéricos permitidos (R$, espaços, etc.)
    # Mantemos apenas números, ponto (.) e vírgula (,)
    clean_input = "".join(filter(lambda x: x.isdigit() or x in (',', '.'), valor_input))
    
    # 2. Tenta identificar se o formato é brasileiro (vírgula como decimal) ou americano (ponto como decimal)
    
    if ',' in clean_input and '.' in clean_input:
        # Caso de 1.234,50 (Ponto de milhar e vírgula decimal)
        # Remove o ponto (milhar) e troca a vírgula (decimal) por ponto.
        clean_input = clean_input.replace('.', '')
        clean_input = clean_input.replace(',', '.')
    elif ',' in clean_input:
        # Caso de 10,50 (Vírgula decimal)
        clean_input = clean_input.replace(',', '.')
        
    # Se o formato for 10.50 (ponto decimal, sem vírgula) ou 10 (apenas inteiro),
    # o string já está no formato float correto.
    
    # 3. Tenta converter para float
    return float(clean_input)

# =================================================================
# === FUNÇÕES DE CONEXÃO E GOVERNANÇA (inalteradas) ===
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
            df_transacoes['Valor'] = pd.to_numeric(df_transacoes['Valor'], errors='coerce')
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
        sheet.append_row(nova_linha)
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

st.title("💸 **Controle Financeiro**")

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
    col_c1, col_c2, col_c3 = st.columns(3)
    
    mes_atual = MESES_PT.get(datetime.now().month, 'Jan')
    mes_referencia_c = col_c1.selectbox(
        "Mês", 
        options=list(MESES_PT.values()), 
        index=list(MESES_PT.values()).index(mes_atual), 
        key="mes_ref_c"
    )
    categoria = col_c2.selectbox("Tipo de Transação", options=['Receita', 'Despesa'], key="cat_c")
    
    # CHAVE DA CORREÇÃO: Usando st.text_input para aceitar a vírgula
    valor_input = col_c3.text_input("Valor (R$)", value="", key="val_c", placeholder="Ex: 235,50 ou 1.235,50") 
    
    descricao = st.text_input("Descrição Detalhada", key="desc_c")
    
    submitted = st.form_submit_button("Lançar Transação!")
    
    if submitted:
        # Tenta converter o valor do texto para float usando a função de parse
        try:
            valor = parse_valor_monetario(valor_input) # <--- CHAMA A FUNÇÃO CORRIGIDA

        except ValueError:
            st.warning("O campo Valor deve ser um número válido (ex: 235,50 ou 1.235,50). Transação não lançada.")
            st.stop() 
        
        if descricao and valor > 0:
            data_to_save = {
                "ID Transacao": f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}",
                "Mês": mes_referencia_c,
                "Descricao": descricao, 
                "Categoria": categoria, 
                "Valor": valor
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
    
    meses_disponiveis = df_transacoes[['Mês', 'Mes_Num']].drop_duplicates().sort_values(by='Mes_Num', ascending=False)['Mês'].tolist()
    
    if meses_disponiveis:
        selected_month = st.sidebar.selectbox("Selecione o Mês:", options=meses_disponiveis, index=0)
    else:
        selected_month = None

    if selected_month:
        df_filtrado = df_transacoes[df_transacoes['Mês'] == selected_month].copy()
    else:
        df_filtrado = pd.DataFrame() 


    st.header(f"📊 Dashboard Básico ({selected_month or 'Nenhum Mês Selecionado'})")
    
    if not df_filtrado.empty:
        
        total_receita = df_filtrado[df_filtrado['Categoria'] == 'Receita']['Valor'].sum()
        total_despesa = df_filtrado[df_filtrado['Categoria'] == 'Despesa']['Valor'].sum()
        margem_liquida = total_receita - total_despesa
        
        margem_delta_color = "inverse" if margem_liquida < 0 else "normal"

        col1, col2, col3 = st.columns(3)
        
        # Função para formatar a moeda (exibição)
        def format_currency(value):
            return f"R$ {value:,.2f}".replace('.', '#').replace(',', '.').replace('#', ',')

        col1.metric("Total de Receitas", format_currency(total_receita))
        col2.metric("Total de Despesas", format_currency(total_despesa))
        col3.metric("Valor Líquido Restante", 
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
        
        DISPLAY_COLUMNS = ['Descricao', 'Valor_Formatado']

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
                    return f"{df_linha['Descricao']} ({df_linha['Mês']} | {valor_formatado})"
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
                        
                        opcoes_categoria = ["Receita", "Despesa"]
                        categoria_existente = transacao_dados.get('Categoria', opcoes_categoria[0])
                        
                        with st.form("form_update_transacao_c"):
                            
                            mes_existente = transacao_dados['Mês']
                            
                            try:
                                valor_existente = float(transacao_dados['Valor']) 
                            except (ValueError, TypeError):
                                valor_existente = 0.0 
                            
                            col_upd_1, col_upd_2 = st.columns(2)
                            
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
                                cat_index = opcoes_categoria.index(categoria_existente)
                            except ValueError:
                                cat_index = 0
                                
                            novo_categoria = col_upd_2.selectbox("Tipo de Transação", opcoes_categoria, index=cat_index, key='ut_tipo_c')
                            
                            # CHAVE DA CORREÇÃO: Usando st.text_input para edição e exibindo valor formatado em PT-BR
                            valor_existente_str_clean = f"{valor_existente:.2f}".replace('.', ',')
                            novo_valor_input = st.text_input("Valor (R$)", value=valor_existente_str_clean, key='ut_valor_c')
                            
                            novo_descricao = st.text_input("Descrição", value=transacao_dados['Descricao'], key='ut_desc_c')
                            
                            update_button = st.form_submit_button("Salvar Atualizações (Update)")

                            if update_button:
                                # Tenta converter o valor do texto para float usando a função de parse
                                try:
                                    novo_valor = parse_valor_monetario(novo_valor_input) # <--- CHAMA A FUNÇÃO CORRIGIDA
                                    
                                except ValueError:
                                    st.warning("O campo Valor deve ser um número válido (ex: 235,50 ou 1.235,50). Atualização não realizada.")
                                    st.stop()
                                
                                if novo_descricao and novo_valor > 0:
                                    dados_atualizados = {
                                        'ID Transacao': transacao_selecionada_id, 
                                        'Descricao': novo_descricao,
                                        'Valor': novo_valor, 
                                        'Categoria': novo_categoria,
                                        'Mês': novo_mes,
                                    }
                                    atualizar_transacao(spreadsheet, transacao_selecionada_id, dados_atualizados)
                                    t.sleep(1)
                                else:
                                    st.warning("Descrição e Valor (deve ser maior que zero) são obrigatórios na atualização.")

                    with col_d:
                        st.markdown("##### Excluir")
                        st.warning(f"Excluindo: **{transacao_dados['Descricao']}** ({format_currency(transacao_dados['Valor'])})")
                        
                        if st.button("🔴 EXCLUIR TRANSAÇÃO", type="primary", key='del_button_c'):
                            deletar_transacao(spreadsheet, transacao_selecionada_id)
                            t.sleep(1)
    else:
        st.info(f"Sem transações para o mês de **{selected_month}**.")


with st.sidebar:
    st.markdown("---")
    st.caption(f"Última leitura de dados: {datetime.now().strftime('%H:%M:%S')}")
