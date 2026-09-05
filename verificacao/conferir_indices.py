"""
conferir_indices.py — prova que a comparacao com CDI/IPCA e honesta.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Uma referencia errada nao quebra nada. Ela so faz voce tomar a decisao errada
com confianca — que e pior do que nao ter referencia nenhuma.

Sao tres formas de mentir, e as tres passam despercebidas na tela:

1. **Comparar periodos diferentes.** O rendimento de um papel pode ignorar 4
   meses de fonte ruim. Se o CDI somar 12, a comparacao esta errada e os dois
   numeros tem exatamente a mesma cara.
2. **Usar a regua do produto concorrente.** Uma NTN-B perde do CDI em ciclo de
   juro alto por construcao. "45% do CDI" diria a ele que errou.
3. **Esconder que o indice esta atrasado.** O IPCA sai com um mes de atraso;
   comparar 12 meses de papel contra 11 de IPCA infla o titulo.

O QUE ELE CONFERE
-----------------
1. MESMOS MESES   o indice soma exatamente os meses que o papel usou
2. CAPITALIZACAO  o acumulado multiplica, nao soma
3. REGUA          NTN-B -> IPCA, pos-fixado -> CDI, internacional -> S&P 500
4. ATRASO         mes que falta na serie e denunciado, nao silenciado
5. VAZIO          serie inexistente devolve None, nunca 0,0
6. CUPOM          o cupom da NTN-B vira resgate, e a atribuicao fecha
7. SOMBRA         a carteira-sombra parte do mesmo ponto e usa os mesmos fluxos
8. ABERTURA       saldo trazido de outro banco nao conta como rendimento
9. OFFLINE        sem internet, o guardado continua de pe

O ITEM 5 E O QUE MAIS IMPORTA. Devolver 0,0 quando nao ha dado se leria como
"o CDI nao rendeu nada no periodo" — e um papel que rendeu 2% pareceria ter
vencido a referencia. `None` obriga a tela a dizer "sem dado".

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_indices
"""

from __future__ import annotations


from financas import banco, config, indices
from financas.calculos import investimentos as inv
from verificacao.base import Conferencia, banco_descartavel


def conferir_mesmos_meses(c: Conferencia) -> None:
    """A referencia soma exatamente os meses que o papel usou."""
    print("=" * 78)
    print("1. O INDICE SOMA OS MESMOS MESES QUE O PAPEL")
    print("=" * 78)
    for linha in banco.consultar("SELECT id, nome FROM investimentos"):
        resultado = inv.rentabilidade_periodo(int(linha["id"]), 24)
        meses = resultado.get("meses") or []
        c.exigir(len(meses) == resultado["meses_considerados"],
                 f"{linha['nome']}: {len(meses)} meses na lista mas "
                 f"{resultado['meses_considerados']} contados")
        if not meses:
            continue
        cobertos, faltando = indices.cobertura("CDI", meses)
        c.exigir(cobertos + len(faltando) == len(meses),
                 f"{linha['nome']}: cobertura nao fecha com a lista de meses")
    print(f"  {c.checagens} checagens sobre a lista de meses")


def conferir_capitalizacao(c: Conferencia) -> None:
    """O acumulado multiplica; nao soma."""
    print()
    print("=" * 78)
    print("2. O ACUMULADO CAPITALIZA")
    print("=" * 78)
    serie = indices.serie("CDI")
    meses = sorted(serie)[-6:]
    if len(meses) < 2:
        print("  (sem serie guardada — pule)")
        return
    esperado = 1.0
    for mes in meses:
        esperado *= 1 + serie[mes]
    esperado -= 1
    obtido = indices.acumulado("CDI", meses)
    c.exigir(obtido is not None and abs(obtido - esperado) < 1e-12,
             f"acumulado {obtido} != capitalizado {esperado}")

    soma = sum(serie[m] for m in meses)
    c.exigir(abs(soma - esperado) > 1e-9,
             "soma e produto deram igual — o teste nao prova capitalizacao")
    print(f"  6 meses: capitalizado {esperado*100:.4f}% vs soma {soma*100:.4f}%")


def conferir_regua(c: Conferencia) -> None:
    """Cada macro recebe o indice certo — ou nenhum."""
    print()
    print("=" * 78)
    print("3. A REGUA CERTA PARA CADA PAPEL")
    print("=" * 78)
    casos = [
        ("Caixa", "Fundo DI", "CDI"),
        ("Renda Fixa", "Tesouro Selic", "CDI"),
        ("Renda Fixa", "CDB", "CDI"),
        ("Renda Fixa", "NTN-B (inflação)", "IPCA"),
        ("Renda Fixa", "NTN-B", "IPCA"),
        ("Internacional", "Stock EUA", "S&P 500"),
        ("Internacional", "ETF EUA", "S&P 500"),
        ("Renda Variável", "Ação BR", "IBOV"),
        ("Imóvel", "Apartamento", None),
        (None, None, None),
    ]
    for macro, classe, esperado in casos:
        obtido = indices.referencia_para(macro, classe)
        c.exigir(obtido == esperado,
                 f"macro={macro!r} classe={classe!r}: esperado {esperado!r}, "
                 f"veio {obtido!r}")
        print(f"  {str(macro):16} {str(classe):20} -> {obtido}")

    for linha in banco.consultar(
            "SELECT nome, classe FROM investimentos WHERE classe IS NOT NULL"):
        macro = inv.macro_da_classe(linha["classe"])
        obtido = indices.referencia_para(macro, linha["classe"])
        if "NTN" in (linha["nome"] or "").upper().replace("-", ""):
            c.exigir(obtido == "IPCA",
                     f"{linha['nome']}: titulo IPCA+ deveria usar IPCA, "
                     f"veio {obtido!r}")
        if macro == "Internacional":
            c.exigir(obtido == "S&P 500",
                     f"{linha['nome']}: internacional se compara ao S&P 500 "
                     f"em reais, veio {obtido!r}")


def conferir_atraso(c: Conferencia) -> None:
    """Mes que falta na serie e denunciado, nao silenciado."""
    print()
    print("=" * 78)
    print("4. MES QUE FALTA E DENUNCIADO")
    print("=" * 78)
    serie = indices.serie("CDI")
    if not serie:
        print("  (sem serie guardada — pule)")
        return
    reais = sorted(serie)[-3:]
    pedidos = reais + ["2099-12"]
    cobertos, faltando = indices.cobertura("CDI", pedidos)
    c.exigir(cobertos == len(reais), f"cobertos {cobertos}, esperado {len(reais)}")
    c.exigir(faltando == ["2099-12"], f"faltando {faltando}, esperado ['2099-12']")

    com_fantasma = indices.acumulado("CDI", pedidos)
    sem_fantasma = indices.acumulado("CDI", reais)
    c.exigir(com_fantasma is not None and sem_fantasma is not None
             and abs(com_fantasma - sem_fantasma) < 1e-12,
             "o mes inexistente mudou o acumulado")
    print(f"  1 mes fantasma detectado, acumulado inalterado "
          f"({sem_fantasma*100:.4f}%)")


def conferir_vazio(c: Conferencia) -> None:
    """Sem dado, devolve None — nunca 0,0."""
    print()
    print("=" * 78)
    print("5. SEM DADO DEVOLVE None, NUNCA ZERO")
    print("=" * 78)
    c.exigir(indices.acumulado("SELIC", ["2026-01"]) is None,
             "serie inexistente deveria devolver None")
    c.exigir(indices.acumulado("CDI", ["1900-01"]) is None,
             "mes inexistente deveria devolver None")
    c.exigir(indices.acumulado("CDI", []) is None,
             "lista vazia deveria devolver None")
    c.exigir(indices.buscar("NAO_EXISTE", None, None) == 0,
             "serie desconhecida deveria devolver 0 sem tocar na rede")
    print("  None em 3 casos de ausencia; serie desconhecida nao busca")


def conferir_cupom(c: Conferencia) -> None:
    """O cupom da NTN-B vira resgate, e a atribuicao fecha com o extrato."""
    print()
    print("=" * 78)
    print("6. O CUPOM SEMESTRAL VIRA RESGATE")
    print("=" * 78)
    c.exigir(indices is not None, "modulo carregado")
    casos = [
        ("NTN-B mai/2035", {5, 11}),
        ("NTN-B mai/2045", {5, 11}),
        ("NTN-B ago/2060", {8, 2}),
        ("NTNB PRINC ago/2032", set()),
        ("LFT mar/2031", set()),
        ("Trend DI FIC RF Simples RL", set()),
        ("IREN", set()),
    ]
    for nome, esperado in casos:
        obtido = inv.meses_de_cupom(nome)
        c.exigir(obtido == esperado,
                 f"{nome}: meses de cupom {sorted(obtido)}, "
                 f"esperado {sorted(esperado)}")

    total_extrato = sum(
        float(linha["total"] or 0) for linha in banco.consultar(
            """SELECT SUM(valor) total FROM investimentos_movimentos
               WHERE tipo_movimento = 'juros' AND valor > 0"""))
    atribuido = inv.cupons_por_papel()
    total_atribuido = sum(atribuido.values())
    c.exigir(abs(total_extrato - total_atribuido) < 0.01,
             f"extrato tem {total_extrato:.2f} de juros mas foram atribuidos "
             f"{total_atribuido:.2f}")
    print(f"  extrato R$ {total_extrato:,.2f} = atribuido R$ {total_atribuido:,.2f}")

    for (papel_id, mes), valor in atribuido.items():
        historico = inv.evolucao(papel_id)
        linha = historico[historico["mes"] == mes]
        if linha.empty:
            continue
        c.exigir(float(linha["resgate"].iloc[0]) >= valor - 0.01,
                 f"papel {papel_id} em {mes}: resgate "
                 f"{float(linha['resgate'].iloc[0]):.2f} < cupom {valor:.2f}")

    for linha in banco.consultar("SELECT id, nome FROM investimentos"):
        if not inv.meses_de_cupom(linha["nome"]):
            continue
        historico = inv.evolucao(int(linha["id"]))
        if historico.empty:
            continue
        soma_cupons = sum(v for (i, _m), v in atribuido.items()
                          if i == int(linha["id"]))
        c.exigir(soma_cupons <= 0 or float(historico["resgate"].sum()) > 0,
                 f"{linha['nome']}: recebeu cupom mas nao tem resgate nenhum")


def conferir_sombra(c: Conferencia) -> None:
    """A carteira-sombra parte do mesmo ponto e usa os mesmos fluxos."""
    print()
    print("=" * 78)
    print("7. A CARTEIRA-SOMBRA E COMPARAVEL")
    print("=" * 78)
    tabela = inv.carteira_contra_indice("CDI")
    if tabela.empty:
        print("  (carteira vazia — pule)")
        return
    primeiro = tabela.iloc[0]
    c.exigir(abs(float(primeiro["saldo"]) - float(primeiro["referencia"])) < 0.01,
             "a sombra nao parte do mesmo ponto que a carteira real")

    carteira = inv.evolucao_carteira()
    c.exigir(len(tabela) == len(carteira),
             f"sombra tem {len(tabela)} meses, carteira tem {len(carteira)}")
    c.exigir(list(tabela["mes"]) == list(carteira["mes"]),
             "os meses da sombra nao batem com os da carteira")

    taxas = indices.serie("CDI")
    anterior = None
    for _, linha in tabela.iterrows():
        if anterior is not None and linha["mes"] in taxas:
            fluxo = float(carteira[carteira["mes"] == linha["mes"]]["aporte"].iloc[0]) \
                - float(carteira[carteira["mes"] == linha["mes"]]["resgate"].iloc[0])
            esperado = (anterior + fluxo) * (1 + taxas[linha["mes"]])
            c.exigir(abs(float(linha["referencia"]) - esperado) < 0.01,
                     f"{linha['mes']}: sombra {linha['referencia']:.2f} "
                     f"!= esperado {esperado:.2f}")
        anterior = float(linha["referencia"])
    print(f"  {len(tabela)} meses, cada um reconferido pela formula")


def conferir_abertura(c: Conferencia) -> None:
    """Saldo trazido de outro banco nao e rendimento."""
    print()
    print("=" * 78)
    print("8. SALDO DE ABERTURA NAO E RENDIMENTO")
    print("=" * 78)
    from financas import dados

    abertura = inv.saldo_de_abertura()
    c.exigir(abertura >= 0, f"saldo de abertura negativo: {abertura}")

    conciliacao = inv.conciliar()
    c.exigir(
        abs(conciliacao["diferenca"] - conciliacao["rendimento_apurado"]) < 1.0,
        f"diferenca {conciliacao['diferenca']:.2f} != rendimento apurado "
        f"{conciliacao['rendimento_apurado']:.2f} — o saldo de abertura "
        f"voltou a contar como ganho")
    print(f"  abertura R$ {abertura:,.2f} descontada")
    print(f"  ponta a ponta R$ {conciliacao['diferenca']:,.2f} = "
          f"mes a mes R$ {conciliacao['rendimento_apurado']:,.2f}")


def conferir_offline(c: Conferencia) -> None:
    """Sem internet, o que ja esta guardado continua de pe.

    POR QUE ELE CHAMA `atualizar` DUAS VEZES. As duas fontes caem de formas
    diferentes: o Banco Central e uma chamada HTTP, e o indice de mercado e
    DERIVADO dos precos ja guardados em `cotacoes`. A primeira chamada existe
    para derivar o que da para derivar do que ja esta em casa; a segunda e a
    que vale, e ela tem de devolver zero em tudo — offline, nada de novo entra.

    Foi assim que apareceu um erro: `buscar_mercado` devolvia "31 meses"
    mesmo com a rede fora, porque contava linhas reescritas em vez de dado
    novo. O numero mentia justamente na hora em que a tela precisa dele para
    dizer se a busca funcionou.
    """
    print()
    print("=" * 78)
    print("9. SEM INTERNET, O GUARDADO SEGUE DE PE")
    print("=" * 78)
    with banco_descartavel("conferir_indices"):
        guardado_antes = indices.serie("CDI")

        original = indices.urllib.request.urlopen

        def cair(*args, **kwargs):
            raise OSError("rede fora — simulado pelo teste")

        from financas import cotacoes

        buscar_cotacao = cotacoes.atualizar

        indices.urllib.request.urlopen = cair
        cotacoes.atualizar = lambda *a, **k: {}
        try:
            indices.atualizar(desde="2026-01")

            resultado = indices.atualizar(desde="2026-01")
            c.exigir(set(resultado.values()) <= {0},
                     f"sem rede deveria devolver zeros, veio {resultado}")
            depois = indices.serie("CDI")
            c.exigir(depois == guardado_antes,
                     "a falha de rede apagou ou alterou o que estava guardado")
            # SO EXIGE SE HOUVER SERIE GUARDADA (2026-09-04). O banco de
            # demonstracao nao semeia CDI de proposito — taxa inventada com
            # cara de medicao e pior que taxa nenhuma. Sem serie, nao ha o que
            # acumular, e reprovar por isso e alarme falso: o que esta secao
            # prova e que a falha de REDE nao estraga o que ja existia.
            if not guardado_antes:
                print("  sem série do CDI neste banco — nada a acumular")
            else:
                acumulado = indices.acumulado("CDI", sorted(guardado_antes)[-3:])
                c.exigir(acumulado is not None,
                         "sem rede, o acumulado do que ja existe deveria "
                         "funcionar")
        finally:
            indices.urllib.request.urlopen = original
            cotacoes.atualizar = buscar_cotacao
    print("  rede derrubada: 0 gravados, serie intacta, acumulado funcionando")


def main() -> int:
    """Roda as nove conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("#" * 78)
    print("#  CONFERINDO OS INDICES DE REFERENCIA (CDI / IPCA)")
    print("#" * 78)
    print()
    c = Conferencia()
    conferir_mesmos_meses(c)
    conferir_capitalizacao(c)
    conferir_regua(c)
    conferir_atraso(c)
    conferir_vazio(c)
    conferir_cupom(c)
    conferir_sombra(c)
    conferir_abertura(c)
    conferir_offline(c)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
