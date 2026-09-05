"""
conferir_compras.py — prova que o rastreador de precos e o calendario nao mentem.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Duas coisas novas na lista de desejos podem enganar em silencio:

1. O HISTORICO DE PRECO. Se ele gravar um ponto por consulta, o grafico vira
   uma linha reta de 300 pontos iguais e o "menor preco ja visto" perde o
   sentido. Se gravar de menos, some a mudanca que voce queria ver. O ponto de
   equilibrio ("so grava quando o preco muda") e uma regra que ninguem confere
   no olho — mas o script confere.

2. O CALENDARIO DE COMPRAS. Ele diz "compre em mar/2027". Se a conta estourar
   o caixa do mes, a resposta e uma promessa que o seu orcamento nao paga —
   e e o tipo de erro que so aparece no dia da compra.

A BUSCA DE PRECO E TESTADA SEM REDE, DE PROPOSITO
--------------------------------------------------
Os tres formatos (JSON-LD, Open Graph, microdata) sao conferidos contra HTMLs
de exemplo escritos aqui dentro. Um teste que dependesse de a loja estar no ar
falharia por motivo errado — e, pior, PASSARIA por motivo errado no dia em que
a loja mudasse o preco. O que este script prova e a LEITURA; se a loja
responde ou bloqueia e outra coisa, e o app ja diz isso na tela.

O QUE ELE CONFERE
------------------
1. NAO DUPLICA PONTO    preco igual ao ultimo nao vira linha nova
2. GRAVA A MUDANCA      preco diferente vira ponto novo, na data certa
3. O RESUMO ACHA        menor, maior e "esta no menor preco" batem
4. LE OS TRES FORMATOS  jsonld, og e microdata, e a menor entre varias ofertas
5. FALHA FALANDO        pagina sem preco e link invalido devolvem MOTIVO
6. CALENDARIO CABE      nenhum mes gasta mais do que tem em caixa
7. CALENDARIO ORDENA    prioridade Alta vem antes, e o que nao cabe e marcado
8. VAZIO NAO QUEBRA     lista vazia e item sem preco passam sem excecao

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_compras
"""

from __future__ import annotations

from contextlib import contextmanager

import pandas as pd

from financas import banco, config, precos
from financas.calculos import compras
from financas.formato import mes_para_indice, vazio
from verificacao.base import Conferencia, banco_vazio


# ---------------------------------------------------------------------------
# HTMLs de exemplo — os tres formatos que as lojas publicam
# ---------------------------------------------------------------------------

HTML_JSONLD = """<html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Notebook",
 "offers":{"@type":"Offer","price":"3999.90","priceCurrency":"BRL"}}
</script></head><body>R$ 3.999,90</body></html>"""

HTML_JSONLD_GRAFO = """<html><head>
<script type="application/ld+json">
{"@graph":[{"@type":"WebPage"},
           {"@type":"Product","offers":[
              {"@type":"Offer","price":"4500.00"},
              {"@type":"Offer","price":"4199.00"}]}]}
</script></head><body></body></html>"""

HTML_OG = """<html><head>
<meta property="og:title" content="Tênis">
<meta property="og:price:amount" content="499.99">
</head><body></body></html>"""

HTML_MICRODATA = """<html><body>
<div itemscope itemtype="https://schema.org/Product">
  <meta itemprop="price" content="2.499,00">
</div></body></html>"""

HTML_SEM_PRECO = """<html><head><title>Loja</title></head>
<body><div class="preco-js" data-load="depois"></div></body></html>"""

HTML_JSONLD_QUEBRADO = """<html><head>
<script type="application/ld+json">{isto nao e json valido</script>
<meta property="og:price:amount" content="150.00">
</head></html>"""


@contextmanager
def pagina_falsa(html: str):
    """Troca o download por um HTML fixo — a leitura e testada, a rede nao."""
    original = precos._baixar
    precos._baixar = lambda url: (html, "")
    try:
        yield
    finally:
        precos._baixar = original


# ---------------------------------------------------------------------------
# As checagens
# ---------------------------------------------------------------------------

def conferir_nao_duplica(c: Conferencia) -> None:
    """Preco igual ao ultimo nao cria linha nova no historico."""
    print("=" * 78)
    print("1. NAO DUPLICA PONTO DE PRECO IGUAL")
    print("=" * 78)

    with banco_vazio("conferir_compras"):
        primeiro = precos.registrar(1, 4299.00, "manual", quando="2026-07-10")
        repetido = precos.registrar(1, 4299.00, "jsonld", quando="2026-07-20")
        de_novo = precos.registrar(1, 4299.00, "jsonld", quando="2026-08-01")

        pontos = precos.historico(1)
        c.exigir(primeiro, "o primeiro preco deveria ter sido gravado")
        c.exigir(not repetido, "preco repetido NAO deveria contar como novo")
        c.exigir(not de_novo, "preco repetido NAO deveria contar como novo")
        c.exigir(len(pontos) == 1,
                 f"tres consultas do mesmo preco deveriam deixar 1 ponto, "
                 f"deixaram {len(pontos)}")
        c.exigir(str(pontos.iloc[0]["data"]) == "2026-07-10",
                 "o ponto deveria guardar a data em que o preco APARECEU, "
                 f"veio {pontos.iloc[0]['data']}")
        print(f"  3 consultas de R$ 4.299,00 -> {len(pontos)} ponto, "
              f"data {pontos.iloc[0]['data']}")


def conferir_grava_mudanca(c: Conferencia) -> None:
    """Preco diferente entra como ponto novo; correcao no mesmo dia substitui."""
    print()
    print("=" * 78)
    print("2. GRAVA A MUDANCA, E CORRIGE O PONTO DO DIA")
    print("=" * 78)

    with banco_vazio("conferir_compras"):
        precos.registrar(1, 4299.00, quando="2026-07-10")
        mudou = precos.registrar(1, 3999.00, quando="2026-08-26")
        c.exigir(mudou, "preco diferente deveria contar como ponto novo")
        c.exigir(len(precos.historico(1)) == 2,
                 "dois precos diferentes deveriam deixar 2 pontos")

        precos.registrar(1, 3950.00, quando="2026-08-26")
        pontos = precos.historico(1)
        c.exigir(len(pontos) == 2,
                 f"corrigir o preco do MESMO dia nao pode criar um terceiro "
                 f"ponto, ficaram {len(pontos)}")
        c.exigir(abs(float(pontos.iloc[-1]["preco"]) - 3950.00) < 0.01,
                 "a correcao do dia deveria ter sobrescrito o valor")
        print(f"  4299 -> 3999 -> (mesmo dia) 3950 = {len(pontos)} pontos, "
              f"ultimo R$ {float(pontos.iloc[-1]['preco']):,.2f}")


def conferir_resumo(c: Conferencia) -> None:
    """Menor, maior e o aviso de 'esta no menor preco' batem com a serie."""
    print()
    print("=" * 78)
    print("3. O RESUMO ACHA O MENOR PRECO")
    print("=" * 78)

    with banco_vazio("conferir_compras"):
        precos.registrar(7, 4299.00, quando="2026-05-01")
        precos.registrar(7, 3750.00, quando="2026-06-01")
        precos.registrar(7, 4100.00, quando="2026-07-01")

        leitura = precos.resumo(7)
        c.exigir(abs(leitura["menor"] - 3750.00) < 0.01,
                 f"menor deveria ser 3750, veio {leitura['menor']}")
        c.exigir(leitura["data_menor"] == "2026-06-01",
                 f"a data do menor deveria ser 2026-06-01, veio "
                 f"{leitura['data_menor']}")
        c.exigir(abs(leitura["maior"] - 4299.00) < 0.01,
                 f"maior deveria ser 4299, veio {leitura['maior']}")
        c.exigir(not leitura["no_menor_preco"],
                 "4100 nao e o menor preco — o aviso nao deveria acender")

        precos.registrar(7, 3700.00, quando="2026-08-01")
        agora = precos.resumo(7)
        c.exigir(agora["no_menor_preco"],
                 "3700 e o menor de todos — o aviso deveria acender")

        # E o mesmo calculo a partir do historico inteiro, que e o caminho que
        # a tela usa: uma consulta so para a lista toda.
        muitos = precos.resumos(precos.historico())
        c.exigir(7 in muitos and muitos[7]["no_menor_preco"],
                 "resumos() a partir do historico inteiro deveria concordar "
                 "com resumo() de um item so")
        print(f"  serie 4299/3750/4100/3700 -> menor R$ "
              f"{agora['menor']:,.2f}, no menor preco: {agora['no_menor_preco']}")


def conferir_leitura_dos_formatos(c: Conferencia) -> None:
    """Os tres formatos padronizados sao lidos, e a menor oferta vence."""
    print()
    print("=" * 78)
    print("4. LE JSON-LD, OPEN GRAPH E MICRODATA (SEM REDE)")
    print("=" * 78)

    casos = [
        (HTML_JSONLD, 3999.90, "jsonld", "JSON-LD simples"),
        (HTML_JSONLD_GRAFO, 4199.00, "jsonld", "JSON-LD em @graph, 2 ofertas"),
        (HTML_OG, 499.99, "og", "Open Graph"),
        (HTML_MICRODATA, 2499.00, "microdata", "microdata em formato BR"),
        (HTML_JSONLD_QUEBRADO, 150.00, "og", "JSON-LD quebrado cai no og"),
    ]
    for html, esperado, fonte_esperada, descricao in casos:
        with pagina_falsa(html):
            preco, fonte = precos.ler_preco_da_pagina("https://loja.exemplo/p")
        c.exigir(preco is not None and abs(preco - esperado) < 0.01,
                 f"{descricao}: esperava {esperado}, veio {preco}")
        c.exigir(fonte == fonte_esperada,
                 f"{descricao}: esperava fonte {fonte_esperada}, veio {fonte}")
        print(f"  {descricao:<34} -> R$ {preco:>10,.2f}  ({fonte})")


def conferir_falha_falando(c: Conferencia) -> None:
    """Quando nao da, a resposta e um MOTIVO legivel — nunca um preco chutado."""
    print()
    print("=" * 78)
    print("5. FALHA DIZENDO O MOTIVO")
    print("=" * 78)

    with pagina_falsa(HTML_SEM_PRECO):
        preco, motivo = precos.ler_preco_da_pagina("https://loja.exemplo/p")
    c.exigir(preco is None, "pagina sem preco nao pode devolver numero")
    c.exigir(len(motivo) > 15 and "preço" in motivo.lower(),
             f"o motivo deveria explicar o que houve, veio {motivo!r}")
    print(f"  página sem preço -> {motivo}")

    preco, motivo = precos.ler_preco_da_pagina("isto-nao-e-um-link")
    c.exigir(preco is None, "link invalido nao pode devolver numero")
    c.exigir("http" in motivo, f"o motivo deveria citar o http, veio {motivo!r}")
    print(f"  link inválido    -> {motivo}")

    preco, motivo = precos.ler_preco_da_pagina(None)
    c.exigir(preco is None and "link" in motivo,
             f"link vazio deveria falar de link, veio {motivo!r}")
    print(f"  sem link         -> {motivo}")


def _lista(**kwargs) -> dict:
    """Uma linha da lista de desejos ja calculada, com padroes."""
    base = {"id": 1, "item": "Item", "prioridade": "Média",
            "preco_referencia": 1000.0, "mes_alvo": None, "em_aberto": True}
    base.update(kwargs)
    return base


def conferir_calendario_cabe(c: Conferencia) -> None:
    """Nenhum mes do calendario gasta mais do que ha em caixa."""
    print()
    print("=" * 78)
    print("6. O CALENDARIO NAO ESTOURA O CAIXA")
    print("=" * 78)

    itens = pd.DataFrame([
        _lista(id=1, item="Notebook", prioridade="Alta", preco_referencia=6000.0),
        _lista(id=2, item="Tênis", prioridade="Baixa", preco_referencia=500.0),
        _lista(id=3, item="Fone", prioridade="Média", preco_referencia=900.0),
    ])
    meses = ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02"]
    projecao = pd.DataFrame({"mes": meses, "saldo_mes": [2000.0] * len(meses)})

    agenda = compras.calendario(itens, projecao, 0.0, "2026-09", n_meses=6)
    agendados = agenda[agenda["mes_sugerido"].notna()]

    # A conta refeita por fora: mes a mes, a sobra acumula e as compras saem.
    caixa = 0.0
    estourou = []
    for passo, mes in enumerate(meses):
        caixa += 2000.0
        gasto_no_mes = float(
            agendados[agendados["mes_sugerido"] == mes]["preco_referencia"].sum())
        if gasto_no_mes > caixa + 0.01:
            estourou.append(f"{mes}: gastou {gasto_no_mes} com {caixa} em caixa")
        caixa -= gasto_no_mes

    c.exigir(not estourou, f"o calendario estourou o caixa: {estourou}")
    c.exigir(len(agendados) == 3, "os tres itens deveriam caber em 6 meses")
    for _, linha in agenda.iterrows():
        print(f"  {linha['item']:<12} {linha['prioridade']:<7} "
              f"R$ {linha['preco_referencia']:>8,.2f} -> {linha['mes_sugerido']}")


def conferir_calendario_ordena(c: Conferencia) -> None:
    """A fila respeita a prioridade, e o que nao cabe aparece marcado."""
    print()
    print("=" * 78)
    print("7. A FILA RESPEITA A PRIORIDADE, E MARCA O QUE NAO CABE")
    print("=" * 78)

    itens = pd.DataFrame([
        _lista(id=1, item="Caro e prioritário", prioridade="Alta",
               preco_referencia=5000.0, mes_alvo="2026-10"),
        _lista(id=2, item="Barato e sem pressa", prioridade="Baixa",
               preco_referencia=200.0),
        _lista(id=3, item="Fora do alcance", prioridade="Baixa",
               preco_referencia=90_000.0),
        _lista(id=4, item="Já comprado", prioridade="Alta",
               preco_referencia=100.0, em_aberto=False),
    ])
    # Seis meses de R$ ····: o item Alta de R$ ···· so cabe no quinto mes, e
    # ate la ele SEGURA a fila — e exatamente isso que o teste quer provar.
    projecao = pd.DataFrame({
        "mes": ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01", "2027-02"],
        "saldo_mes": [1000.0] * 6,
    })
    agenda = compras.calendario(itens, projecao, 0.0, "2026-09", n_meses=6)
    por_item = {linha["item"]: linha for _, linha in agenda.iterrows()}

    caro = por_item["Caro e prioritário"]
    barato = por_item["Barato e sem pressa"]
    fora = por_item["Fora do alcance"]

    c.exigir("Já comprado" not in por_item,
             "item fora de aberto nao deveria entrar no calendario")
    c.exigir(not vazio(caro["mes_sugerido"]),
             "o item de prioridade Alta deveria caber em 6 meses")
    c.exigir(vazio(barato["mes_sugerido"])
             or mes_para_indice(str(barato["mes_sugerido"]))
             >= mes_para_indice(str(caro["mes_sugerido"])),
             "o item Baixa NAO pode furar a fila do item Alta, mesmo sendo "
             "mais barato")
    c.exigir(vazio(fora["mes_sugerido"]),
             "um item de R$ 90.000 nao cabe em 6 meses de R$ 1.000")
    c.exigir(not bool(fora["cabe_no_alvo"]),
             "o que nao cabe no horizonte tem de sair marcado, nao sumir")
    c.exigir(not bool(caro["cabe_no_alvo"]),
             "o item cabe em nov, depois do mes-alvo out — deveria estar "
             "marcado como fora do prazo")
    print(f"  Alta R$ 5.000 (queria out) -> {caro['mes_sugerido']}, "
          f"no prazo: {caro['cabe_no_alvo']}")
    print(f"  Baixa R$ 200 (atrás na fila) -> {barato['mes_sugerido']}")
    print(f"  R$ 90.000 -> {fora['mes_sugerido']} (marcado, não escondido)")


def conferir_vazio_nao_quebra(c: Conferencia) -> None:
    """Lista vazia, item sem preco e historico inexistente passam sem excecao."""
    print()
    print("=" * 78)
    print("8. VAZIO NAO QUEBRA")
    print("=" * 78)

    c.exigir(compras.calendario(pd.DataFrame(), None, 500.0, "2026-09").empty,
             "calendario de lista vazia deveria devolver DataFrame vazio")

    sem_preco = pd.DataFrame([_lista(preco_referencia=0.0)])
    c.exigir(compras.calendario(sem_preco, None, 500.0, "2026-09").empty,
             "item sem preco nao tem como ser agendado")

    sem_projecao = compras.calendario(
        pd.DataFrame([_lista(preco_referencia=900.0)]), None, 500.0,
        "2026-09", n_meses=6)
    c.exigir(not sem_projecao.empty and not vazio(sem_projecao.iloc[0]["mes_sugerido"]),
             "sem projecao, o calendario deveria usar a capacidade mensal")

    with banco_vazio("conferir_compras"):
        c.exigir(precos.historico(999).empty,
                 "historico de item sem preco deveria vir vazio")
        c.exigir(precos.resumo(999)["n_pontos"] == 0,
                 "resumo de item sem historico deveria vir zerado")
        c.exigir(precos.resumos(pd.DataFrame()) == {},
                 "resumos de historico vazio deveria ser um dicionario vazio")
        c.exigir(not precos.registrar(1, None),
                 "registrar preco vazio nao deveria gravar nada")
        c.exigir(not precos.registrar(1, 0.0),
                 "registrar preco zero nao deveria gravar nada")
        relatorio = precos.atualizar(pausa=0)
        c.exigir(relatorio["consultados"] == 0,
                 "sem itens com link, nada deveria ser consultado")
    print("  lista vazia, item sem preço, sem projeção e sem histórico: ok")


def main() -> int:
    """Roda as oito conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("CONFERINDO O RASTREADOR DE PRECOS E O CALENDARIO DE COMPRAS")
    print()

    c = Conferencia()
    conferir_nao_duplica(c)
    conferir_grava_mudanca(c)
    conferir_resumo(c)
    conferir_leitura_dos_formatos(c)
    conferir_falha_falando(c)
    conferir_calendario_cabe(c)
    conferir_calendario_ordena(c)
    conferir_vazio_nao_quebra(c)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
