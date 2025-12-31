# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import uuid # Para gerar IDs únicos (Governança!)

# Importa a lógica do banco de dados/sheets
from db_utils import load_data_from_gsheets, save_transaction_to_gsheets 

st.set_page_config(layout="wide", page_title="Controle Financeiro de Ouro")
st.title("💸 Terminal Financeiro de Comando Doméstico")
st.markdown("---")

# Carrega os dados (função com cache)
df_transacoes, df_categorias = load_data_from_gsheets()

if df_transacoes.empty:
    st.warning("Sem dados carregados. Por favor, verifique as credenciais e o URL da Planilha no db_utils.py.")
else:
    # Cria as abas/tabs
    tab_dashboard, tab_insercao = st.tabs(["📊 Dashboard: Indicadores de Comando", "📥 Inserção de Novas Transações"])

    # --- ABA 1: DASHBOARD ---
    with tab_dashboard:
        st.header("KPIs: O Sarcasmo da Sua Riqueza")
        
        # 1. Cálculo de Métricas (O Pulo do Gato da TI)
        # Transformar o Tipo (Receita/Despesa) em um Sinal (+1/-1) e recalcular o valor
        df_transacoes['Sinal'] = df_transacoes['Tipo'].apply(lambda x: 1 if x == 'Receita' else -1)
        df_transacoes['Valor_Ajustado'] = df_transacoes['Valor'] * df_transacoes['Sinal']
        
        total_receita = df_transacoes[df_transacoes['Tipo'] == 'Receita']['Valor'].sum()
        total_despesa = df_transacoes[df_transacoes['Tipo'] == 'Despesa']['Valor'].sum()
        margem_liquida = total_receita - total_despesa
        
        # Determinando a Cor da Margem (Alegria ou Desespero)
        margem_delta_color = "inverse" if margem_liquida < 0 else "normal"

        col1, col2, col3 = st.columns(3)
        
        # Métrica 1: Receita
        col1.metric("Total de Receitas", f"R$ {total_receita:,.2f}", delta="Caminho do Sucesso")
        
        # Métrica 2: Despesa
        col2.metric("Total de Despesas", f"R$ {total_despesa:,.2f}", delta="O Burocrata do Seu Bolso")
        
        # Métrica 3: Margem Líquida
        col3.metric("Margem Líquida (Lucro/Prejuízo)", 
                    f"R$ {margem_liquida:,.2f}", 
                    delta=f"{'NEGATIVA' if margem_liquida < 0 else 'POSITIVA'} - A Realidade Financeira", 
                    delta_color=margem_delta_color)

        st.markdown("---")
        st.subheader("Onde o dinheiro REALMENTE está indo?")
        
        # Gráfico Básico de Despesas por Categoria
        df_gastos = df_transacoes[df_transacoes['Tipo'] == 'Despesa'].groupby('Categoria')['Valor'].sum().sort_values(ascending=False)
        st.bar_chart(df_gastos)

    # --- ABA 2: INSERÇÃO ---
    with tab_insercao:
        st.header("Operações Manuais: Alimentando a IA (e a Planilha)")
        st.markdown("Use os blocos abaixo para registrar seus movimentos. Lembre-se, **Contas Fixas** e **Contas Variáveis** são ambas Despesas, o que muda é a Categoria que você atribui (Ex: Moradia é Fixa, Lazer é Variável).")

        # -----------------------------------------------------
        # 1. BLOCO ADICIONAR RECEITAS
        # -----------------------------------------------------
        with st.form("form_receita", clear_on_submit=True):
            st.subheader("➕ Adicionar Receita")
            
            # Filtra categorias válidas para Receita
            receita_cats = df_categorias[df_categorias['Tipo'] == 'Receita']['Categoria'].unique().tolist()
            
            col_r1, col_r2 = st.columns(2)
            
            # Campos do Formulário
            descricao = col_r1.text_input("Descrição da Receita", key="desc_r")
            valor = col_r2.number_input("Valor Recebido (R$)", min_value=0.01, format="%.2f", key="val_r")
            
            col_r3, col_r4 = st.columns(2)
            categoria = col_r3.selectbox("Categoria", options=receita_cats, key="cat_r")
            conta = col_r4.text_input("Conta/Meio (Ex: Salário, Conta PJ)", key="cont_r") # Idealmente um selectbox
            
            data = st.date_input("Data de Recebimento", value="today", key="data_r")
            
            submitted = st.form_submit_button("Lançar Receita!")
            
            if submitted:
                # Monta o dicionário de dados para salvar
                new_id = f"TRX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4]}"
                data_to_save = {
                    "ID Transacao": new_id,
                    "Data": data.strftime('%Y-%m-%d'),
                    "Descricao": descricao,
                    "Valor": valor,
                    "Tipo": "Receita", # Tipo fixo
                    "Categoria": categoria,
                    "Subcategoria": "", # Preencher se for necessário (opcional)
                    "Conta/Meio": conta,
                    "Status": "Compensado" # Status padrão
                }
                
                if save_transaction_to_gsheets(data_to_save):
                    st.success(f"Receita '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")
                else:
                    st.error("Falha ao salvar. Verifique as credenciais ou a conexão com o Sheets.")

        st.markdown("---")

        # -----------------------------------------------------
        # 2. BLOCO ADICIONAR CONTAS FIXAS (Despesa Categoria 'Fixa')
        # -----------------------------------------------------
        with st.form("form_fixa", clear_on_submit=True):
            st.subheader("➖ Adicionar Conta Fixa (Despesa Recorrente)")
            
            # Sugestão: Use Categorias específicas que você definiu como Fixas (e.g., Moradia, Assinaturas)
            despesa_cats = df_categorias[df_categorias['Tipo'] == 'Despesa']['Categoria'].unique().tolist()

            # Seleção de categorias fixas (Ajuste conforme suas categorias no Sheets)
            categorias_fixas = [cat for cat in despesa_cats if cat in ['Moradia', 'Assinaturas', 'Educação']]
            
            col_f1, col_f2 = st.columns(2)
            
            descricao = col_f1.text_input("Descrição da Conta Fixa", key="desc_f")
            valor = col_f2.number_input("Valor da Conta (R$)", min_value=0.01, format="%.2f", key="val_f")
            
            col_f3, col_f4 = st.columns(2)
            categoria = col_f3.selectbox("Categoria Fixa", options=categorias_fixas, key="cat_f")
            data = col_f4.date_input("Data de Vencimento/Pagamento", value="today", key="data_f")
            
            status = st.selectbox("Status", options=['Pendente', 'Pago'], key="status_f")
            
            submitted_f = st.form_submit_button("Lançar Conta Fixa!")

            if submitted_f:
                # Monta o dicionário de dados
                new_id = f"TRX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4]}"
                data_to_save = {
                    "ID Transacao": new_id,
                    "Data": data.strftime('%Y-%m-%d'),
                    "Descricao": descricao,
                    "Valor": valor,
                    "Tipo": "Despesa", 
                    "Categoria": categoria,
                    "Subcategoria": "", 
                    "Conta/Meio": "A Definir", 
                    "Status": status 
                }

                if save_transaction_to_gsheets(data_to_save):
                    st.success(f"Conta Fixa '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")
                else:
                    st.error("Falha ao salvar. Tente novamente ou verifique o log.")

        st.markdown("---")

        # -----------------------------------------------------
        # 3. BLOCO ADICIONAR CONTAS VARIÁVEIS (Despesa Categoria 'Variável')
        # -----------------------------------------------------
        with st.form("form_variavel", clear_on_submit=True):
            st.subheader("🛍️ Adicionar Conta Variável (Despesa Esporádica)")
            
            # Sugestão: Use Categorias específicas que você definiu como Variáveis (e.g., Lazer, Alimentação, Vestuário)
            despesa_cats = df_categorias[df_categorias['Tipo'] == 'Despesa']['Categoria'].unique().tolist()
            categorias_variaveis = [cat for cat in despesa_cats if cat not in ['Moradia', 'Assinaturas', 'Educação']] # Exemplo

            col_v1, col_v2 = st.columns(2)
            
            descricao = col_v1.text_input("Descrição da Conta Variável", key="desc_v")
            valor = col_v2.number_input("Valor da Conta (R$)", min_value=0.01, format="%.2f", key="val_v")
            
            col_v3, col_v4 = st.columns(2)
            categoria = col_v3.selectbox("Categoria Variável", options=categorias_variaveis, key="cat_v")
            data = col_v4.date_input("Data da Compra", value="today", key="data_v")
            
            submitted_v = st.form_submit_button("Lançar Conta Variável!")

            if submitted_v:
                # Monta o dicionário de dados
                new_id = f"TRX-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:4]}"
                data_to_save = {
                    "ID Transacao": new_id,
                    "Data": data.strftime('%Y-%m-%d'),
                    "Descricao": descricao,
                    "Valor": valor,
                    "Tipo": "Despesa", 
                    "Categoria": categoria,
                    "Subcategoria": "", 
                    "Conta/Meio": "A Definir", 
                    "Status": "Pago"
                }

                if save_transaction_to_gsheets(data_to_save):
                    st.success(f"Conta Variável '{descricao}' (R$ {valor:,.2f}) registrada com sucesso!")
                else:
                    st.error("Falha ao salvar. Tente novamente ou verifique o log.")
