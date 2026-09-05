"""
conferir_investimentos.py — os numeros da tela de Investimentos batem?
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
A tela de Investimentos mostra o numero que mais convida ao erro do app
inteiro: **"quanto esse papel valorizou"**. Ha duas formas de calcula-lo, as
duas parecem certas, e uma delas mente:

    saldo / aportado − 1        ingenua. Da **+213%** no Trend DI.
    (1+r1)(1+r2)...(1+rn) − 1   encadeada. Da **7,7%** no mesmo papel.

O Trend DI recebeu R$ ···· e devolveu R$ ···· em 29 meses — ele e usado
como caixa. Dividir saldo por aporte liquido de um papel com essa rotatividade
nao significa nada, e o resultado tem exatamente a cara de um numero certo.

Este script existe para que a forma errada nunca volte por descuido.

O QUE ELE CONFERE
-----------------
1. A rentabilidade e composta, e nao somada.
2. Papel sem mes MEDIDO devolve vazio, nunca 0,0.
3. Meses de fonte ruim sao ignorados **e contados**, para a tela avisar.
4. A regua de comparacao e a que `indices.referencia_para` manda — e os dois
   lados usam a mesma lista de meses.
5. O custo medio soma lotes e respeita o fator de grupamento.
6. Compra em moeda estrangeira e convertida UMA vez, na gravacao.
7. A tabela inteira fecha com a carteira, e sai rapido o bastante.

As escritas do teste 5 e 6 acontecem numa COPIA do banco. Um teste que pode
destruir o dado que ele confere nao e um teste.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_investimentos
"""

from __future__ import annotations

import sys
import time

from financas import banco, config, indices
from financas.calculos import investimentos as inv
from financas.formato import vazio
from verificacao.base import Conferencia, banco_descartavel


def limpar_compras(investimento_id: int) -> None:
    """Apaga as compras de um papel DENTRO da copia, antes de testar nele.

    Sem isto, o teste depende do que ele tem lancado de verdade. Foi o que
    aconteceu em 2026-08-29: assim que a compra real do IREN entrou, o teste da
    conversao de moeda passou a somar os dois lotes e falhou por R$ ····

    O defeito era do teste, nao do codigo — e e o tipo de teste que nasce
    passando e quebra quando o app comeca a ser usado.
    """
    from financas import banco as _banco

    _banco.executar("DELETE FROM investimentos_compras WHERE investimento_id = ?",
                    (int(investimento_id),))


def conferir_composicao(c: Conferencia) -> None:
    """A rentabilidade multiplica os meses; nao soma."""
    print("=" * 78)
    print("1. A RENTABILIDADE E COMPOSTA")
    print("=" * 78)

    tabela = inv.desempenho_da_carteira()
    abertas = tabela[tabela["saldo"] > 0]

    for _, papel in abertas.iterrows():
        historico = inv.evolucao(int(papel["id"]))
        if historico.empty:
            continue
        bons = historico[historico["confiavel"].fillna(True).astype(bool)]
        if len(bons) <= 1:
            continue

        composto = 1.0
        for pct in bons["rendimento_pct"]:
            composto *= (1 + float(pct))
        composto -= 1
        somado = float(bons["rendimento_pct"].sum())

        c.exigir_igual(papel["rent_total"], composto,
                   f"{papel['nome']}: rent_total nao bate com a composicao",
                   0.0001)
        if abs(composto - somado) > 0.0005:
            c.exigir(abs(float(papel["rent_total"]) - somado) > 0.0001,
                     f"{papel['nome']}: rent_total igualou a SOMA dos meses "
                     f"({somado:.4f}) — juros compostos nao somam")
    print(f"   {len(abertas)} papeis conferidos")


def conferir_vazio_nunca_zero(c: Conferencia) -> None:
    """Papel sem mes medido sai vazio. Zero se leria como 'nao rendeu'."""
    print()
    print("=" * 78)
    print("2. SEM MEDICAO, SAI VAZIO — NUNCA 0,0")
    print("=" * 78)

    tabela = inv.desempenho_da_carteira()
    sem_medida = tabela[tabela["meses_medidos"] <= 1]

    for _, papel in sem_medida.iterrows():
        if papel["saldo"] <= 0:
            continue
        c.exigir(vazio(papel["rent_total"]),
                 f"{papel['nome']}: so tem {papel['meses_medidos']} mes medido "
                 f"e mesmo assim devolveu rent_total={papel['rent_total']!r}. "
                 f"O primeiro mes e aporte por construcao, nao medicao.")
        print(f"   {papel['nome']}: {papel['meses_medidos']} mes medido, "
              f"rentabilidade vazia")

    c.exigir(len(sem_medida) > 0,
             "nenhum papel sem medicao na base — o teste perdeu o objeto")


def conferir_meses_ignorados(c: Conferencia) -> None:
    """Mes de fonte ruim e ignorado E contado, para a tela poder avisar."""
    print()
    print("=" * 78)
    print("3. MES DE FONTE RUIM E IGNORADO, E CONTADO")
    print("=" * 78)

    tabela = inv.desempenho_da_carteira()
    com_buraco = tabela[tabela["meses_ignorados"] > 0]
    c.exigir(len(com_buraco) > 0,
             "nenhum papel com mes ignorado — a regra de procedencia sumiu?")

    for _, papel in com_buraco.iterrows():
        historico = inv.evolucao(int(papel["id"]))
        ruins = int((~historico["confiavel"].fillna(True).astype(bool)).sum())
        c.exigir_igual(papel["meses_ignorados"], ruins,
                   f"{papel['nome']}: meses_ignorados nao bate com o historico")

        aportado = float(historico["aporte"].sum() - historico["resgate"].sum())
        if aportado > 0.01:
            ingenuo = float(papel["saldo"]) / aportado - 1
            if abs(ingenuo) > 0.5 and not vazio(papel["rent_total"]):
                c.exigir(abs(float(papel["rent_total"]) - ingenuo) > 0.01,
                         f"{papel['nome']}: rent_total ficou igual a conta "
                         f"ingenua saldo/aportado ({ingenuo:.1%})")
                print(f"   {papel['nome']}: encadeada "
                      f"{float(papel['rent_total']):.1%} contra ingenua "
                      f"{ingenuo:.1%} — mede {papel['meses_medidos']}, "
                      f"ignora {papel['meses_ignorados']}")


def conferir_regua(c: Conferencia) -> None:
    """Cada papel e comparado com o indice certo, ou com nenhum."""
    print()
    print("=" * 78)
    print("4. A REGUA CERTA, E OS MESMOS MESES DOS DOIS LADOS")
    print("=" * 78)

    tabela = inv.desempenho_da_carteira()
    for _, papel in tabela[tabela["saldo"] > 0].iterrows():
        esperado = indices.referencia_para(papel["macro"], papel["classe"])
        obtido = None if vazio(papel["indice"]) else papel["indice"]
        c.exigir(obtido == esperado,
                 f"{papel['nome']}: regua {obtido!r}, esperado {esperado!r}")

        macro = str(papel["macro"] or "").upper()
        if macro in ("INTERNACIONAL", "RENDA VARIÁVEL", "RENDA VARIAVEL"):
            c.exigir(obtido != "CDI",
                     f"{papel['nome']}: e {papel['macro']} e voltou a ser "
                     f"medido pelo CDI — o IRE contra o CDI dava −765%, "
                     f"aritmetica sem significado")

        if esperado:
            resultado = inv.desempenho_do_papel(int(papel["id"]), 12,
                                                papel["classe"])
            if resultado["rent_indice"] is not None:
                do_indice = indices.acumulado(esperado, resultado["meses"])
                c.exigir_igual(resultado["rent_indice"], do_indice,
                           f"{papel['nome']}: o indice usou meses diferentes",
                           0.000001)
    print("   regua conferida papel a papel")


def conferir_custo_medio(c: Conferencia) -> None:
    """Custo medio soma lotes, aplica o fator de grupamento e converte uma vez."""
    print()
    print("=" * 78)
    print("5. CUSTO MEDIO: LOTES, GRUPAMENTO E MOEDA")
    print("=" * 78)

    with banco_descartavel("conferir_investimentos"):
        # OS PAPEIS DE TESTE SAEM DO BANCO, nao de numeros escritos aqui.
        # Estavam cravados (4 e 5), que so existem no banco dele. No banco de
        # demonstracao, que tem quatro papeis, o segundo apontava para nada:
        # `custo_medio` devolvia None e a checagem estourava com TypeError.
        # E precisam ser em REAIS — num papel em dolar o preco medio sai
        # convertido, e a conta esperada aqui e sem conversao.
        em_reais = [int(l["id"]) for l in banco.consultar(
            "SELECT id FROM investimentos "
            " WHERE COALESCE(moeda, 'BRL') = 'BRL' ORDER BY id")]
        if not em_reais:
            c.exigir(True, "")
            print("   nenhum papel em reais neste banco — sem efeito")
            return
        papel_brl = em_reais[0]
        limpar_compras(papel_brl)
        c.exigir(inv.custo_medio(papel_brl) is None,
                 "papel sem compra deveria devolver None, nao dicionario zerado")

        inv.salvar_compra(papel_brl, "2025-08-15", 10.0, 100.0, custos=5.0)
        inv.salvar_compra(papel_brl, "2025-09-15", 5.0, 130.0, custos=0.0)

        custo = inv.custo_medio(papel_brl)
        c.exigir_igual(custo["quantidade"], 15.0, "quantidade somada dos dois lotes")
        c.exigir_igual(custo["custo_total_brl"], 1655.0,
                   "custo total = 10x100+5 + 5x130")
        c.exigir_igual(custo["preco_medio_brl"], 1655.0 / 15.0,
                   "preco medio = custo total / quantidade", 0.0001)
        c.exigir_igual(custo["lotes"], 2, "dois lotes")
        print(f"   dois lotes BRL: {custo['quantidade']:.0f} cotas, "
              f"medio R$ {custo['preco_medio_brl']:.2f}")

        corte = inv.custo_medio(papel_brl, ate="2025-08-31")
        c.exigir_igual(corte["quantidade"], 10.0, "corte por data ignora o 2o lote")

        # O PAPEL DE TESTE E O QUE EXISTIR, nao o de numero 5.
        #
        # Estava cravado `papel_split = 5`, que so existe no banco dele. Num
        # banco com menos papeis — o de demonstracao tem quatro — a compra era
        # gravada para um investimento inexistente, `custo_medio` devolvia
        # None e a checagem estourava com TypeError antes de conferir nada.
        papel_split = em_reais[1] if len(em_reais) > 1 else papel_brl
        limpar_compras(papel_split)
        inv.salvar_compra(papel_split, "2026-01-10", 145.0, 4.0,
                          fator_ajuste=0.25)
        agrupado = inv.custo_medio(papel_split)
        c.exigir(agrupado is not None,
                 f"custo_medio devolveu None para o papel {papel_split}")
        if agrupado is None:
            return
        c.exigir_igual(agrupado["quantidade"], 36.25,
                   "grupamento 1:4 — 145 cotas contam como 36,25")
        c.exigir_igual(agrupado["preco_medio_brl"], 580.0 / 36.25,
                   "e o preco medio sobe na mesma proporcao", 0.0001)
        print(f"   grupamento 1:4: 145 -> {agrupado['quantidade']:.2f} cotas")

        try:
            inv.salvar_compra(papel_brl, "2025-10-01", None, None)
            c.exigir(False, "compra sem valor e sem quantidade foi aceita — "
                            "custo desconhecido nao pode virar zero")
        except ValueError:
            c.exigir(True, "")

        try:
            inv.salvar_compra(papel_brl, "15/08/2025", 1.0, 1.0)
            c.exigir(False, "data fora do formato foi aceita")
        except ValueError:
            c.exigir(True, "")


def conferir_moeda(c: Conferencia) -> None:
    """Compra em dolar guarda o valor em reais e o cambio empregado."""
    print()
    print("=" * 78)
    print("6. COMPRA EM DOLAR CONVERTE UMA VEZ, NA GRAVACAO")
    print("=" * 78)

    with banco_descartavel("conferir_investimentos"):
        # O PAPEL EM DOLAR SAI DO BANCO, e se nao houver a checagem diz isso.
        # Estava cravado `17`, que so existe no banco dele; no de demonstracao
        # nao ha papel em moeda estrangeira nenhum, e a checagem reprovava por
        # ausencia de dado em vez de por defeito.
        em_dolar = banco.consultar_um(
            "SELECT id FROM investimentos WHERE moeda = 'USD' ORDER BY id")
        if not em_dolar:
            c.exigir(True, "")
            print("   nenhum papel em dólar neste banco — checagem sem efeito")
            return
        papel_usd = int(em_dolar["id"])
        limpar_compras(papel_usd)
        c.exigir(inv.moeda_do_investimento(papel_usd) == "USD",
                 "o papel de teste deveria estar em USD")

        try:
            identificador = inv.salvar_compra(papel_usd, "2025-10-23", 144.36,
                                              54.54)
        except ValueError as erro:
            print(f"   sem cotacao guardada para a data: {erro}")
            c.exigir(True, "")
            return

        linha = inv.compras(papel_usd)
        linha = linha[linha["id"] == identificador].iloc[0]

        c.exigir(linha["moeda"] == "USD", "a moeda original fica registrada")
        c.exigir(linha["cambio_usado"] is not None and linha["cambio_usado"] > 1,
                 "o cambio empregado tem de ser gravado, para reproduzir depois")
        esperado = float(linha["valor_total"]) * float(linha["cambio_usado"])
        c.exigir_igual(linha["valor_total_brl"], esperado,
                   "valor em reais = valor na moeda x cambio gravado", 0.01)
        c.exigir(float(linha["valor_total_brl"]) > float(linha["valor_total"]),
                 "o valor em reais tem de ser maior que o valor em dolares")

        custo = inv.custo_medio(papel_usd)
        c.exigir_igual(custo["custo_total_brl"], esperado,
                   "o custo medio NAO reconverte o que ja esta em reais", 0.01)
        print(f"   US$ {linha['valor_total']:,.2f} x "
              f"{linha['cambio_usado']:.4f} = R$ {linha['valor_total_brl']:,.2f}")

        ponte = inv.sincronizar_custo_no_saldo(papel_usd)
        c.exigir(ponte["gravados"] > 0,
                 "a compra deveria levar o custo para os meses fotografados — "
                 "sem isso a tela de Imposto continua dizendo 'sem custo'")
        from financas.calculos import imposto as _imposto
        bens = _imposto.bens_e_direitos("2026")
        do_papel = bens[bens["nome"] == "IREN"]
        c.exigir(not do_papel.empty and not vazio(do_papel["custo"].iloc[0]),
                 "o IREN deveria aparecer COM custo na ficha Bens e Direitos")
        if not do_papel.empty:
            c.exigir(str(do_papel["fonte_custo"].iloc[0]) == "manual",
                     "e a procedencia do custo tem de dizer 'manual'")
            print(f"   ficha Bens e Direitos: custo "
                  f"R$ {float(do_papel['custo'].iloc[0]):,.2f} "
                  f"(fonte {do_papel['fonte_custo'].iloc[0]})")

        anterior = inv.custo_medio(papel_usd)
        inv.salvar_compra(papel_usd, "2024-06-10", 10.0, 30.0)
        antes_de_2025 = inv.custo_medio(papel_usd, ate="2024-12-31")
        c.exigir(antes_de_2025["custo_total_brl"] < anterior["custo_total_brl"],
                 "o custo acumulado ate 2024 nao pode incluir a compra de 2025 "
                 "— a ficha de um ano pede o que foi pago ATE aquele ano")


def conferir_tabela(c: Conferencia) -> None:
    """A tabela fecha com a carteira, e sai rapido o bastante."""
    print()
    print("=" * 78)
    print("7. A TABELA FECHA COM A CARTEIRA")
    print("=" * 78)

    inicio = time.perf_counter()
    tabela = inv.desempenho_da_carteira()
    decorrido = (time.perf_counter() - inicio) * 1000

    foto = inv.posicao(None)
    c.exigir_igual(len(tabela), len(foto), "uma linha por papel da posicao")

    abertas = tabela[tabela["saldo"] > 0]
    c.exigir_igual(float(abertas["saldo"].sum()), float(foto[foto["saldo"] > 0]["saldo"].sum()),
               "a soma dos saldos bate com a posicao", 0.01)
    c.exigir_igual(float(abertas["participacao"].sum()), 1.0,
               "os percentuais somam 100%", 0.0001)

    por_macro = abertas.groupby("macro", dropna=False)["saldo"].sum()
    c.exigir_igual(float(por_macro.sum()), float(abertas["saldo"].sum()),
               "agrupar por macro nao perde nem cria dinheiro", 0.01)

    for coluna in ("curva",):
        c.exigir(all(isinstance(v, list) for v in tabela[coluna]),
                 f"a coluna {coluna} deveria ser lista em toda linha")

    c.exigir(decorrido < 600,
             f"desempenho_da_carteira() levou {decorrido:.0f} ms — passou de "
             f"600 ms, a tela vai travar")
    print(f"   {len(tabela)} linhas em {decorrido:.0f} ms")
    print(f"   {len(por_macro)} macros, carteira R$ {abertas['saldo'].sum():,.2f}")


def main() -> int:
    """Roda todas as conferencias e imprime o resultado."""
    c = Conferencia()
    print()
    conferir_composicao(c)
    conferir_vazio_nunca_zero(c)
    conferir_meses_ignorados(c)
    conferir_regua(c)
    conferir_custo_medio(c)
    conferir_moeda(c)
    conferir_tabela(c)

    return c.relatorio()


if __name__ == "__main__":
    sys.exit(main())
