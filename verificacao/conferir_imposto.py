"""
conferir_imposto.py — prova que a tela de IR nao mente nem inventa.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Errar aqui nao trava nada: gera uma declaracao errada, entregue com
confianca, descoberta meses depois pela Receita.

Sao tres formas de errar, e nenhuma delas quebra a tela:

1. **Somar a PLR ao salario.** Ela tem tributacao exclusiva e ficha propria.
   Somada ao rendimento tributavel, empurra ~R$ ···· para a tabela
   progressiva e faz pagar imposto indevido.
2. **Custo desconhecido virar zero.** "Custou R$ ····" se le como bem de
   graca; a verdade e "nao sei quanto custou". Um bem declarado com custo
   zero transforma a venda inteira em ganho tributavel.
3. **Mudar um numero que ja era olhado.** A projecao de caixa ganhou a coluna
   de gasto planejado. Com o botao desligado ela tem de ficar IDENTICA a que
   ele ja usa — senao trocamos o significado de um numero sem avisar.

O QUE ELE CONFERE
-----------------
1. BENS         a soma de 31/12 bate com `investimentos.posicao()`
2. NAO-ZERO     custo desconhecido volta None, nunca 0,0
3. PLR          nunca aparece dentro do rendimento tributavel
4. ANO VAZIO    ano sem dado devolve tabela vazia, nao erro
5. FONTE FRACA  custo de 'valor_aplicado' sempre entra em `custos_faltando`
6. PLANEJADO    ligado, o saldo cai exatamente o valor planejado
7. INTOCADO     desligado, a serie e IDENTICA a de antes
8. GRAVACAO     salvar custo em mes sem foto RECUSA, em vez de fingir
9. PARCIAL      custo do extrato so vale para papel NASCIDO nele
10. FICHA NA TELA  toda ficha do calculo tem cartao, e os cartoes somam

O ITEM 7 E O QUE PROTEGE O QUE JA FUNCIONAVA. O ITEM 8 nasceu de um defeito
de verdade: `salvar_custo` faz UPDATE, e UPDATE numa linha que nao existe casa
com zero linhas sem erro nenhum. Gravar o custo em '2026-12' em agosto de 2026
dizia "salvo" e nao salvava nada.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_imposto
"""

from __future__ import annotations

import pathlib


from financas import banco, config, dados
from financas.calculos import imposto, investimentos as inv, planejamento
from verificacao.base import Conferencia, banco_descartavel


def conferir_bens(c: Conferencia, df) -> None:
    """A posicao de 31/12 bate com a fonte unica da carteira."""
    print("=" * 78)
    print("1. BENS E DIREITOS BATEM COM A CARTEIRA")
    print("=" * 78)
    for ano in imposto.anos_disponiveis(df):
        bens = imposto.bens_e_direitos(ano)
        posicao = inv.posicao(f"{ano}-12")
        esperado = posicao[posicao["saldo"] > 0] if not posicao.empty else posicao
        c.exigir(len(bens) == len(esperado),
                 f"{ano}: {len(bens)} bens contra {len(esperado)} na posicao")
        if bens.empty:
            continue
        soma_bens = float(bens["valor_mercado"].sum())
        soma_pos = float(esperado["saldo"].sum())
        c.exigir(abs(soma_bens - soma_pos) < 0.01,
                 f"{ano}: mercado {soma_bens:.2f} != posicao {soma_pos:.2f}")
        print(f"  {ano}-12: {len(bens):>2} papeis, R$ {soma_bens:>12,.2f}")


def conferir_nao_zero(c: Conferencia, df) -> None:
    """Custo desconhecido volta None — nunca 0,0."""
    print()
    print("=" * 78)
    print("2. CUSTO DESCONHECIDO E None, NUNCA ZERO")
    print("=" * 78)
    import pandas as pd

    zeros = 0
    vazios = 0
    for ano in imposto.anos_disponiveis(df):
        bens = imposto.bens_e_direitos(ano)
        if bens.empty:
            continue
        for _, linha in bens.iterrows():
            custo = linha["custo"]
            if pd.isna(custo):
                vazios += 1
                continue
            if float(custo) == 0.0:
                zeros += 1
                c.exigir(bool(linha["fonte_custo"]),
                         f"{ano}/{linha['nome']}: custo 0,00 sem fonte — "
                         f"'nao sei' virou 'custou nada'")
    c.exigir(True, "varredura concluida")
    print(f"  {vazios} custos vazios (corretos), {zeros} zeros explicitos")


def conferir_plr(c: Conferencia, df) -> None:
    """A PLR nunca entra no rendimento tributavel."""
    print()
    print("=" * 78)
    print("3. A PLR NAO VAZA PARA O RENDIMENTO TRIBUTAVEL")
    print("=" * 78)
    for ano in imposto.anos_disponiveis(df):
        rendimentos = imposto.rendimentos(df, ano)
        if rendimentos.empty:
            continue
        plr = rendimentos[rendimentos["categoria"] == "PLR"]
        if plr.empty:
            continue
        ficha = str(plr["ficha"].iloc[0])
        c.exigir(ficha == imposto.FICHA_EXCLUSIVA,
                 f"{ano}: PLR foi para a ficha {ficha!r}")
        c.exigir(str(plr["codigo"].iloc[0] or "").startswith("11"),
                 f"{ano}: PLR sem o codigo 11")

        por_ficha = imposto.total_por_ficha(rendimentos)
        tributavel = por_ficha.get(imposto.FICHA_TRIBUTAVEL, 0.0)
        valor_plr = float(plr["valor"].sum())
        salario = float(
            rendimentos[rendimentos["categoria"] == "Salário"]["valor"].sum())
        c.exigir(abs(tributavel - salario) < 0.01,
                 f"{ano}: tributavel {tributavel:.2f} != salario "
                 f"{salario:.2f} — algo a mais entrou ali")
        print(f"  {ano}: tributavel R$ {tributavel:>11,.2f} | "
              f"PLR separada R$ {valor_plr:>11,.2f}")


def conferir_ano_vazio(c: Conferencia, df) -> None:
    """Ano sem dado devolve tabela vazia, nao erro."""
    print()
    print("=" * 78)
    print("4. ANO SEM DADO NAO QUEBRA")
    print("=" * 78)
    for ano in ("1999", "2099", "", "nao-e-ano"):
        try:
            resumo = imposto.resumo(df, ano)
            c.exigir(resumo["rendimentos"].empty,
                     f"ano {ano!r} devolveu rendimentos")
            c.exigir(resumo["bens"].empty, f"ano {ano!r} devolveu bens")
            c.exigir(resumo["retido"].empty, f"ano {ano!r} devolveu imposto")
        except Exception as erro:
            c.exigir(False, f"ano {ano!r} levantou {type(erro).__name__}: {erro}")
    print("  4 anos impossiveis, nenhuma excecao")


def conferir_fonte_fraca(c: Conferencia, df) -> None:
    """Custo vindo de 'valor_aplicado' sempre aparece como pendente."""
    print()
    print("=" * 78)
    print("5. A FONTE QUE MENTE SEMPRE E DENUNCIADA")
    print("=" * 78)
    total_fracos = 0
    for ano in imposto.anos_disponiveis(df):
        bens = imposto.bens_e_direitos(ano)
        if bens.empty:
            continue
        faltando = imposto.custos_faltando(bens)
        nomes_pendentes = set(faltando["nome"])
        fracos = bens[bens["fonte_custo"] == "valor_aplicado"]
        total_fracos += len(fracos)
        for _, linha in fracos.iterrows():
            c.exigir(linha["nome"] in nomes_pendentes,
                     f"{ano}/{linha['nome']}: custo de 'valor_aplicado' "
                     f"passou como se fosse confiavel")
    c.exigir(True, "varredura concluida")
    print(f"  {total_fracos} custos de fonte fraca, todos marcados como pendentes")


def conferir_planejado(c: Conferencia, df) -> None:
    """Ligado, a projecao cai exatamente o valor planejado."""
    print()
    print("=" * 78)
    print("6. O GASTO PLANEJADO ENTRA PELO VALOR CERTO")
    print("=" * 78)
    mes_base = "2026-08"
    planejados = planejamento.gastos_planejados(mes_base, 18)
    total = float(planejados["valor"].sum()) if not planejados.empty else 0.0

    desligado = planejamento.projecao_caixa(df, mes_base, 18)
    ligado = planejamento.projecao_caixa(df, mes_base, 18,
                                         incluir_planejados=True)
    c.exigir(not desligado.empty and not ligado.empty, "projecao vazia")
    if desligado.empty or ligado.empty:
        return

    fim_desligado = float(desligado["saldo_acumulado"].iloc[-1])
    fim_ligado = float(ligado["saldo_acumulado"].iloc[-1])
    c.exigir(abs((fim_desligado - fim_ligado) - total) < 0.01,
             f"diferenca {fim_desligado - fim_ligado:.2f} != planejado "
             f"{total:.2f}")

    for nome, tabela in (("desligado", desligado), ("ligado", ligado)):
        c.exigir("gastos_planejados" in tabela.columns,
                 f"{nome}: falta a coluna gastos_planejados")
        c.exigir(abs(float(tabela["gastos_planejados"].sum()) - total) < 0.01,
                 f"{nome}: a coluna nao soma o total planejado")

    if not planejados.empty:
        descricoes = list(planejados["descricao"])
        c.exigir(len(descricoes) == len(set(descricoes)),
                 f"descricao repetida em gastos_planejados: {descricoes}")
    print(f"  planejado R$ {total:,.2f} | fim {fim_desligado:,.2f} -> "
          f"{fim_ligado:,.2f}")


def conferir_intocado(c: Conferencia, df) -> None:
    """Desligado, a projecao e identica a que ele ja usa."""
    print()
    print("=" * 78)
    print("7. DESLIGADO, A PROJECAO NAO MUDOU")
    print("=" * 78)
    mes_base = "2026-08"
    projecao = planejamento.projecao_caixa(df, mes_base, 18)
    c.exigir(not projecao.empty, "projecao vazia")
    if projecao.empty:
        return

    acumulado = 0.0
    for _, linha in projecao.iterrows():
        antigo = (float(linha["fixos"]) + float(linha["parcelas_cartao"])
                  + float(linha["outras_variaveis"]))
        c.exigir(abs(float(linha["total_despesas"]) - antigo) < 0.01,
                 f"{linha['mes']}: total_despesas {linha['total_despesas']:.2f} "
                 f"!= soma antiga {antigo:.2f} — o planejado vazou com o "
                 f"botao desligado")
        acumulado += float(linha["receita_prevista"]) - antigo
        c.exigir(abs(float(linha["saldo_acumulado"]) - acumulado) < 0.01,
                 f"{linha['mes']}: acumulado divergiu")
    print(f"  {len(projecao)} meses reconferidos pela formula antiga")


def conferir_gravacao(c: Conferencia, df) -> None:
    """Gravar custo em mes sem foto tem de RECUSAR, nao fingir que gravou."""
    print()
    print("=" * 78)
    print("8. GRAVAR EM MES SEM FOTO RECUSA")
    print("=" * 78)
    papel = banco.consultar_um(
        """SELECT investimento_id AS id, MAX(mes) AS mes
             FROM investimentos_saldos GROUP BY investimento_id LIMIT 1""")
    if not papel:
        print("  (sem saldo nenhum — pule)")
        return

    ok = imposto.salvar_custo(int(papel["id"]), papel["mes"], 1234.56, "manual")
    c.exigir(ok is True, "gravar em mes existente devolveu False")
    lido = banco.consultar_um(
        """SELECT custo_aplicado AS c, fonte_custo AS f
             FROM investimentos_saldos WHERE investimento_id = ? AND mes = ?""",
        (int(papel["id"]), papel["mes"]))
    c.exigir(lido is not None and abs(float(lido["c"]) - 1234.56) < 0.01,
             "o custo nao foi gravado no mes que existe")
    c.exigir(lido is not None and lido["f"] == "manual",
             "a procedencia nao foi gravada")

    antes = banco.consultar_um(
        "SELECT COUNT(*) AS n FROM investimentos_saldos")["n"]
    recusou = imposto.salvar_custo(int(papel["id"]), "2099-12", 999.99, "manual")
    depois = banco.consultar_um(
        "SELECT COUNT(*) AS n FROM investimentos_saldos")["n"]
    c.exigir(recusou is False,
             "gravar em mes sem foto devolveu True — o app diria 'salvo' "
             "sem ter salvado")
    c.exigir(antes == depois,
             "a gravacao em mes inexistente criou linha do nada")

    for ano in imposto.anos_disponiveis(df):
        bens = imposto.bens_e_direitos(ano)
        if bens.empty:
            continue
        for _, linha in bens.iterrows():
            existe = banco.consultar_um(
                """SELECT 1 FROM investimentos_saldos s
                     JOIN investimentos i ON i.id = s.investimento_id
                    WHERE i.nome = ? AND s.mes = ?""",
                (linha["nome"], linha["mes_do_dado"]))
            c.exigir(existe is not None,
                     f"{ano}/{linha['nome']}: mes_do_dado "
                     f"{linha['mes_do_dado']!r} nao tem linha de saldo")
    print("  grava onde existe, recusa onde nao existe, sem criar linha")


def conferir_custo_parcial(c: Conferencia, df) -> None:
    """O custo tirado do extrato so vale se o extrato viu o papel NASCER."""
    print()
    print("=" * 78)
    print("9. CUSTO PARCIAL NAO PASSA POR COMPLETO")
    print("=" * 78)
    inicio, _fim = inv.periodo_do_extrato_da_corretora()
    if not inicio:
        print("  (sem extrato — pule)")
        return

    respondeu = 0
    for papel in banco.consultar("SELECT id, nome FROM investimentos"):
        valor = imposto.custo_pelo_extrato(int(papel["id"]), "2026-08")
        if valor is None:
            continue
        respondeu += 1
        nascimento = banco.consultar_um(
            """SELECT MIN(mes) AS m FROM investimentos_saldos
                WHERE investimento_id = ? AND saldo > 0""", (int(papel["id"]),))
        c.exigir(nascimento is not None and nascimento["m"] >= inicio,
                 f"{papel['nome']}: extrato comeca em {inicio} mas o papel "
                 f"nasce em {nascimento['m'] if nascimento else '?'} — o custo "
                 f"sairia pela metade com rotulo de confiavel")

        saldo = banco.consultar_um(
            """SELECT saldo FROM investimentos_saldos
                WHERE investimento_id = ? AND saldo > 0
                ORDER BY mes DESC LIMIT 1""", (int(papel["id"]),))
        if saldo and float(saldo["saldo"]) > 0:
            proporcao = valor / float(saldo["saldo"])
            c.exigir(proporcao > 0.2,
                     f"{papel['nome']}: custo {valor:.2f} e so "
                     f"{proporcao:.0%} do saldo — cheira a custo parcial")
    c.exigir(True, "varredura concluida")
    print(f"  extrato desde {inicio} · {respondeu} papel(is) com custo aceito")


def conferir_toda_ficha_na_tela(c: Conferencia, df) -> None:
    """Toda ficha que o calculo produz tem um cartao na tela do IR.

    POR QUE ISTO PRECISOU EXISTIR (2026-09-04)
    ------------------------------------------
    A ficha `Rendimentos Isentos e Nao Tributaveis` nasceu em 2026-09-03, para
    a indenizacao. O calculo passou a devolve-la certinho — e a
    tela continuou com tres cartoes: tributavel, exclusiva e triagem. Os
    R$ ···· apareciam so na tabela de baixo, e os tres numeros do topo nao
    somavam o total.

    Um resumo que nao fecha ensina a desconfiar do resumo, que e pior do que
    nao ter resumo. E o defeito era invisivel: nada quebra, nenhum numero fica
    errado — so falta um.

    Esta checagem le a PAGINA (`ast`, sem abrir o Streamlit) e exige que cada
    `FICHA_*` do modulo de calculo seja citada la. Ficha nova sem cartao passa
    a reprovar aqui, no dia em que for criada.
    """
    print()
    print("=" * 78)
    print("10. TODA FICHA TEM CARTAO NA TELA")
    print("=" * 78)

    fichas = {nome: getattr(imposto, nome) for nome in dir(imposto)
              if nome.startswith("FICHA_")}
    pagina = pathlib.Path("paginas/imposto.py").read_text(encoding="utf-8")

    for nome in sorted(fichas):
        c.exigir(f"calc.{nome}" in pagina,
                 f"{nome} ({fichas[nome]}) existe no calculo e nao aparece em "
                 f"paginas/imposto.py — o resumo nao vai fechar")
        print(f"  {nome:<18} {'na tela' if f'calc.{nome}' in pagina else 'FALTANDO'}")

    # E o teste que da sentido ao de cima: os cartoes tem de somar o total.
    tabela = imposto.rendimentos(df, "2026")
    if not tabela.empty:
        por_ficha = tabela.groupby("ficha")["valor"].sum()
        soma = sum(por_ficha.get(v, 0.0) for v in fichas.values())
        c.exigir(abs(soma - float(tabela["valor"].sum())) < 0.01,
                 f"os cartoes somam {soma:.2f} e o total e "
                 f"{tabela['valor'].sum():.2f} — falta uma ficha")
        print(f"  soma das fichas R$ {soma:,.2f} = total R$ "
              f"{tabela['valor'].sum():,.2f}")


def main() -> int:
    """Roda as nove conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("#" * 78)
    print("#  CONFERINDO O IMPOSTO DE RENDA E O GASTO PLANEJADO")
    print("#" * 78)
    print()
    c = Conferencia()
    with banco_descartavel("conferir_imposto"):
        df = dados.carregar_lancamentos()
        conferir_bens(c, df)
        conferir_nao_zero(c, df)
        conferir_plr(c, df)
        conferir_ano_vazio(c, df)
        conferir_fonte_fraca(c, df)
        conferir_planejado(c, df)
        conferir_intocado(c, df)
        conferir_gravacao(c, df)
        conferir_custo_parcial(c, df)
        conferir_toda_ficha_na_tela(c, df)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
