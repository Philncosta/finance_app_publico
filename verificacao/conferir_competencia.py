"""
conferir_competencia.py — prova que a fatura conta no mes do GASTO.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
A migracao 13 reescreveu 3.080 linhas. Uma migracao de dado nao levanta erro
quando erra: ela grava numeros plausiveis, e o estrago aparece semanas depois
como "esse mes parece estranho".

Sao quatro formas de errar aqui, e nenhuma quebra a tela:

1. **Mover dinheiro em vez de mover a janela.** Recuar competencia e
   deslocamento: o total do periodo inteiro tem de sair identico ao centavo.
2. **Mover o que nao devia.** So a fatura recua. Extrato e lancamento manual
   ja contavam no mes em que aconteceram.
3. **Partir um parcelamento.** `chave_parcelamento` e montada a partir da
   competencia. Se as linhas antigas ficarem com a chave velha e a proxima
   importacao calcular com a nova, o mesmo parcelamento vira dois grupos —
   e ninguem percebe ate a conta de "total a vencer" dar errado.
4. **Trocar um desalinhamento por outro.** A tentacao seguinte e empurrar a
   parcela +1 mes na projecao de caixa "porque a fatura vence dia 05". Isso
   separaria a fatura do salario que a paga, que e o problema original de
   cabeca para baixo.

O QUE ELE CONFERE
-----------------
1. TOTAIS       receita, despesa e saldo do periodo inteiro nao mudam
2. SO A FATURA  toda linha de fatura recuou 1 mes; nenhuma outra se moveu
3. GRUPOS       a chave de parcelamento e reproduzivel pela regra atual
4. MESMO DIA    duas compras iguais no mesmo dia nao escondem dinheiro ATIVO
5. CORRENTES    `parcelas.ativos()` acha correntes coerentes
6. IMPORTACAO   o leitor traduz nome de arquivo -> competencia
7. CICLO        cada fatura contem compras de ~dia 26 a ~dia 25 do mes dela
8. ALINHAMENTO  salario e gasto do cartao do mesmo ciclo caem no MESMO mes
9. FUTURO       `mes_e_futuro` separa "nao comecou" de "esta acontecendo"

O ITEM 7 E O MOTIVO DE TUDO ISSO EXISTIR.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_competencia
"""

from __future__ import annotations

from collections import defaultdict

from financas import banco, config, dados
from financas.calculos import parcelas, planejamento
from financas.formato import mes_para_indice, normalizar_texto, somar_meses
from financas.leitores.fatura_csv import (competencia_da_fatura,
                                          mes_do_nome_arquivo)
from verificacao.base import Conferencia, banco_descartavel


def conferir_totais(c: Conferencia, df) -> None:
    """Deslocar janela nao cria nem destroi dinheiro."""
    print("=" * 78)
    print("1. O TOTAL DO PERIODO NAO MUDOU")
    print("=" * 78)
    receita = dados.total_receita(df)
    despesa = dados.total_despesa(df)

    bruto = banco.consultar_um(
        """SELECT
             COALESCE(SUM(CASE WHEN natureza IN ('Receita','Receita Extraordinária')
                               THEN valor END), 0) AS r,
             COALESCE(-SUM(CASE WHEN natureza = 'Despesa' THEN valor END), 0) AS d
           FROM lancamentos""")
    c.exigir(abs(receita - float(bruto["r"])) < 0.01,
             f"receita {receita:.2f} != soma direta {float(bruto['r']):.2f}")
    c.exigir(abs(despesa - float(bruto["d"])) < 0.01,
             f"despesa {despesa:.2f} != soma direta {float(bruto['d']):.2f}")

    por_mes = 0.0
    for mes in sorted(str(m) for m in df["mes_competencia"].dropna().unique()):
        d = df[df["mes_competencia"] == mes]
        por_mes += dados.total_receita(d) - dados.total_despesa(d)
    c.exigir(abs(por_mes - (receita - despesa)) < 0.01,
             f"soma dos meses {por_mes:.2f} != saldo total "
             f"{receita - despesa:.2f} — alguma linha se perdeu")
    print(f"  receita R$ {receita:>13,.2f} | despesa R$ {despesa:>13,.2f}")
    print(f"  soma dos saldos mensais bate com o saldo total")


def conferir_so_a_fatura(c: Conferencia, df) -> None:
    """Toda linha de fatura esta no mes ANTERIOR ao vencimento; as outras nao."""
    print()
    print("=" * 78)
    print("2. SO A FATURA ANDOU")
    print("=" * 78)
    fora = 0
    total = 0
    for linha in banco.consultar(
            """SELECT data, mes_competencia FROM lancamentos
                WHERE origem = 'Fatura'
                  AND (parcela_total IS NULL OR parcela_total <= 1)"""):
        total += 1
        mes_da_compra = str(linha["data"])[:7]
        defasagem = (mes_para_indice(linha["mes_competencia"] or "")
                     or 0) - (mes_para_indice(mes_da_compra) or 0)
        if defasagem not in (0, 1):
            fora += 1
            c.exigir(False,
                     f"compra {linha['data']} caiu em "
                     f"{linha['mes_competencia']} (defasagem {defasagem})")
    c.exigir(fora == 0, f"{fora} compras fora da janela do ciclo")
    print(f"  {total} compras a vista, {total - fora} dentro da janela do ciclo")

    desalinhados = banco.consultar_um(
        """SELECT COUNT(*) AS n FROM lancamentos
            WHERE origem <> 'Fatura'
              AND substr(data, 1, 7) <> mes_competencia""")["n"]
    c.exigir(desalinhados == 0,
             f"{desalinhados} linhas de extrato/manual com competencia "
             f"diferente do mes da data")
    print(f"  extrato e manual: {desalinhados} desalinhados (esperado 0)")


def conferir_grupos(c: Conferencia, df) -> None:
    """A chave de parcelamento junta o que tem de juntar."""
    print()
    print("=" * 78)
    print("3. OS GRUPOS DE PARCELAMENTO ESTAO INTEIROS")
    print("=" * 78)
    grupos = defaultdict(list)
    for r in banco.consultar(
            """SELECT id, chave_parcelamento, descricao, parcela_atual,
                      parcela_total, mes_competencia
                 FROM lancamentos WHERE chave_parcelamento IS NOT NULL"""):
        grupos[r["chave_parcelamento"]].append(r)

    colisoes: list[tuple[str, list]] = []
    for chave, linhas in grupos.items():
        totais = {l["parcela_total"] for l in linhas}
        c.exigir(len(totais) == 1,
                 f"grupo {chave!r} mistura parcela_total {totais}")
        atuais = [l["parcela_atual"] for l in linhas]
        if len(atuais) != len(set(atuais)):
            colisoes.append((chave, sorted(atuais)))
        for l in linhas:
            indice = mes_para_indice(l["mes_competencia"])
            esperada = (f"{normalizar_texto(l['descricao'])}|"
                        f"{l['parcela_total']}|"
                        f"{indice - (l['parcela_atual'] - 1)}")
            c.exigir(l["chave_parcelamento"] == esperada,
                     f"id {l['id']}: chave {l['chave_parcelamento']!r} != "
                     f"{esperada!r} — a proxima importacao criaria outro grupo")
    print(f"  {len(grupos)} grupos, todos reprodutiveis pela regra atual")

    if colisoes:
        print(f"  {len(colisoes)} chave(s) compartilhada(s) por mais de uma "
              f"compra — normal, a data separa:")
        for chave, atuais in colisoes:
            print(f"    · {chave}  parcelas {atuais}")


def conferir_compras_no_mesmo_dia(c: Conferencia, df) -> None:
    """Duas compras iguais NO MESMO DIA somem uma dentro da outra.

    `parcelamentos()` agrupa por `chave_parcelamento` **mais data**, e isso
    resolve o caso comum: duas idas a mesma loja em dias diferentes viram duas
    linhas, cada uma com seu valor.

    O que a data NAO resolve e quando as duas compras sao no MESMO dia:

        07/07/2026  MERCADOLIVRE  R$ ····  1/2   <- some
        07/07/2026  MERCADOLIVRE  R$ ····  1/2   <- fica

    Mesma descricao, mesmo total de parcelas, mesmo mes E mesmo dia: nada nas
    colunas separa as duas. `groupby(chave, data).tail(1)` fica com uma so, e a
    outra desaparece da visao de parcelamentos.

    E DUAS SITUACOES DIFERENTES CAEM AQUI — a tela nao pode confundi-las:

      compras distintas     duas idas a loja no mesmo dia. Uma some.
      duplicata estornada   a mesma cobranca lancada duas vezes e devolvida.
                            Nada some, porque nunca foram duas compras.

    O SHEIN de 17/10/2025 e o segundo caso: duas linhas de "1 de 6" a
    R$ ···· e um credito de R$ ···· na mesma competencia. O MERCADOLIVRE
    de 07/07/2026 e o primeiro: R$ ···· e R$ ···· sem credito nenhum.

    Hoje o prejuizo e zero — os dois casos ja terminaram. Mas se acontecesse
    numa compra em aberto, parte da divida ficaria invisivel no "total a
    vencer", que e um numero que ele olha para decidir. E essa a unica
    exigencia deste teste.
    """
    print()
    print("=" * 78)
    print("4. DUAS COMPRAS IGUAIS NO MESMO DIA")
    print("=" * 78)
    grupos = defaultdict(list)
    for r in banco.consultar(
            """SELECT id, chave_parcelamento, data, valor, parcela_atual,
                      parcela_total, descricao, mes_competencia
                 FROM lancamentos WHERE chave_parcelamento IS NOT NULL"""):
        grupos[(r["chave_parcelamento"], r["data"])].append(r)

    casos = 0
    ativos = parcelas.ativos(df, dados.mes_corrente())
    chaves_ativas = set(ativos["chave"]) if not ativos.empty else set()

    creditos = defaultdict(list)
    for r in banco.consultar(
            """SELECT descricao, mes_competencia, valor
                 FROM lancamentos WHERE origem = 'Fatura' AND valor > 0"""):
        creditos[(normalizar_texto(r["descricao"]),
                  r["mes_competencia"])].append(float(r["valor"]))

    for (chave, data), linhas in grupos.items():
        atuais = [l["parcela_atual"] for l in linhas]
        if len(atuais) == len(set(atuais)):
            continue
        casos += 1
        primeiras = [l for l in linhas if l["parcela_atual"] == 1]
        visiveis = 1
        descricao = normalizar_texto(linhas[0]["descricao"])
        mes = primeiras[0]["mes_competencia"] if primeiras else linhas[0]["mes_competencia"]
        devolucoes = creditos.get((descricao, mes), [])
        casados = [v for v in devolucoes
                   if any(abs(v - abs(float(l["valor"]))) < 0.05
                          for l in primeiras)]
        estornada = bool(casados)
        credito = casados[0] if casados else 0.0
        rotulo = ("duplicata estornada" if estornada
                  else "compras distintas no mesmo dia")
        valores = ", ".join(f"R$ {abs(float(l['valor'])):,.2f}"
                            for l in primeiras)
        print(f"  · {chave}")
        print(f"      {data}: {len(primeiras)} linhas de parcela 1 "
              f"({valores}); o app enxerga {visiveis} — {rotulo}")
        if estornada:
            print(f"      credito de R$ {credito:,.2f} na mesma competencia")

        c.exigir(chave not in chaves_ativas,
                 f"{chave!r} em {data}: linhas fundidas numa corrente ATIVA — "
                 f"parte da divida ficaria fora do total a vencer")

    c.exigir(True, "varredura concluida")
    if casos:
        print(f"  {casos} caso(s), todos em correntes ENCERRADAS — o total a "
              f"vencer de hoje esta certo")
    else:
        print("  nenhum caso")


def conferir_correntes(c: Conferencia, df) -> None:
    """As correntes em aberto continuam coerentes."""
    print()
    print("=" * 78)
    print("5. AS CORRENTES EM ABERTO")
    print("=" * 78)
    ativos = parcelas.ativos(df, dados.mes_corrente())
    for _, p in ativos.iterrows():
        c.exigir(int(p["parcelas_restantes"]) > 0,
                 f"{p['descricao']}: em aberto sem parcela restante")
        c.exigir(p["mes_termino"] >= dados.mes_corrente(),
                 f"{p['descricao']}: termina em {p['mes_termino']}, no passado")
    print(f"  {len(ativos)} correntes em aberto, todas com termino no futuro")


def conferir_importacao(c: Conferencia) -> None:
    """O leitor traduz o nome do arquivo, e reimportar nao duplica."""
    print()
    print("=" * 78)
    print("6. O LEITOR TRADUZ VENCIMENTO -> COMPETENCIA")
    print("=" * 78)
    casos = [
        ("Fatura2026-09-05.csv", "2026-09", "2026-08"),
        ("Fatura_2026-03.csv", "2026-03", "2026-02"),
        ("fatura 2026-01-05.CSV", "2026-01", "2025-12"),
        ("lixo.csv", None, None),
    ]
    for nome, esperado_nome, esperado_comp in casos:
        c.exigir(mes_do_nome_arquivo(nome) == esperado_nome,
                 f"{nome}: parser devolveu {mes_do_nome_arquivo(nome)!r}")
        c.exigir(competencia_da_fatura(nome) == esperado_comp,
                 f"{nome}: competencia {competencia_da_fatura(nome)!r}, "
                 f"esperado {esperado_comp!r}")
        print(f"  {nome:24} vencimento {str(esperado_nome):>9} -> "
              f"competencia {str(esperado_comp):>9}")

    c.exigir(competencia_da_fatura("Fatura2026-01-05.csv") == "2025-12",
             "janeiro nao voltou para dezembro do ano anterior")


def conferir_ciclo(c: Conferencia) -> None:
    """Cada fatura cobre ~dia 26 do mes anterior a ~dia 25 do mes dela."""
    print()
    print("=" * 78)
    print("7. A JANELA DE CADA FATURA")
    print("=" * 78)
    linhas = banco.consultar(
        """SELECT mes_competencia AS m, MIN(data) AS a, MAX(data) AS b,
                  COUNT(*) AS n
             FROM lancamentos
            WHERE origem = 'Fatura' AND (parcela_total IS NULL OR parcela_total <= 1)
            GROUP BY m HAVING n >= 20 ORDER BY m DESC LIMIT 8""")
    for linha in linhas:
        fim = int(str(linha["b"])[8:10])
        mes_do_fim = str(linha["b"])[:7]
        c.exigir(mes_do_fim == linha["m"],
                 f"comp {linha['m']}: ultima compra em {linha['b']}, "
                 f"fora do mes de competencia")
        c.exigir(fim >= 15,
                 f"comp {linha['m']}: ciclo termina dia {fim}, cedo demais")
        print(f"  comp {linha['m']}: {linha['a']} a {linha['b']} ({linha['n']} compras)")


def conferir_alinhamento(c: Conferencia, df) -> None:
    """Salario e gasto do cartao do mesmo ciclo caem no MESMO mes."""
    print()
    print("=" * 78)
    print("8. SALARIO E FATURA NO MESMO MES — O MOTIVO DE TUDO")
    print("=" * 78)
    meses_com_salario = {
        r["m"] for r in banco.consultar(
            """SELECT mes_competencia AS m FROM lancamentos
                WHERE categoria = 'Salário' GROUP BY m""")}
    meses_com_fatura = {
        r["m"] for r in banco.consultar(
            """SELECT mes_competencia AS m FROM lancamentos
                WHERE origem = 'Fatura' GROUP BY m HAVING COUNT(*) >= 20""")}

    # O MES QUE AINDA ESTA ACONTECENDO NAO PODE SER COBRADO (2026-09-03).
    # A fatura de setembro chega no comeco do mes; o salario dele cai no dia
    # 24. Em 03/09 o mes tinha 3 dias de extrato e a fatura inteira — e a
    # checagem acusava desalinhamento onde so havia calendario. Um alarme que
    # dispara todo comeco de mes ensina a ignorar o alarme, que e pior do que
    # nao ter alarme nenhum.
    #
    # `mes_esta_em_andamento` e a mesma regra que as telas usam para nao
    # chamar um mes pela metade de fechamento. O preco disto e real e vale
    # dizer: se o desalinhamento voltar, esta checagem so acusa quando o mes
    # fechar. Por isso o mes posto de lado e IMPRESSO, nao pulado em silencio.
    em_andamento = sorted(m for m in meses_com_fatura
                          if dados.mes_esta_em_andamento(m))
    fechados = meses_com_fatura - set(em_andamento)

    orfaos = sorted(fechados - meses_com_salario)
    c.exigir(not orfaos,
             f"meses com fatura e SEM salario: {orfaos} — o desalinhamento "
             f"voltou")
    print(f"  {len(fechados)} meses fechados com fatura, todos com salario junto")
    for mes in em_andamento:
        tem = "com" if mes in meses_com_salario else "ainda sem"
        print(f"  {mes} de fora: o mes ainda esta acontecendo ({tem} salario)")

    proj = planejamento.projecao_caixa(df, "2026-08", 6)
    grade = parcelas.grade_futura(df, "2026-08", 6)
    por_mes = dict(zip(grade["mes"], grade["total"]))
    for _, linha in proj.iterrows():
        esperado = float(por_mes.get(linha["mes"], 0.0))
        c.exigir(abs(float(linha["parcelas_cartao"]) - esperado) < 0.01,
                 f"{linha['mes']}: projecao usou {linha['parcelas_cartao']:.2f} "
                 f"mas a grade diz {esperado:.2f} — alguem deslocou a parcela")
    print(f"  projecao de caixa usa a parcela na competencia, sem deslocar")


def conferir_futuro(c: Conferencia) -> None:
    """`mes_e_futuro` separa 'nao comecou' de 'esta acontecendo'."""
    print()
    print("=" * 78)
    print("9. MES FUTURO x MES EM ANDAMENTO")
    print("=" * 78)
    corrente = dados.mes_corrente()
    passado = somar_meses(corrente, -1)
    futuro = somar_meses(corrente, 1)

    c.exigir(not dados.mes_e_futuro(passado), f"{passado} marcado como futuro")
    c.exigir(not dados.mes_e_futuro(corrente),
             f"{corrente} e o mes corrente, nao futuro")
    c.exigir(dados.mes_e_futuro(futuro), f"{futuro} deveria ser futuro")
    c.exigir(not dados.mes_e_futuro(None), "None nao e mes futuro")

    c.exigir(dados.mes_esta_em_andamento(corrente),
             f"{corrente} deixou de estar em andamento")
    c.exigir(dados.mes_esta_em_andamento(futuro),
             f"{futuro} tambem esta 'em andamento' (nao fechado)")
    c.exigir(not dados.mes_esta_em_andamento(passado),
             f"{passado} deveria estar fechado")
    print(f"  {passado} fechado | {corrente} em andamento | {futuro} futuro")


def main() -> int:
    """Roda as nove conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("#" * 78)
    print("#  CONFERINDO A COMPETENCIA DA FATURA")
    print("#" * 78)
    print()
    c = Conferencia()
    with banco_descartavel("conferir_competencia"):
        df = dados.carregar_lancamentos()
        conferir_totais(c, df)
        conferir_so_a_fatura(c, df)
        conferir_grupos(c, df)
        conferir_compras_no_mesmo_dia(c, df)
        conferir_correntes(c, df)
        conferir_importacao(c)
        conferir_ciclo(c)
        conferir_alinhamento(c, df)
        conferir_futuro(c)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
