# controle.py
import streamlit as st
import pandas as pd
from datetime import datetime

# Importa a lógica do banco de dados/sheets (Garanta que db_utils.py está na mesma pasta!)
from db_utils import load_data_from_gsheets, save_transaction_to_gsheets 

# --- CONFIGURAÇÃO INICIAL E ESTILO ---
st.set_page_config(layout="wide", page_title="Controle Financeiro de Ouro")
st.title("💸 Terminal Financeiro de Comando Doméstico")
st.markdown("---")

# --- CARREGAMENTO DE DADOS (Ponto Crítico de Falha) ---
# Tenta carregar os dados. Se as credenciais ou a planilha falharem, o código para aqui.
df_transacoes, df_categorias = load_data_from_gsheets()

if df_transacoes.empty:
    st.error("Sem dados para análise. Verifique se o Streamlit Secrets, as permissões do Sheets e a estrutura de abas estão corretas.")
else:
    # --- PREPARAÇÃO DE DADOS PARA ANÁLISE ---
    
    # Adiciona o sinal (1 para Receita, -1 para Despesa) para cálculo da Margem
    df_transacoes['Sinal'] = df_transacoes['Tipo'].apply(lambda x: 1 if x == 'Receita' else -1)
    df_transacoes['Valor_Ajustado'] = df_transacoes['Valor'] * df_transacoes['Sinal']
    
    # Define as categorias para os Selectboxes (puxando da aba CATEGORIAS)
    all_despesa_cats = df_categorias[df_categorias['Tipo'] == 'Despesa']['Categoria'].unique().tolist()
    all_receita_cats = df_categorias[df_categorias['Tipo'] == 'Receita']['Categoria'].unique().tolist()
    
    # Categorias Fictícias: Ajuste estas listas conforme as categorias reais no seu Sheets!
    FIXED_CATEGORIES_DEFAULT = ['Moradia', 'Assinaturas', 'Educação', 'Contas', 'Empréstimos']
    fixed_cats = [cat for cat in all_despesa_cats if cat in FIXED_CATEGORIES_DEFAULT]
    variable_cats = [cat for cat in all_despesa_cats if cat not in FIXED_CATEGORIES_DEFAULT]
    
    # Se a filtragem falhar, usa todas as despesas como fallback
    if not fixed_cats: fixed_cats = all_despesa_cats
    if not variable_cats: variable_cats = all_despesa_cats


    # --- CRIAÇÃO DAS ABAS (DASHBOARD E INSERÇÃO) ---
    tab_dashboard, tab_insercao = st.tabs(["📊 Dashboard: Indicadores de Comando", "📥 Inserção de Novas Transações"])

    # --- ABA 1: DASHBOARD DE MÉTRICAS (KPIs) ---
    with tab_dashboard:
        st.header("KPIs: O Sarcasmo da Sua Riqueza")
        
        # Cálculo das Métricas
        total_receita = df_transacoes[df_transacoes['Tipo'] == 'Receita']['Valor'].sum()
        total_despesa = df_transacoes[df_transacoes['Tipo'] == 'Despesa']['Valor'].sum()
        margem_liquida = total_receita - total_despesa
        
        margem_delta_color = "inverse" if margem_liquida < 0 else "normal"

        col1, col2, col3 = st.columns(3)
        
        col1.metric("Total de Receitas", f"R$ {total_receita:,.2f}", delta="Caminho do Sucesso")
        col2.metric("Total de Despesas", f"R$ {total_despesa:,.2f}", delta="O Burocrata do Seu Bolso")
        col3.metric("Margem Líquida (Lucro/Prejuízo)", 
                    f"R$ {margem_liquida:,.2f}", 
                    delta=f"{'NEGATIVA' if margem_liquida < 0 else 'POSITIVA'} - A Realidade Financeira", 
                    delta_color=margem_delta_color)

        st.markdown("---")
        st.subheader("Onde o dinheiro REALMENTE está indo? (Gráfico de Despesas)")
        
        df_gastos = df_transacoes[df_transacoes['Tipo'] == 'Despesa'].groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
        st.bar_chart(df_gastos)


    # --- ABA 2: FORMULÁRIOS DE INSERÇÃO ---
    with tab_insercao:
        st.header("Operações Manuais: Alimentando a Máquina de Dados")
        
        # --- BLOCO 1: ADICIONAR RECEITAS ---
        with st.form("form_receita", clear_on_submit=True):
            st.subheader("💰 Adicionar Receita")
            col_r1, col_r2 = st.columns(2)
            descricao = col_r1.text_input("Descrição da Receita", key="desc_r")
            valor = col_r2.number_input("Valor Recebido (R$)", min_value=0.01, format="%.2f", key="val_r")
            col_r3, col_r4 = st.columns(2)
            categoria = col_r3.selectbox("Categoria", options=all_receita_cats, key="cat_r")
            conta = col_r4.text_input("Conta/Meio", key="cont_r")
            data = st.date_input("Data de Recebimento", value="today", key="data_r")
            submitted = st.form_submit_button("Lançar Receita!")
            
            if submitted:
                data_to_save = {
                    "Data": data.strftime('%Y-%m-%d'), "Descricao": descricao, "Valor": valor,
                    "Tipo": "Receita", "Categoria": categoria, "Subcategoria": "", 
                    "Conta/Meio": conta, "Status": "Compensado" 
                }
                if save_transaction_to_gsheets(data_to_save):
                    st.success(f"Receita '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")

        st.markdown("---")

        # --- BLOCO 2: ADICIONAR CONTAS FIXAS ---
        with st.form("form_fixa", clear_on_submit=True):
            st.subheader("🏠 Adicionar Conta Fixa (Recorrente)")
            st.caption(f"Categorias Fixas: {', '.join(fixed_cats)}")
            
            col_f1, col_f2 = st.columns(2)
            descricao = col_f1.text_input("Descrição da Conta Fixa", key="desc_f")
            valor = col_f2.number_input("Valor da Conta (R$)", min_value=0.01, format="%.2f", key="val_f")
            col_f3, col_f4 = st.columns(2)
            categoria = col_f3.selectbox("Categoria Fixa", options=fixed_cats, key="cat_f")
            status = col_f4.selectbox("Status", options=['Pendente', 'Pago'], key="status_f")
            data = st.date_input("Data de Vencimento/Pagamento", value="today", key="data_f")
            
            submitted_f = st.form_submit_button("Lançar Conta Fixa!")
            if submitted_f:
                data_to_save = {
                    "Data": data.strftime('%Y-%m-%d'), "Descricao": descricao, "Valor": valor,
                    "Tipo": "Despesa", "Categoria": categoria, "Subcategoria": "", 
                    "Conta/Meio": "A Definir", "Status": status 
                }
                if save_transaction_to_gsheets(data_to_save):
                    st.success(f"Conta Fixa '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")

        st.markdown("---")

        # --- BLOCO 3: ADICIONAR CONTAS VARIÁVEIS ---
        with st.form("form_variavel", clear_on_submit=True):
            st.subheader("🛒 Adicionar Conta Variável (Esporádica)")
            st.caption(f"Categorias Variáveis: {', '.join(variable_cats)}")
            
            col_v1, col_v2 = st.columns(2)
            descricao = col_v1.text_input("Descrição da Conta Variável", key="desc_v")
            valor = col_v2.number_input("Valor da Compra (R$)", min_value=0.01, format="%.2f", key="val_v")
            col_v3, col_v4 = st.columns(2)
            categoria = col_v3.selectbox("Categoria Variável", options=variable_cats, key="cat_v")
            conta = col_v4.text_input("Conta/Meio", key="cont_v")
            data = st.date_input("Data da Compra", value="today", key="data_v")
            
            submitted_v = st.form_submit_button("Lançar Conta Variável!")

            if submitted_v:
                data_to_save = {
                    "Data": data.strftime('%Y-%m-%d'), "Descricao": descricao, "Valor": valor,
                    "Tipo": "Despesa", "Categoria": categoria, "Subcategoria": "", 
                    "Conta/Meio": conta, "Status": "Pago"
                }
                if save_transaction_to_gsheets(data_to_save):
                    st.success(f"Conta Variável '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")
