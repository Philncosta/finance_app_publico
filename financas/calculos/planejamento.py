"""
planejamento.py — Orcamento, simulacao de cenarios e projecao de caixa.
==============================================================================

TRES PERGUNTAS, TRES FUNCOES
----------------------------
    orcado_vs_real()   "Estou dentro do que planejei para este mes?"
    simular()          "E se eu cortasse 20% de Comida? Quanto sobraria?"
    projecao_caixa()   "Com o que ja sei hoje, como fica meu saldo em 18 meses?"

SOBRE A PROJECAO DE CAIXA
-------------------------
Ela nao adivinha nada. Monta o mes futuro somando quatro coisas que ja sao
conhecidas hoje:

    + salario previsto        (voce informa; ou usa a media recente)
    - gastos fixos            (do cadastro, com inicio/fim/reajuste)
    - parcelas do cartao      (as ja contratadas, de calculos/parcelas.py)
    - outras variaveis        (a media dos ultimos 6 meses)

O unico chute e a ultima linha, e mesmo ela e a sua propria media. Isso e de
proposito: uma projecao que se apoia em suposicao otimista nao serve para
decidir nada.
"""

from __future__ import annotations

import pandas as pd

from financas import banco, config, dados
from financas.calculos import fixos, parcelas
from financas.formato import normalizar_texto, somar_meses, vazio


def orcamento_do_mes(mes: str) -> dict[str, float]:
    """Le a meta de gasto de cada grande categoria naquele mes.

    Se o mes nao tem orcamento proprio, herda o do mes mais recente que tiver.
    Assim voce define uma vez e vale para os meses seguintes, sem precisar
    recadastrar tudo todo mes.
    """
    linhas = banco.consultar(
        "SELECT grande_categoria, valor_orcado FROM orcamento WHERE mes = ?", (mes,)
    )
    if linhas:
        return {l["grande_categoria"]: l["valor_orcado"] for l in linhas}

    referencia = banco.consultar_um(
        "SELECT MAX(mes) AS m FROM orcamento WHERE mes <= ?", (mes,)
    )

    if not referencia or not referencia["m"]:
        referencia = banco.consultar_um("SELECT MIN(mes) AS m FROM orcamento")
    if not referencia or not referencia["m"]:
        return {}

    linhas = banco.consultar(
        "SELECT grande_categoria, valor_orcado FROM orcamento WHERE mes = ?",
        (referencia["m"],),
    )
    return {l["grande_categoria"]: l["valor_orcado"] for l in linhas}


def orcado_vs_real(df: pd.DataFrame, mes: str) -> pd.DataFrame:
    """Compara o gasto real com a meta, por grande categoria.

    Devolve [grande_categoria, orcado, real, diferenca, pct_usado, situacao].

    `diferenca` positiva = sobrou do orcamento. Negativa = estourou.
    `situacao` classifica em "ok" (ate 80%), "atenção" (80-100%) e
    "estourou" (acima de 100%) — as faixas que a barra colorida usa na tela.

    Inclui TODAS as grandes categorias que aparecem em qualquer um dos dois
    lados: as que tem meta mas nao tiveram gasto (sobra integral) e as que
    tiveram gasto sem meta cadastrada (aparecem com meta zero, para nao
    ficarem invisiveis).
    """
    colunas = ["grande_categoria", "orcado", "real", "diferenca", "pct_usado",
               "situacao"]

    metas = orcamento_do_mes(mes)
    real = dados.por_categoria(dados.do_mes(df, mes), "grande_categoria")
    gastos = dict(zip(real["grande_categoria"], real["total"])) if not real.empty else {}

    todas = sorted(set(metas) | set(gastos))
    if not todas:
        return pd.DataFrame(columns=colunas)

    linhas = []
    for grande_categoria in todas:
        orcado = float(metas.get(grande_categoria, 0.0))
        gasto = float(gastos.get(grande_categoria, 0.0))
        pct = gasto / orcado if orcado else 0.0

        if not orcado:
            situacao = "sem meta"
        elif pct > 1.0:
            situacao = "estourou"
        elif pct >= 0.8:
            situacao = "atenção"
        else:
            situacao = "ok"

        linhas.append({
            "grande_categoria": grande_categoria,
            "orcado": orcado,
            "real": gasto,
            "diferenca": orcado - gasto,
            "pct_usado": pct,
            "situacao": situacao,
        })

    return pd.DataFrame(linhas, columns=colunas).sort_values("real", ascending=False)


def salvar_orcamento(mes: str, valores: dict[str, float]) -> int:
    """Grava a meta de cada grande categoria para um mes."""
    return banco.executar_muitos(
        "INSERT OR REPLACE INTO orcamento (mes, grande_categoria, valor_orcado) "
        "VALUES (?,?,?)",
        [(mes, categoria, float(valor)) for categoria, valor in valores.items()],
    )


def media_por_grande_categoria(df: pd.DataFrame, mes: str,
                               janela_meses: int = 6) -> pd.DataFrame:
    """Gasto medio mensal de cada grande categoria nos ultimos N meses.

    E a base do simulador: para responder "e se eu cortasse 20%?", primeiro
    precisamos saber quanto e o 100%.

    Assim como em fixos.py, dividimos pela JANELA INTEIRA e nao pelos meses em
    que houve gasto — um gasto esporadico deve pesar menos na media mensal.
    """
    mes_inicial = somar_meses(mes, -janela_meses) or mes
    if df.empty:
        return pd.DataFrame(columns=["grande_categoria", "media_mensal"])

    janela = df[
        (df["mes_competencia"] >= mes_inicial)
        & (df["mes_competencia"] < mes)
    ]
    gastos = dados.despesas(janela)
    if gastos.empty:
        return pd.DataFrame(columns=["grande_categoria", "media_mensal"])

    agrupado = (
        gastos.groupby("grande_categoria")["valor"]
        .sum().mul(-1).div(janela_meses)
        .reset_index()
        .rename(columns={"valor": "media_mensal"})
        .sort_values("media_mensal", ascending=False)
    )
    return agrupado


def simular(df: pd.DataFrame, mes: str, ajustes: dict[str, float],
            receita_prevista: float, janela_meses: int = 6) -> dict:
    """Aplica cortes/aumentos percentuais e mostra o resultado.

    `ajustes` e {grande_categoria: variacao}, onde a variacao e FRACAO:
        -0.20  corta 20%
         0.10  aumenta 10%
         0      mantem

    Devolve {tabela, total_atual, total_simulado, economia, saldo_atual,
    saldo_simulado}. A tabela tem uma linha por grande categoria, com o gasto
    medio atual, o ajuste, o simulado e a economia.
    """
    base = media_por_grande_categoria(df, mes, janela_meses)
    if base.empty:
        return {
            "tabela": pd.DataFrame(columns=["grande_categoria", "media_mensal",
                                            "ajuste", "simulado", "economia"]),
            "total_atual": 0.0, "total_simulado": 0.0, "economia": 0.0,
            "saldo_atual": receita_prevista, "saldo_simulado": receita_prevista,
        }

    tabela = base.copy()
    tabela["ajuste"] = tabela["grande_categoria"].map(
        lambda categoria: float(ajustes.get(categoria, 0.0))
    )
    tabela["simulado"] = tabela["media_mensal"] * (1 + tabela["ajuste"])
    tabela["economia"] = tabela["media_mensal"] - tabela["simulado"]

    total_atual = float(tabela["media_mensal"].sum())
    total_simulado = float(tabela["simulado"].sum())

    return {
        "tabela": tabela,
        "total_atual": total_atual,
        "total_simulado": total_simulado,
        "economia": total_atual - total_simulado,
        "saldo_atual": receita_prevista - total_atual,
        "saldo_simulado": receita_prevista - total_simulado,
    }


def e_de_item_fixo(df_lancamentos: pd.DataFrame,
                   df_cadastro: pd.DataFrame) -> pd.Series:
    """Mascara: quais lancamentos pertencem a algum gasto fixo ATIVO.

    POR QUE ISTO EXISTE. A base da media de variaveis excluia so quem tem
    `tipo = 'Fixo'` no lancamento. Mas `tipo` vem da regra de importacao, e um
    item pode estar cadastrado como gasto fixo enquanto seus lancamentos
    continuam chegando marcados 'Variável' — foi o caso do estacionamento, do
    ANTHROPIC e dos suplementos. Nesses casos o mesmo gasto entrava nos DOIS
    lados da previsao: no cadastro de fixos e na media de variaveis.

    O cadastro e a fonte de verdade sobre o que e fixo; `tipo` e so uma pista.
    """
    if df_lancamentos.empty:
        return pd.Series(dtype=bool)

    marcados = pd.Series(False, index=df_lancamentos.index)
    if df_cadastro.empty:
        return marcados

    descricoes = fixos.descricoes_normalizadas(df_lancamentos)
    ativos = df_cadastro[df_cadastro["ativo"].fillna(1).astype(bool)]
    for _, item in ativos.iterrows():
        marcados |= fixos.casar_no_historico(df_lancamentos, item, descricoes)
    return marcados


def projecao_caixa(df: pd.DataFrame, mes_base: str, n_meses: int = 18,
                   salario_previsto: float | None = None,
                   saldo_inicial: float = 0.0,
                   janela_meses: int = 6,
                   incluir_planejados: bool = False) -> pd.DataFrame:
    """Monta o fluxo de caixa dos proximos N meses.

    Colunas devolvidas:
        mes, receita_prevista, fixos, fixos_conta, fixos_cartao,
        parcelas_cartao, outras_variaveis, gastos_planejados, total_despesas,
        saldo_mes, saldo_acumulado

    `fixos_conta` e `fixos_cartao` sao DECOMPOSICAO de `fixos`, nao
    substituicao: `fixos` continua sendo a soma dos dois, e `total_despesas`
    continua sendo `fixos + parcelas_cartao + outras_variaveis`. Separar os
    dois responde "quanto da minha fatura ja esta vendida antes de eu comprar
    qualquer coisa" — que e a pergunta de quem quer fazer sobrar salario.

    De onde vem cada parte:
        receita_prevista  o salario que voce informou (ou a media de receita
                          recorrente dos ultimos meses, se nao informou) MAIS
                          receitas ja lancadas naquele mes futuro (como o
                          rateio do PLR, que ja esta no banco ate dezembro)
        fixos             cadastro de gastos fixos, respeitando inicio/fim, JA
                          SEM o que a grade de parcelas projeta por outro
                          caminho — ver `fixos.situacao_no_mes`
        parcelas_cartao   parcelas ja contratadas (calculos/parcelas.py), no
                          mes da competencia, sem deslocar +1 mes: a receita e
                          o gasto do mesmo ciclo ja caem no mesmo balde, e a
                          fatura e paga poucos dias depois com dinheiro que ja
                          entrou. Empurrar para o mes do vencimento recriaria
                          o desalinhamento que a migracao 13 corrigiu.
        outras_variaveis  media dos ultimos 6 meses do que NAO e fixo e NAO e
                          parcela — para nao contar a mesma coisa duas vezes
        gastos_planejados viagem, mobilia, compra grande — o que voce marcou
                          com data. So entra na conta se `incluir_planejados`
                          for True; a coluna aparece sempre, para a tela poder
                          mostrar o que ESTA sendo ignorado.

    SOBRE `incluir_planejados` VIR DESLIGADO
    ----------------------------------------
    Ligado, ele muda o `saldo_acumulado` — um numero que ja e olhado hoje.
    Mudar isso por baixo seria trocar o significado de um numero sem avisar,
    entao a tela oferece o botao e a diferenca fica visivel. Ver
    `gastos_planejados()`.
    """
    colunas = ["mes", "receita_prevista", "fixos", "fixos_conta",
               "fixos_cartao", "parcelas_cartao", "outras_variaveis",
               "gastos_planejados", "total_despesas", "saldo_mes",
               "saldo_acumulado"]

    cadastro_fixos = fixos.cadastro()

    if salario_previsto is None:
        salario_previsto = banco.obter_parametro_num("salario_previsto", 0.0)
    if not salario_previsto:
        serie = dados.por_mes(df)
        if not serie.empty:
            reais = dados.meses_fechados(serie)
            reais = reais[reais["mes"] <= mes_base].tail(janela_meses)
            if not reais.empty:
                salario_previsto = float(
                    (reais["receita"] - reais["receita_extra"]).median())

    ultimo_fechado = mes_base
    if dados.mes_esta_em_andamento(mes_base):
        ultimo_fechado = somar_meses(mes_base, -1) or mes_base
    mes_inicial = somar_meses(ultimo_fechado, -(janela_meses - 1)) or ultimo_fechado

    outras_media = 0.0
    if not df.empty:
        janela = df[
            (df["mes_competencia"] >= mes_inicial)
            & (df["mes_competencia"] <= ultimo_fechado)
        ]
        gastos = dados.despesas(janela)
        if not gastos.empty:
            variaveis_avulsas = gastos[
                (gastos["tipo"] != config.TIPO_FIXO)
                & (~gastos["e_parcelado"])
                & (~e_de_item_fixo(gastos, cadastro_fixos))
            ]
            if not variaveis_avulsas.empty:
                por_mes_variavel = (
                    variaveis_avulsas.groupby("mes_competencia")["valor"].sum().mul(-1)
                )
                outras_media = float(por_mes_variavel.median())

    receitas_lancadas = {}
    if not df.empty:
        futuras = dados.receitas(df[df["mes_competencia"] > mes_base])
        if not futuras.empty:
            receitas_lancadas = (
                futuras.groupby("mes_competencia")["valor"].sum().to_dict())

    grade_parcelas = parcelas.grade_futura(df, mes_base, n_meses)
    parcelas_por_mes = dict(zip(grade_parcelas["mes"], grade_parcelas["total"]))

    planejados_por_mes = total_planejado_por_mes(mes_base, n_meses)

    linhas = []
    acumulado = saldo_inicial
    for passo in range(1, n_meses + 1):
        mes = somar_meses(mes_base, passo)
        if not mes:
            break

        receita = float(salario_previsto or 0.0) + float(receitas_lancadas.get(mes, 0.0))
        situacao = fixos.situacao_no_mes(cadastro_fixos, df, mes, mes_base,
                                         janela_meses)
        if situacao.empty:
            fixos_conta = fixos_cartao = 0.0
        else:
            do_cartao = situacao["forma_pagamento"] == config.FORMA_CARTAO
            fixos_cartao = float(situacao[do_cartao]["entra_na_previsao"].sum())
            fixos_conta = float(situacao[~do_cartao]["entra_na_previsao"].sum())
        total_fixos = fixos_conta + fixos_cartao
        total_parcelas = float(parcelas_por_mes.get(mes, 0.0))
        planejado = float(planejados_por_mes.get(mes, 0.0))
        total_despesas = total_fixos + total_parcelas + outras_media
        if incluir_planejados:
            total_despesas += planejado
        saldo_mes = receita - total_despesas
        acumulado += saldo_mes

        linhas.append({
            "mes": mes,
            "receita_prevista": receita,
            "fixos": total_fixos,
            "fixos_conta": fixos_conta,
            "fixos_cartao": fixos_cartao,
            "parcelas_cartao": total_parcelas,
            "outras_variaveis": outras_media,
            "gastos_planejados": planejado,
            "total_despesas": total_despesas,
            "saldo_mes": saldo_mes,
            "saldo_acumulado": acumulado,
        })

    return pd.DataFrame(linhas, columns=colunas)


def gastos_planejados(mes_base: str, n_meses: int = 18) -> pd.DataFrame:
    """Gasto pontual que voce JA planejou e que cai dentro da janela.

    Colunas: mes, descricao, valor, origem

    POR QUE ISTO PRECISA EXISTIR
    ----------------------------
    `projecao_caixa` le gasto fixo, parcela de cartao e media de variaveis —
    tudo que se REPETE. Mas o que quebra um caixa nao e o que se repete, e o
    que cai de uma vez: uma viagem, mobiliar uma casa, trocar o carro.

    Sem isto, uma viagem de R$ ···· marcada para marco/2027 existe como meta
    na tela de Metas e a projecao continua mostrando marco/2027 confortavel. O
    app deixava planejar o gasto e depois escondia o gasto.

    DUAS FONTES, E O CUIDADO COM A DUPLA CONTAGEM
    ---------------------------------------------
      metas             tipo "Compra à vista", com prazo. Falta o que ainda
                        nao foi acumulado: `valor_alvo - ja_acumulado`.
      futuras_compras   com `mes_alvo` preenchido, agrupadas por `projeto`.

    `promover_para_meta()` cria uma meta E DEIXA o item na lista de compras —
    entao os dois lados podem descrever a mesma coisa. A meta vence, e a
    compra de mesmo nome e descartada. O casamento e por nome normalizado,
    porque e exatamente o campo que a promocao copia.

    Nao entram: metas de Reserva, Acumular e Financiamento. Elas sao plano de
    POUPANCA, que se espalha por muitos meses — trata-las como despesa de um
    mes so inventaria um rombo que nao existe.
    """
    colunas = ["mes", "descricao", "valor", "origem"]
    if not mes_base:
        return pd.DataFrame(columns=colunas)

    janela = {somar_meses(mes_base, passo) for passo in range(1, n_meses + 1)}
    janela.discard(None)
    if not janela:
        return pd.DataFrame(columns=colunas)

    linhas = []
    nomes_de_meta = set()

    for meta in banco.consultar(
            """SELECT meta, valor_alvo, ja_acumulado, prazo FROM metas
                WHERE tipo = 'Compra à vista' AND status = 'Ativa'
                  AND prazo IS NOT NULL"""):
        nomes_de_meta.add(normalizar_texto(meta["meta"] or ""))
        if meta["prazo"] not in janela:
            continue
        falta = float(meta["valor_alvo"] or 0) - float(meta["ja_acumulado"] or 0)
        if falta > 0:
            linhas.append({"mes": meta["prazo"], "descricao": meta["meta"],
                           "valor": falta, "origem": "meta"})

    for compra in banco.consultar(
            """SELECT item, projeto, mes_alvo, preco_alvo, preco_atual, status
                 FROM futuras_compras
                WHERE mes_alvo IS NOT NULL AND TRIM(mes_alvo) <> ''
                  AND COALESCE(status, '') NOT IN ('Comprado', 'Descartado')"""):
        if compra["mes_alvo"] not in janela:
            continue
        if normalizar_texto(compra["item"] or "") in nomes_de_meta:
            continue
        precos = [float(p) for p in (compra["preco_alvo"], compra["preco_atual"])
                  if not vazio(p) and float(p) > 0]
        if not precos:
            continue
        projeto = (compra["projeto"] or "").strip()
        linhas.append({
            "mes": compra["mes_alvo"],
            "descricao": f"{projeto} · {compra['item']}" if projeto
                         else compra["item"],
            "valor": min(precos),
            "origem": f"projeto: {projeto}" if projeto else "compra futura",
        })

    return pd.DataFrame(linhas, columns=colunas).sort_values(["mes", "descricao"])


def total_planejado_por_mes(mes_base: str, n_meses: int = 18) -> dict[str, float]:
    """O mesmo de `gastos_planejados`, somado por mes."""
    tabela = gastos_planejados(mes_base, n_meses)
    if tabela.empty:
        return {}
    return {str(mes): float(grupo["valor"].sum())
            for mes, grupo in tabela.groupby("mes")}


def alertas_da_projecao(df_projecao: pd.DataFrame) -> list[str]:
    """Le a projecao e escreve os avisos importantes em portugues claro.

    Um numero numa tabela e facil de nao ver. Uma frase dizendo "em marco o
    seu saldo fica negativo" e dificil de ignorar — e o objetivo do painel e
    que voce nao seja pego de surpresa.
    """
    if df_projecao.empty:
        return []

    from financas.formato import fmt_brl_md, rotulo_mes

    avisos = []

    negativos = df_projecao[df_projecao["saldo_mes"] < 0]
    if not negativos.empty:
        primeiro = negativos.iloc[0]
        avisos.append(
            f"Em {rotulo_mes(primeiro['mes'])} as despesas previstas passam a "
            f"receita em {fmt_brl_md(abs(primeiro['saldo_mes']))}."
        )

    acumulado_negativo = df_projecao[df_projecao["saldo_acumulado"] < 0]
    if not acumulado_negativo.empty:
        primeiro = acumulado_negativo.iloc[0]
        avisos.append(
            f"O saldo acumulado fica negativo a partir de "
            f"{rotulo_mes(primeiro['mes'])}."
        )

    parcelas_serie = df_projecao["parcelas_cartao"]
    if len(parcelas_serie) > 1 and parcelas_serie.iloc[0] > 0:
        zerou = df_projecao[df_projecao["parcelas_cartao"] < 0.01]
        if not zerou.empty:
            mes_livre = zerou.iloc[0]
            avisos.append(
                f"A partir de {rotulo_mes(mes_livre['mes'])} não há mais "
                f"parcela de cartão contratada — sobram "
                f"{fmt_brl_md(parcelas_serie.iloc[0])} por mês em relação a hoje."
            )

    return avisos
