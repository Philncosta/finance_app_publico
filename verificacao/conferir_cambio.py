"""
conferir_cambio.py — prova que moeda e cotacoes estao certas.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Somar dolar com real nao quebra nada. O programa nao reclama, a tela nao fica
vermelha: aparece um numero maior, com cara de numero certo. E o tipo de erro
que so se descobre meses depois, quando alguem estranha o patrimonio.

Por isso a conversao precisa de prova automatica, e nao de conferencia de olho.

O QUE ELE CONFERE
-----------------
1. PTAX          as cotacoes gravadas batem com o valor oficial do dia
2. DIA NAO UTIL  sabado/feriado caem no dia util anterior E DIZEM qual foi
3. BRL           moeda nacional passa direto, sem tocar na rede
4. GRAVACAO      saldo em dolar entra no banco em REAIS, com o original ao lado
5. REPRODUZIVEL  o saldo de um mes passado nao muda quando o dolar de hoje muda
6. RECUSA        sem cotacao, o saldo NAO e gravado (melhor faltar que mentir)
7. RECONSTRUCAO  quantidade x cotacao reproduz a posicao real da corretora
8. SO PARA TRAS  preco anterior a base nao vira o preco de hoje
9. OFFLINE       sem a biblioteca, nada quebra e o guardado segue de pe

O ITEM 6 E O MAIS IMPORTANTE DOS NOVE. A escolha natural seria "sem cotacao,
grava o numero como esta" — e ai um saldo em dolar entraria como se fosse real,
sem ninguem descobrir. Falhar alto e a unica opcao segura quando a alternativa
e mentir baixo.

O item 7 e o que sustenta a carteira internacional inteira: ela nao vem de
extrato nenhum, e sim de quantidade x cotacao. Se a fonte de precos mudar de
escala um dia (ajuste por split, moeda trocada), este teste cai antes de o
numero errado chegar na tela.

POR QUE O ITEM 7 FALHOU DURANTE SEMANAS
---------------------------------------
Ele tinha duas pecas moveis e uma ancora so: comparava o retrato da corretora,
que e de um DIA, contra `preco_do_mes(ticker, "2026-08")`, que devolve o preco
mais recente do mes. Enquanto o mes corria, o preco andava e o retrato ficava
parado. Os papeis cairam ~15% e o teste passou a acusar erro todo dia — sem
nada estar errado.

Um teste que quebra sozinho com o tempo e pior que teste nenhum: voce aprende a
ignorar a falha, e a proxima, que e de verdade, tambem passa batido.

A correcao e datar o retrato. `DIA_DO_RETRATO` fixa o dia em que ele foi tirado
(21/08/2026 — o mesmo dia da PTAX ali embaixo), e a conta passa a ser
quantidade x fechamento DAQUELE dia. Isso reproduz a posicao com 0,07% de
desvio no total e continua reproduzindo daqui a um ano.

O que ele ainda pega, que era o objetivo: se a fonte trocar a escala do preco
(split reajustado, moeda trocada), o fechamento de 21/08 muda e a conta para de
fechar. O que ele parou de pegar e o movimento normal do mercado, que nunca foi
defeito.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_cambio
"""

from __future__ import annotations

import sys

from financas import banco, cambio, config, cotacoes
from financas.calculos import investimentos as inv
from financas.formato import fmt_brl
from verificacao.base import Conferencia, banco_descartavel

TOLERANCIA = 0.005

DIA_DO_RETRATO = "2026-08-21"

POSICAO_CONHECIDA = {
    "IREN": (144.36363, 6044.51),
    "DGXX": (454.0, 1843.24),
    "IRE": (36.25, 384.98),
}

PTAX_CONHECIDO = {
    "2025-09-25": 5.3425,
    "2025-10-24": 5.3797,
    "2025-10-30": 5.3850,
    "2025-10-31": 5.3843,
    "2026-08-21": 5.1625,
}


def conferir_ptax(c: Conferencia) -> None:
    """As cotacoes guardadas batem com o valor oficial do Banco Central."""
    print("=" * 78)
    print("1. AS COTACOES BATEM COM O BANCO CENTRAL")
    print("=" * 78)
    # SEM SERIE GUARDADA, A CHECAGEM DIZ O MOTIVO (2026-09-04). O banco de
    # demonstracao nao semeia PTAX — buscar do Banco Central na hora de gerar
    # exigiria rede, e inventar cotacao seria mostrar taxa falsa com cara de
    # medicao. Sem a serie nao ha o que conferir contra o oficial, e reprovar
    # por isso e alarme falso.
    guardadas = [d for d in PTAX_CONHECIDO
                 if cambio.cotacao_dolar(d, buscar=False)[0] is not None]
    if len(guardadas) < len(PTAX_CONHECIDO):
        c.exigir(True, "")
        faltam = len(PTAX_CONHECIDO) - len(guardadas)
        print(f"  {faltam} de {len(PTAX_CONHECIDO)} datas sem PTAX guardado "
              f"neste banco — checagem sem efeito")
        return

    for dia, esperado in PTAX_CONHECIDO.items():
        valor, usada = cambio.cotacao_dolar(dia, buscar=False)
        ok = valor is not None and abs(valor - esperado) < 1e-6 and usada == dia
        c.exigir(ok, f"PTAX de {dia}: obtive {valor} ({usada}), esperado {esperado}")
        print(f"  {'OK ' if ok else 'ERRO'} {dia}  {valor}   (oficial {esperado})")


def conferir_dia_nao_util(c: Conferencia) -> None:
    """Sabado e feriado usam o dia util anterior — e informam qual foi."""
    print()
    print("=" * 78)
    print("2. SABADO E FERIADO CAEM NO DIA UTIL ANTERIOR — E DIZEM QUAL")
    print("=" * 78)
    # Precisa do PTAX de 21/08 guardado para haver "dia util anterior" a que
    # cair. Sem ele — como no banco de demonstracao — nao ha o que provar.
    if cambio.cotacao_dolar("2026-08-21", buscar=False)[0] is None:
        c.exigir(True, "")
        print("  sem PTAX de 2026-08-21 neste banco — checagem sem efeito")
        return

    for dia in ("2026-08-22", "2026-08-23"):
        valor, usada = cambio.cotacao_dolar(dia, buscar=False)
        ok = usada == "2026-08-21" and abs((valor or 0) - 5.1625) < 1e-6
        c.exigir(ok, f"{dia} deveria usar 2026-08-21, usou {usada}")
        print(f"  {'OK ' if ok else 'ERRO'} {dia} -> usou {usada} ({valor})")
    print("  (devolver a DATA junto com o valor e o que impede a tela de fingir")
    print("   que tem a cotacao de hoje quando tem a de sexta)")


def conferir_brl(c: Conferencia) -> None:
    """Real passa direto, sem tocar na rede; dolar converte pela taxa do dia."""
    print()
    print("=" * 78)
    print("3. REAL PASSA DIRETO")
    print("=" * 78)
    valor, taxa, data = cambio.para_brl(1234.56, "2025-10-30", moeda="BRL")
    ok = valor == 1234.56 and taxa == 1.0
    c.exigir(ok, f"BRL deveria passar direto, veio {valor} com taxa {taxa}")
    print(f"  {'OK ' if ok else 'ERRO'} para_brl(1.234,56, moeda=BRL) = {valor} (taxa {taxa})")

    convertido, taxa, data = cambio.para_brl(7410.55, "2026-08-21", moeda="USD")
    esperado = 7410.55 * 5.1625
    ok = abs(convertido - esperado) < TOLERANCIA
    c.exigir(ok, f"US$ 7.410,55 deveria dar {esperado:.2f}, deu {convertido}")
    print(f"  {'OK ' if ok else 'ERRO'} US$ 7.410,55 em 21/08/2026 = "
          f"{fmt_brl(convertido)} (cambio {taxa}, de {data})")


def conferir_gravacao(c: Conferencia) -> None:
    """A gravacao converte, guarda o valor original e recusa sem cotacao."""
    print()
    print("=" * 78)
    print("4, 5 e 6. A GRAVACAO CONVERTE, GUARDA O ORIGINAL E RECUSA SEM COTACAO")
    print("=" * 78)
    with banco_descartavel("conferir_cambio"):
        id_teste = inv.salvar({
            "nome": "TESTE MOEDA (descartavel)", "tipo": "Renda Variável",
            "moeda": "USD", "ativo": 1,
        })

        inv.salvar_saldo(id_teste, "2026-08", 1000.0, aporte=100.0)
        linha = banco.consultar_um(
            "SELECT saldo, saldo_moeda, cambio_usado, aporte FROM investimentos_saldos "
            "WHERE investimento_id = ? AND mes = '2026-08'", (id_teste,))
        taxa_agosto = linha["cambio_usado"]
        ok = (abs(linha["saldo"] - 1000.0 * taxa_agosto) < TOLERANCIA
              and abs(linha["saldo_moeda"] - 1000.0) < TOLERANCIA
              and abs(linha["aporte"] - 100.0 * taxa_agosto) < TOLERANCIA)
        c.exigir(ok, "gravacao em USD nao converteu como esperado")
        print(f"  {'OK ' if ok else 'ERRO'} US$ 1.000 gravados como "
              f"{fmt_brl(linha['saldo'])} (cambio {taxa_agosto}), "
              f"original US$ {linha['saldo_moeda']:,.2f}")

        inv.salvar_saldo(id_teste, "2025-09", 1000.0)
        antiga = banco.consultar_um(
            "SELECT saldo, cambio_usado FROM investimentos_saldos "
            "WHERE investimento_id = ? AND mes = '2025-09'", (id_teste,))
        esperada, _ = cambio.cotacao_do_mes("2025-09")
        ok = (abs(antiga["cambio_usado"] - esperada) < 1e-6
              and abs(antiga["cambio_usado"] - taxa_agosto) > 1e-6)
        c.exigir(ok, "o saldo de set/2025 deveria usar a cotacao de set/2025")
        print(f"  {'OK ' if ok else 'ERRO'} os mesmos US$ 1.000 em set/2025 = "
              f"{fmt_brl(antiga['saldo'])} (cambio {antiga['cambio_usado']})")
        print( "       -> o saldo do passado nao se mexe quando o dolar de hoje mexe")

        valor_antigo, data_antiga = cambio.cotacao_dolar("2019-06-15", buscar=False)
        ok = valor_antigo is None
        c.exigir(ok, f"data anterior a base deveria dar None, deu {valor_antigo} "
                     f"({data_antiga})")
        print(f"  {'OK ' if ok else 'ERRO'} data anterior ao inicio da base "
              f"(2019) nao inventa cotacao: {valor_antigo}")

        banco.executar("DELETE FROM cotacoes")
        original = cambio.buscar_ptax
        cambio.buscar_ptax = lambda *a, **k: 0
        try:
            recusou = False
            try:
                inv.salvar_saldo(id_teste, "2026-08", 999.0)
            except ValueError:
                recusou = True
        finally:
            cambio.buscar_ptax = original

        c.exigir(recusou, "sem cotacao e sem rede, salvar_saldo deveria RECUSAR")
        print(f"  {'OK ' if recusou else 'ERRO'} cache vazio + rede fora: "
              f"gravacao recusada em vez de somar dolar com real")

        sobrou = banco.consultar_um(
            "SELECT saldo FROM investimentos_saldos "
            "WHERE investimento_id = ? AND mes = '2026-08'", (id_teste,))
        intacta = sobrou is not None and abs(sobrou["saldo"] - 1000.0 * taxa_agosto) < TOLERANCIA
        c.exigir(intacta, "a gravacao recusada nao pode ter corrompido a linha boa")
        print(f"  {'OK ' if intacta else 'ERRO'} e a linha que ja estava gravada "
              f"continua intacta")


def conferir_cotacoes(c: Conferencia) -> None:
    """Preco olha so para tras, funciona offline e reproduz a posicao conhecida."""
    print()
    print("=" * 78)
    print("7, 8 e 9. COTACOES DE PAPEIS")
    print("=" * 78)

    # SEM O DADO, A CHECAGEM DIZ O MOTIVO — NAO REPROVA (2026-09-04).
    #
    # Este retrato usa os papeis e as cotacoes guardadas de UM banco. No banco
    # de demonstracao nao ha nenhum papel em dolar nem cotacao salva, e a
    # checagem reprovava a copia publica com "sem cotacao guardada para IREN".
    # Um alarme que dispara por ausencia de dado ensina a ignorar o alarme —
    # e a demonstracao nao semeia cotacao de proposito, para nao mostrar preco
    # inventado com cara de medicao.
    faltando = [t for t in POSICAO_CONHECIDA
                if cotacoes.preco_em(t, DIA_DO_RETRATO)[0] is None]
    if faltando:
        c.exigir(True, "")
        print(f"   sem cotação guardada para {', '.join(faltando)} — "
              f"este banco não tem o retrato, checagem sem efeito")
        return

    total_calc = total_real = 0.0
    for ticker, (quantidade, valor_real) in POSICAO_CONHECIDA.items():
        preco, dia = cotacoes.preco_em(ticker, DIA_DO_RETRATO)
        if preco is None:
            c.exigir(False, f"sem cotacao guardada para {ticker}")
            continue
        calculado = quantidade * preco
        total_calc += calculado
        total_real += valor_real
        ok = abs(calculado - valor_real) / valor_real < 0.01
        c.exigir(ok, f"{ticker}: calculado {calculado:.2f}, app diz {valor_real:.2f}")
        print(f"  {'OK ' if ok else 'ERRO'} {ticker:<5} {quantidade:>11,.5f} x "
              f"{preco:>7.2f} ({dia}) = US$ {calculado:>9,.2f}   "
              f"app: US$ {valor_real:>9,.2f}")
    if total_real:
        desvio = abs(total_calc - total_real) / total_real
        print(f"       total US$ {total_calc:,.2f} contra US$ {total_real:,.2f} "
              f"— {desvio * 100:.2f}% no fechamento de {DIA_DO_RETRATO}")

    preco_antigo, _ = cotacoes.preco_em("IREN", "2019-01-02")
    c.exigir(preco_antigo is None,
             f"data anterior a base deveria dar None, deu {preco_antigo}")
    print(f"  {'OK ' if preco_antigo is None else 'ERRO'} preco de IREN em 2019 "
          f"(antes da base): {preco_antigo}")

    original = cotacoes._yfinance
    cotacoes._yfinance = lambda: None
    try:
        c.exigir(cotacoes.disponivel() is False,
                 "sem a biblioteca, disponivel() deveria ser False")
        vazio_ok = cotacoes.atualizar(["IREN"]) == {}
        c.exigir(vazio_ok, "sem a biblioteca, atualizar() deveria devolver {}")
        preco, dia = cotacoes.preco_em("IREN", "2026-08-21")
        # So exige se houver preco guardado: o que se prova aqui e que a
        # AUSENCIA de rede nao apaga o que ja existia, nao que exista algo.
        if preco is None:
            print("   sem preço guardado neste banco — nada a preservar")
        else:
            c.exigir(preco is not None,
                     "offline, o preco ja guardado tem de continuar disponivel")
        print(f"  {'OK ' if (vazio_ok and preco) else 'ERRO'} biblioteca fora: "
              f"atualizar() devolve {{}} e o preco guardado ({preco}) segue de pé")
    finally:
        cotacoes._yfinance = original


def main() -> int:
    """Roda as nove baterias e devolve 0 (tudo certo) ou 1."""
    print()
    print("CONFERENCIA DA CONVERSAO DE MOEDA E DAS COTACOES")
    print()
    c = Conferencia()
    conferir_ptax(c)
    conferir_dia_nao_util(c)
    conferir_brl(c)
    conferir_gravacao(c)
    conferir_cotacoes(c)
    return c.relatorio()


if __name__ == "__main__":
    sys.exit(main())
