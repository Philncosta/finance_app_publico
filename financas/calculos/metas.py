"""
metas.py — Objetivos financeiros e o aporte que cada um exige.
==============================================================================

A CONTA CENTRAL
---------------
Uma meta e sempre a mesma pergunta: "quero R$ X ate a data D; quanto preciso
guardar por mes?"

        aporte_necessario = (valor_alvo - ja_acumulado) / meses_restantes

Simples assim. O valor do modulo nao esta na formula, e em cruzar isso com a
sua CAPACIDADE real de poupar (que vem do Planejamento) e dizer, sem rodeio,
quais prazos sao possiveis e quais nao sao.

O RECURSO MAIS HONESTO: A DATA PREVISTA REAL
---------------------------------------------
Existem duas datas para cada meta:

    prazo desejado   a data que voce escolheu
    data prevista    a data em que voce vai chegar la NO RITMO ATUAL

Se voce definiu um aporte de R$ ····/mes para uma meta de R$ ····, a data
prevista fica a 30 anos de distancia, mesmo que o prazo desejado diga 2 anos.
Mostrar as duas lado a lado e o que transforma uma lista de desejos num plano.

O "JA ACUMULADO" PODE SER DIGITADO, OU PODE SER REAL
-----------------------------------------------------
Por padrao, `ja_acumulado` e um numero que voce digita — serve bem para uma
entrada de imovel ou uma reserva, onde o dinheiro fica parado numa conta e so
voce sabe quanto tem.

Mas para uma meta como "chegar a R$ ···· investido", digitar o numero a
mao significa lembrar de atualizar toda vez que o valor da carteira mudar —
e ele muda todo mes, com aporte e com oscilacao de mercado. Uma meta que
depende de voce lembrar de atualizar um numero acaba desatualizada.

Por isso uma meta pode ter `vinculo = "patrimonio_investido"`. Quando tem,
`calcular()` IGNORA o que esta digitado na coluna e usa o patrimonio investido
de VERDADE — o mesmo numero que o Dashboard mostra em "Investido"
(`estado.carteira_conciliacao()["carteira_cadastrada"]`). A meta passa a se
atualizar sozinha, a cada aporte, resgate ou variacao de mercado.

NAO HA JUROS NA PROJECAO, DE PROPOSITO
---------------------------------------
`meses_no_ritmo = falta / aporte` e uma SOMA, nao um valor futuro composto.
R$ ····/mes por 24 meses aqui dao R$ ···· nunca mais que isso. A decisao e
deliberada: o objetivo desta conta e responder "quanto da minha propria
receita/despesa eu vou guardar", nao simular retorno de investimento — isso
ja existe, separado, na comparacao com indices da tela de Investimentos.
Somar as duas coisas aqui inflaria a meta com uma expectativa de mercado que
pode nao se realizar.
"""

from __future__ import annotations

import math

import pandas as pd

from financas import banco
from financas.formato import indice_para_mes, mes_para_indice, vazio

VINCULO_PATRIMONIO_INVESTIDO = "patrimonio_investido"

# As listas ficam aqui, e nao na pagina, porque agora sao usadas em DOIS
# lugares da mesma tela — o formulario de cada cartao e a tabela do modo
# avancado. Duas copias divergiriam no dia em que um tipo novo entrasse so
# numa delas, e a meta gravada por um lado sumiria da caixa de selecao do outro.
TIPOS = ["Reserva", "Acumular", "Financiamento", "Compra à vista",
         "Viagem", "Outro"]
PRIORIDADES = ["Alta", "Média", "Baixa"]
STATUS_POSSIVEIS = ["Ativa", "Concluída", "Pausada"]


def cadastro() -> pd.DataFrame:
    """Le as metas cadastradas."""
    return banco.df("SELECT * FROM metas ORDER BY ordem, id")


def _renumerar() -> list[int]:
    """Da a cada meta um `ordem` unico de 1 a N, na ordem em que ela aparece.

    Existe porque `ordem` nasceu com `DEFAULT 0`: todas as metas cadastradas
    pela tabela tem ordem 0, e trocar dois zeros nao muda nada. Renumerar
    antes de qualquer troca resolve isso de uma vez, sem migracao — a ordem
    visivel na tela (`ORDER BY ordem, id`) e a que vira 1, 2, 3...
    """
    ids = [int(linha["id"])
           for linha in banco.consultar("SELECT id FROM metas ORDER BY ordem, id")]
    banco.executar_muitos(
        "UPDATE metas SET ordem = ? WHERE id = ?",
        [(posicao, id_meta) for posicao, id_meta in enumerate(ids, start=1)],
    )
    return ids


def mover(id_meta: int, direcao: int) -> bool:
    """Sobe (`direcao` negativa) ou desce (positiva) a meta uma posicao.

    Devolve False quando nao ha para onde ir — a primeira meta nao sobe, a
    ultima nao desce — para a tela poder desabilitar o botao sem calcular a
    posicao por fora.
    """
    ids = _renumerar()
    if int(id_meta) not in ids:
        return False

    posicao = ids.index(int(id_meta))
    destino = posicao + (1 if direcao > 0 else -1)
    if not 0 <= destino < len(ids):
        return False

    ids[posicao], ids[destino] = ids[destino], ids[posicao]
    banco.executar_muitos(
        "UPDATE metas SET ordem = ? WHERE id = ?",
        [(nova, id_meta) for nova, id_meta in enumerate(ids, start=1)],
    )
    return True


def calcular(df_metas: pd.DataFrame, mes_atual: str,
             patrimonio_investido: float | None = None) -> pd.DataFrame:
    """Acrescenta as colunas calculadas de cada meta.

    `patrimonio_investido`: o valor real da carteira agora (mesma fonte do
    Dashboard). So e usado nas metas com `vinculo == VINCULO_PATRIMONIO_INVESTIDO`
    — para essas, ele SUBSTITUI o `ja_acumulado` digitado. As demais metas
    continuam usando o que esta no cadastro, sem mudanca de comportamento.

    Colunas acrescentadas:
        falta               quanto ainda falta juntar
        meses_restantes     ate o prazo desejado
        aporte_necessario   quanto teria de guardar por mes para cumprir o
                            prazo — ZERO quando a meta nao tem prazo, porque
                            sem data nao ha exigencia mensal a cumprir
        aporte_definido     quanto voce decidiu guardar (vem do cadastro)
        meses_no_ritmo      em quantos meses voce chega no ritmo atual
        data_prevista       quando voce chega, no ritmo atual
        pct_concluido       0 a 1
        situacao            texto curto que resume o estado
        atrasada            True se a data prevista passa do prazo desejado
    """
    colunas_extras = ["falta", "meses_restantes", "aporte_necessario",
                      "meses_no_ritmo", "data_prevista", "pct_concluido",
                      "situacao", "atrasada"]
    if df_metas.empty:
        vazio_df = df_metas.copy()
        for coluna in colunas_extras:
            vazio_df[coluna] = pd.Series(dtype="object")
        return vazio_df

    indice_atual = mes_para_indice(mes_atual) or 0
    linhas = []

    for _, meta in df_metas.iterrows():
        alvo = float(meta.get("valor_alvo") or 0)
        vinculada = (meta.get("vinculo") == VINCULO_PATRIMONIO_INVESTIDO
                     and patrimonio_investido is not None)
        acumulado = (float(patrimonio_investido) if vinculada
                     else float(meta.get("ja_acumulado") or 0))
        aporte = float(meta.get("aporte_definido") or 0)
        falta = max(0.0, alvo - acumulado)

        prazo = meta.get("prazo")
        if vazio(prazo):
            meses_restantes = None
        else:
            indice_prazo = mes_para_indice(str(prazo))
            meses_restantes = (
                max(0, indice_prazo - indice_atual) if indice_prazo else None)

        # SEM PRAZO E DIFERENTE DE PRAZO AGORA, e a versao anterior tratava os
        # dois como o mesmo caso (`if meses_restantes` e falso para None e para
        # 0). O efeito: a meta "chegar a R$ ···· investido", que nao tem
        # data, aparecia exigindo os R$ ···· que faltam DENTRO DESTE MES. O
        # numero contaminava a soma de `resumo()`, e com ele o "sua capacidade
        # cobre tudo?" e o botao de distribuir — a meta sem prazo levava
        # praticamente toda a capacidade, porque a exigencia dela era o valor
        # inteiro. Sem data para cumprir nao ha exigencia mensal nenhuma: e
        # zero. Prazo ESTE mes continua exigindo o que falta de uma vez.
        if meses_restantes is None:
            aporte_necessario = 0.0
        elif meses_restantes == 0:
            aporte_necessario = falta
        else:
            aporte_necessario = falta / meses_restantes

        if falta <= 0:
            meses_no_ritmo = 0
            data_prevista = "concluída"
        elif aporte <= 0:
            meses_no_ritmo = None
            data_prevista = "sem aporte definido"
        else:
            meses_no_ritmo = math.ceil(falta / aporte)
            data_prevista = indice_para_mes(indice_atual + meses_no_ritmo)

        pct = acumulado / alvo if alvo else 0.0
        atrasada = False
        if falta <= 0:
            situacao = "concluída"
        elif aporte <= 0:
            situacao = "sem aporte definido"
        elif meses_restantes is None:
            situacao = "sem prazo"
        elif meses_no_ritmo is not None and meses_no_ritmo > meses_restantes:
            situacao = "atrasada"
            atrasada = True
        else:
            situacao = "no ritmo"

        registro = meta.to_dict()
        registro.update({
            "ja_acumulado": acumulado,
            "falta": falta,
            "meses_restantes": meses_restantes,
            "aporte_necessario": aporte_necessario,
            "meses_no_ritmo": meses_no_ritmo,
            "data_prevista": data_prevista,
            "pct_concluido": min(1.0, pct),
            "situacao": situacao,
            "atrasada": atrasada,
        })
        linhas.append(registro)

    return pd.DataFrame(linhas)


def resumo(df_calculado: pd.DataFrame, capacidade_mensal: float) -> dict:
    """Cruza todas as metas com quanto voce consegue guardar por mes.

    Devolve:
        total_alvo, total_acumulado, total_falta, pct_geral,
        aporte_necessario_total   soma do que TODAS as metas exigem por mes
        aporte_definido_total     soma do que voce decidiu guardar
        capacidade                quanto voce consegue guardar
        sobra                     capacidade - aporte definido
        deficit                   quanto falta de capacidade para os prazos
        viavel                    True se a capacidade cobre todos os prazos
        n_atrasadas
    """
    if df_calculado.empty:
        return {
            "total_alvo": 0.0, "total_acumulado": 0.0, "total_falta": 0.0,
            "pct_geral": 0.0, "aporte_necessario_total": 0.0,
            "aporte_definido_total": 0.0, "capacidade": capacidade_mensal,
            "sobra": capacidade_mensal, "deficit": 0.0, "viavel": True,
            "n_atrasadas": 0, "n_metas": 0,
        }

    ativas = df_calculado[df_calculado.get("status", "Ativa") != "Concluída"]

    total_alvo = float(ativas["valor_alvo"].sum())
    total_acumulado = float(ativas["ja_acumulado"].sum())
    necessario = float(ativas["aporte_necessario"].sum())
    definido = float(ativas["aporte_definido"].sum())

    return {
        "total_alvo": total_alvo,
        "total_acumulado": total_acumulado,
        "total_falta": float(ativas["falta"].sum()),
        "pct_geral": total_acumulado / total_alvo if total_alvo else 0.0,
        "aporte_necessario_total": necessario,
        "aporte_definido_total": definido,
        "capacidade": capacidade_mensal,
        "sobra": capacidade_mensal - definido,
        "deficit": max(0.0, necessario - capacidade_mensal),
        "viavel": necessario <= capacidade_mensal,
        "n_atrasadas": int(ativas["atrasada"].sum()),
        "n_metas": int(len(ativas)),
    }


def capacidade_sugerida(df_projecao: pd.DataFrame) -> float:
    """Sugere quanto voce consegue guardar por mes, a partir da projecao de caixa.

    Usa a MEDIANA do saldo mensal projetado, e nunca devolve numero negativo
    (nao da para "guardar menos que zero" — se o saldo e negativo, a
    capacidade e zero e o problema esta no orcamento, nao na meta).
    """
    if df_projecao.empty or "saldo_mes" not in df_projecao.columns:
        return 0.0
    return max(0.0, float(df_projecao["saldo_mes"].median()))
