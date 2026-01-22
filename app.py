import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import hashlib
from datetime import datetime

# --- CONFIGURAÇÃO DA CONEXÃO EM NUVEM ---
def init_db():
    # A URL será configurada no painel do Streamlit Cloud depois
    db_url = st.secrets["postgres_url"]
    engine = create_engine(db_url)
    
    # Criar tabelas iniciais se não existirem (Sintaxe PostgreSQL)
    with engine.connect() as conn:
        conn.execute(text('CREATE TABLE IF NOT EXISTS categorias (id SERIAL PRIMARY KEY, nome TEXT UNIQUE)'))
        conn.execute(text('CREATE TABLE IF NOT EXISTS unidades (id SERIAL PRIMARY KEY, nome TEXT UNIQUE)'))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS produtos 
                           (id SERIAL PRIMARY KEY, nome TEXT, categoria TEXT, min_estoque REAL, 
                            unidade TEXT, preco_unit REAL, saldo REAL DEFAULT 0)'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS movimentacoes 
                           (id SERIAL PRIMARY KEY, data TEXT, produto_id INTEGER, tipo TEXT, 
                            quantidade REAL, preco_unit REAL, usuario TEXT, motivo TEXT)'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS logs 
                           (id SERIAL PRIMARY KEY, data TEXT, usuario TEXT, acao TEXT, detalhe TEXT)'''))
        conn.execute(text('''CREATE TABLE IF NOT EXISTS usuarios 
                           (username TEXT PRIMARY KEY, password TEXT, role TEXT, trocar_senha INTEGER DEFAULT 0,
                            p_leitura INTEGER DEFAULT 1, p_excluir INTEGER DEFAULT 0, p_cadastrar INTEGER DEFAULT 0)'''))
        
        # Verificar admin
        res = conn.execute(text("SELECT * FROM usuarios WHERE username = 'admin'")).fetchone()
        if not res:
            senha_admin = hashlib.sha256(str.encode('admin123')).hexdigest()
            conn.execute(text("INSERT INTO usuarios VALUES (:u, :p, :r, 0, 1, 1, 1)"),
                         {"u": 'admin', "p": senha_admin, "r": 'ADMINISTRADOR'})
        conn.commit()
    return engine

def registar_log(engine, usuario, acao, detalhe):
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    with engine.connect() as conn:
        conn.execute(text("INSERT INTO logs (data, usuario, acao, detalhe) VALUES (:d, :u, :a, :det)"),
                     {"d": data_hora, "u": usuario, "a": acao, "det": detalhe})
        conn.commit()

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def main():
    st.set_page_config(page_title="SND - Hospital GACC", layout="wide")
    
    try: st.image("logo.png", width=150)
    except: pass

    engine = init_db()

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    # --- LOGIN ---
    if not st.session_state['logged_in']:
        st.title("🏥 SND - Hospital GACC")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type='password')
        if st.button("Entrar"):
            with engine.connect() as conn:
                res = conn.execute(text("SELECT * FROM usuarios WHERE username = :u"), {"u": u}).fetchone()
                if res and hash_pass(p) == res[1]:
                    st.session_state.update({
                        'logged_in': True, 'user': u, 'role': res[2], 
                        'p_leitura': res[4], 'p_excluir': res[5], 'p_cadastrar': res[6]
                    })
                    st.rerun()
                else: st.error("Login inválido.")
        return

    # --- BARRA LATERAL ---
    st.sidebar.title("Menu")
    if st.sidebar.button("🔴 Sair"):
        st.session_state['logged_in'] = False
        st.rerun()

    menu = ["Dashboard", "Estoque Atual", "Entradas e Saídas", "Cadastrar Itens", "Relatórios"]
    if st.session_state['role'] == 'ADMINISTRADOR':
        menu += ["Gestão de Usuários", "Painel de Logs"]
    
    choice = st.sidebar.radio("Navegação", menu)

    # --- TELAS (RESUMO) ---
    if choice == "Dashboard":
        st.header("📊 Painel Gerencial")
        df = pd.read_sql('SELECT * FROM produtos', engine)
        if not df.empty:
            st.metric("Total de Itens", len(df))
            st.dataframe(df, use_container_width=True)
        else: st.info("Sistema vazio na nuvem.")

    elif choice == "Cadastrar Itens":
        st.header("📝 Cadastros")
        with st.expander("Categorias"):
            nc = st.text_input("Nova Categoria")
            if st.button("Salvar") and nc:
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO categorias (nome) VALUES (:n)"), {"n": nc})
                    conn.commit()
                st.rerun()
        
        # ... (Outras funções de cadastro seguem a mesma lógica de conexão)

    # --- 7. PAINEL DE LOGS (ADMIN APENAS) ---
    elif choice == "Painel de Logs":
        st.header("🕵️ Auditoria (Logs do Sistema)")
        # Note que agora usamos 'engine' (da nuvem) em vez de 'conn' (local)
        df_logs = pd.read_sql('SELECT * FROM logs ORDER BY id DESC', engine)
        st.dataframe(df_logs, use_container_width=True)

if __name__ == '__main__':
    main()