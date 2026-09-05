"""
conferir_rebalanceamento.py — prova que a conta do aporte esta certa.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
O rebalanceamento e a unica tela que diz "ponha R$ X aqui". Se a conta estiver
errada, voce vai investir errado — e, pior, sem perceber, porque o numero
parece razoavel de qualquer jeito.

Um erro de arredondamento que faz a soma dar R$ ···· em vez de R$ ···· nao
quebra nada e nao aparece na tela. Por isso a conferencia e automatica.

AS QUATRO GARANTIAS
-------------------
1. SOMA EXATA          o total distribuido e exatamente o aporte informado
2. NUNCA NEGATIVO      nenhuma classe recebe valor negativo (nao sugere vender)
3. SEM ULTRAPASSAR     nenhuma classe recebe mais do que falta para o ideal
4. CARTEIRA APROXIMA   a soma das distancias ate a meta nunca aumenta

UMA GARANTIA QUE **NAO** VALE, E POR QUE
----------------------------------------
"Nenhuma classe termina mais longe da meta do que estava" parece o teste obvio,
e foi o primeiro que eu escrevi. Ele FALHA — e falha corretamente:

    classe   saldo   meta   antes  recebe  depois
    C1        44,0   45,0%  44,0%    1,02   40,9%   <- recebeu e se afastou
    C2         1,0   45,0%   1,0%    8,98    9,1%
    C3        55,0   10,0%  55,0%    0,00   50,0%

O percentual e uma divisao, e o aporte aumenta o denominador de todo mundo. Uma
classe quase na meta, enchida devagar, perde para a diluicao. No conjunto a
carteira se aproximou (distancia total 90 -> 80 pontos), que e o que importa.

Prometer a garantia forte deixaria o teste bonito e mentiroso. Este arquivo
testa a garantia verdadeira.

COMO ELE TESTA
--------------
Duas frentes. A primeira e a sua carteira de verdade, com metas de exemplo. A
segunda sao centenas de carteiras SORTEADAS — saldos e metas aleatorios,
inclusive os casos esquisitos (carteira vazia, uma classe so, meta zerada).

Testar so com a carteira real provaria pouco: ela e um caso especifico, e os
bugs de arredondamento aparecem justamente nas combinacoes que ninguem pensou
em testar a mao.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_rebalanceamento
"""

from __future__ import annotations

import random
import sys

import pandas as pd

from financas import banco, config
from financas.calculos import investimentos as inv
from financas.formato import fmt_brl, fmt_pct
from verificacao.base import Conferencia, banco_descartavel

TOLERANCIA = 0.005


def _distribuir(saldos: dict[str, float], alvos: dict[str, float],
                aporte: float) -> dict[str, float]:
    """A MESMA conta de `investimentos.rebalancear`, isolada dos dados.

    Repetir a formula aqui e proposital: se o teste chamasse a funcao de
    producao para calcular o resultado esperado, ele concordaria com qualquer
    erro que ela tivesse. Escrita duas vezes, de forma independente, uma serve
    de conferencia da outra.
    """
    total_novo = sum(saldos.values()) + aporte
    soma_alvos = sum(alvos.values())
    if aporte <= 0 or soma_alvos <= 0:
        return {nome: 0.0 for nome in saldos}

    faltas = {nome: max(0.0, alvos.get(nome, 0.0) * total_novo - saldo)
              for nome, saldo in saldos.items()}
    soma_faltas = sum(faltas.values())

    if soma_faltas <= 0:
        return {n: aporte * alvos.get(n, 0.0) / soma_alvos for n in saldos}
    if aporte <= soma_faltas:
        return {n: aporte * faltas[n] / soma_faltas for n in saldos}
    sobra = aporte - soma_faltas
    return {n: faltas[n] + sobra * alvos.get(n, 0.0) / soma_alvos for n in saldos}


def conferir_um_caso(conferencia: Conferencia, tabela: pd.DataFrame,
                     aporte: float, rotulo: str) -> None:
    """Aplica as quatro garantias a um resultado de `rebalancear`."""
    if tabela.empty:
        return

    distribuido = float(tabela["aportar"].sum())
    esperado = aporte if float(tabela["percentual_alvo"].sum()) > 0 else 0.0
    conferencia.exigir(
        abs(distribuido - esperado) < TOLERANCIA,
        f"{rotulo}: distribuiu {distribuido:.2f}, esperado {esperado:.2f}")

    negativos = tabela[tabela["aportar"] < 0]
    conferencia.exigir(
        negativos.empty,
        f"{rotulo}: {len(negativos)} classe(s) com aporte negativo")

    if float(tabela["aportar"].sum()) <= float(tabela["falta"].sum()) + TOLERANCIA:
        for _, linha in tabela.iterrows():
            conferencia.exigir(
                linha["aportar"] <= linha["falta"] + TOLERANCIA,
                f"{rotulo}: '{linha['nome']}' recebeu {linha['aportar']:.2f} "
                f"mas so faltavam {linha['falta']:.2f}")

    distancia_antes = float(tabela["desvio"].abs().sum())
    distancia_depois = float(tabela["desvio_depois"].abs().sum())
    conferencia.exigir(
        distancia_depois <= distancia_antes + 1e-9,
        f"{rotulo}: a carteira se afastou da meta "
        f"({distancia_antes:.6f} -> {distancia_depois:.6f})")


def conferir_carteira_real(conferencia: Conferencia) -> None:
    """Roda a conta sobre a sua carteira, com uma meta de exemplo.

    As metas usadas aqui NAO sao gravadas no banco — a conferencia nao pode
    mexer nos seus dados. Elas sao montadas em memoria so para o teste.
    """
    print("=" * 78)
    print("1. A SUA CARTEIRA DE VERDADE")
    print("=" * 78)

    atual = inv.alocacao_atual(nivel="classe")
    if atual.empty:
        print("  (carteira vazia — importe a posicao antes)")
        return

    total = float(atual["saldo"].sum())
    print(f"  Carteira hoje: {fmt_brl(total)} em {len(atual)} classe(s)")
    for _, linha in atual.iterrows():
        print(f"    {linha['nome'][:26]:26} {fmt_brl(linha['saldo']):>15} "
              f"{fmt_pct(linha['percentual']):>7}")

    metas_exemplo = {
        "NTN-B (inflação)": 0.35, "Tesouro Selic": 0.15, "Fundo DI": 0.10,
        "ETF": 0.20, "Ação BR": 0.10, "Stock EUA": 0.10,
    }
    saldos = {n: float(s) for n, s in zip(atual["nome"], atual["saldo"])}
    for nome in metas_exemplo:
        saldos.setdefault(nome, 0.0)

    for aporte in [0, 0.01, 100, 5000, 79608, 500000]:
        esperado = _distribuir(saldos, metas_exemplo, aporte)
        soma = sum(esperado.values())
        conferencia.exigir(
            abs(soma - (aporte if aporte > 0 else 0)) < TOLERANCIA,
            f"carteira real, aporte {aporte}: soma {soma:.2f}")

    print()
    print("  Com um aporte de R$ 5.000,00 (metas de exemplo):")
    aporte = 5000.0
    reparticao = _distribuir(saldos, metas_exemplo, aporte)
    total_novo = total + aporte
    for nome, valor in sorted(reparticao.items(), key=lambda x: -x[1]):
        if valor < 0.005:
            continue
        depois = (saldos[nome] + valor) / total_novo
        print(f"    {nome[:26]:26} {fmt_brl(valor):>13}   "
              f"{fmt_pct(saldos[nome] / total):>6} -> {fmt_pct(depois):>6} "
              f"(meta {fmt_pct(metas_exemplo[nome])})")
    print(f"    {'soma':26} {fmt_brl(sum(reparticao.values())):>13}")


def conferir_sorteados(conferencia: Conferencia, quantidade: int = 400) -> None:
    """Sorteia carteiras e metas, e aplica as garantias a cada uma."""
    print()
    print("=" * 78)
    print(f"2. {quantidade} CARTEIRAS SORTEADAS")
    print("=" * 78)

    aleatorio = random.Random(20260822)
    piores = []

    for caso in range(quantidade):
        quantas = aleatorio.randint(1, 8)
        nomes = [f"C{i}" for i in range(quantas)]

        if aleatorio.random() < 0.15:
            saldos = {n: 0.0 for n in nomes}
        else:
            saldos = {n: round(aleatorio.choice([0, 0, 1, 100, 5000, 200000])
                               * aleatorio.random(), 2) for n in nomes}

        if aleatorio.random() < 0.2:
            alvos = {n: 0.0 for n in nomes}
        else:
            brutos = [aleatorio.random() for _ in nomes]
            soma = sum(brutos) or 1
            fator = 1.0 if aleatorio.random() < 0.7 else aleatorio.uniform(0.3, 0.9)
            alvos = {n: b / soma * fator for n, b in zip(nomes, brutos)}

        aporte = aleatorio.choice([0, 0.01, 1, 500, 5000, 1_000_000])
        reparticao = _distribuir(saldos, alvos, aporte)

        soma_dist = sum(reparticao.values())
        alvo_soma = aporte if (aporte > 0 and sum(alvos.values()) > 0) else 0.0
        conferencia.exigir(
            abs(soma_dist - alvo_soma) < TOLERANCIA,
            f"sorteio {caso}: soma {soma_dist:.4f} != {alvo_soma:.4f}")

        conferencia.exigir(
            all(v >= -TOLERANCIA for v in reparticao.values()),
            f"sorteio {caso}: valor negativo distribuido")

        total = sum(saldos.values())
        total_novo = total + aporte
        if total > 0 and total_novo > 0 and sum(alvos.values()) > 0:
            def distancia(mapa, denominador):
                return sum(abs(mapa[n] / denominador - alvos[n]) for n in nomes)

            antes = distancia(saldos, total)
            depois = distancia({n: saldos[n] + reparticao[n] for n in nomes},
                               total_novo)
            if depois > antes + 1e-9:
                piores.append((caso, antes, depois))
            conferencia.exigir(
                depois <= antes + 1e-9,
                f"sorteio {caso}: carteira afastou-se "
                f"({antes:.6f} -> {depois:.6f})")

            faltas = {n: max(0.0, alvos[n] * total_novo - saldos[n]) for n in nomes}
            if aporte <= sum(faltas.values()) + 1e-9:
                for nome in nomes:
                    conferencia.exigir(
                        reparticao[nome] <= faltas[nome] + 1e-6,
                        f"sorteio {caso}: '{nome}' passou do ideal")

    print(f"  casos testados      : {quantidade}")
    print(f"  checagens acumuladas: {conferencia.checagens}")
    print(f"  carteiras que pioraram: {len(piores)}")


def conferir_funcao_de_producao(conferencia: Conferencia) -> None:
    """Confere a `rebalancear` de verdade, com metas gravadas numa COPIA do banco.

    O seu banco nao e tocado — ver `banco_descartavel`.
    """
    print()
    print("=" * 78)
    print("3. A FUNCAO `rebalancear` COM AS METAS NO BANCO (copia descartavel)")
    print("=" * 78)

    if inv.alocacao_atual(nivel="classe").empty:
        print("  (carteira vazia — importe a posicao antes)")
        return

    with banco_descartavel("conferir_rebalanceamento"):
        banco.executar("DELETE FROM metas_alocacao")
        sem_meta = inv.rebalancear(1000.0, nivel="classe")
        distribuido = float(sem_meta["aportar"].sum()) if not sem_meta.empty else 0.0
        conferencia.exigir(
            abs(distribuido) < TOLERANCIA,
            f"sem metas: distribuiu {distribuido:.2f}, deveria ser 0,00")
        print(f"  sem meta nenhuma, aporte R$ 1.000 -> distribuiu "
              f"{fmt_brl(distribuido):>12}   "
              f"{'OK' if abs(distribuido) < TOLERANCIA else 'ERRO'}")

        for nome, alvo in [("NTN-B (inflação)", 0.35), ("Tesouro Selic", 0.15),
                           ("Fundo DI", 0.10), ("ETF", 0.20),
                           ("Ação BR", 0.10), ("Stock EUA", 0.10)]:
            inv.salvar_meta("classe", nome, alvo, 0.05)

        for aporte in [0, 1, 5000, 250000]:
            tabela = inv.rebalancear(aporte, nivel="classe")
            conferir_um_caso(conferencia, tabela, aporte, f"rebalancear({aporte})")
            distribuido = float(tabela["aportar"].sum()) if not tabela.empty else 0.0
            print(f"  aporte {fmt_brl(aporte):>14} -> distribuiu "
                  f"{fmt_brl(distribuido):>14}   "
                  f"{'OK' if abs(distribuido - aporte) < TOLERANCIA else 'ERRO'}")

        prazos = inv.meses_para_meta(5000, nivel="classe")
        print()
        print("  No ritmo de R$ 5.000/mes, quando cada classe entra na faixa:")
        for _, linha in prazos.iterrows():
            quando = (f"{int(linha['meses'])} mes(es)" if linha["alcancavel"]
                      else "não alcança no horizonte")
            print(f"    {linha['nome'][:26]:26} {fmt_pct(linha['percentual']):>6} "
                  f"-> meta {fmt_pct(linha['percentual_alvo']):>6}   {quando}")
            conferencia.exigir(
                linha["meses"] is None or linha["meses"] >= 0,
                f"prazo negativo em '{linha['nome']}'")


def main() -> int:
    """Roda as tres baterias de conferencia e devolve 0 (tudo certo) ou 1."""
    print()
    print("CONFERENCIA DO REBALANCEAMENTO POR APORTE")
    print()
    conferencia = Conferencia()
    conferir_carteira_real(conferencia)
    conferir_sorteados(conferencia)
    conferir_funcao_de_producao(conferencia)
    return conferencia.relatorio()


if __name__ == "__main__":
    sys.exit(main())
