"""
app.py — A porta de entrada do Painel Financeiro.
==============================================================================

COMO RODAR
----------
    Duplo clique em  iniciar.bat
    ou, pelo terminal:

        .venv\\Scripts\\streamlit run app.py

O QUE ESTE ARQUIVO FAZ (e o que ele NAO faz)
---------------------------------------------
Ele e o "hall de entrada": prepara o banco, aplica o tema, monta o menu da
esquerda e entrega o controle para a pagina escolhida. Nenhum calculo e
nenhum grafico acontece aqui — cada tela cuida de si, dentro de paginas/.

Manter este arquivo curto e proposital: quando algo quebra, voce sabe que o
problema esta na PAGINA, nao na entrada.

A ORDEM DAS COISAS IMPORTA
--------------------------
    1. st.set_page_config   PRECISA ser o primeiro comando Streamlit do script.
                            Se vier depois de qualquer outro, o Streamlit
                            reclama e para.
    2. preparar_banco()     cria as tabelas se for a primeira vez.
    3. tema.aplicar()       injeta o CSS.
    4. st.navigation(...)   monta o menu e roda a pagina escolhida.

SOBRE O st.navigation
---------------------
E a forma moderna do Streamlit montar um app de varias telas. A alternativa
antiga era criar uma pasta `pages/` e deixar o Streamlit descobrir sozinho,
mas ali os titulos saem do nome do arquivo e nao da para agrupar. Com
`st.navigation` nos escolhemos o titulo, o icone e os grupos.
"""

from __future__ import annotations

import streamlit as st

from financas import config

st.set_page_config(
    page_title=config.NOME_APP,
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ui import atualizacao, estado, privacidade, tema  # noqa: E402


def barra_lateral_rodape() -> None:
    """O rodape da barra lateral: versao, banco e como abrir de outro aparelho."""
    from financas import banco

    with st.sidebar:
        st.markdown("---")

        total = banco.contar("lancamentos")
        ultimo = banco.consultar_um(
            "SELECT MAX(mes_competencia) AS m FROM lancamentos")
        mes_final = ultimo["m"] if ultimo and ultimo["m"] else "—"

        st.caption(f"**{total:,}**".replace(",", ".") + f" lançamentos · até {mes_final}")
        st.caption(f"Banco: `{config.CAMINHO_BANCO.name}`")

        with st.expander("Abrir em outro aparelho"):
            st.caption(
                "O app aceita conexões da sua rede local. No celular ou "
                "tablet, com o mesmo Wi-Fi, abra o endereço que aparece na "
                "janela preta como **Network URL**."
            )
            st.code("http://SEU-IP:8501", language=None)
            st.caption(
                "Para descobrir o IP, rode `ipconfig` no Prompt de Comando e "
                "procure por *Endereço IPv4*."
            )


def main() -> None:
    """Monta e roda o app."""
    resumo = estado.preparar_banco()

    tema.aplicar()

    privacidade.botao()

    with st.sidebar:
        # As cores saem daqui e vao para as classes `.marca-*` do tema. Com a
        # barra lateral escura, o `texto` (quase preto) escrito na mao aqui
        # dentro deixava o nome do app invisivel sobre o indigo — e cor
        # embutida em HTML e justamente a que ninguem lembra de atualizar
        # quando o fundo muda.
        st.markdown(
            f"""
            <div class="marca">
              <div class="marca-titulo">💰 {config.NOME_APP}</div>
              <div class="marca-sub">controle pessoal · dados locais</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    paginas = {
        "Visão geral": [
            st.Page("paginas/dashboard.py", title="Dashboard",
                    icon=":material/dashboard:", default=True),
            st.Page("paginas/lancamentos.py", title="Lançamentos",
                    icon=":material/receipt_long:"),
            st.Page("paginas/importar.py", title="Importar arquivos",
                    icon=":material/upload_file:"),
        ],
        "Planejar": [
            st.Page("paginas/planejamento.py", title="Planejamento",
                    icon=":material/insights:"),
            st.Page("paginas/cartao_parcelas.py", title="Cartão e parcelas",
                    icon=":material/credit_card:"),
            st.Page("paginas/gastos_fixos.py", title="Gastos fixos",
                    icon=":material/event_repeat:"),
        ],
        "Construir": [
            st.Page("paginas/patrimonio.py", title="Patrimônio",
                    icon=":material/savings:"),
            st.Page("paginas/investimentos.py", title="Investimentos",
                    icon=":material/trending_up:"),
            st.Page("paginas/metas_compras.py", title="Metas e compras",
                    icon=":material/flag:"),
            st.Page("paginas/financiamento.py", title="Financiamento",
                    icon=":material/home:"),
            st.Page("paginas/imposto.py", title="Imposto de renda",
                    icon=":material/receipt:"),
        ],
        "Ajustes": [
            st.Page("paginas/regras.py", title="Regras",
                    icon=":material/rule:"),
            st.Page("paginas/configuracoes.py", title="Configurações",
                    icon=":material/settings:"),
        ],
    }

    navegacao = st.navigation(paginas, position="sidebar")

    estado.seletor_de_periodo()
    atualizacao.bloco()

    barra_lateral_rodape()

    if resumo.get("migracoes_aplicadas"):
        st.toast("Banco de dados criado com sucesso.", icon="✅")

    navegacao.run()


if __name__ == "__main__":
    main()
