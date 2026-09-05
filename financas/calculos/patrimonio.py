"""
patrimonio.py — Quanto voce tem, e por quantos meses isso te sustenta.
==============================================================================

DUAS PERGUNTAS
--------------
    evolucao()        Como o meu dinheiro cresceu (ou encolheu) mes a mes?
    posicao_atual()   Se a renda parasse hoje, por quantos meses eu aguento?

A SEGUNDA E A MAIS IMPORTANTE. Ter R$ ···· guardados nao significa nada
sozinho: para quem gasta R$ ···· por mes sao 12 meses de tranquilidade; para
quem gasta R$ ···· sao menos de tres. Por isso a reserva e medida em MESES
DE DESPESA, nao em reais.

DE ONDE SAI CADA NUMERO
-----------------------
SALDO EM CONTA — o dinheiro liquido, na conta corrente. Vem de duas fontes,
nesta ordem de preferencia:
    1. o que voce digitou na tabela (tabela patrimonio_mensal);
    2. o ULTIMO saldo do extrato daquele mes (coluna saldo_apos), que o
       proprio banco informou na importacao.
A segunda fonte e o que faz isso funcionar sem trabalho manual: se voce
importa o extrato, o saldo se atualiza sozinho.

SALDO APLICADO — o que esta investido. O banco nao manda esse numero no
extrato da conta corrente, entao ele e ESTIMADO acumulando as transferencias:

    aplicado(mes) = aplicado(mes anterior) + aportes - resgates + rendimentos

Os aportes e resgates sao os lancamentos de natureza Investimento, que agora
tem sinal correto (a correcao feita na migracao). Voce pode sobrescrever o
valor de qualquer mes digitando o saldo real — util para acertar quando o
rendimento da corretora nao passa pela conta corrente.
"""

from __future__ import annotations

import pandas as pd

from financas import banco, config, dados
from financas.formato import somar_meses, vazio


def _saldos_informados() -> dict[str, dict]:
    """Le a tabela patrimonio_mensal: {mes: {saldo_conta, saldo_aplicado_manual}}."""
    return {
        linha["mes"]: {
            "saldo_conta": linha["saldo_conta"],
            "saldo_aplicado_manual": linha["saldo_aplicado_manual"],
        }
        for linha in banco.consultar(
            "SELECT mes, saldo_conta, saldo_aplicado_manual FROM patrimonio_mensal")
    }


def _saldo_do_extrato(df: pd.DataFrame) -> dict[str, float]:
    """Ultimo saldo informado pelo banco em cada mes, tirado do extrato.

    "Ultimo" = o do lancamento mais recente do mes. Ordenamos por data e hora
    porque num mesmo dia pode haver varias transacoes, e so a ultima carrega o
    saldo de fechamento.
    """
    if df.empty:
        return {}
    extrato = dados.da_conta(df)
    extrato = extrato[extrato["saldo_apos"].notna()]
    if extrato.empty:
        return {}

    ordenado = extrato.sort_values(
        ["mes_competencia", "data", "hora"], na_position="first")
    ultimos = ordenado.groupby("mes_competencia").tail(1)
    return dict(zip(ultimos["mes_competencia"], ultimos["saldo_apos"]))


def evolucao(df: pd.DataFrame, saldo_aplicado_inicial: float | None = None) -> pd.DataFrame:
    """Monta a tabela de patrimonio mes a mes.

    Colunas devolvidas:
        mes, saldo_conta, aportes, resgates, aporte_liquido, rendimentos,
        saldo_aplicado, patrimonio_total, capital_terceiros,
        patrimonio_proprio, origem_saldo

    SOBRE AS DUAS LEITURAS DE PATRIMONIO:

        patrimonio_total    tudo que esta nas suas contas  (inclui terceiros)
        patrimonio_proprio  o que sobra se voce devolver   (exclui terceiros)

    O dinheiro de terceiros ja e Transferencia, entao nunca entrou em receita
    nem em despesa. Mas ele ESTA na conta e ESTA investido junto com o seu —
    por isso precisa ser descontado aqui, e so aqui.

    `origem_saldo` diz de onde veio o saldo em conta ("informado" ou
    "extrato") — aparece na tela para voce saber em quais meses precisa
    conferir.
    """
    colunas = ["mes", "saldo_conta", "aportes", "resgates", "aporte_liquido",
               "rendimentos", "saldo_aplicado", "patrimonio_total",
               "capital_terceiros", "patrimonio_proprio", "origem_saldo"]
    if df.empty:
        return pd.DataFrame(columns=colunas)

    if saldo_aplicado_inicial is None:
        saldo_aplicado_inicial = banco.obter_parametro_num("saldo_aplicado_inicial", 0.0)

    informados = _saldos_informados()
    do_extrato = _saldo_do_extrato(df)
    from financas.calculos import investimentos as _inv
    carteira_por_mes = _inv.total_por_mes()

    investimentos = df[df["natureza"] == config.NATUREZA_INVESTIMENTO]

    de_terceiros = df[df["categoria"] == config.categoria_terceiros()]
    terceiros_por_mes = (de_terceiros.groupby("mes_competencia")["valor"].sum()
                         if not de_terceiros.empty else {})

    meses = sorted(df["mes_competencia"].unique())
    linhas = []
    aplicado = float(saldo_aplicado_inicial)
    ultimo_saldo_conta = 0.0
    terceiros = 0.0

    for mes in meses:
        do_mes = investimentos[investimentos["mes_competencia"] == mes]

        if do_mes.empty:
            aportes = resgates = rendimentos = 0.0
        else:
            rendimento_linhas = do_mes[do_mes["categoria"] == "Rendimentos"]
            movimento = do_mes[do_mes["categoria"] != "Rendimentos"]
            rendimentos = float(rendimento_linhas["valor"].sum())
            aportes = float(-movimento[movimento["valor"] < 0]["valor"].sum())
            resgates = float(movimento[movimento["valor"] > 0]["valor"].sum())

        aplicado += aportes - resgates + rendimentos

        da_carteira = carteira_por_mes.get(mes)
        if da_carteira is not None:
            aplicado = float(da_carteira)

        manual = informados.get(mes, {}).get("saldo_aplicado_manual")
        if not vazio(manual):
            aplicado = float(manual)

        informado = informados.get(mes, {}).get("saldo_conta")
        if not vazio(informado):
            saldo_conta = float(informado)
            origem_saldo = "informado"
        elif mes in do_extrato:
            saldo_conta = float(do_extrato[mes])
            origem_saldo = "extrato"
        else:
            saldo_conta = ultimo_saldo_conta
            origem_saldo = "repetido"
        ultimo_saldo_conta = saldo_conta

        terceiros += float(terceiros_por_mes.get(mes, 0.0))
        total = saldo_conta + aplicado

        linhas.append({
            "mes": mes,
            "saldo_conta": saldo_conta,
            "aportes": aportes,
            "resgates": resgates,
            "aporte_liquido": aportes - resgates,
            "rendimentos": rendimentos,
            "saldo_aplicado": aplicado,
            "patrimonio_total": total,
            "capital_terceiros": terceiros,
            "patrimonio_proprio": total - terceiros,
            "origem_saldo": origem_saldo,
        })

    return pd.DataFrame(linhas, columns=colunas)


def posicao_atual(df: pd.DataFrame, mes: str | None = None,
                  janela_despesa: int = 6) -> dict:
    """A foto de hoje: quanto tem, quanto gasta, por quanto tempo dura.

    Devolve:
        saldo_conta, saldo_aplicado, patrimonio_total,
        capital_terceiros, patrimonio_proprio,
        despesa_media, meses_de_reserva, meta_meses, falta_para_meta,
        pct_da_meta, situacao

    A reserva de emergencia sai do PATRIMONIO PROPRIO, nao do total: dinheiro
    de terceiros esta na conta mas nao esta disponivel para voce viver dele.
    Conta-lo diria "voce aguenta 15 meses" quando o numero verdadeiro e menor
    — e e numa emergencia que essa diferenca apareceria.

    `situacao` classifica a reserva em quatro faixas, que a tela colore:
        "crítica"     menos de 1 mes
        "frágil"      1 a 3 meses
        "razoável"    3 meses ate a meta
        "confortável" meta atingida
    """
    tabela = evolucao(df)
    if tabela.empty:
        return {
            "saldo_conta": 0.0, "saldo_aplicado": 0.0, "patrimonio_total": 0.0,
            "capital_terceiros": 0.0, "patrimonio_proprio": 0.0,
            "despesa_media": 0.0, "meses_de_reserva": 0.0,
            "meta_meses": banco.obter_parametro_num("meta_reserva_meses", 6),
            "falta_para_meta": 0.0, "pct_da_meta": 0.0, "situacao": "sem dados",
            "mes": mes,
        }

    if not mes:
        mes = dados.mes_mais_recente()

    if mes:
        recorte = tabela[tabela["mes"] <= mes]
        atual = recorte.iloc[-1] if not recorte.empty else tabela.iloc[-1]
    else:
        atual = tabela.iloc[-1]
    mes_ref = atual["mes"]

    serie = dados.por_mes(df)
    if not serie.empty:
        if "quantidade" in serie.columns:
            serie = serie[serie["quantidade"] >= 5]
        inicio = somar_meses(mes_ref, -(janela_despesa - 1)) or mes_ref
        janela = serie[(serie["mes"] >= inicio) & (serie["mes"] <= mes_ref)]
        despesa_media = float(janela["despesa"].median()) if not janela.empty else 0.0
    else:
        despesa_media = 0.0

    meta_meses = banco.obter_parametro_num("meta_reserva_meses", 6)
    patrimonio_total = float(atual["patrimonio_total"])
    capital_terceiros = float(atual.get("capital_terceiros", 0.0) or 0.0)
    patrimonio_proprio = patrimonio_total - capital_terceiros

    meses_reserva = patrimonio_proprio / despesa_media if despesa_media else 0.0
    alvo = meta_meses * despesa_media

    if meses_reserva < 1:
        situacao = "crítica"
    elif meses_reserva < 3:
        situacao = "frágil"
    elif meses_reserva < meta_meses:
        situacao = "razoável"
    else:
        situacao = "confortável"

    return {
        "mes": mes_ref,
        "saldo_conta": float(atual["saldo_conta"]),
        "saldo_aplicado": float(atual["saldo_aplicado"]),
        "patrimonio_total": patrimonio_total,
        "capital_terceiros": capital_terceiros,
        "patrimonio_proprio": patrimonio_proprio,
        "despesa_media": despesa_media,
        "meses_de_reserva": meses_reserva,
        "meta_meses": meta_meses,
        "falta_para_meta": max(0.0, alvo - patrimonio_proprio),
        "pct_da_meta": patrimonio_proprio / alvo if alvo else 0.0,
        "situacao": situacao,
    }


def salvar_saldo(mes: str, saldo_conta: float | None,
                 saldo_aplicado: float | None = None) -> None:
    """Grava (ou corrige) o saldo de um mes na tabela patrimonio_mensal."""
    banco.executar(
        """INSERT INTO patrimonio_mensal (mes, saldo_conta, saldo_aplicado_manual)
           VALUES (?,?,?)
           ON CONFLICT(mes) DO UPDATE SET
               saldo_conta = excluded.saldo_conta,
               saldo_aplicado_manual = excluded.saldo_aplicado_manual""",
        (mes, saldo_conta, saldo_aplicado),
    )
