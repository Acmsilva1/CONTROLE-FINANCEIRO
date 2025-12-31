# controle.py
import streamlit as st
import pandas as pd
from datetime import datetime
import time

# Importa a lógica do banco de dados/sheets (Garanta que db_utils.py está na mesma pasta!)
from db_utils import load_data_from_gsheets, save_transaction_to_gsheets 

# --- CONFIGURAÇÃO INICIAL E ESTILO ---
st.set_page_config(layout="wide", page_title="Controle Financeiro de Ouro")
st.title("💸 Terminal Financeiro de Comando Doméstico")

# --- AUTO-REFRESH E TIMER ---
placeholder = st.empty()

# --- CARREGAMENTO DE DADOS (COM CACHE) ---
df_transacoes, df_categorias = load_data_from_gsheets()

if df_transacoes.empty:
    st.error("Sem dados para análise. Verifique se o Streamlit Secrets, as permissões do Sheets e a estrutura de abas estão corretas. (Adicione dados de teste válidos!)")
else:
    # --- PREPARAÇÃO DE DADOS E FILTROS ---
    
    # 1. Filtra linhas com Data inválida (NaN/NaT) para evitar o erro 'NaN'
    df_transacoes = df_transacoes.dropna(subset=['Data']).copy() 
    
    if df_transacoes.empty:
        st.error("Após a limpeza de dados inválidos na coluna 'Data', o dataset ficou vazio. Verifique a formatação das datas na planilha.")
    else:
        # Adiciona colunas de análise
        df_transacoes['Ano_Mes'] = df_transacoes['Data'].dt.to_period('M').astype(str)
        df_transacoes['Sinal'] = df_transacoes['Tipo'].apply(lambda x: 1 if x == 'Receita' else -1)
        df_transacoes['Valor_Ajustado'] = df_transacoes['Valor'] * df_transacoes['Sinal']
        
        # Categorias para Selectboxes
        all_despesa_cats = df_categorias[df_categorias['Tipo'] == 'Despesa']['Categoria'].unique().tolist()
        all_receita_cats = df_categorias[df_categorias['Tipo'] == 'Receita']['Categoria'].unique().tolist()
        
        # Filtros de Mês/Ano (Sidebar)
        st.sidebar.header("🗓️ Filtro de Período")
        all_periods = sorted(df_transacoes['Ano_Mes'].unique(), reverse=True)
        
        default_period = all_periods[0] if all_periods else None
        selected_period = st.sidebar.selectbox("Selecione o Mês/Ano:", options=all_periods, index=0) if all_periods else "N/A"
            
        # APLICAÇÃO DO FILTRO
        df_filtrado = df_transacoes[df_transacoes['Ano_Mes'] == selected_period].copy()

        st.sidebar.caption(f"Análise atual: **{selected_period}**")
        st.sidebar.markdown("---")

        # --- FUNÇÃO PARA SALVAR COM RERUN ---
        def handle_submission(data_dict, success_message):
            if save_transaction_to_gsheets(data_dict):
                st.success(success_message)
                time.sleep(1) 
                st.rerun() 
            else:
                st.error("Falha ao salvar. Verifique o log.")

        
        # =================================================================
        # === DASHBOARD (PARTE 1) ===
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
        
        st.subheader("Onde o dinheiro REALMENTE está indo? (Gráfico de Despesas)")
        df_gastos = df_filtrado[df_filtrado['Tipo'] == 'Despesa'].groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
        st.bar_chart(df_gastos)
        
        st.markdown("---")
        
        # --- TABELA DE REGISTROS FILTRADOS ---
        st.subheader(f"📑 Registros de Transações ({selected_period})")
        df_display = df_filtrado[['Data', 'Descricao', 'Valor', 'Tipo', 'Categoria', 'Conta/Meio', 'Status']]
        df_display['Data'] = df_display['Data'].dt.strftime('%d/%m/%Y') 
        st.dataframe(df_display, use_container_width=True)

        st.markdown("#") # Espaço
        st.markdown("#") # Espaço
        st.markdown("---") 

        # =================================================================
        # === INSERÇÃO DE DADOS (TODOS OS 3 FORMULÁRIOS) ===
        # =================================================================

        st.header("📥 Inserção de Novas Transações")
        st.caption("Use os formulários abaixo para alimentar a máquina de dados.")
        
        # --- BLOCO 1: ADICIONAR RECEITAS ---
        with st.form("form_receita", clear_on_submit=True):
            st.subheader("💰 1. Adicionar Receita")
            col_r1, col_r2 = st.columns(2)
            descricao = col_r1.text_input("Descrição da Receita", key="desc_r")
            valor = col_r2.number_input("Valor Recebido (R$)", min_value=0.01, format="%.2f", key="val_r")
            col_r3, col_r4 = st.columns(2)
            categoria = col_r3.selectbox("Categoria", options=all_receita_cats, key="cat_r")
            conta = col_r4.text_input("Conta/Meio", key="cont_r")
            data = st.date_input("Data de Recebimento", value=datetime.now().date(), key="data_r") 
            submitted = st.form_submit_button("Lançar Receita!")
            
            if submitted:
                data_to_save = {
                    "Data": data.strftime('%d/%m/%Y'), 
                    "Descricao": descricao, "Valor": valor,
                    "Tipo": "Receita", "Categoria": categoria, "Subcategoria": "", 
                    "Conta/Meio": conta, "Status": "Compensado" 
                }
                handle_submission(data_to_save, f"Receita '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")

        st.markdown("---")
        
        # --- BLOCO 2: ADICIONAR DESPESA FIXA ---
        with st.form("form_fixa", clear_on_submit=True):
            st.subheader("🏠 2. Adicionar Despesa Fixa")
            col_f1, col_f2 = st.columns(2)
            descricao = col_f1.text_input("Descrição da Despesa Fixa", key="desc_f")
            valor = col_f2.number_input("Valor da Despesa (R$)", min_value=0.01, format="%.2f", key="val_f")
            col_f3, col_f4 = st.columns(2)
            categoria = col_f3.selectbox("Categoria", options=all_despesa_cats, key="cat_f")
            conta = col_f4.text_input("Conta/Meio de Pagamento", key="cont_f")
            data = st.date_input("Data de Vencimento/Pagamento", value=datetime.now().date(), key="data_f") 
            submitted = st.form_submit_button("Lançar Despesa Fixa!")
            
            if submitted:
                data_to_save = {
                    "Data": data.strftime('%d/%m/%Y'), 
                    "Descricao": descricao, "Valor": valor,
                    "Tipo": "Despesa", "Categoria": categoria, "Subcategoria": "Fixa", 
                    "Conta/Meio": conta, "Status": "Pago" 
                }
                handle_submission(data_to_save, f"Despesa Fixa '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")
        
        st.markdown("---")

        # --- BLOCO 3: ADICIONAR DESPESA VARIÁVEL ---
        with st.form("form_variavel", clear_on_submit=True):
            st.subheader("🛒 3. Adicionar Despesa Variável")
            col_v1, col_v2 = st.columns(2)
            descricao = col_v1.text_input("Descrição da Despesa Variável", key="desc_v")
            valor = col_v2.number_input("Valor da Despesa (R$)", min_value=0.01, format="%.2f", key="val_v")
            col_v3, col_v4 = st.columns(2)
            categoria = col_v3.selectbox("Categoria", options=all_despesa_cats, key="cat_v")
            conta = col_v4.text_input("Conta/Meio de Pagamento", key="cont_v")
            data = st.date_input("Data da Transação", value=datetime.now().date(), key="data_v") 
            submitted = st.form_submit_button("Lançar Despesa Variável!")
            
            if submitted:
                data_to_save = {
                    "Data": data.strftime('%d/%m/%Y'), 
                    "Descricao": descricao, "Valor": valor,
                    "Tipo": "Despesa", "Categoria": categoria, "Subcategoria": "Variável", 
                    "Conta/Meio": conta, "Status": "Pago" 
                }
                handle_submission(data_to_save, f"Despesa Variável '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")


        # --- FIM DO CÓDIGO DO APLICATIVO ---

    # --- TIMER STATUS ---
    with placeholder:
        st.caption(f"Última atualização de dados (Manual/Auto): {datetime.now().strftime('%H:%M:%S')}")
        st.markdown("---")

# --- REFRESH AUTOMÁTICO (NO FIM DO SCRIPT) ---
if not df_transacoes.empty:
    time.sleep(30) 
    st.rerun()
