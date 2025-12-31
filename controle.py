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
# Usa um container temporário para mensagens de status e o timer
placeholder = st.empty()
with placeholder:
    # Mostra o status do último refresh
    st.caption(f"Última atualização de dados (Manual/Auto): {datetime.now().strftime('%H:%M:%S')}")
    st.markdown("---")

# --- CARREGAMENTO DE DADOS (AGORA COM CACHE) ---
df_transacoes, df_categorias = load_data_from_gsheets()

if df_transacoes.empty:
    st.error("Sem dados para análise. Verifique se o Streamlit Secrets, as permissões do Sheets e a estrutura de abas estão corretas. (Adicione dados de teste!)")
else:
    # --- PREPARAÇÃO DE DADOS E FILTROS ---
    
    # Adiciona colunas para filtragem
    df_transacoes['Ano_Mes'] = df_transacoes['Data'].dt.to_period('M').astype(str)
    df_transacoes['Sinal'] = df_transacoes['Tipo'].apply(lambda x: 1 if x == 'Receita' else -1)
    df_transacoes['Valor_Ajustado'] = df_transacoes['Valor'] * df_transacoes['Sinal']
    
    # Categorias para Selectboxes
    all_despesa_cats = df_categorias[df_categorias['Tipo'] == 'Despesa']['Categoria'].unique().tolist()
    all_receita_cats = df_categorias[df_categorias['Tipo'] == 'Receita']['Categoria'].unique().tolist()
    
    # Filtros de Mês/Ano (Sidebar)
    st.sidebar.header("🗓️ Filtro de Período")
    all_periods = sorted(df_transacoes['Ano_Mes'].unique(), reverse=True)
    
    if all_periods:
        default_period = all_periods[0] # Mês mais recente como padrão
        selected_period = st.sidebar.selectbox("Selecione o Mês/Ano:", options=all_periods, index=0)
        
        # APLICAÇÃO DO FILTRO
        df_filtrado = df_transacoes[df_transacoes['Ano_Mes'] == selected_period].copy()
    else:
        df_filtrado = df_transacoes.copy()
        selected_period = "Todos os Períodos"

    st.sidebar.caption(f"Análise atual: **{selected_period}**")
    st.sidebar.markdown("---")


    # --- CRIAÇÃO DAS ABAS (DASHBOARD E INSERÇÃO) ---
    tab_dashboard, tab_insercao = st.tabs(["📊 Dashboard: Indicadores de Comando", "📥 Inserção de Novas Transações"])

    # --- ABA 1: DASHBOARD DE MÉTRICAS (KPIs) ---
    with tab_dashboard:
        st.header(f"KPIs do Período: {selected_period}")
        
        # Cálculo das Métricas com DADOS FILTRADOS
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
        
        # --- NOVO: TABELA DE REGISTROS FILTRADOS ---
        st.subheader(f"📑 Registros de Transações ({selected_period})")
        # Seleciona apenas as colunas relevantes para exibição
        df_display = df_filtrado[['Data', 'Descricao', 'Valor', 'Tipo', 'Categoria', 'Conta/Meio', 'Status']]
        st.dataframe(df_display, use_container_width=True)


    # --- ABA 2: FORMULÁRIOS DE INSERÇÃO ---
    with tab_insercao:
        st.header("Operações Manuais: Alimentando a Máquina de Dados")
        
        # Função para salvar dados com Rerun
        def handle_submission(data_dict, success_message):
            if save_transaction_to_gsheets(data_dict):
                st.success(success_message)
                # O RERUN É CRÍTICO para buscar os dados novos
                st.rerun() 
            else:
                st.error("Falha ao salvar. Verifique o log.")

        # --- BLOCO 1: ADICIONAR RECEITAS ---
        with st.form("form_receita", clear_on_submit=True):
            st.subheader("💰 Adicionar Receita")
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
                    "Data": data.strftime('%Y-%m-%d'), "Descricao": descricao, "Valor": valor,
                    "Tipo": "Receita", "Categoria": categoria, "Subcategoria": "", 
                    "Conta/Meio": conta, "Status": "Compensado" 
                }
                handle_submission(data_to_save, f"Receita '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")

        st.markdown("---")

        # ... (Outros formulários: fixos e variáveis, usando handle_submission) ...
        # (Para manter o foco, os blocos de Conta Fixa e Variável precisam ser replicados usando handle_submission)
        
# --- FIM DO CÓDIGO DO APLICATIVO ---

# --- REFRESH AUTOMÁTICO (NO FIM DO SCRIPT) ---
time.sleep(20) # Pausa o script por 20 segundos
st.rerun() # Força o recarregamento, limpando o cache se o ttl tiver expirado ou se houver nova submissão
