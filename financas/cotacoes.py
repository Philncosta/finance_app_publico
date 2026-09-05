"""
cotacoes.py — Quanto vale um papel, num dia.
==============================================================================

O QUE ESTE ARQUIVO FAZ
----------------------
Busca preco de fechamento de acoes, ETFs e FIIs e guarda no banco. Serve para
duas coisas:

    1. saber quanto a carteira vale hoje, sem voce digitar nada;
    2. RECONSTRUIR quanto ela valia no passado — quantidade x preco do mes.

A segunda e a que mais rendeu. A conta internacional nao exporta extrato, mas
os tres papeis (IREN, DGXX, IRE) sao da NASDAQ e as quantidades ficaram
estaveis desde 31/10/2025. Com o preco de fechamento de cada mes, dez meses de
saldo saem exatos, sem ninguem digitar nada e sem estimativa.

O LIMITE, DITO SEM RODEIO
-------------------------
Isto cobre **acoes, ETFs e FIIs** — o que tem ticker publico:

    B3          sufixo .SA     TASA3.SA, BBAS3.SA, PETR4.SA
    EUA         direto         IREN, DGXX, IRE

**Tesouro Direto e fundos NAO tem ticker publico.** LFT, NTN-B e o Trend DI
continuam vindo do arquivo de posicao da corretora, como sempre. Esta API
resolve a parte internacional e a renda variavel, nao a carteira inteira.

A RESSALVA DA BIBLIOTECA
------------------------
`yfinance` nao e oficial: ela raspa o Yahoo Finance e ja quebrou outras vezes
quando o Yahoo mexeu no site. Por isso duas defesas:

    1. tudo que e buscado fica GRAVADO em `cotacoes`;
    2. se a busca falhar, as funcoes usam o que ja esta guardado e DIZEM de
       quando e.

O painel nunca deixa de abrir por causa de rede ou de uma biblioteca quebrada.

POR QUE PRECO E CAMBIO MORAM NA MESMA TABELA
--------------------------------------------
Sao a mesma pergunta: *quanto vale uma unidade, neste dia*. O dolar entra com o
"ticker" `USDBRL` (ver `cambio.py`). Duas tabelas quase iguais seriam duas
chances de divergir.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from financas import banco
from financas.formato import parse_data, vazio

SUFIXO_B3 = ".SA"


def _yfinance():
    """Importa yfinance so quando precisa, e devolve None se nao der.

    O import fica AQUI DENTRO de proposito. `financas/` tem de continuar
    importavel num ambiente sem yfinance instalado — senao uma dependencia
    opcional, que so serve para renda variavel, derrubaria o app inteiro na
    hora de abrir.
    """
    try:
        import warnings
        warnings.filterwarnings("ignore", module="yfinance")
        import yfinance
        return yfinance
    except Exception:
        return None


def disponivel() -> bool:
    """A biblioteca de cotacoes esta instalada? A tela usa para avisar."""
    return _yfinance() is not None


def gravar(ticker: str, precos: dict, moeda: str = "USD", fonte: str = "yfinance") -> int:
    """Grava um mapa {data ISO: preco}. Devolve quantos dias entraram."""
    if not precos:
        return 0
    agora = banco.agora()
    linhas = [(ticker.upper(), dia, float(valor), moeda, fonte, agora)
              for dia, valor in precos.items() if valor is not None]
    return banco.executar_muitos(
        """INSERT INTO cotacoes (ticker, data, fechamento, moeda, fonte, obtida_em)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(ticker, data) DO UPDATE SET
             fechamento = excluded.fechamento, fonte = excluded.fonte,
             obtida_em = excluded.obtida_em""",
        linhas,
    )


def atualizar(tickers, desde=None, ate=None) -> dict:
    """Busca o historico de fechamento e grava. Devolve {ticker: dias_gravados}.

    SOBRE O AJUSTE POR GRUPAMENTO/DESDOBRAMENTO. Os precos vem **ajustados por
    split**, e isso e o que a gente quer: preco ajustado x quantidade de HOJE
    da o valor correto em qualquer data passada, porque o split nao muda o
    valor da posicao, so em quantos pedacos ela esta dividida.

    Foi exatamente o caso do IRE, que fez um grupamento de 1 para 4 em
    20/03/2026 — os dois "Ajuste + R$ ····" que apareceram no extrato dele.
    Antes do grupamento eram 145 cotas; depois, 36,25. Com preco ajustado e a
    quantidade atual, os meses de 2025 saem certos mesmo assim.

    Nunca levanta erro por causa de rede: um ticker que falhar entra com 0.
    """
    yf = _yfinance()
    if yf is None:
        return {}

    if isinstance(tickers, str):
        tickers = [tickers]
    inicio = parse_data(desde) or (date.today() - timedelta(days=365 * 3))
    fim = (parse_data(ate) or date.today()) + timedelta(days=1)

    resultado: dict[str, int] = {}
    for ticker in tickers:
        ticker = (ticker or "").strip().upper()
        if not ticker:
            continue
        try:
            historico = yf.Ticker(ticker).history(
                start=inicio.isoformat(), end=fim.isoformat(), auto_adjust=False)
        except Exception:
            resultado[ticker] = 0
            continue
        if historico is None or historico.empty or "Close" not in historico:
            resultado[ticker] = 0
            continue

        moeda = "BRL" if ticker.endswith(SUFIXO_B3) else "USD"
        precos = {
            indice.date().isoformat(): float(valor)
            for indice, valor in historico["Close"].items()
            if valor is not None and not vazio(valor)
        }
        resultado[ticker] = gravar(ticker, precos, moeda=moeda)
    return resultado


def preco_em(ticker: str, dia=None) -> tuple[float | None, str | None]:
    """O fechamento daquele papel na data pedida. Devolve (preco, data_usada).

    Mesma regra do cambio, e pelo mesmo motivo: fim de semana e feriado nao tem
    pregao, entao a funcao anda para tras e **devolve a data que usou**. E so
    olha para TRAS — o preco de amanha nao diz quanto o papel valia ontem.
    """
    alvo = parse_data(dia) or date.today()
    linha = banco.consultar_um(
        """SELECT data, fechamento FROM cotacoes
           WHERE ticker = ? AND data <= ? ORDER BY data DESC LIMIT 1""",
        ((ticker or "").upper(), alvo.isoformat()))
    if linha is None:
        return (None, None)
    return (float(linha["fechamento"]), linha["data"])


def serie(ticker: str, desde=None) -> pd.DataFrame:
    """Todo o historico de fechamento de um papel. Colunas: data, fechamento.

    POR QUE ISTO PRECISOU EXISTIR: o banco guarda 756 fechamentos DIARIOS de
    IREN e DGXX e 215 do IRE — tres anos de preco — e nenhuma tela mostrava
    nada disso. As duas leituras que existiam (`preco_em`, `preco_do_mes`)
    devolvem um ponto so, porque foram escritas para converter saldo, nao para
    desenhar curva.

    Devolve DataFrame vazio com as colunas certas quando o ticker nao tem nada
    guardado — a tela desenha um grafico do mesmo tamanho com o recado dentro,
    em vez de sumir com o bloco.

    `desde` aceita 'AAAA-MM-DD' ou date; None traz tudo.
    """
    alvo = parse_data(desde)
    if alvo is None:
        linhas = banco.df(
            "SELECT data, fechamento FROM cotacoes WHERE ticker = ? "
            "ORDER BY data", ((ticker or "").upper(),))
    else:
        linhas = banco.df(
            "SELECT data, fechamento FROM cotacoes WHERE ticker = ? "
            "AND data >= ? ORDER BY data",
            ((ticker or "").upper(), alvo.isoformat()))
    if linhas.empty:
        return pd.DataFrame(columns=["data", "fechamento"])
    return linhas


def preco_do_mes(ticker: str, mes: str) -> tuple[float | None, str | None]:
    """O fechamento do ULTIMO dia daquele mes — a referencia do saldo mensal."""
    from financas.cambio import ultimo_dia_do_mes
    fim = ultimo_dia_do_mes(mes)
    if fim is None:
        return (None, None)
    return preco_em(ticker, min(fim, date.today()))


def tickers_cadastrados() -> list[str]:
    """Os tickers dos investimentos ativos que tem um cadastrado."""
    return [l["ticker"].strip().upper()
            for l in banco.consultar(
                "SELECT DISTINCT ticker FROM investimentos "
                "WHERE ticker IS NOT NULL AND TRIM(ticker) <> ''")
            if l["ticker"]]


def atualizar_carteira(desde=None) -> dict:
    """Atualiza as cotacoes de todos os papeis da carteira que tem ticker.

    E o que o botao "Atualizar cotacoes" da tela chama. Papel sem ticker
    (Tesouro, fundo) simplesmente nao entra — nao ha o que buscar.
    """
    return atualizar(tickers_cadastrados(), desde=desde)


def resumo() -> dict:
    """Quantos papeis e quantos dias estao guardados, e de quando e o mais novo.

    Serve para a tela dizer "cotacoes de 21/08/2026" em vez de mostrar numero
    sem procedencia — sobretudo quando a ultima busca falhou.
    """
    linha = banco.consultar_um(
        """SELECT COUNT(*) AS dias, COUNT(DISTINCT ticker) AS papeis,
                  MAX(data) AS ultima
           FROM cotacoes WHERE ticker <> 'USDBRL'""")
    return {
        "papeis": int(linha["papeis"]) if linha else 0,
        "dias": int(linha["dias"]) if linha else 0,
        "ultima": linha["ultima"] if linha else None,
        "biblioteca_ok": disponivel(),
    }
