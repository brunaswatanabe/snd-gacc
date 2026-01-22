import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import shutil
import os
from datetime import datetime

# --- CONFIGURAÇÕES DO BANCO DE DADOS ---
def init_db():
    # A mudança para v8 garante a criação de um banco novo com a estrutura correta
    conn = sqlite3.connect('estoque_v8.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS categorias (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)')
    c.execute('CREATE TABLE IF NOT EXISTS unidades (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT UNIQUE)')
    c.execute('''CREATE TABLE IF NOT EXISTS produtos 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, categoria TEXT, min_estoque REAL, 
                  unidade TEXT, preco_unit REAL, saldo REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS movimentacoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, produto_id INTEGER, tipo TEXT, 
                  quantidade REAL, preco_unit REAL, usuario TEXT, motivo TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS logs 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, usuario TEXT, acao TEXT, detalhe TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (username TEXT PRIMARY KEY, password TEXT, role TEXT, trocar_senha INTEGER DEFAULT 0,
                  p_leitura INTEGER DEFAULT 1, p_excluir INTEGER DEFAULT 0, p_cadastrar INTEGER DEFAULT 0)''')
    
    # Criar administrador padrão
    c.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    if not c.fetchone():
        c.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?, ?, ?)", 
                  ('admin', hashlib.sha256(str.encode('admin123')).hexdigest(), 'ADMINISTRADOR', 0, 1, 1, 1))
    conn.commit()
    return conn

# --- FUNÇÕES AUXILIARES ---
def registar_log(conn, usuario, acao, detalhe):
    c = conn.cursor()
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.execute("INSERT INTO logs (data, usuario, acao, detalhe) VALUES (?, ?, ?, ?)", (data_hora, usuario, acao, detalhe))
    conn.commit()

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- APLICAÇÃO ---
def main():
    st.set_page_config(page_title="Sistema de Gestão de Estoque", layout="wide")
    
    # Placeholder para imagem/logo
    # st.image("logo.png", width=150)

    conn = init_db()
    c = conn.cursor()

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    # --- LÓGICA DE LOGIN ---
    if not st.session_state['logged_in']:
        st.title("Acesso ao Sistema de Estoque")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type='password')
        if st.button("Entrar"):
            c.execute('SELECT * FROM usuarios WHERE username = ?', (u,))
            res = c.fetchone()
            if res and hash_pass(p) == res[1]:
                st.session_state.update({
                    'logged_in': True, 'user': u, 'role': res[2], 
                    'p_leitura': res[4], 'p_excluir': res[5], 'p_cadastrar': res[6]
                })
                registar_log(conn, u, "LOGIN", "Acesso realizado")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
        return

    # --- BARRA LATERAL (MENU E SAIR) ---
    st.sidebar.title("Menu Principal")
    st.sidebar.write(f"Usuário: **{st.session_state['user']}**")
    
    # BOTÃO SAIR: Colocado aqui para garantir visibilidade imediata após login
    if st.sidebar.button("🔴 SAIR DO SISTEMA"):
        registar_log(conn, st.session_state['user'], "LOGOUT", "Saída do sistema")
        st.session_state['logged_in'] = False
        st.rerun()
    
    st.sidebar.divider()
    
    # Definição das opções de navegação com base no perfil
    opcoes = ["Dashboard", "Estoque Atual", "Entradas e Saídas", "Cadastrar Itens", "Relatórios"]
    if st.session_state['role'] == 'ADMINISTRADOR':
        opcoes += ["Gestão de Usuários", "Painel de Logs"]
    
    choice = st.sidebar.radio("Navegação", opcoes)

    # --- TELAS ---
    if choice == "Dashboard":
        st.header("📊 Dashboard Gerencial")
        df = pd.read_sql('SELECT * FROM produtos', conn)
        if not df.empty:
            df['Status'] = df.apply(lambda x: "🚨 COMPRAR" if x['saldo'] <= x['min_estoque'] else "✅ OK", axis=1)
            c1, c2 = st.columns(2)
            c1.metric("Itens Cadastrados", len(df))
            c2.metric("Itens Críticos", len(df[df['Status'] == "🚨 COMPRAR"]))
            st.subheader("Visão Geral")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("O sistema ainda não possui produtos cadastrados.")

    elif choice == "Estoque Atual":
        st.header("📋 Estoque em Tempo Real")
        df_est = pd.read_sql('SELECT nome, categoria, saldo, unidade, min_estoque FROM produtos', conn)
        if not df_est.empty:
            df_est['Status'] = df_est.apply(lambda x: "🚨 COMPRAR" if x['saldo'] <= x['min_estoque'] else "✅ OK", axis=1)
            st.dataframe(df_est, use_container_width=True)
        else:
            st.info("Estoque vazio.")

    elif choice == "Entradas e Saídas":
        st.header("🔄 Movimentações")
        if st.session_state['p_cadastrar']:
            df_p = pd.read_sql('SELECT id, nome, preco_unit FROM produtos', conn)
            if not df_p.empty:
                with st.form("movimentacao"):
                    p_sel = st.selectbox("Produto", df_p['nome'].tolist())
                    tipo = st.selectbox("Tipo", ["Entrada", "Saída"])
                    qtd = st.number_input("Quantidade", min_value=0.01, format="%.2f")
                    mot = st.text_input("Observação")
                    if st.form_submit_button("Confirmar"):
                        idx = int(df_p[df_p['nome'] == p_sel]['id'].values[0])
                        v_u = float(df_p[df_p['nome'] == p_sel]['preco_unit'].values[0])
                        op = 1 if tipo == "Entrada" else -1
                        c.execute("UPDATE produtos SET saldo = saldo + ? WHERE id = ?", (qtd*op, idx))
                        c.execute("INSERT INTO movimentacoes (data, produto_id, tipo, quantidade, preco_unit, usuario, motivo) VALUES (?,?,?,?,?,?,?)",
                                  (datetime.now().strftime("%d/%m/%Y %H:%M"), idx, tipo, qtd, v_u, st.session_state['user'], mot))
                        registar_log(conn, st.session_state['user'], "MOVIMENTAÇÃO", f"{tipo}: {qtd} de {p_sel}")
                        conn.commit()
                        st.success("Operação realizada!")
            else: st.warning("Cadastre produtos primeiro.")
        else: st.error("Acesso negado para cadastro.")

    elif choice == "Cadastrar Itens":
        st.header("📝 Gestão de Cadastros")
        
        with st.expander("Gerenciar Categorias e Unidades"):
            col1, col2 = st.columns(2)
            # Categorias
            cat_n = col1.text_input("Nova Categoria")
            if col1.button("Salvar Categoria") and cat_n:
                try:
                    c.execute("INSERT INTO categorias (nome) VALUES (?)", (cat_n,))
                    registar_log(conn, st.session_state['user'], "CADASTRO CAT", cat_n)
                    conn.commit(); st.rerun()
                except: st.error("Erro ou categoria duplicada.")
            
            # Unidades
            un_n = col2.text_input("Nova Unidade (Kg, Un, etc)")
            if col2.button("Salvar Unidade") and un_n:
                try:
                    c.execute("INSERT INTO unidades (nome) VALUES (?)", (un_n,))
                    registar_log(conn, st.session_state['user'], "CADASTRO UNID", un_n)
                    conn.commit(); st.rerun()
                except: st.error("Erro.")

        st.divider()
        if st.session_state['p_cadastrar']:
            st.subheader("Novo Produto")
            l_cat = [r[0] for r in c.execute("SELECT nome FROM categorias").fetchall()]
            l_un = [r[0] for r in c.execute("SELECT nome FROM unidades").fetchall()]
            with st.form("produto"):
                nome = st.text_input("Nome do Item")
                ca = st.selectbox("Categoria", l_cat)
                un = st.selectbox("Unidade", l_un)
                mi = st.number_input("Estoque Mínimo", 0.0)
                pr = st.number_input("Preço Unitário", 0.0)
                if st.form_submit_button("Cadastrar"):
                    c.execute("INSERT INTO produtos (nome, categoria, min_estoque, unidade, preco_unit) VALUES (?,?,?,?,?)", (nome, ca, mi, un, pr))
                    registar_log(conn, st.session_state['user'], "NOVO PRODUTO", nome)
                    conn.commit(); st.success("Cadastrado!")

    elif choice == "Relatórios":
        st.header("📑 Histórico de Movimentações")
        df_rel = pd.read_sql('''SELECT m.data, p.nome as Item, m.tipo, m.quantidade, p.unidade, m.usuario, m.motivo 
                                FROM movimentacoes m JOIN produtos p ON m.produto_id = p.id ORDER BY m.id DESC''', conn)
        st.dataframe(df_rel, use_container_width=True)

    elif choice == "Gestão de Usuários":
        st.header("👥 Controle de Acessos")
        with st.form("usuario"):
            nu = st.text_input("Nome do Usuário")
            np = st.text_input("Senha")
            nr = st.selectbox("Perfil", ["USER", "ADMINISTRADOR"])
            p_l = st.checkbox("Permissão: Leitura", value=True)
            p_c = st.checkbox("Permissão: Cadastrar")
            p_e = st.checkbox("Permissão: Excluir")
            if st.form_submit_button("Criar Usuário"):
               conn.execute(text("INSERT INTO usuarios (username, password, role, trocar_senha, p_leitura, p_excluir, p_cadastrar) VALUES (:u, :p, :r, 1, :l, :e, :c)"),
               {"u": nu, "p": senha_h, "r": nr, "l": int(p_lei), "e": int(p_exc), "c": int(p_cad)})
                registar_log(conn, st.session_state['user'], "GESTÃO USUÁRIO", f"Criou: {nu}")
                conn.commit(); st.success("Usuário criado!")

    elif choice == "Painel de Logs":
        st.header("🕵️ Auditoria (Logs do Sistema)")
        df_logs = pd.read_sql('SELECT * FROM logs ORDER BY id DESC', conn)
        st.dataframe(df_logs, use_container_width=True)

if __name__ == '__main__':
    main()