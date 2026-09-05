"""
conferir_previsao.py — prova que previsao nunca vira dinheiro de verdade.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Misturar previsao com realizado nao quebra nada: produz um numero maior, com
cara de numero certo. E o pior tipo de erro possivel num painel de financas,
porque a pessoa decide em cima dele.

A regra que ele pediu, e que este script existe para garantir:

> "assim que as receitas ou despesas vierem, que elas se abatam na previsao
>  para nao serem consideradas 2x. Inclusive, caso a receita tambem nao venha
>  (em caso de demissao, por exemplo)."

O QUE ELE CONFERE
-----------------
1. PASSADO      mes fechado nao tem previsao nenhuma — nunca muda
2. PREVISAO     o mes com receita preve MENOS que um mes vazio
3. ABATIMENTO   tirar a receita faz a previsao crescer o MESMO tanto
4. SEM DIVIDA   previsao nunca e negativa (nao existe "receita a devolver")
5. SOMA         realizado + previsto bate com os totais, ao centavo
6. PARCELAS     as parcelas previstas do mes sao as MESMAS da grade do cartao
7. AGREGADOS    a taxa do periodo e a media movel IGNORAM o mes parcial
8. RATEIO       a PLR rateada por ano soma exatamente a PLR daquele ano
9. ORIGEM       a tela sabe se o numero veio do historico ou de um campo
10. ENVELHECE   mudanca de patamar de renda dispara o aviso, e a regua e
                sempre um mes FECHADO
11. DEDUP       gasto fixo que ja e parcela do cartao entra com ZERO
12. PARTICAO    os tres baldes do realizado somam o total, sem id repetido
13. REGRESSAO   sem cadastro de fixos, a projecao e a formula antiga
14. MEDIANA     a base nova nunca e maior que a antiga
15. INTERRUPTOR desligar um item tira exatamente o valor dele
16. MEDIA 6M    usa so mes fechado, e nunca desaba para zero
17. COMPOSICAO  a tabela item a item soma EXATAMENTE o KPI da tela
18. COM BASE    com base fixa, ela bate com a projecao de caixa
19. TRANSICAO   pagar um fixo muda a situacao, nao o total do mes
21. MESMA BASE  comprometimento + guardado = 100%, sempre

O ITEM 3 E O CORACAO, e ele nao e tautologico: roda a previsao duas vezes, com
e sem a receita ja recebida, e exige que a diferenca seja exatamente o valor
recebido. Se falhar, o painel esta contando o mesmo dinheiro duas vezes.

O ITEM 12 E O QUE SUSTENTA O ABATIMENTO POR BALDE. Se os tres baldes
particionam a despesa realizada — soma exata e nenhum lancamento em dois — e
aritmeticamente impossivel abater o mesmo real duas vezes. Ele nao pode exigir
"igual a ontem", porque a formula mudou de proposito: exige a propriedade.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_previsao
"""

from __future__ import annotations


from financas import banco, config, dados
from financas.calculos import fixos, kpis, parcelas, planejamento, previsao
from financas.formato import somar_meses
from verificacao.base import Conferencia, banco_descartavel


def conferir_passado(c: Conferencia, df) -> None:
    """Mes fechado nao ganha previsao. O passado nao muda."""
    print("=" * 78)
    print("1. MES FECHADO NAO TEM PREVISAO")
    print("=" * 78)
    corrente = dados.mes_corrente()
    fechados = [m for m in sorted(str(x) for x in
                                  df["mes_competencia"].dropna().unique())
                if m < corrente]
    for mes in fechados:
        p = previsao.do_mes(df, mes)
        c.exigir(p["fechado"], f"{mes} nao foi marcado como fechado")
        c.exigir(p["receita_prevista"] == 0.0,
                 f"{mes} recebeu {p['receita_prevista']:.2f} de receita prevista")
        c.exigir(p["despesa_prevista"] == 0.0,
                 f"{mes} recebeu {p['despesa_prevista']:.2f} de despesa prevista")
        do_mes = df[df["mes_competencia"] == mes]
        c.exigir(abs(p["receita_total"] - dados.total_receita(do_mes)) < 0.01,
                 f"{mes}: receita total != realizada")
        c.exigir(abs(p["despesa_total"] - dados.total_despesa(do_mes)) < 0.01,
                 f"{mes}: despesa total != realizada")
    print(f"  {len(fechados)} meses fechados, nenhum com previsao")


def conferir_abatimento(c: Conferencia, df) -> None:
    """O que ja entrou some da previsao — real por real."""
    print()
    print("=" * 78)
    print("2. A PREVISAO E O QUE FALTA")
    print("=" * 78)
    corrente = dados.mes_corrente()
    seguinte = somar_meses(corrente, 1)

    p_corrente = previsao.do_mes(df, corrente)
    p_seguinte = previsao.do_mes(df, seguinte)

    c.exigir(p_corrente["receita_prevista"] <= p_seguinte["receita_prevista"] + 0.01,
             f"o mes corrente preve MAIS receita ({p_corrente['receita_prevista']:.2f}) "
             f"que um mes vazio ({p_seguinte['receita_prevista']:.2f}) — "
             f"o abatimento nao esta acontecendo")
    print(f"  {corrente} (com receita ja lancada): prevé "
          f"R$ {p_corrente['receita_prevista']:,.2f}")
    print(f"  {seguinte} (vazio):                  prevé "
          f"R$ {p_seguinte['receita_prevista']:,.2f}")

    c.exigir(p_corrente["despesa_prevista"] <= p_seguinte["despesa_prevista"] + 0.01,
             f"o mes corrente preve MAIS despesa que um mes vazio — "
             f"o abatimento nao esta acontecendo")


def conferir_salario(c: Conferencia, df) -> None:
    """A receita que CHEGA abate a previsao, real por real.

    A prova nao pode ser "recebeu salario, previsao zera" — isso seria forte
    demais e estaria errado. O esperado e a mediana de TODA a receita
    recorrente (salario + cashback + reembolso pequeno); com o salario na
    conta, ainda pode faltar a parte miuda, e prever isso e o trabalho do
    modulo.

    O que TEM de ser verdade e o abatimento: tirar a receita do mes faz a
    previsao CRESCER exatamente aquele valor. E o mesmo teste, feito de tras
    para frente, e nao e tautologico — ele compara duas execucoes reais.
    """
    print()
    print("=" * 78)
    print("3. A RECEITA QUE CHEGA ABATE A PREVISAO, REAL POR REAL")
    print("=" * 78)
    corrente = dados.mes_corrente()

    com = previsao.do_mes(df, corrente)

    do_mes = df[df["mes_competencia"] == corrente]
    recorrente = do_mes[
        (do_mes["natureza"] == "Receita")
        & (do_mes["categoria"] != "PLR")
    ] if not do_mes.empty else do_mes
    valor_recorrente = float(recorrente["valor"].sum()) if not recorrente.empty else 0.0

    sem = previsao.do_mes(df.drop(index=recorrente.index), corrente)

    cresceu = sem["receita_prevista"] - com["receita_prevista"]
    esperado_maximo = min(valor_recorrente, sem["receita_prevista"])
    c.exigir(abs(cresceu - esperado_maximo) < 0.01,
             f"tirar R$ {valor_recorrente:,.2f} de receita fez a previsao "
             f"crescer R$ {cresceu:,.2f}, esperado R$ {esperado_maximo:,.2f} — "
             f"o abatimento nao e real por real")

    c.exigir(com["receita_total"] <= sem["receita_total"] + valor_recorrente + 0.01,
             "receber dinheiro ja previsto aumentou o total do mes — "
             "e isso e contar duas vezes")

    print(f"  {corrente}: com a receita  -> prevé R$ {com['receita_prevista']:,.2f}")
    print(f"  {corrente}: sem a receita  -> prevé R$ {sem['receita_prevista']:,.2f}")
    print(f"  a diferenca e R$ {cresceu:,.2f} para R$ {valor_recorrente:,.2f} "
          f"de receita recebida")


def conferir_sem_divida(c: Conferencia, df) -> None:
    """Previsao nunca e negativa."""
    print()
    print("=" * 78)
    print("4. PREVISAO NUNCA E NEGATIVA")
    print("=" * 78)
    corrente = dados.mes_corrente()
    for passo in range(0, 7):
        mes = somar_meses(corrente, passo)
        p = previsao.do_mes(df, mes)
        c.exigir(p["receita_prevista"] >= 0,
                 f"{mes}: receita prevista negativa ({p['receita_prevista']})")
        c.exigir(p["despesa_prevista"] >= 0,
                 f"{mes}: despesa prevista negativa ({p['despesa_prevista']})")
    print("  7 meses a frente, nenhuma previsao negativa")


def conferir_soma(c: Conferencia, df) -> None:
    """realizado + previsto = total, ao centavo."""
    print()
    print("=" * 78)
    print("5. AS PARTES SOMAM O TODO")
    print("=" * 78)
    corrente = dados.mes_corrente()
    for passo in range(-3, 4):
        mes = somar_meses(corrente, passo)
        p = previsao.do_mes(df, mes)
        c.exigir(abs((p["receita_realizada"] + p["receita_prevista"])
                     - p["receita_total"]) < 0.01,
                 f"{mes}: receita nao soma")
        c.exigir(abs((p["despesa_realizada"] + p["despesa_prevista"])
                     - p["despesa_total"]) < 0.01,
                 f"{mes}: despesa nao soma")
        c.exigir(abs((p["receita_total"] - p["despesa_total"])
                     - p["saldo_total"]) < 0.01,
                 f"{mes}: saldo nao bate com receita menos despesa")
    print("  7 meses conferidos, todas as partes somam o todo")


def conferir_parcelas(c: Conferencia, df) -> None:
    """As parcelas previstas do mes sao as mesmas da grade do cartao."""
    print()
    print("=" * 78)
    print("6. AS PARCELAS PREVISTAS BATEM COM A GRADE DO CARTAO")
    print("=" * 78)
    corrente = dados.mes_corrente()
    grade = parcelas.grade_futura(df, corrente, 6)
    por_mes = dict(zip(grade["mes"], grade["total"]))

    for passo in range(1, 5):
        mes = somar_meses(corrente, passo)
        do_previsao = previsao.parcelas_do_mes(df, mes)
        soma = float(do_previsao["valor"].sum()) if not do_previsao.empty else 0.0
        esperado = float(por_mes.get(mes, 0.0))
        c.exigir(abs(soma - esperado) < 0.01,
                 f"{mes}: previsao diz R$ {soma:,.2f}, a grade do cartao diz "
                 f"R$ {esperado:,.2f} — duas fontes discordando")
        if esperado > 0:
            print(f"  {mes}: R$ {soma:,.2f} em {len(do_previsao)} parcelas")

    c.exigir(previsao.parcelas_do_mes(df, corrente).empty,
             f"{corrente} tem parcela prevista — ela ja esta na base")


def conferir_agregados(c: Conferencia, df) -> None:
    """A taxa do periodo e a media movel ignoram o mes parcial."""
    print()
    print("=" * 78)
    print("7. OS AGREGADOS IGNORAM O MES PARCIAL")
    print("=" * 78)
    tabela = kpis.taxa_de_poupanca(df)
    c.exigir(not tabela.empty, "tabela da taxa de poupanca vazia")
    if tabela.empty:
        return

    parciais = tabela[tabela["parcial"]]
    c.exigir(len(parciais) <= 1,
             f"{len(parciais)} meses parciais — so o corrente pode ser")

    fechados = tabela[~tabela["parcial"]]
    esperado = (float(fechados["saldo"].sum()) / float(fechados["receita"].sum())
                if float(fechados["receita"].sum()) else 0.0)
    obtido = kpis.taxa_de_poupanca_agregada(tabela)
    c.exigir(abs(obtido - esperado) < 1e-9,
             f"agregada {obtido:.6f} != so-fechados {esperado:.6f} — "
             f"a previsao vazou para o resumo do passado")

    for _, linha in parciais.iterrows():
        anteriores = fechados[fechados["mes"] < linha["mes"]].tail(3)
        if anteriores.empty:
            continue
        c.exigir(abs(float(linha["media_movel"])
                     - float(anteriores["taxa"].mean())) < 1e-9,
                 f"{linha['mes']}: a media movel incluiu o proprio mes parcial")
    print(f"  {len(fechados)} meses medidos, {len(parciais)} parcial; "
          f"agregada {obtido*100:.1f}%")


def conferir_rateio(c: Conferencia, df) -> None:
    """A PLR rateada por ano soma exatamente a PLR daquele ano."""
    print()
    print("=" * 78)
    print("8. O RATEIO DA PLR FECHA POR ANO")
    print("=" * 78)
    tabela = kpis.serie_rateando_plr(df)
    c.exigir(not tabela.empty, "serie rateada vazia")
    if tabela.empty:
        return

    plr_por_ano: dict[str, float] = {}
    for linha in banco.consultar(
            """SELECT substr(mes_competencia, 1, 4) AS ano, SUM(valor) AS v
                 FROM lancamentos WHERE categoria = 'PLR' GROUP BY ano"""):
        plr_por_ano[linha["ano"]] = float(linha["v"] or 0)

    meses_por_ano: dict[str, int] = {}
    rateado_por_ano: dict[str, float] = {}
    for _, linha in tabela.iterrows():
        ano = str(linha["mes"])[:4]
        meses_por_ano[ano] = meses_por_ano.get(ano, 0) + 1
        rateado_por_ano[ano] = rateado_por_ano.get(ano, 0.0) + (
            float(linha["receita_rateada"]) - float(linha["receita_recorrente"]))

    for ano, total in plr_por_ano.items():
        if ano not in rateado_por_ano:
            continue
        esperado = total * meses_por_ano[ano] / 12
        c.exigir(abs(rateado_por_ano[ano] - esperado) < 0.01,
                 f"{ano}: rateado R$ {rateado_por_ano[ano]:,.2f}, esperado "
                 f"R$ {esperado:,.2f} ({meses_por_ano[ano]} meses na serie)")
        completo = " (ano inteiro)" if meses_por_ano[ano] == 12 else ""
        print(f"  {ano}: PLR R$ {total:>11,.2f} -> rateado "
              f"R$ {rateado_por_ano[ano]:>11,.2f} em {meses_por_ano[ano]} "
              f"meses{completo}")

    for _, linha in tabela.iterrows():
        ano = str(linha["mes"])[:4]
        pedaco = float(linha["receita_rateada"]) - float(linha["receita_recorrente"])
        esperado_mes = plr_por_ano.get(ano, 0.0) / 12
        c.exigir(abs(pedaco - esperado_mes) < 0.01,
                 f"{linha['mes']}: recebeu R$ {pedaco:,.2f} de rateio, mas o "
                 f"ano {ano} da R$ {esperado_mes:,.2f} por mes")


def conferir_origem(c: Conferencia, df) -> None:
    """A previsao diz de onde veio, e o valor informado manda."""
    print()
    print("=" * 78)
    print("9. DE ONDE VEIO O NUMERO")
    print("=" * 78)
    corrente = dados.mes_corrente()
    seguinte = somar_meses(corrente, 1)

    banco.definir_parametro("salario_previsto", 0.0)
    automatico = previsao.do_mes(df, seguinte)
    c.exigir(automatico["origem_receita"] == "mediana",
             f"sem valor informado, a origem deveria ser 'mediana', "
             f"veio {automatico['origem_receita']!r}")

    banco.definir_parametro("salario_previsto", 9999.0)
    informado = previsao.do_mes(df, seguinte)
    c.exigir(informado["origem_receita"] == "informado",
             f"com valor informado, a origem deveria ser 'informado', "
             f"veio {informado['origem_receita']!r}")
    c.exigir(abs(informado["receita_prevista"] - 9999.0) < 0.01,
             f"o valor informado nao mandou: previu "
             f"R$ {informado['receita_prevista']:,.2f} em vez de R$ 9.999,00")
    print(f"  sem informar: R$ {automatico['receita_prevista']:,.2f} (mediana)")
    print(f"  informando  : R$ {informado['receita_prevista']:,.2f} (informado)")

    banco.definir_parametro("salario_previsto", 0.0)


def conferir_envelhece(c: Conferencia, df) -> None:
    """Mudanca de patamar dispara o aviso; a regua e sempre mes FECHADO."""
    print()
    print("=" * 78)
    print("10. A PREVISAO AVISA QUANDO ENVELHECE")
    print("=" * 78)
    corrente = dados.mes_corrente()
    seguinte = somar_meses(corrente, 1)

    regua = previsao._ultimo_mes_fechado(seguinte)
    c.exigir(regua is not None, "nao achou mes fechado para servir de regua")
    if regua:
        c.exigir(not dados.mes_esta_em_andamento(regua),
                 f"a regua {regua} ainda esta em andamento")
        c.exigir(regua < corrente,
                 f"a regua {regua} nao e anterior ao mes corrente")
        print(f"  regua de {seguinte}: {regua} (fechado)")

    banco.definir_parametro("salario_previsto", 0.0)
    normal = previsao.do_mes(df, seguinte)

    banco.definir_parametro("salario_previsto",
                            max(1.0, normal["recorrente_recente"]) * 3)
    mudou = previsao.do_mes(df, seguinte)
    c.exigir(mudou["previsao_desatualizada"],
             "a previsao ficou 3x distante do ultimo mes fechado e o aviso "
             "nao acendeu")
    print(f"  previsao 3x acima do ultimo fechado -> aviso: "
          f"{mudou['previsao_desatualizada']}")

    banco.definir_parametro("salario_previsto", 0.0)
    de_volta = previsao.do_mes(df, seguinte)
    c.exigir(de_volta["previsao_desatualizada"] == normal["previsao_desatualizada"],
             "zerar o campo nao devolveu a previsao ao estado automatico")
    print(f"  zerando o campo, volta ao automatico: "
          f"R$ {de_volta['receita_prevista']:,.2f}")


def conferir_dedup(c: Conferencia, df) -> None:
    """Gasto fixo que ja e parcela do cartao entra na previsao com ZERO."""
    print()
    print("=" * 78)
    print("11. FIXO QUE JA E PARCELA NAO CONTA DUAS VEZES")
    print("=" * 78)
    cadastro = fixos.cadastro()
    base = dados.mes_mais_recente() or dados.mes_corrente()
    achados = 0
    for passo in range(1, 13):
        mes = somar_meses(base, passo)
        situacao = fixos.situacao_no_mes(cadastro, df, mes, base)
        if situacao.empty:
            continue
        em_parcela = situacao[situacao["situacao"] == config.SITUACAO_PARCELA]
        for _, linha in em_parcela.iterrows():
            achados += 1
            c.exigir(linha["entra_na_previsao"] == 0.0,
                     f"{mes}: {linha['item']} esta nas parcelas mas entrou "
                     f"com {linha['entra_na_previsao']:.2f}")
        soma = float(situacao["entra_na_previsao"].sum())
        piso = fixos.total_mensal(cadastro, mes)
        suprimido = float(em_parcela["cadastrado"].sum())
        lancados = situacao[situacao["situacao"] == config.SITUACAO_LANCADO]
        ajuste = float((lancados["lancado"] - lancados["cadastrado"]).sum())
        c.exigir(abs((piso - suprimido + ajuste) - soma) < 0.01,
                 f"{mes}: piso {piso:.2f} menos suprimido {suprimido:.2f} "
                 f"mais ajuste {ajuste:.2f} != previsao {soma:.2f}")
    print(f"  {achados} item-mes suprimido(s) por ja estarem nas parcelas")


def conferir_particao(c: Conferencia, df) -> None:
    """Os tres baldes do realizado particionam a despesa. Sem sobreposicao."""
    print()
    print("=" * 78)
    print("12. A PARTICAO DO REALIZADO")
    print("=" * 78)
    corrente = dados.mes_mais_recente() or dados.mes_corrente()
    for passo in range(0, 4):
        mes = somar_meses(corrente, -passo)
        if not mes:
            continue
        baldes = previsao.baldes_do_mes(df, mes)
        soma = baldes["parcela"] + baldes["fixo"] + baldes["avulsa"]
        real = dados.total_despesa(dados.do_mes(df, mes))
        c.exigir(abs(soma - real) < 0.01,
                 f"{mes}: baldes somam {soma:.2f} mas a despesa e {real:.2f}")

        ids = (baldes["ids_parcela"] | baldes["ids_fixo"]
               | baldes["ids_avulsa"])
        total_ids = (len(baldes["ids_parcela"]) + len(baldes["ids_fixo"])
                     + len(baldes["ids_avulsa"]))
        c.exigir(len(ids) == total_ids,
                 f"{mes}: {total_ids - len(ids)} lancamento(s) em dois baldes")
        print(f"  {mes}: parcela {baldes['parcela']:>10,.2f} | "
              f"fixo {baldes['fixo']:>10,.2f} | "
              f"avulsa {baldes['avulsa']:>10,.2f} = {soma:>11,.2f}")


def conferir_regressao(c: Conferencia, df) -> None:
    """Sem cadastro de fixos, a projecao volta a ser a formula antiga."""
    print()
    print("=" * 78)
    print("13. SEM CADASTRO, A PROJECAO E A DE ANTES")
    print("=" * 78)
    base = dados.mes_mais_recente() or dados.mes_corrente()
    banco.executar("DELETE FROM gastos_fixos")
    df_limpo = dados.carregar_lancamentos()
    projecao = planejamento.projecao_caixa(df_limpo, base, 18)
    c.exigir(not projecao.empty, "projecao vazia sem cadastro")
    if projecao.empty:
        return

    grade = parcelas.grade_futura(df_limpo, base, 18)
    por_mes = dict(zip(grade["mes"], grade["total"]))

    gastos = dados.despesas(df_limpo)
    inicio, fim = fixos.janela_fechada(base)
    janela = gastos[(gastos["mes_competencia"] >= inicio)
                    & (gastos["mes_competencia"] <= fim)]
    avulsas = janela[(janela["tipo"] != config.TIPO_FIXO)
                     & (~janela["e_parcelado"])]
    mediana = float(avulsas.groupby("mes_competencia")["valor"]
                    .sum().mul(-1).median()) if not avulsas.empty else 0.0

    for _, linha in projecao.iterrows():
        c.exigir(linha["fixos"] == 0.0,
                 f"{linha['mes']}: cadastro vazio mas fixos = {linha['fixos']:.2f}")
        c.exigir(abs(float(linha["outras_variaveis"]) - mediana) < 0.01,
                 f"{linha['mes']}: mediana {linha['outras_variaveis']:.2f} "
                 f"!= formula antiga {mediana:.2f}")
        c.exigir(abs(float(linha["parcelas_cartao"])
                     - float(por_mes.get(linha["mes"], 0.0))) < 0.01,
                 f"{linha['mes']}: parcelas != grade_futura")
        c.exigir(abs(float(linha["fixos"]) - (float(linha["fixos_conta"])
                     + float(linha["fixos_cartao"]))) < 0.01,
                 f"{linha['mes']}: fixos != conta + cartao")
        c.exigir(abs(float(linha["total_despesas"])
                     - (float(linha["fixos"]) + float(linha["parcelas_cartao"])
                        + float(linha["outras_variaveis"]))) < 0.01,
                 f"{linha['mes']}: total_despesas != soma das partes")
    print(f"  {len(projecao)} meses conferidos contra a formula antiga")


def conferir_mediana(c: Conferencia, df) -> None:
    """A base nova de variaveis e subconjunto da antiga, entao nunca e maior."""
    print()
    print("=" * 78)
    print("14. A MEDIANA NAO CONTA O QUE JA E FIXO")
    print("=" * 78)
    base = dados.mes_mais_recente() or dados.mes_corrente()
    cadastro = fixos.cadastro()
    inicio, fim = fixos.janela_fechada(base)
    gastos = dados.despesas(df)
    janela = gastos[(gastos["mes_competencia"] >= inicio)
                    & (gastos["mes_competencia"] <= fim)]
    antiga = janela[(janela["tipo"] != config.TIPO_FIXO)
                    & (~janela["e_parcelado"])]
    nova = antiga[~planejamento.e_de_item_fixo(antiga, cadastro)]

    por_mes_antiga = antiga.groupby("mes_competencia")["valor"].sum().mul(-1)
    por_mes_nova = nova.groupby("mes_competencia")["valor"].sum().mul(-1)
    for mes, valor in por_mes_antiga.items():
        c.exigir(float(por_mes_nova.get(mes, 0.0)) <= valor + 0.01,
                 f"{mes}: base nova ({por_mes_nova.get(mes, 0.0):.2f}) maior "
                 f"que a antiga ({valor:.2f}) — o filtro adicionou linhas")

    med_antiga = float(por_mes_antiga.median()) if not por_mes_antiga.empty else 0.0
    med_nova = float(por_mes_nova.median()) if not por_mes_nova.empty else 0.0
    c.exigir(med_nova <= med_antiga + 0.01,
             f"mediana nova {med_nova:.2f} > antiga {med_antiga:.2f}")
    removido = float(-antiga["valor"].sum()) - float(-nova["valor"].sum())
    print(f"  mediana antiga R$ {med_antiga:,.2f} | nova R$ {med_nova:,.2f} | "
          f"R$ {removido:,.2f} tirado da janela por ja ser fixo cadastrado")


def conferir_interruptor(c: Conferencia, df) -> None:
    """Desligar um item tira exatamente o valor dele, e nada mais."""
    print()
    print("=" * 78)
    print("15. DESLIGAR UM ITEM E CIRURGICO")
    print("=" * 78)
    base = dados.mes_mais_recente() or dados.mes_corrente()
    mes = somar_meses(base, 1)
    cadastro = fixos.cadastro()
    if cadastro.empty:
        print("  sem cadastro para testar")
        return

    situacao = fixos.situacao_no_mes(cadastro, df, mes, base)
    previstos = situacao[situacao["situacao"] == config.SITUACAO_PREVISTO]
    if previstos.empty:
        print("  nenhum item previsto neste mes")
        return

    alvo = previstos.loc[previstos["entra_na_previsao"].idxmax()]
    antes = planejamento.projecao_caixa(df, base, 1).iloc[0]

    banco.executar("UPDATE gastos_fixos SET considerar_previsao = 0 WHERE id = ?",
                   (int(alvo["id"]),))
    depois = planejamento.projecao_caixa(df, base, 1).iloc[0]

    queda = float(antes["fixos"]) - float(depois["fixos"])
    c.exigir(abs(queda - float(alvo["entra_na_previsao"])) < 0.01,
             f"desligar {alvo['item']} tirou {queda:.2f}, esperado "
             f"{alvo['entra_na_previsao']:.2f}")
    c.exigir(abs(float(antes["parcelas_cartao"])
                 - float(depois["parcelas_cartao"])) < 0.01,
             "desligar um fixo mexeu nas parcelas do cartao")
    c.exigir(abs(float(antes["outras_variaveis"])
                 - float(depois["outras_variaveis"])) < 0.01,
             "desligar um fixo mexeu na media de variaveis")

    banco.executar("UPDATE gastos_fixos SET considerar_previsao = 1 WHERE id = ?",
                   (int(alvo["id"]),))
    de_volta = planejamento.projecao_caixa(df, base, 1).iloc[0]
    c.exigir(abs(float(de_volta["fixos"]) - float(antes["fixos"])) < 0.01,
             "religar o item nao devolveu o valor original")
    print(f"  {alvo['item']}: desligar tirou R$ {queda:,.2f}, religar devolveu")


def conferir_media_seis_meses(c: Conferencia, df) -> None:
    """`Média 6m` usa so mes fechado, e nunca desaba para zero."""
    print()
    print("=" * 78)
    print("16. A MEDIA POR COBRANCA NAO CAI PARA ZERO")
    print("=" * 78)
    base = dados.mes_mais_recente() or dados.mes_corrente()
    mes = somar_meses(base, 1)

    inicio, fim = fixos.janela_fechada(base)
    c.exigir(fim <= base, f"a janela terminou em {fim}, depois de {base}")
    c.exigir(not dados.mes_esta_em_andamento(fim),
             f"a janela terminou em {fim}, que ainda esta em andamento")

    banco.executar(f"UPDATE gastos_fixos SET base_valor = '{config.BASE_MEDIA}'")
    cadastro = fixos.cadastro()
    situacao = fixos.situacao_no_mes(cadastro, df, mes, base)
    for _, linha in situacao.iterrows():
        if linha["situacao"] != config.SITUACAO_PREVISTO:
            continue
        c.exigir(linha["esperado"] > 0.0,
                 f"{linha['item']}: com Média 6m o esperado virou "
                 f"{linha['esperado']:.2f}")
        if linha["media_por_cobranca"] == 0.0:
            c.exigir(abs(linha["esperado"] - linha["cadastrado"]) < 0.01,
                     f"{linha['item']}: sem historico, devia usar o cadastrado")

    banco.executar(
        f"UPDATE gastos_fixos SET base_valor = '{config.BASE_CADASTRADO}'")
    print(f"  janela fechada {inicio}..{fim}; "
          f"{len(situacao)} item(ns) conferido(s) com Média 6m")


def conferir_composicao(c: Conferencia, df) -> None:
    """17. A tabela item a item soma EXATAMENTE o KPI que a tela mostra.

    ESTE E O ITEM QUE FECHA O BURACO DE 30/08/2026. O dashboard mostrava, na
    mesma tela, R$ ···· de despesa prevista e R$ ···· na quebra por
    categoria: 82% da previsao nao aparecia em lugar nenhum, porque a tela
    injetava so as parcelas e deixava fixos e mediana de fora.

    A prova nao pode ser "igual a ontem" — ontem estava errado. Ela exige a
    PROPRIEDADE: a soma da composicao e o total da despesa sao o mesmo numero,
    em todo mes, ao centavo. Enquanto isso valer, a tela nao tem como divergir
    do KPI, porque o KPI e a soma da tabela.

    LINHA NEGATIVA E PERMITIDA, MAS SO DE UM LADO. Existem 111 lancamentos com
    `natureza='Despesa'` e valor POSITIVO na base — estornos de fatura, e
    tambem dinheiro de terceiros que caiu na mesma vala. Eles viram linha
    negativa aqui, e tem de virar: `despesa_total` ja os abate, e recusa-los
    quebraria a soma. O que NAO pode existir e previsao negativa — nao existe
    "conta fixa que devolve dinheiro". Dai a checagem olhar a `origem`, e nao
    o sinal sozinho.

    RODA ANTES DE `conferir_regressao`, de proposito: aquela apaga
    `gastos_fixos` para provar a formula antiga e nao restaura. Rodando depois,
    estas tres conferencias passariam contra um cadastro vazio — verdes, e
    sem ter exercitado nada.
    """
    print("\n[17] COMPOSICAO — a tabela item a item soma o KPI")

    meses = sorted(m for m in df["mes_competencia"].dropna().unique() if m)
    for mes in meses:
        composicao = previsao.composicao_do_mes(df, mes)
        atual = previsao.do_mes(df, mes)
        soma = float(composicao["valor"].sum()) if not composicao.empty else 0.0
        c.exigir(abs(soma - atual["despesa_total"]) < 0.01,
                 f"{mes}: composicao soma {soma:.2f} mas despesa_total e "
                 f"{atual['despesa_total']:.2f}")

        if not composicao.empty:
            negativas = composicao[composicao["valor"] < -0.005]
            c.exigir(
                bool((negativas["origem"] == "lancamento").all()),
                f"{mes}: ha PREVISAO com valor negativo — so lancamento pode "
                f"ser negativo (estorno)")
            c.exigir(
                set(composicao["origem"]) <= {"lancamento", "fixo", "parcela"},
                f"{mes}: composicao tem origem fora de lancamento/fixo/parcela "
                f"— {sorted(set(composicao['origem']))}")

        if not dados.mes_esta_em_andamento(mes):
            situacoes = (set(composicao["situacao"]) if not composicao.empty
                         else set())
            c.exigir(situacoes <= {config.SITUACAO_LANCADO},
                     f"{mes}: mes fechado com situacao alem de lancado — "
                     f"{sorted(situacoes)}")

    print(f"  {len(meses)} meses; soma da composicao == despesa_total em todos")


def conferir_composicao_com_base(c: Conferencia, df) -> None:
    """18. Com base fixa, a composicao bate com a projecao de caixa.

    A COMPOSICAO E SO COMPROMISSO; A PROJECAO SOMA TAMBEM O VARIAVEL. Entao a
    igualdade nao e contra `total_despesas`, e sim contra a parte contratada:

        composicao  ==  fixos + parcelas_cartao        (sem outras_variaveis)

    E essa diferenca que a tela de Planejamento mostra com nome proprio, em vez
    de deixar dois totais discordando em silencio.

    POR QUE ISTO E UMA SEGUNDA PROVA, e nao a mesma de cima. A janela da
    mediana anda com o `mes_base`, e com ela anda o recorte de meses fechados
    que decide quais parcelas ja foram faturadas. Sem base fixa, os meses de
    uma tela que mostra varios ficariam cada um olhando de um ponto diferente.
    """
    print("\n[18] COMPOSICAO COM BASE — bate com a parte contratada")

    base = dados.mes_corrente()
    projecao = planejamento.projecao_caixa(df, base, 6)
    if projecao.empty:
        print("  sem projecao para conferir")
        return

    for _, linha in projecao.iterrows():
        composicao = previsao.composicao_do_mes(df, linha["mes"], mes_base=base)
        soma = float(composicao["valor"].sum()) if not composicao.empty else 0.0
        contratado = float(linha["fixos"]) + float(linha["parcelas_cartao"])
        c.exigir(abs(soma - contratado) < 0.01,
                 f"{linha['mes']}: composicao com base {base} soma {soma:.2f} "
                 f"mas fixos+parcelas da {contratado:.2f}")
        c.exigir(float(linha["outras_variaveis"]) >= 0.0,
                 f"{linha['mes']}: outras_variaveis negativa")

    print(f"  base {base}; {len(projecao)} meses conferidos contra "
          f"fixos + parcelas_cartao")


def conferir_transicao(c: Conferencia, df) -> None:
    """19. Pagar um gasto fixo muda a SITUACAO, nao o total do mes.

    O pedido, em 30/08/2026: "vamos considerar um pagamento de 2k de aluguel.
    Quando efetivamente houver o pagamento, ele vai continuar sendo considerado
    no saldo do mes, mas em vez de ser previsao sera algo ja pago."

    A prova percorre os itens que aparecem como `previsto` num mes e `lancado`
    noutro e exige as duas metades:

        1. a coluna `fixo` os identifica com o MESMO nome nos dois meses —
           senao a linha existe, o total fecha, e ainda assim e impossivel
           seguir o mesmo gasto de um mes para o outro
        2. cada um aparece exatamente uma vez por mes, nunca nos dois estados
           ao mesmo tempo, que seria contar duas vezes
    """
    print("\n[19] TRANSICAO — pago muda a situacao, nao o total")

    meses = sorted(m for m in df["mes_competencia"].dropna().unique() if m)
    vistos: dict[str, set] = {}
    for mes in meses[-8:]:
        composicao = previsao.composicao_do_mes(df, mes)
        if composicao.empty:
            continue
        nomeados = composicao[composicao["fixo"].astype(bool)]
        for nome, linhas in nomeados.groupby("fixo"):
            situacoes = set(linhas["situacao"])
            c.exigir(
                not (config.SITUACAO_PREVISTO in situacoes
                     and config.SITUACAO_LANCADO in situacoes),
                f"{mes}: '{nome}' aparece como previsto E lancado no mesmo mes")
            vistos.setdefault(nome, set()).update(situacoes)

    atravessam = [nome for nome, situacoes in vistos.items()
                  if {config.SITUACAO_PREVISTO, config.SITUACAO_LANCADO}
                  <= situacoes]
    c.exigir(bool(atravessam),
             "nenhum gasto fixo aparece como previsto num mes e lancado "
             "noutro — a transicao nao esta sendo exercitada")

    print(f"  {len(vistos)} item(ns) rastreados pelo nome; "
          f"{len(atravessam)} atravessam previsto -> lancado")


def conferir_mesma_base(c: Conferencia, df) -> None:
    """Os KPIs do mes tem de falar todos da MESMA base.

    POR QUE ISTO PRECISOU EXISTIR (2026-09-03). A faixa do Dashboard mostrava,
    lado a lado:

        Receita R$ ···· · Despesa R$ ···· · Comprometimento 120,8%

    Quem divide os dois numeros que estao na tela acha 76,5%. O comprometimento
    vinha de `resultado_do_mes`, que e despesa REALIZADA sobre receita
    REALIZADA, enquanto os vizinhos ja vinham com previsao. E a dica dizia
    "despesa dividida por receita", o que era literalmente falso para os
    numeros ao lado. Ele perguntou, e estava certo.

    A CONTA QUE DENUNCIA: comprometimento e taxa de poupanca sao duas fatias da
    mesma receita. Somam 100%, sempre. Somavam 144,3%.

    Esta checagem nao olha a tela — ela exige a identidade que a tela precisa
    respeitar. Se alguem voltar a misturar as bases, a soma sai de 100%.
    """
    print()
    print("=" * 78)
    print("21. OS KPIS DO MES FALAM DA MESMA BASE")
    print("=" * 78)

    for mes in sorted(df["mes_competencia"].dropna().unique())[-8:]:
        prev = previsao.do_mes(df, mes)
        resultado = kpis.resultado_do_mes(df, mes)

        receita = (prev["receita_total"] if prev["tem_previsao"]
                   else resultado["receita_total"])
        despesa = (prev["despesa_total"] if prev["tem_previsao"]
                   else resultado["despesa"])
        saldo = prev["saldo_total"] if prev["tem_previsao"] else resultado["saldo"]
        if not receita:
            continue

        comprometido = despesa / receita
        guardado = saldo / receita
        c.exigir(abs(comprometido + guardado - 1.0) < 0.0001,
                 f"{mes}: comprometido {comprometido:.4%} + guardado "
                 f"{guardado:.4%} = {comprometido + guardado:.4%}, tinha de "
                 f"dar 100% — as duas fatias sao da mesma receita")

        # E a armadilha exata que existia: usar o comprometimento realizado
        # ao lado de numeros com previsao.
        if prev["tem_previsao"]:
            c.exigir(
                abs(resultado["comprometimento"] - comprometido) > 1e-9
                or abs(prev["receita_prevista"]) < 0.01,
                f"{mes}: com previsao, o comprometimento realizado nao pode "
                f"ser o mesmo numero — se for, alguem juntou as bases")
        print(f"  {mes}  comprometido {comprometido:>7.1%} + guardado "
              f"{guardado:>7.1%} = {comprometido + guardado:.1%}")


def main() -> int:
    """Roda as vinte e uma conferencias. Devolve 0 se tudo passou, 1 se falhou."""
    print()
    print("#" * 78)
    print("#  CONFERINDO A PREVISAO DO MES E O RATEIO DA PLR")
    print("#" * 78)
    print()
    c = Conferencia()
    with banco_descartavel("conferir_previsao"):
        df = dados.carregar_lancamentos()
        conferir_passado(c, df)
        conferir_abatimento(c, df)
        conferir_salario(c, df)
        conferir_sem_divida(c, df)
        conferir_soma(c, df)
        conferir_parcelas(c, df)
        conferir_agregados(c, df)
        conferir_rateio(c, df)
        conferir_origem(c, df)
        conferir_envelhece(c, df)
        conferir_dedup(c, df)
        conferir_particao(c, df)
        conferir_mediana(c, df)
        conferir_media_seis_meses(c, df)
        conferir_interruptor(c, df)
        conferir_composicao(c, df)
        conferir_composicao_com_base(c, df)
        conferir_transicao(c, df)
        conferir_regressao(c, df)
        conferir_mesma_base(c, df)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
