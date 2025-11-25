"""
Protótipo de Assistente Jurídico Inteligente (APAC/PE) com backend minimalista.

Este aplicativo Streamlit demonstra funcionalidades básicas de edição de peças,
exportação de documentos e, agora, uma consulta jurídica com RAG (Retrieval
Augmented Generation) simplificado usando bibliotecas open‑source. A lógica de
RAG indexa referências normativas fornecidas e seleciona os tópicos mais
relevantes para responder a perguntas do usuário.  Para manter o protótipo
simples, a resposta é gerada por uma abordagem extrativa (resumo) e não por
um modelo generativo pesado.  Todos os dados permanecem locais e nenhuma
chamada externa a APIs é feita.

Requisitos:
  - Python 3.10+
  - streamlit
  - scikit‑learn

Execute com:

    streamlit run main.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from io import BytesIO
from textwrap import dedent
from typing import Any, List, Optional, Tuple

import streamlit as st

# -----------------------------------------------------------------------------
# Pacotes para RAG
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# -----------------------------------------------------------------------------
# Helpers básicos


def summarize_text(text: str, max_sentences: int = 3) -> str:
    """Resumo extrativo simples baseado em sentenças.

    Recebe uma string e retorna as primeiras ``max_sentences`` sentenças.
    Essa função é utilizada tanto para resumir documentos quanto para
    condensar textos recuperados pelo mecanismo de RAG.
    """
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    return ". ".join(sentences[:max_sentences]) + ("." if sentences else "")


def generate_docx(content: str) -> BytesIO:
    """Gera um arquivo DOCX em memória a partir de texto simples.

    Se o pacote ``python‑docx`` não estiver instalado, retorna um buffer vazio.
    """
    try:
        from docx import Document  # type: ignore
    except ImportError:
        return BytesIO()
    buffer = BytesIO()
    doc = Document()
    for paragraph in content.split("\n"):
        doc.add_paragraph(paragraph)
    doc.save(buffer)
    buffer.seek(0)
    return buffer


def load_docx(file) -> str:
    """Extrai texto de um arquivo DOCX carregado. Retorna string vazia se
    ocorrer erro ou se o ``python‑docx`` não estiver instalado."""
    try:
        from docx import Document  # type: ignore
        from docx.opc.exceptions import PackageNotFoundError  # type: ignore
    except ImportError:
        return ""
    try:
        doc = Document(file)
        return "\n".join(p.text for p in doc.paragraphs)
    except (PackageNotFoundError, AttributeError, ValueError, TypeError, IOError):
        # retorne string vazia conforme contrato.
        return ""


# -----------------------------------------------------------------------------
# Dados do desafio (tipos de peça e referências normativas)

DOCUMENT_TYPES: List[str] = [
    "Nota técnica",
    "Ofício",
    "Contratos, distratos e rescisões",
    "Aditivos contratuais (prorrogação e reajustes)",
    "Termos de cessão",
    "Convênios",
    "Termo Referencial",
    "Editais",
    "Portarias",
    "Resoluções",
    "Decretos",
    "Leis estaduais",
    "Despachos",
    "Relatórios",
    "Processos administrativos (penalidade e disciplinar)",
    "Notificações",
    "Acordos de cooperação",
    "Termos de compromisso",
]

NORMATIVE_REFERENCES: List[str] = [
    "Lei nº 14.133/2021 (Nova Lei de Licitações)",
    "Lei nº 8.666/1993 (vigente em transição)",
    "Lei nº 6.123/1968 (Estatuto dos Servidores do Estado de Pernambuco)",
    "Decreto estadual nº 52.359/2022",
    "Decreto nº 42.191/2015",
    "Decreto nº 57.002/2024",
    "Lei nº 10.406, de 10 de janeiro de 2002",
    "Lei nº 13.105, de 16 de março de 2015",
    "Constituição da República Federativa do Brasil de 1988",
    "Lei nº 14.028, de 26 de março de 2010",
    "Resoluções da ANA",
    "Boletins da Procuradoria Geral do Estado – PGE",
    "Lei nº 12.984, de 30 de dezembro de 2005",
    "Lei nº 12.334, de 20 de setembro de 2010",
]


def build_document_from_metadata(
    doc_type: str,
    parte_autora: Optional[str],
    parte_re: Optional[str],
    objeto: Optional[str],
    prazo: Optional[str],
) -> str:
    """Gera um corpo de documento simples com base no tipo e nos dados essenciais.

    Serve como 'template dinâmico' para o protótipo. Em produção, isso seria
    substituído por modelos mais ricos ou por um backend LaTeX/LLM.
    """
    # Normalize None -> empty string to satisfy typing and avoid "None" in output
    parte_autora = parte_autora or ""
    parte_re = parte_re or ""
    objeto = objeto or ""
    prazo = prazo or ""

    doc_type_upper = doc_type.upper()

    if doc_type == "Ofício":
        template = f"""
        {doc_type_upper}

        À(ao) {parte_re}

        Assunto: {objeto}

        Prezado(a),

        [Descreva aqui o contexto e o pedido principal.]

        {parte_autora}
        Prazo: {prazo}
        """
    elif doc_type == "Nota técnica":
        template = f"""
        {doc_type_upper}

        Interessado(a): {parte_autora}
        Assunto: {objeto}
        Prazo: {prazo}

        [Insira aqui a análise técnica, fundamentação jurídica e conclusão.]

        {parte_autora}
        """
    else:
        template = f"""
        {doc_type_upper}

        Parte autora: {parte_autora}
        Parte ré/interessada: {parte_re}
        Objeto: {objeto}
        Prazo: {prazo}

        [Descreva aqui os fatos, fundamentos jurídicos e pedidos.]
        """

    return dedent(template).strip()


# -----------------------------------------------------------------------------
# RAG backend minimalista


@dataclass
class SimpleRAG:
    """Classe que encapsula um índice TF‑IDF e permite consultas básicas.

    Esta implementação usa TfidfVectorizer para indexar uma pequena coleção
    de documentos (nesse caso, as referências normativas). A similaridade
    coseno é utilizada para selecionar as entradas mais relevantes para uma
    consulta textual.
    """

    documents: List[str]
    vectorizer: TfidfVectorizer = TfidfVectorizer()
    tfidf_matrix: Any = None

    def __post_init__(self) -> None:
        # Ajuste o vetor de documentos ao iniciar.
        self.tfidf_matrix = self.vectorizer.fit_transform(self.documents)

    def query(self, question: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Retorna as ``top_k`` referências mais relevantes para a questão.

        Parameters
        ----------
        question : str
            Consulta escrita pelo usuário.
        top_k : int
            Número de documentos a retornar.

        Returns
        -------
        List[Tuple[str, float]]
            Lista de tuplas contendo o texto da referência e sua similaridade.
        """
        if not question.strip():
            return []
        query_vector = self.vectorizer.transform([question])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()
        # obtenha índices dos top_k maiores valores
        top_indices = similarities.argsort()[::-1][:top_k]
        return [(self.documents[i], float(similarities[i])) for i in top_indices]

    def answer(self, question: str, max_sentences: int = 3) -> str:
        """Gera uma resposta simplificada concatenando as melhores referências.

        Esta função concatena os títulos das referências normativas mais relevantes
        e utiliza ``summarize_text`` para criar um resumo breve.  Em um
        ambiente real, a concatenação seria substituída por um modelo de
        linguagem generativo (LLM) que produziria uma resposta estruturada com
        base no contexto recuperado.
        """
        retrieved = self.query(question, top_k=max_sentences)
        if not retrieved:
            return "Não foram encontradas referências normativas para esta questão."
        context = "\n".join([ref for ref, score in retrieved])
        # Use o resumo simples como resposta
        return summarize_text(context, max_sentences=max_sentences)


# Inicialize o índice RAG com as referências normativas
RAG_ENGINE = SimpleRAG(documents=NORMATIVE_REFERENCES)


# -----------------------------------------------------------------------------
# UI helpers (landing/feature cards/sidebar)

FEATURE_CARDS = [
    (
        "📝 Editor de documentos",
        "Edição direta do texto com upload de .txt/.docx e exportação para .docx.",
    ),
    (
        "⚖️ Consulta jurídica (RAG)",
        "Faça perguntas sobre legislação ou modelos e receba referências normativas relevantes.",
    ),
    (
        "📑 Templates padronizados",
        "Início rápido por tipo de peça com placeholders para partes/objeto/prazos.",
    ),
]

PROMPT_EXAMPLES = [
    (
        "Pergunta sobre licitações",
        "Quais leis tratam das licitações públicas em Pernambuco?",
    ),
    (
        "Pergunta sobre estatuto",
        "O que rege o estatuto dos servidores do estado de Pernambuco?",
    ),
]


def show_normative_references() -> None:
    """Exibe o catálogo normativo na sidebar.

    Importante: quando usamos um ``expander`` na sidebar, os widgets
    subsequentes devem ser emitidos via ``st.write`` (e não ``st.sidebar.write``)
    para garantir que o conteúdo seja renderizado dentro do expander. Caso
    contrário, os itens aparecem fora do componente, como relatado pelo usuário.
    """
    st.sidebar.markdown("**Fundamentação Jurídica**")
    # Utilize st.write dentro do contexto do expander para manter o escopo
    with st.sidebar.expander("Catálogo normativo (estático)", expanded=False):
        for ref in NORMATIVE_REFERENCES:
            st.write(f"- {ref}")


def welcome_screen() -> None:
    """Tela de boas-vindas mostrada antes do login.

    Serve como 'splash screen' que limita o acesso às funcionalidades.
    """
    st.title("Assistente Jurídico Inteligente — APAC/PE")
    st.subheader("Acesso restrito")

    st.write(
        "Para utilizar o editor de peças, a consulta jurídica (RAG) e a exportação "
        "de documentos, é necessário realizar login usando as credenciais de "
        "demonstração na barra lateral."
    )

    a, b, c = st.columns(3)
    a.metric("Tipos de peças", len(DOCUMENT_TYPES))
    b.metric("Referências normativas", len(NORMATIVE_REFERENCES))
    c.metric("Status do protótipo", "Aguardando login")

    st.info(
        "Use o menu **Autenticação** na sidebar (usuário `admin`, senha `password`). "
        "Após o login, o menu de navegação será liberado."
    )


def sidebar_layout() -> str:
    st.sidebar.markdown("### Sessão")

    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    # ---------- BLOCO DE AUTENTICAÇÃO ----------
    with st.sidebar.expander(
        "Autenticação", expanded=not st.session_state["logged_in"]
    ):
        st.write("Demo: usuário **admin**, senha **password**.")
        u = st.text_input(
            "Usuário",
            key="login_user",
            disabled=st.session_state["logged_in"],
        )
        p = st.text_input(
            "Senha",
            type="password",
            key="login_pass",
            disabled=st.session_state["logged_in"],
        )

        if not st.session_state["logged_in"]:
            if st.button("Entrar"):
                if u == "admin" and p == "password":
                    st.session_state["logged_in"] = True
                    st.success("Login realizado com sucesso.")
                    # força um novo rerun já com logged_in=True (compatível com versões antigas e novas)
                    rerun_fn = getattr(st, "rerun", None) or getattr(
                        st, "experimental_rerun", None
                    )
                    if callable(rerun_fn):
                        try:
                            rerun_fn()
                        except (
                            RuntimeError,
                            OSError,
                            AttributeError,
                            TypeError,
                            KeyboardInterrupt,
                        ):
                            # Se ocorrer qualquer erro ao tentar forçar o rerun, ignoramos;
                            pass
                else:
                    st.error("Credenciais inválidas.")

    # Se ainda não logou, NÃO mostra menu nem navegação
    if not st.session_state["logged_in"]:
        st.sidebar.info(
            "Faça login para liberar o menu de navegação e as funcionalidades."
        )
        return "Início"

    # ---------- A PARTIR DAQUI, SÓ QUEM ESTÁ LOGADO ----------
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Atalhos")

    nav_options = ["Início", "Gerar/Editar", "Consulta RAG", "Exportar"]

    # valor padrão da navegação
    current_nav = st.session_state.get("nav", "Início")
    if current_nav not in nav_options:
        current_nav = "Início"

    nav_choice = st.sidebar.radio(
        "Navegação",
        nav_options,
        index=nav_options.index(current_nav),
    )

    # Mantém 'nav' sempre sincronizado com o rádio
    st.session_state["nav"] = nav_choice

    st.sidebar.caption("Protótipo simplificado: RAG ativo, LLM isolada/LaTeX ausentes")
    show_normative_references()
    st.sidebar.markdown("---")
    with st.sidebar.expander("Ajuda & LGPD", expanded=False):
        st.write(
            "Este é um protótipo local. Em produção, será obrigatório cumprir a LGPD, "
            "com anonimização e isolamento de dados/processos."
        )

    return nav_choice


def feature_cards() -> None:
    left, right = st.columns(2)
    cards = [left, right]
    for i, (title, desc) in enumerate(FEATURE_CARDS):
        with cards[i % 2].container():
            st.markdown(f"#### {title}")
            st.write(desc)
            st.divider()


def landing_home() -> None:
    st.title("Assistente Jurídico Inteligente — APAC/PE (Protótipo)")
    st.markdown(
        "Plataforma web **SaaS‑like** com editor, consulta jurídica e exportação. "
        "Esta **página inicial** demonstra as capacidades previstas nesta versão simplificada."
    )
    a, b, c = st.columns(3)
    a.metric("Tipos de peças", len(DOCUMENT_TYPES))
    b.metric("Referências normativas", len(NORMATIVE_REFERENCES))
    c.metric("Status", "RAG ativo", "protótipo")
    tabs = st.tabs(
        ["Visão geral", "Como funciona", "Exemplos de consultas", "Templates"]
    )
    with tabs[0]:
        feature_cards()
        st.info(
            "Protótipo: o motor LaTeX e a LLM isolada não estão habilitados nesta versão."
        )
    with tabs[1]:
        st.markdown("#### Fluxo recomendado")
        st.markdown(
            "- **1) Selecionar tipo de peça** e preencher dados essenciais (partes, objeto, prazos)\n"
            "- **2) Importar documento** (opcional) e **editar** no editor\n"
            "- **3) Consultar RAG** para obter referências normativas relevantes\n"
            "- **4) Exportar para DOCX**\n"
        )
        st.button(
            "Ir para Gerar/Editar",
            key="start_generate",
            on_click=lambda: st.session_state.update(nav="Gerar/Editar"),
        )
    with tabs[2]:
        for label, example in PROMPT_EXAMPLES:
            with st.expander(f"{label}"):
                st.code(example)
    with tabs[3]:
        st.caption("Modelos baseados nos tipos de peça do desafio.")
        cols = st.columns(3)
        for i, doc in enumerate(DOCUMENT_TYPES[:9]):
            with cols[i % 3]:
                st.write(f"**{doc}**")
                st.button(
                    "Usar template",
                    key=f"tpl_{i}",
                    on_click=lambda d=doc: st.session_state.update(
                        selected_template=d, nav="Gerar/Editar"
                    ),
                )
        st.caption(
            "Use a sidebar para navegar e o formulário para preencher os campos da peça."
        )


# -----------------------------------------------------------------------------
# Telas principais


def screen_generate_edit() -> None:
    """Tela para gerar e editar documentos: formulário de metadados, upload e editor.

    Esta função exibe o formulário de dados essenciais (partes, objeto, prazos),
    aplica templates, permite upload de .txt/.docx e mantém o conteúdo do editor
    no st.session_state de forma a preservar edições do usuário entre reruns.
    """
    st.header("Gerar / Editar documento")

    # Seleção do tipo de peça (respeita template vindo da landing)
    default_idx = 0
    if (
        "selected_template" in st.session_state
        and st.session_state["selected_template"] in DOCUMENT_TYPES
    ):
        default_idx = DOCUMENT_TYPES.index(st.session_state["selected_template"])

    doc_type = st.selectbox("Tipo de peça", DOCUMENT_TYPES, index=default_idx)
    # mantém o template selecionado no estado
    st.session_state["selected_template"] = doc_type

    # Garante que o editor tenha uma chave no estado
    if "doc_content" not in st.session_state:
        st.session_state["doc_content"] = ""

    # ------------------- Form de metadados -------------------
    with st.form("form_dados"):
        st.write("**Dados essenciais**")
        parte_autora = st.text_input(
            "Parte Autora",
            placeholder="Nome da parte autora",
            value=st.session_state.get("doc_meta", {}).get("parte_autora", ""),
        )
        parte_re = st.text_input(
            "Parte Ré/Interessada",
            placeholder="Nome da parte ré/interessada",
            value=st.session_state.get("doc_meta", {}).get("parte_re", ""),
        )
        objeto = st.text_input(
            "Objeto",
            placeholder="Descrição resumida do objeto",
            value=st.session_state.get("doc_meta", {}).get("objeto", ""),
        )
        prazo = st.text_input(
            "Prazos",
            placeholder="Data/prazo relevante",
            value=st.session_state.get("doc_meta", {}).get("prazo", ""),
        )

        submitted = st.form_submit_button("Aplicar dados ao template")

    # Quando o usuário clica em "Aplicar", gera/atualiza o corpo do documento
    if submitted:
        st.session_state["doc_meta"] = {
            "doc_type": doc_type,
            "parte_autora": parte_autora,
            "parte_re": parte_re,
            "objeto": objeto,
            "prazo": prazo,
        }
        st.session_state["doc_content"] = build_document_from_metadata(
            doc_type=doc_type,
            parte_autora=parte_autora,
            parte_re=parte_re,
            objeto=objeto,
            prazo=prazo,
        )
        # Reset uploaded file tracking because user intentionally replaced content via template
        if "uploaded_file_name" in st.session_state:
            st.session_state.pop("uploaded_file_name", None)
        st.success("Template aplicado ao editor com os dados informados.")

    # ------------------- Upload + Editor -------------------
    st.subheader("Documento")
    uploaded_file = st.file_uploader("Upload (.txt ou .docx)", type=["txt", "docx"])
    if uploaded_file is not None:
        # Use the uploaded file name to detect changes across reruns;
        # only overwrite doc_content when a new file is actually uploaded.
        uploaded_name = getattr(uploaded_file, "name", None)
        prev_name = st.session_state.get("uploaded_file_name")
        if uploaded_name != prev_name:
            # Determine file type primarily by filename extension (more reliable across sources).
            uploaded_ext = os.path.splitext(uploaded_name or "")[1].lower()
            is_txt = uploaded_ext == ".txt"
            is_docx = uploaded_ext == ".docx"
            # Fallback: if extension missing or unrecognized, try MIME type
            if not (is_txt or is_docx):
                mime = getattr(uploaded_file, "type", "") or ""
                is_txt = mime == "text/plain" or mime.startswith("text/")
                is_docx = (
                    mime
                    == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    or "officedocument.wordprocessingml.document" in mime
                )

            if is_txt:
                try:
                    # Streamlit UploadedFile supports .read()
                    text_content = uploaded_file.read().decode("utf-8", errors="ignore")
                except (UnicodeDecodeError, AttributeError, TypeError):
                    # If decoding fails or read()/decode() aren't available,
                    # try to reset stream and read via getvalue()
                    try:
                        uploaded_file.seek(0)
                    except (OSError, ValueError):
                        pass
                    try:
                        text_content = uploaded_file.getvalue().decode(
                            "utf-8", errors="ignore"
                        )
                    except (AttributeError, UnicodeDecodeError, TypeError):
                        text_content = ""
            elif is_docx:
                text_content = (
                    load_docx(uploaded_file) or "Não foi possível ler o DOCX."
                )
            else:
                # Unknown type: attempt to read as text first then as docx
                try:
                    text_candidate = uploaded_file.read().decode(
                        "utf-8", errors="ignore"
                    )
                    if text_candidate.strip():
                        text_content = text_candidate
                    else:
                        text_content = (
                            load_docx(uploaded_file)
                            or "Não foi possível ler o arquivo."
                        )
                except (AttributeError, UnicodeDecodeError, TypeError):
                    text_content = (
                        load_docx(uploaded_file) or "Não foi possível ler o arquivo."
                    )

            # Se um novo arquivo for enviado, ele passa a ser o conteúdo base do editor
            st.session_state["doc_content"] = text_content
            st.session_state["uploaded_file_name"] = uploaded_name
        else:
            # Arquivo igual ao já carregado anteriormente: não sobrescrever para preservar edições do usuário.
            st.info(
                "Arquivo já carregado anteriormente — mantendo conteúdo atual (edições preservadas)."
            )

    st.text_area(
        "Editor (conteúdo do documento)",
        height=350,
        key="doc_content",
        help="Edição local no navegador (nenhum dado é enviado a serviços externos).",
    )

    cols = st.columns(2)
    with cols[0]:
        if st.button("Gerar resumo", key="resumo_btn"):
            resumo = summarize_text(st.session_state.get("doc_content", ""))
            st.info(resumo or "Nenhum conteúdo para resumir.")
    with cols[1]:
        st.caption(
            "Futuro: comandos de alto nível (ex.: 'inserir cláusula X', 'padronizar linguagem Y')."
        )


def screen_consult_rag() -> None:
    """Interface para consultas jurídicas usando o mecanismo de RAG."""
    st.header("Consulta Jurídica (RAG)")
    st.write(
        "Faça uma pergunta sobre legislação, decretos ou modelos de documentos. "
        "O sistema retornará as referências normativas mais relevantes."
    )
    query = st.text_input(
        "Digite sua pergunta", placeholder="Ex.: Quais leis tratam das licitações?"
    )
    if st.button("Consultar", key="consultar_btn"):
        if not query.strip():
            st.warning("Digite uma pergunta para consultar.")
        else:
            with st.spinner("Consultando base normativa..."):
                results = RAG_ENGINE.query(query, top_k=3)
                answer = RAG_ENGINE.answer(query)
            st.markdown("#### Referências Relevantes")
            for ref, score in results:
                st.write(f"- {ref} (score: {score:.2f})")
            st.markdown("#### Resumo da Resposta")
            st.success(answer)


def screen_export() -> None:
    st.header("Exportar")
    content = st.session_state.get("doc_content", "")
    if not content:
        st.warning("Nada para exportar. Crie ou edite um documento em 'Gerar/Editar'.")
        return
    if st.button("Exportar para DOCX"):
        buf = generate_docx(content)
        if buf.getbuffer().nbytes == 0:
            st.error("Instale 'python-docx' para habilitar a exportação.")
        else:
            st.download_button(
                "Baixar DOCX",
                data=buf,
                file_name="documento_juridico.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
    st.caption("Futuro: exportação para PDF com backend LaTeX.")


# -----------------------------------------------------------------------------
# App


def main() -> None:
    st.set_page_config(page_title="Assistente Jurídico Inteligente", layout="wide")

    # Atalho de navegação a partir de botões na landing/templates
    # Sincroniza a escolha com o estado da sessão
    nav_choice = sidebar_layout()

    # Se não estiver logado, mostra apenas a tela de boas-vindas e encerra
    if not st.session_state.get("logged_in", False):
        welcome_screen()
        return

    # Roteamento entre telas (somente após login)
    if nav_choice == "Início":
        landing_home()
    elif nav_choice == "Gerar/Editar":
        screen_generate_edit()
    elif nav_choice == "Consulta RAG":
        screen_consult_rag()
    else:
        screen_export()


if __name__ == "__main__":
    main()
