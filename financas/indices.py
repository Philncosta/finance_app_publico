"""Indices de referencia: CDI e IPCA, do Banco Central.

POR QUE ESTE ARQUIVO EXISTE
===========================
"A NTN-B mai/2035 rendeu 6,38%" nao e informacao. E so um numero ate voce
saber contra o que comparar. No mesmo periodo:

    CDI    14,22%      IPCA    4,44%

Conforme a regua, o mesmo papel "perdeu feio" ou "protegeu o poder de compra
com folga". Sem referencia, a tela de rentabilidade so gera ansiedade.

A REGUA CERTA DEPENDE DO PAPEL — E ESSA E A PARTE QUE IMPORTA
==============================================================
Este e o erro mais comum em planilha de investimento pessoal: comparar tudo
com o CDI. Nos SEUS numeros, medidos em 2026-08-24:

    LFT mar/2031      103% do CDI    <- CDI e a regua certa
    Trend DI           88% do CDI    <- CDI e a regua certa
    NTN-B mai/2045     19% do CDI    <- o CDI aqui MENTE
    IRE              -765% do CDI    <- aritmetica sem significado

Uma NTN-B perde do CDI em ciclo de juro alto **por construcao**: a marcacao a
mercado cai justamente porque a Selic subiu. Julgar um IPCA+ pelo CDI e usar a
regua do produto concorrente. A pergunta certa para ela e "protegeu da
inflacao?", e a resposta esta no IPCA.

E "% do CDI" para um papel que perdeu dinheiro nao quer dizer nada: o
resultado troca de sinal e a razao vira ruido.

Por isso `referencia_para()` escolhe o indice pelo MACRO do papel, e devolve
`None` quando nenhum indice serve. Nenhuma referencia e melhor que a errada.

DE ONDE VEM O DADO
==================
API SGS do Banco Central — publica, sem chave, mesma casa do PTAX que o
`cambio.py` ja usa:

    serie 4391   CDI acumulado no mes (% a.m.)
    serie  433   IPCA mensal (% a.m.)

Como todo modulo de `financas/`, este nao importa streamlit e nunca levanta
erro por causa de rede: sem internet, usa o que ja esta guardado.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date

from financas import banco
from financas.formato import mes_para_indice

SERIES = {
    "CDI": 4391,
    "IPCA": 433,
}

SERIES_MERCADO = {
    "IBOV": ("^BVSP", "Ibovespa, o índice da bolsa brasileira"),
    "S&P 500": ("IVVB11.SA",
                "S&P 500 **em reais**, pelo ETF IVVB11 — inclui o câmbio, "
                "que é o que um investidor brasileiro de fato sente"),
    "SMLL": ("SMAL11.SA",
             "small caps brasileiras, pelo ETF SMAL11 (aproximação do índice)"),
    "IFIX": ("XFIX11.SA",
             "fundos imobiliários, pelo ETF XFIX11 (aproximação do índice)"),
}

_URL_SGS = ("https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
            "?formato=json&dataInicial={inicio}&dataFinal={fim}")


def _ddmmyyyy(dia: date) -> str:
    """O SGS so aceita data no formato dd/mm/aaaa."""
    return dia.strftime("%d/%m/%Y")


def buscar(nome: str, inicio: date, fim: date) -> int:
    """Busca uma serie no Banco Central e grava. Devolve quantos meses gravou.

    Nao levanta erro se a internet estiver fora: devolve 0 e o resto do app
    segue com o que ja tem guardado — a mesma regra do `cambio.py`.
    """
    nome = (nome or "").strip().upper()
    serie = SERIES.get(nome)
    if serie is None:
        return 0

    url = _URL_SGS.format(serie=serie, inicio=_ddmmyyyy(inicio),
                          fim=_ddmmyyyy(fim))
    try:
        with urllib.request.urlopen(url, timeout=30) as resposta:
            dados = json.load(resposta)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return 0

    agora = banco.agora()
    linhas = []
    for item in dados or []:
        bruto = (item.get("data") or "")
        valor = item.get("valor")
        if len(bruto) != 10 or valor in (None, ""):
            continue
        mes = f"{bruto[6:10]}-{bruto[3:5]}"
        try:
            taxa = float(valor) / 100
        except (TypeError, ValueError):
            continue
        linhas.append((nome, mes, taxa, "sgs", agora))

    if not linhas:
        return 0
    return banco.executar_muitos(
        """INSERT INTO indices (nome, mes, taxa, fonte, obtida_em)
           VALUES (?,?,?,?,?)
           ON CONFLICT(nome, mes) DO UPDATE SET
             taxa = excluded.taxa, fonte = excluded.fonte,
             obtida_em = excluded.obtida_em""",
        linhas,
    )


def buscar_mercado(nome: str, desde: str | None = None) -> int:
    """Deriva a variacao mensal de um indice de bolsa. Devolve meses gravados.

    POR QUE ESTE CAMINHO E DIFERENTE DO CDI
    ---------------------------------------
    CDI e IPCA vem do Banco Central ja como TAXA do mes. IBOV, S&P, SMLL e
    IFIX nao existem no SGS: eles sao PRECO, e precisam virar taxa.

    O caminho reaproveita o que ja existe em vez de abrir uma segunda porta
    para a mesma coisa:

        cotacoes.atualizar(ticker)   busca e grava o fechamento DIARIO
        aqui                          le esse fechamento, pega o ULTIMO dia de
                                      cada mes e calcula a variacao

    Assim o preco tem uma fonte so no projeto (`cotacoes`), e `indices` fica
    sendo uma VISTA derivada dela. Guardar o preco em dois lugares seria duas
    chances de divergir.

    O ULTIMO DIA DE CADA MES, e nao a media: a serie tem de casar com a
    carteira, cujo saldo tambem e a foto do fim do mes.

    SOBRE OS PROXIES. SMLL e IFIX entram por ETF (SMAL11, XFIX11), porque o
    indice em si nao tem ticker publico. O ETF rende um pouco menos que o
    indice — taxa de administracao —, e a tela diz que e aproximacao. E o S&P
    entra em REAIS (IVVB11): a carteira-sombra e em reais, e aplicar uma
    variacao em dolar sobre ela somaria moedas sem quebrar.

    O QUE O NUMERO DEVOLVIDO SIGNIFICA: meses em que o dado MUDOU — novo ou
    diferente do guardado. Nao e a contagem de linhas reescritas. A diferenca
    apareceu num teste: com a rede fora, esta funcao redevolvia a serie inteira
    a partir dos precos ja guardados e anunciava "31 meses gravados", quando
    nada tinha entrado. Um numero que so significa "reescrevi" nao serve para
    a tela dizer se a busca funcionou.
    """
    from financas import cotacoes

    if nome not in SERIES_MERCADO:
        return 0
    ticker = SERIES_MERCADO[nome][0]
    cotacoes.atualizar([ticker], desde=f"{desde}-01" if desde else None)

    precos = banco.consultar(
        "SELECT data, fechamento FROM cotacoes WHERE ticker = ? ORDER BY data",
        (ticker.upper(),))
    if len(precos) < 2:
        return 0

    fim_do_mes: dict[str, float] = {}
    for linha in precos:
        fim_do_mes[str(linha["data"])[:7]] = float(linha["fechamento"])

    ja_guardado = serie(nome)
    meses = sorted(fim_do_mes)
    agora = banco.agora()
    gravar, novidades = [], 0
    for anterior, atual in zip(meses, meses[1:]):
        base = fim_do_mes[anterior]
        if not base:
            continue
        taxa = fim_do_mes[atual] / base - 1
        gravar.append((nome, atual, taxa, f"yfinance:{ticker}", agora))
        antiga = ja_guardado.get(atual)
        if antiga is None or abs(antiga - taxa) > 1e-9:
            novidades += 1
    if not gravar:
        return 0

    banco.executar_muitos(
        """INSERT INTO indices (nome, mes, taxa, fonte, obtida_em)
           VALUES (?,?,?,?,?)
           ON CONFLICT(nome, mes) DO UPDATE SET
             taxa = excluded.taxa, fonte = excluded.fonte,
             obtida_em = excluded.obtida_em""",
        gravar,
    )
    return novidades


def atualizar(desde: str | None = None, com_mercado: bool = True) -> dict:
    """Atualiza CDI, IPCA e os indices de bolsa. Devolve {nome: meses_gravados}.

    `desde` no formato 'AAAA-MM'. Sem ele, pega os ultimos 5 anos — barato,
    sao poucas linhas por ano, e evita buracos no meio da serie.

    `com_mercado=False` pula IBOV, S&P, SMLL e IFIX. Serve para quem esta sem
    rede ou sem `yfinance`: o Banco Central continua respondendo, e meia
    atualizacao e melhor que nenhuma.
    """
    hoje = date.today()
    if desde and mes_para_indice(desde) is not None:
        inicio = date(int(desde[:4]), int(desde[5:7]), 1)
    else:
        inicio = date(hoje.year - 5, 1, 1)

    resultado = {nome: buscar(nome, inicio, hoje) for nome in SERIES}
    if com_mercado:
        marca = desde or inicio.strftime("%Y-%m")
        for nome in SERIES_MERCADO:
            resultado[nome] = buscar_mercado(nome, marca)
    return resultado


def disponiveis() -> list[str]:
    """Os indices que tem serie guardada, na ordem em que a tela deve oferecer."""
    guardados = {linha["nome"] for linha in banco.consultar(
        "SELECT DISTINCT nome FROM indices")}
    ordem = ["CDI", "IPCA", "IBOV", "S&P 500", "SMLL", "IFIX"]
    return [nome for nome in ordem if nome in guardados] + sorted(
        guardados - set(ordem))


def descricao(nome: str) -> str:
    """O que aquele indice e, em uma frase, para a tela poder explicar."""
    if nome in SERIES_MERCADO:
        return SERIES_MERCADO[nome][1]
    if nome == "CDI":
        return "o juro de referência — a régua do pós-fixado e do caixa"
    if nome == "IPCA":
        return "a inflação oficial — a régua de quem investe para se proteger dela"
    return ""


def serie(nome: str, ate: str | None = None) -> dict[str, float]:
    """A serie guardada como {mes: taxa em fracao}."""
    sql = "SELECT mes, taxa FROM indices WHERE nome = ?"
    params: list = [(nome or "").strip().upper()]
    if ate:
        sql += " AND mes <= ?"
        params.append(ate)
    return {linha["mes"]: float(linha["taxa"])
            for linha in banco.consultar(sql + " ORDER BY mes", tuple(params))}


def acumulado(nome: str, meses) -> float | None:
    """Quanto o indice rendeu NOS MESES INFORMADOS, capitalizado.

    O parametro `meses` nao e um intervalo, e uma LISTA — e isso e o ponto.

    Se o rendimento de um papel ignora 4 meses porque a fonte do aporte nao
    era confiavel (ver `investimentos.evolucao`), a referencia tem de ignorar
    os MESMOS 4. Comparar 8 meses de fundo contra 12 meses de CDI e uma
    mentira que passa despercebida, porque os dois numeros parecem do mesmo
    tipo.

    Devolve `None` se nenhum dos meses pedidos existe na serie — melhor que
    devolver 0,0, que se leria como "o CDI nao rendeu nada".
    """
    guardada = serie(nome)
    fator = 1.0
    achou = False
    for mes in meses:
        taxa = guardada.get(mes)
        if taxa is None:
            continue
        fator *= 1 + taxa
        achou = True
    return (fator - 1) if achou else None


def cobertura(nome: str, meses) -> tuple[int, list[str]]:
    """Quantos dos meses pedidos a serie tem, e quais faltam.

    Existe por um motivo concreto: **o IPCA sai com um mes de atraso.** Em
    24/08/2026 a serie ia so ate julho. Comparar 12 meses de NTN-B contra 11
    meses de IPCA subestima a inflacao e faz o titulo parecer melhor do que
    foi — e nada na tela denunciaria isso, porque os dois numeros tem a mesma
    cara.

    `acumulado()` capitaliza o que existe, de proposito; quem mostra na tela
    chama esta funcao junto e avisa quando falta mes.
    """
    guardada = serie(nome)
    pedidos = list(meses)
    faltando = [m for m in pedidos if m not in guardada]
    return len(pedidos) - len(faltando), faltando


def referencia_para(macro: str | None, classe: str | None = None) -> str | None:
    """Qual indice serve de regua para um papel. `None` quando nenhum serve.

    A escolha e por MACRO, porque e o macro que carrega o tipo de risco:

        Caixa, Renda Fixa pos-fixada   -> CDI
        Renda Fixa indexada ao IPCA    -> IPCA
        Renda Variavel brasileira      -> IBOV
        Internacional                  -> S&P 500 (em reais)
        o resto                        -> nenhum

    AS DUAS ULTIMAS SAO NOVAS, E CUMPREM UMA PROMESSA. Ate 2026-08-29 esta
    funcao devolvia `None` para internacional e renda variavel, e a explicacao
    dizia: *"a regua honesta seria o S&P ou o setor do papel — que este app nao
    acompanha. Enquanto nao acompanhar, nao mostra referencia nenhuma."*

    Agora acompanha. `SERIES_MERCADO` traz IBOV, S&P 500, SMLL e IFIX, e o
    internacional deixou de ser comparado ao CDI (que dava -765% no IRE) para
    ser comparado ao indice que faz sentido.

    O `None` continua existindo para o que nao tem regua — e continua sendo
    resposta legitima, nao lacuna.
    """
    texto = f"{classe or ''} {macro or ''}".upper()
    limpo = (macro or "").strip().upper()

    if "IPCA" in texto or "NTN-B" in texto or "NTNB" in texto:
        return "IPCA"
    if limpo in ("CAIXA", "RENDA FIXA"):
        return "CDI"
    if limpo == "INTERNACIONAL":
        return "S&P 500"
    if limpo in ("RENDA VARIÁVEL", "RENDA VARIAVEL"):
        return "IBOV"
    return None


def resumo() -> dict:
    """Estado das series guardadas, para a tela dizer de quando e o dado."""
    linhas = banco.consultar(
        """SELECT nome, COUNT(*) n, MAX(mes) ultimo, MAX(obtida_em) em
           FROM indices GROUP BY nome""")
    return {linha["nome"]: {"meses": linha["n"], "ultimo_mes": linha["ultimo"],
                            "atualizado_em": linha["em"]}
            for linha in linhas}
