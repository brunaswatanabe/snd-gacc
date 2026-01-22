import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import hashlib
from datetime import datetime

# --- INICIALIZAÇÃO DO BANCO ---
def init_db():
    try:
        # Puxa a URL que você colou no Secrets
        db_url = st.secrets["postgres_url"]
        engine = create_engine(db_url)
        # Cria a tabela de usuários se não existir no Supabase
        with engine.connect() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY, 
                    password TEXT, 
                    role TEXT, 
                    p_leitura INTEGER DEFAULT 1, 
                    p_excluir INTEGER DEFAULT 0, 
                    p_cadastrar INTEGER DEFAULT 0
                )
            '''))
            conn.commit()
        return engine
    except Exception as e:
        st.error(f"Erro de Conexão: {e}")
        return None

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def main():
    st.set_page_config(page_title="SND - Hospital GACC", layout="wide")
    
    # Logo do GACC
    try: st.sidebar.image("logo.png", use_container_width=True)
    except: pass

    engine = init_db()
    if not engine: return

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    # --- TELA DE LOGIN ---
    if not st.session_state['logged_in']:
        st.title("🏥 SND - Hospital GACC")
        u = st.text_input("Usuário")
        p = st.text_input("Senha", type='password')
        if st.button("Entrar"):
            with engine.connect() as conn:
                res = conn.execute(text("SELECT * FROM usuarios WHERE username = :u"), {"u": u}).fetchone()
                if res and hash_pass(p) == res[1]:
                    st.session_state.update({'logged_in': True, 'user': u})
                    st.rerun()
                else: st.error("Login inválido.")
        return

    # --- GESTÃO DE USUÁRIOS (FIX PARA O ERRO SQLITE) ---
    st.header("👥 Controle de Acessos")
    with st.form("novo_usuario"):
        nu = st.text_input("Nome")
        np = st.text_input("Senha", type='password')
        if st.form_submit_button("Criar Usuário"):
            try:
                with engine.connect() as conn:
                    # Aqui usamos o engine do Supabase, NÃO o sqlite3
                    conn.execute(text("INSERT INTO usuarios (username, password) VALUES (:u, :p)"), 
                                 {"u": nu, "p": hash_pass(np)})
                    conn.commit()
                st.success(f"Usuário {nu} cadastrado na nuvem!")
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

if __name__ == '__main__':
    main()