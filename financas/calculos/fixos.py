"""
fixos.py — Gastos fixos: o que voce paga todo mes sem decidir de novo.
==============================================================================

O QUE E UM GASTO FIXO AQUI
--------------------------
Aluguel, faculdade, assinatura, seguro. A caracteristica que importa nao e o
valor ser igual todo mes — e voce NAO decidir de novo a cada mes. Ja decidiu
uma vez, e agora ele vem sozinho.

Isso muda o que fazer com ele: gasto variavel se corta mudando de habito
("vou pedir menos delivery"); gasto fixo so se corta mudando de contrato
(cancelar, renegociar, trocar de plano). Sao esforcos bem diferentes, e por
isso o painel separa os dois.

O RECURSO MAIS UTIL DESTE MODULO
--------------------------------
`comparar_com_real()`. Voce cadastra "conta de luz: R$ ····". Mas quanto
voce REALMENTE pagou de luz nos ultimos 6 meses? Se a media real for R$ ···· o
seu planejamento esta subestimando a conta em R$ ···· por mes — R$ ···· por
ano que voce achava que tinha e nao tem.

A ligacao entre o item cadastrado e os lancamentos reais e feita pela coluna
`chave_historico`: um pedaco de texto que aparece na descricao do lancamento
("LIGHT" para a conta de luz, "ESTACIO" para a faculdade).
"""

from __future__ import annotations

import pandas as pd

from financas import banco, config
from financas.formato import (mes_para_indice, normalizar_texto, somar_meses,
                              vazio)


def cadastro() -> pd.DataFrame:
    """Le o cadastro de gastos fixos com a grande categoria junto."""
    return banco.df(
        """SELECT g.*, c.grande_categoria
           FROM gastos_fixos g
           LEFT JOIN categorias c ON c.nome = g.categoria
           ORDER BY g.ativo DESC, g.valor_mensal DESC"""
    )


def valor_no_mes(item: dict | pd.Series, mes: str) -> float:
    """Valor do item naquele mes, ja com o reajuste anual aplicado.

    Se voce cadastrou "aluguel R$ ···· reajuste 5% ao ano, inicio 2026-01",
    entao em 2027-01 o valor esperado ja e R$ ····

    A conta e juro composto simples:

        valor_final = valor * (1 + reajuste) ^ anos_completos

    Usamos anos COMPLETOS (divisao inteira por 12) porque reajuste de contrato
    acontece de uma vez no aniversario, nao um pouquinho por mes.
    """
    valor = float(item.get("valor_mensal") or 0)
    reajuste = float(item.get("reajuste_aa") or 0)
    inicio = item.get("inicio")

    if reajuste == 0 or vazio(inicio):
        return valor

    indice_inicio = mes_para_indice(str(inicio))
    indice_mes = mes_para_indice(mes)
    if indice_inicio is None or indice_mes is None or indice_mes <= indice_inicio:
        return valor

    anos_completos = (indice_mes - indice_inicio) // 12
    return valor * ((1 + reajuste) ** anos_completos)


def ativos_no_mes(df_cadastro: pd.DataFrame, mes: str) -> pd.DataFrame:
    """So os itens que estao valendo naquele mes.

    Um item vale no mes se:
        - esta marcado como ativo, E
        - ja comecou (inicio <= mes ou inicio em branco), E
        - ainda nao terminou (fim >= mes ou fim em branco)

    O curso de frances, cadastrado de 2026-08 a 2026-12, aparece em setembro
    mas some em janeiro — sem voce precisar lembrar de apagar.
    """
    if df_cadastro.empty:
        return df_cadastro

    indice_mes = mes_para_indice(mes)
    if indice_mes is None:
        return df_cadastro.iloc[0:0]

    def esta_valendo(linha) -> bool:
        if not linha.get("ativo", 1):
            return False
        inicio = linha.get("inicio")
        fim = linha.get("fim")
        if not vazio(inicio):
            indice_inicio = mes_para_indice(str(inicio))
            if indice_inicio is not None and indice_mes < indice_inicio:
                return False
        if not vazio(fim):
            indice_fim = mes_para_indice(str(fim))
            if indice_fim is not None and indice_mes > indice_fim:
                return False
        return True

    selecionados = df_cadastro.apply(esta_valendo, axis=1)
    return df_cadastro[selecionados]


def total_mensal(df_cadastro: pd.DataFrame, mes: str) -> float:
    """Soma dos gastos fixos que valem naquele mes, com reajuste.

    ESTE E O PISO CADASTRADO BRUTO — o que voce anotou, sem perguntar se o
    dinheiro ja saiu ou se a despesa ja esta sendo projetada por outro caminho.
    E o numero certo para a tela de Gastos fixos.

    NAO e o numero que entra na previsao. Para isso existe `situacao_no_mes`,
    que desconta o que ja e parcela do cartao ou ja foi lancado. As duas telas
    mostram valores diferentes DE PROPOSITO, e a diferenca entre elas e sempre
    explicavel item a item.
    """
    valendo = ativos_no_mes(df_cadastro, mes)
    if valendo.empty:
        return 0.0
    return float(sum(valor_no_mes(linha, mes) for _, linha in valendo.iterrows()))


def descricoes_normalizadas(df_lancamentos: pd.DataFrame) -> pd.Series:
    """As descricoes prontas para comparar, calculadas de uma vez so.

    Normalizar texto e a parte cara do casamento, e quem varre 15 itens x 18
    meses faria a mesma passada 270 vezes. Calcule aqui uma vez e passe o
    resultado para `casar_no_historico`.
    """
    if df_lancamentos.empty:
        return pd.Series(dtype="object")
    return df_lancamentos["descricao"].map(normalizar_texto)


def casar_no_historico(df_lancamentos: pd.DataFrame,
                       item: dict | pd.Series,
                       descricoes: pd.Series | None = None) -> pd.Series:
    """Mascara booleana: quais lancamentos sao deste item cadastrado.

    Casa pela `chave_historico` — a chave normalizada tem que estar CONTIDA na
    descricao normalizada. Quando o item tem `categoria_historico` preenchida,
    exige tambem que a categoria bata.

    POR QUE O FILTRO DE CATEGORIA E OPCIONAL. A chave do aluguel e
    "EDUARDO MOREIRA", e existem Pix de Lazer para a mesma pessoa: sem
    filtro, eles entram na conta do aluguel. Mas ligar o filtro por padrao
    quebraria os itens cuja categoria cadastrada NAO e a categoria em que os
    lancamentos caem (o ANTHROPIC esta em Educacao e chega em Outros) — e um
    item que deixa de casar volta a ser contado duas vezes na previsao. Entao o
    filtro e escolha por item, e a tela avisa quando uma chave casa com mais de
    uma categoria.

    Devolve uma Series de False do tamanho certo quando nao ha chave, para quem
    chama poder sempre indexar sem checar antes.
    """
    if df_lancamentos.empty:
        return pd.Series(dtype=bool)

    vazia = pd.Series(False, index=df_lancamentos.index)
    chave = normalizar_texto(item.get("chave_historico"))
    if not chave:
        return vazia

    if descricoes is None:
        descricoes = descricoes_normalizadas(df_lancamentos)
    casaram = descricoes.str.contains(chave, regex=False, na=False)

    categoria = item.get("categoria_historico")
    if not vazio(categoria):
        casaram &= df_lancamentos["categoria"] == str(categoria).strip()
    return casaram


def comparar_com_real(df_cadastro: pd.DataFrame, df_lancamentos: pd.DataFrame,
                      mes: str, janela_meses: int = 6) -> pd.DataFrame:
    """Compara o valor cadastrado com o que voce realmente pagou.

    Para cada item que tem `chave_historico`, procura nos ultimos N meses os
    lancamentos cuja descricao CONTEM aquela chave, e calcula a media mensal.

    Devolve [item, categoria, cadastrado, media_real, diferenca, ocorrencias,
    meses_com_gasto, situacao], onde `situacao` e:

        "sem histórico"  -> nunca apareceu; ou a chave esta errada, ou o gasto
                            nao existe mais
        "acima"          -> voce paga MAIS do que cadastrou (subestimado)
        "abaixo"         -> voce paga MENOS (superestimado, sobra dinheiro)
        "confere"        -> diferenca menor que 10%

    A tolerancia de 10% evita marcar como problema uma conta de luz que varia
    naturalmente de um mes para o outro.

    DUAS MEDIAS, E ELAS RESPONDEM PERGUNTAS DIFERENTES. `media_real` divide
    pela JANELA INTEIRA — um item que apareceu em 3 dos 6 meses pesa metade, e
    e isso que voce quer ao comparar quanto o item custa por mes.
    `media_por_cobranca` divide pelos meses em que ele DE FATO apareceu, e e a
    unica que serve como estimativa: mes sem cobranca costuma ser dado
    faltando, nao custo zero. A conta de luz da R$ ···· pela primeira regua e
    R$ ···· pela segunda; usar a primeira como previsao cortaria a conta pela
    metade.
    """
    colunas = ["item", "categoria", "chave_historico", "cadastrado", "media_real",
               "media_por_cobranca", "diferenca", "diferenca_pct", "ocorrencias",
               "meses_com_gasto", "meses_sem_gasto", "categorias_casadas",
               "situacao"]
    if df_cadastro.empty:
        return pd.DataFrame(columns=colunas)

    mes_inicial = somar_meses(mes, -janela_meses) or mes
    if df_lancamentos.empty:
        janela = df_lancamentos
    else:
        janela = df_lancamentos[
            (df_lancamentos["mes_competencia"] >= mes_inicial)
            & (df_lancamentos["mes_competencia"] < mes)
            & (df_lancamentos["natureza"] == config.NATUREZA_DESPESA)
        ]

    meses_da_janela = sorted(
        str(m) for m in janela["mes_competencia"].dropna().unique()
    ) if not janela.empty else []
    descricoes = descricoes_normalizadas(janela)

    linhas = []
    for _, item in df_cadastro.iterrows():
        cadastrado = valor_no_mes(item, mes)
        chave = item.get("chave_historico")

        if vazio(chave) or janela.empty:
            linhas.append({
                "item": item["item"], "categoria": item.get("categoria"),
                "chave_historico": chave, "cadastrado": cadastrado,
                "media_real": 0.0, "media_por_cobranca": 0.0, "diferenca": 0.0,
                "diferenca_pct": 0.0, "ocorrencias": 0, "meses_com_gasto": 0,
                "meses_sem_gasto": meses_da_janela, "categorias_casadas": [],
                "situacao": "sem histórico",
            })
            continue

        casaram = janela[casar_no_historico(janela, item, descricoes)]

        if casaram.empty:
            media_real = 0.0
            media_por_cobranca = 0.0
            meses_com_gasto = 0
            meses_presentes: list[str] = []
            categorias_casadas: list[str] = []
        else:
            total = float(-casaram["valor"].sum())
            meses_presentes = sorted(
                str(m) for m in casaram["mes_competencia"].dropna().unique())
            meses_com_gasto = len(meses_presentes)
            media_real = total / janela_meses
            media_por_cobranca = total / meses_com_gasto
            categorias_casadas = sorted(
                str(c) for c in casaram["categoria"].dropna().unique())

        diferenca = media_real - cadastrado
        pct = diferenca / cadastrado if cadastrado else 0.0

        if meses_com_gasto == 0:
            situacao = "sem histórico"
        elif abs(pct) <= 0.10:
            situacao = "confere"
        elif pct > 0:
            situacao = "acima"
        else:
            situacao = "abaixo"

        linhas.append({
            "item": item["item"], "categoria": item.get("categoria"),
            "chave_historico": chave, "cadastrado": cadastrado,
            "media_real": media_real, "media_por_cobranca": media_por_cobranca,
            "diferenca": diferenca, "diferenca_pct": pct,
            "ocorrencias": int(len(casaram)),
            "meses_com_gasto": meses_com_gasto,
            "meses_sem_gasto": [m for m in meses_da_janela
                                if m not in meses_presentes],
            "categorias_casadas": categorias_casadas,
            "situacao": situacao,
        })

    resultado = pd.DataFrame(linhas, columns=colunas)
    return resultado.sort_values("diferenca", key=abs, ascending=False)


def janela_fechada(mes_base: str, janela_meses: int = 6) -> tuple[str, str]:
    """O primeiro e o ultimo mes da janela de meses JA FECHADOS.

    O mes em andamento esta pela metade: incluir ele numa media puxa o numero
    para baixo so porque o mes ainda nao acabou. Esta e a mesma janela que
    `planejamento.projecao_caixa` usa, e as duas precisam concordar — medir a
    receita com uma regua e a despesa com outra ja enviesou a projecao uma vez.
    """
    from financas import dados

    ultimo = mes_base
    if dados.mes_esta_em_andamento(mes_base):
        ultimo = somar_meses(mes_base, -1) or mes_base
    primeiro = somar_meses(ultimo, -(janela_meses - 1)) or ultimo
    return primeiro, ultimo


def situacao_no_mes(df_cadastro: pd.DataFrame, df_lancamentos: pd.DataFrame,
                    mes: str, mes_base: str | None = None,
                    janela_meses: int = 6) -> pd.DataFrame:
    """Quanto cada gasto fixo entra na previsao daquele mes, e por que.

    Um gasto fixo pode chegar a previsao por tres caminhos, e SO UM deve valer,
    senao a mesma despesa conta duas vezes:

        1. ja foi lancado no mes      (a fatura chegou, o Pix saiu)
        2. ja e parcela projetada     (`parcelas.grade_futura` cuida dele)
        3. o cadastro                 (a estimativa, quando 1 e 2 nao cobrem)

    A PRECEDENCIA, e o motivo de cada linha:

        considerar_previsao = 0   -> 'desligado'  voce tirou da conta
        nao vale neste mes        -> 'fora'       inicio/fim
        casa uma parcela prevista -> 'parcela'    a grade ja projeta isso
        ja tem lancamento no mes  -> 'lançado'    o real vale mais que a estimativa
        senao                     -> 'previsto'   ainda vai cair

    A parcela vence o cadastro porque a parcela e FATO CONTRATADO e o cadastro
    e estimativa. Quando os dois descrevem a mesma despesa, o fato manda. E
    tirar o lado do cadastro (em vez de tirar a parcela da grade) e a unica
    ordem que mantem `parcelas_cartao` igual a `parcelas.grade_futura`, como
    `conferir_competencia` exige.

    DUAS COLUNAS DE VALOR, E ELAS NAO SAO A MESMA PERGUNTA:

        entra_na_previsao   o que `projecao_caixa` soma — "quanto este item
                            custa neste mes". Item ja lancado devolve o valor
                            LANCADO, nao zero: `projecao_caixa` nao conta
                            despesa ja lancada de mes futuro, entao zerar aqui
                            faria a mensalidade que voce ja lancou ate dezembro
                            sumir da projecao.
        falta_no_mes        o que `previsao.do_mes` soma — "quanto ainda vai
                            sair". Item ja lancado devolve zero: ja saiu.

    `mes_base` e o mes de onde se olha, e serve para perguntar as parcelas o
    que ainda nao foi faturado a partir dali. Sem ele, usa o mes corrente.
    """
    from financas import dados
    from financas.calculos import parcelas

    colunas = ["id", "item", "categoria", "grande_categoria", "forma_pagamento",
               "cadastrado", "media_por_cobranca", "esperado", "lancado",
               "parcela_prevista", "entra_na_previsao", "falta_no_mes",
               "situacao", "motivo"]
    if df_cadastro.empty:
        return pd.DataFrame(columns=colunas)

    if mes_base is None:
        mes_base = dados.mes_corrente()

    valendo = set(ativos_no_mes(df_cadastro, mes).index)

    do_mes = (df_lancamentos[df_lancamentos["mes_competencia"] == mes]
              if not df_lancamentos.empty else df_lancamentos)
    gastos_do_mes = dados.despesas(do_mes) if not do_mes.empty else do_mes
    descricoes_mes = descricoes_normalizadas(gastos_do_mes)

    inicio, fim = janela_fechada(mes_base, janela_meses)
    if df_lancamentos.empty:
        historico = df_lancamentos
    else:
        historico = dados.despesas(df_lancamentos[
            (df_lancamentos["mes_competencia"] >= inicio)
            & (df_lancamentos["mes_competencia"] <= fim)
        ])
    descricoes_hist = descricoes_normalizadas(historico)

    n_meses = max(1, (mes_para_indice(mes) or 0) - (mes_para_indice(mes_base) or 0))
    futuras = parcelas.detalhe_futuro(df_lancamentos, mes_base, n_meses)
    do_mes_parcelas = (futuras[futuras["mes"] == mes]
                       if not futuras.empty else futuras)
    descricoes_parcelas = descricoes_normalizadas(do_mes_parcelas)

    linhas = []
    for indice, item in df_cadastro.iterrows():
        cadastrado = valor_no_mes(item, mes)

        casaram_hist = (historico[casar_no_historico(historico, item,
                                                     descricoes_hist)]
                        if not historico.empty else historico)
        if casaram_hist.empty:
            media_por_cobranca = 0.0
        else:
            media_por_cobranca = (
                float(-casaram_hist["valor"].sum())
                / int(casaram_hist["mes_competencia"].nunique()))

        cobrancas = (int(casaram_hist["mes_competencia"].nunique())
                     if not casaram_hist.empty else 0)
        usa_media = (str(item.get("base_valor") or config.BASE_CADASTRADO)
                     == config.BASE_MEDIA and cobrancas >= 2)
        esperado = media_por_cobranca if usa_media else cadastrado

        lancado = 0.0
        if not gastos_do_mes.empty:
            casaram_mes = gastos_do_mes[
                casar_no_historico(gastos_do_mes, item, descricoes_mes)]
            lancado = float(-casaram_mes["valor"].sum())

        parcela_prevista = 0.0
        if not do_mes_parcelas.empty:
            casaram_parcela = do_mes_parcelas[
                casar_no_historico(do_mes_parcelas, item, descricoes_parcelas)]
            parcela_prevista = float(casaram_parcela["valor"].sum())

        if not item.get("considerar_previsao", 1):
            situacao = config.SITUACAO_DESLIGADO
            entra, falta = 0.0, 0.0
            motivo = "você tirou este item da previsão"
        elif indice not in valendo:
            situacao = config.SITUACAO_FORA
            entra, falta = 0.0, 0.0
            motivo = "não vale neste mês (início/fim)"
        elif parcela_prevista > 0.01:
            situacao = config.SITUACAO_PARCELA
            entra, falta = 0.0, 0.0
            motivo = (f"já está nas parcelas do cartão "
                      f"(R$ {parcela_prevista:,.2f})")
        elif lancado > 0.01:
            situacao = config.SITUACAO_LANCADO
            entra, falta = lancado, 0.0
            motivo = f"já foi lançado neste mês (R$ {lancado:,.2f})"
        else:
            situacao = config.SITUACAO_PREVISTO
            entra, falta = esperado, esperado
            motivo = ("média das últimas cobranças" if usa_media
                      else "valor cadastrado")

        linhas.append({
            "id": item.get("id"), "item": item["item"],
            "categoria": item.get("categoria"),
            "grande_categoria": item.get("grande_categoria"),
            "forma_pagamento": (item.get("forma_pagamento")
                                or config.FORMA_CONTA),
            "cadastrado": cadastrado, "media_por_cobranca": media_por_cobranca,
            "esperado": esperado, "lancado": lancado,
            "parcela_prevista": parcela_prevista,
            "entra_na_previsao": entra, "falta_no_mes": falta,
            "situacao": situacao, "motivo": motivo,
        })

    return pd.DataFrame(linhas, columns=colunas)


def por_grande_categoria(df_cadastro: pd.DataFrame, mes: str) -> pd.DataFrame:
    """Total de gasto fixo por grande categoria naquele mes."""
    valendo = ativos_no_mes(df_cadastro, mes)
    if valendo.empty:
        return pd.DataFrame(columns=["grande_categoria", "total", "quantidade",
                                     "percentual"])

    valendo = valendo.copy()
    valendo["valor_ajustado"] = [valor_no_mes(l, mes) for _, l in valendo.iterrows()]
    valendo["grande_categoria"] = valendo["grande_categoria"].fillna("Outros")

    agrupado = (
        valendo.groupby("grande_categoria")
        .agg(total=("valor_ajustado", "sum"), quantidade=("item", "size"))
        .reset_index()
        .sort_values("total", ascending=False)
    )
    soma = agrupado["total"].sum()
    agrupado["percentual"] = agrupado["total"] / soma if soma else 0.0
    return agrupado


def indicadores(df_cadastro: pd.DataFrame, df_lancamentos: pd.DataFrame,
                mes: str, receita_do_mes: float = 0.0) -> dict:
    """Os numeros de gasto fixo que aparecem no Dashboard.

    Devolve:
        cadastrado         soma do que esta cadastrado e valendo neste mes
        realizado          o que de fato foi lancado como Fixo neste mes
        n_itens            quantos itens estao valendo
        pct_da_receita     quanto da receita do mes ja esta comprometido
        diferenca          realizado - cadastrado
    """
    from financas import dados

    cadastrado = total_mensal(df_cadastro, mes)
    do_mes = dados.do_mes(df_lancamentos, mes)
    gastos = dados.despesas(do_mes)
    realizado = (
        float(-gastos[gastos["tipo"] == config.TIPO_FIXO]["valor"].sum())
        if not gastos.empty else 0.0
    )

    return {
        "cadastrado": cadastrado,
        "realizado": realizado,
        "n_itens": int(len(ativos_no_mes(df_cadastro, mes))),
        "pct_da_receita": cadastrado / receita_do_mes if receita_do_mes else 0.0,
        "diferenca": realizado - cadastrado,
    }


def projecao(df_cadastro: pd.DataFrame, mes_base: str,
             n_meses: int = 18) -> pd.DataFrame:
    """Quanto de gasto fixo cai em cada mes a frente.

    Leva em conta inicio, fim e reajuste de cada item — entao a projecao ja
    mostra o degrau de quando um curso acaba ou um contrato reajusta.
    """
    linhas = []
    for passo in range(n_meses):
        mes = somar_meses(mes_base, passo)
        if not mes:
            break
        linhas.append({
            "mes": mes,
            "total": total_mensal(df_cadastro, mes),
            "quantidade": int(len(ativos_no_mes(df_cadastro, mes))),
        })
    return pd.DataFrame(linhas, columns=["mes", "total", "quantidade"])
