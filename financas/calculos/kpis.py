"""
kpis.py — Os numeros grandes do painel.
==============================================================================

O QUE E UM KPI
--------------
"Key Performance Indicator" — indicador-chave. Na pratica: aquele numero
grande num cartao no topo da tela, que responde uma pergunta sozinho.

Este arquivo reproduz os cinco blocos de indicadores que a aba "Dashboard
Financeiro" da planilha tinha, cada um respondendo uma pergunta diferente:

    resultado_do_mes()      Sobrou ou faltou dinheiro?
    composicao_despesa()    O gasto foi decisao deste mes ou heranca do passado?
    cartao()                Como esta o cartao e o que ainda vem por ai?
    gastos_fixos()          Quanto da minha renda ja esta comprometido antes
                            de eu decidir qualquer coisa?
    medias_tendencia()      Este mes foi normal ou fora da curva?

CADA FUNCAO DEVOLVE UM DICIONARIO
---------------------------------
Assim a pagina escolhe o que mostrar sem precisar decorar a ordem dos valores,
e acrescentar um indicador novo nao quebra quem ja usa os antigos.

TODAS AS FUNCOES SAO PURAS
--------------------------
Recebem o DataFrame, devolvem numeros. Nao leem banco, nao importam Streamlit.
Da para conferir qualquer uma no terminal comparando com a planilha — foi
assim que a projecao de parcelas foi validada contra a aba Parcelas Futuras.
"""

from __future__ import annotations

import pandas as pd

from financas import config, dados
from financas.calculos import parcelas
from financas.formato import somar_meses


def resultado_do_mes(df: pd.DataFrame, mes: str) -> dict:
    """Receita, despesa e saldo do mes escolhido.

    A RECEITA VEM SEPARADA EM DUAS PARTES, e isso e proposital. Em fevereiro
    voce recebeu R$ ···· de PLR; em agosto, R$ ···· de indenizacao.
    Somar isso ao salario faz o mes parecer confortavel quando na verdade foi
    excepcional — e nao se planeja o ano seguinte em cima de excecao.

    A planilha resolvia isso mostrando so a receita recorrente no resumo anual
    (foi o que explicou as diferencas na conferencia da migracao). Aqui
    mostramos as duas, com a extraordinaria destacada.

    Devolve:
        receita_total, receita_recorrente, receita_extraordinaria,
        despesa, saldo, saldo_recorrente, comprometimento, tem_extraordinaria
    """
    do_mes = dados.do_mes(df, mes)

    receita_recorrente = dados.total_receita(do_mes, incluir_extraordinaria=False)
    receita_extra = dados.total_extraordinaria(do_mes)
    receita_total = receita_recorrente + receita_extra
    despesa = dados.total_despesa(do_mes)

    return {
        "mes": mes,
        "receita_total": receita_total,
        "receita_recorrente": receita_recorrente,
        "receita_extraordinaria": receita_extra,
        "tem_extraordinaria": abs(receita_extra) > 0.01,
        "despesa": despesa,
        "saldo": receita_total - despesa,
        "saldo_recorrente": receita_recorrente - despesa,
        "comprometimento": despesa / receita_total if receita_total else 0.0,
        "comprometimento_recorrente": (
            despesa / receita_recorrente if receita_recorrente else 0.0
        ),
        "quantidade": len(do_mes),
    }


def composicao_despesa(df: pd.DataFrame, mes: str) -> dict:
    """Separa o gasto do mes entre "eu decidi agora" e "ja estava contratado".

    ESTA E A ANALISE MAIS UTIL DO PAINEL. Duas pessoas podem gastar os mesmos
    R$ ···· num mes: uma decidiu tudo naquele mes e pode cortar no mes que
    vem; a outra so esta pagando parcela de compra antiga e nao tem o que
    cortar. O total nao distingue as duas — esta conta sim.

    As tres partes:
        gasto_novo          o que voce decidiu neste mes (inclui a 1a parcela)
        parcelas_herdadas   parcelas 2, 3, 4... de compras de meses anteriores
        parcelas_previstas  o que ainda vai chegar de parcelas ja contratadas

    E o indicador que fecha a conta:
        novo_comprometimento  quanto de divida FUTURA voce criou neste mes
    """
    do_mes = dados.do_mes(df, mes)
    gastos = dados.despesas(do_mes)

    despesa_total = dados.total_despesa(do_mes)

    herdadas = gastos[gastos["e_parcela_herdada"]] if not gastos.empty else gastos
    parcelas_herdadas = float(-herdadas["valor"].sum()) if not herdadas.empty else 0.0

    gasto_novo = despesa_total - parcelas_herdadas
    previstas = parcelas.ja_contratado_para(df, mes, somar_meses(mes, 1) or mes)
    compromisso_herdado = parcelas_herdadas + previstas

    base = despesa_total + previstas

    return {
        "gasto_novo": gasto_novo,
        "parcelas_herdadas": parcelas_herdadas,
        "parcelas_previstas": previstas,
        "compromisso_herdado": compromisso_herdado,
        "pct_herdado": compromisso_herdado / base if base else 0.0,
        "pct_novo": gasto_novo / despesa_total if despesa_total else 0.0,
        "novo_comprometimento": parcelas.novo_comprometimento(df, mes),
        "despesa_total": despesa_total,
    }


def cartao(df: pd.DataFrame, mes: str) -> dict:
    """Os numeros do cartao no mes, e o que ainda esta por vir.

    Devolve:
        total_mes             quanto a fatura do mes somou
        variavel_realizado    a parte variavel (a que da para cortar)
        fixo_realizado        a parte fixa (assinatura, mensalidade)
        saldo_futuro          tudo que ainda vai ser cobrado de parcelamentos
        n_parcelamentos       quantos parcelamentos estao ativos
        maior_parcelamento    o maior saldo devedor individual
        pct_da_despesa        quanto do gasto do mes passou pelo cartao
    """
    do_mes = dados.do_mes(df, mes)
    no_cartao = dados.do_cartao(do_mes)
    gastos_cartao = dados.despesas(no_cartao)

    total_mes = float(-gastos_cartao["valor"].sum()) if not gastos_cartao.empty else 0.0

    if gastos_cartao.empty:
        variavel = fixo = 0.0
    else:
        variavel = float(
            -gastos_cartao[gastos_cartao["tipo"] == config.TIPO_VARIAVEL]["valor"].sum())
        fixo = float(
            -gastos_cartao[gastos_cartao["tipo"] == config.TIPO_FIXO]["valor"].sum())

    ativos = parcelas.ativos(df)
    despesa_total = dados.total_despesa(do_mes)

    return {
        "total_mes": total_mes,
        "variavel_realizado": variavel,
        "fixo_realizado": fixo,
        "saldo_futuro": parcelas.total_a_vencer(df),
        "n_parcelamentos": int(len(ativos)),
        "maior_parcelamento": (
            float(ativos["total_a_vencer"].max()) if not ativos.empty else 0.0
        ),
        "pct_da_despesa": total_mes / despesa_total if despesa_total else 0.0,
        "quantidade": len(gastos_cartao),
    }


def fixos_variaveis(df: pd.DataFrame, mes: str) -> dict:
    """Quanto do mes foi gasto fixo e quanto foi variavel.

    A diferenca importa para decidir onde mexer: gasto fixo se corta mudando
    de contrato (cancelar assinatura, trocar de plano); gasto variavel se
    corta mudando de habito. Sao dois tipos de esforco bem diferentes.
    """
    do_mes = dados.do_mes(df, mes)
    gastos = dados.despesas(do_mes)
    if gastos.empty:
        return {"fixo": 0.0, "variavel": 0.0, "total": 0.0,
                "pct_fixo": 0.0, "parcelado": 0.0, "a_vista": 0.0}

    fixo = float(-gastos[gastos["tipo"] == config.TIPO_FIXO]["valor"].sum())
    variavel = float(-gastos[gastos["tipo"] == config.TIPO_VARIAVEL]["valor"].sum())
    parcelado = float(-gastos[gastos["e_parcelado"]]["valor"].sum())
    total = fixo + variavel

    return {
        "fixo": fixo,
        "variavel": variavel,
        "total": total,
        "pct_fixo": fixo / total if total else 0.0,
        "parcelado": parcelado,
        "a_vista": total - parcelado,
    }


def medias_tendencia(df: pd.DataFrame, mes: str) -> dict:
    """Compara o mes com a media dos meses anteriores.

    IMPORTANTE: as janelas de media NAO incluem o mes escolhido. Se
    incluissem, o mes estaria sendo comparado com ele mesmo e a comparacao
    perderia o sentido — um mes caro puxaria a propria media para cima e
    pareceria menos fora da curva do que foi.

    Tambem descartamos os meses "de futuro" (aqueles que so tem parcela
    agendada e nenhum gasto real ainda), senao a media desabaria.

    Devolve as medias de 3 e 6 meses da despesa e do cartao, e a variacao do
    mes atual contra a media de 3 meses.
    """
    serie = dados.por_mes(df)
    if serie.empty:
        return _tendencia_vazia()

    anteriores = serie[serie["mes"] < mes].sort_values("mes", ascending=False)

    if "quantidade" in anteriores.columns:
        anteriores = anteriores[anteriores["quantidade"] >= 5]
    anteriores = anteriores[anteriores["despesa"] > 1]

    if anteriores.empty:
        return _tendencia_vazia()

    despesa_3m = float(anteriores.head(3)["despesa"].mean())
    despesa_6m = float(anteriores.head(6)["despesa"].mean())
    receita_6m = float(anteriores.head(6)["receita"].mean())

    no_cartao = dados.despesas(dados.do_cartao(df))
    if no_cartao.empty:
        cartao_3m = cartao_6m = 0.0
    else:
        por_mes_cartao = (
            no_cartao.groupby("mes_competencia")["valor"].sum().mul(-1).reset_index()
        )
        por_mes_cartao = por_mes_cartao[por_mes_cartao["mes_competencia"] < mes]
        por_mes_cartao = por_mes_cartao.sort_values("mes_competencia", ascending=False)
        cartao_3m = float(por_mes_cartao.head(3)["valor"].mean()) if len(por_mes_cartao) else 0.0
        cartao_6m = float(por_mes_cartao.head(6)["valor"].mean()) if len(por_mes_cartao) else 0.0

    atual = serie[serie["mes"] == mes]
    despesa_atual = float(atual["despesa"].iloc[0]) if not atual.empty else 0.0

    proximo = somar_meses(mes, 1)
    parcelas_proximo = parcelas.previsto_no_mes(df, mes, proximo) if proximo else 0.0

    return {
        "despesa_media_3m": despesa_3m,
        "despesa_media_6m": despesa_6m,
        "receita_media_6m": receita_6m,
        "cartao_media_3m": cartao_3m,
        "cartao_media_6m": cartao_6m,
        "despesa_atual": despesa_atual,
        "variacao_3m": (
            (despesa_atual - despesa_3m) / despesa_3m if despesa_3m else 0.0
        ),
        "previsao_proximo": despesa_3m + parcelas_proximo,
        "meses_considerados": int(len(anteriores)),
    }


def _tendencia_vazia() -> dict:
    """Resposta neutra quando ainda nao ha historico suficiente."""
    return {
        "despesa_media_3m": 0.0, "despesa_media_6m": 0.0,
        "receita_media_6m": 0.0, "cartao_media_3m": 0.0, "cartao_media_6m": 0.0,
        "despesa_atual": 0.0, "variacao_3m": 0.0, "previsao_proximo": 0.0,
        "meses_considerados": 0,
    }


def resumo_anual(df: pd.DataFrame, ano: str) -> pd.DataFrame:
    """Tabela mes a mes do ano, com saldo acumulado e trimestres.

    Reproduz o "RESUMO ANUAL" da planilha. Devolve todos os 12 meses, mesmo os
    que ainda nao aconteceram (com zero), para a tabela ter sempre o mesmo
    formato e o grafico nao encolher no meio do ano.
    """
    colunas = ["mes", "rotulo", "receita", "receita_extra", "despesa",
               "saldo", "acumulado", "comprometimento", "e_trimestre"]

    serie = dados.por_mes(df)
    do_ano = serie[serie["mes"].str.startswith(str(ano))] if not serie.empty else serie
    por_mes = {linha["mes"]: linha for _, linha in do_ano.iterrows()}

    linhas = []
    acumulado = 0.0
    for numero_mes in range(1, 13):
        mes = f"{ano}-{numero_mes:02d}"
        registro = por_mes.get(mes)
        receita = float(registro["receita"]) if registro is not None else 0.0
        extra = float(registro["receita_extra"]) if registro is not None else 0.0
        despesa = float(registro["despesa"]) if registro is not None else 0.0
        saldo = receita - despesa
        acumulado += saldo

        linhas.append({
            "mes": mes,
            "rotulo": ["jan", "fev", "mar", "abr", "mai", "jun",
                       "jul", "ago", "set", "out", "nov", "dez"][numero_mes - 1],
            "receita": receita,
            "receita_extra": extra,
            "despesa": despesa,
            "saldo": saldo,
            "acumulado": acumulado,
            "comprometimento": despesa / receita if receita else 0.0,
            "e_trimestre": False,
        })

        if numero_mes % 3 == 0:
            trimestre = linhas[-3:]
            soma_receita = sum(l["receita"] for l in trimestre)
            soma_despesa = sum(l["despesa"] for l in trimestre)
            linhas.append({
                "mes": f"{ano}-T{numero_mes // 3}",
                "rotulo": f"{numero_mes // 3}º trim.",
                "receita": soma_receita,
                "receita_extra": sum(l["receita_extra"] for l in trimestre),
                "despesa": soma_despesa,
                "saldo": soma_receita - soma_despesa,
                "acumulado": acumulado,
                "comprometimento": soma_despesa / soma_receita if soma_receita else 0.0,
                "e_trimestre": True,
            })

    return pd.DataFrame(linhas, columns=colunas)


def anos_disponiveis(df: pd.DataFrame) -> list[str]:
    """Os anos que aparecem no banco, do mais recente para o mais antigo."""
    if df.empty:
        return []
    return sorted(df["mes_competencia"].str.slice(0, 4).unique(), reverse=True)


def painel(df: pd.DataFrame, mes: str) -> dict:
    """Calcula todos os blocos de uma vez, para a pagina do Dashboard.

    Junta em um dicionario de dicionarios:
        {"resultado": {...}, "composicao": {...}, "cartao": {...}, ...}

    Ter uma funcao so evita que a pagina chame cinco funcoes na ordem errada,
    e deixa obvio o que precisa mudar quando um bloco novo for criado.
    """
    return {
        "mes": mes,
        "resultado": resultado_do_mes(df, mes),
        "composicao": composicao_despesa(df, mes),
        "cartao": cartao(df, mes),
        "fixos_variaveis": fixos_variaveis(df, mes),
        "tendencia": medias_tendencia(df, mes),
    }


def variacao_por_categoria(df: pd.DataFrame, mes: str,
                           limite: int = 8) -> pd.DataFrame:
    """O que subiu e o que caiu contra o mes anterior, por grande categoria.

    POR QUE ISTO VALE MAIS QUE UMA MEDIA DE 3 MESES

    "Voce gastou 22% acima da media" e uma informacao morta: nao da para fazer
    nada com ela. "Saude subiu R$ ···· e Viagem R$ ····" e acionavel, porque
    voce lembra o que aconteceu e decide se repete no mes que vem.

    Devolve [grande_categoria, atual, anterior, variacao, variacao_pct],
    ordenado pelo tamanho da mudanca — nao pelo tamanho do gasto. Uma
    categoria grande e estavel nao interessa aqui; uma pequena que triplicou,
    sim.

    Categorias que existem so num dos dois meses entram com zero do outro
    lado, senao a maior novidade do mes ficaria de fora justamente por ser
    nova.
    """
    colunas = ["grande_categoria", "atual", "anterior", "variacao", "variacao_pct"]
    anterior_mes = somar_meses(mes, -1)
    if not anterior_mes:
        return pd.DataFrame(columns=colunas)

    def gastos_do(m):
        tabela = dados.por_categoria(dados.do_mes(df, m), "grande_categoria")
        if tabela.empty:
            return {}
        return {linha["grande_categoria"]: abs(float(linha["total"]))
                for _, linha in tabela.iterrows()}

    atual = gastos_do(mes)
    passado = gastos_do(anterior_mes)
    if not atual and not passado:
        return pd.DataFrame(columns=colunas)

    linhas = []
    for nome in set(atual) | set(passado):
        valor_atual = atual.get(nome, 0.0)
        valor_passado = passado.get(nome, 0.0)
        variacao = valor_atual - valor_passado
        linhas.append({
            "grande_categoria": nome,
            "atual": valor_atual,
            "anterior": valor_passado,
            "variacao": variacao,
            "variacao_pct": (variacao / valor_passado) if valor_passado else None,
        })

    tabela = pd.DataFrame(linhas, columns=colunas)
    tabela["peso"] = tabela["variacao"].abs()
    return (tabela.sort_values("peso", ascending=False)
            .drop(columns=["peso"]).head(limite).reset_index(drop=True))


def taxa_de_poupanca(df: pd.DataFrame, meses_minimos: int = 5) -> pd.DataFrame:
    """Quanto por cento da receita sobrou, mes a mes.

    O INDICADOR QUE FALTAVA. O painel dizia quanto entrou e quanto saiu, mas
    nao respondia a pergunta que importa no longo prazo: **estou guardando
    dinheiro?** Um mes com R$ ···· de receita e R$ ···· de despesa parece
    otimo em valores absolutos e e pessimo em taxa (5%).

        taxa = (receita − despesa) ÷ receita

O MES CORRENTE ENTRA, E ISSO MUDOU EM 2026-08-25
    ------------------------------------------------
    Ele pediu: *"por que nao entra o mes corrente? Acho que ele poderia ser
    atualizado in real time."*

    A exclusao existia por um motivo que **deixou de valer**: as despesas
    chegavam antes da receita, porque a fatura do cartao contava no mes do
    VENCIMENTO e o salario no mes em que caiu. Era o desalinhamento que a
    migracao 13 corrigiu. Hoje o gasto do cartao e o salario do mesmo ciclo
    caem no mesmo mes, e o mes corrente ja nasce coerente.

    O mes corrente entra com **previsao**: realizado + o que ainda falta
    (`calculos/previsao.do_mes`). A coluna `parcial` diz quais meses sao
    assim, para o grafico desenhar diferente e para a media movel ignora-los.

    Mes FUTURO continua fora desta tabela. Ele nao tem receita nenhuma
    realizada, e uma taxa de poupanca sobre previsao pura seria opiniao
    desenhada como fato.

    O FILTRO QUE FICA:
    - menos de `meses_minimos` lancamentos: um mes que so tem parcela
      agendada daria uma taxa de −300% e afundaria a escala do grafico.

    Devolve [mes, receita, despesa, saldo, taxa, media_movel, parcial].
    """
    colunas = ["mes", "receita", "despesa", "saldo", "taxa", "media_movel",
               "parcial"]
    serie = dados.por_mes(df)
    if serie.empty:
        return pd.DataFrame(columns=colunas)

    corrente = dados.mes_corrente()
    fechados = dados.meses_fechados(serie, meses_minimos)

    do_corrente = serie[serie["mes"] == corrente]
    if not do_corrente.empty:
        from financas.calculos import previsao as _previsao

        prev = _previsao.do_mes(df, corrente)
        if prev["receita_total"] > 0:
            fechados = pd.concat([
                fechados,
                pd.DataFrame([{
                    "mes": corrente,
                    "receita": prev["receita_total"],
                    "despesa": prev["despesa_total"],
                }]),
            ], ignore_index=True)

    serie = fechados[fechados["receita"] > 0].sort_values("mes")
    if serie.empty:
        return pd.DataFrame(columns=colunas)

    tabela = serie[["mes", "receita", "despesa"]].copy()
    tabela["saldo"] = tabela["receita"] - tabela["despesa"]
    tabela["taxa"] = tabela["saldo"] / tabela["receita"]
    tabela["parcial"] = tabela["mes"] == corrente
    fechados_taxa = tabela.loc[~tabela["parcial"], "taxa"]
    media = fechados_taxa.rolling(3, min_periods=1).mean()
    tabela["media_movel"] = media.reindex(tabela.index).ffill()
    return tabela[colunas].reset_index(drop=True)


def taxa_de_poupanca_agregada(tabela: pd.DataFrame) -> float:
    """A taxa do periodo inteiro: soma dos saldos ÷ soma das receitas.

    IGNORA O MES PARCIAL. Desde 2026-08-25 a tabela inclui o mes corrente com
    previsao; somar previsao num indicador que resume o passado misturaria
    medida com palpite. A barra do mes aparece no grafico, mas nao entra aqui.

    NUNCA use a media das taxas mensais no lugar desta. Sao numeros
    diferentes, e a media engana feio:

        media das taxas mensais  −32,0%
        mediana                  −38,3%
        AGREGADA                 +28,3%   <- a verdadeira

    (medido em 2026-08-23, sobre 28 meses fechados)

    O motivo e que a receita dele oscila muito: R$ ···· no mes mais magro
    contra R$ ···· no mais gordo, catorze vezes. Um mes magro produz uma taxa
    de −236% (set/2025), e uma media de percentuais trata esse mes como se
    pesasse igual a um mes de PLR. A agregada pesa cada mes pelo tamanho dele,
    que e o que faz sentido quando a pergunta e "de tudo que entrou, quanto
    sobrou".

    Repare que a distancia entre as duas leituras CRESCEU desde a primeira vez
    que esta explicacao foi escrita (eram −12,1% e +29,6%). Nao e o metodo que
    piorou: e a renda que ficou mais irregular. Mais um motivo para nao usar a
    media de percentuais.
    """
    if tabela.empty:
        return 0.0
    medidos = (tabela[~tabela["parcial"].fillna(False).astype(bool)]
               if "parcial" in tabela.columns else tabela)
    if medidos.empty:
        return 0.0
    receita = float(medidos["receita"].sum())
    return float(medidos["saldo"].sum()) / receita if receita else 0.0


def comparativo_anual(df: pd.DataFrame) -> pd.DataFrame:
    """Receita, despesa e saldo de cada ano, lado a lado.

    So passou a fazer sentido quando o banco ganhou 2024 e 2025 — com um ano
    so nao ha comparacao nenhuma.

    A coluna `meses` importa para ler o resto: 2024 tem 9 meses de dados e
    2026 esta pela metade, entao comparar os TOTAIS engana. Por isso vao junto
    as medias mensais, que sao o numero comparavel.

    O mes em andamento fica de fora pelo mesmo motivo de `taxa_de_poupanca`:
    ele tem a despesa contratada mas nao a receita inteira, e rebaixaria a
    media do ano corrente sem que nada tivesse piorado.

    Devolve [ano, receita, despesa, saldo, meses, receita_media, despesa_media].
    """
    colunas = ["ano", "receita", "despesa", "saldo", "meses",
               "receita_media", "despesa_media"]
    serie = dados.por_mes(df)
    if serie.empty:
        return pd.DataFrame(columns=colunas)

    serie = dados.meses_fechados(serie)
    if serie.empty:
        return pd.DataFrame(columns=colunas)

    serie = serie.copy()
    serie["ano"] = serie["mes"].str[:4]
    agrupado = (
        serie.groupby("ano")
        .agg(receita=("receita", "sum"), despesa=("despesa", "sum"),
             meses=("mes", "size"))
        .reset_index()
        .sort_values("ano")
    )
    agrupado["saldo"] = agrupado["receita"] - agrupado["despesa"]
    agrupado["receita_media"] = agrupado["receita"] / agrupado["meses"]
    agrupado["despesa_media"] = agrupado["despesa"] / agrupado["meses"]
    return agrupado[colunas].reset_index(drop=True)


def serie_rateando_plr(df: pd.DataFrame,
                       meses_de_rateio: int = 12) -> pd.DataFrame:
    """A mesma serie mensal, mas com o PLR DILUIDO pelos meses seguintes.

    AS DUAS LEITURAS DE UM PLR
    --------------------------
    Ele recebe PLR duas vezes por ano, em fevereiro e agosto. Isso distorce
    qualquer leitura mensal: o mes do bonus parece extraordinario e os outros
    parecem magros, quando aquele dinheiro e remuneracao do ano inteiro.

        COMO ENTROU   o PLR aparece inteiro no mes em que caiu.
                      Responde "quanto dinheiro entrou na conta em fevereiro?"

        RATEADO       o PLR e espalhado pelos meses seguintes.
                      Responde "quanto eu ganho por mes, de verdade?"

    Nenhuma das duas e "a certa" — sao perguntas diferentes, e por isso o
    painel mostra as duas lado a lado.

    SO O QUE ESTA NA CATEGORIA `PLR` E RATEADO
    ------------------------------------------
    E nao toda receita extraordinaria. A diferenca importa: ele tem
    R$ ···· da Caixa Previdencia e R$ ···· da Porto Seguro marcados
    como extraordinarios, e esses NAO sao remuneracao diluida ao longo do ano
    — sao eventos unicos, que devem continuar aparecendo no mes em que
    cairam.

    Quem decide o que e PLR e ELE, marcando a categoria na tela de
    Lancamentos. Nao ha regra de valor adivinhando: um limiar de "acima de
    X e PLR" erraria tanto para cima quanto para baixo, e classificacao
    errada de R$ ···· estraga o ano inteiro em silencio.

    POR QUE ISTO E CALCULO E NAO LANCAMENTO
    ---------------------------------------
    Ate 2026-08-23 o rateio existia como 12 LANCAMENTOS gravados no banco,
    herdados da planilha. Como o PLR original tambem estava la, os mesmos
    R$ ···· contavam duas vezes na receita — 12% de receita fantasma.

    Uma visao nao pode ser um fato. O fato e o dinheiro que entrou; o rateio e
    uma forma de olhar para ele.

O RATEIO E POR ANO-CALENDARIO
    -----------------------------
    A PLR do ANO se espalha pelos 12 meses DAQUELE ano. As duas de 2025 somam
    R$ ···· entao todo mes de 2025 recebe R$ ····; as de 2026 somam
    outro valor, e todo mes de 2026 recebe o dele.

    Mudou em 2026-08-25, a pedido dele. Antes, cada PLR se espalhava pelos 12
    meses SEGUINTES ao mes em que caiu — o que fazia a PLR de agosto/2025
    ainda pingar em julho/2026, misturando dois anos. Comparar janeiro com
    fevereiro do mesmo ano ficava confuso porque cada um carregava um pedaco
    diferente do passado.

    Por ano, todo mes do mesmo ano recebe a MESMA parcela. A pergunta que o
    grafico responde — "quanto eu ganho por mes?" — passa a ter uma resposta
    estavel dentro do ano.

    **Ano em andamento:** divide pelo que ja caiu, sempre por 12. Se a segunda
    PLR do ano ainda nao chegou, o grafico sobe quando ela chegar — e sobe
    para o ano inteiro de uma vez. Isso e proposital: e a mesma leitura que
    ele pediu para a taxa de poupanca, que anda conforme o ano anda.

    A coluna `rateio_futuro` guarda os pedacos que caem em meses FORA da
    serie (a base comeca em abr/2024, entao jan a mar/2024 nao aparecem).

    Devolve [mes, receita, receita_recorrente, receita_rateada, despesa,
             saldo, rateio_futuro].
    """
    colunas = ["mes", "receita", "receita_recorrente", "receita_rateada",
               "despesa", "saldo", "rateio_futuro"]
    serie = dados.por_mes(df)
    if serie.empty:
        return pd.DataFrame(columns=colunas)

    serie = serie.sort_values("mes").reset_index(drop=True)
    meses = list(serie["mes"])
    posicao = {m: i for i, m in enumerate(meses)}

    recebidas = dados.receitas(df)
    plr_por_mes = {}
    if not recebidas.empty:
        so_plr = recebidas[recebidas["categoria"] == config.CATEGORIA_PLR]
        if not so_plr.empty:
            plr_por_mes = (
                so_plr.groupby("mes_competencia")["valor"].sum().to_dict())

    plr_por_ano: dict[str, float] = {}
    for mes_do_plr, valor in plr_por_mes.items():
        if valor and valor > 0:
            plr_por_ano[str(mes_do_plr)[:4]] = (
                plr_por_ano.get(str(mes_do_plr)[:4], 0.0) + float(valor))

    rateado = [0.0] * len(meses)
    futuro = 0.0
    for ano, total in plr_por_ano.items():
        parcela = total / meses_de_rateio
        for numero in range(1, meses_de_rateio + 1):
            alvo = f"{ano}-{numero:02d}"
            if alvo in posicao:
                rateado[posicao[alvo]] += parcela
            else:
                futuro += parcela

    sem_plr = [float(r) - float(plr_por_mes.get(m, 0.0))
               for m, r in zip(meses, serie["receita"])]

    tabela = pd.DataFrame({
        "mes": meses,
        "receita": serie["receita"].to_numpy(),
        "receita_recorrente": sem_plr,
        "receita_rateada": [a + b for a, b in zip(sem_plr, rateado)],
        "despesa": serie["despesa"].to_numpy(),
    })
    tabela["saldo"] = tabela["receita_rateada"] - tabela["despesa"]
    tabela["rateio_futuro"] = futuro
    return tabela[colunas]
