"""
investimentos.py — A carteira: o que voce tem aplicado e quanto rendeu.
==============================================================================

O PROBLEMA QUE ESTE MODULO RESOLVE
----------------------------------
O extrato da conta corrente sabe dizer quanto dinheiro SAIU para a conta de
investimento. Ele nao sabe dizer:

    - em QUE voce aplicou (CDB? Tesouro? fundo?)
    - quanto aquilo VALE hoje
    - quanto RENDEU

Nenhum desses tres dados aparece no extrato — eles vivem na corretora. Por
isso a carteira tem duas metades, e entender a divisao e entender o modulo:

    METADE AUTOMATICA   vem dos lancamentos. Quanto voce mandou para
                        investimento, quanto tirou. Nao precisa de trabalho
                        nenhum: sai da importacao do extrato.

    METADE MANUAL       vem de voce. Quais sao os investimentos e quanto cada
                        um vale no fim do mes. Toma dois minutos por mes:
                        abrir a corretora e anotar os saldos.

E a `conciliar()` cruza as duas: "voce mandou X para investimento; a soma da
sua carteira e Y; a diferenca e Z". Se Z for muito diferente do rendimento
esperado, ou falta cadastrar alguma coisa, ou algum saldo esta desatualizado.

A CONTA DO RENDIMENTO
---------------------
Nao da para simplesmente comparar dois saldos, porque entre um mes e outro
voce pode ter aportado ou resgatado. O rendimento e o que sobra depois de
tirar essas duas coisas:

    rendimento(mes) = saldo(mes) − saldo(mes anterior) − aporte(mes) + resgate(mes)

Exemplo: o saldo saiu de R$ ···· para R$ ···· mas voce aportou R$ ····
no meio. O rendimento foi R$ ···· e nao R$ ····

Todas as funcoes aqui sao puras ou leem o banco — nenhuma importa Streamlit.
"""

from __future__ import annotations

import re

import pandas as pd

from financas import banco, cambio
from datetime import date

from financas.formato import mes_para_indice, normalizar_texto, vazio

TIPOS = [
    "Renda Fixa",
    "Tesouro Direto",
    "Fundo",
    "Renda Variável",
    "Previdência",
    "Poupança",
    "Cripto",
    "Outro",
]

INDEXADORES = ["CDI", "IPCA+", "Prefixado", "Selic", "Variável", "Poupança", "Outro"]

LIQUIDEZ = ["Diária", "D+1", "D+30", "No vencimento", "Sem liquidez"]


def cadastro(apenas_ativos: bool = False) -> pd.DataFrame:
    """Le a lista de investimentos cadastrados."""
    sql = "SELECT * FROM investimentos"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY ativo DESC, nome"
    return banco.df(sql)


CAMPOS_CADASTRO = ["nome", "ticker", "tipo", "instituicao", "indexador",
                   "taxa_contratada", "data_inicio", "data_vencimento",
                   "liquidez", "objetivo", "ativo", "observacao", "classe",
                   "moeda", "tema"]


def salvar(investimento: dict) -> int:
    """Grava um investimento (novo, ou atualiza se vier com id).

    NA ATUALIZACAO, SO MEXE NOS CAMPOS QUE VOCE MANDOU.

    Isso importa desde que a importacao da posicao passou a preencher a
    `classe` sozinha: se o UPDATE reescrevesse a linha inteira, salvar o
    formulario de cadastro — que nao tem campo de classe — apagaria a
    classificacao, e o rebalanceamento perderia o papel de vista sem ninguem
    entender por que.
    """
    campos = [c for c in CAMPOS_CADASTRO if c in investimento]
    valores = [investimento.get(campo) for campo in campos]
    if not campos:
        raise ValueError("Nenhum campo para gravar no investimento.")

    if investimento.get("id"):
        atribuicoes = ", ".join(f"{campo} = ?" for campo in campos)
        banco.executar(
            f"UPDATE investimentos SET {atribuicoes} WHERE id = ?",
            (*valores, int(investimento["id"])),
        )
        return int(investimento["id"])

    marcadores = ",".join("?" * len(campos))
    return banco.executar(
        f"INSERT INTO investimentos ({','.join(campos)}) VALUES ({marcadores})",
        valores,
    )


def apagar(investimento_id: int) -> None:
    """Apaga um investimento e todos os saldos dele.

    Os saldos vao junto de proposito: sem o investimento, eles nao querem
    dizer nada. Apagar so o cadastro deixaria linhas orfas na outra tabela.
    """
    banco.executar("DELETE FROM investimentos_saldos WHERE investimento_id = ?",
                   (investimento_id,))
    banco.executar("DELETE FROM investimentos WHERE id = ?", (investimento_id,))


def saldos(investimento_id: int | None = None) -> pd.DataFrame:
    """Le os saldos mensais, de um investimento ou de todos."""
    if investimento_id is None:
        return banco.df(
            """SELECT s.*, i.nome, i.tipo, i.instituicao
               FROM investimentos_saldos s
               JOIN investimentos i ON i.id = s.investimento_id
               ORDER BY s.mes, i.nome"""
        )
    return banco.df(
        "SELECT * FROM investimentos_saldos WHERE investimento_id = ? ORDER BY mes",
        (investimento_id,),
    )


def moeda_do_investimento(investimento_id: int) -> str:
    """A moeda em que aquele papel e cotado. 'BRL' quando nao ha nada gravado."""
    linha = banco.consultar_um(
        "SELECT moeda FROM investimentos WHERE id = ?", (investimento_id,))
    return ((linha["moeda"] if linha else None) or cambio.MOEDA_PADRAO).upper()


def salvar_saldo(investimento_id: int, mes: str, saldo: float,
                 aporte: float = 0.0, resgate: float = 0.0,
                 observacao: str | None = None) -> None:
    """Grava (ou corrige) o saldo de um investimento num mes.

    O "ON CONFLICT ... DO UPDATE" e um upsert: se ja existe linha para aquele
    investimento naquele mes, atualiza em vez de dar erro de chave duplicada.

    AQUI, E SO AQUI, A MOEDA E CONVERTIDA
    -------------------------------------
    Se o papel e cotado em dolar, os valores chegam em dolar e sao gravados
    **em reais**, pela cotacao do FIM DAQUELE MES. O valor original fica em
    `saldo_moeda` e a taxa empregada em `cambio_usado`.

    Concentrar a conversao neste ponto e a decisao central da Fase 1. A
    alternativa seria converter em cada calculo — e sao seis (`posicao`,
    `evolucao_carteira`, `alocacao_atual`, `conciliar`, `patrimonio.evolucao` e
    o rebalanceamento). Seis lugares para lembrar e seis chances de esquecer;
    e o dia em que alguem esquecesse, o app somaria dolar com real **sem
    quebrar**, mostrando um patrimonio errado que parece certo.

    Convertendo na entrada, o resto do app continua sendo um app de reais.

    POR QUE A COTACAO DO FIM DO MES, E NAO A DE HOJE: o saldo e a foto do fim
    do mes. Usar a cotacao de hoje faria o saldo de marco mudar toda vez que o
    dolar mexesse — e reimportar o mesmo arquivo daria um numero diferente a
    cada dia. Guardar `cambio_usado` fecha o circulo: da para reproduzir depois
    o numero que estava na tela.
    """
    moeda = moeda_do_investimento(investimento_id)
    saldo, aporte, resgate = float(saldo), float(aporte), float(resgate)

    if moeda == cambio.MOEDA_PADRAO:
        saldo_brl, aporte_brl, resgate_brl = saldo, aporte, resgate
        saldo_moeda = taxa = None
    else:
        taxa, _data = cambio.cotacao_do_mes(mes)
        if taxa is None:
            raise ValueError(
                f"Nao consegui a cotacao de {moeda} para {mes}. O saldo NAO foi "
                f"gravado — gravar sem converter somaria {moeda} com reais. "
                f"Rode a atualizacao de cotacoes e tente de novo."
            )
        saldo_moeda = saldo
        saldo_brl = saldo * taxa
        aporte_brl = aporte * taxa
        resgate_brl = resgate * taxa

    banco.executar(
        """INSERT INTO investimentos_saldos
           (investimento_id, mes, saldo, aporte, resgate, observacao,
            saldo_moeda, cambio_usado)
           VALUES (?,?,?,?,?,?,?,?)
           ON CONFLICT(investimento_id, mes) DO UPDATE SET
             saldo = excluded.saldo, aporte = excluded.aporte,
             resgate = excluded.resgate, observacao = excluded.observacao,
             saldo_moeda = excluded.saldo_moeda,
             cambio_usado = excluded.cambio_usado""",
        (investimento_id, mes, saldo_brl, aporte_brl, resgate_brl,
         observacao, saldo_moeda, taxa),
    )


def atualizar_saldos_por_cotacao(mes: str) -> dict:
    """Recalcula o saldo do mes para os papeis que tem ticker E quantidade.

    E o que transforma a busca de cotacao em numero na tela: sem isto, atualizar
    os precos guardaria dados que ninguem olha.

        saldo = quantidade x cotacao de fechamento do fim do mes

    QUEM ENTRA, E POR QUE OS OUTROS FICAM DE FORA
    ---------------------------------------------
    Exige as DUAS coisas:

      - **ticker**, senao nao ha preco para buscar (Tesouro e fundo nao tem);
      - **quantidade**, senao nao ha o que multiplicar.

    A quantidade vem do ultimo mes em que foi registrada. Se um papel nunca
    teve quantidade gravada, ele fica de fora — e fica de fora **em silencio de
    proposito**: chutar uma quantidade seria pior que nao atualizar.

    O QUE ELA NAO TOCA
    ------------------
    `aporte` e `resgate` do mes sao LIDOS e regravados como estavam. Eles
    contam quanto dinheiro entrou e saiu daquele papel, e isso nao se deduz de
    preco nenhum — sobrescrever com zero apagaria a informacao que separa
    rendimento de dinheiro novo.

    Devolve {atualizados, ignorados, detalhes, mes}.
    """
    from financas import cambio, cotacoes

    if mes_para_indice(mes) is None:
        raise ValueError(f"Mes invalido: {mes!r}. Esperado 'AAAA-MM'.")
    fim_deste_mes = cambio.ultimo_dia_do_mes(mes)
    if fim_deste_mes and fim_deste_mes > date.today() and mes > date.today().strftime("%Y-%m"):
        raise ValueError(
            f"Nao da para atualizar o saldo de {mes}: e um mes futuro.")

    atualizados, ignorados, detalhes = 0, [], []

    for papel in banco.consultar(
            """SELECT id, nome, ticker, moeda FROM investimentos
               WHERE ativo = 1 AND ticker IS NOT NULL AND TRIM(ticker) <> ''"""):
        linha_qtd = banco.consultar_um(
            """SELECT quantidade FROM investimentos_saldos
               WHERE investimento_id = ? AND mes <= ? AND quantidade IS NOT NULL
                 AND quantidade > 0
               ORDER BY mes DESC LIMIT 1""",
            (papel["id"], mes))
        if not linha_qtd:
            ignorados.append(f"{papel['nome']} (sem quantidade registrada)")
            continue

        preco, dia = cotacoes.preco_do_mes(papel["ticker"], mes)
        if preco is None:
            ignorados.append(f"{papel['nome']} (sem cotação)")
            continue

        quantidade = float(linha_qtd["quantidade"])
        anterior = banco.consultar_um(
            """SELECT aporte, resgate, saldo, cambio_usado FROM investimentos_saldos
               WHERE investimento_id = ? AND mes = ?""", (papel["id"], mes))
        aporte = float(anterior["aporte"] or 0) if anterior else 0.0
        resgate = float(anterior["resgate"] or 0) if anterior else 0.0
        taxa_anterior = float(anterior["cambio_usado"]) if (
            anterior and anterior["cambio_usado"]) else None
        if taxa_anterior:
            aporte /= taxa_anterior
            resgate /= taxa_anterior

        salvar_saldo(papel["id"], mes, quantidade * preco, aporte, resgate,
                     observacao=f"Cotação de {dia} × {quantidade:g} unid.")
        banco.executar(
            "UPDATE investimentos_saldos SET quantidade = ? "
            "WHERE investimento_id = ? AND mes = ?",
            (quantidade, papel["id"], mes))
        atualizados += 1
        detalhes.append({
            "nome": papel["nome"], "ticker": papel["ticker"],
            "quantidade": quantidade, "preco": preco, "data_preco": dia,
            "moeda": papel["moeda"] or "BRL",
        })

    return {"atualizados": atualizados, "ignorados": ignorados,
            "detalhes": detalhes, "mes": mes}


def apagar_saldo(investimento_id: int, mes: str) -> None:
    """Remove o registro de um mes."""
    banco.executar(
        "DELETE FROM investimentos_saldos WHERE investimento_id = ? AND mes = ?",
        (investimento_id, mes),
    )


_DATA_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def compras(investimento_id: int | None = None) -> pd.DataFrame:
    """As compras lancadas a mao, de um papel ou de todos.

    Colunas: id, investimento_id, nome, data, quantidade, valor_unitario,
             custos, valor_total, moeda, cambio_usado, valor_total_brl,
             fator_ajuste, observacao, criado_em

    POR QUE ESTA TABELA EXISTE
    --------------------------
    O saldo mensal diz quanto o papel VALE. Ele nao diz quanto voce PAGOU — e
    sem isso nao ha preco medio, nao ha "valorizou quanto sobre o custo", e a
    ficha de Bens e Direitos do IR fica sem o unico numero que ela pede.

    A corretora tem uma coluna "Valor aplicado", e ela nao serve: muda sozinha,
    sem voce ter movimentado nada (ver `docs/11`). Compra lancada por voce e a
    unica fonte que nao mente.
    """
    sql = """SELECT c.*, i.nome
               FROM investimentos_compras c
               JOIN investimentos i ON i.id = c.investimento_id"""
    if investimento_id is None:
        return banco.df(sql + " ORDER BY c.data, c.id")
    return banco.df(sql + " WHERE c.investimento_id = ? ORDER BY c.data, c.id",
                    (investimento_id,))


def salvar_compra(investimento_id: int, data_compra: str,
                  quantidade: float | None, valor_unitario: float | None,
                  custos: float = 0.0, valor_total: float | None = None,
                  fator_ajuste: float = 1.0,
                  observacao: str | None = None) -> int:
    """Registra uma compra e devolve o id dela.

    AQUI TAMBEM A MOEDA E CONVERTIDA, E PELO MESMO MOTIVO
    ----------------------------------------------------
    Vale a regra de `salvar_saldo`: converte na ENTRADA, uma vez, e o resto do
    app continua sendo um app de reais. A diferenca e a data usada — aqui e o
    **dia da ordem**, nao o fim do mes, porque foi nesse dia que o dinheiro
    saiu. `cambio_usado` fica gravado para o numero ser reproduzivel depois.

    `valor_total` pode vir pronto (fundo, que nao tem cota unitaria) ou ser
    calculado de `quantidade x valor_unitario + custos`. Papel sem quantidade
    exige `valor_total`; sem um dos dois caminhos a funcao levanta, em vez de
    gravar um zero que depois viraria "custou nada".

    `fator_ajuste` guarda grupamento e desdobramento. Ele nasce 1,0 e so muda
    se voce disser — o app nao tem como saber de um evento societario. O IRE
    fez 1:4 em 20/03/2026: uma compra anterior a essa data precisa de 0,25 para
    a quantidade comparar com a de hoje.
    """
    if vazio(data_compra) or not _DATA_ISO.fullmatch(str(data_compra)):
        raise ValueError(
            f"Data invalida: {data_compra!r}. Esperado 'AAAA-MM-DD'. "
            f"Conferir so o tamanho nao basta: '15/08/2025' tambem tem dez "
            f"caracteres, e seria gravado de cabeca para baixo.")

    quantidade = None if vazio(quantidade) else float(quantidade)
    valor_unitario = None if vazio(valor_unitario) else float(valor_unitario)
    custos = 0.0 if vazio(custos) else float(custos)

    if vazio(valor_total):
        if quantidade is None or valor_unitario is None:
            raise ValueError(
                "Informe o valor total, ou a quantidade e o preco unitario. "
                "Sem um dos dois a compra nao tem custo, e custo desconhecido "
                "nao pode virar zero.")
        valor_total = quantidade * valor_unitario + custos
    valor_total = float(valor_total)

    moeda = moeda_do_investimento(investimento_id)
    if moeda == cambio.MOEDA_PADRAO:
        total_brl, taxa = valor_total, None
    else:
        total_brl, taxa, _data = cambio.para_brl(valor_total, data_compra, moeda)
        if total_brl is None:
            raise ValueError(
                f"Nao consegui a cotacao de {moeda} para {data_compra}. A "
                f"compra NAO foi gravada — gravar sem converter somaria "
                f"{moeda} com reais.")

    return banco.executar(
        """INSERT INTO investimentos_compras
           (investimento_id, data, quantidade, valor_unitario, custos,
            valor_total, moeda, cambio_usado, valor_total_brl, fator_ajuste,
            observacao, criado_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
        (investimento_id, data_compra, quantidade, valor_unitario, custos,
         valor_total, moeda, taxa, total_brl,
         1.0 if vazio(fator_ajuste) else float(fator_ajuste), observacao),
    )


def apagar_compra(compra_id: int) -> None:
    """Remove uma compra lancada."""
    banco.executar("DELETE FROM investimentos_compras WHERE id = ?",
                   (compra_id,))


def custo_medio(investimento_id: int, ate: str | None = None) -> dict | None:
    """O que voce pagou por este papel, somando os lotes. None se nao ha compra.

    Devolve: quantidade, custo_total_brl, custo_total_moeda, preco_medio_brl,
             preco_medio_moeda, moeda, lotes, primeira_compra

    A QUANTIDADE SAI AJUSTADA, O PRECO MEDIO TAMBEM
    -----------------------------------------------
    Cada lote entra como `quantidade x fator_ajuste`. Depois de um grupamento
    1:4, um lote de 145 cotas conta como 36,25 — que e o numero comparavel com
    a posicao de hoje e com a cotacao, que ja vem ajustada por split.

    Sem isso o preco medio ficaria 4x menor que o preco atual e a tela diria
    que o papel quadruplicou.

    `None`, e nao um dicionario zerado, quando nao ha compra lancada: zero se
    leria como "custou nada", e a verdade e "nao sei". E a mesma regra do
    `custo` na tela de Imposto.
    """
    tabela = compras(investimento_id)
    if tabela.empty:
        return None
    if ate:
        tabela = tabela[tabela["data"].astype(str) <= str(ate)]
        if tabela.empty:
            return None
    return _custo_medio_de(tabela)


def _custo_medio_de(tabela: pd.DataFrame) -> dict | None:
    """A conta do custo medio, separada da leitura do banco.

    Existe para `desempenho_da_carteira` poder buscar TODAS as compras de uma
    vez e chamar isto por papel, em vez de uma consulta por linha da tabela.
    A conta mora num lugar so; o que muda e de onde vem a tabela.
    """
    if tabela.empty:
        return None

    fator = tabela["fator_ajuste"].fillna(1.0).astype(float)
    quantidades = tabela["quantidade"].astype(float) * fator
    quantidade = float(quantidades.sum()) if quantidades.notna().all() else None

    total_brl = float(tabela["valor_total_brl"].sum())
    total_moeda = float(tabela["valor_total"].sum())
    moeda = str(tabela["moeda"].iloc[-1])

    return {
        "quantidade": quantidade,
        "custo_total_brl": total_brl,
        "custo_total_moeda": total_moeda,
        "preco_medio_brl": (total_brl / quantidade
                            if quantidade and quantidade > 0 else None),
        "preco_medio_moeda": (total_moeda / quantidade
                              if quantidade and quantidade > 0 else None),
        "moeda": moeda,
        "lotes": int(len(tabela)),
        "primeira_compra": str(tabela["data"].iloc[0]),
    }


ABREV_MES = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]


def meses_de_cupom(nome: str) -> set[int]:
    """Em que meses do ano um titulo publico paga juros semestrais.

    A NTN-B paga cupom no MES DO VENCIMENTO e seis meses antes. O vencimento
    ja esta no nome que a corretora usa, e o app so precisa ler:

        "NTN-B mai/2035"        -> {5, 11}    maio e novembro
        "NTN-B ago/2060"        -> {8, 2}     agosto e fevereiro
        "NTNB PRINC ago/2032"   -> set()      PRINCIPAL nao paga cupom
        "LFT mar/2031"          -> set()      Tesouro Selic nao paga cupom

    O "PRINC" nao e detalhe de nomenclatura: e a diferenca entre o Tesouro
    IPCA+ e o Tesouro IPCA+ com Juros Semestrais. O primeiro paga tudo no
    vencimento. Tratar os dois igual inventaria um cupom que nunca caiu.

    Devolve conjunto vazio para qualquer papel que nao seja NTN-B com cupom —
    e vazio quer dizer "nao procure cupom para este", nao "nao achei".
    """
    texto = normalizar_texto(nome or "")
    if "NTN" not in texto.replace("-", ""):
        return set()
    if "PRINC" in texto:
        return set()
    for indice, abrev in enumerate(ABREV_MES, start=1):
        if f"{abrev.upper()}/" in texto:
            return {indice, (indice + 6 - 1) % 12 + 1}
    return set()


def cupons_por_papel() -> dict[tuple[int, str], float]:
    """Quanto de juros semestrais cada titulo recebeu em cada mes.

    POR QUE ISSO PRECISA SER DEDUZIDO
    ---------------------------------
    O extrato da corretora registra o cupom, mas **nao diz de qual titulo**:

        REPASSE DE JUROS TESOURO DIRETO 17/08/2026        706,67
        REPASSE DE JUROS TESOURO DIRETO 17/08/2026        362,88
        REPASSE DE JUROS TESOURO DIRETO 17/08/2026        870,38

    Sao tres linhas porque sao tres LOTES de compra do mesmo titulo, nao tres
    titulos. Sem atribuir, o cupom nao vira resgate de papel nenhum — e, como
    o titulo VALE MENOS depois de pagar, o cupom aparece como prejuizo do
    tamanho exato dele mesmo. Era o caso das tres NTN-B dele.

    COMO A ATRIBUICAO E FEITA, E POR QUE ELA FECHA
    ----------------------------------------------
    Duas regras, as duas vindas de como a NTN-B funciona:

    1. **O mes do cupom sai do vencimento** (ver `meses_de_cupom`). Em
       fevereiro e agosto so a ago/2060 paga; em maio, as mai/2035 e mai/2045.

    2. **Toda NTN-B paga o MESMO cupom por unidade**, porque todas usam o
       mesmo VNA (o valor nominal atualizado pelo IPCA). Entao o rateio entre
       titulos que pagam no mesmo mes e proporcional a QUANTIDADE.

    A regra 2 foi verificada nos dados dele em 2026-08-24, e e o que da
    confianca no rateio:

        18/02/2026   R$ ···· /  7,84 un = R$ ···· por unidade
        15/05/2026   R$ ···· / 10,62 un = R$ ···· por unidade
        17/08/2026   R$ ···· / 14,22 un = R$ ···· por unidade

    Tres datas, dois titulos diferentes, mesmo valor por unidade — e a
    diferenca entre fevereiro e agosto e o proprio IPCA acumulado no periodo.

    O valor atribuido e o cupom BRUTO, de proposito. E o bruto que sai do
    titulo (o preco cai por ele). O IRRF que a corretora retem e imposto dele,
    um custo da carteira — nao desempenho do papel.

    Devolve {(investimento_id, mes): valor}.
    """
    juros: dict[str, float] = {}
    for linha in banco.consultar(
            """SELECT mes_competencia mes, SUM(valor) total
               FROM investimentos_movimentos
               WHERE tipo_movimento = 'juros' AND valor > 0
               GROUP BY mes_competencia"""):
        if linha["mes"]:
            juros[linha["mes"]] = float(linha["total"] or 0)
    if not juros:
        return {}

    pagadores = [(int(l["id"]), l["nome"], meses_de_cupom(l["nome"]))
                 for l in banco.consultar("SELECT id, nome FROM investimentos")]
    pagadores = [p for p in pagadores if p[2]]
    if not pagadores:
        return {}

    atribuido: dict[tuple[int, str], float] = {}
    for mes, total in juros.items():
        numero_do_mes = int(mes[5:7])
        elegiveis = []
        for papel_id, _nome, meses in pagadores:
            if numero_do_mes not in meses:
                continue
            linha = banco.consultar_um(
                """SELECT quantidade FROM investimentos_saldos
                   WHERE investimento_id = ? AND mes <= ? AND quantidade > 0
                   ORDER BY mes DESC LIMIT 1""", (papel_id, mes))
            if linha and linha["quantidade"]:
                elegiveis.append((papel_id, float(linha["quantidade"])))

        soma = sum(q for _, q in elegiveis)
        if not soma:
            continue
        for papel_id, quantidade in elegiveis:
            atribuido[(papel_id, mes)] = total * quantidade / soma
    return atribuido


def evolucao(investimento_id: int, cupons: dict | None = None,
             periodo_extrato: tuple | None = None) -> pd.DataFrame:
    """A historia de um investimento, mes a mes, com o rendimento calculado.

    Colunas: mes, saldo, aporte, resgate, rendimento, rendimento_pct,
             saldo_anterior

    `rendimento_pct` e o rendimento sobre a base que ficou aplicada durante o
    mes — o saldo anterior mais o aporte. Sem somar o aporte, um mes em que
    voce dobrou a aplicacao mostraria um percentual sem sentido.

    OS DOIS PARAMETROS OPCIONAIS SAO SO PERFORMANCE, E VALEM MUITO
    --------------------------------------------------------------
    `cupons` e `periodo_extrato` sao iguais para TODOS os papeis — sao
    propriedades da carteira, nao do papel. Mas esta funcao os calculava por
    conta propria a cada chamada, e quem chama itera sobre os papeis.

    Medido em 2026-08-25, com 18 papeis cadastrados, so no topo da tela de
    Investimentos:

        evolucao() rodava        144 vezes
        cupons_por_papel() idem  144 vezes
        consultas ao SQLite    1.045
        tempo                  2.871 ms   — a cada clique

    (`conciliar()` no Dashboard pagava 1.531 ms do mesmo jeito.)

    Passando os dois de fora, quem itera calcula UMA vez e reaproveita. Ficam
    opcionais de proposito: chamar `evolucao(id)` sozinha continua correto e
    devolve exatamente o mesmo, so que pagando o preco inteiro. Um parametro
    de performance nunca deve virar uma armadilha de correcao.
    """
    colunas = ["mes", "saldo", "aporte", "resgate", "rendimento",
               "rendimento_pct", "saldo_anterior", "confiavel"]

    linhas_saldo = saldos(investimento_id)
    if linhas_saldo.empty:
        return pd.DataFrame(columns=colunas)

    inicio_extrato, fim_extrato = (
        periodo_extrato if periodo_extrato is not None
        else periodo_do_extrato_da_corretora())
    if cupons is None:
        cupons = cupons_por_papel()

    linhas_saldo = linhas_saldo.sort_values("mes")
    resultado = []
    saldo_anterior = 0.0
    primeiro = True

    for _, linha in linhas_saldo.iterrows():
        saldo = float(linha["saldo"] or 0)
        aporte = float(linha["aporte"] or 0)
        resgate = float(linha["resgate"] or 0)
        mes = linha["mes"]

        if primeiro and saldo_anterior == 0 and aporte == 0 and saldo > 0:
            aporte = saldo

        cupom = cupons.get((int(investimento_id), mes), 0.0)
        if cupom:
            resgate += cupom

        rendimento = saldo - saldo_anterior - aporte + resgate

        tem_quantidade = linha.get("quantidade") is not None and not vazio(
            linha.get("quantidade"))
        no_extrato = bool(inicio_extrato and inicio_extrato <= mes <= fim_extrato)
        confiavel = primeiro or tem_quantidade or no_extrato

        base = saldo_anterior + aporte
        resultado.append({
            "mes": mes,
            "saldo": saldo,
            "aporte": aporte,
            "resgate": resgate,
            "rendimento": rendimento,
            "rendimento_pct": rendimento / base if base > 0 else 0.0,
            "saldo_anterior": saldo_anterior,
            "confiavel": confiavel,
        })
        saldo_anterior = saldo
        primeiro = False

    return pd.DataFrame(resultado, columns=colunas)


def total_por_mes() -> dict[str, float]:
    """Quanto a carteira INTEIRA valia no fim de cada mes, em reais.

    Soma `investimentos_saldos` — que ja inclui tudo que e acompanhado: a
    posicao da XP, o dinheiro parado na corretora e a carteira internacional
    (esta ja convertida para reais na gravacao, ver `salvar_saldo`).

    POR QUE ESTA FUNCAO EXISTE (2026-08-23). A tela de Patrimonio lia
    `patrimonio_mensal.saldo_aplicado_manual`, que a importacao da posicao
    preenchia com o total do ARQUIVO DA XP. Enquanto a XP era a carteira
    inteira, dava no mesmo. No dia em que a conta internacional entrou, as duas
    telas passaram a discordar na mesma sessao:

        Investimentos -> R$ ····    (posicao(), soma tudo)
        Patrimonio    -> R$ ····    (so o arquivo da XP)

    Dois numeros para a mesma coisa e um defeito, mesmo quando os dois estao
    "certos" pela sua propria definicao. Agora ha uma fonte so, e as duas telas
    bebem dela.

    A licao geral: quando um numero e derivado de uma FONTE (o arquivo da
    corretora), ele envelhece no dia em que aparece uma segunda fonte. Derivar
    do ESTADO (a tabela de saldos) nao tem esse problema.
    """
    return {
        linha["mes"]: float(linha["total"] or 0)
        for linha in banco.consultar(
            "SELECT mes, SUM(saldo) AS total FROM investimentos_saldos GROUP BY mes")
    }


def periodo_do_extrato_da_corretora() -> tuple[str | None, str | None]:
    """(primeiro mes, ultimo mes) cobertos pelo extrato da corretora, ou (None, None).

    Serve para saber ONDE aquela fonte pode ser usada. Um mes sem nenhuma linha
    de aporte/resgate pode ser um mes sem movimento (dado bom) ou um mes que o
    arquivo nem alcanca (ausencia de dado) — e as duas coisas nao podem ser
    confundidas.
    """
    linha = banco.consultar_um(
        "SELECT MIN(mes_competencia) AS a, MAX(mes_competencia) AS b "
        "FROM investimentos_movimentos")
    if not linha or not linha["a"]:
        return (None, None)
    return (linha["a"], linha["b"])


def fluxo_externo_mensal() -> dict[str, float]:
    """Quanto entrou (+) ou saiu (−) da corretora em cada mes, da MELHOR fonte.

    DUAS FONTES PARA O MESMO FATO, E UMA REGRA PARA ESCOLHER
    --------------------------------------------------------
    O dinheiro que atravessa a fronteira entre a conta corrente e a corretora
    aparece dos dois lados:

        EXTRATO DA CORRETORA  `investimentos_movimentos`, tipo aporte/resgate.
                              E a fonte melhor: e a propria corretora dizendo
                              o que recebeu. So existe de 2026-01 em diante.

        CONTA CORRENTE        lancamentos das categorias `Investimentos` e
                              `Desinvestimentos`. Cobre desde 2024-04, mas
                              depende de a classificacao estar certa.

    A regra: **onde o extrato da corretora alcanca, ele manda; fora dali, vale
    a conta corrente.**

    POR QUE ISTO PRECISOU EXISTIR (2026-08-23). Ate aqui so o extrato da
    corretora era usado. Quando os arquivos de posicao de 2024-2025 entraram,
    todo mes anterior a 2026 ficou com fluxo ZERO — e a variacao inteira do
    saldo virou "rendimento". Junho/2024 apareceu com **−R$ ····** de
    rendimento (era um CDB vencendo) e julho com **+R$ ····** (era um aporte).

    A CONFERENCIA QUE DEU CONFIANCA NESTA REGRA
    -------------------------------------------
    Nos 8 meses de 2026 as duas fontes existem, e batem **ao centavo** em 7:

        2026-01 a 2026-07   diferenca 0,00 em todos
        2026-08             diferenca R$ ····

    E a diferenca de agosto nao e ruido: sao as duas TED de R$ ···· que
    sairam da corretora e entraram na conta como TED recebida em nome do
    proprio titular,
    classificadas `Transferencia` em vez de `Desinvestimentos`. O extrato da
    corretora registra as duas como `resgate` e acerta.

    Ou seja: onde da para comparar, a fonte preferida ganha exatamente nos
    casos em que a outra erra. E o melhor argumento possivel para a ordem
    escolhida.
    """
    inicio, fim = periodo_do_extrato_da_corretora()

    fluxo = {
        linha["mes"]: -float(linha["v"] or 0)
        for linha in banco.consultar(
            """SELECT mes_competencia AS mes, SUM(valor) AS v
               FROM lancamentos
               WHERE categoria IN ('Investimentos', 'Desinvestimentos')
               GROUP BY mes_competencia""")
    }

    if inicio:
        for mes in list(fluxo):
            if inicio <= mes <= fim:
                fluxo[mes] = 0.0
        for linha in banco.consultar(
                """SELECT mes_competencia AS mes, SUM(valor) AS v
                   FROM investimentos_movimentos
                   WHERE tipo_movimento IN ('aporte', 'resgate')
                   GROUP BY mes_competencia"""):
            fluxo[linha["mes"]] = float(linha["v"] or 0)

    return fluxo


def evolucao_carteira() -> pd.DataFrame:
    """Soma todos os investimentos, mes a mes.

    Devolve [mes, saldo, aporte, resgate, rendimento, rendimento_pct].

    DE ONDE VEM O APORTE, E POR QUE NAO E A SOMA DOS APORTES DE CADA PAPEL
    ----------------------------------------------------------------------
    Somar o aporte papel a papel exigiria saber quanto voce colocou em CADA
    titulo, e esse dado nao existe: a coluna "Total aplicado" do bloco do
    Tesouro nao e custo de aquisicao — ela vem zerada no arquivo historico e
    igual a posicao no arquivo atual (ver `leitores/posicao_xp.py`).

    Tentar usa-la produziu numeros absurdos: agosto/2026 apareceu com aporte de
    R$ ···· e rendimento de -R$ ····.

    O que a carteira INTEIRA cresce ou encolhe tem uma fonte confiavel e
    independente: o FLUXO EXTERNO entre a conta corrente e a corretora, que
    esta em `investimentos_movimentos` com tipo "aporte" e "resgate".

        variacao da carteira  =  fluxo externo  +  rendimento

    Compra e venda DENTRO da corretora nao entram: comprar um titulo converte
    dinheiro parado em titulo, e o tamanho da carteira nao muda.

    Essa conta foi conferida mes a mes contra os arquivos de posicao e fecha
    nos 8 meses de 2026 (ver o CHANGELOG de 2026-08-22).
    """
    colunas = ["mes", "saldo", "aporte", "resgate", "rendimento", "rendimento_pct"]

    lista = cadastro()
    if lista.empty:
        return pd.DataFrame(columns=colunas)

    cupons = cupons_por_papel()
    periodo = periodo_do_extrato_da_corretora()

    partes = []
    for _, investimento in lista.iterrows():
        historico = evolucao(int(investimento["id"]), cupons, periodo)
        if not historico.empty:
            partes.append(historico)

    if not partes:
        return pd.DataFrame(columns=colunas)

    tudo = pd.concat(partes, ignore_index=True)
    agrupado = (
        tudo.groupby("mes")
        .agg(saldo=("saldo", "sum"), saldo_anterior=("saldo_anterior", "sum"))
        .reset_index()
        .sort_values("mes")
    )

    fluxo = fluxo_externo_mensal()
    meses_com_foto = list(agrupado["mes"])
    anterior = None
    liquido_por_foto = []
    for mes_foto in meses_com_foto:
        soma = sum(v for m, v in fluxo.items()
                   if (anterior is None or m > anterior) and m <= mes_foto)
        liquido_por_foto.append(soma)
        anterior = mes_foto

    agrupado["aporte"] = [max(0.0, v) for v in liquido_por_foto]
    agrupado["resgate"] = [max(0.0, -v) for v in liquido_por_foto]

    variacao = agrupado["saldo"] - agrupado["saldo_anterior"]
    agrupado["rendimento"] = variacao - (agrupado["aporte"] - agrupado["resgate"])
    if len(agrupado):
        primeiro = agrupado.index[0]
        agrupado.loc[primeiro, "rendimento"] = 0.0

    base = agrupado["saldo_anterior"] + agrupado["aporte"]
    agrupado["rendimento_pct"] = (agrupado["rendimento"] / base).where(base > 0, 0.0)
    return agrupado[colunas]


def carteira_contra_indice(nome_indice: str = "CDI") -> pd.DataFrame:
    """A carteira ao lado de uma CARTEIRA-SOMBRA que so rende o indice.

    Colunas: mes, saldo, referencia

    POR QUE SOMBRA, E NAO UMA LINHA DE TAXA
    ---------------------------------------
    O grafico da carteira mostra REAIS; o CDI e uma TAXA. Desenhar uma taxa
    junto de um valor nao compara nada — as duas escalas nao se falam.

    O que responde a pergunta de verdade ("e se eu tivesse deixado tudo no
    fundo DI?") e simular a MESMA carteira com os MESMOS aportes e resgates,
    rendendo o indice em vez do que rendeu:

        sombra_do_mes = (sombra_anterior + aporte − resgate) × (1 + taxa)

    A sombra comeca no mesmo ponto que a carteira real, no primeiro mes
    acompanhado. As duas so se separam a partir do segundo — que e o unico
    jeito de a comparacao ser justa.

    A base `sombra_anterior + aporte` e a mesma convencao que `evolucao` usa
    para `rendimento_pct`: dinheiro que entrou no mes rende o mes inteiro. Usar
    convencoes diferentes para a carteira e para a sombra criaria uma
    diferenca que nao e desempenho, e sim aritmetica.

    Meses sem o indice guardado ficam com `referencia` = NaN, para a linha
    interromper em vez de mentir uma continuidade.
    """
    from financas import indices

    carteira = evolucao_carteira()
    colunas = ["mes", "saldo", "referencia"]
    if carteira.empty:
        return pd.DataFrame(columns=colunas)

    taxas = indices.serie(nome_indice)
    linhas = []
    sombra = None
    for _, mes_linha in carteira.iterrows():
        mes = mes_linha["mes"]
        if sombra is None:
            sombra = float(mes_linha["saldo"])
        else:
            taxa = taxas.get(mes)
            base = sombra + float(mes_linha["aporte"]) - float(mes_linha["resgate"])
            sombra = base * (1 + taxa) if taxa is not None else float("nan")
        linhas.append({"mes": mes, "saldo": float(mes_linha["saldo"]),
                       "referencia": sombra})
    return pd.DataFrame(linhas, columns=colunas)


def posicao(mes: str | None = None) -> pd.DataFrame:
    """A foto da carteira num mes: cada investimento com o saldo mais recente.

    Se um investimento nao tem saldo naquele mes, usamos o ultimo saldo
    conhecido ANTES dele — e a coluna `mes_do_saldo` avisa de quando ele e.
    Isso e melhor que mostrar zero: um CDB que voce nao atualizou nao virou
    pó, so nao foi anotado.

    A lista vem COMPLETA, com os papeis ja zerados. Quem soma a carteira
    precisa deles (somam zero, nao atrapalham) e o historico do que ja se
    operou tem valor. Quem so quer o que esta aplicado filtra `saldo > 0` —
    e a tela de Investimentos faz exatamente isso.

    Colunas: id, nome, tipo, instituicao, indexador, saldo, mes_do_saldo,
             desatualizado, rendimento_mes, rendimento_total,
             rendimento_confiavel, meses_sem_fonte, aportado_total,
             participacao
    """
    colunas = ["id", "nome", "tipo", "instituicao", "indexador", "objetivo",
               "saldo", "mes_do_saldo", "desatualizado", "rendimento_mes",
               "rendimento_total", "rendimento_confiavel", "meses_sem_fonte",
               "aportado_total", "participacao"]

    lista = cadastro()
    if lista.empty:
        return pd.DataFrame(columns=colunas)

    cupons = cupons_por_papel()
    periodo = periodo_do_extrato_da_corretora()

    resultado = []
    for _, investimento in lista.iterrows():
        historico = evolucao(int(investimento["id"]), cupons, periodo)
        if historico.empty:
            resultado.append({
                "id": int(investimento["id"]), "nome": investimento["nome"],
                "tipo": investimento["tipo"], "instituicao": investimento.get("instituicao"),
                "indexador": investimento.get("indexador"),
                "objetivo": investimento.get("objetivo"),
                "saldo": 0.0, "mes_do_saldo": None, "desatualizado": True,
                "rendimento_mes": 0.0, "rendimento_total": 0.0,
                "rendimento_confiavel": None, "meses_sem_fonte": 0,
                "aportado_total": 0.0, "participacao": 0.0,
            })
            continue

        ate_o_mes = historico[historico["mes"] <= mes] if mes else historico
        if ate_o_mes.empty:
            ate_o_mes = historico.head(0)

        if ate_o_mes.empty:
            saldo, mes_saldo, rendimento_mes = 0.0, None, 0.0
        else:
            ultima = ate_o_mes.iloc[-1]
            saldo = float(ultima["saldo"])
            mes_saldo = ultima["mes"]
            rendimento_mes = float(ultima["rendimento"])

        resultado.append({
            "id": int(investimento["id"]),
            "nome": investimento["nome"],
            "tipo": investimento["tipo"],
            "instituicao": investimento.get("instituicao"),
            "indexador": investimento.get("indexador"),
            "objetivo": investimento.get("objetivo"),
            "saldo": saldo,
            "mes_do_saldo": mes_saldo,
            "desatualizado": bool(mes and mes_saldo and mes_saldo < mes
                                  and saldo > 0),
            "rendimento_mes": rendimento_mes,
            "rendimento_total": float(ate_o_mes["rendimento"].sum()),
            "rendimento_confiavel": (
                float(ate_o_mes.iloc[1:][ate_o_mes.iloc[1:]["confiavel"]]["rendimento"].sum())
                if len(ate_o_mes) > 1 and bool(ate_o_mes.iloc[1:]["confiavel"].any())
                else None),
            "meses_sem_fonte": int((~ate_o_mes["confiavel"]).sum())
                               if not ate_o_mes.empty else 0,
            "aportado_total": float(ate_o_mes["aporte"].sum()),
            "participacao": 0.0,
        })

    tabela = pd.DataFrame(resultado, columns=colunas)
    total = tabela["saldo"].sum()
    if total:
        tabela["participacao"] = tabela["saldo"] / total
    return tabela.sort_values("saldo", ascending=False)


def por_tipo(tabela_posicao: pd.DataFrame) -> pd.DataFrame:
    """Agrupa a carteira por tipo de investimento (para o gráfico de pizza)."""
    if tabela_posicao.empty:
        return pd.DataFrame(columns=["tipo", "saldo", "quantidade", "participacao"])

    agrupado = (
        tabela_posicao.groupby("tipo")
        .agg(saldo=("saldo", "sum"), quantidade=("id", "size"))
        .reset_index()
        .sort_values("saldo", ascending=False)
    )
    total = agrupado["saldo"].sum()
    agrupado["participacao"] = agrupado["saldo"] / total if total else 0.0
    return agrupado


def movimentacoes(df_lancamentos: pd.DataFrame) -> pd.DataFrame:
    """Aportes e resgates extraidos dos lancamentos, mes a mes.

    Usa as categorias `Investimentos` (dinheiro indo) e `Desinvestimentos`
    (dinheiro voltando) — as mesmas que as regras 3 e 4 do extrato aplicam
    automaticamente na importacao.

    Devolve [mes, aportado, resgatado, liquido, acumulado].
    """
    colunas = ["mes", "aportado", "resgatado", "liquido", "acumulado"]
    if df_lancamentos.empty:
        return pd.DataFrame(columns=colunas)

    movimento = df_lancamentos[
        df_lancamentos["categoria"].isin(["Investimentos", "Desinvestimentos"])
    ]
    if movimento.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (
        movimento.groupby("mes_competencia")
        .apply(lambda g: pd.Series({
            "aportado": float(-g[g["valor"] < 0]["valor"].sum()),
            "resgatado": float(g[g["valor"] > 0]["valor"].sum()),
        }), include_groups=False)
        .reset_index()
        .rename(columns={"mes_competencia": "mes"})
        .sort_values("mes")
    )
    agrupado["liquido"] = agrupado["aportado"] - agrupado["resgatado"]
    agrupado["acumulado"] = agrupado["liquido"].cumsum()
    return agrupado[colunas]


def fluxo_externo_por_mes() -> pd.DataFrame:
    """O mesmo que `movimentacoes()`, mas da fonte COMBINADA.

    Devolve [mes, aportado, resgatado, liquido, acumulado].

    POR QUE EXISTE, SENDO QUE `movimentacoes()` JA FAZIA ISSO (2026-08-23)

    `movimentacoes()` le so os lancamentos da conta corrente. A tela de
    Investimentos usava as duas fontes ao mesmo tempo sem perceber:

        KPI do topo        R$ ····   (fonte combinada, via conciliar)
        "O que o extrato diz"  R$ ····   (so a conta corrente)

    Trinta mil reais de diferenca, na mesma tela, para a mesma coisa. E o
    defeito que este projeto trata como bug — nao porque um dos numeros esteja
    errado pela sua propria definicao, mas porque **quem le nao tem como saber
    qual dos dois usar.**

    A diferenca eram as duas TED de R$ ···· que sairam da corretora e
    entraram na conta como TED recebida em nome do proprio titular: o
    extrato da corretora
    as registra como resgate, a conta corrente nao.

    `movimentacoes()` continua existindo — ela responde "o que os LANCAMENTOS
    dizem", que e uma pergunta legitima. Ela e que nao servia para este lugar.
    """
    colunas = ["mes", "aportado", "resgatado", "liquido", "acumulado"]
    fluxo = fluxo_externo_mensal()
    if not fluxo:
        return pd.DataFrame(columns=colunas)

    linhas = [
        {"mes": mes,
         "aportado": max(0.0, valor),
         "resgatado": max(0.0, -valor),
         "liquido": valor}
        for mes, valor in sorted(fluxo.items())
    ]
    tabela = pd.DataFrame(linhas, columns=colunas[:-1])
    tabela["acumulado"] = tabela["liquido"].cumsum()
    return tabela[colunas]


def saldo_de_abertura(carteira_no_tempo: pd.DataFrame | None = None) -> float:
    """O que a carteira JA valia no primeiro mes acompanhado.

    `carteira_no_tempo` e so performance: quem ja tem a saida de
    `evolucao_carteira()` na mao passa, em vez de mandar recalcular a carteira
    inteira. `conciliar()` fazia exatamente isso — chamava esta funcao e
    `evolucao_carteira()` logo em seguida, e as duas percorriam todos os
    papeis. Ver a nota de performance em `evolucao`.

    A conta da XP foi aberta em 17/04/2024 com R$ ···· vindos de outro
    banco. Esse dinheiro entrou na carteira sem passar por nenhuma
    transferencia que o app pudesse ver — nao ha lancamento de origem.

    POR QUE ISSO PRECISA DE UMA FUNCAO
    ----------------------------------
    `conciliar()` fazia `carteira - aportado_liquido` e chamava o resto de
    rendimento. Mas o saldo de abertura tambem nao foi aportado, e tambem
    caia nesse "resto" — entao ele aparecia como ganho. Dinheiro trazido de
    outro banco nao e rendimento; e a mesma familia do saldo de abertura de um
    papel virando ganho, so que no nivel da carteira inteira.

    O sintoma era dois numeros discordando na mesma tela: "DIFERENCA
    R$ ····" ao lado de "RENDIMENTO APURADO R$ ····". A distancia
    entre eles era exatamente este valor.

    Devolve 0.0 quando nao ha historico.
    """
    if carteira_no_tempo is None:
        carteira_no_tempo = evolucao_carteira()
    if carteira_no_tempo.empty:
        return 0.0
    primeiro = carteira_no_tempo.iloc[0]
    abertura = (float(primeiro["saldo"])
                - float(primeiro["aporte"])
                + float(primeiro["resgate"]))
    return max(0.0, abertura)


def conciliar(mes: str | None = None) -> dict:
    """Compara a carteira cadastrada com o que os lancamentos dizem.

    NAO RECEBE MAIS O DataFrame DE LANCAMENTOS (2026-08-25). Ela recebia
    `df_lancamentos` como primeiro argumento e **nunca o usava**: sobrou de
    quando a conta somava `movimentacoes(df)`, antes de `fluxo_externo_mensal()`
    passar a ler o banco direto (ver a docstring daquela funcao).

    Um parametro morto e pior que nenhum — quem le acredita que o resultado
    depende do que passou ali, e passa a se preocupar em manter o df em dia
    para uma funcao que nem olha para ele. E o mesmo problema que `dados.py`
    descreve no `meses_disponiveis`.

    Devolve:
        carteira_cadastrada  soma dos saldos que voce anotou
        aportado_liquido     quanto saiu da conta para investimento (líquido)
        saldo_abertura       o que a carteira ja valia no primeiro mes
        diferenca            carteira − aportado_liquido − saldo_abertura
        rendimento_apurado   a soma dos rendimentos calculados por investimento
        n_desatualizados     quantos saldos estao velhos
        situacao             texto curto que resume

    COMO LER A DIFERENCA: se voce mandou R$ ···· para investimento e a sua
    carteira vale R$ ···· a diferenca de R$ ···· e o rendimento acumulado.
    Uma diferenca NEGATIVA quer dizer perda — ou, bem mais provavel, que falta
    cadastrar algum investimento ou atualizar algum saldo.
    """
    tabela = posicao(mes)
    carteira = float(tabela["saldo"].sum()) if not tabela.empty else 0.0

    carteira_no_tempo = evolucao_carteira()

    # OS DOIS LADOS DA CONTA PRECISAM SER DO MESMO MES (2026-09-03).
    # `posicao()` devolve a carteira ate o ultimo saldo CADASTRADO — hoje
    # 2026-08. `fluxo_externo_mensal()` somava tudo o que existe de extrato,
    # que vai ate 2026-09. Resultado: a conta comparava um patrimonio de
    # agosto com transferencias de setembro.
    #
    # O sintoma eram os dois medidores de rendimento discordando em
    # R$ ···· na tela — que e, ao centavo, o fluxo liquido de 2026-09
    # (+269,00 de aporte −R$ ···· de resgate). Nao era erro de calculo em
    # nenhum dos dois: era um mes a mais de um lado da balanca.
    #
    # Alinhados, `diferenca` e `rendimento_apurado` passam a bater exatamente.
    # O MES PEDIDO NAO PODE PASSAR DO ULTIMO SALDO QUE EXISTE. Pedir 2026-09
    # nao faz a carteira ser de setembro: `posicao()` devolve o ultimo saldo
    # conhecido de cada papel, que e de agosto. Somar o fluxo de setembro
    # contra um patrimonio de agosto e o mesmo descompasso, so que pedido de
    # proposito — e e o caminho VIVO, porque o Dashboard passa o mes corrente.
    ultimo_da_carteira = (str(carteira_no_tempo.iloc[-1]["mes"])
                          if not carteira_no_tempo.empty else None)
    mes_referencia = mes
    if ultimo_da_carteira and (not mes_referencia
                               or mes_referencia > ultimo_da_carteira):
        mes_referencia = ultimo_da_carteira

    fluxo = fluxo_externo_mensal()
    aportado_liquido = sum(v for m, v in fluxo.items()
                           if not mes_referencia or m <= mes_referencia)

    abertura = saldo_de_abertura(carteira_no_tempo)

    # O QUE ENTROU DE FORA PELA PROPRIA CORRETORA. `aportado_liquido` conta so
    # o que atravessou a fronteira entre a conta corrente e a corretora. Mas
    # dinheiro pode chegar DIRETO ali — foi o que aconteceu com os R$ ····
    # que entraram de fora em 2026-09. Sem esta parcela, esse dinheiro aparecia
    # dentro de `diferenca`, ou seja, como rendimento de investimento.
    #
    # `nao_explicado` e o que o app ainda NAO SABE o que e: movimento que nao
    # casou com regra nenhuma e que voce ainda nao triou. Ele sai da diferenca
    # e vira linha propria — que e o unico jeito de "sumiu dinheiro" virar uma
    # coisa que da para ver.
    from financas.calculos import fechamento
    componentes = fechamento.por_componente(mes_referencia)
    externo = componentes["entradas"] - componentes["saidas"]
    nao_explicado = componentes["nao_explicado"]

    # DUAS COISAS DIFERENTES, DE PROPOSITO SEPARADAS. `nao_explicado` entra na
    # equacao e por isso respeita o mes de referencia. `a_triar` e a lista de
    # trabalho pendente e NAO respeita: um movimento de setembro que voce ainda
    # nao classificou continua sendo uma pendencia em agosto, so nao entra numa
    # conta de agosto. Somar os dois no mesmo numero esconderia justamente o
    # caso que motivou tudo isto — os R$ ···· de fora, que caem num mes
    # que a carteira ainda nao alcanca.
    a_triar = fechamento.movimentos_a_triar()
    valor_a_triar = float(a_triar["valor"].abs().sum()) if not a_triar.empty else 0.0

    diferenca = carteira - aportado_liquido - abertura - externo - nao_explicado

    if not carteira_no_tempo.empty:
        ate_o_mes = (carteira_no_tempo[carteira_no_tempo["mes"] <= mes]
                     if mes else carteira_no_tempo)
        rendimento_apurado = float(ate_o_mes["rendimento"].sum())
    else:
        rendimento_apurado = 0.0
    n_desatualizados = (
        int(tabela["desatualizado"].sum()) if not tabela.empty else 0)

    if tabela.empty:
        situacao = "carteira vazia"
    elif len(a_triar):
        # Vem ANTES de "saldos desatualizados" porque e mais grave: um saldo
        # velho e um numero atrasado, e dinheiro sem explicacao e um numero
        # que nao se sabe se existe. Usa a lista de pendencias, nao o valor da
        # equacao, para que a pendencia apareca no mes em que ela existe.
        situacao = "há dinheiro sem explicação"
    elif n_desatualizados:
        situacao = "saldos desatualizados"
    elif abs(diferenca) < 1:
        situacao = "confere"
    elif diferenca > 0:
        situacao = "rendendo"
    else:
        situacao = "abaixo do aportado"

    return {
        "carteira_cadastrada": carteira,
        "aportado_liquido": aportado_liquido,
        "entrou_de_fora": externo,
        "nao_explicado": nao_explicado,
        "saldo_abertura": abertura,
        "diferenca": diferenca,
        "rendimento_apurado": rendimento_apurado,
        "n_investimentos": int((tabela["saldo"] > 0).sum()),
        "n_desatualizados": n_desatualizados,
        "n_a_triar": int(len(a_triar)),
        "valor_a_triar": valor_a_triar,
        "mes_referencia": mes_referencia,
        "situacao": situacao,
        "mes": mes,
    }


def sugerir_aportes_do_mes(df_lancamentos: pd.DataFrame, mes: str) -> dict:
    """Quanto os lancamentos dizem que entrou e saiu de investimento no mes.

    Serve para preencher a tela de atualizacao de saldo sem voce ter que
    procurar no extrato: o app ja sabe que em agosto sairam R$ ···· da
    conta para investimento.
    """
    movimento = movimentacoes(df_lancamentos)
    if movimento.empty:
        return {"aportado": 0.0, "resgatado": 0.0}
    do_mes = movimento[movimento["mes"] == mes]
    if do_mes.empty:
        return {"aportado": 0.0, "resgatado": 0.0}
    return {
        "aportado": float(do_mes["aportado"].iloc[0]),
        "resgatado": float(do_mes["resgatado"].iloc[0]),
    }


def rentabilidade_periodo(investimento_id: int, meses: int = 12,
                          historico: pd.DataFrame | None = None) -> dict:
    """Rentabilidade acumulada de um investimento nos ultimos N meses.

    A rentabilidade acumulada NAO e a soma dos percentuais mensais — juros
    compostos nao somam, multiplicam:

        acumulado = (1 + r1) × (1 + r2) × ... − 1

    Devolve {rendimento, rentabilidade, meses_considerados, media_mensal,
    meses_ignorados, meses} — `meses` e a LISTA dos meses que entraram, para
    a referencia (CDI/IPCA) poder somar exatamente os mesmos.

    `historico` e o mesmo tipo de atalho que `evolucao` oferece com `cupons` e
    `periodo_extrato`: quem ja tem a evolucao do papel na mao passa ela aqui e
    evita refaze-la. Medido com os 11 papeis abertos: 394 ms buscando de novo,
    contra pouco mais de 50 ms reaproveitando. Numa tabela que calcula
    rentabilidade em toda linha, essa diferenca e a tela travar ou nao.
    """
    vazio_ = {"rendimento": 0.0, "rentabilidade": 0.0, "meses_considerados": 0,
              "media_mensal": 0.0, "meses_ignorados": 0, "meses": []}

    if historico is None:
        historico = evolucao(investimento_id)
    if historico.empty:
        return vazio_

    recorte = historico.tail(meses)

    if "confiavel" in recorte.columns:
        bons = recorte[recorte["confiavel"].fillna(True).astype(bool)]
    else:
        bons = recorte
    ignorados = int(len(recorte) - len(bons))

    if bons.empty:
        return {**vazio_, "meses_ignorados": ignorados, "meses": []}

    rendimento = float(bons["rendimento"].sum())

    acumulado = 1.0
    for pct in bons["rendimento_pct"]:
        acumulado *= (1 + float(pct))
    rentabilidade = acumulado - 1

    quantidade = int(len(bons))
    media = (acumulado ** (1 / quantidade) - 1) if quantidade else 0.0

    return {
        "rendimento": rendimento,
        "rentabilidade": rentabilidade,
        "meses_considerados": quantidade,
        "media_mensal": media,
        "meses_ignorados": ignorados,
        "meses": [str(m) for m in bons["mes"]],
    }


def sincronizar_custo_no_saldo(investimento_id: int) -> dict:
    """Leva o custo das compras lancadas para os meses fotografados do papel.

    Devolve {gravados, ignorados, preservados}.

    POR QUE ISTO PRECISA EXISTIR
    ----------------------------
    A compra lancada resolve o preco medio da tela de Investimentos, mas a
    ficha **Bens e Direitos** do IR le outra coluna: `investimentos_saldos.
    custo_aplicado`. Sem esta ponte, voce lancaria a compra e a tela de Imposto
    continuaria dizendo "sem custo confiavel" — dois lugares sabendo coisas
    diferentes sobre o mesmo papel, que e o defeito que este projeto persegue.

    O CUSTO E ACUMULADO ATE AQUELE MES, e nao o total de hoje. A ficha de 2025
    pede o que voce tinha pago ate 31/12/2025; escrever o custo de hoje em todo
    mes faria uma compra de 2026 aparecer na declaracao de 2025.

    O QUE ELA SE RECUSA A SOBRESCREVER
    ----------------------------------
    Mes cujo custo veio do **extrato da corretora** (`fonte_custo='extrato'`)
    fica como esta: ali o dinheiro foi visto de verdade, com o papel nomeado.
    Ja o que veio de `valor_aplicado` — a coluna que muda sozinha, descrita em
    `docs/11` — e substituido sem cerimonia.

    E so grava onde JA EXISTE foto: `imposto.salvar_custo` devolve False para
    mes sem linha, porque um UPDATE sem linha casa com zero e nao reclama.
    """
    from financas.calculos import imposto as _imposto

    historico = saldos(investimento_id)
    if historico.empty or compras(investimento_id).empty:
        return {"gravados": 0, "ignorados": 0, "preservados": 0}

    gravados = ignorados = preservados = 0
    for _, linha in historico.iterrows():
        mes = str(linha["mes"])
        if str(linha.get("fonte_custo") or "") == "extrato":
            preservados += 1
            continue
        fim = cambio.ultimo_dia_do_mes(mes)
        ate = fim.isoformat() if fim else f"{mes}-28"
        acumulado = custo_medio(investimento_id, ate=ate)
        if acumulado is None:
            ignorados += 1
            continue
        if _imposto.salvar_custo(investimento_id, mes,
                                 acumulado["custo_total_brl"], "manual"):
            gravados += 1
        else:
            ignorados += 1

    return {"gravados": gravados, "ignorados": ignorados,
            "preservados": preservados}


def desempenho_do_papel(investimento_id: int, meses: int = 12,
                        classe: str | None = None,
                        historico: pd.DataFrame | None = None,
                        macro: str | None = None) -> dict:
    """Rentabilidade de um papel JA COMPARADA com a regua certa dele.

    Devolve: rentabilidade, rendimento, meses_considerados, meses_ignorados,
             meses, media_mensal, indice, rent_indice, vs_indice,
             meses_do_indice, meses_faltando

    POR QUE ISTO VIROU FUNCAO
    -------------------------
    Ate agora a tela montava esta comparacao a mao, em quatro chamadas
    encadeadas (`macro_da_classe` -> `referencia_para` -> `acumulado` ->
    `cobertura`). Cada tela nova que quisesse o mesmo numero teria de repetir
    as quatro na ordem certa — e a segunda copia e onde as duas comecam a
    divergir.

    A REGUA ERRADA E PIOR QUE NENHUMA. `indices.referencia_para` devolve CDI
    para pos-fixado e caixa, IPCA para NTN-B, e **None** para internacional e
    renda variavel. Quando e None, `rent_indice` e `vs_indice` saem None e a
    tela nao escreve comparacao nenhuma — o IRE contra o CDI dava −765%, que e
    aritmetica sem significado.

    E OS DOIS LADOS USAM OS MESMOS MESES. `rentabilidade_periodo` devolve a
    lista dos meses que entraram, e e essa lista que vai para
    `indices.acumulado`. Comparar 8 meses de fundo contra 12 meses de CDI e uma
    mentira que passa despercebida, porque os dois numeros tem a mesma cara.
    """
    from financas import indices

    resultado = rentabilidade_periodo(investimento_id, meses, historico)
    if classe is None:
        linha = banco.consultar_um(
            "SELECT classe FROM investimentos WHERE id = ?", (investimento_id,))
        classe = linha["classe"] if linha else None

    if macro is None:
        macro = macro_da_classe(classe)
    indice = indices.referencia_para(macro, classe)
    rent_indice = vs_indice = None
    faltando: list[str] = []
    cobertos = 0

    if indice and resultado["meses"]:
        rent_indice = indices.acumulado(indice, resultado["meses"])
        cobertos, faltando = indices.cobertura(indice, resultado["meses"])
        if rent_indice is not None:
            vs_indice = resultado["rentabilidade"] - rent_indice

    return {
        **resultado,
        "indice": indice,
        "rent_indice": rent_indice,
        "vs_indice": vs_indice,
        "meses_do_indice": cobertos,
        "meses_faltando": faltando,
    }


def desempenho_da_carteira(mes: str | None = None) -> pd.DataFrame:
    """Uma linha por papel, com tudo que a tela de Investimentos precisa mostrar.

    Colunas: id, nome, tipo, classe, macro, instituicao, indexador, moeda,
             ticker, saldo, participacao, quantidade, saldo_moeda, mes_do_saldo,
             desatualizado, preco_medio, preco_atual, custo_total,
             rendimento_mes, rendimento_confiavel, rent_mes, rent_12m,
             rent_total, meses_medidos, meses_ignorados, indice, rent_indice,
             vs_indice, curva

    UMA PASSADA SO, E ISSO E O DESENHO
    ----------------------------------
    `cupons_por_papel()` e `periodo_do_extrato_da_corretora()` sao calculados
    UMA vez e repassados a cada `evolucao()`; a evolucao de cada papel e
    calculada UMA vez e repassada as duas chamadas de rentabilidade (12 meses e
    total). Sem esses dois cuidados a mesma tabela custa 394 ms por clique.

    O QUE SAI VAZIO, E POR QUE NUNCA SAI ZERO
    -----------------------------------------
    Atencao ao ler: o pandas converte `None` em `NaN` nas colunas numericas.
    Entao **teste com `formato.vazio()`, nunca com `is None`** — `NaN is None`
    e False, e a tela acabaria escrevendo "nan%".

        rent_12m / rent_total     quando o papel nao tem nenhum mes MEDIDO.
                                  O primeiro mes de um papel e aporte por
                                  construcao, nao medicao — um papel com um mes
                                  so nunca foi medido, e zero se leria como
                                  "nao rendeu".
        preco_medio / custo_total quando nao ha compra lancada.
        preco_atual               quando o papel nao tem ticker com cotacao.
        saldo_moeda               quando o papel e em reais — ai `saldo` ja e o
                                  valor na moeda dele, e repetir seria ruido.

    `preco_medio` e `preco_atual` saem os DOIS EM REAIS, e isso precisa ser
    dito: a cotacao de um papel americano chega em dolar, e mostrar um preco
    medio em real ao lado de um preco atual em dolar faria a tela comparar
    grandezas diferentes — o IREN pareceria ter caido 80% so pela troca de
    moeda. A conversao do preco atual usa a cotacao de HOJE, porque e um preco
    de hoje; a do preco medio ficou gravada no dia da compra.
        indice / vs_indice        quando nenhuma regua serve (internacional e
                                  renda variavel).

    `meses_ignorados` acompanha a rentabilidade de proposito: o Trend DI mede 9
    dos seus 29 meses, e uma tela que mostrasse 7,7% sem dizer isso estaria
    escondendo de onde o numero saiu.
    """
    colunas = ["id", "nome", "tipo", "classe", "macro", "instituicao",
               "indexador", "moeda", "ticker", "saldo", "participacao",
               "quantidade", "saldo_moeda", "mes_do_saldo", "desatualizado",
               "preco_medio",
               "preco_atual", "custo_total", "rendimento_mes",
               "rendimento_confiavel", "rent_mes", "rent_12m", "rent_total",
               "meses_medidos", "meses_ignorados", "indice", "rent_indice",
               "vs_indice", "curva"]

    foto = posicao(mes)
    if foto.empty:
        return pd.DataFrame(columns=colunas)

    fichas = cadastro().set_index("id")
    cupons = cupons_por_papel()
    periodo = periodo_do_extrato_da_corretora()
    ultimos = saldos()

    tabela_classes = classes()
    macro_por_classe = dict(zip(tabela_classes["nome"], tabela_classes["macro"]))
    todas_compras = compras()
    precos: dict[str, float | None] = {}

    linhas = []
    for _, papel in foto.iterrows():
        ident = int(papel["id"])
        ficha = fichas.loc[ident] if ident in fichas.index else None

        def _do_cadastro(campo, padrao=None):
            if ficha is None or campo not in ficha.index:
                return padrao
            valor = ficha[campo]
            return padrao if vazio(valor) else valor

        classe = _do_cadastro("classe")
        ticker = _do_cadastro("ticker")
        moeda = _do_cadastro("moeda", "BRL")

        historico = evolucao(ident, cupons=cupons, periodo_extrato=periodo)
        macro = macro_por_classe.get(classe)
        doze = desempenho_do_papel(ident, 12, classe, historico, macro)
        total = rentabilidade_periodo(ident, 999, historico)

        do_papel = ultimos[ultimos["investimento_id"] == ident] if not ultimos.empty else ultimos
        quantidade = saldo_moeda = None
        if not do_papel.empty:
            em_ordem = do_papel.sort_values("mes")
            if "quantidade" in em_ordem.columns:
                ultima = em_ordem["quantidade"].dropna()
                quantidade = float(ultima.iloc[-1]) if len(ultima) else None
            if "saldo_moeda" in em_ordem.columns:
                na_moeda = em_ordem["saldo_moeda"].dropna()
                saldo_moeda = float(na_moeda.iloc[-1]) if len(na_moeda) else None

        custo = None
        if not todas_compras.empty:
            do_papel_compras = todas_compras[
                todas_compras["investimento_id"] == ident]
            if not do_papel_compras.empty:
                custo = _custo_medio_de(do_papel_compras)

        preco_atual = None
        if ticker:
            if ticker not in precos:
                from financas import cotacoes
                preco, _data = cotacoes.preco_em(ticker)
                if preco is not None and moeda != cambio.MOEDA_PADRAO:
                    preco, _taxa, _dia = cambio.para_brl(preco, None, moeda)
                precos[ticker] = preco
            preco_atual = precos[ticker]

        rent_mes = None
        if not historico.empty:
            ultimo_mes = historico.iloc[-1]
            if bool(ultimo_mes.get("confiavel", True)):
                rent_mes = float(ultimo_mes["rendimento_pct"])

        linhas.append({
            "id": ident,
            "nome": papel["nome"],
            "tipo": papel["tipo"],
            "classe": classe,
            "macro": macro,
            "instituicao": papel["instituicao"],
            "indexador": papel["indexador"],
            "moeda": moeda,
            "ticker": ticker,
            "saldo": float(papel["saldo"]),
            "participacao": float(papel["participacao"]),
            "quantidade": quantidade,
            "saldo_moeda": saldo_moeda,
            "mes_do_saldo": papel["mes_do_saldo"],
            "desatualizado": bool(papel["desatualizado"]),
            "preco_medio": custo["preco_medio_brl"] if custo else None,
            "custo_total": custo["custo_total_brl"] if custo else None,
            "preco_atual": preco_atual,
            "rendimento_mes": float(papel["rendimento_mes"]),
            "rendimento_confiavel": papel["rendimento_confiavel"],
            "rent_mes": rent_mes,
            "rent_12m": (doze["rentabilidade"]
                         if doze["meses_considerados"] > 1 else None),
            "rent_total": (total["rentabilidade"]
                           if total["meses_considerados"] > 1 else None),
            "meses_medidos": total["meses_considerados"],
            "meses_ignorados": total["meses_ignorados"],
            "indice": doze["indice"],
            "rent_indice": doze["rent_indice"],
            "vs_indice": doze["vs_indice"],
            "curva": [float(v) for v in historico["saldo"].tail(12)],
        })

    return pd.DataFrame(linhas, columns=colunas)



def exposicao_economica(desempenho: pd.DataFrame | None = None) -> pd.DataFrame:
    """Quanto a carteira realmente aposta em cada papel-alvo, contando alavancagem.

    A PERGUNTA QUE A TABELA DE POSICOES NAO RESPONDE. A tela lista IREN e IRE
    como duas linhas, com dois valores. Mas o IRE e um fundo alavancado 2x
    SOBRE O IREN: quem tem os dois tem uma aposta so, e um pedaco dela dobrado.

        posicao IREN               R$ ····
        posicao IRE                US$   265,35
        exposicao via IRE (x2)     US$   530,70
        ------------------------------------------
        EXPOSICAO REAL A IREN      R$ ····

    Somar as duas linhas pelo valor de tela da R$ ···· e subestima o
    risco. A diferenca parece pequena aqui porque a posicao em IRE e pequena —
    ela deixa de ser pequena depressa, e e justamente quando ninguem esta
    olhando.

    O QUE ESTA FUNCAO NAO FAZ. Ela nao soma exposicao entre papeis diferentes
    que por acaso andam juntos: IREN e DGXX sao os dois do mesmo setor e
    caminham parecido, e isso nao aparece aqui. Isto mede so o que e o MESMO
    papel-alvo, que e um fato, nao uma estimativa de correlacao.

    Devolve uma linha por papel-alvo, com `direta`, `via_alavancado`,
    `exposicao` e `participacao` (sobre a carteira toda). Papel sem ticker fica
    de fora: sem ticker nao ha como saber de que ele e feito.
    """
    from financas import fundamentos

    if desempenho is None:
        desempenho = desempenho_da_carteira()
    if desempenho.empty:
        return pd.DataFrame()

    carteira = float(desempenho["saldo"].sum())
    direta: dict[str, float] = {}
    alavancada: dict[str, float] = {}
    fatores: dict[str, float] = {}

    for _, papel in desempenho.iterrows():
        ticker = None if vazio(papel.get("ticker")) else str(papel["ticker"]).upper()
        saldo = float(papel["saldo"] or 0)
        if not ticker or saldo <= 0:
            continue

        ficha = fundamentos.ficha(ticker)
        alavanca = ficha.get("alavancagem") if ficha.get("tem_dado") else None
        alvo = (alavanca or {}).get("subjacente")

        if alavanca and alvo:
            fator = alavanca["fator"]
            alavancada[alvo] = alavancada.get(alvo, 0.0) + saldo * abs(fator)
            fatores[alvo] = fator
        else:
            direta[ticker] = direta.get(ticker, 0.0) + saldo

    alvos = sorted(set(direta) | set(alavancada))
    if not alvos:
        return pd.DataFrame()

    linhas = []
    for alvo in alvos:
        pela_direta = direta.get(alvo, 0.0)
        pelo_fundo = alavancada.get(alvo, 0.0)
        total = pela_direta + pelo_fundo
        linhas.append({
            "papel": alvo,
            "direta": pela_direta,
            "via_alavancado": pelo_fundo,
            "exposicao": total,
            "participacao": total / carteira if carteira else None,
            "fator": fatores.get(alvo),
        })

    tabela = pd.DataFrame(linhas).sort_values("exposicao", ascending=False)
    return tabela.reset_index(drop=True)

def rentabilidade_por_mes_e_ano() -> pd.DataFrame:
    """A rentabilidade da carteira em grade: uma linha por ano, doze colunas.

    Colunas: ano, m01..m12, no_ano, acumulado

    A grade responde uma pergunta que a linha do tempo nao responde bem —
    *"como foi cada mes?"*. Numa linha de saldo, um mes ruim no meio de uma
    subida some; na grade ele fica vermelho no meio da fileira.

    `no_ano` compoe os meses daquele ano; `acumulado` compoe TUDO desde o
    inicio ate o fim daquele ano. Os dois multiplicam, nao somam — 1,82%
    seguido de 1,34% da 3,18%, nao 3,16%.

    Mes sem dado fica `None` e a tela deixa a celula vazia. Zero ali diria
    "nao rendeu", que e diferente de "nao sei".
    """
    colunas = ["ano"] + [f"m{n:02d}" for n in range(1, 13)] + ["no_ano",
                                                               "acumulado"]
    carteira = evolucao_carteira()
    if carteira.empty:
        return pd.DataFrame(columns=colunas)

    carteira = carteira.copy()
    carteira["ano"] = carteira["mes"].astype(str).str[:4]
    carteira["numero"] = carteira["mes"].astype(str).str[5:7].astype(int)

    acumulado = 1.0
    linhas = []
    for ano in sorted(carteira["ano"].unique()):
        do_ano = carteira[carteira["ano"] == ano]
        linha = {"ano": ano}
        for numero in range(1, 13):
            celula = do_ano[do_ano["numero"] == numero]
            linha[f"m{numero:02d}"] = (float(celula["rendimento_pct"].iloc[0])
                                       if len(celula) else None)
        no_ano = 1.0
        for pct in do_ano["rendimento_pct"]:
            no_ano *= (1 + float(pct))
            acumulado *= (1 + float(pct))
        linha["no_ano"] = no_ano - 1
        linha["acumulado"] = acumulado - 1
        linhas.append(linha)

    return pd.DataFrame(linhas, columns=colunas)


_TIPO_POR_GRUPO = {
    "TESOURO DIRETO": "Tesouro Direto",
    "FUNDOS DE INVESTIMENTOS": "Fundo",
    "RENDA FIXA": "Renda Fixa",
    "ACOES": "Renda Variável",
    "FUNDOS IMOBILIARIOS": "Renda Variável",
}

_INDEXADOR_POR_CLASSE = {
    "NTN-B (inflação)": "IPCA+",
    "Tesouro Selic": "Selic",
    "Prefixado": "Prefixado",
    "Fundo DI": "CDI",
    "CDB / LCI / LCA": "CDI",
    "Ação BR": "Variável",
    "ETF": "Variável",
    "FII": "Variável",
    "Stock EUA": "Variável",
    "Cripto": "Variável",
}


def macros() -> pd.DataFrame:
    """Os macros cadastrados, na ordem em que devem aparecer na tela."""
    return banco.df("SELECT * FROM macros_ativo ORDER BY ordem, nome")


def classes() -> pd.DataFrame:
    """As classes cadastradas, com o macro a que pertencem."""
    return banco.df("SELECT * FROM classes_ativo ORDER BY ordem, nome")


def temas() -> pd.DataFrame:
    """Os temas de exposicao cadastrados, na ordem em que aparecem na tela."""
    return banco.df("SELECT * FROM temas_ativo ORDER BY ordem, nome")


def sugestao_de_tema(ticker: str | None) -> str | None:
    """O que o provedor de fundamentos DIZ sobre o setor do papel.

    E SUGESTAO, NUNCA PREENCHIMENTO. Para a IREN, o yfinance devolve
    `sector = "Financial Services"` e `industry = "Capital Markets"` — a
    classificacao contabil da empresa, nao a exposicao economica dela. Uma
    mineradora de bitcoin que virou datacenter de IA aparece como servico
    financeiro, e com toda a confianca de um dado que veio de fora.

    Por isso isto devolve TEXTO para a tela mostrar ao lado do campo, e nao um
    tema para gravar. Quem decide e voce, olhando.

    Devolve None quando nao ha ticker ou nao ha fundamento guardado — nunca
    busca na rede: esta funcao roda a cada desenho da tabela de cadastro.
    """
    if vazio(ticker):
        return None

    linha = banco.consultar_um(
        "SELECT dados FROM fundamentos WHERE ticker = ?", (str(ticker).strip(),))
    if not linha:
        return None

    import json
    try:
        dados = json.loads(linha["dados"])
    except (ValueError, TypeError):
        return None

    partes = [str(dados.get(campo)).strip()
              for campo in ("sector", "industry")
              if not vazio(dados.get(campo))]
    return " · ".join(partes) or None


def macro_da_classe(nome_classe: str | None) -> str | None:
    """Sobe um nivel: dada a classe, devolve o macro."""
    if not nome_classe:
        return None
    linha = banco.consultar_um(
        "SELECT macro FROM classes_ativo WHERE nome = ?", (nome_classe,))
    return linha["macro"] if linha else None


def classificar_papel(nome: str, grupo: str | None = None) -> tuple[str | None, str | None]:
    """Descobre (macro, classe) a partir do NOME do papel.

    POR QUE PELO NOME, E NAO PELO GRUPO DO ARQUIVO
    ----------------------------------------------
    A corretora agrupa por conveniencia dela, e o rotulo muda de um mes para o
    outro. No arquivo de 22/08, "NTN-B ago/2060" e "LFT mar/2031" aparecem no
    MESMO bloco, rotulado "Pos-Fixado" — mas a NTN-B e indexada a inflacao e a
    LFT a Selic. Sao classes diferentes, com riscos diferentes.

    Ja o nome do papel nao mente: quem se chama NTN-B e NTN-B.

    Cada classe traz em `palavras_chave` uma lista separada por "|". A primeira
    classe (na ordem cadastrada) cuja palavra-chave aparecer no nome vence.
    Classes de palavra-chave vazia — Acao BR, Stock EUA — so entram por
    classificacao manual, porque nao ha padrao no nome que as identifique.
    """
    if not nome:
        return (None, None)

    texto = normalizar_texto(nome)
    for _, linha in classes().iterrows():
        palavras = (linha["palavras_chave"] or "").strip()
        if not palavras:
            continue
        for palavra in palavras.split("|"):
            palavra = palavra.strip().upper()
            if palavra and palavra in texto:
                return (linha["macro"], linha["nome"])

    if re.fullmatch(r"[A-Z]{4}[3-6]", texto.strip()):
        return ("Renda Variável", "Ação BR")

    if grupo:
        grupo_normalizado = normalizar_texto(grupo)
        if "TESOURO" in grupo_normalizado or "RENDA FIXA" in grupo_normalizado:
            return ("Renda Fixa", None)
        if "IMOBILIARIO" in grupo_normalizado:
            return ("Renda Variável", None)

    return (None, None)


# ---------------------------------------------------------------------------
# OS EIXOS DA CARTEIRA
# ---------------------------------------------------------------------------
# A mesma carteira responde a perguntas diferentes conforme o eixo por que se
# olha. `macro` e `classe` ja existiam; `prazo`, `indexador` e `liquidez` sao
# DERIVADOS do que o cadastro ja guarda — nao ha campo novo para preencher.
#
# EIXO, NAO NIVEL. Sao formas independentes de cortar a mesma carteira, e nao
# degraus de uma arvore: um NTN-B 2045 e "Renda Fixa" no macro, "NTN-B" na
# classe e "IPCA+ Ultra longo" no prazo, sem que um contenha o outro.

DIMENSOES = ("macro", "classe", "tema", "prazo", "indexador", "liquidez")

ROTULOS_DIMENSAO = {
    "macro": "Macro",
    "classe": "Classe",
    "tema": "Tema (exposição)",
    "prazo": "Prazo e indexador",
    "indexador": "Indexador",
    "liquidez": "Liquidez",
}

# Os cortes, em anos ate o vencimento. O ultimo balde e tudo acima do maior.
CORTES_DE_PRAZO = ((3, "Curto"), (8, "Médio"), (20, "Longo"))
PRAZO_MAIS_LONGO = "Ultra longo"

BALDE_DIARIA = "Liquidez diária"
BALDE_SEM_PRAZO = "Sem prazo (renda variável)"
BALDE_SEM_VENCIMENTO = "Sem vencimento definido"

_MACROS_SEM_PRAZO = ("Renda Variável", "Internacional", "Outros")


def _anos_ate(vencimento, referencia: date) -> float | None:
    """Quantos anos faltam do `referencia` ate o vencimento. None se nao da."""
    if vazio(vencimento):
        return None
    texto = str(vencimento)[:10]
    try:
        alvo = date.fromisoformat(texto)
    except ValueError:
        return None
    return (alvo - referencia).days / 365.25


def balde_de_prazo(papel, mes: str | None = None,
                   macro: str | None = None) -> str:
    """Em que faixa de prazo este papel cai, no mes olhado.

    A ORDEM DAS REGRAS E O DESENHO:

        1. renda variavel nao tem prazo  -> "Sem prazo (renda variável)"
        2. liquidez diaria vence tudo    -> "Liquidez diária"
        3. tem vencimento                -> faixa pelo tempo que falta
        4. resto                         -> "Sem vencimento definido"

    A regra 2 vem antes da 3 de proposito: um CDB com liquidez diaria e
    vencimento em 2027 e dinheiro disponivel HOJE — o vencimento dele so diz
    ate quando ele rende, nao quando voce alcanca o dinheiro.

    A regra 1 tambem precisa vir antes da 2, senao uma acao (que tem liquidez
    "Diária" no cadastro) cairia no balde de caixa. Acao e liquida e nao e
    reserva: o preco no dia do resgate e que decide.

    A REFERENCIA E O MES OLHADO, NAO `hoje`. Um NTN-B 2032 era longo em 2020 e
    e medio agora. Usar `hoje` faria a tela de um mes passado classificar os
    papeis com a regua de hoje — e o grafico de evolucao mentiria.
    """
    if macro in _MACROS_SEM_PRAZO:
        return BALDE_SEM_PRAZO
    indexador = str(papel.get("indexador") or "").strip()
    if normalizar_texto(indexador).startswith("VARIAVEL"):
        return BALDE_SEM_PRAZO

    liquidez = normalizar_texto(str(papel.get("liquidez") or ""))
    if liquidez.startswith("DI"):          # "Diária", "Diaria", "D+0"
        return BALDE_DIARIA

    referencia = cambio.ultimo_dia_do_mes(mes) if mes else date.today()
    anos = _anos_ate(papel.get("data_vencimento"), referencia or date.today())
    if anos is None:
        return BALDE_SEM_VENCIMENTO

    faixa = PRAZO_MAIS_LONGO
    for limite, nome in CORTES_DE_PRAZO:
        if anos <= limite:
            faixa = nome
            break

    return f"{indexador} {faixa}".strip() if indexador else faixa


def balde_de(papel, dimensao: str, mes: str | None = None,
             macro: str | None = None) -> str:
    """Em que grupo o papel cai, nesta dimensao.

    `papel` e a linha do CADASTRO (precisa de `indexador`, `data_vencimento` e
    `liquidez`), nao a de `posicao()`, que nao carrega esses tres campos.

    Nunca devolve vazio: um papel sem informacao vira "(sem …)" e continua
    somando. Sumir da conta seria pior que aparecer mal classificado — o total
    da tela deixaria de bater com o da carteira.
    """
    if dimensao == "prazo":
        return balde_de_prazo(papel, mes, macro)

    if dimensao == "macro":
        return macro or "(sem macro)"

    if dimensao == "classe":
        return papel.get("classe") or "(sem classe)"

    valor = papel.get(dimensao)
    return str(valor).strip() if not vazio(valor) else f"(sem {dimensao})"


def tipo_do_papel(grupo: str | None, macro: str | None) -> str:
    """Escolhe um `tipo` do cadastro (a lista TIPOS) para um papel importado."""
    if grupo:
        chave = normalizar_texto(grupo)
        for marca, tipo in _TIPO_POR_GRUPO.items():
            if marca in chave:
                return tipo
    if macro in TIPOS:
        return macro
    return "Outro"


def metas(nivel: str = "classe") -> pd.DataFrame:
    """As metas cadastradas num nivel ('macro' ou 'classe').

    `percentual_alvo` e `tolerancia` sao FRACOES: 0.30 = 30%, 0.05 = 5 pontos.
    """
    return banco.df(
        """SELECT nome, percentual_alvo, tolerancia
           FROM metas_alocacao WHERE nivel = ? ORDER BY nome""",
        (nivel,),
    )


def salvar_meta(nivel: str, nome: str, percentual_alvo: float,
                tolerancia: float = 0.05) -> None:
    """Grava (ou corrige) a meta de um macro/classe."""
    banco.executar(
        """INSERT INTO metas_alocacao (nivel, nome, percentual_alvo, tolerancia)
           VALUES (?,?,?,?)
           ON CONFLICT(nivel, nome) DO UPDATE SET
             percentual_alvo = excluded.percentual_alvo,
             tolerancia = excluded.tolerancia""",
        (nivel, nome, float(percentual_alvo), float(tolerancia)),
    )


def apagar_meta(nivel: str, nome: str) -> None:
    """Remove a meta de um macro/classe."""
    banco.executar(
        "DELETE FROM metas_alocacao WHERE nivel = ? AND nome = ?", (nivel, nome))


def soma_das_metas(nivel: str = "classe") -> float:
    """Quanto as metas somam. Deveria dar 1,0 (100%); serve para avisar."""
    tabela = metas(nivel)
    return float(tabela["percentual_alvo"].sum()) if not tabela.empty else 0.0


def alocacao_atual(mes: str | None = None, nivel: str = "classe",
                   carteira: pd.DataFrame | None = None) -> pd.DataFrame:
    """Agrupa a carteira por um EIXO e compara com a meta.

    `nivel` e qualquer nome de `DIMENSOES`: macro, classe, prazo, indexador ou
    liquidez. Metas de alocacao so existem para macro e classe — nos eixos
    derivados toda linha vem com `tem_meta = False` e alvo zero, e a tela
    esconde as colunas de meta. Isso e de proposito: "quanto quero ter em
    IPCA+ Longo" e uma pergunta legitima, mas nao e a que este cadastro
    responde hoje, e inventar um alvo vazio seria pior que nao ter.

    Colunas: nome, saldo, percentual, percentual_alvo, tolerancia, desvio,
             dentro_faixa, tem_meta, quantidade

    Uma classe com META mas SEM DINHEIRO entra na tabela com saldo zero — e
    justamente ela que o rebalanceamento precisa enxergar. Uma classe com
    dinheiro e sem meta tambem entra, marcada com `tem_meta = False`, para
    voce nao esquecer que ela existe.

    `carteira` e so performance: a tela chama esta funcao duas vezes seguidas
    (uma por classe, outra por macro) e as duas montavam a mesma `posicao()`
    do zero. Ver a nota em `evolucao`.
    """
    colunas = ["nome", "saldo", "percentual", "percentual_alvo", "tolerancia",
               "desvio", "dentro_faixa", "tem_meta", "quantidade"]

    if carteira is None:
        carteira = posicao(mes)
    lista = cadastro()

    por_nome: dict[str, float] = {}
    contagem: dict[str, int] = {}
    if not carteira.empty:
        # A linha inteira do cadastro, e nao so a classe: as dimensoes
        # derivadas precisam de `indexador`, `data_vencimento` e `liquidez`,
        # que `posicao()` nao carrega.
        cadastro_por_id = {}
        if not lista.empty:
            cadastro_por_id = {int(l["id"]): l for _, l in lista.iterrows()}

        macro_por_classe = {l["nome"]: l["macro"] for _, l in classes().iterrows()}

        for _, item in carteira.iterrows():
            papel = cadastro_por_id.get(int(item["id"]), item)
            classe = papel.get("classe")
            if not classe:
                _, classe = classificar_papel(item["nome"], item.get("tipo"))
            macro = macro_por_classe.get(classe)

            chave = balde_de(
                {**dict(papel), "classe": classe}, nivel, mes, macro)
            por_nome[chave] = por_nome.get(chave, 0.0) + float(item["saldo"] or 0)
            contagem[chave] = contagem.get(chave, 0) + 1

    tabela_metas = metas(nivel)
    metas_por_nome = {l["nome"]: (float(l["percentual_alvo"]), float(l["tolerancia"]))
                      for _, l in tabela_metas.iterrows()}

    for nome_meta in metas_por_nome:
        por_nome.setdefault(nome_meta, 0.0)

    if not por_nome:
        return pd.DataFrame(columns=colunas)

    total = sum(por_nome.values())
    linhas = []
    for nome, saldo in por_nome.items():
        alvo, tolerancia = metas_por_nome.get(nome, (0.0, 0.05))
        percentual = saldo / total if total else 0.0
        desvio = percentual - alvo
        linhas.append({
            "nome": nome,
            "saldo": saldo,
            "percentual": percentual,
            "percentual_alvo": alvo,
            "tolerancia": tolerancia,
            "desvio": desvio,
            "dentro_faixa": abs(desvio) <= tolerancia,
            "tem_meta": nome in metas_por_nome,
            "quantidade": contagem.get(nome, 0),
        })

    return (pd.DataFrame(linhas, columns=colunas)
            .sort_values("saldo", ascending=False)
            .reset_index(drop=True))


def rebalancear(aporte: float, mes: str | None = None,
                nivel: str = "classe") -> pd.DataFrame:
    """Diz quanto do aporte vai para cada classe, sem nunca sugerir vender.

    Colunas: nome, saldo, percentual, percentual_alvo, tolerancia, desvio,
             dentro_faixa, tem_meta, quantidade, ideal, falta, aportar,
             saldo_depois, percentual_depois, desvio_depois

    Garantias (conferidas em `verificacao/conferir_rebalanceamento.py`):
      - a soma da coluna `aportar` e EXATAMENTE o aporte informado;
      - nenhuma classe recebe valor negativo (nunca sugere vender);
      - nenhuma classe passa do proprio ideal por causa do aporte;
      - a soma das distancias ate a meta nunca aumenta.

    A ultima garantia e sobre a carteira INTEIRA, nao classe por classe: um
    aporte pode aproximar a soma das distancias enquanto UMA classe se afasta,
    e ainda assim ser o movimento certo. Prometer a garantia classe por classe
    seria mais bonito e seria mentira.
    """
    base = alocacao_atual(mes, nivel)
    if base.empty:
        return base.assign(ideal=[], falta=[], aportar=[], saldo_depois=[],
                           percentual_depois=[], desvio_depois=[])

    aporte = max(0.0, float(aporte or 0))
    total_atual = float(base["saldo"].sum())
    total_novo = total_atual + aporte

    base = base.copy()
    base["ideal"] = base["percentual_alvo"] * total_novo
    base["falta"] = (base["ideal"] - base["saldo"]).clip(lower=0)

    soma_faltas = float(base["falta"].sum())
    soma_alvos = float(base["percentual_alvo"].sum())

    if aporte <= 0 or soma_alvos <= 0:
        base["aportar"] = 0.0
    elif soma_faltas <= 0:
        base["aportar"] = aporte * base["percentual_alvo"] / soma_alvos
    elif aporte <= soma_faltas:
        base["aportar"] = aporte * base["falta"] / soma_faltas
    else:
        sobra = aporte - soma_faltas
        base["aportar"] = base["falta"] + sobra * base["percentual_alvo"] / soma_alvos

    base["aportar"] = base["aportar"].round(2)
    distribuido = float(base["aportar"].sum())
    residuo = round(aporte - distribuido, 2)
    if residuo and distribuido > 0:
        maior = base["aportar"].idxmax()
        base.loc[maior, "aportar"] = round(base.loc[maior, "aportar"] + residuo, 2)

    base["saldo_depois"] = base["saldo"] + base["aportar"]
    base["percentual_depois"] = (base["saldo_depois"] / total_novo
                                 if total_novo else 0.0)
    base["desvio_depois"] = base["percentual_depois"] - base["percentual_alvo"]

    return base.sort_values("aportar", ascending=False).reset_index(drop=True)


def meses_para_meta(aporte: float, mes: str | None = None,
                    nivel: str = "classe", limite: int = 360) -> pd.DataFrame:
    """Em quantos meses cada classe entra na faixa da meta, no ritmo informado.

    Simula mes a mes, aplicando a mesma regra de `rebalancear`. A simulacao
    IGNORA rendimento de proposito: ninguem sabe quanto a bolsa vai render, e
    supor um numero deixaria a resposta bonita e mentirosa. Sem rendimento, o
    prazo e o pior caso realista — e o que voce quer saber.

    Colunas: nome, percentual, percentual_alvo, meses, alcancavel
    """
    base = alocacao_atual(mes, nivel)
    colunas = ["nome", "percentual", "percentual_alvo", "meses", "alcancavel"]
    if base.empty:
        return pd.DataFrame(columns=colunas)

    aporte = max(0.0, float(aporte or 0))
    nomes = list(base["nome"])
    saldos_simulados = {n: float(s) for n, s in zip(nomes, base["saldo"])}
    alvos = {n: float(a) for n, a in zip(nomes, base["percentual_alvo"])}
    tolerancias = {n: float(t) for n, t in zip(nomes, base["tolerancia"])}
    soma_alvos = sum(alvos.values())

    def dentro(nome, total):
        atual = saldos_simulados[nome] / total if total else 0.0
        return abs(atual - alvos[nome]) <= tolerancias[nome]

    total = sum(saldos_simulados.values())
    quando: dict[str, int | None] = {
        n: (0 if dentro(n, total) else None) for n in nomes}

    if aporte > 0 and soma_alvos > 0:
        for mes_numero in range(1, limite + 1):
            if all(v is not None for v in quando.values()):
                break
            total_novo = total + aporte
            faltas = {n: max(0.0, alvos[n] * total_novo - saldos_simulados[n])
                      for n in nomes}
            soma_faltas = sum(faltas.values())
            for n in nomes:
                if soma_faltas > 0:
                    parte = aporte * faltas[n] / soma_faltas
                else:
                    parte = aporte * alvos[n] / soma_alvos
                saldos_simulados[n] += parte
            total = total_novo
            for n in nomes:
                if quando[n] is None and dentro(n, total):
                    quando[n] = mes_numero

    linhas = []
    for _, item in base.iterrows():
        nome = item["nome"]
        linhas.append({
            "nome": nome,
            "percentual": item["percentual"],
            "percentual_alvo": item["percentual_alvo"],
            "meses": quando[nome],
            "alcancavel": quando[nome] is not None,
        })
    return pd.DataFrame(linhas, columns=colunas)


def _investimento_por_nome(nome: str) -> int | None:
    """Acha um investimento ja cadastrado pelo nome (ignorando maiuscula)."""
    linha = banco.consultar_um(
        "SELECT id FROM investimentos WHERE UPPER(TRIM(nome)) = UPPER(TRIM(?))",
        (nome,))
    return int(linha["id"]) if linha else None


def _movimentos_do_papel(nome: str, mes: str) -> tuple[float, float] | None:
    """Compra e venda DAQUELE papel no mes, tiradas do extrato da corretora.

    E a fonte mais confiavel que existe, porque e dinheiro de verdade mudando
    de lugar — nao uma coluna calculada pela corretora. O extrato nomeia o
    fundo em cada linha:

        "RESGATE Trend DI FIC RF Simples RL"          -> venda
        "TED ... APLICACAO FUNDOS Trend DI"           -> compra

    Casamos pelas DUAS PRIMEIRAS PALAVRAS do nome ("TREND DI"), porque o
    extrato costuma abreviar o resto. Duas palavras ja separam "Trend DI" de
    "Trend Investback".

    O Tesouro nao entra aqui: o extrato so diz "COMPRA TESOURO DIRETO
    CLIENTES", sem dizer QUAL titulo. Para esses, quem resolve e a quantidade.

    Devolve (aporte, resgate) ou None se nada casou.
    """
    palavras = normalizar_texto(nome).split()
    if len(palavras) < 2:
        return None
    marca = " ".join(palavras[:2])

    aporte = resgate = 0.0
    achou = False
    for linha in banco.consultar(
            """SELECT descricao, valor, tipo_movimento FROM investimentos_movimentos
               WHERE mes_competencia = ? AND tipo_movimento IN ('compra', 'venda')""",
            (mes,)):
        if marca not in normalizar_texto(linha["descricao"]):
            continue
        achou = True
        if linha["valor"] < 0:
            aporte += -float(linha["valor"])
        else:
            resgate += float(linha["valor"])
    return (aporte, resgate) if achou else None


def _quantidade_anterior(investimento_id: int, mes: str) -> tuple[float, float] | None:
    """(quantidade, preco unitario) do ultimo mes ANTES deste, se houver."""
    linha = banco.consultar_um(
        """SELECT quantidade, saldo FROM investimentos_saldos
           WHERE investimento_id = ? AND mes < ? AND quantidade IS NOT NULL
             AND quantidade > 0
           ORDER BY mes DESC LIMIT 1""",
        (investimento_id, mes))
    if not linha:
        return None
    quantidade = float(linha["quantidade"])
    return quantidade, float(linha["saldo"] or 0) / quantidade


def _custo_anterior(investimento_id: int, mes: str) -> float | None:
    """O custo aplicado no ultimo mes ANTES deste, se ja tiver sido gravado."""
    linha = banco.consultar_um(
        """SELECT custo_aplicado FROM investimentos_saldos
           WHERE investimento_id = ? AND mes < ? AND custo_aplicado IS NOT NULL
           ORDER BY mes DESC LIMIT 1""",
        (investimento_id, mes))
    return float(linha["custo_aplicado"]) if linha else None


def _somar_repetidos(linhas: list[dict]) -> list[dict]:
    """Junta numa linha so os papeis que aparecem com o MESMO NOME no arquivo.

    POR QUE ISTO PRECISOU EXISTIR (2026-08-23)

    O arquivo de abril/2024 traz DUAS linhas chamadas exatamente
    "CDB BANCO XP S.A. - JUN/2024", de R$ ···· e R$ ···· Sao duas
    aplicacoes distintas no mesmo papel — compradas em datas diferentes, com o
    mesmo emissor e o mesmo vencimento, e a corretora nao as diferencia.

    O estrago sem esta funcao e silencioso: `_investimento_por_nome` acha o
    mesmo id para as duas, e `salvar_saldo` grava com
    `ON CONFLICT(investimento_id, mes) DO UPDATE`. A segunda linha SOBRESCREVE
    a primeira, e R$ ···· somem da carteira sem nenhum aviso.

    Some sem aviso porque o total do MES continua certo: ele vem de
    `meta['soma_ativos']`, lido do cabecalho do arquivo. So a visao por papel
    fica errada — que e exatamente o tipo de erro que ninguem percebe.

    Somar e o certo aqui: dois CDBs do mesmo emissor e vencimento sao o mesmo
    instrumento para efeito de carteira, alocacao e risco. O que nao da para
    fazer e escolher uma das duas.
    """
    juntos: dict[str, dict] = {}
    for linha in linhas:
        chave = normalizar_texto(linha.get("nome"))
        if chave not in juntos:
            juntos[chave] = dict(linha)
            continue
        alvo = juntos[chave]
        alvo["valor"] = (alvo.get("valor") or 0) + (linha.get("valor") or 0)
        for campo in ("quantidade", "valor_aplicado"):
            a, b = alvo.get(campo), linha.get(campo)
            alvo[campo] = (a + b) if (a is not None and b is not None) else None
    return list(juntos.values())


def gravar_posicao(resultado) -> dict:
    """Grava no banco a posicao lida de `leitores/posicao_xp.py`.

    Para cada papel do arquivo:
      1. acha o investimento pelo nome — se for a primeira vez, cadastra,
         ja classificado por `classificar_papel`;
      2. grava o saldo do mes e o custo aplicado;
      3. deduz o APORTE do mes pela variacao do custo (ver a migracao 4).

    No fim grava o total em `patrimonio_mensal.saldo_aplicado_manual`, que a
    tela de Patrimonio ja usa com prioridade sobre a estimativa. E o que faz o
    numero do patrimonio deixar de ser um palpite.

    Devolve um resumo: criados, atualizados, mes, total.
    """
    if resultado.erros or not resultado.linhas:
        return {"criados": 0, "atualizados": 0, "mes": None, "total": 0.0,
                "novos": []}

    mes = resultado.meta["mes_competencia"]
    criados, atualizados, novos = 0, 0, []

    for item in _somar_repetidos(resultado.linhas):
        nome = item["nome"]
        investimento_id = _investimento_por_nome(nome)
        macro, classe = classificar_papel(nome, item.get("grupo"))

        if investimento_id is None:
            investimento_id = salvar({
                "nome": nome,
                "tipo": tipo_do_papel(item.get("grupo"), macro),
                "instituicao": "XP",
                "indexador": _INDEXADOR_POR_CLASSE.get(classe),
                "data_vencimento": item.get("vencimento"),
                "liquidez": "No vencimento" if item.get("vencimento") else "Diária",
                "classe": classe,
                "moeda": "BRL",
                "ativo": 1,
            })
            criados += 1
            novos.append(f"{nome} → {classe or 'sem classe'}")
        else:
            atualizados += 1
            atual = banco.consultar_um(
                "SELECT classe FROM investimentos WHERE id = ?", (investimento_id,))
            if classe and atual and not (atual["classe"] or "").strip():
                banco.executar("UPDATE investimentos SET classe = ? WHERE id = ?",
                               (classe, investimento_id))
            banco.executar("UPDATE investimentos SET ativo = 1 WHERE id = ?",
                           (investimento_id,))

        custo = item.get("valor_aplicado")
        quantidade = item.get("quantidade")
        aporte = resgate = 0.0

        primeira_vez = not banco.consultar_um(
            """SELECT 1 FROM investimentos_saldos
               WHERE investimento_id = ? AND mes < ? LIMIT 1""",
            (investimento_id, mes))

        movimentos = None if primeira_vez else _movimentos_do_papel(nome, mes)

        if primeira_vez:
            aporte = item["valor"]

        elif movimentos is not None:
            aporte, resgate = movimentos

        elif custo is not None:
            anterior = _custo_anterior(investimento_id, mes)
            if anterior is not None:
                diferenca = custo - anterior
                aporte = max(0.0, diferenca)
                resgate = max(0.0, -diferenca)

        elif quantidade:
            anterior = _quantidade_anterior(investimento_id, mes)
            preco_unitario = item["valor"] / quantidade if quantidade else 0.0
            if anterior is not None:
                diferenca_qtd = quantidade - anterior[0]
                if diferenca_qtd > 0:
                    aporte = diferenca_qtd * preco_unitario
                elif diferenca_qtd < 0:
                    resgate = -diferenca_qtd * anterior[1]

        salvar_saldo(investimento_id, mes, item["valor"], aporte, resgate,
                     observacao=f"Importado da posição de {item['data_posicao']}")
        banco.executar(
            """UPDATE investimentos_saldos SET custo_aplicado = ?, quantidade = ?
               WHERE investimento_id = ? AND mes = ?""",
            (float(custo) if custo is not None else None,
             float(quantidade) if quantidade else None,
             investimento_id, mes))

    nomes_na_foto = {l["nome"].strip().upper() for l in resultado.linhas}
    nomes_na_foto.add(banco.NOME_CAIXA_CORRETORA.strip().upper())
    sumidos = []
    for candidato in banco.consultar(
            """SELECT DISTINCT i.id, i.nome
               FROM investimentos i
               JOIN investimentos_saldos s ON s.investimento_id = i.id
               WHERE s.observacao LIKE 'Importado da posição%'"""):
        if candidato["nome"].strip().upper() in nomes_na_foto:
            continue
        anterior = banco.consultar_um(
            """SELECT mes, saldo FROM investimentos_saldos
               WHERE investimento_id = ? AND mes < ? ORDER BY mes DESC LIMIT 1""",
            (candidato["id"], mes))
        if not anterior or not anterior["saldo"]:
            continue
        salvar_saldo(candidato["id"], mes, 0.0, 0.0, float(anterior["saldo"]),
                     observacao=f"Ausente da posição de {resultado.meta['data_posicao']} "
                                f"— tratado como vendido")
        banco.executar(
            """UPDATE investimentos_saldos SET custo_aplicado = 0
               WHERE investimento_id = ? AND mes = ?""", (candidato["id"], mes))
        banco.executar("UPDATE investimentos SET ativo = 0 WHERE id = ?",
                       (candidato["id"],))
        sumidos.append(candidato["nome"])

    caixa = float(resultado.meta.get("saldo_disponivel") or 0)
    id_caixa = _investimento_por_nome(banco.NOME_CAIXA_CORRETORA)
    if id_caixa is None and caixa > 0:
        id_caixa = salvar({
            "nome": banco.NOME_CAIXA_CORRETORA, "tipo": "Outro",
            "instituicao": "XP", "classe": "Saldo em conta", "moeda": "BRL",
            "liquidez": "Diária", "ativo": 1,
            "observacao": "Criado pela importação da posição: coluna "
                          "'Saldo Disponível' do arquivo da corretora.",
        })
        criados += 1
        novos.append(f"{banco.NOME_CAIXA_CORRETORA} → Saldo em conta")
    if id_caixa is not None:
        anterior_caixa = banco.consultar_um(
            """SELECT saldo FROM investimentos_saldos
               WHERE investimento_id = ? AND mes < ? ORDER BY mes DESC LIMIT 1""",
            (id_caixa, mes))
        saldo_antes = float(anterior_caixa["saldo"] or 0) if anterior_caixa else 0.0
        variacao = caixa - saldo_antes

        salvar_saldo(id_caixa, mes, caixa,
                     aporte=max(0.0, variacao), resgate=max(0.0, -variacao),
                     observacao=f"Importado da posição de "
                                f"{resultado.meta['data_posicao']}")

    total = float(resultado.meta.get("patrimonio")
                  or (resultado.meta.get("soma_ativos") or 0) + caixa)

    return {"criados": criados, "atualizados": atualizados, "mes": mes,
            "total": total, "caixa": caixa, "novos": novos, "sumidos": sumidos}


def gravar_movimentos(resultado) -> dict:
    """Grava as movimentacoes lidas de `leitores/extrato_xp_xlsx.py`.

    O "INSERT OR IGNORE" com a coluna `id_unico UNIQUE` faz a deduplicacao
    acontecer no proprio banco: reimportar o mesmo arquivo, ou importar dois
    extratos que se sobrepoem, simplesmente nao grava a segunda copia.
    """
    if resultado.erros or not resultado.linhas:
        return {"gravados": 0, "ignorados": 0}

    parametros = [
        (l["id_unico"], l["data"], l.get("liquidacao"), l["mes_competencia"],
         l["descricao"], l["valor"], l.get("saldo_apos"), l["tipo_movimento"],
         banco.agora())
        for l in resultado.linhas
    ]
    gravados = banco.executar_muitos(
        """INSERT OR IGNORE INTO investimentos_movimentos
           (id_unico, data, liquidacao, mes_competencia, descricao, valor,
            saldo_apos, tipo_movimento, criado_em)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        parametros,
    )
    return {"gravados": gravados, "ignorados": len(parametros) - gravados}


def movimentos(mes: str | None = None, tipo: str | None = None) -> pd.DataFrame:
    """Le as movimentacoes da conta de investimento, com filtros opcionais."""
    sql = "SELECT * FROM investimentos_movimentos WHERE 1=1"
    params: list = []
    if mes:
        sql += " AND mes_competencia = ?"
        params.append(mes)
    if tipo:
        sql += " AND tipo_movimento = ?"
        params.append(tipo)
    return banco.df(sql + " ORDER BY data DESC, id DESC", tuple(params))


def resumo_movimentos(mes: str | None = None) -> pd.DataFrame:
    """Soma as movimentacoes por tipo. Devolve [tipo_movimento, quantidade, soma]."""
    sql = """SELECT tipo_movimento, COUNT(*) AS quantidade, SUM(valor) AS soma
             FROM investimentos_movimentos"""
    params: list = []
    if mes:
        sql += " WHERE mes_competencia = ?"
        params.append(mes)
    return banco.df(sql + " GROUP BY tipo_movimento ORDER BY ABS(SUM(valor)) DESC",
                    tuple(params))
