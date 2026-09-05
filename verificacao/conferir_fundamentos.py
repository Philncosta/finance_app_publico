"""
conferir_fundamentos.py — prova que a analise de papel nao inventa numero.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Uma tela de analise de acao e o lugar mais facil do app para mentir com cara de
competencia. Sao numeros de aparencia tecnica, vindos de uma fonte que nao e
oficial, sobre empresas que voce nao conhece de perto. Se um deles estiver
errado, nada quebra: aparece um multiplo plausivel e voce decide em cima dele.

Sao quatro formas de mentir, e as quatro ja apareceram no dado real:

1. **Multiplo negativo.** O IREN chega com `forwardPE = -172,9`. Impresso como
   esta, vira "P/L de -172", que nao quer dizer coisa nenhuma — P/L pressupoe
   lucro, e essa empresa da prejuizo.
2. **Vazio que parece defeito.** Um traco no cartao de P/L faz voce achar que a
   busca falhou. A verdade e informacao: a empresa nao da lucro.
3. **Campo de empresa em cima de fundo.** ETF nao tem caixa nem divida
   proprios. Desenhar "A empresa aguenta?" para um ETF e perguntar de uma
   empresa que nao existe.
4. **O nome do fundo alavancado.** "2X Long IREN" sugere o dobro do IREN. No
   periodo medido o IREN fez -35,8%, o dobro seria -71,5%, e o IRE entregou
   -89,5%. Quem le so o nome erra por 17,9 pontos.

O QUE ELE CONFERE
-----------------
1. MULTIPLO      P/L so existe com lucro positivo; com prejuizo devolve None
2. FOLEGO        so existe quando a empresa QUEIMA caixa; quem gera devolve None
3. ALAVANCAGEM   os tres padroes de nome das gestoras, e os falsos positivos
4. DECAIMENTO    2x por dia nao e 2x no periodo, e a conta bate por fora
5. EXPOSICAO     alavancado conta pelo fator, e o total supera a soma das linhas
6. VAZIO         papel sem dado devolve tem_dado=False, nunca campo zerado
7. OFFLINE       sem rede, o que ja esta guardado continua servindo

O ITEM 2 E O MENOS OBVIO. A tentacao e devolver um numero enorme quando a
empresa gera caixa ("folego de 9.999 meses"). Isso e pior que None: o cartao
fica preenchido, com cara de medicao, respondendo uma pergunta que nao se
aplica.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_fundamentos
"""

from __future__ import annotations

from financas import fundamentos
from financas.calculos import investimentos as inv
from verificacao.base import Conferencia


def conferir_multiplo(c: Conferencia) -> None:
    """P/L com prejuizo nao existe — e o negativo da fonte e lixo, nao dado."""
    print("=" * 78)
    print("1. MULTIPLO SO EXISTE COM LUCRO")
    print("=" * 78)

    casos = [
        (25.0, 3.10, 25.0, "empresa lucrativa: passa"),
        (-172.9, -2.22, None, "prejuizo: o negativo da fonte vira None"),
        (30.0, -0.57, None, "prejuizo com multiplo positivo: ainda assim None"),
        (None, 3.10, None, "campo ausente continua ausente"),
        (0.0, 3.10, None, "zero nao e multiplo"),
    ]
    for valor, lucro, esperado, descricao in casos:
        obtido = fundamentos._multiplo_valido(valor, lucro)
        c.exigir(obtido == esperado,
                 f"multiplo({valor}, lucro={lucro}): esperado {esperado}, "
                 f"veio {obtido}")
        print(f"  {descricao:<52} {str(obtido):>8}")

    for ticker in ("IREN", "DGXX"):
        ficha = fundamentos.ficha(ticker)
        if not ficha.get("tem_dado"):
            continue
        if ficha.get("da_lucro") is False:
            c.exigir(ficha["pl"] is None and ficha["pl_projetado"] is None,
                     f"{ticker}: da prejuizo mas veio com P/L "
                     f"{ficha['pl']}/{ficha['pl_projetado']}")
            c.exigir(any("prejuízo" in m for m in ficha["motivos"]),
                     f"{ticker}: sem P/L e sem explicar por que — o vazio "
                     f"sozinho parece falha de busca")
            print(f"  {ticker}: sem P/L, com a frase explicando o motivo")


def conferir_folego(c: Conferencia) -> None:
    """Folego de caixa so responde para quem queima caixa."""
    print()
    print("=" * 78)
    print("2. FOLEGO SO EXISTE PARA QUEM QUEIMA CAIXA")
    print("=" * 78)

    casos = [
        ({"totalCash": 1200, "freeCashflow": -1200}, 12.0, "queima: 12 meses"),
        ({"totalCash": 6_084_700_160, "freeCashflow": -4_237_871_104}, 17.2,
         "IREN de verdade: ~17 meses"),
        ({"totalCash": 62_000_000_000, "freeCashflow": 90_000_000_000}, None,
         "gera caixa: None, nunca um numero enorme"),
        ({"totalCash": 100, "freeCashflow": 0}, None, "fluxo zero: None"),
        ({"totalCash": None, "freeCashflow": -50}, None, "sem caixa: None"),
    ]
    for dados, esperado, descricao in casos:
        obtido, _fluxo = fundamentos._folego_de_caixa(dados)
        if esperado is None:
            ok = obtido is None
        else:
            ok = obtido is not None and abs(obtido - esperado) < 0.15
        c.exigir(ok, f"folego {dados}: esperado {esperado}, veio {obtido}")
        marca = "—" if obtido is None else f"{obtido:.1f}"
        print(f"  {descricao:<52} {marca:>8}")


def conferir_alavancagem(c: Conferencia) -> None:
    """Os tres jeitos de nomear um fundo alavancado, e o que NAO e um."""
    print()
    print("=" * 78)
    print("3. ALAVANCAGEM LIDA NO NOME DO FUNDO")
    print("=" * 78)

    casos = [
        ("Defiance Daily Target 2X Long IREN ETF", 2, "IREN"),
        ("Direxion Daily TSLA Bull 2X Shares", 2, "TSLA"),
        ("Direxion Daily NVDA Bear 2X Shares", -2, "NVDA"),
        ("Direxion Daily Semiconductor Bear 3X Shares", -3, None),
        ("Apple Inc.", None, None),
        ("iShares Core S&P 500 ETF", None, None),
        ("Vanguard Total Stock Market ETF", None, None),
        ("", None, None),
        (None, None, None),
    ]
    for nome, fator, alvo in casos:
        obtido = fundamentos.alavancagem(nome)
        if fator is None:
            c.exigir(obtido is None,
                     f"{nome!r}: nao e alavancado, mas veio {obtido}")
        else:
            c.exigir(obtido is not None and obtido["fator"] == fator,
                     f"{nome!r}: fator esperado {fator}, veio {obtido}")
            c.exigir(obtido is not None and obtido["subjacente"] == alvo,
                     f"{nome!r}: alvo esperado {alvo}, veio {obtido}")
        print(f"  {str(nome)[:46]:<46} {str(obtido and obtido['fator']):>5} "
              f"{str(obtido and obtido['subjacente'] or ''):>6}")

    ficha = fundamentos.ficha("IRE")
    if ficha.get("tem_dado"):
        alavanca = ficha.get("alavancagem")
        c.exigir(alavanca is not None and alavanca["subjacente"] == "IREN",
                 f"IRE: a fonte classifica como acao comum; o nome dela diz "
                 f"2X Long IREN, e e o nome que esta certo. Veio {alavanca}")
        c.exigir(ficha["caixa"] is None and ficha["pl"] is None,
                 "IRE: fundo nao pode aparecer com caixa nem P/L proprios")


def conferir_decaimento(c: Conferencia) -> None:
    """2x por dia nao e 2x no periodo — e a diferenca cresce com a oscilacao."""
    print()
    print("=" * 78)
    print("4. 2X POR DIA NAO E 2X NO PERIODO")
    print("=" * 78)

    conta = fundamentos.decaimento(-0.895, -0.358, 2)
    c.exigir(abs(conta["esperado"] - (-0.716)) < 1e-9,
             f"esperado deveria ser 2x -35,8% = -71,6%, veio {conta['esperado']}")
    c.exigir(conta["diferenca"] < 0,
             "o alavancado entregou PIOR que o dobro; a diferenca tem de ser "
             "negativa")
    print(f"  IREN -35,8% · 2x seria {conta['esperado']*100:.1f}% · "
          f"IRE {conta['real']*100:.1f}% · dif {conta['diferenca']*100:+.1f} p.p.")

    preco_alvo, preco_2x = 100.0, 100.0
    for variacao in (0.10, -0.10) * 10:
        preco_alvo *= 1 + variacao
        preco_2x *= 1 + variacao * 2
    retorno_alvo = preco_alvo / 100 - 1
    retorno_2x = preco_2x / 100 - 1
    simulado = fundamentos.decaimento(retorno_2x, retorno_alvo, 2)
    c.exigir(simulado["diferenca"] < -0.01,
             f"20 dias de +10%/-10%: o 2x deveria ficar bem atras do dobro, "
             f"veio diferenca {simulado['diferenca']:.4f}")
    print(f"  simulado (+10%/-10% x10): alvo {retorno_alvo*100:>6.2f}% · "
          f"2x seria {simulado['esperado']*100:>6.2f}% · "
          f"real {retorno_2x*100:>6.2f}%")

    sem_oscilacao = fundamentos.decaimento(0.0, 0.0, 2)
    c.exigir(sem_oscilacao["diferenca"] == 0,
             "sem movimento nao ha decaimento nenhum")


def conferir_exposicao(c: Conferencia) -> None:
    """O alavancado conta pelo fator, e o total supera a soma das linhas."""
    print()
    print("=" * 78)
    print("5. EXPOSICAO ECONOMICA CONTA A ALAVANCAGEM")
    print("=" * 78)

    desempenho = inv.desempenho_da_carteira()
    tabela = inv.exposicao_economica(desempenho)
    if tabela.empty:
        print("  (sem papel com ticker — pule)")
        return

    for _, linha in tabela.iterrows():
        soma = float(linha["direta"]) + float(linha["via_alavancado"])
        c.exigir(abs(float(linha["exposicao"]) - soma) < 0.01,
                 f"{linha['papel']}: exposicao nao e a soma das partes")
        c.exigir(float(linha["exposicao"]) >= float(linha["direta"]) - 0.01,
                 f"{linha['papel']}: exposicao menor que a posicao direta")
        print(f"  {linha['papel']:<6} direta {linha['direta']:>12,.2f} + "
              f"via fundo {linha['via_alavancado']:>10,.2f} = "
              f"{linha['exposicao']:>12,.2f}")

    com_fundo = tabela[tabela["via_alavancado"] > 0]
    if not com_fundo.empty:
        alvo = com_fundo.iloc[0]
        fator = float(alvo["fator"])
        posicao_do_fundo = float(alvo["via_alavancado"]) / abs(fator)
        soma_das_linhas = float(alvo["direta"]) + posicao_do_fundo
        c.exigir(float(alvo["exposicao"]) > soma_das_linhas + 0.01,
                 f"{alvo['papel']}: a exposicao real tem de SUPERAR a soma das "
                 f"linhas da tela — e o ponto inteiro desta conta. "
                 f"{alvo['exposicao']:.2f} contra {soma_das_linhas:.2f}")
        print(f"  {alvo['papel']}: soma das linhas da tela "
              f"R$ {soma_das_linhas:,.2f} contra exposicao real "
              f"R$ {float(alvo['exposicao']):,.2f}")


def conferir_vazio(c: Conferencia) -> None:
    """Papel desconhecido devolve tem_dado=False, nunca campo zerado."""
    print()
    print("=" * 78)
    print("6. SEM DADO E SEM DADO, NAO E ZERO")
    print("=" * 78)

    for ticker in ("", "   ", "ZZZZTICKERQUENAOEXISTE"):
        ficha = fundamentos.ficha(ticker)
        c.exigir(ficha.get("tem_dado") is False,
                 f"{ticker!r}: deveria devolver tem_dado=False, veio {ficha}")
        c.exigir("caixa" not in ficha or ficha.get("caixa") is None,
                 f"{ticker!r}: sem dado nao pode trazer caixa")
    print("  ticker vazio, so espaco e inexistente: tem_dado=False nos tres")

    ficha = fundamentos.ficha("IREN")
    if ficha.get("tem_dado"):
        for campo in ("pl", "pl_projetado", "folego_meses", "alvo"):
            valor = ficha.get(campo)
            c.exigir(valor is None or isinstance(valor, (int, float)),
                     f"IREN.{campo}: nem None nem numero, veio {valor!r}")
        c.exigir(ficha.get("obtido_em") is not None,
                 "ficha com dado tem de dizer de quando ele e")
        print(f"  IREN: ficha datada de {ficha['obtido_em']}")


def conferir_offline(c: Conferencia) -> None:
    """Sem rede, o que ja esta guardado continua servindo."""
    print()
    print("=" * 78)
    print("7. SEM INTERNET, O GUARDADO SEGUE DE PE")
    print("=" * 78)

    antes = fundamentos.ficha("IREN")
    if not antes.get("tem_dado"):
        print("  (nada guardado para IREN — pule)")
        return

    import builtins
    original = builtins.__import__

    def cair(nome, *args, **kwargs):
        if nome == "yfinance":
            raise ImportError("rede fora — simulado pelo teste")
        return original(nome, *args, **kwargs)

    builtins.__import__ = cair
    try:
        c.exigir(fundamentos.buscar("ZZZNOVOTICKER") is None,
                 "sem a biblioteca, buscar() deveria devolver None")
        depois = fundamentos.ficha("IREN", buscar_agora=True)
        c.exigir(depois.get("tem_dado") is True,
                 "offline, a ficha ja guardada tem de continuar servindo")
        c.exigir(depois.get("caixa") == antes.get("caixa"),
                 "a falha de rede alterou o que estava guardado")
    finally:
        builtins.__import__ = original
    print("  rede derrubada: ficha guardada intacta, busca nova devolve None")


def conferir_sufixo_da_b3(c: Conferencia) -> None:
    """Codigo da B3 ganha `.SA`; ticker americano nao pode ser tocado."""
    print()
    print("=" * 78)
    print("8. O SUFIXO .SA, SO ONDE ELE PERTENCE")
    print("=" * 78)

    from ui.analise import _com_sufixo_da_bolsa as com_sufixo

    # Ele digitou DIVO11, o Yahoo respondeu 404 e a tela disse "nao achei
    # fundamentos" — verdade tecnica, inutil na pratica: o dado existia como
    # DIVO11.SA. A regra so vale porque as duas formas nao se confundem.
    da_b3 = ["PETR4", "BBAS3", "DIVO11", "HGLG11", "GOLD11", "TASA3"]
    for codigo in da_b3:
        obtido = com_sufixo(codigo)
        c.exigir(obtido == f"{codigo}.SA",
                 f"«{codigo}» e da B3 e deveria virar «{codigo}.SA», "
                 f"veio «{obtido}»")

    # O outro lado importa mais: acrescentar .SA num ticker americano
    # quebraria a busca que HOJE funciona.
    de_fora = ["AAPL", "NVDA", "IREN", "DGXX", "IRE", "VT", "VOO", "NOBL",
               "BRK-B", "TSLA"]
    for codigo in de_fora:
        obtido = com_sufixo(codigo)
        c.exigir(obtido == codigo,
                 f"«{codigo}» nao e da B3 e nao pode ser alterado, "
                 f"veio «{obtido}»")

    c.exigir(com_sufixo("PETR4.SA") == "PETR4.SA",
             "quem ja tem o sufixo nao pode ganhar outro")

    print(f"  {len(da_b3)} codigos da B3   -> ganharam .SA")
    print(f"  {len(de_fora)} tickers de fora -> intactos")
    print("  PETR4.SA          -> intacto (nao duplica o sufixo)")


def conferir_botao_forca(c: Conferencia) -> None:
    """O botao "Buscar dados de novo" precisa realmente ir a fonte."""
    print()
    print("=" * 78)
    print("9. \"BUSCAR DADOS DE NOVO\" FORCA DE VERDADE")
    print("=" * 78)

    # `ficha(buscar_agora=True)` chamava `buscar()` sem `forcar`, e `buscar`
    # devolve o guardado quando a data e a de hoje. No mesmo dia, o botao nao
    # buscava nada — e o dia em que voce aperta o botao e justamente aquele em
    # que desconfia do guardado.
    chamadas = []
    original = fundamentos.buscar

    def espiao(ticker, forcar=False):
        chamadas.append(forcar)
        return original(ticker, forcar=forcar)

    fundamentos.buscar = espiao
    try:
        fundamentos.ficha("IREN", buscar_agora=True)
    finally:
        fundamentos.buscar = original

    c.exigir(chamadas and chamadas[0] is True,
             f"o botao tem de chamar buscar(forcar=True); as chamadas foram "
             f"{chamadas}")
    print(f"  ficha(buscar_agora=True) -> buscar(forcar={chamadas[0] if chamadas else '?'})")


def main() -> int:
    """Roda as nove conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("#" * 78)
    print("#  CONFERINDO A ANALISE DE PAPEL")
    print("#" * 78)
    print()
    c = Conferencia()
    conferir_multiplo(c)
    conferir_folego(c)
    conferir_alavancagem(c)
    conferir_decaimento(c)
    conferir_exposicao(c)
    conferir_vazio(c)
    conferir_offline(c)
    conferir_sufixo_da_b3(c)
    conferir_botao_forca(c)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
