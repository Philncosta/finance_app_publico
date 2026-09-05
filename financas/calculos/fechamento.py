"""
fechamento.py — O caixa fecha, ou o app diz de quanto nao fechou.
==============================================================================

A EQUACAO
---------
    saldo_inicial + entradas − saidas + rendimento + cambio − custos
    + nao_explicado = saldo_final

`nao_explicado` e calculado POR DIFERENCA e sempre exibido. Essa e a mudanca
de fundo em relacao ao que existia.

POR QUE ISTO PRECISOU EXISTIR
-----------------------------
`investimentos.conciliar()` fazia:

    diferenca = carteira − aportado − saldo_abertura     # e chamava de rendimento

Toda sobra virava rendimento, porque nao havia outro lugar para por. Enquanto
so existissem dois caminhos para o dinheiro cruzar a fronteira (conta corrente
-> corretora e volta), a conta fechava. Mas o dinheiro dele anda por tres
contas, e um dia entrou por um quarto caminho:

    2026-09-02   TED - RECEBIMENTO EXTERNO   +R$ ····

Dinheiro entrando de fora DIRETO na corretora. Nao e aporte
(nao veio da conta corrente) nem rendimento (nao foi a carteira que produziu).
`fluxo_externo_mensal()` nao o contava, entao ele apareceu como lucro de
investimento — e ninguem foi avisado.

O pedido dele foi exatamente este: **"nao pode haver dinheiro sumindo no meio
do caminho"**. Para isso o app precisa, antes de tudo, ser capaz de DIZER que
sumiu. Uma sobra empurrada para "rendimento" e uma sobra que nao existe.

DERIVA O QUE DA, GUARDA O QUE NAO DA
------------------------------------
O componente de cada movimento sai do `tipo_movimento` por
`COMPONENTE_DO_TIPO`. So `outro` sobra — e ai `natureza` guarda a resposta que
voce deu na triagem, porque "TED - RECEBIMENTO EXTERNO" tanto pode ser venda
quanto heranca ou reembolso, e adivinhar erraria em silencio.

TRANSFERENCIA INTERNA SOMA ZERO
-------------------------------
Dinheiro indo da conta corrente para a de investimentos aparece nas duas
contas, com sinais opostos. No total, some. E isso que prova que nada se perdeu
entre elas — e a checagem que `conferir_fechamento.py` faz para todo mes.
"""

from __future__ import annotations

import pandas as pd

from financas import banco, config

# Em que componente da equacao cada movimento da corretora entra.
#
#   interna    anda entre as SUAS contas: soma zero no total
#   rendimento a carteira produziu (juros, dividendo, rendimento de fundo)
#   custo      saiu para fora e nao volta (imposto, taxa)
#   nenhum     nao cruza fronteira nenhuma: compra e venda so trocam a FORMA
#              do dinheiro dentro da mesma conta
COMPONENTE_DO_TIPO = {
    "aporte": "interna",
    "resgate": "interna",
    "compra": "nenhum",
    "venda": "nenhum",
    "juros": "rendimento",
    "dividendo": "rendimento",
    "rendimento": "rendimento",
    "imposto": "custo",
    "taxa": "custo",
}

# O que a triagem pode responder para um movimento `outro`.
NATUREZAS = {
    "entrada_externa": "dinheiro que entrou de fora (receita)",
    "saida_externa": "dinheiro que saiu para fora (despesa)",
    "interna": "transferência entre contas minhas",
}

# Que sinal o extrato tem de mostrar para cada resposta. A convencao do app e
# a do banco: negativo saiu, positivo entrou.
#
# POR QUE ISTO E UMA TRAVA, E NAO UMA CORRECAO AUTOMATICA. Marcar uma entrada
# de +R$ ···· como "saiu para fora" produzia uma despesa de valor POSITIVO —
# uma linha incoerente, que soma no mes em vez de subtrair. Da para "consertar"
# invertendo o sinal sozinho, mas ai o app inventaria uma despesa de cinco mil
# que nunca existiu. Quem sabe a direcao do dinheiro e o extrato; a sua resposta
# diz de ONDE ele veio, nao para que lado foi. Quando os dois se contradizem,
# um dos dois esta errado e o app pergunta em vez de escolher.
SINAL_ESPERADO = {"entrada_externa": 1, "saida_externa": -1}

COMPONENTES = ("entradas", "saidas", "rendimento", "cambio", "custos",
               "nao_explicado")


def componente_de(movimento) -> str | None:
    """Em que componente da equacao este movimento entra. None = a triar.

    A ordem importa: o `tipo_movimento` manda quando e conhecido, e `natureza`
    so e consultada para o que sobrou. Consultar `natureza` primeiro deixaria
    uma resposta antiga de triagem sobrepor uma regra nova — o mesmo erro de
    guardar o que se deriva.
    """
    tipo = str(movimento.get("tipo_movimento") or "").strip()
    componente = COMPONENTE_DO_TIPO.get(tipo)
    if componente:
        return componente

    natureza = movimento.get("natureza")
    if natureza in NATUREZAS:
        return {"entrada_externa": "entradas",
                "saida_externa": "saidas"}.get(natureza, "interna")
    return None


# Um movimento triado como entrada ou saida externa TEM de ter o seu
# lancamento. Se ele nao existe mais, a triagem esta pela metade.
#
#     SELECT ... FROM investimentos_movimentos m
#      LEFT JOIN lancamentos l ON l.id_unico = 'corretora:' || m.id_unico
#      WHERE m.natureza IN ('entrada_externa','saida_externa') AND l.id IS NULL
#
# POR QUE ISTO PRECISOU EXISTIR. A tela de Lancamentos deixa apagar qualquer
# linha, e Configuracoes deixa apagar todas. Apagando o espelho, o movimento
# continuava marcado como triado: sumia da fila, sumia da receita do mes, e
# NADA avisava. Era o mesmo "dinheiro sumindo no meio do caminho" que este
# modulo existe para impedir, so que criado por nos.
_ESPELHO_OBRIGATORIO = ("entrada_externa", "saida_externa")


def _sem_espelho() -> list[int]:
    """Ids de movimentos triados como externos cujo lancamento nao existe mais."""
    marcadores = ",".join("?" * len(_ESPELHO_OBRIGATORIO))
    return [linha["id"] for linha in banco.consultar(
        f"""SELECT m.id
              FROM investimentos_movimentos m
              LEFT JOIN lancamentos l ON l.id_unico = ? || m.id_unico
             WHERE m.natureza IN ({marcadores})
               AND l.id IS NULL""",
        (PREFIXO_ESPELHO, *_ESPELHO_OBRIGATORIO))]


def movimentos_a_triar() -> pd.DataFrame:
    """Os movimentos que o app nao soube classificar, e por isso pergunta.

    Enquanto estiverem aqui, o valor deles aparece em `nao_explicado`. E de
    proposito que a lista seja a mesma coisa que a linha do fechamento: se
    houver algo a triar, o numero na tela mostra exatamente quanto.

    Duas razoes para um movimento estar aqui, e a coluna `motivo` diz qual:

        "nunca classificado"       o app nao teve regra e voce ainda nao disse
        "o lançamento foi apagado" voce ja disse, mas o lancamento que provava
                                   isso nao existe mais — entao a resposta
                                   perdeu o efeito e o app volta a perguntar

    O segundo caso e auto-reparo de proposito: melhor perguntar de novo do que
    deixar o dinheiro sair da receita do mes em silencio.
    """
    conhecidos = ",".join("?" * len(COMPONENTE_DO_TIPO))
    tabela = banco.df(
        f"""SELECT id, data, mes_competencia, descricao, tipo_movimento,
                   natureza, valor
              FROM investimentos_movimentos
             WHERE (natureza IS NULL
                    AND COALESCE(tipo_movimento, '') NOT IN ({conhecidos}))
                OR id IN (SELECT m.id
                            FROM investimentos_movimentos m
                            LEFT JOIN lancamentos l
                                   ON l.id_unico = ? || m.id_unico
                           WHERE m.natureza IN ('entrada_externa',
                                                'saida_externa')
                             AND l.id IS NULL)
             ORDER BY data DESC, id DESC""",
        (*COMPONENTE_DO_TIPO, PREFIXO_ESPELHO),
    )
    if not tabela.empty:
        tabela["motivo"] = [
            "o lançamento foi apagado" if n else "nunca classificado"
            for n in tabela["natureza"]
        ]
    return tabela


# Prefixo do `id_unico` do lancamento-espelho. Serve para duas coisas: nao
# colidir com nenhuma linha vinda de extrato ou fatura, e permitir achar o
# espelho de um movimento sem guardar um ponteiro para ele.
PREFIXO_ESPELHO = "corretora:"

# De onde o lancamento-espelho diz que veio. Nao pode ser "Manual": Manual
# quer dizer "voce digitou", e este veio de arquivo. O campo `origem` existe
# justamente para voce saber de onde o numero saiu; mentir nele e barato de
# fazer e caro de descobrir.
ORIGEM_ESPELHO = "Corretora"


def conta_da_corretora() -> int | None:
    """O id da conta de investimentos, para o lancamento-espelho morar nela."""
    linha = banco.consultar_um(
        "SELECT id FROM contas WHERE nome = 'Conta Investimentos XP'")
    return int(linha["id"]) if linha else None


def espelho_de(movimento) -> str:
    """O `id_unico` do lancamento que espelha este movimento da corretora."""
    return PREFIXO_ESPELHO + str(movimento["id_unico"])


def natureza_da_categoria(categoria: str) -> str:
    """A natureza que uma categoria implica. Levanta se ela nao existir.

    Existe separada para poder ser chamada ANTES de qualquer gravacao. Ver a
    nota sobre validar tudo antes de gravar, em `triar`.
    """
    linha = banco.consultar_um(
        "SELECT natureza_padrao FROM categorias WHERE nome = ?", (categoria,))
    if not linha:
        raise ValueError(f"categoria desconhecida: {categoria!r}")
    return str(linha["natureza_padrao"])


def _sincronizar_espelho(movimento, natureza: str, categoria: str | None) -> None:
    """Cria, atualiza ou apaga o lancamento que espelha o movimento.

    POR QUE ISTO PRECISOU EXISTIR
    -----------------------------
    Ele perguntou: "como os 5k que entraram foi receita extra, por que nao
    entra para os lancamentos?" Nao havia resposta boa. `lancamentos` so
    nascia de extrato da conta corrente ou de fatura, e esse dinheiro entrou
    direto na corretora — nenhum leitor jamais o viu.

    O efeito era visivel em setembro/2026: uma despesa de R$ ···· paga com
    esse dinheiro contava, e a receita de R$ ···· que a pagou nao existia
    em lugar nenhum. O mes parecia cinco mil pior do que foi.

    TRANSFERENCIA INTERNA NAO GERA ESPELHO
    --------------------------------------
    E a regra que evita contar o mesmo dinheiro duas vezes. Quando o dinheiro
    anda entre as SUAS contas, a outra ponta ja esta no extrato da conta
    corrente — os R$ ···· que ele tirou da corretora ja estao la como
    `Transferencia`. Criar um espelho aqui somaria a mesma quantia de novo.

    E se voce mudar de ideia e retriar como interna, o espelho tem de SUMIR,
    nao ficar orfao. Por isso esta funcao apaga tambem, e nao so cria.

    A NATUREZA VEM DA CATEGORIA, como em todo o resto do app: voce configura
    "Indenizacao e Receita Extraordinaria" uma vez, em Configuracoes, e tudo
    que aponta para essa categoria herda. Ver `regras.classificar_fatura`.
    """
    chave = espelho_de(movimento)

    if natureza == "interna" or not categoria:
        banco.executar("DELETE FROM lancamentos WHERE id_unico = ?", (chave,))
        return

    banco.executar(
        """INSERT INTO lancamentos
             (id_unico, data, mes_competencia, descricao, valor,
              categoria, tipo, natureza, origem, conta_id, observacao,
              criado_em, atualizado_em)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))
           ON CONFLICT(id_unico) DO UPDATE SET
             categoria = excluded.categoria,
             natureza = excluded.natureza,
             atualizado_em = datetime('now')""",
        (chave,
         movimento["data"],
         movimento["mes_competencia"],
         movimento["descricao"],
         float(movimento["valor"]),
         categoria,
         config.TIPO_VARIAVEL,
         natureza_da_categoria(categoria),
         ORIGEM_ESPELHO,
         conta_da_corretora(),
         "Entrou direto na corretora, sem passar pela conta corrente."))


def triar(movimento_id: int, natureza: str,
          categoria: str | None = None) -> None:
    """Grava a sua resposta para um movimento que o app nao soube classificar.

    `categoria` so faz sentido para dinheiro que cruzou a fronteira do
    patrimonio (entrada ou saida externa): e ela que decide em que ficha do
    imposto o valor cai, e por isso e sua, nao do app. Transferencia interna
    nao leva categoria porque nao vira lancamento nenhum.
    """
    # VALIDA TUDO ANTES DE GRAVAR QUALQUER COISA.
    #
    # A primeira versao gravava a natureza e so depois olhava a categoria. Com
    # uma categoria invalida, o erro subia DEPOIS de o movimento ja ter saido
    # da fila de triagem: ele sumia da tela como se tivesse sido resolvido, e
    # sem lancamento nenhum do outro lado. Meia triagem gravada e pior que
    # nenhuma, porque parece que deu certo.
    if natureza not in NATUREZAS:
        raise ValueError(f"natureza desconhecida: {natureza!r}")

    movimento = banco.consultar_um(
        "SELECT * FROM investimentos_movimentos WHERE id = ?",
        (int(movimento_id),))
    if not movimento:
        raise ValueError(f"movimento inexistente: {movimento_id}")

    esperado = SINAL_ESPERADO.get(natureza)
    valor = float(movimento["valor"] or 0)
    if esperado and valor and (valor > 0) != (esperado > 0):
        sentido = "entrou" if valor > 0 else "saiu"
        raise ValueError(
            f"o extrato diz que esse dinheiro {sentido} "
            f"(R$ {valor:,.2f}), e a resposta diz o contrário "
            f"— «{NATUREZAS[natureza]}»")

    if natureza != "interna" and categoria:
        natureza_da_categoria(categoria)   # levanta antes de gravar

    banco.executar(
        "UPDATE investimentos_movimentos SET natureza = ? WHERE id = ?",
        (natureza, int(movimento_id)))
    _sincronizar_espelho(movimento, natureza, categoria)


def ler_triagem(linhas) -> tuple[list[tuple], list[str], list[str]]:
    """Le o que voce preencheu na tabela de triagem e separa em tres montes.

    Devolve `(respondidos, sem_categoria, incompativel)`:

        respondidos    (id, natureza, categoria) prontos para `triar`
        sem_categoria  entrou ou saiu de fora, mas ficou sem categoria
        incompativel   categoria que nao serve para aquele sentido

    POR QUE ISTO NAO MORA NA TELA
    -----------------------------
    Estava em `paginas/investimentos.py`, dentro do `if st.button(...)`. Logica
    ali dentro nao tem como ser conferida: nenhum script consegue apertar o
    botao, entao os casos de borda — categoria vazia, categoria de despesa
    escolhida para uma entrada, interna com categoria preenchida — so seriam
    descobertos por voce, usando.

    O NOME DA COLUNA E O CONTRATO. `linhas` vem do `st.data_editor` ja
    renomeado, entao as chaves sao as que aparecem na tela. Mudar um rotulo
    la sem mudar aqui quebra — e a checagem 12 e o que faz isso aparecer.
    """
    respondidos: list[tuple] = []
    sem_categoria: list[str] = []
    incompativel: list[str] = []

    rotulos = {v: k for k, v in NATUREZAS.items()}

    for _, linha in linhas.iterrows():
        natureza = rotulos.get(linha.get("O que foi isto?"))
        if not natureza:
            continue

        # O sinal do extrato manda. `triar` recusa a contradicao de qualquer
        # jeito, lendo o banco; aqui e so para a tela conseguir explicar em vez
        # de estourar uma excecao na cara de quem clicou.
        esperado = SINAL_ESPERADO.get(natureza)
        valor = linha.get("Valor")
        try:
            valor = float(valor)
        except (TypeError, ValueError):
            valor = 0.0
        if esperado and valor and (valor > 0) != (esperado > 0):
            incompativel.append(
                f"«{linha.get('Lançamento')}» {'entrou' if valor > 0 else 'saiu'} "
                f"pelo extrato, e a resposta diz o contrário")
            continue

        escolhida = linha.get("Categoria")
        categoria = (str(escolhida).strip()
                     if escolhida and str(escolhida).strip()
                     and str(escolhida).strip().lower() != "nan"
                     else None)

        if natureza == "interna":
            # Interna nao vira lancamento. Categoria escolhida aqui seria
            # ignorada em silencio — melhor devolver limpa, para quem chama
            # nao achar que ela foi usada.
            respondidos.append((int(linha["id"]), natureza, None))
        elif not categoria:
            sem_categoria.append(str(linha.get("Lançamento") or linha["id"]))
        elif categoria not in categorias_para(natureza):
            incompativel.append(
                f"«{categoria}» não serve para {NATUREZAS[natureza]}")
        else:
            respondidos.append((int(linha["id"]), natureza, categoria))

    return respondidos, sem_categoria, incompativel


def categorias_para(natureza: str) -> list[str]:
    """As categorias que fazem sentido para uma entrada ou saida externa.

    Entrada externa so pode receber categoria de receita, e saida so de
    despesa. Deixar a lista inteira aberta convidaria a marcar um dinheiro que
    entrou como "Alimentacao" — e o app aceitaria calado.
    """
    naturezas = (config.NATUREZAS_RECEITA if natureza == "entrada_externa"
                 else config.NATUREZAS_DESPESA)
    marcadores = ",".join("?" * len(naturezas))
    return [linha["nome"] for linha in banco.consultar(
        f"""SELECT nome FROM categorias
             WHERE ativa = 1 AND natureza_padrao IN ({marcadores})
             ORDER BY nome""", tuple(naturezas))]


def _movimentos(mes: str | None = None) -> pd.DataFrame:
    """Os movimentos da corretora, ate o mes pedido (ou todos)."""
    if mes:
        return banco.df(
            "SELECT * FROM investimentos_movimentos WHERE mes_competencia <= ?",
            (mes,))
    return banco.df("SELECT * FROM investimentos_movimentos")


def somar(tabela: pd.DataFrame) -> dict[str, float]:
    """Soma uma tabela de movimentos em cada componente da equacao.

    Separada de `por_componente` porque esta funcao e PURA: entra um
    DataFrame, sai um dicionario, sem tocar no banco. E o que torna possivel
    `conferir_fechamento.py` provar as regras com movimentos inventados —
    inclusive os casos que o banco real nao tem, como uma saida externa ou um
    movimento triado. Um teste que so consegue olhar os dados de verdade so
    descobre os erros que ja aconteceram.

    `entradas` vem positiva e `saidas` positiva tambem (o sinal esta no nome,
    nao no numero) — assim a equacao se le como se fala: "entrou X, saiu Y".
    """
    somas = {c: 0.0 for c in COMPONENTES}
    somas["interna"] = 0.0

    if tabela.empty:
        return somas

    for _, movimento in tabela.iterrows():
        valor = float(movimento.get("valor") or 0)
        componente = componente_de(movimento)

        if componente is None:
            somas["nao_explicado"] += valor
        elif componente == "entradas":
            somas["entradas"] += valor
        elif componente == "saidas":
            somas["saidas"] += -valor
        elif componente == "rendimento":
            somas["rendimento"] += valor
        elif componente == "custo":
            somas["custos"] += -valor
        elif componente == "interna":
            somas["interna"] += valor

    return somas


def por_componente(mes: str | None = None) -> dict[str, float]:
    """Os componentes da equacao para os movimentos da corretora ate `mes`.

    Antes de somar, esquece a resposta de quem perdeu o lancamento. Sem isso a
    equacao contaria como `entradas` um dinheiro que a tela ja voltou a
    perguntar — dois lugares do app dando respostas diferentes sobre a mesma
    quantia, que e a familia de bug que este modulo existe para acabar.
    """
    tabela = _movimentos(mes)
    orfaos = set(_sem_espelho())
    if orfaos and not tabela.empty:
        tabela = tabela.copy()
        tabela.loc[tabela["id"].isin(orfaos), "natureza"] = None
    return somar(tabela)
