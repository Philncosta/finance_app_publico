"""
precos.py — Quanto um item da lista de desejos custou, ao longo do tempo.
==============================================================================

O PROBLEMA QUE ELE RESOLVE
--------------------------
`futuras_compras.preco_atual` e um numero que se SOBRESCREVE. Voce anota
R$ ···· hoje, R$ ···· no mes que vem, e o 4.299 some. Sem os valores
anteriores, o app nao consegue responder a unica pergunta que uma lista de
desejos precisa responder:

        "R$ ···· e barato, ou ja esteve mais barato?"

Uma linha por consulta em `precos_compras` responde isso de graca: menor preco
ja visto, curva do preco, e o aviso de "esta no melhor preco desde que voce
comecou a acompanhar".

SO PONTO DE MUDANCA, E O GRAFICO E EM DEGRAU
--------------------------------------------
`registrar()` NAO grava um ponto por consulta. Se o preco de hoje e igual ao
ultimo gravado, ele so carimba `obtido_em` — "conferi hoje, nao mudou". Quinze
consultas de um preco parado viram um ponto, nao quinze.

Isso obriga o grafico a ser em DEGRAU (`line_shape="hv"`), nao em linha reta.
A diferenca nao e estetica: dois pontos, 4.299 em 10/07 e 3.999 em 26/08,
ligados por uma reta desenham uma queda suave que nunca existiu. O preco ficou
em 4.299 ate o dia em que virou 3.999. O degrau e o desenho honesto.

A BUSCA AUTOMATICA, E O TAMANHO DELA
------------------------------------
`ler_preco_da_pagina()` baixa o HTML do link e procura o preco em tres lugares
padronizados, nesta ordem:

    1. JSON-LD    <script type="application/ld+json"> com @type Product
    2. Open Graph <meta property="og:price:amount">
    3. Microdata  itemprop="price"

Sao os tres formatos que as lojas publicam de proposito, para o Google
entender a pagina. Nao ha raspagem de HTML visual aqui — nada de "pega a
terceira <div> da classe tal", que quebra na primeira mudanca de layout.

**E isso funciona em PARTE das lojas, nao em todas.** Amazon e Mercado Livre
bloqueiam acesso automatico e/ou montam o preco por JavaScript depois que a
pagina abre; nesses, a busca falha e o preco continua sendo digitado a mao. E
o mesmo trato do `cotacoes.py` com o yfinance: quando funciona, poupa
digitacao; quando nao funciona, o app nao quebra, DIZ o motivo com todas as
letras, e o campo manual continua valendo.

A busca so roda quando voce clica no botao — nunca ao abrir a pagina. Uma
consulta que sai sozinha a cada `st.rerun()` viraria dezenas de requisicoes
por minuto para a loja, o que e abuso e o caminho mais curto para o bloqueio.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime

import pandas as pd

from financas import banco
from financas.formato import parse_brl, vazio

# Um agente de navegador comum. Sem isso, boa parte das lojas devolve 403
# direto — nao por seguranca, por politica de trafego automatizado.
_AGENTE = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_CABECALHOS = {
    "User-Agent": _AGENTE,
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

_TIMEOUT = 15          # segundos por pagina
_INTERVALO = 1.0       # segundos entre uma loja e a proxima
_LIMITE_BYTES = 3_000_000   # o suficiente para o <head> e o corpo da pagina

_RE_JSONLD = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE)
_RE_OG = re.compile(
    r'<meta[^>]+(?:property|name)\s*=\s*["\'](?:og:price:amount|'
    r'product:price:amount)["\'][^>]*content\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE)
_RE_MICRODATA = re.compile(
    r'<meta[^>]+itemprop\s*=\s*["\']price["\'][^>]*content\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE)

STATUS_ABERTOS = ("Desejo", "Pesquisando", "Aguardando preço")


# ----------------------------------------------------------------------------
# O historico
# ----------------------------------------------------------------------------

def registrar(compra_id: int, preco, fonte: str = "manual",
              quando=None) -> bool:
    """Guarda um preco no historico. Devolve True se algo NOVO entrou.

    Tres caminhos, nesta ordem:

        preco igual ao ultimo    so carimba `obtido_em` -> devolve False
        ja ha ponto de hoje      corrige aquele ponto   -> devolve True
        caso contrario           insere ponto novo      -> devolve True

    O primeiro caminho e o que mantem a tabela pequena e o grafico legivel:
    conferir o mesmo preco todo dia por um mes deixa UM ponto, com a data em
    que ele apareceu e o carimbo de quando foi conferido pela ultima vez.
    """
    if vazio(preco):
        return False
    valor = float(preco)
    if valor <= 0:
        return False

    dia = str(quando or date.today())[:10]
    agora = datetime.now().isoformat(timespec="seconds")

    ultimo = banco.consultar_um(
        "SELECT id, data, preco FROM precos_compras "
        " WHERE compra_id = ? ORDER BY data DESC, id DESC LIMIT 1",
        (int(compra_id),),
    )

    if ultimo is not None and abs(float(ultimo["preco"]) - valor) < 0.005:
        banco.executar(
            "UPDATE precos_compras SET obtido_em = ?, fonte = ? WHERE id = ?",
            (agora, fonte, int(ultimo["id"])),
        )
        return False

    if ultimo is not None and str(ultimo["data"])[:10] == dia:
        banco.executar(
            "UPDATE precos_compras SET preco = ?, fonte = ?, obtido_em = ? "
            " WHERE id = ?",
            (valor, fonte, agora, int(ultimo["id"])),
        )
        return True

    banco.executar(
        "INSERT INTO precos_compras (compra_id, data, preco, fonte, obtido_em) "
        "VALUES (?, ?, ?, ?, ?)",
        (int(compra_id), dia, valor, fonte, agora),
    )
    return True


def historico(compra_id: int | None = None) -> pd.DataFrame:
    """Os pontos de preco, de um item ou de todos.

    Sem argumento devolve o historico inteiro — e assim que a pagina carrega
    tudo numa consulta so, em vez de uma por item da lista.
    """
    if compra_id is None:
        return banco.df(
            "SELECT compra_id, data, preco, fonte, obtido_em "
            "  FROM precos_compras ORDER BY compra_id, data, id")
    return banco.df(
        "SELECT compra_id, data, preco, fonte, obtido_em "
        "  FROM precos_compras WHERE compra_id = ? ORDER BY data, id",
        (int(compra_id),))


def _resumo_da_serie(serie: pd.DataFrame) -> dict:
    """A leitura de uma serie de precos ja carregada.

    Separado de `resumo()` para que a pagina possa calcular o resumo de 40
    itens a partir de UMA consulta ao banco, sem 40 idas e voltas.
    """
    vazio_dict = {
        "n_pontos": 0, "atual": None, "data_atual": None, "conferido_em": None,
        "menor": None, "data_menor": None, "maior": None, "data_maior": None,
        "no_menor_preco": False, "acima_do_menor": None,
        "dias_acompanhando": 0, "variacao_total": None,
    }
    if serie is None or serie.empty:
        return vazio_dict

    ordenada = serie.sort_values(["data"])
    precos = ordenada["preco"].astype(float)

    ultimo = ordenada.iloc[-1]
    primeiro = ordenada.iloc[0]
    linha_menor = ordenada.loc[precos.idxmin()]
    linha_maior = ordenada.loc[precos.idxmax()]

    atual = float(ultimo["preco"])
    menor = float(linha_menor["preco"])

    inicio = pd.to_datetime(primeiro["data"], errors="coerce")
    dias = 0 if pd.isna(inicio) else max(0, (pd.Timestamp.today().normalize()
                                             - inicio.normalize()).days)

    return {
        "n_pontos": int(len(ordenada)),
        "atual": atual,
        "data_atual": str(ultimo["data"]),
        "conferido_em": (None if vazio(ultimo.get("obtido_em"))
                         else str(ultimo["obtido_em"])),
        "menor": menor,
        "data_menor": str(linha_menor["data"]),
        "maior": float(linha_maior["preco"]),
        "data_maior": str(linha_maior["data"]),
        "no_menor_preco": atual <= menor + 0.005,
        "acima_do_menor": (atual / menor - 1) if menor else None,
        "dias_acompanhando": dias,
        "variacao_total": (atual / float(primeiro["preco"]) - 1
                           if float(primeiro["preco"]) else None),
    }


def resumo(compra_id: int) -> dict:
    """Menor preco, maior preco e onde o preco de hoje esta entre os dois."""
    return _resumo_da_serie(historico(compra_id))


def resumos(df_historico: pd.DataFrame) -> dict[int, dict]:
    """O resumo de cada item, a partir do historico inteiro ja carregado."""
    if df_historico is None or df_historico.empty:
        return {}
    return {int(compra_id): _resumo_da_serie(serie)
            for compra_id, serie in df_historico.groupby("compra_id")}


# ----------------------------------------------------------------------------
# A busca na pagina da loja
# ----------------------------------------------------------------------------

def _baixar(url: str) -> tuple[str | None, str]:
    """Baixa o HTML da pagina. Devolve (html, "") ou (None, motivo legivel).

    O motivo e escrito para aparecer NA TELA, para voce. "HTTPError 403" nao
    diz nada a quem so queria saber o preco de um notebook; "a loja bloqueou o
    acesso automatico" diz, e ja indica a saida (digitar o preco a mao).
    """
    if vazio(url):
        return None, "sem link cadastrado"

    endereco = str(url).strip()
    if not endereco.lower().startswith(("http://", "https://")):
        return None, "o link não é um endereço http(s)"

    pedido = urllib.request.Request(endereco, headers=_CABECALHOS)
    try:
        with urllib.request.urlopen(pedido, timeout=_TIMEOUT) as resposta:
            bruto = resposta.read(_LIMITE_BYTES)
            codificacao = resposta.headers.get_content_charset() or "utf-8"
        return bruto.decode(codificacao, errors="replace"), ""
    except urllib.error.HTTPError as erro:
        if erro.code in (401, 403, 406, 429):
            return None, f"a loja bloqueou o acesso automático (HTTP {erro.code})"
        return None, f"a loja respondeu HTTP {erro.code}"
    except urllib.error.URLError as erro:
        return None, f"não consegui alcançar o site ({erro.reason})"
    except TimeoutError:
        return None, "a loja demorou demais para responder"
    except Exception as erro:                      # nunca derruba a pagina
        return None, f"falhou ao ler a página ({type(erro).__name__})"


def _precos_do_jsonld(html: str) -> list[float]:
    """Os precos declarados nos blocos JSON-LD da pagina.

    O bloco pode vir como objeto, como lista, ou embrulhado num "@graph" — as
    tres formas sao validas no padrao e todas aparecem em loja brasileira. E o
    preco pode estar em `offers.price`, `offers.lowPrice`, ou numa LISTA de
    ofertas (o mesmo produto em varios vendedores).
    """
    achados: list[float] = []

    def varrer(no):
        if isinstance(no, list):
            for item in no:
                varrer(item)
            return
        if not isinstance(no, dict):
            return
        for chave in ("@graph", "mainEntity", "itemListElement"):
            if chave in no:
                varrer(no[chave])
        ofertas = no.get("offers")
        if ofertas is not None:
            for oferta in (ofertas if isinstance(ofertas, list) else [ofertas]):
                if not isinstance(oferta, dict):
                    continue
                for campo in ("price", "lowPrice"):
                    valor = parse_brl(oferta.get(campo))
                    if valor and valor > 0:
                        achados.append(valor)
                varrer(oferta.get("offers"))

    for bloco in _RE_JSONLD.findall(html):
        try:
            varrer(json.loads(bloco.strip()))
        except (ValueError, TypeError):
            continue                       # bloco quebrado nao invalida os outros
    return achados


def ler_preco_da_pagina(url: str) -> tuple[float | None, str]:
    """Tenta descobrir o preco na pagina do link.

    Devolve `(preco, fonte)` quando acha — fonte e 'jsonld', 'og' ou
    'microdata' — e `(None, motivo)` quando nao acha, com o motivo escrito
    para ser mostrado na tela.

    Entre precos concorrentes na mesma pagina (varios vendedores do mesmo
    produto), fica com o MENOR: e o que voce pagaria se comprasse ali.
    """
    html, erro = _baixar(url)
    if html is None:
        return None, erro

    do_jsonld = _precos_do_jsonld(html)
    if do_jsonld:
        return min(do_jsonld), "jsonld"

    for expressao, nome in ((_RE_OG, "og"), (_RE_MICRODATA, "microdata")):
        encontrado = expressao.search(html)
        if encontrado:
            valor = parse_brl(encontrado.group(1))
            if valor and valor > 0:
                return valor, nome

    return None, ("não achei o preço no HTML — ou não é uma página de "
                  "produto, ou a loja monta o preço por JavaScript")


def rastreaveis(apenas_abertos: bool = True) -> pd.DataFrame:
    """Os itens da lista que tem link e, por isso, dao para consultar."""
    sql = ("SELECT id, item, link, preco_atual, preco_alvo, status "
           "  FROM futuras_compras "
           " WHERE link IS NOT NULL AND TRIM(link) <> ''")
    if apenas_abertos:
        marcas = ",".join("?" * len(STATUS_ABERTOS))
        return banco.df(f"{sql} AND status IN ({marcas}) ORDER BY id",
                        STATUS_ABERTOS)
    return banco.df(f"{sql} ORDER BY id")


def atualizar(ids=None, pausa: float = _INTERVALO) -> dict:
    """Consulta o preco de cada item com link e grava o que conseguir.

    Devolve um relatorio para a tela mostrar item a item:

        consultados   quantos links foram abertos
        mudaram       [(item, preco_antigo, preco_novo)]
        iguais        [item] — conferidos, preco nao mudou
        falhas        {item: motivo}

    NENHUMA FALHA E SILENCIOSA. Um rastreador que erra sem avisar e pior que
    nenhum: voce olha um preco de tres meses atras achando que e de hoje.

    A pausa entre uma loja e a proxima existe por educacao e por
    sobrevivencia: rajada de requisicao e o caminho curto para o bloqueio.
    """
    alvos = rastreaveis()
    if ids is not None:
        escolhidos = {int(i) for i in ids}
        alvos = alvos[alvos["id"].isin(escolhidos)]

    relatorio = {"consultados": 0, "mudaram": [], "iguais": [], "falhas": {}}
    if alvos.empty:
        return relatorio

    for posicao, (_, linha) in enumerate(alvos.iterrows()):
        if posicao and pausa:
            time.sleep(pausa)

        relatorio["consultados"] += 1
        nome = str(linha["item"])
        preco, fonte = ler_preco_da_pagina(linha["link"])

        if preco is None:
            relatorio["falhas"][nome] = fonte
            continue

        anterior = None if vazio(linha.get("preco_atual")) else float(linha["preco_atual"])
        mudou = registrar(int(linha["id"]), preco, fonte)

        banco.executar(
            "UPDATE futuras_compras SET preco_atual = ?, data_cotacao = ? "
            " WHERE id = ?",
            (preco, str(date.today()), int(linha["id"])),
        )

        if mudou and (anterior is None or abs(anterior - preco) >= 0.005):
            relatorio["mudaram"].append((nome, anterior, preco))
        else:
            relatorio["iguais"].append(nome)

    return relatorio
