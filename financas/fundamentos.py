"""
fundamentos.py — O que a empresa por tras do papel diz de si.
==============================================================================

O QUE ESTE ARQUIVO FAZ
----------------------
Busca os numeros contabeis de uma acao ou ETF (caixa, divida, lucro, receita,
alvo dos analistas), guarda o json cru no banco e devolve uma FICHA ja
interpretada — com as ressalvas coladas no numero, nao numa nota de rodape.

Ele nao decide nada. Nao diz comprar nem vender, nao da nota, nao pontua. Ele
mostra o que existe e diz alto o que nao existe.

A MEDICAO QUE DEFINIU ESTE ARQUIVO
----------------------------------
Antes de desenhar, medimos o que a fonte entrega para os papeis da carteira:

    IREN   18 de 22 campos    sem P/L (prejuizo)   setor: "Financial Services"
    DGXX   17 de 22 campos    sem P/L (prejuizo)   1 analista cobrindo
    IRE     2 de 22 campos    ETF alavancado 2x sobre IREN

Tres conclusoes que mudaram o desenho:

1. **O kit classico nao serve para o que ele tem.** P/L, PEG, dividend yield e
   ROE positivo pressupoem lucro. Nenhum dos tres papeis da lucro. Um painel de
   valuation sairia vazio nos tres — e vazio nao e resposta.
2. **O setor da fonte pode estar errado.** O IREN e mineradora de bitcoin
   pivotando para datacenter de IA, e chega classificado como "Servicos
   Financeiros / Mercado de Capitais". Comparar "contra o setor" o compararia
   com bancos. Por isso `SETOR_SUSPEITO` existe e a tela avisa.
3. **Numero negativo em campo de multiplo e lixo, nao informacao.** O IREN vem
   com `forwardPE = -172,9`. Uma tela ingenua imprimiria isso como "P/L de
   -172" — que nao quer dizer nada. Aqui multiplo com lucro negativo vira
   `None`, e a ficha explica por que.

O QUE SUBSTITUI O KIT CLASSICO QUANDO NAO HA LUCRO
--------------------------------------------------
A pergunta que importa para empresa que queima caixa nao e "esta cara?", e sim
**"o dinheiro dura quanto tempo?"**. Isso e computavel:

    folego = caixa / queima anual de caixa

    IREN   R$ ···· bi de caixa, queima 4,24 bi/ano  ->  ~17 meses
    DGXX   US$  128 mi de caixa, queima  117 mi/ano  ->  ~13 meses

E o balanco dos dois e oposto: o IREN deve R$ ···· bi, mais do que tem em
caixa; o DGXX nao deve nada. Duas empresas no prejuizo, riscos diferentes.

O CACHE E DE UM DIA, E DIZ DE QUANDO E
--------------------------------------
Balanco muda por trimestre, nao por minuto. Buscar a cada abertura de tela
seria lento e sem ganho. O json cru fica em `fundamentos` com `obtido_em`, e a
ficha carrega essa data ate a tela — a mesma regra de `cotacoes.py`: se a rede
cair, o guardado continua servindo e DIZ que e antigo.

Guardamos o json **cru**, sem interpretar. Quando a leitura estiver errada,
da para corrigir sem buscar tudo de novo.

Como todo modulo de `financas/`, este nao importa streamlit.
"""

from __future__ import annotations

import json
import re
from datetime import date

from financas import banco

CAMPOS = (
    "quoteType", "shortName", "longName", "sector", "industry", "currency",
    "marketCap", "trailingPE", "forwardPE", "priceToBook", "trailingEps",
    "returnOnEquity", "debtToEquity", "totalCash", "totalDebt", "freeCashflow",
    "operatingCashflow", "totalRevenue", "revenueGrowth", "earningsGrowth",
    "profitMargins", "currentRatio", "dividendYield", "beta",
    "targetMeanPrice", "targetLowPrice", "targetHighPrice",
    "numberOfAnalystOpinions", "recommendationKey", "longBusinessSummary",
)

SETOR_SUSPEITO = {
    "IREN": "mineradora de bitcoin pivotando para datacenter de IA — a fonte "
            "classifica como Serviços Financeiros, o que a compararia com "
            "bancos",
}

_SEM_FUNDAMENTO = {
    "ETF": "ETF não tem balanço próprio: ele carrega uma cesta. Caixa, dívida "
           "e lucro são das empresas de dentro, não do fundo.",
    "ALAVANCADO": "ETF alavancado não tem balanço nenhum para analisar — ele "
                  "persegue um múltiplo do movimento DIÁRIO de outro papel.",
}

_ALAVANCAGEM = (
    re.compile(r"\b(?P<fator>[23])\s*X\b.{0,15}?"
               r"\b(?P<direcao>LONG|SHORT|BULL|BEAR)\b"
               r"(?:\s+(?P<alvo>[A-Z]{2,5})\b)?", re.IGNORECASE),
    re.compile(r"\b(?P<alvo>[A-Z]{2,5})\s+"
               r"(?P<direcao>(?i:LONG|SHORT|BULL|BEAR))\s+"
               r"(?P<fator>[23])\s*[Xx]\b"),
    re.compile(r"\b(?P<direcao>LONG|SHORT|BULL|BEAR)\s+"
               r"(?P<fator>[23])\s*X\b", re.IGNORECASE),
)

_INVERSOS = ("SHORT", "BEAR")


def alavancagem(nome: str | None) -> dict | None:
    """Le fator, direcao e papel-alvo do NOME do fundo. `None` se nao for.

    POR QUE PELO NOME, E NAO PELO `quoteType`. O IRE chega da fonte como
    `EQUITY` — acao comum — quando o nome dele diz literalmente "Defiance Daily
    Target 2X Long IREN ETF". O campo estruturado esta errado e o texto esta
    certo. Aqui a gente le o que esta certo.

    ISSO IMPORTA POR DOIS MOTIVOS, e nenhum e cosmetico:

    1. **Ele nao tem balanco para analisar.** Nao e dado faltando: o conceito
       nao se aplica. A tela precisa dizer isso em vez de mostrar campos vazios.
    2. **A exposicao real e o dobro da posicao.** Quem tem IREN e IRE tem uma
       aposta so, e parte dela dobrada. Somar as duas posicoes pelo valor de
       tela subestima o risco concentrado.

    E ha a terceira, que e a que ninguem conta: **2x por DIA nao e 2x no
    periodo.** Ver `decaimento()`.

    SAO TRES PADROES PORQUE AS GESTORAS NOMEIAM AO CONTRARIO UMA DA OUTRA:

        Defiance    "Daily Target 2X Long IREN"      fator antes da direcao
        Direxion    "Daily TSLA Bull 2X Shares"      alvo antes, fator depois
        Direxion    "Semiconductor Bear 3X Shares"   sem ticker no nome

    O terceiro padrao acha a alavancagem mas nao o alvo, e devolve
    `subjacente: None` — que e a resposta honesta. Nomes que escondem o fator
    em palavra ("UltraPro", "Ultra") ficam de fora de proposito: adivinhar que
    "UltraPro" e 3x seria chutar, e um chute aqui vira conta de exposicao
    errada.
    """
    for padrao in _ALAVANCAGEM:
        achado = padrao.search(nome or "")
        if not achado:
            continue
        sinal = -1 if achado.group("direcao").upper() in _INVERSOS else 1
        try:
            alvo = achado.group("alvo")
        except IndexError:
            alvo = None
        return {"fator": int(achado.group("fator")) * sinal,
                "direcao": "inverso" if sinal < 0 else "direto",
                "subjacente": (alvo or "").upper() or None}
    return None


def decaimento(retorno_papel: float, retorno_alvo: float, fator: float) -> dict:
    """Compara o que o alavancado entregou com o que \"fator x\" sugeriria.

    A CONTA QUE OS NOMES DESSES FUNDOS ESCONDEM. Um ETF "2x" persegue o dobro
    do movimento de UM DIA. Repetir isso todo dia NAO da o dobro no periodo —
    da menos, e a diferenca cresce com a oscilacao do papel-alvo. E aritmetica,
    nao opiniao: cair 10% e subir 10% no dia seguinte volta a 99% no papel
    normal, e a 96% no alavancado 2x.

    Medido na carteira dele, 215 pregoes:

        IREN            -35,8%
        2x do IREN      -71,5%   <- o que o nome do fundo sugere
        IRE (real)      -89,5%   <- 17,9 p.p. PIOR

    A razao diaria entre os dois deu mediana 1,99 — a alavancagem funciona
    exatamente como anunciada, todo dia. O buraco vem de multiplicar dias, nao
    de a promessa ter sido quebrada.
    """
    esperado = retorno_alvo * fator
    return {"esperado": esperado, "real": retorno_papel,
            "diferenca": retorno_papel - esperado}


def _tabela_vazia(ticker: str) -> dict:
    """A ficha de quem nao tem dado nenhum, com o motivo no lugar do vazio."""
    return {"ticker": ticker, "obtido_em": None, "tem_dado": False}


def buscar(ticker: str, forcar: bool = False) -> dict | None:
    """Busca os fundamentos e grava o json cru. Devolve o dicionario cru.

    Devolve `None` quando a biblioteca nao esta instalada ou a busca falha —
    nunca levanta. Quem chama decide se usa o guardado.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return None

    if not forcar:
        guardado = _guardado(ticker)
        if guardado and guardado.get("obtido_em") == date.today().isoformat():
            return guardado["dados"]

    try:
        import yfinance
    except ImportError:
        return None

    try:
        cru = yfinance.Ticker(ticker).info or {}
    except Exception:
        return None

    dados = {campo: cru.get(campo) for campo in CAMPOS if cru.get(campo) is not None}
    if not dados:
        return None

    banco.executar(
        """INSERT INTO fundamentos (ticker, dados, fonte, obtido_em)
           VALUES (?,?,?,?)
           ON CONFLICT(ticker) DO UPDATE SET
             dados = excluded.dados, fonte = excluded.fonte,
             obtido_em = excluded.obtido_em""",
        (ticker, json.dumps(dados), "yfinance", date.today().isoformat()),
    )
    return dados


def _guardado(ticker: str) -> dict | None:
    """Le o que ja esta no banco, sem tocar na rede."""
    linha = banco.consultar_um(
        "SELECT dados, fonte, obtido_em FROM fundamentos WHERE ticker = ?",
        (ticker,))
    if not linha:
        return None
    try:
        return {"dados": json.loads(linha["dados"]), "fonte": linha["fonte"],
                "obtido_em": linha["obtido_em"]}
    except (ValueError, TypeError):
        return None


def _folego_de_caixa(dados: dict) -> tuple[float | None, float | None]:
    """Quantos meses o caixa cobre a queima. `None` quando a empresa nao queima.

    Fluxo de caixa livre positivo significa que ela GERA dinheiro, e ai a
    pergunta "quanto tempo dura?" nao se aplica. Devolver um numero enorme
    seria pior que devolver nada.
    """
    caixa = dados.get("totalCash")
    fluxo = dados.get("freeCashflow")
    if caixa is None or fluxo is None or fluxo >= 0:
        return None, fluxo
    return caixa / abs(fluxo) * 12, fluxo


def _multiplo_valido(valor, lucro) -> float | None:
    """Multiplo so existe com lucro positivo. Com prejuizo, e ruido com sinal."""
    if valor is None or valor <= 0:
        return None
    if lucro is not None and lucro <= 0:
        return None
    return valor


def ficha(ticker: str, buscar_agora: bool = False) -> dict:
    """Devolve a leitura interpretada, com as ressalvas junto de cada numero.

    Toda chave que pode ser desconhecida vem `None`, nunca 0 — a regra de
    `docs/11`. `motivos` traz as frases que a tela precisa mostrar no lugar
    dos campos ausentes, e `avisos` o que ela precisa mostrar AO LADO dos
    campos presentes.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return _tabela_vazia(ticker)

    if buscar_agora:
        # `forcar=True` importa: sem ele, `buscar` devolve o guardado quando a
        # data e a de hoje, e o botao "Buscar dados de novo" nao buscava nada
        # no mesmo dia — prometia forcar e nao forcava. O caso em que voce
        # aperta o botao e justamente aquele em que desconfia do guardado.
        buscar(ticker, forcar=True)
    guardado = _guardado(ticker)
    if not guardado:
        if buscar(ticker) is None:
            return _tabela_vazia(ticker)
        guardado = _guardado(ticker)
    if not guardado:
        return _tabela_vazia(ticker)

    dados = guardado["dados"]
    lucro = dados.get("trailingEps")
    folego, fluxo = _folego_de_caixa(dados)
    caixa, divida = dados.get("totalCash"), dados.get("totalDebt")

    avisos, motivos = [], []

    if ticker in SETOR_SUSPEITO:
        avisos.append(
            f"**O setor informado pela fonte está errado.** {ticker} é "
            f"{SETOR_SUSPEITO[ticker]}.")

    analistas = dados.get("numberOfAnalystOpinions")
    if analistas is not None and analistas <= 2:
        avisos.append(
            f"O alvo de preço vem de **{analistas} analista"
            f"{'s' if analistas > 1 else ''}** — isso não é consenso, é uma "
            f"opinião. Um alvo com essa cobertura diz mais sobre quem o "
            f"escreveu que sobre a empresa.")

    if lucro is not None and lucro <= 0:
        motivos.append(
            "**Sem P/L, e não é falha de dado: a empresa dá prejuízo.** "
            "Múltiplo de lucro não existe sem lucro — e o número negativo que "
            "a fonte devolve não quer dizer nada. Para empresa assim, a "
            "pergunta que responde é o fôlego de caixa, aqui em cima.")

    alavanca = alavancagem(dados.get("longName") or dados.get("shortName"))
    if not dados.get("totalRevenue") and not dados.get("totalCash"):
        motivos.append(_SEM_FUNDAMENTO["ALAVANCADO" if alavanca else "ETF"])
    if alavanca:
        alvo_texto = (f" sobre **{alavanca['subjacente']}**"
                      if alavanca["subjacente"] else "")
        avisos.append(
            f"**Fundo alavancado {abs(alavanca['fator'])}x"
            f"{' inverso' if alavanca['fator'] < 0 else ''}{alvo_texto}.** Ele "
            f"persegue {abs(alavanca['fator'])}x o movimento de **um dia** — "
            f"e {abs(alavanca['fator'])}x por dia não dá "
            f"{abs(alavanca['fator'])}x no período. Quanto mais o alvo "
            f"oscila, mais o resultado fica atrás do que o nome sugere.")

    return {
        "ticker": ticker,
        "tem_dado": True,
        "obtido_em": guardado["obtido_em"],
        "nome": dados.get("longName") or dados.get("shortName"),
        "resumo": dados.get("longBusinessSummary"),
        "setor": dados.get("sector"),
        "industria": dados.get("industry"),
        "moeda": dados.get("currency"),
        "valor_de_mercado": dados.get("marketCap"),
        "lucro_por_acao": lucro,
        "da_lucro": None if lucro is None else lucro > 0,
        "pl": _multiplo_valido(dados.get("trailingPE"), lucro),
        "pl_projetado": _multiplo_valido(dados.get("forwardPE"), lucro),
        "preco_sobre_patrimonio": dados.get("priceToBook"),
        "margem": dados.get("profitMargins"),
        "retorno_patrimonio": dados.get("returnOnEquity"),
        "crescimento_receita": dados.get("revenueGrowth"),
        "receita": dados.get("totalRevenue"),
        "caixa": caixa,
        "divida": divida,
        "divida_maior_que_caixa": (None if caixa is None or divida is None
                                   else divida > caixa),
        "fluxo_de_caixa": fluxo,
        "folego_meses": folego,
        "liquidez_corrente": dados.get("currentRatio"),
        "dividendos": dados.get("dividendYield"),
        "beta": dados.get("beta"),
        "alvo": dados.get("targetMeanPrice"),
        "alvo_min": dados.get("targetLowPrice"),
        "alvo_max": dados.get("targetHighPrice"),
        "analistas": analistas,
        "recomendacao": dados.get("recommendationKey"),
        "alavancagem": alavanca,
        "avisos": avisos,
        "motivos": motivos,
    }


def resumo() -> dict:
    """Quantos papeis tem ficha guardada e de quando e a mais velha."""
    linha = banco.consultar_um(
        "SELECT COUNT(*) AS n, MIN(obtido_em) AS antiga, MAX(obtido_em) AS nova "
        "FROM fundamentos")
    return {"papeis": (linha["n"] if linha else 0) or 0,
            "mais_antiga": linha["antiga"] if linha else None,
            "mais_nova": linha["nova"] if linha else None}
