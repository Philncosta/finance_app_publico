"""
cartao_parcelas.py — O cartao e tudo que ja esta contratado para o futuro.
==============================================================================

A PERGUNTA DESTA TELA
---------------------
"Quanto do meu dinheiro futuro eu ja gastei?"

Uma compra em 10x nao e um gasto de hoje: e um compromisso que ocupa os
proximos 10 meses. O extrato nao mostra isso — ele so mostra a parcela do mes.
Esta tela junta as pontas e mostra o compromisso inteiro.

DE ONDE VEM O CALCULO
---------------------
Tudo de `financas/calculos/parcelas.py`, que foi conferido contra a aba
"Parcelas Futuras" da planilha: a linha TOTAL PREVISTO bateu mes a mes
(R$ ···· / R$ ···· / 117 x 5 / 0).
"""

from __future__ import annotations

import streamlit as st

from financas import dados
from financas.calculos import kpis, parcelas
from financas.formato import fmt_num, fmt_pct, rotulo_mes, somar_meses
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado, graficos

df = estado.lancamentos()

c.cabecalho("Cartão e parcelas", "O que já está contratado para os próximos meses")

if df.empty:
    c.aviso_vazio("Sem lançamentos ainda.", "Importe uma fatura para começar.")
    st.stop()

mes = estado.seletor_de_mes_topo()

indicadores_cartao = kpis.cartao(df, mes)
ativos = parcelas.ativos(df)
grade = parcelas.grade_futura(df, mes, 18)
total_vencer = parcelas.total_a_vencer(df)


mes_do_pagamento = somar_meses(mes, 1)

c.linha_kpis([
    {
        "rotulo": "Gasto de " + rotulo_mes(mes),
        "valor": fmt_brl(indicadores_cartao["total_mes"]),
        "ajuda": (f"{indicadores_cartao['quantidade']} lançamentos · "
                  f"sai da conta em 05/{(mes_do_pagamento or '')[5:7]}"),
        "cor": "azul",
    },
    {
        "rotulo": "Total ainda a vencer",
        "valor": fmt_brl(total_vencer),
        "ajuda": "se você parasse de gastar hoje, isto ainda chegaria",
        "cor": "amarela",
    },
    {
        "rotulo": "Parcelamentos ativos",
        "valor": fmt_num(len(ativos)),
        "ajuda": f"maior: {fmt_brl(indicadores_cartao['maior_parcelamento'])}",
    },
    {
        "rotulo": "Novo comprometimento",
        "valor": fmt_brl(parcelas.novo_comprometimento(df, mes)),
        "ajuda": "dívida futura criada neste mês",
        "cor": "vermelha" if parcelas.novo_comprometimento(df, mes) > 0 else None,
    },
])

if not ativos.empty:
    mes_ultimo = ativos["mes_termino"].max()
    proximo = grade.iloc[0] if not grade.empty else None
    c.nota(
        f"Você tem <strong>{len(ativos)} parcelamentos</strong> em aberto, "
        f"somando <strong>{fmt_brl(total_vencer)}</strong>. "
        + (f"No mês que vem caem <strong>{fmt_brl(proximo['total'])}</strong> "
           f"em {int(proximo['quantidade'])} parcelas. " if proximo is not None else "")
        + f"O último termina em <strong>{rotulo_mes(mes_ultimo)}</strong>."
    )
else:
    c.nota("Nenhum parcelamento em aberto. O cartão está limpo daqui pra frente.")


c.nota(
    f"<b>O mês aqui é o mês do gasto, não o do vencimento.</b> A fatura de "
    f"<b>{rotulo_mes(mes)}</b> reúne o que você passou no cartão de cerca de "
    f"26/{(somar_meses(mes, -1) or '')[5:7]} a 25/{mes[5:7]} — o cartão fecha "
    f"por volta do dia 25 — e ela é <b>paga em 05/"
    f"{(mes_do_pagamento or '')[5:7]}</b>.<br><br>"
    f"Contar no mês do gasto é o que mantém a fatura junto do salário que a "
    f"paga: os dois caem na mesma virada do dia 25. Antes disso, a fatura "
    f"contava no mês do vencimento e setembro/2026 aparecia com "
    f"{priv.fmt_brl(-11001.23)} de saldo sem ter nenhuma receita."
)

st.markdown("### Quanto cai em cada mês à frente")
st.caption(
    "Só parcelas JÁ CONTRATADAS. Não inclui gasto novo nem conta fixa — é o "
    "piso da sua fatura, o valor que chega mesmo se você não usar o cartão."
)
with c.painel(chave="parcelas_futuras"):
    priv.grafico(graficos.barras_parcelas_futuras(grade), width="stretch",
                 key="cartao_parcelas_barras_parcelas_futuras")


st.markdown("### Parcelamentos em aberto")

if ativos.empty:
    c.aviso_vazio("Nenhuma compra parcelada com parcelas a vencer.")
else:
    col1, col2 = st.columns([3, 2], gap="medium")

    with col1:
        with c.painel(chave="parcelamentos_ativos"):
            priv.grafico(
                graficos.barras_parcelamentos_ativos(ativos),
                width="stretch", key="cartao_parcelas_barras_parcelamentos_ativos")

    with col2:
        with c.painel("Quando cada um termina"):
            por_termino = (
                ativos.groupby("mes_termino")
                .agg(quantidade=("chave", "size"), valor=("total_a_vencer", "sum"))
                .reset_index().sort_values("mes_termino")
            )
            for _, linha in por_termino.iterrows():
                st.markdown(
                    f"**{rotulo_mes(linha['mes_termino'])}** — "
                    f"{int(linha['quantidade'])} parcelamento(s) encerram, "
                    f"liberando {fmt_brl_md(linha['valor'])} no total"
                )
            st.caption(
                "Cada data dessas é um alívio no orçamento. Anotar quando elas "
                "chegam ajuda a não recomprometer o dinheiro assim que ele sobra."
            )

    st.markdown("**Detalhe de cada parcelamento**")
    tabela = ativos[[
        "descricao", "categoria", "ultima_faturada", "parcela_total",
        "valor_parcela", "parcelas_restantes", "total_a_vencer",
        "mes_origem", "mes_termino",
    ]].copy()
    tabela["progresso"] = tabela["ultima_faturada"] / tabela["parcela_total"]

    priv.tabela(
        tabela.rename(columns={
            "descricao": "Compra", "categoria": "Categoria",
            "ultima_faturada": "Paga", "parcela_total": "Total",
            "valor_parcela": "Valor/parcela",
            "parcelas_restantes": "Restam",
            "total_a_vencer": "A vencer",
            "mes_origem": "Comprada em", "mes_termino": "Termina em",
            "progresso": "Progresso",
        }),
        hide_index=True, width="stretch", height=380,
        column_config={
            "Valor/parcela": c.config_moeda("Valor/parcela"),
            "A vencer": c.config_moeda("A vencer"),
            "Progresso": st.column_config.ProgressColumn(
                "Progresso", min_value=0, max_value=1, format="%.0f%%"),
        },
    )


with st.expander("Ver parcela por parcela, mês a mês"):
    detalhe = parcelas.detalhe_futuro(df, mes, 12)
    if detalhe.empty:
        st.caption("Nenhuma parcela futura.")
    else:
        for mes_futuro in detalhe["mes"].unique():
            do_mes_futuro = detalhe[detalhe["mes"] == mes_futuro]
            total_mes = do_mes_futuro["valor"].sum()
            st.markdown(
                f"**{rotulo_mes(mes_futuro)}** — {fmt_brl_md(total_mes)} "
                f"em {len(do_mes_futuro)} parcelas"
            )
            priv.tabela(
                do_mes_futuro[["descricao", "parcela", "categoria", "valor"]]
                .rename(columns={
                    "descricao": "Compra", "parcela": "Parcela",
                    "categoria": "Categoria", "valor": "Valor",
                }),
                hide_index=True, width="stretch",
                column_config={"Valor": c.config_moeda("Valor")},
            )


st.markdown("---")
st.markdown(f"### O que passou no cartão em {rotulo_mes(mes)}")

do_mes_cartao = dados.do_cartao(dados.do_mes(df, mes))
gastos_cartao = dados.despesas(do_mes_cartao)

if gastos_cartao.empty:
    c.aviso_vazio(f"Nenhum lançamento de cartão em {rotulo_mes(mes)}.")
else:
    col_a, col_b = st.columns([1, 1], gap="medium")
    with col_a:
        with c.painel(chave="pizza_cartao"):
            priv.grafico(
                graficos.pizza_por_grande_categoria(
                    dados.por_categoria(do_mes_cartao, "grande_categoria"),
                    estado.cores_grande_categoria()),
                width="stretch", key="cartao_parcelas_pizza_por_grande_categoria")
    with col_b:
        parcelado = float(-gastos_cartao[gastos_cartao["e_parcelado"]]["valor"].sum())
        a_vista = indicadores_cartao["total_mes"] - parcelado
        with c.painel("À vista x parcelado"):
            c.card_meta("Parcelado", parcelado, indicadores_cartao["total_mes"])
            st.markdown("")
            c.card_meta("À vista", a_vista, indicadores_cartao["total_mes"])
            st.caption(
                f"{fmt_pct(parcelado / indicadores_cartao['total_mes'] if indicadores_cartao['total_mes'] else 0)}"
                " da fatura deste mês é parcela — dinheiro que você já tinha gastado antes."
            )

    with c.painel(chave="top_estabelecimentos_cartao"):
        priv.grafico(graficos.top_estabelecimentos(do_mes_cartao),
                     width="stretch", key="cartao_parcelas_top_estabelecimentos")

c.rodape_atualizado(len(do_mes_cartao), mes)
