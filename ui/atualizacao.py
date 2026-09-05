"""atualizacao.py — o bloco "buscar dados de fora", na barra lateral.

==============================================================================

POR QUE ISTO SAIU DE DENTRO DA TELA DE INVESTIMENTOS
-----------------------------------------------------
Os botoes de buscar cotacao e indice moravam em
*Investimentos -> Manutencao -> Atualizar saldos*. Tres cliques de profundidade
para uma acao que se faz toda semana, e escondida dentro da tela mais
especifica do app — quando o que eles atualizam serve o painel inteiro: o
indice alimenta a comparacao da carteira, e o dolar alimenta o patrimonio.

A SEPARACAO QUE O DESENHO FAZ, E QUE VALE ENTENDER
--------------------------------------------------
    BUSCAR o dado de fora   e global e sem mes -> barra lateral (aqui)
    APLICAR a um mes        muda uma foto      -> fica na tela de Investimentos

`atualizar_saldos_por_cotacao(mes)` reescreve o saldo daquele mes, entao ela
continua ao lado do seletor de mes, onde voce ve em que foto esta mexendo. O
que subiu para a lateral foi so a busca, que nao decide mes nenhum.

O BLOCO NASCE FECHADO
---------------------
Um `expander` recolhido. A barra lateral ja tem o menu, a marca, o olhinho, o
periodo e o rodape; mais dois botoes soltos ali seriam a mesma uniformidade
que `docs/06` chama de anti-padrao. Fechado, ele custa uma linha e continua a
um clique.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from financas import cambio, cotacoes, indices


def _linha_de_estado() -> str:
    """Uma frase dizendo de quando e o dado guardado. Nunca finge estar novo."""
    resumo_cotacoes = cotacoes.resumo()
    resumo_indices = indices.resumo()
    resumo_cambio = cambio.resumo()

    partes = []
    if resumo_cotacoes.get("papeis"):
        partes.append(f"cotações de {resumo_cotacoes.get('ultima') or '—'}")
    if resumo_cambio.get("ultima"):
        partes.append(f"dólar de {resumo_cambio['ultima']}")
    do_cdi = resumo_indices.get("CDI") or {}
    if do_cdi.get("ultimo_mes"):
        partes.append(f"CDI até {do_cdi['ultimo_mes']}")
    return " · ".join(partes) if partes else "nada guardado ainda"


def bloco() -> None:
    """Desenha, na barra lateral, o bloco de buscar dados de fora.

    Dois botoes, um para cada fonte, porque elas falham de formas diferentes:
    o Banco Central pode estar de pe com o Yahoo fora, e ai atualizar indice
    funciona e atualizar cotacao nao. Um botao so esconderia qual das duas
    quebrou.
    """
    from ui import estado

    with st.sidebar:
        with st.expander("Atualizar dados de fora", expanded=False):
            st.caption(_linha_de_estado())

            tem_ticker = bool(cotacoes.tickers_cadastrados())
            pode_buscar = cotacoes.resumo()["biblioteca_ok"]

            if st.button(
                    "Cotações e dólar", key="lateral_cotacoes",
                    width="stretch", disabled=not (tem_ticker and pode_buscar),
                    help="Busca o fechamento dos papéis com ticker e o PTAX "
                         "dos últimos 15 dias. Não mexe em saldo nenhum — "
                         "para recalcular um mês, use Investimentos → "
                         "Manutenção → Atualizar saldos."):
                with st.spinner("Buscando cotações…"):
                    baixadas = cotacoes.atualizar_carteira()
                    cambio.buscar_ptax(date.today() - timedelta(days=15),
                                       date.today())
                estado.limpar_cache()
                total = sum(baixadas.values())
                if total:
                    st.success(f"{total} cotação(ões) atualizada(s).")
                else:
                    st.warning(
                        "Não consegui buscar agora — sem internet ou provedor "
                        "fora. O app segue com o que já está guardado.")

            if st.button(
                    "Índices", key="lateral_indices", width="stretch",
                    help="CDI e IPCA do Banco Central; IBOV, S&P 500, SMLL e "
                         "IFIX derivados do fechamento diário."):
                with st.spinner("Buscando índices…"):
                    gravados = indices.atualizar(desde="2024-01")
                estado.limpar_cache()
                vieram = [f"{nome} ({n})" for nome, n in gravados.items() if n]
                if vieram:
                    st.success("Atualizados: " + ", ".join(vieram))
                else:
                    st.warning(
                        "Nenhum índice veio agora. O app segue com o que já "
                        "está guardado.")

            if not tem_ticker:
                st.caption(
                    "Nenhum papel com ticker cadastrado — não há cotação a "
                    "buscar. Tesouro e fundo não têm ticker público.")
            elif not pode_buscar:
                st.caption(
                    "A biblioteca `yfinance` não está instalada. Índices do "
                    "Banco Central continuam funcionando.")
