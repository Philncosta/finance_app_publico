"""
parcelas.py — Projeta as parcelas do cartao que ainda vao chegar.
==============================================================================

O PROBLEMA
----------
Voce comprou uma passagem em 10x em novembro. Ate agosto ja foram 9 parcelas.
A decima ainda vai vir — e ela ja esta contratada, voce nao tem escolha. Se o
painel so mostra o que ja foi faturado, ele esconde a parte da conta que ja
esta comprometida.

Esta e a informacao mais util do painel inteiro: quanto do seu proximo mes ja
esta vendido antes de voce gastar qualquer coisa.

COMO A PROJECAO FUNCIONA
------------------------
Cada compra parcelada tem uma `chave_parcelamento` que junta todas as suas
parcelas (foi montada na importacao — veja migracao/carregar.py). Para cada
chave, olhamos:

    parcela_total          quantas parcelas a compra tem no total  (ex: 10)
    ultima_faturada        a maior parcela que ja apareceu         (ex:  9)
    mes_da_ultima          em que mes ela apareceu                 (2026-08)
    valor_da_parcela       quanto custa cada uma                   (R$ ····)

Dai:

    parcelas_restantes  = 10 - 9 = 1
    total_a_vencer      = 1 x R$ ····
    e ela cai em          2026-08 + 1 = 2026-09

Repetindo isso para os 58 parcelamentos e somando por mes, sai a grade de
"quanto ja esta comprometido em cada mes a frente".

UM CUIDADO IMPORTANTE
---------------------
So projetamos parcelas do CARTAO (origem = Fatura). Compromissos futuros que
voce lancou a mao (como as mensalidades dos cursos, ja registradas ate
dezembro) sao lancamentos de verdade e ja estao no banco — se projetassemos
esses tambem, o mes contaria duas vezes.
"""

from __future__ import annotations

import pandas as pd

from financas import config, dados
from financas.formato import indice_para_mes, mes_para_indice


_MEMORIA: dict[tuple, pd.DataFrame] = {}
_MEMORIA_MAX = 4


def _impressao_digital(df: pd.DataFrame) -> tuple | None:
    """Assinatura barata do conteudo do DataFrame. None quando nao da para tirar."""
    try:
        return (len(df), float(df["valor"].sum()),
                int(df["parcela_total"].sum()), str(df["data"].max()))
    except (KeyError, TypeError, ValueError):
        return None


def limpar_memoria() -> None:
    """Esquece os parcelamentos guardados. Use depois de alterar lancamentos."""
    _MEMORIA.clear()


def parcelamentos(df: pd.DataFrame) -> pd.DataFrame:
    """Resume cada compra parcelada do cartao numa linha.

    Devolve um DataFrame com uma linha por parcelamento e as colunas:
        chave, descricao, categoria, grande_categoria, tipo,
        parcela_total, ultima_faturada, mes_ultima, mes_origem,
        valor_parcela, parcelas_restantes, total_a_vencer, mes_termino
    """
    colunas = ["chave", "descricao", "categoria", "grande_categoria", "tipo",
               "parcela_total", "ultima_faturada", "mes_ultima", "mes_origem",
               "valor_parcela", "parcelas_restantes", "total_a_vencer",
               "mes_termino"]
    if df.empty:
        return pd.DataFrame(columns=colunas)

    chave = _impressao_digital(df)
    if chave is not None and chave in _MEMORIA:
        return _MEMORIA[chave].copy()

    parceladas = df[
        (df["origem"] == config.ORIGEM_FATURA)
        & df["chave_parcelamento"].notna()
        & (df["parcela_total"] > 1)
    ]
    if parceladas.empty:
        return pd.DataFrame(columns=colunas)

    ordenadas = parceladas.sort_values(
        ["chave_parcelamento", "data", "parcela_atual"])
    ultimas = ordenadas.groupby(
        ["chave_parcelamento", "data"], as_index=False).tail(1)

    creditos = df[(df["origem"] == config.ORIGEM_FATURA) & (df["valor"] > 0)]
    estornos = set()
    if not creditos.empty:
        estornos = {
            (linha["descricao"], linha["mes_competencia"],
             int(round(abs(linha["valor"]) * 100)))
            for _, linha in creditos.iterrows()
        }

    linhas = []
    for _, parcela in ultimas.iterrows():
        total = int(parcela["parcela_total"])
        ultima = int(parcela["parcela_atual"])
        restantes = max(0, total - ultima)

        assinatura = (parcela["descricao"], parcela["mes_competencia"],
                      int(round(abs(parcela["valor"]) * 100)))
        if assinatura in estornos:
            restantes = 0

        indice_ultima = mes_para_indice(parcela["mes_competencia"])
        if indice_ultima is None:
            continue

        valor_parcela = abs(float(parcela["valor"]))
        mes_origem = indice_para_mes(indice_ultima - (ultima - 1))
        mes_termino = indice_para_mes(indice_ultima + restantes)

        linhas.append({
            "chave": parcela["chave_parcelamento"],
            "descricao": parcela["descricao"],
            "categoria": parcela["categoria"],
            "grande_categoria": parcela["grande_categoria"],
            "tipo": parcela["tipo"],
            "parcela_total": total,
            "ultima_faturada": ultima,
            "mes_ultima": parcela["mes_competencia"],
            "mes_origem": mes_origem,
            "valor_parcela": valor_parcela,
            "parcelas_restantes": restantes,
            "total_a_vencer": restantes * valor_parcela,
            "mes_termino": mes_termino,
        })

    resultado = pd.DataFrame(linhas, columns=colunas)
    resultado = resultado.sort_values("total_a_vencer", ascending=False)

    if chave is not None:
        if len(_MEMORIA) >= _MEMORIA_MAX:
            _MEMORIA.pop(next(iter(_MEMORIA)))
        _MEMORIA[chave] = resultado.copy()
    return resultado


def ativos(df: pd.DataFrame, mes_base: str | None = None) -> pd.DataFrame:
    """So os parcelamentos que ainda tem parcela para vencer NO FUTURO.

    Sao duas condicoes, e a segunda foi acrescentada em 2026-08-23:

    1. ainda faltam parcelas (`parcelas_restantes > 0`);
    2. a ultima parcela cai daqui para a frente (`mes_termino >= mes_base`).

    A segunda existe porque "faltam parcelas" nao basta. Um parcelamento cujas
    parcelas restantes estavam todas no PASSADO — porque a compra foi
    estornada, ou porque a fatura daqueles meses nunca foi importada —
    continuava aparecendo como "em aberto". Eram R$ ···· de parcelas
    fantasma no total a vencer.

    Sem `mes_base`, usa o mes corrente.

    PASSE O `mes_base` SEMPRE QUE O CONTEXTO FOR OUTRO MES. Ate 2026-08-23,
    `grade_futura` e `detalhe_futuro` chamavam `ativos(df)` sem repassar o
    proprio `mes_base` — entao a projecao de um mes passado era anacronica:
    respondia "o que ainda falta HOJE", nao "o que faltava naquele mes".
    """
    todos = parcelamentos(df)
    if todos.empty:
        return todos
    base = mes_base or dados.mes_corrente()
    return todos[(todos["parcelas_restantes"] > 0)
                 & (todos["mes_termino"] >= base)]


def grade_futura(df: pd.DataFrame, mes_base: str,
                 n_meses: int = 18) -> pd.DataFrame:
    """Quanto de parcela ja contratada cai em cada mes a frente.

    Devolve [mes, total, quantidade] com uma linha por mes, INCLUSIVE os meses
    em que nao cai nada (com total zero). Ter o mes vazio na tabela importa:
    sem ele, o grafico de barras pularia o mes e daria a impressao errada de
    que o tempo passou mais rapido.
    """
    indice_base = mes_para_indice(mes_base)
    if indice_base is None:
        return pd.DataFrame(columns=["mes", "total", "quantidade"])

    meses = [indice_para_mes(indice_base + i) for i in range(1, n_meses + 1)]
    total_por_mes = {mes: 0.0 for mes in meses}
    qtd_por_mes = {mes: 0 for mes in meses}

    for _, parcelamento in ativos(df, mes_base).iterrows():
        indice_ultima = mes_para_indice(parcelamento["mes_ultima"])
        if indice_ultima is None:
            continue
        for passo in range(1, int(parcelamento["parcelas_restantes"]) + 1):
            mes = indice_para_mes(indice_ultima + passo)
            if mes in total_por_mes:
                total_por_mes[mes] += parcelamento["valor_parcela"]
                qtd_por_mes[mes] += 1

    return pd.DataFrame({
        "mes": meses,
        "total": [total_por_mes[m] for m in meses],
        "quantidade": [qtd_por_mes[m] for m in meses],
    })


def detalhe_futuro(df: pd.DataFrame, mes_base: str,
                   n_meses: int = 12) -> pd.DataFrame:
    """A mesma projecao, mas linha a linha (mes + qual compra).

    Serve para a tabela detalhada e para o grafico empilhado por categoria.
    """
    indice_base = mes_para_indice(mes_base)
    if indice_base is None:
        return pd.DataFrame(columns=["mes", "descricao", "categoria",
                                     "grande_categoria", "parcela", "valor"])

    limite = indice_base + n_meses
    linhas = []
    for _, parcelamento in ativos(df, mes_base).iterrows():
        indice_ultima = mes_para_indice(parcelamento["mes_ultima"])
        if indice_ultima is None:
            continue
        for passo in range(1, int(parcelamento["parcelas_restantes"]) + 1):
            indice = indice_ultima + passo
            if not (indice_base < indice <= limite):
                continue
            numero = int(parcelamento["ultima_faturada"]) + passo
            linhas.append({
                "mes": indice_para_mes(indice),
                "descricao": parcelamento["descricao"],
                "categoria": parcelamento["categoria"],
                "grande_categoria": parcelamento["grande_categoria"],
                "parcela": f'{numero}/{int(parcelamento["parcela_total"])}',
                "valor": parcelamento["valor_parcela"],
            })

    resultado = pd.DataFrame(
        linhas,
        columns=["mes", "descricao", "categoria", "grande_categoria",
                 "parcela", "valor"],
    )
    return resultado.sort_values(["mes", "valor"], ascending=[True, False])


def total_a_vencer(df: pd.DataFrame) -> float:
    """Soma de TUDO que ainda vai ser cobrado de parcelamentos em aberto.

    E o numero que responde "se eu parasse de gastar hoje, quanto ainda
    chegaria de fatura?".
    """
    lista = ativos(df)
    return float(lista["total_a_vencer"].sum()) if not lista.empty else 0.0


def herdadas_no_mes(df: pd.DataFrame, mes: str) -> float:
    """Parcelas de compras ANTIGAS ja lancadas naquele mes (2a em diante).

    Diferente de `previsto_no_mes`, que projeta o que AINDA NAO foi faturado.
    As duas juntas respondem "quanto daquele mes ja estava contratado", e nao
    se sobrepoem: a projecao comeca depois da ultima parcela ja registrada.
    """
    if df.empty:
        return 0.0
    do_mes = df[(df["mes_competencia"] == mes) & df["e_parcela_herdada"]]
    if do_mes.empty:
        return 0.0
    gastos = do_mes[do_mes["e_despesa"]]
    return float(-gastos["valor"].sum()) if not gastos.empty else 0.0


def ja_contratado_para(df: pd.DataFrame, mes_base: str, mes_alvo: str) -> float:
    """Quanto do `mes_alvo` ja esta comprometido por compras parceladas.

    SOMA AS DUAS METADES, e e por isso que existe:

        herdadas    parcelas ja LANCADAS naquele mes (a fatura ja foi importada)
        previstas   parcelas que ainda NAO foram faturadas

    O PROBLEMA QUE ISTO RESOLVE (2026-08-23). O painel usava so a segunda, e o
    cartao "JA CONTRATADO P/ SET/2026" mostrava **R$ ····** — enquanto setembro
    tinha R$ ···· de parcelas herdadas ja lancadas. O numero estava certo
    pela definicao dele ("o que ainda nao foi faturado") e lia como o oposto da
    verdade: "nada comprometido em setembro".

    Medido na base inteira, era R$ ···· em TODOS os meses menos o ultimo
    importado — porque assim que a fatura seguinte entra, nao sobra nada a
    projetar.

    > Um numero honesto pela sua propria definicao ainda pode mentir, se a
    > pergunta que a tela faz for outra.
    """
    return herdadas_no_mes(df, mes_alvo) + previsto_no_mes(df, mes_base, mes_alvo)


def previsto_no_mes(df: pd.DataFrame, mes_base: str, mes_alvo: str) -> float:
    """Quanto de parcela AINDA NAO FATURADA cai num mes especifico.

    So conta o que a fatura ainda nao registrou. Para "quanto daquele mes ja
    esta comprometido", use `ja_contratado_para`, que soma as duas metades.
    """
    grade = grade_futura(df, mes_base, n_meses=36)
    if grade.empty:
        return 0.0
    linha = grade[grade["mes"] == mes_alvo]
    return float(linha["total"].iloc[0]) if not linha.empty else 0.0


def novo_comprometimento(df: pd.DataFrame, mes: str) -> float:
    """Quanto de divida FUTURA voce criou neste mes.

    Conta so as PRIMEIRAS parcelas do mes e soma o que ficou para os meses
    seguintes (parcela x (total - 1)). Uma compra de R$ ···· em 12x feita
    agora aparece como R$ ···· de comprometimento novo: os outros 11 meses.

    E o indicador de "o quanto eu hipotequei o meu futuro neste mes" — a
    planilha tinha isso e e uma das metricas mais honestas do painel.
    """
    if df.empty:
        return 0.0
    novas = df[
        (df["mes_competencia"] == mes)
        & (df["origem"] == config.ORIGEM_FATURA)
        & (df["parcela_atual"] == 1)
        & (df["parcela_total"] > 1)
    ]
    if novas.empty:
        return 0.0
    return float((novas["valor"].abs() * (novas["parcela_total"] - 1)).sum())
