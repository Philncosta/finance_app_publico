"""
financiamento.py — Simulador de financiamento imobiliario (PRICE e SAC).
==============================================================================

O QUE ESTE MODULO CALCULA
-------------------------
Voce informa: valor do imovel, entrada, prazo, taxa de juros e os seguros. Ele
devolve a TABELA MES A MES do financiamento inteiro — quanto de cada
prestacao vai para juros, quanto abate a divida, e como o saldo devedor cai.

E, o mais interessante, simula ADIANTAR PARCELAS: se voce jogar R$ ···· por mes
a mais, quanto de juros deixa de pagar e quantos meses a menos leva.

OS DOIS SISTEMAS
----------------
PRICE — a prestacao e SEMPRE A MESMA do comeco ao fim. No inicio quase tudo e
juro e quase nada abate a divida; isso vai se invertendo ao longo do tempo.
Bom para quem precisa de previsibilidade no orcamento.

    prestacao = saldo x [ i / (1 - (1+i)^-n) ]

    onde i = juro mensal e n = numero de parcelas. Essa formula e a "Tabela
    Price" e resolve: qual valor fixo, pago n vezes, quita a divida com juros?

SAC — a AMORTIZACAO e sempre a mesma (saldo dividido pelo prazo). A prestacao
comeca alta e vai caindo todo mes, porque o juro incide sobre um saldo cada
vez menor. Paga MENOS juros no total, mas exige mais folga no comeco.

    amortizacao = saldo_inicial / n
    prestacao   = amortizacao + juro_do_mes

CONVERSAO DA TAXA — UM DETALHE QUE MUDA MUITO DINHEIRO
-------------------------------------------------------
O contrato diz "10,5% ao ano". Isso vira quanto ao mes?

    Equivalente (efetiva):  (1 + 0,105)^(1/12) - 1  =  0,8355% ao mes
    Linear (nominal/12):     0,105 / 12             =  0,8750% ao mes

Parece pouca diferenca, mas em 360 meses da dezenas de milhares de reais. Os
bancos brasileiros costumam usar a EQUIVALENTE em contratos de imovel. A
planilha permitia escolher e mantivemos a escolha.

OS CUSTOS QUE NAO SAO JUROS
---------------------------
    MIP  seguro de morte e invalidez — % sobre o SALDO DEVEDOR (cai com o tempo)
    DFI  seguro de danos ao imovel   — % sobre o VALOR DO IMOVEL (fixo)
    taxa de administracao            — valor fixo em reais por mes

Eles nao abatem divida nenhuma, mas saem do seu bolso todo mes. Ignora-los faz
a prestacao parecer 5% a 10% menor do que e de verdade.
"""

from __future__ import annotations

import pandas as pd

from financas import banco

SISTEMAS = ["PRICE", "SAC"]
CONVERSOES = ["Equivalente (efetiva)", "Linear (nominal/12)"]
EFEITOS_APORTE = ["Reduzir prazo", "Reduzir parcela"]

MAX_PARCELAS = 600


def cenario_padrao() -> dict:
    """Devolve o primeiro cenario salvo, ou um cenario novo com valores tipicos."""
    linha = banco.consultar_um("SELECT * FROM financiamento_cenarios ORDER BY id LIMIT 1")
    if linha is not None:
        return dict(linha)
    return {
        "nome": "Novo cenário", "valor_imovel": 500000.0, "valor_entrada": 100000.0,
        "prazo_meses": 360, "sistema": "PRICE", "juros_aa": 0.105,
        "conversao_taxa": "Equivalente (efetiva)", "seguro_mip_am": 0.00025,
        "seguro_dfi_am": 0.0001, "taxa_adm_mes": 25.0, "aporte_extra_mes": 0.0,
        "aporte_inicio": 1, "aporte_pontual": 0.0, "aporte_pontual_parcela": 12,
        "efeito_aporte": "Reduzir prazo",
    }


def taxa_mensal(juros_aa: float, conversao: str) -> float:
    """Converte a taxa anual em taxa mensal, do jeito escolhido.

    Ver a explicacao no topo do arquivo — a diferenca entre os dois metodos
    vale muito dinheiro num contrato de 30 anos.
    """
    if juros_aa <= 0:
        return 0.0
    if conversao == "Linear (nominal/12)":
        return juros_aa / 12
    return (1 + juros_aa) ** (1 / 12) - 1


def prestacao_price(saldo: float, taxa: float, parcelas: int) -> float:
    """A prestacao fixa da Tabela Price.

    Quando a taxa e zero (financiamento sem juros), a formula daria divisao
    por zero — nesse caso a prestacao e simplesmente o saldo dividido pelo
    numero de parcelas.
    """
    if parcelas <= 0:
        return 0.0
    if taxa <= 0:
        return saldo / parcelas
    fator = (1 + taxa) ** (-parcelas)
    return saldo * taxa / (1 - fator)


def tabela(cenario: dict) -> pd.DataFrame:
    """Monta a tabela de amortizacao completa, mes a mes.

    Colunas devolvidas:
        parcela, saldo_inicial, juros, amortizacao, amortizacao_extra,
        prestacao, mip, dfi, taxa_adm, desembolso, saldo_final

    `prestacao`  = juros + amortizacao (o que o contrato cobra de divida)
    `desembolso` = prestacao + seguros + taxa + aporte extra
                   (o que REALMENTE sai da sua conta naquele mes)

    A diferenca entre os dois e o que faz a conta bater com a vida real.
    """
    valor_imovel = float(cenario.get("valor_imovel") or 0)
    entrada = float(cenario.get("valor_entrada") or 0)
    saldo = max(0.0, valor_imovel - entrada)
    prazo = int(cenario.get("prazo_meses") or 0)

    colunas = ["parcela", "saldo_inicial", "juros", "amortizacao",
               "amortizacao_extra", "prestacao", "mip", "dfi", "taxa_adm",
               "desembolso", "saldo_final"]
    if saldo <= 0 or prazo <= 0:
        return pd.DataFrame(columns=colunas)

    taxa = taxa_mensal(float(cenario.get("juros_aa") or 0),
                       cenario.get("conversao_taxa") or CONVERSOES[0])
    sistema = (cenario.get("sistema") or "PRICE").upper()
    mip_pct = float(cenario.get("seguro_mip_am") or 0)
    dfi_pct = float(cenario.get("seguro_dfi_am") or 0)
    taxa_adm = float(cenario.get("taxa_adm_mes") or 0)

    aporte_mensal = float(cenario.get("aporte_extra_mes") or 0)
    aporte_inicio = int(cenario.get("aporte_inicio") or 1)
    aporte_pontual = float(cenario.get("aporte_pontual") or 0)
    parcela_pontual = int(cenario.get("aporte_pontual_parcela") or 0)
    efeito = cenario.get("efeito_aporte") or "Reduzir prazo"
    reduz_parcela = efeito == "Reduzir parcela"

    prestacao_fixa = prestacao_price(saldo, taxa, prazo)
    amortizacao_sac = saldo / prazo

    linhas = []
    saldo_atual = saldo
    parcelas_restantes = prazo

    for numero in range(1, MAX_PARCELAS + 1):
        if saldo_atual <= 0.005 or parcelas_restantes <= 0:
            break

        saldo_inicial = saldo_atual
        juros = saldo_inicial * taxa

        if sistema == "SAC":
            if reduz_parcela:
                amortizacao = saldo_inicial / parcelas_restantes
            else:
                amortizacao = amortizacao_sac
            prestacao = amortizacao + juros
        else:
            if reduz_parcela:
                prestacao = prestacao_price(saldo_inicial, taxa, parcelas_restantes)
            else:
                prestacao = prestacao_fixa
            amortizacao = prestacao - juros

        amortizacao = min(amortizacao, saldo_inicial)

        prestacao = min(prestacao, amortizacao + juros)

        extra = 0.0
        if aporte_mensal > 0 and numero >= aporte_inicio:
            extra += aporte_mensal
        if aporte_pontual > 0 and numero == parcela_pontual:
            extra += aporte_pontual
        extra = min(extra, max(0.0, saldo_inicial - amortizacao))

        mip = saldo_inicial * mip_pct
        dfi = valor_imovel * dfi_pct

        saldo_final = saldo_inicial - amortizacao - extra

        linhas.append({
            "parcela": numero,
            "saldo_inicial": saldo_inicial,
            "juros": juros,
            "amortizacao": amortizacao,
            "amortizacao_extra": extra,
            "prestacao": prestacao,
            "mip": mip,
            "dfi": dfi,
            "taxa_adm": taxa_adm,
            "desembolso": prestacao + mip + dfi + taxa_adm + extra,
            "saldo_final": max(0.0, saldo_final),
        })

        saldo_atual = saldo_final
        parcelas_restantes -= 1

    return pd.DataFrame(linhas, columns=colunas)


def resumo(cenario: dict) -> dict:
    """Os numeros de fechamento do contrato.

    Devolve:
        primeira_prestacao, ultima_prestacao, primeiro_desembolso,
        prazo_efetivo, total_amortizado, total_juros, total_seguros_taxas,
        custo_total, custo_com_entrada, ltv, pct_entrada,
        juros_economizados, meses_economizados

    `juros_economizados` compara com o MESMO contrato sem nenhum aporte
    extra — e a resposta para "vale a pena adiantar?".
    """
    tabela_calculada = tabela(cenario)
    if tabela_calculada.empty:
        return {
            "primeira_prestacao": 0.0, "ultima_prestacao": 0.0,
            "primeiro_desembolso": 0.0, "prazo_efetivo": 0,
            "total_amortizado": 0.0, "total_juros": 0.0,
            "total_seguros_taxas": 0.0, "custo_total": 0.0,
            "custo_com_entrada": 0.0, "ltv": 0.0, "pct_entrada": 0.0,
            "juros_economizados": 0.0, "meses_economizados": 0,
            "valor_financiado": 0.0,
        }

    valor_imovel = float(cenario.get("valor_imovel") or 0)
    entrada = float(cenario.get("valor_entrada") or 0)
    financiado = max(0.0, valor_imovel - entrada)

    total_juros = float(tabela_calculada["juros"].sum())
    total_seguros = float(
        (tabela_calculada["mip"] + tabela_calculada["dfi"]
         + tabela_calculada["taxa_adm"]).sum())
    total_amortizado = float(
        (tabela_calculada["amortizacao"] + tabela_calculada["amortizacao_extra"]).sum())

    sem_aporte = dict(cenario)
    sem_aporte.update({"aporte_extra_mes": 0.0, "aporte_pontual": 0.0})
    tem_aporte = (float(cenario.get("aporte_extra_mes") or 0) > 0
                  or float(cenario.get("aporte_pontual") or 0) > 0)

    if tem_aporte:
        base = tabela(sem_aporte)
        juros_sem_aporte = float(base["juros"].sum()) if not base.empty else 0.0
        prazo_sem_aporte = int(len(base))
    else:
        juros_sem_aporte = total_juros
        prazo_sem_aporte = int(len(tabela_calculada))

    return {
        "valor_financiado": financiado,
        "primeira_prestacao": float(tabela_calculada["prestacao"].iloc[0]),
        "ultima_prestacao": float(tabela_calculada["prestacao"].iloc[-1]),
        "primeiro_desembolso": float(tabela_calculada["desembolso"].iloc[0]),
        "prazo_efetivo": int(len(tabela_calculada)),
        "total_amortizado": total_amortizado,
        "total_juros": total_juros,
        "total_seguros_taxas": total_seguros,
        "custo_total": total_amortizado + total_juros + total_seguros,
        "custo_com_entrada": total_amortizado + total_juros + total_seguros + entrada,
        "ltv": financiado / valor_imovel if valor_imovel else 0.0,
        "pct_entrada": entrada / valor_imovel if valor_imovel else 0.0,
        "juros_economizados": max(0.0, juros_sem_aporte - total_juros),
        "meses_economizados": max(0, prazo_sem_aporte - int(len(tabela_calculada))),
    }


def por_ano(tabela_calculada: pd.DataFrame) -> pd.DataFrame:
    """Agrupa a tabela por ano de contrato.

    360 linhas nao cabem num grafico legivel; 30 barras sim. Cada barra mostra
    quanto daquele ano foi juro e quanto abateu a divida — e a imagem que
    explica por que os primeiros anos parecem nao andar.
    """
    if tabela_calculada.empty:
        return pd.DataFrame(columns=["ano", "juros", "amortizacao", "seguros",
                                     "desembolso", "saldo_final"])

    agrupado = tabela_calculada.copy()
    agrupado["ano"] = ((agrupado["parcela"] - 1) // 12) + 1
    agrupado["seguros"] = (agrupado["mip"] + agrupado["dfi"] + agrupado["taxa_adm"])
    agrupado["amortizacao_total"] = (
        agrupado["amortizacao"] + agrupado["amortizacao_extra"])

    resultado = (
        agrupado.groupby("ano")
        .agg(
            juros=("juros", "sum"),
            amortizacao=("amortizacao_total", "sum"),
            seguros=("seguros", "sum"),
            desembolso=("desembolso", "sum"),
            saldo_final=("saldo_final", "last"),
        )
        .reset_index()
    )
    return resultado


def salvar_cenario(cenario: dict) -> int:
    """Grava um cenario (novo ou existente, se vier com id)."""
    campos = [
        "nome", "valor_imovel", "valor_entrada", "prazo_meses", "sistema",
        "juros_aa", "conversao_taxa", "seguro_mip_am", "seguro_dfi_am",
        "taxa_adm_mes", "aporte_extra_mes", "aporte_inicio", "aporte_pontual",
        "aporte_pontual_parcela", "efeito_aporte",
    ]
    valores = [cenario.get(campo) for campo in campos]

    if cenario.get("id"):
        atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)
        banco.executar(
            f"UPDATE financiamento_cenarios SET {atribuicoes} WHERE id = ?",
            (*valores, cenario["id"]),
        )
        return int(cenario["id"])

    marcadores = ",".join("?" * len(campos))
    return banco.executar(
        f"INSERT INTO financiamento_cenarios ({','.join(campos)}) VALUES ({marcadores})",
        valores,
    )
