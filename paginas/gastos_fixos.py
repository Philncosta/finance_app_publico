"""
gastos_fixos.py — O que sai da conta todo mes sem voce decidir de novo.
==============================================================================

O RECURSO QUE JUSTIFICA ESTA TELA
---------------------------------
A comparacao "cadastrado x realidade". Voce anota "conta de luz: R$ ····",
mas quanto pagou DE VERDADE nos ultimos 6 meses? Se a media real for outra, o
seu planejamento inteiro esta apoiado num numero errado.

A ligacao entre o item cadastrado e os lancamentos reais e a coluna
"Chave no histórico": um pedaco de texto que aparece na descricao do
lancamento. Para o aluguel a chave e "EDUARDO MOREIRA"; para a faculdade,
"ESTACIO".

QUANDO APARECE "sem histórico"
------------------------------
Quer dizer que a chave nao casou com nenhum lancamento na janela. Duas causas
possiveis: a chave esta errada, ou o gasto realmente nao aconteceu naquele
periodo (um item que so comeca no mes que vem, por exemplo).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from financas import banco, config
from financas.calculos import fixos, kpis
from financas.formato import fmt_pct, rotulo_mes, somar_meses, vazio
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado, graficos


def _texto_ou_none(valor) -> str | None:
    """Converte para texto limpo, ou `None` quando vazio.

    Uma célula vazia do `st.data_editor` chega como `NaN` do pandas, e
    `NaN or ""` continua sendo `NaN` (porque `bool(NaN)` é `True`) — daí
    `str(x or "")` gravar a STRING "nan" no banco em vez de None. `vazio()`
    é a única forma segura de checar isso.
    """
    return None if vazio(valor) else str(valor).strip() or None


def _numero_ou(valor, padrao: float) -> float:
    """Como `_texto_ou_none`, para número: célula vazia tem `NaN` onde devia
    ter o padrão, e `NaN or 0` continua sendo `NaN` — mesma armadilha."""
    return padrao if vazio(valor) else float(valor)


df = estado.lancamentos()
cadastro = estado.cadastro_fixos()

c.cabecalho("Gastos fixos", "O piso do seu orçamento")
c.mostrar_recado()

mes = estado.seletor_de_mes_topo()

if mes is None:
    mes = "2026-01"

resultado_mes = kpis.resultado_do_mes(df, mes) if not df.empty else {"receita_total": 0}
indicadores = fixos.indicadores(cadastro, df, mes, resultado_mes["receita_total"])


c.linha_kpis([
    {
        "rotulo": "Fixo cadastrado",
        "valor": fmt_brl(indicadores["cadastrado"]),
        "ajuda": f"{indicadores['n_itens']} itens valendo em {rotulo_mes(mes)}",
        "cor": "azul",
    },
    {
        "rotulo": "Fixo realizado no mês",
        "valor": fmt_brl(indicadores["realizado"]),
        "ajuda": "lançamentos marcados como Fixo",
    },
    {
        "rotulo": "% da receita",
        "valor": fmt_pct(indicadores["pct_da_receita"]),
        "ajuda": "quanto já está comprometido antes de qualquer escolha",
        "cor": (
            "vermelha" if indicadores["pct_da_receita"] > 0.5
            else "amarela" if indicadores["pct_da_receita"] > 0.3
            else "verde"
        ),
    },
])

if indicadores["pct_da_receita"] > 0.5:
    c.nota(
        f"Mais da metade da sua receita "
        f"(<strong>{fmt_pct(indicadores['pct_da_receita'])}</strong>) vai para "
        f"gastos fixos. Isso deixa pouca margem para imprevisto — vale olhar "
        f"a lista abaixo procurando contrato para renegociar ou cancelar."
    )


st.markdown("### Cadastrado x realidade")

col_janela, col_texto = st.columns([1, 3])
with col_janela:
    janela = st.selectbox("Janela de comparação", [3, 6, 12], index=1,
                          format_func=lambda n: f"{n} meses", key="fixos_janela")
with col_texto:
    inicio_janela = somar_meses(mes, -janela)
    st.caption(
        f"Compara o valor cadastrado com a média mensal realmente paga entre "
        f"{rotulo_mes(inicio_janela)} e {rotulo_mes(somar_meses(mes, -1))}. "
        f"A média divide pela janela inteira, então um gasto que só apareceu "
        f"em 3 dos {janela} meses pesa proporcionalmente menos."
    )

comparacao = fixos.comparar_com_real(cadastro, df, mes, janela)

if comparacao.empty:
    c.aviso_vazio("Nenhum gasto fixo cadastrado ainda.",
                  "Use a tabela mais abaixo para cadastrar o primeiro.")
else:
    acima = comparacao[comparacao["situacao"] == "acima"]
    sem_historico = comparacao[comparacao["situacao"] == "sem histórico"]

    if not acima.empty:
        total_subestimado = float(acima["diferenca"].sum())
        st.warning(
            f"**{len(acima)} item(ns) custam mais do que o cadastrado**, "
            f"somando {fmt_brl_md(total_subestimado)} a mais por mês "
            f"({fmt_brl_md(total_subestimado * 12)} por ano) do que o seu "
            f"planejamento supõe."
        )

    tabela = comparacao.copy()
    tabela["diferenca_pct"] = tabela["diferenca_pct"] * 100
    priv.tabela(
        tabela[["item", "categoria", "cadastrado", "media_real", "diferenca",
                "diferenca_pct", "meses_com_gasto", "situacao"]].rename(columns={
            "item": "Item", "categoria": "Categoria",
            "cadastrado": "Cadastrado", "media_real": "Média real",
            "diferenca": "Diferença", "diferenca_pct": "Dif. %",
            "meses_com_gasto": "Meses c/ gasto", "situacao": "Situação",
        }),
        hide_index=True, width="stretch", height=420,
        column_config={
            "Cadastrado": c.config_moeda("Cadastrado"),
            "Média real": c.config_moeda("Média real"),
            "Diferença": c.config_moeda("Diferença", "positivo = paga mais do que cadastrou"),
            "Dif. %": c.config_percentual("Dif. %"),
        },
    )

    if not sem_historico.empty:
        st.caption(
            f"**{len(sem_historico)} item(ns) sem histórico**: a chave não "
            f"encontrou nenhum lançamento na janela. Confira se a "
            f"«Chave no histórico» bate com o texto que aparece no extrato ou "
            f"na fatura — ou se o gasto ainda não começou."
        )

    com_buraco = comparacao[
        (comparacao["meses_com_gasto"] > 0)
        & (comparacao["meses_sem_gasto"].map(len) > 0)
    ]
    if not com_buraco.empty:
        st.caption(
            "**Meses sem cobrança na janela** — pode ser que você tenha pago "
            "de outro jeito, ou que falte importar aquele extrato: "
            + " · ".join(
                f"_{linha['item']}_ ({', '.join(rotulo_mes(m) for m in linha['meses_sem_gasto'])})"
                for _, linha in com_buraco.iterrows()
            )
        )


st.markdown("### Onde o fixo está concentrado")
col1, col2 = st.columns([3, 2], gap="medium")
resumo_gc = fixos.por_grande_categoria(cadastro, mes)

with col1:
    with c.painel(chave="fixo_por_categoria"):
        priv.grafico(
            graficos.gastos_fixos_por_categoria(
                resumo_gc, estado.cores_grande_categoria()),
            width="stretch", key="gastos_fixos_gastos_fixos_por_categoria")
with col2:
    if not resumo_gc.empty:
        tabela_gc = resumo_gc.copy()
        tabela_gc["percentual"] = tabela_gc["percentual"] * 100
        priv.tabela(
            tabela_gc.rename(columns={
                "grande_categoria": "Grande categoria", "total": "Mensal",
                "quantidade": "Itens", "percentual": "% do fixo",
            }),
            hide_index=True, width="stretch",
            column_config={
                "Mensal": c.config_moeda("Mensal"),
                "% do fixo": c.config_percentual("% do fixo"),
            },
        )


with st.expander("Como o gasto fixo evolui nos próximos meses"):
    st.caption(
        "Leva em conta início, fim e reajuste anual de cada item. Os degraus "
        "para baixo são contratos que terminam; os para cima, reajustes."
    )
    projecao_fixos = fixos.projecao(cadastro, mes, 18)
    if not projecao_fixos.empty:
        priv.tabela(
            projecao_fixos.assign(mes=projecao_fixos["mes"].map(rotulo_mes)).rename(
                columns={"mes": "Mês", "total": "Total fixo", "quantidade": "Itens"}),
            hide_index=True, width="stretch", height=300,
            column_config={"Total fixo": c.config_moeda("Total fixo")},
        )


st.markdown("---")
c.secao(f"O que entra na previsão de {rotulo_mes(mes)}")
st.caption(
    "O valor cadastrado nem sempre é o que a previsão soma. Um item que já foi "
    "lançado no mês, ou que já está sendo projetado como parcela do cartão, "
    "não pode ser somado de novo — senão a mesma despesa conta duas vezes."
)

situacao = fixos.situacao_no_mes(cadastro, df, mes)

if situacao.empty:
    c.aviso_vazio("Nenhum gasto fixo cadastrado ainda.",
                  "Use a tabela abaixo para cadastrar o primeiro.")
else:
    em_parcela = situacao[situacao["situacao"] == config.SITUACAO_PARCELA]
    if not em_parcela.empty:
        st.warning(
            f"**{len(em_parcela)} item(ns) já estão nas parcelas do cartão** e "
            f"por isso não são somados de novo: "
            f"{fmt_brl_md(float(em_parcela['parcela_prevista'].sum()))} por mês "
            f"que a previsão contava duas vezes."
        )

    entra = float(situacao["entra_na_previsao"].sum())
    do_cartao = situacao["forma_pagamento"] == config.FORMA_CARTAO
    c.linha_kpis([
        {
            "rotulo": "Entra na previsão",
            "valor": fmt_brl(entra),
            "ajuda": f"o piso cadastrado é {fmt_brl(indicadores['cadastrado'])}",
            "cor": "azul",
        },
        {
            "rotulo": "Pago por boleto/Pix",
            "valor": fmt_brl(float(situacao[~do_cartao]["entra_na_previsao"].sum())),
            "ajuda": "sai direto da conta",
        },
        {
            "rotulo": "Pago no cartão",
            "valor": fmt_brl(float(situacao[do_cartao]["entra_na_previsao"].sum())),
            "ajuda": "já está vendido na fatura antes de você comprar nada",
        },
    ])

    priv.tabela(
        situacao[["item", "forma_pagamento", "cadastrado", "entra_na_previsao",
                  "situacao", "motivo"]].rename(columns={
            "item": "Item", "forma_pagamento": "Como paga",
            "cadastrado": "Cadastrado", "entra_na_previsao": "Entra",
            "situacao": "Situação", "motivo": "Por quê",
        }),
        hide_index=True, width="stretch", height=420,
        column_config={
            "Cadastrado": c.config_moeda("Cadastrado"),
            "Entra": c.config_moeda("Entra", "o que a previsão soma"),
        },
    )

ambiguas = [
    linha for _, linha in comparacao.iterrows()
    if len(linha.get("categorias_casadas") or []) > 1
] if not comparacao.empty else []
for linha in ambiguas:
    st.caption(
        f"A chave «**{linha['chave_historico']}**» de _{linha['item']}_ casa "
        f"com lançamentos de {', '.join(linha['categorias_casadas'])}. Se ela "
        f"estiver pegando coisa que não é deste item, preencha «Só desta "
        f"categoria» no cadastro abaixo."
    )


st.markdown("---")
st.markdown("### Cadastro de gastos fixos")
st.caption(
    "Edite direto na tabela e clique em Salvar. Para adicionar um item novo, "
    "use a última linha vazia."
)

colunas_cadastro = ["id", "item", "categoria", "valor_mensal", "forma_pagamento",
                    "considerar_previsao", "base_valor", "dia", "inicio",
                    "fim", "reajuste_aa", "ativo", "chave_historico",
                    "categoria_historico"]
para_editar = (
    cadastro[colunas_cadastro].copy() if not cadastro.empty
    else pd.DataFrame(columns=colunas_cadastro)
)
para_editar["reajuste_aa"] = para_editar["reajuste_aa"].fillna(0) * 100
para_editar["ativo"] = para_editar["ativo"].fillna(1).astype(bool)
para_editar["considerar_previsao"] = (
    para_editar["considerar_previsao"].fillna(1).astype(bool))
para_editar["forma_pagamento"] = (
    para_editar["forma_pagamento"].fillna(config.FORMA_CONTA))
para_editar["base_valor"] = (
    para_editar["base_valor"].fillna(config.BASE_CADASTRADO))
para_editar["categoria_historico"] = (
    para_editar["categoria_historico"].fillna(""))

editado = priv.editor(
    para_editar,
    hide_index=True, width="stretch", num_rows="dynamic",
    key="editor_fixos",
    column_config={
        "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
        "item": st.column_config.TextColumn("Item", required=True, width="large"),
        "categoria": st.column_config.SelectboxColumn(
            "Categoria", options=estado.lista_categorias()),
        "valor_mensal": st.column_config.NumberColumn(
            "Valor mensal", format="R$ %.2f", min_value=0.0, step=10.0),
        "forma_pagamento": st.column_config.SelectboxColumn(
            "Como paga", options=config.FORMAS_PAGAMENTO, width="small",
            help="Cartão = cai na fatura. Conta = boleto, Pix ou débito"),
        "considerar_previsao": st.column_config.CheckboxColumn(
            "Na previsão",
            help="desmarque para tirar este item da projeção de caixa"),
        "base_valor": st.column_config.SelectboxColumn(
            "Base do valor", options=config.BASES_VALOR, width="small",
            help="Cadastrado usa o valor ao lado; Média 6m usa a média das "
                 "últimas cobranças reais, para conta que varia todo mês"),
        "dia": st.column_config.NumberColumn(
            "Dia", min_value=1, max_value=31, step=1, help="dia do vencimento"),
        "inicio": st.column_config.TextColumn("Início", help="AAAA-MM", width="small"),
        "fim": st.column_config.TextColumn(
            "Fim", help="AAAA-MM — deixe vazio se não tem fim previsto", width="small"),
        "reajuste_aa": st.column_config.NumberColumn(
            "Reajuste % a.a.", format="%.1f%%", min_value=0.0, step=0.5,
            help="reajuste anual do contrato"),
        "ativo": st.column_config.CheckboxColumn("Ativo"),
        "chave_historico": st.column_config.TextColumn(
            "Chave no histórico", width="medium",
            help="texto que aparece na descrição do lançamento, ex: ESTACIO"),
        "categoria_historico": st.column_config.SelectboxColumn(
            "Só desta categoria", options=[""] + estado.lista_categorias(),
            width="small",
            help="deixe vazio para casar com qualquer categoria; preencha "
                 "quando a chave estiver pegando lançamentos que não são "
                 "deste item"),
    },
)

sumiram, apagar = c.guarda_de_exclusao(
    editado, cadastro, "item", "gasto fixo", "confirmar_exclusao_fixos")

if st.button("Salvar cadastro", type="primary"):
    salvos = 0
    for _, linha in editado.iterrows():
        item = _texto_ou_none(linha.get("item")) or ""
        if not item:
            continue

        campos = [
            ("item", item),
            ("categoria", _texto_ou_none(linha.get("categoria"))),
            ("valor_mensal", _numero_ou(linha.get("valor_mensal"), 0.0)),
            ("forma_pagamento", _texto_ou_none(linha.get("forma_pagamento"))
             or config.FORMA_CONTA),
            ("considerar_previsao", 1 if linha.get("considerar_previsao") else 0),
            ("base_valor", _texto_ou_none(linha.get("base_valor"))
             or config.BASE_CADASTRADO),
            ("dia", int(linha["dia"]) if pd.notna(linha.get("dia")) else None),
            ("inicio", _texto_ou_none(linha.get("inicio"))),
            ("fim", _texto_ou_none(linha.get("fim"))),
            ("reajuste_aa", _numero_ou(linha.get("reajuste_aa"), 0.0) / 100),
            ("ativo", 1 if linha.get("ativo") else 0),
            ("chave_historico", _texto_ou_none(linha.get("chave_historico"))),
            ("categoria_historico",
             _texto_ou_none(linha.get("categoria_historico"))),
        ]
        nomes = [nome for nome, _ in campos]
        valores = tuple(valor for _, valor in campos)

        if pd.notna(linha.get("id")):
            atribuicoes = ", ".join(f"{nome}=?" for nome in nomes)
            banco.executar(
                f"UPDATE gastos_fixos SET {atribuicoes} WHERE id=?",
                (*valores, int(linha["id"])),
            )
        else:
            banco.executar(
                f"INSERT INTO gastos_fixos ({','.join(nomes)}) "
                f"VALUES ({','.join('?' * len(nomes))})",
                valores,
            )
        salvos += 1

    if sumiram and apagar:
        for id_antigo in sumiram:
            banco.executar("DELETE FROM gastos_fixos WHERE id = ?", (id_antigo,))
        c.recado(f"{salvos} item(ns) salvo(s). {len(sumiram)} apagado(s).",
                 "aviso")
    elif sumiram:
        c.recado(
            f"{salvos} item(ns) salvo(s). {'O' if len(sumiram) == 1 else 'Os'} "
            f"{len(sumiram)} que você removeu da tabela "
            f"{'continua' if len(sumiram) == 1 else 'continuam'} no banco — "
            f"marque a caixa de confirmação para apagar de verdade.", "info")
    else:
        c.recado(f"{salvos} item(ns) salvo(s).")

    estado.limpar_cache()
    st.rerun()
