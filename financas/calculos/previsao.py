"""O que um mes JA TEM e o que ainda FALTA acontecer nele.

POR QUE ESTE MODULO EXISTE
==========================
O painel so mostrava mes fechado. Um mes em andamento aparecia pela metade e o
mes seguinte aparecia zerado — mesmo quando ja havia R$ ···· de parcelas
contratadas caindo nele. Em 25/08/2026 o dashboard dizia, na mesma tela:

    setembro: saldo R$ ····        <- "nao aconteceu nada"
    ja contratado p/ out: R$ ····

Ou seja, ele sabia o que vinha e mostrava zero.

A REGRA QUE MANDA AQUI: PREVISAO E O QUE FALTA
==============================================
Pedido dele, e e a parte que faz este modulo ser seguro:

> "assim que as receitas ou despesas vierem, que elas se abatam na previsao
>  para nao serem consideradas 2x. Inclusive, caso a receita tambem nao venha
>  (em caso de demissao, por exemplo)."

Entao a conta nunca e "o esperado do mes". E sempre:

    previsto = max(0, esperado − ja_realizado)

Tres consequencias, e as tres importam:

1. **Nada conta duas vezes.** O salario de agosto ja caiu? A previsao de
   receita de agosto vira zero sozinha, sem ninguem desligar nada.
2. **Mes fechado nao tem previsao.** Assim que o mes acaba, so resta o que
   aconteceu. Se o salario nunca veio, o mes fica como foi — o app nao insiste
   numa receita que nao existiu.
3. **A previsao encolhe sozinha ao longo do mes.** No dia 1 ela e quase tudo;
   no dia 26, quase nada.

DE ONDE VEM O "ESPERADO"
========================
De `planejamento.projecao_caixa`, que ja existe e ja e a ferramenta de
projecao do app. **Nao ha um segundo motor aqui de proposito**: duas
projecoes que discordam na mesma tela seria o defeito que este projeto passa o
tempo todo consertando.
"""

from __future__ import annotations

import pandas as pd

from financas import banco, config, dados
from financas.calculos import fixos, parcelas, planejamento
from financas.formato import mes_para_indice, somar_meses


def _do_mes(df: pd.DataFrame, mes: str) -> pd.DataFrame:
    """As linhas ja lancadas naquele mes."""
    if df.empty or "mes_competencia" not in df.columns:
        return df
    return df[df["mes_competencia"] == mes]


def baldes_do_mes(df: pd.DataFrame, mes: str) -> dict:
    """Reparte a despesa JA REALIZADA do mes em tres baldes que nao se cruzam.

    POR QUE ISTO PRECISA EXISTIR. A previsao abate o que ja aconteceu do que
    era esperado. Fazer isso no TOTAL parece certo e quebra quando um balde
    estoura e o outro nao: se voce gastou R$ ···· em variaveis e ainda nao
    pagou o aluguel, `max(0, esperado − realizado)` conclui que quase nada
    falta — o estouro do variavel "comeu" os fixos que ainda vao cair. O erro e
    sempre para o lado otimista, que e o pior lado.

    Abater balde por balde exige que os baldes PARTICIONEM a despesa: todo
    lancamento em exatamente um, pela mesma precedencia que
    `fixos.situacao_no_mes` usa do outro lado —

        parcela  >  fixo  >  avulsa

    E essa igualdade que torna aritmeticamente impossivel abater o mesmo real
    duas vezes, e e o que `conferir_previsao` mede.

    Devolve os tres totais e os tres conjuntos de `id`, para a prova poder
    conferir que nenhum id aparece em dois baldes.
    """
    vazio = {"parcela": 0.0, "fixo": 0.0, "avulsa": 0.0,
             "ids_parcela": set(), "ids_fixo": set(), "ids_avulsa": set()}

    do_mes = _do_mes(df, mes)
    if do_mes.empty:
        return vazio
    gastos = dados.despesas(do_mes)
    if gastos.empty:
        return vazio

    e_parcela = gastos["e_parcelado"].fillna(False).astype(bool)
    e_fixo = (
        (gastos["tipo"] == config.TIPO_FIXO)
        | planejamento.e_de_item_fixo(gastos, fixos.cadastro())
    ) & ~e_parcela
    e_avulsa = ~e_parcela & ~e_fixo

    def resumo(mascara) -> tuple[float, set]:
        recorte = gastos[mascara]
        if recorte.empty:
            return 0.0, set()
        return float(-recorte["valor"].sum()), set(recorte["id"].dropna())

    total_parcela, ids_parcela = resumo(e_parcela)
    total_fixo, ids_fixo = resumo(e_fixo)
    total_avulsa, ids_avulsa = resumo(e_avulsa)

    return {
        "parcela": total_parcela, "fixo": total_fixo, "avulsa": total_avulsa,
        "ids_parcela": ids_parcela, "ids_fixo": ids_fixo,
        "ids_avulsa": ids_avulsa,
    }


def do_mes(df: pd.DataFrame, mes: str) -> dict:
    """Quanto o mes ja tem, e quanto ainda falta chegar nele.

    Devolve:
        mes                  o mes pedido
        fechado              o mes ja acabou? entao nao ha previsao nenhuma
        futuro               o mes nem comecou
        receita_realizada    o que ja entrou
        receita_prevista     o que ainda se espera entrar (ja abatido)
        despesa_realizada    o que ja saiu
        despesa_prevista     o que ainda se espera sair (ja abatido)
        receita_total        realizada + prevista
        despesa_total        realizada + prevista
        saldo_total          receita_total − despesa_total
        tem_previsao         ha algo previsto acima de um centavo
        origem_receita       'informado' | 'mediana' | None — DE ONDE saiu o
                             salario esperado
        recorrente_recente   a receita recorrente do ultimo mes fechado, para
                             a tela poder comparar com a previsao
        previsao_desatualizada  o ultimo mes fechado ficou >15% distante da
                             previsao? entao ela pode estar velha

    Para um mes FECHADO, os campos `_prevista` sao zero e os `_total` sao
    iguais aos realizados. Isso e o que garante que o passado nunca mude.

    A DESPESA PREVISTA E SO COMPROMISSO (desde 30/08/2026)
    ======================================================
        despesa_prevista = fixos_a_pagar + parcelas_a_vencer

    A mediana do gasto variavel saiu a pedido dele: *"Quero so o que de
    concreto vai entrar na previsao, que sao as parcelas + gastos fixos."* Todo
    numero aqui passou a ter um contrato ou um cadastro atras, e da para
    conferir linha a linha em `composicao_do_mes`.

    **O QUE ISSO CUSTA, E PRECISA FICAR DITO:** o saldo previsto ficou
    otimista. Setembro/2026 foi de −R$ ···· para +R$ ···· porque
    R$ ···· de gasto variavel — que a historia dele diz que vai acontecer —
    deixaram de ser contados. Nao e erro: e outra pergunta. Mas a tela tem de
    dizer que o variavel nao esta ali, senao o numero mente por omissao.

    Quem quiser o mes com o variavel dentro tem `planejamento.projecao_caixa`,
    que continua somando `outras_variaveis` e mostrando a coluna separada.
    """
    vazio = {
        "mes": mes, "fechado": True, "futuro": False,
        "receita_realizada": 0.0, "receita_prevista": 0.0,
        "despesa_realizada": 0.0, "despesa_prevista": 0.0,
        "receita_total": 0.0, "despesa_total": 0.0, "saldo_total": 0.0,
        "tem_previsao": False, "origem_receita": None,
        "recorrente_recente": 0.0, "previsao_desatualizada": False,
    }
    if not mes:
        return vazio

    do_mes_df = _do_mes(df, mes)
    receita_realizada = dados.total_receita(do_mes_df)
    despesa_realizada = dados.total_despesa(do_mes_df)

    em_andamento = dados.mes_esta_em_andamento(mes)
    resultado = {
        **vazio,
        "mes": mes,
        "fechado": not em_andamento,
        "futuro": dados.mes_e_futuro(mes),
        "receita_realizada": receita_realizada,
        "despesa_realizada": despesa_realizada,
        "receita_total": receita_realizada,
        "despesa_total": despesa_realizada,
        "saldo_total": receita_realizada - despesa_realizada,
    }
    if not em_andamento:
        return resultado

    esperado = planejamento.projecao_caixa(df, somar_meses(mes, -1), 1)
    if esperado.empty:
        return resultado
    linha = esperado.iloc[0]

    salario_esperado = float(linha["receita_prevista"]) - float(
        _receitas_lancadas_no_mes(df, mes))
    salario_recebido = _recorrente_do_mes(df, mes)
    receita_prevista = max(0.0, salario_esperado - salario_recebido)
    situacao = fixos.situacao_no_mes(fixos.cadastro(), df, mes,
                                     somar_meses(mes, -1))
    fixos_a_pagar = (
        float(situacao[situacao["situacao"] == config.SITUACAO_PREVISTO]
              ["falta_no_mes"].sum()) if not situacao.empty else 0.0)
    parcelas_a_vencer = parcelas.previsto_no_mes(df, somar_meses(mes, -1), mes)
    despesa_prevista = fixos_a_pagar + parcelas_a_vencer

    informado = banco.obter_parametro_num("salario_previsto", 0.0)
    origem = "informado" if informado and informado > 0 else "mediana"

    recorrente_recente = _recorrente_do_mes(df, _ultimo_mes_fechado(mes))
    distante = (recorrente_recente > 0 and salario_esperado > 0
                and abs(recorrente_recente - salario_esperado)
                / salario_esperado > 0.15)

    resultado.update({
        "origem_receita": origem,
        "recorrente_recente": recorrente_recente,
        "previsao_desatualizada": bool(distante),
        "receita_prevista": receita_prevista,
        "despesa_prevista": despesa_prevista,
        "receita_total": receita_realizada + receita_prevista,
        "despesa_total": despesa_realizada + despesa_prevista,
        "saldo_total": (receita_realizada + receita_prevista)
                       - (despesa_realizada + despesa_prevista),
        "tem_previsao": (receita_prevista + despesa_prevista) > 0.01,
    })
    return resultado


def _ultimo_mes_fechado(antes_de: str) -> str | None:
    """O mes fechado mais recente antes de `antes_de`.

    NAO e simplesmente `mes − 1`. Olhando para setembro, o mes anterior e
    agosto — que ainda esta acontecendo. No dia 3 de agosto a receita
    recorrente dele seria quase zero, e comparar a previsao com isso dispararia
    um "previsao desatualizada" todo comeco de mes, sem nada ter mudado.

    So mes fechado serve de regua: ele ja tem a historia inteira.
    """
    if not antes_de:
        return None
    passo = somar_meses(antes_de, -1)
    for _ in range(24):
        if not passo:
            return None
        if not dados.mes_esta_em_andamento(passo):
            return passo
        passo = somar_meses(passo, -1)
    return None


def _recorrente_do_mes(df: pd.DataFrame, mes: str) -> float:
    """A receita RECORRENTE ja recebida no mes — tudo que nao e extraordinario.

    COMPARAR IGUAL COM IGUAL. O esperado que vem de `projecao_caixa` e a
    mediana de `receita − receita_extraordinaria`: salario MAIS as outras
    entradas que se repetem (cashback, reembolso pequeno). Confrontar isso so
    com a categoria `Salário` deixava um residuo que nunca fechava — agosto
    previa R$ ···· de receita "ainda por vir" com o salario ja na conta.

    Extraordinaria fica de fora dos dois lados: PLR e indenizacao nao se
    esperam todo mes, e some-las aqui apagaria a previsao de um mes inteiro
    por causa de um evento unico.
    """
    if not mes:
        return 0.0
    do_mes_df = _do_mes(df, mes)
    if do_mes_df.empty:
        return 0.0
    recebidas = dados.receitas(do_mes_df)
    if recebidas.empty:
        return 0.0
    extraordinaria = recebidas[
        recebidas["natureza"] == "Receita Extraordinária"]
    total = float(recebidas["valor"].sum())
    extra = float(extraordinaria["valor"].sum()) if not extraordinaria.empty else 0.0
    return total - extra


def _receitas_lancadas_no_mes(df: pd.DataFrame, mes: str) -> float:
    """As receitas ja lancadas naquele mes — o que `projecao_caixa` ja somou.

    Existe so para desfazer essa soma e chegar ao salario esperado puro.
    Ver `do_mes`.
    """
    do_mes_df = _do_mes(df, mes)
    if do_mes_df.empty:
        return 0.0
    return float(dados.receitas(do_mes_df)["valor"].sum())         if not dados.receitas(do_mes_df).empty else 0.0


def parcelas_do_mes(df: pd.DataFrame, mes: str) -> pd.DataFrame:
    """As parcelas contratadas que ainda vao cair no mes, com categoria.

    Colunas: mes, descricao, categoria, grande_categoria, parcela, valor

    Serve para a quebra por categoria de um mes que ainda nao aconteceu: sem
    isto, "Para onde o dinheiro foi" de setembro fica vazio mesmo com
    R$ ···· ja contratados.

    So devolve o que **ainda nao foi faturado**. A parcela que ja esta na base
    (porque a fatura foi importada) fica de fora daqui — ela ja e realizada, e
    conta-la aqui seria conta-la duas vezes.
    """
    colunas = ["mes", "descricao", "categoria", "grande_categoria",
               "parcela", "valor"]
    if not mes or not dados.mes_esta_em_andamento(mes):
        return pd.DataFrame(columns=colunas)

    base = dados.mes_corrente()
    distancia = 1
    passo = base
    while passo < mes and distancia < 60:
        passo = somar_meses(passo, 1)
        if passo == mes:
            break
        distancia += 1
    if mes <= base:
        return pd.DataFrame(columns=colunas)

    detalhe = parcelas.detalhe_futuro(df, base, distancia)
    if detalhe.empty:
        return pd.DataFrame(columns=colunas)
    return detalhe[detalhe["mes"] == mes][colunas]


def composicao_do_mes(df: pd.DataFrame, mes: str,
                      mes_base: str | None = None) -> pd.DataFrame:
    """Cada real que sai (ou ainda vai sair) do mes, com NOME e SITUACAO.

    POR QUE ESTE MODULO GANHOU MAIS UMA FUNCAO
    ==========================================
    Em 30/08/2026 o dashboard de setembro dizia, na mesma tela:

        O mes -> Despesa .................. R$ ····
        Para onde o dinheiro foi .......... R$  R$ ····

    Os dois numeros estavam certos e respondiam perguntas diferentes: o KPI
    somava fixos + parcelas + mediana; a rosca recebia so as parcelas, porque
    a tela injetava apenas `parcelas_do_mes`. **R$ ···· — 82% da previsao —
    nao apareciam em lugar nenhum**: R$ ···· de gastos fixos com nome e
    categoria, e R$ ···· da mediana das variaveis.

    A CORRECAO NAO E SOMAR MAIS UM GRAFICO. E fazer o KPI ser a soma da lista:

        composicao_do_mes(df, mes)["valor"].sum() == do_mes(df, mes)["despesa_total"]

    Os quatro blocos abaixo sao exatamente as quatro parcelas que `do_mes` ja
    soma, montados com as MESMAS chamadas e os MESMOS argumentos. A igualdade
    vale por construcao, nao por coincidencia — e `conferir_previsao` mede.

    AS TRES SITUACOES, e o vocabulario e o mesmo da tela de Gastos Fixos, de
    proposito: inventar sinonimos para os mesmos estados e como ter dois nomes
    para o mesmo numero.

        lançado      ja aconteceu — o lancamento esta na base
        parcela      parcela contratada que ainda vai cair na fatura
        previsto     fixo cadastrado que ainda nao foi pago

    SO COMPROMISSO — A MEDIANA SAIU (30/08/2026)
    ============================================
    A primeira versao trazia uma quarta linha, "Gasto variavel estimado", com a
    mediana dos ultimos 6 meses. Ele pediu para tirar: *"Quero so o que de
    concreto vai entrar na previsao, que sao as parcelas + gastos fixos."*

    E uma escolha de significado, nao um conserto — as duas versoes estavam
    certas para perguntas diferentes:

        com mediana   "quanto o mes provavelmente vai custar"
        so compromisso "quanto ja esta vendido antes de eu decidir nada"

    A segunda e a que ele quer, e e a que se pode conferir linha a linha: todo
    numero aqui tem um contrato ou um cadastro atras. **O preco e que o saldo
    previsto fica otimista** — setembro passou de −R$ ···· para +R$ ····
    ao tirar R$ ···· de gasto variavel que a historia dele diz que vai
    acontecer. Quem le esta tela precisa saber que o variavel nao esta aqui; e
    o que a tarja da secao diz, e e por isso que ela nao pode sumir.

    A mediana continua existindo e visivel em `projecao_caixa`, na coluna
    `outras_variaveis`, que a tela de Planejamento mostra com nome proprio.

    MES FECHADO produz so o primeiro bloco. O passado nunca ganha previsao.

    SOBRE `mes_base`, E POR QUE ELE PRECISOU EXISTIR
    ================================================
    Sem ele, cada mes seria montado olhando do mes imediatamente anterior — que
    e o que `do_mes` faz, e esta certo para UM mes. Mas uma tela que mostra
    set, out e nov lado a lado precisa dos tres olhando do MESMO ponto, senao
    a janela da mediana anda junto com o alvo: medindo aqui, `outras_variaveis`
    vale R$ ···· com base em agosto e R$ ···· com base em outubro.

    O sintoma seria novembro aparecendo como R$ ···· nesta funcao e
    R$ ···· na aba de projecao — dois numeros discordando na mesma tela,
    que e exatamente a doenca que esta funcao existe para curar. Entao quem
    mostra varios meses passa o mesmo `mes_base` para todos, o mesmo que
    entrega a `projecao_caixa`.

    Omitido, vale `mes − 1`, que reproduz `do_mes` exatamente.
    """
    colunas = ["item", "fixo", "categoria", "grande_categoria", "forma",
               "valor", "situacao", "origem"]

    if not mes:
        return pd.DataFrame(columns=colunas)

    cadastro = fixos.cadastro()
    blocos = []

    do_mes_df = _do_mes(df, mes)
    gastos = dados.despesas(do_mes_df) if not do_mes_df.empty else do_mes_df
    if not gastos.empty:
        blocos.append(pd.DataFrame({
            "item": gastos["descricao"],
            "fixo": _nome_do_fixo(gastos, cadastro),
            "categoria": gastos["categoria"],
            "grande_categoria": gastos["grande_categoria"],
            "forma": gastos["origem"].map(
                lambda o: config.FORMA_CARTAO if o == config.ORIGEM_FATURA
                else config.FORMA_CONTA),
            "valor": -gastos["valor"].astype(float),
            "situacao": config.SITUACAO_LANCADO,
            "origem": "lancamento",
        }))

    if not dados.mes_esta_em_andamento(mes):
        return _juntar_composicao(blocos, colunas)

    anterior = mes_base or somar_meses(mes, -1)
    distancia = max(1, (mes_para_indice(mes) or 0)
                    - (mes_para_indice(anterior) or 0))

    situacao = fixos.situacao_no_mes(cadastro, df, mes, anterior)
    if not situacao.empty:
        a_pagar = situacao[situacao["situacao"] == config.SITUACAO_PREVISTO]
        if not a_pagar.empty:
            blocos.append(pd.DataFrame({
                "item": a_pagar["item"],
                "fixo": a_pagar["item"],
                "categoria": a_pagar["categoria"],
                "grande_categoria": a_pagar["grande_categoria"],
                "forma": a_pagar["forma_pagamento"],
                "valor": a_pagar["falta_no_mes"].astype(float),
                "situacao": config.SITUACAO_PREVISTO,
                "origem": "fixo",
            }))

    futuras = parcelas.detalhe_futuro(df, anterior, distancia)
    a_vencer = futuras[futuras["mes"] == mes] if not futuras.empty else futuras
    if not a_vencer.empty:
        blocos.append(pd.DataFrame({
            "item": a_vencer["descricao"] + " — " + a_vencer["parcela"],
            "fixo": "",
            "categoria": a_vencer["categoria"],
            "grande_categoria": a_vencer["grande_categoria"],
            "forma": config.FORMA_CARTAO,
            "valor": a_vencer["valor"].astype(float),
            "situacao": config.SITUACAO_PARCELA,
            "origem": "parcela",
        }))

    return _juntar_composicao(blocos, colunas)


def _nome_do_fixo(gastos: pd.DataFrame, cadastro: pd.DataFrame) -> pd.Series:
    """Para cada lancamento, o nome do gasto fixo a que ele pertence.

    POR QUE ISTO PRECISA EXISTIR. O pedido era simples: "quando efetivamente
    houver o pagamento, ele vai continuar sendo considerado, mas em vez de ser
    previsao sera algo ja pago". A situacao ja mudava sozinha — mas o NOME
    mudava junto. Em setembro a linha se chama "Aluguel"; em agosto, depois de
    pago, ela vira "Pix enviado para Eduardo Moreira de Lima". Mesmo
    dinheiro, mesma finalidade, e impossivel seguir a mesma linha de um mes
    para o outro.

    Entao o `item` continua sendo a verdade crua do extrato — trocar isso
    seria esconder o que o banco escreveu — e esta coluna diz a que item do
    cadastro aquele lancamento pertence. A tela agrupa por ela.

    Reusa `casar_no_historico`, a MESMA regra que decide se um fixo ja foi
    lancado. Se as duas divergissem, um item poderia aparecer como `previsto` e
    ao mesmo tempo ter lancamento apontando para ele.
    """
    nomes = pd.Series("", index=gastos.index, dtype="object")
    if gastos.empty or cadastro.empty:
        return nomes

    descricoes = fixos.descricoes_normalizadas(gastos)
    ativos = cadastro[cadastro["ativo"].fillna(1).astype(bool)]
    for _, item in ativos.iterrows():
        casaram = fixos.casar_no_historico(gastos, item, descricoes)
        nomes[casaram & (nomes == "")] = item["item"]
    return nomes


def _juntar_composicao(blocos: list, colunas: list) -> pd.DataFrame:
    """Empilha os blocos na ordem do maior valor. Vazio devolve o molde."""
    if not blocos:
        return pd.DataFrame(columns=colunas)
    juntos = pd.concat(blocos, ignore_index=True)[colunas]
    return juntos.sort_values("valor", ascending=False).reset_index(drop=True)


def composicao_por(composicao: pd.DataFrame,
                   coluna: str = "grande_categoria") -> pd.DataFrame:
    """Agrupa a composicao no mesmo formato que `dados.por_categoria` devolve.

    Existe para os graficos que ja existem continuarem funcionando sem
    adaptador: eles esperam [coluna, total, quantidade, percentual].

    NAO da para usar `dados.por_categoria` direto aqui — ela chama
    `dados.despesas()`, que depende de `e_despesa`/`natureza` e da convencao de
    que despesa tem valor NEGATIVO. Na composicao o valor ja e positivo (o
    quanto sai), e uma linha prevista nao e um lancamento. Emprestar a funcao
    exigiria fabricar colunas falsas so para satisfazer o filtro — e um
    DataFrame que finge ser lancamento e exatamente o tipo de coisa que volta
    como bug seis meses depois.
    """
    colunas = [coluna, "total", "quantidade", "percentual"]
    if composicao.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (composicao.groupby(coluna)
                .agg(total=("valor", "sum"), quantidade=("valor", "size"))
                .reset_index()
                .sort_values("total", ascending=False))
    soma = float(agrupado["total"].sum())
    agrupado["percentual"] = agrupado["total"] / soma if soma else 0.0
    return agrupado[colunas]


def resumo_da_composicao(composicao: pd.DataFrame) -> dict:
    """Os totais que a tela mostra em cima da tabela.

    `cartao` e `conta` respondem "quanto ja esta vendido antes de eu comprar
    qualquer coisa", separando por onde o dinheiro sai — sao duas datas e dois
    jeitos de reagir, entao somar os dois num numero so apagaria a diferenca
    que interessa.
    """
    vazio = {"total": 0.0, "cartao": 0.0, "conta": 0.0,
             "realizado": 0.0, "a_vir": 0.0, "linhas": 0}
    if composicao.empty:
        return vazio

    e_lancado = composicao["situacao"] == config.SITUACAO_LANCADO

    return {
        "total": float(composicao["valor"].sum()),
        "cartao": float(composicao[
            composicao["forma"] == config.FORMA_CARTAO]["valor"].sum()),
        "conta": float(composicao[
            composicao["forma"] == config.FORMA_CONTA]["valor"].sum()),
        "realizado": float(composicao[e_lancado]["valor"].sum()),
        "a_vir": float(composicao[~e_lancado]["valor"].sum()),
        "linhas": int(len(composicao)),
    }


def rotulo(previsao: dict) -> str:
    """Uma frase curta dizendo o que naquele numero e previsao.

    Existe para a tela nunca mostrar previsao sem dizer que e previsao — a
    regra vale mesmo quando o espaco e pouco.
    """
    if not previsao.get("tem_previsao"):
        return ""
    from financas.formato import fmt_brl_md

    partes = []
    if previsao["receita_prevista"] > 0.01:
        partes.append(f"{fmt_brl_md(previsao['receita_prevista'])} de receita")
    if previsao["despesa_prevista"] > 0.01:
        partes.append(f"{fmt_brl_md(previsao['despesa_prevista'])} de despesa")
    return "inclui " + " e ".join(partes) + " ainda previstos"
