# controle.py (CORRIGIDO)
import streamlit as st
import pandas as pd
from datetime import datetime, time, date
import uuid
import time as t

# Importa a lógica refatorada (db_utils.py deve estar na mesma pasta!)
from db_utils import conectar_sheets_resource, carregar_dados, adicionar_transacao, atualizar_transacao, deletar_transacao 


# --- CONFIGURAÇÃO INICIAL E CONEXÃO ---

st.set_page_config(layout="wide", page_title="Controle Financeiro de Ouro")
st.title("💸 Terminal Financeiro de Comando Doméstico (CRUD)")

# Conexão com o Sheet (cached resource)
spreadsheet = conectar_sheets_resource()
if spreadsheet is None:
    st.stop() # Para o aplicativo se a conexão falhar

# Carregamento de Dados (cached data)
df_transacoes, df_categorias = carregar_dados() # <--- CHAMADA CORRIGIDA (SEM PARÂMETRO)


# --- DASHBOARD E FILTROS ---

if df_transacoes.empty:
    st.error("Sem dados válidos para análise. Verifique as planilhas TRANSACOES e CATEGORIAS.")
    
    # Se não há dados válidos, ainda mostramos o formulário de criação
    st.markdown("---")
    st.header("📥 Inserção de Nova Transação")

else:
    # --- PREPARAÇÃO DE DADOS PARA ANÁLISE ---
    df_transacoes['Ano_Mes'] = df_transacoes['Data'].dt.to_period('M').astype(str)
    df_transacoes['Sinal'] = df_transacoes['Tipo'].apply(lambda x: 1 if x == 'Receita' else -1)
    df_transacoes['Valor_Ajustado'] = df_transacoes['Valor'] * df_transacoes['Sinal']
    
    # Categorias para Selectboxes
    all_despesa_cats = df_categorias[df_categorias['Tipo'] == 'Despesa']['Categoria'].unique().tolist()
    all_receita_cats = df_categorias[df_categorias['Tipo'] == 'Receita']['Categoria'].unique().tolist()
    
    # Filtros de Mês/Ano (Sidebar)
    st.sidebar.header("🗓️ Filtro de Período")
    all_periods = sorted(df_transacoes['Ano_Mes'].unique(), reverse=True)
    
    selected_period = st.sidebar.selectbox("Selecione o Mês/Ano:", options=all_periods, index=0)
        
    # APLICAÇÃO DO FILTRO
    df_filtrado = df_transacoes[df_transacoes['Ano_Mes'] == selected_period].copy()

    st.sidebar.caption(f"Análise atual: **{selected_period}**")
    st.sidebar.markdown("---")

    # =================================================================
    # === DASHBOARD VISUALIZAÇÃO ===
    # =================================================================

    st.header(f"📊 Dashboard: Indicadores de Comando ({selected_period})")
        
    # Cálculo das Métricas
    total_receita = df_filtrado[df_filtrado['Tipo'] == 'Receita']['Valor'].sum()
    total_despesa = df_filtrado[df_filtrado['Tipo'] == 'Despesa']['Valor'].sum()
    margem_liquida = total_receita - total_despesa
    
    margem_delta_color = "inverse" if margem_liquida < 0 else "normal"

    col1, col2, col3 = st.columns(3)
    
    col1.metric("Total de Receitas", f"R$ {total_receita:,.2f}", delta="Caminho do Sucesso")
    col2.metric("Total de Despesas", f"R$ {total_despesa:,.2f}", delta="O Burocrata do Seu Bolso")
    col3.metric("Margem Líquida", 
                f"R$ {margem_liquida:,.2f}", 
                delta=f"{'NEGATIVA' if margem_liquida < 0 else 'POSITIVA'} - A Realidade Financeira", 
                delta_color=margem_delta_color)

    st.markdown("---")
    
    st.subheader("Gráfico de Despesas por Categoria")
    df_gastos = df_filtrado[df_filtrado['Tipo'] == 'Despesa'].groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
    st.bar_chart(df_gastos)
    
    st.markdown("---")
    
    # --- TABELA DE REGISTROS FILTRADOS ---
    st.subheader(f"📑 Registros de Transações ({selected_period})")
    df_display = df_filtrado[['ID Transacao', 'Data', 'Descricao', 'Valor', 'Tipo', 'Categoria', 'Conta/Meio', 'Status']]
    # Exibir data no formato BR
    df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y') 
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.markdown("#") # Espaço
    st.markdown("---") 

    # =================================================================
    # === SEÇÃO CRUD: CRIAÇÃO, EDIÇÃO E EXCLUSÃO ===
    # =================================================================

    st.header("🛠️ Gerenciamento de Transações (CRUD)")
    
    # --- ABA/EXPANDER DE CRIAÇÃO (CREATE) ---
    with st.expander("📥 1. REGISTRAR NOVA TRANSAÇÃO (Create)", expanded=False):
        
        tab_rec, tab_fix, tab_var = st.tabs(["Receita", "Despesa Fixa", "Despesa Variável"])
        
        # --- TAB: RECEITA ---
        with tab_rec:
            with st.form("form_receita", clear_on_submit=True):
                st.subheader("💰 Lançar Receita")
                col_r1, col_r2 = st.columns(2)
                descricao = col_r1.text_input("Descrição da Receita", key="desc_r")
                valor = col_r2.number_input("Valor Recebido (R$)", min_value=0.01, format="%.2f", key="val_r")
                col_r3, col_r4 = st.columns(2)
                categoria = col_r3.selectbox("Categoria", options=all_receita_cats, key="cat_r")
                conta = col_r4.text_input("Conta/Meio", key="cont_r")
                data = st.date_input("Data de Recebimento", value=date.today(), key="data_r") 
                submitted = st.form_submit_button("Lançar Receita!")
                
                if submitted:
                    if descricao and valor:
                        data_to_save = {
                            "id_transacao": f"TRX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4]}",
                            "Data": data.strftime('%d/%m/%Y'), # Formato BR para o Sheets
                            "Descricao": descricao, "Valor": valor,
                            "Tipo": "Receita", "Categoria": categoria, "Subcategoria": "", 
                            "Conta/Meio": conta, "Status": "Compensado" 
                        }
                        adicionar_transacao(spreadsheet, data_to_save)
                        t.sleep(1) # Pausa para ver a mensagem
                        st.rerun()
                    else:
                        st.warning("Descrição e Valor são obrigatórios. Não complique.")

        # --- TAB: DESPESA FIXA ---
        with tab_fix:
            with st.form("form_fixa", clear_on_submit=True):
                st.subheader("🏠 Lançar Despesa Fixa")
                col_f1, col_f2 = st.columns(2)
                descricao = col_f1.text_input("Descrição da Despesa Fixa", key="desc_f")
                valor = col_f2.number_input("Valor da Despesa (R$)", min_value=0.01, format="%.2f", key="val_f")
                col_f3, col_f4 = st.columns(2)
                categoria = col_f3.selectbox("Categoria", options=all_despesa_cats, key="cat_f")
                conta = col_f4.text_input("Conta/Meio de Pagamento", key="cont_f")
                data = st.date_input("Data de Vencimento/Pagamento", value=date.today(), key="data_f") 
                submitted = st.form_submit_button("Lançar Despesa Fixa!")
                
                if submitted:
                    if descricao and valor:
                        data_to_save = {
                            "id_transacao": f"TRX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4]}",
                            "Data": data.strftime('%d/%m/%Y'), 
                            "Descricao": descricao, "Valor": valor,
                            "Tipo": "Despesa", "Categoria": categoria, "Subcategoria": "Fixa", 
                            "Conta/Meio": conta, "Status": "Pago" 
                        }
                        adicionar_transacao(spreadsheet, data_to_save)
                        t.sleep(1)
                        st.rerun()
                    else:
                        st.warning("Descrição e Valor são obrigatórios. Não complique.")

        # --- TAB: DESPESA VARIÁVEL ---
        with tab_var:
            with st.form("form_variavel", clear_on_submit=True):
                st.subheader("🛒 Lançar Despesa Variável")
                col_v1, col_v2 = st.columns(2)
                descricao = col_v1.text_input("Descrição da Despesa Variável", key="desc_v")
                valor = col_v2.number_input("Valor da Despesa (R$)", min_value=0.01, format="%.2f", key="val_v")
                col_v3, col_v4 = st.columns(2)
                categoria = col_v3.selectbox("Categoria", options=all_despesa_cats, key="cat_v")
                conta = col_v4.text_input("Conta/Meio de Pagamento", key="cont_v")
                data = st.date_input("Data da Transação", value=date.today(), key="data_v") 
                submitted = st.form_submit_button("Lançar Despesa Variável!")
                
                if submitted:
                    if descricao and valor:
                        data_to_save = {
                            "id_transacao": f"TRX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4]}",
                            "Data": data.strftime('%d/%m/%Y'), 
                            "Descricao": descricao, "Valor": valor,
                            "Tipo": "Despesa", "Categoria": categoria, "Subcategoria": "Variável", 
                            "Conta/Meio": conta, "Status": "Pago" 
                        }
                        adicionar_transacao(spreadsheet, data_to_save)
                        t.sleep(1)
                        st.rerun()
                    else:
                        st.warning("Descrição e Valor são obrigatórios. Não complique.")
        
        st.markdown("---")

    # --- BLOCO DE EDIÇÃO E EXCLUSÃO (UPDATE/DELETE) ---
    with st.expander("📝 2. ATUALIZAR/EXCLUIR TRANSAÇÃO", expanded=True):
        
        if df_transacoes.empty:
            st.info("Sem transações para editar ou excluir.")
        else:
            
            transacoes_atuais = df_transacoes['ID Transacao'].tolist()
            
            def formatar_selecao_transacao(id_val):
                df_linha = df_transacoes[df_transacoes['ID Transacao'] == id_val].iloc[0]
                # Acesso seguro ao Valor, formatado para exibição
                valor_formatado = f"{df_linha['Valor']:,.2f}".replace('.', '#').replace(',', '.').replace('#', ',')
                return f"{df_linha['Descricao']} (R$ {valor_formatado} - {id_val[:4]}...)"


            transacao_selecionada_id = st.selectbox(
                "Selecione a Transação para Ação (Edição/Exclusão):",
                options=transacoes_atuais,
                index=0,
                format_func=formatar_selecao_transacao,
                key='sel_upd_del'
            )
        
            if transacao_selecionada_id:
                transacao_dados = df_transacoes[df_transacoes['ID Transacao'] == transacao_selecionada_id].iloc[0]

                col_u, col_d = st.columns([3, 1])

                with col_u:
                    st.markdown("##### Atualizar Transação Selecionada")
                    with st.form("form_update_transacao"):
                        
                        col_upd_1, col_upd_2 = st.columns(2)
                        
                        # Conversão segura de data/hora para os widgets
                        data_existente = pd.to_datetime(transacao_dados['Data']).date()
                        valor_existente = transacao_dados['Valor']
                        tipo_existente = transacao_dados['Tipo']
                        
                        novo_tipo = col_upd_1.selectbox("Tipo", ["Receita", "Despesa"], index=["Receita", "Despesa"].index(tipo_existente), key='ut_tipo')
                        novo_valor = col_upd_2.number_input("Valor (R$)", value=valor_existente, min_value=0.01, format="%.2f", key='ut_valor')

                        novo_descricao = st.text_input("Descrição", value=transacao_dados['Descricao'], key='ut_desc')
                        
                        col_upd_3, col_upd_4 = st.columns(2)
                        
                        # Filtra categorias baseadas no tipo selecionado
                        opcoes_cat = all_receita_cats if novo_tipo == 'Receita' else all_despesa_cats
                        
                        try:
                             cat_index = opcoes_cat.index(transacao_dados['Categoria'])
                        except ValueError:
                             cat_index = 0
                             
                        novo_categoria = col_upd_3.selectbox("Categoria", options=opcoes_cat, index=cat_index, key='ut_cat')
                        
                        opcoes_status = ['Compensado', 'Pendente', 'Cancelado', 'Pago']
                        try:
                             status_index = opcoes_status.index(transacao_dados['Status'])
                        except ValueError:
                             status_index = 0
                        novo_status = col_upd_4.selectbox("Status", opcoes_status, index=status_index, key='ut_status')
                        
                        col_upd_5, col_upd_6 = st.columns(2)
                        novo_data = col_upd_5.date_input("Data", value=data_existente, key='ut_data')
                        novo_conta = col_upd_6.text_input("Conta/Meio", value=transacao_dados['Conta/Meio'], key='ut_conta')
                        
                        update_button = st.form_submit_button("Salvar Atualizações (Update)")

                        if update_button:
                            if novo_descricao and novo_valor:
                                dados_atualizados = {
                                    'id_transacao': transacao_selecionada_id, 
                                    'Descricao': novo_descricao,
                                    'Valor': novo_valor,
                                    'Tipo': novo_tipo,
                                    'Categoria': novo_categoria,
                                    # Manter Subcategoria (Fixa/Variável) se existir, ou vazio
                                    'Subcategoria': transacao_dados.get('Subcategoria', ''), 
                                    'Conta/Meio': novo_conta,
                                    'Status': novo_status,
                                    'Data': novo_data.strftime('%d/%m/%Y'), # Formato BR para o Sheets
                                }
                                atualizar_transacao(spreadsheet, transacao_selecionada_id, dados_atualizados)
                                t.sleep(1)
                                st.rerun()
                            else:
                                st.warning("Descrição e Valor são obrigatórios na atualização.")

                        
                with col_d:
                    st.markdown("##### Excluir Transação")
                    st.warning(f"Excluindo: **{transacao_dados['Descricao']}** (R$ {transacao_dados['Valor']:,.2f})")
                    
                    if st.button("🔴 EXCLUIR TRANSAÇÃO (Delete)", type="primary", key='del_button'):
                        deletar_transacao(spreadsheet, transacao_selecionada_id)
                        t.sleep(1)
                        st.rerun()

# --- FIM DO CÓDIGO DO APLICATIVO ---

# Mantemos o timer no final da UI (aqui não precisa do st.rerun() no final, pois já temos o st_autorefresh ou o rerun manual)
with st.sidebar:
    st.markdown("---")
    st.caption(f"Última atualização de dados: {datetime.now().strftime('%H:%M:%S')}")
