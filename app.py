import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import hashlib
from datetime import datetime

# --- CONEXÃO SUPABASE ---
def init_db():
    try:
        db_url = st.secrets["postgres_url"]
        engine = create_engine(db_url)
        # Criação das tabelas no formato Postgres
        with engine.connect() as conn:
            conn.execute(text('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    username TEXT PRIMARY KEY, 
                    password TEXT, 
                    role TEXT, 
                    trocar_senha INTEGER DEFAULT 0,
                    p_leitura INTEGER DEFAULT 1, 
                    p_excluir INTEGER DEFAULT 0, 
                    p_cadastrar INTEGER DEFAULT 0
                )
            '''))
            conn.commit()
        return engine
    except Exception as e:
        st.error(f"Erro de conexão com a Nuvem: {e}")
        return None

def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def main():
    st.set_page_config(page_title="SND - Hospital GACC", layout="wide")
    
    # Logo do GACC (vencendo o desafio técnico)
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
                    st.session_state.update({'logged_in': True, 'user': u, 'role': res[2], 'p_cadastrar': res[6]})
                    st.rerun()
                else: st.error("Login inválido.")
        return

    # --- GESTÃO DE USUÁRIOS (ONDE DAVA O ERRO) ---
    st.header("👥 Controle de Acessos")
    with st.form("new_user"):
        nu = st.text_input("Nome do Usuário")
        np = st.text_input("Senha", type='password')
        nr = st.selectbox("Perfil", ["USER", "ADMINISTRADOR"])
        c1, c2, c3 = st.columns(3)
        p_lei = c1.checkbox("Permissão: Leitura", value=True)
        p_cad = c2.checkbox("Permissão: Cadastrar")
        p_exc = c3.checkbox("Permissão: Excluir")
        
        if st.form_submit_button("Criar Usuário"):
            try:
                senha_h = hash_pass(np)
                with engine.connect() as conn:
                    # SQL Explícito para Postgres
                    conn.execute(text("""
                        INSERT INTO usuarios (username, password, role, trocar_senha, p_leitura, p_excluir, p_cadastrar) 
                        VALUES (:u, :p, :r, 0, :l, :e, :c)
                    """), {"u": nu, "p": senha_h, "r": nr, "l": int(p_lei), "e": int(p_exc), "c": int(p_cad)})
                    conn.commit()
                st.success(f"Usuário {nu} criado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao salvar no Supabase: {e}")

if __name__ == '__main__':
    main()