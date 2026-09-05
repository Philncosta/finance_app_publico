"""
cambio.py — Converter dolar em real, pela cotacao do dia certo.
==============================================================================

POR QUE ESTE ARQUIVO EXISTE
---------------------------
A partir de agosto/2026 a carteira tem papeis em DOLAR (IREN, DGXX, IRE, na
conta internacional). O resto do app inteiro pensa em reais: o patrimonio, a
reserva de emergencia, a alocacao, o rebalanceamento.

Somar R$ ···· (dolares) com R$ ···· (reais) daria R$ ···· de coisa
nenhuma. Alguem precisa fazer a ponte, e e este arquivo.

A REGRA DO PROJETO: A CONVERSAO ACONTECE UMA VEZ SO
----------------------------------------------------
Nao e cada calculo que converte — seria seis lugares para lembrar, e um dia
alguem esqueceria. A conversao acontece **na hora de gravar o saldo**, e o
banco guarda os dois numeros:

    saldo        em REAIS, e o que todo calculo do app soma
    saldo_moeda  o valor original em dolar, para a tela mostrar

Ou seja: depois que o dado entra, o app volta a ser um app de reais.

DE ONDE VEM A COTACAO
---------------------
Do **PTAX do Banco Central** — a taxa oficial, publicada todo dia util. E API
publica, sem cadastro e sem chave:

    https://olinda.bcb.gov.br/olinda/servico/PTAX/...

Usamos a **cotacao de VENDA**, que e a referencia para quem compra dolar, e e a
que a Receita usa para declaracao. A de compra fica guardada tambem, mas nao e
a que entra nas contas.

E POR QUE NAO A TAXA QUE VOCE PAGOU DE VERDADE
-----------------------------------------------
A taxa da corretora tem spread e IOF embutidos — no seu cambio de 30/10/2025
foram 0,15% de spread mais 1,10% de IOF. Essa taxa e o CUSTO da operacao, e ela
importa para saber se voce fez um bom negocio.

Mas para dizer "quanto vale hoje, em reais, o que esta la fora", a referencia
tem de ser a taxa de mercado — senao o patrimonio mudaria conforme a corretora
que voce usou. Por isso: **PTAX para avaliar, taxa real para medir o custo.**

SEM INTERNET, O APP CONTINUA FUNCIONANDO
-----------------------------------------
Toda cotacao buscada fica gravada na tabela `cotacoes`. Se a busca falhar, as
funcoes daqui usam a ultima cotacao guardada e DIZEM de que dia ela e. O painel
nunca deixa de abrir por causa de rede.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta

from financas import banco
from financas.formato import parse_data, vazio

TICKER_DOLAR = "USDBRL"

MOEDA_PADRAO = "BRL"

MAX_DIAS_PARA_TRAS = 10

_URL_PTAX = (
    "https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/"
    "CotacaoDolarPeriodo(dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)"
    "?@dataInicial='{inicio}'&@dataFinalCotacao='{fim}'&$format=json"
)


def _mdy(d: date) -> str:
    """A API do BCB quer a data no formato americano MM-DD-AAAA."""
    return d.strftime("%m-%d-%Y")


def buscar_ptax(inicio: date, fim: date) -> int:
    """Busca o dolar no Banco Central e grava. Devolve quantos dias gravou.

    Nao levanta erro se a internet estiver fora: devolve 0 e o resto do app
    segue com o que ja tem guardado. Uma cotacao velha e melhor que uma tela
    quebrada, desde que o app diga que ela e velha — e ele diz.
    """
    url = _URL_PTAX.format(inicio=_mdy(inicio), fim=_mdy(fim))
    try:
        with urllib.request.urlopen(url, timeout=30) as resposta:
            dados = json.load(resposta)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return 0

    linhas = []
    agora = banco.agora()
    for item in dados.get("value", []):
        dia = (item.get("dataHoraCotacao") or "")[:10]
        venda = item.get("cotacaoVenda")
        if not dia or venda is None:
            continue
        linhas.append((TICKER_DOLAR, dia, float(venda), "BRL", "ptax", agora))

    if not linhas:
        return 0
    return banco.executar_muitos(
        """INSERT INTO cotacoes (ticker, data, fechamento, moeda, fonte, obtida_em)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(ticker, data) DO UPDATE SET
             fechamento = excluded.fechamento, fonte = excluded.fonte,
             obtida_em = excluded.obtida_em""",
        linhas,
    )


def cotacao_dolar(dia=None, buscar: bool = True) -> tuple[float | None, str | None]:
    """Quanto valia um dolar naquele dia. Devolve (valor, data_usada).

    A DATA DEVOLVIDA IMPORTA TANTO QUANTO O VALOR. Sabado nao tem PTAX; feriado
    tambem nao. Nesses casos a funcao anda para tras ate achar um dia util e
    **devolve a data que realmente usou**, para a tela poder dizer
    "cotacao de sexta-feira" em vez de fingir que tem a de hoje.

    `buscar=False` desliga o acesso a rede — util em teste e em qualquer lugar
    que precise ser rapido e previsivel.
    """
    alvo = parse_data(dia) if dia is not None else date.today()
    if alvo is None:
        return (None, None)

    limite = (alvo - timedelta(days=MAX_DIAS_PARA_TRAS)).isoformat()

    def procurar():
        return banco.consultar_um(
            """SELECT data, fechamento FROM cotacoes
               WHERE ticker = ? AND data <= ? AND data >= ?
               ORDER BY data DESC LIMIT 1""",
            (TICKER_DOLAR, alvo.isoformat(), limite))

    linha = procurar()
    if linha is None and buscar:
        buscar_ptax(alvo - timedelta(days=MAX_DIAS_PARA_TRAS), alvo)
        linha = procurar()

    if linha is None:
        linha = banco.consultar_um(
            "SELECT data, fechamento FROM cotacoes WHERE ticker = ? AND data <= ? "
            "ORDER BY data DESC LIMIT 1", (TICKER_DOLAR, alvo.isoformat()))
    if linha is None:
        return (None, None)
    return (float(linha["fechamento"]), linha["data"])


def para_brl(valor, dia=None, moeda: str = "USD") -> tuple[float | None, float | None, str | None]:
    """Converte um valor para reais. Devolve (valor_brl, cotacao, data_usada).

    Devolver a cotacao e a data junto com o resultado nao e detalhe: e o que
    permite GRAVAR o cambio empregado (coluna `investimentos_saldos.cambio_usado`)
    e reproduzir depois o numero que estava na tela. A cotacao de hoje nao serve
    para conferir o saldo de marco.

    Moeda BRL devolve o proprio valor, sem tocar na rede.
    """
    if vazio(valor):
        return (None, None, None)
    valor = float(valor)
    if (moeda or MOEDA_PADRAO).upper() == MOEDA_PADRAO:
        return (valor, 1.0, None)

    cotacao, data_usada = cotacao_dolar(dia)
    if cotacao is None:
        return (None, None, None)
    return (valor * cotacao, cotacao, data_usada)


def ultimo_dia_do_mes(mes: str) -> date | None:
    """O ultimo dia do mes 'AAAA-MM'. E a data de referencia dos saldos mensais.

    O saldo de um mes e a foto do FIM do mes, entao a cotacao que o converte
    tem de ser a do fim do mes tambem — nao a de hoje. Sem isto, reimportar um
    arquivo antigo daria um numero diferente a cada dia.
    """
    from financas.formato import mes_para_indice, indice_para_mes
    indice = mes_para_indice(mes)
    if indice is None:
        return None
    seguinte = indice_para_mes(indice + 1)
    primeiro_do_seguinte = date(int(seguinte[:4]), int(seguinte[5:7]), 1)
    return primeiro_do_seguinte - timedelta(days=1)


def cotacao_do_mes(mes: str) -> tuple[float | None, str | None]:
    """A cotacao do fim daquele mes: (valor, data_usada). Ver `ultimo_dia_do_mes`."""
    fim = ultimo_dia_do_mes(mes)
    if fim is None:
        return (None, None)
    hoje = date.today()
    return cotacao_dolar(min(fim, hoje))


def historico(desde: str | None = None) -> list[dict]:
    """As cotacoes de dolar guardadas, da mais recente para a mais antiga."""
    sql = "SELECT data, fechamento, fonte FROM cotacoes WHERE ticker = ?"
    params: list = [TICKER_DOLAR]
    if desde:
        sql += " AND data >= ?"
        params.append(desde)
    return [dict(l) for l in banco.consultar(sql + " ORDER BY data DESC", tuple(params))]


def resumo() -> dict:
    """Como esta a base de cotacoes: quantas, de quando ate quando, e a ultima.

    Serve para a tela dizer "dolar de 21/08/2026" em vez de mostrar um numero
    sem procedencia.
    """
    linha = banco.consultar_um(
        """SELECT COUNT(*) AS n, MIN(data) AS primeira, MAX(data) AS ultima
           FROM cotacoes WHERE ticker = ?""", (TICKER_DOLAR,))
    ultima_cotacao, ultima_data = (None, None)
    if linha and linha["ultima"]:
        ultima_cotacao, ultima_data = cotacao_dolar(linha["ultima"], buscar=False)
    return {
        "dias": int(linha["n"]) if linha else 0,
        "primeira": linha["primeira"] if linha else None,
        "ultima": ultima_data,
        "cotacao": ultima_cotacao,
    }
