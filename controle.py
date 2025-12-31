# controle.py (SIMPLIFICADO)
import streamlit as st
import pandas as pd
from datetime import datetime, date
import uuid
import time as t 
# Ferramenta para o auto-refresh que você já estava usando
from streamlit_autorefresh import st_autorefresh 

# Importa a lógica refatorada (db_utils.py deve estar na mesma pasta!)
from db_utils import conectar_sheets_resource, carregar_dados, adicionar_transacao, atualizar_transacao, deletar_transacao 

# --- CONFIGURAÇÃO INICIAL E CONEXÃO ---

st.set_page_config(layout="wide", page_title="Controle Financeiro Básico")
st.title("💸 Controle Financeiro Básico (CRUD)")

# Conexão com o Sheet (cached resource)
spreadsheet = conectar_sheets_resource()
if spreadsheet is None:
    st.stop() 

# --- AUTO-REFRESH (10 segundos) ---
st_autorefresh(interval=10000, key="data_refresh_key_simple")
st.sidebar.info("🔄 Atualização automática a cada 10 segundos.")

# Carregamento de Dados (cached data)
df_transacoes = carregar_dados() 

# =================================================================
# === INSERÇÃO DE DADOS (CREATE) ===
# =================================================================

st.header("📥 Registrar Nova Transação (Create)")

with st.form("form_transacao", clear_on_submit=True):
    col_c1, col_c2, col_c3 = st.columns(3)
    
    # Inputs (5 colunas)
    data = col_c1.date_input("Data da Transação", value=date.today(), key="data_c")
    categoria = col_c2.selectbox("Tipo de Transação", options=['Receita', 'Despesa'], key="cat_c")
    valor = col_c3.number_input("Valor (R$)", min_value=0.01, format="%.2f", key="val_c")
    descricao = st.text_input("Descrição Detalhada", key="desc_c")
    
    submitted = st.form_submit_button("Lançar Transação!")
    
    if submitted:
        if descricao and valor:
            data_to_save = {
                "ID Transacao": f"TRX-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:4]}",
                "Data": data.strftime('%d/%m/%Y'), # Formato BR para o Sheets
                "Descricao": descricao, 
                "Categoria": categoria, 
                "Valor": valor
            }
            adicionar_transacao(spreadsheet, data_to_save)
            t.sleep(1) 
        else:
            st.warning("Descrição e Valor são obrigatórios. Simplifique, mas não tanto.")


st.markdown("---") 

if df_transacoes.empty:
    st.error("Sem dados válidos para análise. Adicione uma transação para começar.")
else:
    
    # --- PREPARAÇÃO DE DADOS PARA ANÁLISE ---
    df_transacoes['Ano_Mes'] = df_transacoes['Data'].dt.to_period('M').astype(str)
    
    # Filtros de Mês/Ano (Sidebar)
    st.sidebar.header("🗓️ Filtro de Período")
    all_periods = sorted(df_transacoes['Ano_Mes'].unique(), reverse=True)
    
    selected_period = st.sidebar.selectbox("Selecione o Mês/Ano:", options=all_periods, index=0)
        
    # APLICAÇÃO DO FILTRO
    df_filtrado = df_transacoes[df_transacoes['Ano_Mes'] == selected_period].copy()

    st.sidebar.caption(f"Análise atual: **{selected_period}**")
    st.sidebar.markdown("---")

    # =================================================================
    # === DASHBOARD SIMPLIFICADO ===
    # =================================================================

    st.header(f"📊 Dashboard Básico ({selected_period})")
        
    # Cálculo das Métricas (Receita, Despesa, Líquido)
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
    
    # =================================================================
    # === VISUALIZAÇÃO DA TABELA (READ) ===
    # =================================================================

    st.subheader(f"📑 Registros de Transações ({selected_period})")
    
    df_display = df_filtrado[['ID Transacao', 'Data', 'Descricao', 'Categoria', 'Valor']].copy()
    df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y') 
    
    # Formatação de Valor (para exibição)
    df_display['Valor'] = df_display.apply(
        lambda row: f"R$ {row['Valor']:,.2f}".replace('.', '#').replace(',', '.').replace('#', ','), axis=1
    )
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.markdown("---") 

    # =================================================================
    # === SEÇÃO CRUD: EDIÇÃO E EXCLUSÃO (UPDATE/DELETE) ===
    # =================================================================

    st.header("🛠️ Edição e Exclusão (Update/Delete)")
    
    with st.expander("📝 Gerenciar Transação", expanded=True):
        
        transacoes_atuais = df_transacoes['ID Transacao'].tolist()
        
        def formatar_selecao_transacao(id_val):
            df_linha = df_transacoes[df_transacoes['ID Transacao'] == id_val].iloc[0]
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

            col_u, col_d = st.columns([4, 1])

            with col_u:
                st.markdown("##### Atualizar Transação Selecionada")
                
                with st.form("form_update_transacao"):
                    
                    data_existente = pd.to_datetime(transacao_dados['Data']).date()
                    valor_existente = transacao_dados['Valor']
                    categoria_existente = transacao_dados['Categoria']
                    
                    col_upd_1, col_upd_2 = st.columns(2)
                    
                    novo_categoria = col_upd_1.selectbox("Tipo de Transação", ["Receita", "Despesa"], index=["Receita", "Despesa"].index(categoria_existente), key='ut_tipo')
                    novo_valor = col_upd_2.number_input("Valor (R$)", value=valor_existente, min_value=0.01, format="%.2f", key='ut_valor')
                    
                    novo_descricao = st.text_input("Descrição", value=transacao_dados['Descricao'], key='ut_desc')
                    
                    novo_data = st.date_input("Data", value=data_existente, key='ut_data')
                    
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
                            t.sleep(1)
                        else:
                            st.warning("Descrição e Valor são obrigatórios na atualização.")

            with col_d:
                st.markdown("##### Excluir")
                st.warning(f"Excluindo: **{transacao_dados['Descricao']}** (R$ {transacao_dados['Valor']:,.2f})")
                
                if st.button("🔴 EXCLUIR TRANSAÇÃO (Delete)", type="primary", key='del_button'):
                    deletar_transacao(spreadsheet, transacao_selecionada_id)
                    t.sleep(1)

with st.sidebar:
    st.markdown("---")
    st.caption(f"Última leitura de dados: {datetime.now().strftime('%H:%M:%S')}")
