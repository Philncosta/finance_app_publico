"""
compras.py — Lista de desejos: o que voce quer comprar, e se vale a pena agora.
==============================================================================

A IDEIA
-------
Toda compra grande comeca como vontade. Anotar a vontade num lugar, com preco
alvo e preco de hoje, faz duas coisas:

    1. Cria uma pausa entre querer e comprar (a lista vira o "carrinho" onde a
       vontade espera).
    2. Deixa a decisao objetiva: quando o preco chega no alvo, compra; quando
       nao chega, espera.

A PONTE COM AS METAS
--------------------
Item caro nao e compra, e projeto. Acima de um valor de corte (parametro
`corte_meta`, R$ ···· por padrao), o item deixa de ser "compro quando der" e
passa a exigir um plano de poupanca — ou seja, vira meta.

A funcao `promover_para_meta()` faz essa passagem com um clique, levando o
preco como valor alvo.
"""

from __future__ import annotations

import pandas as pd

from financas import banco
from financas.formato import (indice_para_mes, mes_para_indice, somar_meses,
                              vazio)

STATUS_POSSIVEIS = ["Desejo", "Pesquisando", "Aguardando preço", "Comprado", "Descartado"]
PRIORIDADES = ["Alta", "Média", "Baixa"]


def cadastro() -> pd.DataFrame:
    """Le a lista de futuras compras."""
    return banco.df("SELECT * FROM futuras_compras ORDER BY id")


def calcular(df_compras: pd.DataFrame, corte_meta: float | None = None) -> pd.DataFrame:
    """Acrescenta as colunas calculadas de cada item.

    Colunas acrescentadas:
        preco_referencia  o menor entre alvo e atual (o que voce pagaria hoje
                          se comprasse pelo melhor preco conhecido)
        variacao          quanto o preco atual esta acima (ou abaixo) do alvo,
                          em fracao: 0.13 = 13% acima do alvo
        atingiu_alvo      True quando o preco atual chegou no alvo
        vira_meta         True quando o valor passa do corte
        em_aberto         True quando ainda nao foi comprado nem descartado
    """
    colunas_extras = ["preco_referencia", "variacao", "atingiu_alvo",
                      "vira_meta", "em_aberto"]
    if df_compras.empty:
        saida = df_compras.copy()
        for coluna in colunas_extras:
            saida[coluna] = pd.Series(dtype="object")
        return saida

    if corte_meta is None:
        corte_meta = banco.obter_parametro_num("corte_meta", 1000.0)

    saida = df_compras.copy()

    def calcular_linha(item):
        alvo = item.get("preco_alvo")
        atual = item.get("preco_atual")
        alvo = None if vazio(alvo) else float(alvo)
        atual = None if vazio(atual) else float(atual)

        precos = [p for p in (alvo, atual) if p is not None and p > 0]
        referencia = min(precos) if precos else 0.0
        maior = max(precos) if precos else 0.0

        variacao = (atual / alvo - 1) if (alvo and atual) else None

        status = item.get("status") or "Desejo"
        return pd.Series({
            "preco_referencia": referencia,
            "variacao": variacao,
            "atingiu_alvo": bool(alvo and atual and atual <= alvo),
            "vira_meta": maior >= corte_meta,
            "em_aberto": status not in ("Comprado", "Descartado"),
        })

    calculadas = saida.apply(calcular_linha, axis=1)
    for coluna in colunas_extras:
        saida[coluna] = calculadas[coluna]

    ordem_prioridade = {"Alta": 0, "Média": 1, "Baixa": 2}
    saida["_ordem"] = saida["prioridade"].map(
        lambda p: ordem_prioridade.get(p, 1)).fillna(1)
    saida = saida.sort_values(
        ["em_aberto", "_ordem", "preco_referencia"],
        ascending=[False, True, False],
    ).drop(columns=["_ordem"])

    return saida


def indicadores(df_calculado: pd.DataFrame) -> dict:
    """Os numeros do topo da tela de compras.

    Devolve: n_em_aberto, valor_em_aberto, valor_alta_prioridade,
             n_atingiram_alvo, n_viram_meta
    """
    if df_calculado.empty:
        return {"n_em_aberto": 0, "valor_em_aberto": 0.0,
                "valor_alta_prioridade": 0.0, "n_atingiram_alvo": 0,
                "n_viram_meta": 0}

    abertos = df_calculado[df_calculado["em_aberto"]]
    alta = abertos[abertos["prioridade"] == "Alta"]

    return {
        "n_em_aberto": int(len(abertos)),
        "valor_em_aberto": float(abertos["preco_referencia"].sum()),
        "valor_alta_prioridade": float(alta["preco_referencia"].sum()),
        "n_atingiram_alvo": int(abertos["atingiu_alvo"].sum()),
        "n_viram_meta": int(abertos["vira_meta"].sum()),
    }


def calendario(df_calculado: pd.DataFrame, projecao: pd.DataFrame | None,
               capacidade_mensal: float, mes_base: str,
               n_meses: int = 12) -> pd.DataFrame:
    """Em que mes cada item da lista cabe no orcamento, um depois do outro.

    A CONTA. Cada mes futuro tem uma sobra — `saldo_mes` da projecao de caixa
    do Planejamento, ou a sua capacidade mensal quando nao ha projecao. Essa
    sobra ACUMULA de um mes para o outro (e o que voce guardou e nao gastou), e
    o item entra no primeiro mes em que o acumulado cobre o preco dele.

    A FILA E RIGOROSA, DE PROPOSITO. Os itens sao atendidos em ordem de
    prioridade, e um item caro SEGURA a fila ate caber. A alternativa
    (pular o caro e ir enfiando os baratos que cabem) rende uma lista mais
    cheia e uma prioridade que nao significa nada: o item "Alta" de R$ ····
    nunca chegaria, porque os de R$ ···· comeriam a sobra todo mes. Se voce
    quer o barato antes, e so mudar a prioridade dele — que e exatamente o
    controle que a coluna existe para dar.

    Colunas devolvidas (uma linha por item em aberto):
        mes_sugerido      'AAAA-MM' em que ele cabe, ou None se nao cabe em
                          `n_meses`
        meses_de_espera   quantos meses a partir de `mes_base`
        cabe_no_alvo      False quando o mes sugerido passa do `mes_alvo` que
                          voce queria (ou quando nao cabe no horizonte)
        caixa_depois      quanto sobra no acumulado logo apos a compra

    NAO HA JUROS NEM PARCELAMENTO AQUI: e uma soma de sobras, tudo a vista.
    Parcelar muda a conta e ja tem tela propria (Cartão e parcelas).
    """
    colunas = ["id", "item", "prioridade", "preco_referencia", "mes_alvo",
               "mes_sugerido", "meses_de_espera", "cabe_no_alvo", "caixa_depois"]
    if df_calculado.empty or "em_aberto" not in df_calculado.columns:
        return pd.DataFrame(columns=colunas)

    fila = df_calculado[
        df_calculado["em_aberto"] & (df_calculado["preco_referencia"] > 0)
    ].copy()
    if fila.empty:
        return pd.DataFrame(columns=colunas)

    ordem_prioridade = {"Alta": 0, "Média": 1, "Baixa": 2}
    fila["_ordem"] = fila["prioridade"].map(
        lambda p: ordem_prioridade.get(p, 1)).fillna(1)
    fila["_alvo"] = fila.get("mes_alvo", pd.Series(dtype="object")).map(
        lambda m: mes_para_indice(str(m)) if not vazio(m) else 9999)
    fila = fila.sort_values(["_ordem", "_alvo", "preco_referencia"])

    # Quanto sobra em cada mes: a projecao manda; sem ela, a capacidade.
    sobra_do_mes: dict[str, float] = {}
    if projecao is not None and not projecao.empty and "saldo_mes" in projecao:
        sobra_do_mes = {
            str(linha["mes"]): max(0.0, float(linha["saldo_mes"]))
            for _, linha in projecao.iterrows()
        }

    indice_base = mes_para_indice(mes_base) or 0
    pendentes = list(fila.iterrows())
    resultado = []
    caixa = 0.0

    for passo in range(n_meses):
        mes = indice_para_mes(indice_base + passo)
        caixa += sobra_do_mes.get(mes, max(0.0, float(capacidade_mensal)))

        # A fila e rigorosa: o primeiro que nao couber para a rodada do mes.
        while pendentes:
            item = pendentes[0][1]
            preco = float(item["preco_referencia"])
            if preco > caixa:
                break
            pendentes.pop(0)
            caixa -= preco
            alvo = item.get("mes_alvo")
            indice_alvo = None if vazio(alvo) else mes_para_indice(str(alvo))
            resultado.append({
                "id": item.get("id"),
                "item": item.get("item"),
                "prioridade": item.get("prioridade"),
                "preco_referencia": preco,
                "mes_alvo": None if vazio(alvo) else str(alvo),
                "mes_sugerido": mes,
                "meses_de_espera": passo,
                "cabe_no_alvo": (indice_alvo is None
                                 or indice_base + passo <= indice_alvo),
                "caixa_depois": caixa,
            })

    for _, item in pendentes:
        alvo = item.get("mes_alvo")
        resultado.append({
            "id": item.get("id"),
            "item": item.get("item"),
            "prioridade": item.get("prioridade"),
            "preco_referencia": float(item["preco_referencia"]),
            "mes_alvo": None if vazio(alvo) else str(alvo),
            "mes_sugerido": None,
            "meses_de_espera": None,
            "cabe_no_alvo": False,
            "caixa_depois": None,
        })

    return pd.DataFrame(resultado, columns=colunas)


def meses_para_juntar(valor: float, capacidade_mensal: float) -> float | None:
    """Em quantos meses da para juntar `valor` guardando `capacidade` por mes.

    Devolve None quando a capacidade e zero ou negativa — porque nesse caso a
    resposta honesta e "nunca, do jeito que esta", e devolver um numero enorme
    so confundiria a tela.
    """
    if capacidade_mensal <= 0 or valor <= 0:
        return None
    return valor / capacidade_mensal


def promover_para_meta(id_compra: int, mes_atual: str,
                       prazo_meses: int = 12) -> int:
    """Transforma um item da lista de desejos numa meta de poupanca.

    Leva o preco de referencia como valor alvo e cria a meta com o prazo
    escolhido. O item continua na lista de compras (com status "Aguardando
    preço"), porque voce ainda vai querer acompanhar o preco dele.
    """
    item = banco.consultar_um("SELECT * FROM futuras_compras WHERE id = ?", (id_compra,))
    if item is None:
        raise ValueError(f"Item {id_compra} nao encontrado na lista de compras.")

    precos = [
        float(p) for p in (item["preco_alvo"], item["preco_atual"])
        if not vazio(p) and float(p) > 0
    ]
    valor_alvo = min(precos) if precos else 0.0

    ultima = banco.consultar_um("SELECT COALESCE(MAX(ordem), 0) AS m FROM metas")
    novo_id = banco.executar(
        """INSERT INTO metas
           (meta, tipo, valor_alvo, ja_acumulado, prazo, aporte_definido,
            prioridade, status, observacao, ordem)
           VALUES (?, 'Compra à vista', ?, 0, ?, 0, ?, 'Ativa', ?, ?)""",
        (
            item["item"],
            valor_alvo,
            somar_meses(mes_atual, prazo_meses),
            item["prioridade"] or "Média",
            f"Criada a partir da lista de futuras compras (item #{id_compra}).",
            int(ultima["m"]) + 1,
        ),
    )

    banco.executar(
        "UPDATE futuras_compras SET status = 'Aguardando preço' WHERE id = ?",
        (id_compra,),
    )
    return novo_id
