import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import hashlib
from datetime import datetime

# --- CONFIGURAÇÃO DA CONEXÃO EM NUVEM ---
def init_db():
    # URL configurada no Secrets do Streamlit Cloud
    db_url = st.secrets["postgres_url"]
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # 1. Categorias
        conn.execute(text('CREATE TABLE IF NOT EXISTS categorias (id SERIAL PRIMARY KEY, nome TEXT UNIQUE)'))
        # 2. Unidades
        conn.execute(text('CREATE TABLE IF NOT EXISTS unidades (id SERIAL PRIMARY KEY, nome TEXT UNIQUE)'))
        # 3. Produtos
        conn.execute(text('''CREATE TABLE IF NOT EXISTS produtos 
                           (id SERIAL PRIMARY KEY, nome TEXT, categoria TEXT, min_estoque REAL, 
                            unidade TEXT, preco_unit REAL, saldo REAL DEFAULT 0)'''))
        # 4. Movimentações
        conn.execute(text('''CREATE TABLE IF NOT EXISTS movimentacoes 
                           (id SERIAL PRIMARY KEY, data TEXT, produto_id INTEGER, tipo TEXT, 
                            quantidade REAL, preco_unit REAL, usuario TEXT, motivo TEXT)'''))
        # 5. Logs
        conn.execute(text('''CREATE TABLE IF NOT EXISTS logs 
                           (id SERIAL PRIMARY KEY, data TEXT, usuario TEXT, acao TEXT, detalhe TEXT)'''))
        # 6. Usuários
        conn.execute(text('''CREATE TABLE IF NOT EXISTS usuarios 
                           (username TEXT PRIMARY KEY, password TEXT, role TEXT, trocar_senha INTEGER DEFAULT 0,
                            p_leitura INTEGER DEFAULT 1, p_excluir INTEGER DEFAULT 0, p_cadastrar INTEGER DEFAULT 0)'''))
        
        # Verificar se existe o admin padrão
        res = conn.execute(text("SELECT * FROM usuarios WHERE username = 'admin'")).fetchone()
        if not res:
            senha_admin = hashlib.sha256(str.encode('admin123')).hexdigest()
            conn.execute(text("INSERT INTO usuarios (username, password, role, trocar_senha, p_leitura, p_excluir, p_cadastrar) VALUES (:u, :p, :r, 0, 1, 1, 1)"),
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
    
    try:
        st.sidebar.image("logo.png", use_container_width=True)
    except:
        pass

    engine = init_db()

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
                    st.session_state.update({
                        'logged_in': True, 'user': u, 'role': res[2], 
                        'p_leitura': res[4], 'p_excluir': res[5], 'p_cadastrar': res[6]
                    })
                    registar_log(engine, u, "LOGIN", "Entrou no sistema")
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")
        return

    # --- BARRA LATERAL ---
    st.sidebar.title("Navegação")
    if st.sidebar.button("🔴 Sair do Sistema"):
        st.session_state['logged_in'] = False
        st.rerun()

    menu = ["Dashboard", "Estoque Atual", "Entradas e Saídas", "Cadastrar Itens", "Relatórios"]
    if st.session_state['role'] == 'ADMINISTRADOR':
        menu += ["Gestão de Usuários", "Painel de Logs"]
    
    choice = st.sidebar.radio("Ir para:", menu)

    # --- 1. DASHBOARD ---
    if choice == "Dashboard":
        st.header("📊 Painel Gerencial")
        df = pd.read_sql('SELECT * FROM produtos', engine)
        if not df.empty:
            c1, c2 = st.columns(2)
            c1.metric("Total de Itens", len(df))
            v_estoque = (df['saldo'] * df['preco_unit']).sum()
            c2.metric("Valor em Estoque", f"R$ {v_estoque:,.2f}")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("O estoque está vazio.")

    # --- 2. ESTOQUE ATUAL ---
    elif choice == "Estoque Atual":
        st.header("📋 Saldo em Tempo Real")
        df_est = pd.read_sql('SELECT nome, categoria, saldo, unidade, min_estoque FROM produtos', engine)
        if not df_est.empty:
            df_est['Status'] = df_est.apply(lambda x: "🚨 COMPRAR" if x['saldo'] <= x['min_estoque'] else "✅ OK", axis=1)
            st.dataframe(df_est, use_container_width=True)
        else:
            st.info("Nenhum item cadastrado.")

    # --- 3. ENTRADAS E SAÍDAS ---
    elif choice == "Entradas e Saídas":
        st.header("🔄 Movimentação de Materiais")
        if not st.session_state['p_cadastrar']:
            st.error("Você não tem permissão para registrar movimentações.")
        else:
            df_p = pd.read_sql('SELECT id, nome, preco_unit FROM produtos', engine)
            if not df_p.empty:
                with st.form("mov"):
                    p_sel = st.selectbox("Selecione o Produto", df_p['nome'].tolist())
                    tipo = st.selectbox("Tipo de Operação", ["Entrada", "Saída"])
                    qtd = st.number_input("Quantidade", min_value=0.01, format="%.2f")
                    obs = st.text_input("Observação / Motivo")
                    if st.form_submit_button("Confirmar Movimentação"):
                        p_id = int(df_p[df_p['nome'] == p_sel]['id'].values[0])
                        v_u = float(df_p[df_p['nome'] == p_sel]['preco_unit'].values[0])
                        oper = 1 if tipo == "Entrada" else -1
                        with engine.connect() as conn:
                            conn.execute(text("UPDATE produtos SET saldo = saldo + :q WHERE id = :id"), {"q": qtd*oper, "id": p_id})
                            conn.execute(text("INSERT INTO movimentacoes (data, produto_id, tipo, quantidade, preco_unit, usuario, motivo) VALUES (:d,:id,:t,:q,:v,:u,:m)"),
                                         {"d": datetime.now().strftime("%d/%m/%Y %H:%M"), "id": p_id, "t": tipo, "q": qtd, "v": v_u, "u": st.session_state['user'], "m": obs})
                            conn.commit()
                        registar_log(engine, st.session_state['user'], "MOVIMENTAÇÃO", f"{tipo} de {qtd} em {p_sel}")
                        st.success("Registrado com sucesso!")
            else: st.warning("Cadastre produtos antes de movimentar.")

    # --- 4. CADASTRAR ITENS ---
    elif choice == "Cadastrar Itens":
        st.header("📝 Gestão de Cadastros")
        
        with st.expander("Categorias e Unidades"):
            col1, col2 = st.columns(2)
            # Categorias
            nova_cat = col1.text_input("Nova Categoria")
            if col1.button("Salvar Categoria") and nova_cat:
                with engine.connect() as conn:
                    try:
                        conn.execute(text("INSERT INTO categorias (nome) VALUES (:n)"), {"n": nova_cat})
                        conn.commit()
                        st.success("Categoria salva!")
                        st.rerun()
                    except: st.error("Erro ou categoria duplicada.")
            # Unidades
            nova_un = col2.text_input("Nova Unidade (Ex: Kg, Fardo)")
            if col2.button("Salvar Unidade") and nova_un:
                with engine.connect() as conn:
                    try:
                        conn.execute(text("INSERT INTO unidades (nome) VALUES (:n)"), {"n": nova_un})
                        conn.commit()
                        st.success("Unidade salva!")
                        st.rerun()
                    except: st.error("Erro.")

        if st.session_state['p_cadastrar']:
            st.divider()
            st.subheader("📦 Novo Produto")
            with engine.connect() as conn:
                list_cat = [r[0] for r in conn.execute(text("SELECT nome FROM categorias")).fetchall()]
                list_uni = [r[0] for r in conn.execute(text("SELECT nome FROM unidades")).fetchall()]
            
            with st.form("new_prod"):
                n = st.text_input("Nome do Produto")
                ca = st.selectbox("Categoria", list_cat)
                un = st.selectbox("Unidade", list_uni)
                mi = st.number_input("Estoque Mínimo", 0.0)
                pr = st.number_input("Preço Unitário", 0.0)
                if st.form_submit_button("Cadastrar Produto"):
                    with engine.connect() as conn:
                        conn.execute(text("INSERT INTO produtos (nome, categoria, min_estoque, unidade, preco_unit) VALUES (:n,:c,:m,:u,:p)"),
                                     {"n": n, "c": ca, "m": mi, "u": un, "p": pr})
                        conn.commit()
                    registar_log(engine, st.session_state['user'], "CADASTRO PRODUTO", n)
                    st.success("Produto cadastrado!")

    # --- 5. RELATÓRIOS ---
    elif choice == "Relatórios":
        st.header("📑 Histórico Geral")
        query = '''
            SELECT m.data, p.nome as item, m.tipo, m.quantidade, p.unidade, m.usuario, m.motivo 
            FROM movimentacoes m JOIN produtos p ON m.produto_id = p.id ORDER BY m.id DESC
        '''
        df_rel = pd.read_sql(query, engine)
        st.dataframe(df_rel, use_container_width=True)
        st.download_button("📥 Baixar Relatório", df_rel.to_csv(index=False).encode('utf-8'), "relatorio_gacc.csv")

    # --- 6. GESTÃO DE USUÁRIOS ---
    elif choice == "Gestão de Usuários":
        st.header("👥 Gestão de Acessos")
        with st.form("new_user"):
            nu = st.text_input("Nome de Usuário")
            np = st.text_input("Senha")
            nr = st.selectbox("Perfil", ["USER", "ADMINISTRADOR"])
            c1, c2, c3 = st.columns(3)
            p_lei = c1.checkbox("Leitura", value=True)
            p_cad = c2.checkbox("Cadastrar")
            p_exc = c3.checkbox("Excluir")
            if st.form_submit_button("Criar Usuário"):
                with engine.connect() as conn:
                    senha_h = hash_pass(np)
                    conn.execute(text("INSERT INTO usuarios VALUES (:u,:p,:r,1,:l,:e,:c)"),
                                 {"u": nu, "p": senha_h, "r": nr, "l": int(p_lei), "e": int(p_exc), "c": int(p_cad)})
                    conn.commit()
                st.success(f"Usuário {nu} criado!")

    # --- 7. PAINEL DE LOGS ---
    elif choice == "Painel de Logs":
        st.header("🕵️ Auditoria do Sistema")
        df_logs = pd.read_sql('SELECT * FROM logs ORDER BY id DESC', engine)
        st.dataframe(df_logs, use_container_width=True)

if __name__ == '__main__':
    main()