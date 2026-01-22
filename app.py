import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import hashlib

# 1. Função de Conexão (Liga o site ao Banco de Dados)
def get_engine():
    try:
        url = st.secrets["postgres_url"]
        return create_engine(url)
    except:
        st.error("Erro nos Segredos do Streamlit. Verifique o Passo 4.")
        return None

# 2. Função para proteger a senha
def hash_pass(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def main():
    st.set_page_config(page_title="SND GACC", layout="wide")
    engine = get_engine()
    if not engine: return

    # TELA DE LOGIN
    if 'logado' not in st.session_state: st.session_state.logado = False

    if not st.session_state.logado:
        st.title("🏥 SND - Hospital GACC")
        user = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        if st.button("Entrar"):
            with engine.connect() as conn:
                res = conn.execute(text("SELECT password FROM usuarios WHERE username = :u"), {"u": user}).fetchone()
                if res and hash_pass(senha) == res[0]:
                    st.session_state.logado = True
                    st.rerun()
                else: st.error("Usuário ou senha incorretos.")
        return

    # MENU APÓS LOGIN
    st.sidebar.title(f"Bem-vinda!")
    menu = st.sidebar.radio("Navegação", ["Estoque", "Cadastros"])
    
    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()

    if menu == "Estoque":
        st.header("📦 Saldo de Produtos")
        df = pd.read_sql("SELECT * FROM produtos", engine)
        st.dataframe(df, use_container_width=True)

    elif menu == "Cadastros":
        st.header("📝 Novo Produto")
        with st.form("cad_prod"):
            nome = st.text_input("Nome do Alimento")
            cat = st.text_input("Categoria (Ex: Secos)")
            if st.form_submit_button("Salvar"):
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO produtos (nome, categoria) VALUES (:n, :c)"), {"n": nome, "c": cat})
                    conn.commit()
                st.success("Cadastrado!")

if __name__ == "__main__":
    main()