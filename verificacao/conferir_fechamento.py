"""
conferir_fechamento.py — prova que o caixa fecha, ou que o app avisa.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Ele descreveu como o dinheiro dele realmente anda — conta corrente, conta de
investimentos, conta global — e fez um pedido que e uma exigencia de projeto:

    "nao pode haver dinheiro sumindo no meio do caminho"

O app nao atendia. `conciliar()` fazia

    diferenca = carteira - aportado - abertura      # e chamava de rendimento

Toda sobra virava rendimento, porque nao havia outra gaveta. Funcionou
enquanto so existissem dois caminhos para o dinheiro cruzar a fronteira. Ate
o dia em que entrou por um terceiro:

    2026-09-02   TED - RECEBIMENTO EXTERNO   +R$ ····

Dinheiro chegando de fora DIRETO na corretora. Nao e aporte
(nao saiu da conta corrente) nem rendimento (nao foi a carteira que produziu).
Virou lucro de investimento em silencio.

OS DOIS ERROS SAO DE FAMILIAS DIFERENTES
----------------------------------------
Investigando, apareceram dois, e vale nao confundi-los:

1. A SOBRA VIRANDO RENDIMENTO. Falta de gaveta. Resolvido com o componente
   `nao_explicado`, que e calculado por diferenca e EXIBIDO, nunca absorvido.

2. OS DOIS LADOS DA BALANCA EM MESES DIFERENTES. `posicao()` devolvia a
   carteira ate o ultimo saldo cadastrado (2026-08) e o fluxo somava ate onde
   houvesse extrato (2026-09). Os dois medidores de rendimento discordavam em
   R$ ···· — exatamente o fluxo liquido de setembro. Nao era erro de
   conta em nenhum dos dois: era um mes a mais de um lado da balanca.

O segundo passava despercebido porque o numero errado era plausivel. E o tipo
de defeito que so uma checagem automatica pega, e a checagem 6 e ela.

O QUE ELE CONFERE
------------------
1. O TIPO MANDA             `natureza` so responde pelo que o tipo nao explica
2. SEM RESPOSTA, APARECE    nao classificado vai inteiro para a sobra
3. TRIADO, SAI DA SOBRA     e entra no componente que voce escolheu
4. INTERNA SOMA ZERO        transferencia entre contas suas nao move o total
5. COMPRA NAO E FLUXO       comprar so troca a forma do dinheiro
6. OS DOIS MEDIDORES BATEM  diferenca == rendimento_apurado, ao centavo
7. O CASO REAL DELE         os R$ ···· estao na fila, nao no rendimento
8. RESPOSTA INVALIDA NAO GRAVA
9. O ESPELHO                que cruzou a fronteira vira lancamento; interna nao
10. CATEGORIA COMBINA       entrada so recebe receita, saida so despesa
11. INDENIZACAO E ISENTA    cai na ficha certa da declaracao
12. A TABELA LIDA COMO A TELA LE   os casos de borda do botao
13. O SINAL DO EXTRATO MANDA      resposta que contradiz a direcao e recusada
14. LANCAMENTO APAGADO            devolve o movimento para a fila, com motivo

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_fechamento
"""

from __future__ import annotations


import pandas as pd

from financas import banco, config
from financas.calculos import fechamento, imposto
from financas.calculos import investimentos as inv
from verificacao.base import Conferencia, banco_descartavel


def movimentos(*linhas) -> pd.DataFrame:
    """Movimentos de mentira, cada um como (tipo, natureza, valor)."""
    return pd.DataFrame(
        [{"tipo_movimento": t, "natureza": n, "valor": v}
         for t, n, v in linhas])


def conferir_tipo_manda(c: Conferencia) -> None:
    """`natureza` so e consultada para o que o tipo nao explica.

    A ordem importa de verdade. Se `natureza` fosse lida primeiro, uma
    resposta antiga de triagem passaria por cima de uma regra nova — o mesmo
    erro de guardar aquilo que se deriva, so que com efeito retroativo.
    """
    print("=" * 78)
    print("1. O TIPO MANDA, A NATUREZA SO RESPONDE PELO RESTO")
    print("=" * 78)

    casos = [
        ({"tipo_movimento": "aporte", "natureza": None}, "interna"),
        ({"tipo_movimento": "juros", "natureza": None}, "rendimento"),
        ({"tipo_movimento": "taxa", "natureza": None}, "custo"),
        ({"tipo_movimento": "compra", "natureza": None}, "nenhum"),
        # o caso que trava a ordem: tipo conhecido + natureza contraditoria
        ({"tipo_movimento": "aporte", "natureza": "entrada_externa"}, "interna"),
        ({"tipo_movimento": "outro", "natureza": "entrada_externa"}, "entradas"),
        ({"tipo_movimento": "outro", "natureza": None}, None),
        ({"tipo_movimento": None, "natureza": None}, None),
    ]
    for movimento, esperado in casos:
        obtido = fechamento.componente_de(movimento)
        c.exigir(obtido == esperado,
                 f"{movimento} deveria dar «{esperado}», deu «{obtido}»")
        print(f"  tipo={str(movimento['tipo_movimento']):<11} "
              f"natureza={str(movimento['natureza']):<16} -> {obtido}")


def conferir_sobra_aparece(c: Conferencia) -> None:
    """Movimento sem classificacao vai INTEIRO para `nao_explicado`."""
    print()
    print("=" * 78)
    print("2. SEM RESPOSTA, O DINHEIRO APARECE NA SOBRA")
    print("=" * 78)

    somas = fechamento.somar(movimentos(("outro", None, 5064.80)))
    c.exigir(abs(somas["nao_explicado"] - 5064.80) < 0.01,
             f"nao_explicado deveria ser 5064.80, veio {somas['nao_explicado']}")
    c.exigir(abs(somas["rendimento"]) < 0.01,
             "movimento nao classificado nao pode virar rendimento — veio "
             f"{somas['rendimento']}")
    c.exigir(abs(somas["entradas"]) < 0.01,
             "nem pode ser adivinhado como entrada")
    print(f"  nao explicado R$ {somas['nao_explicado']:,.2f}, "
          f"rendimento R$ {somas['rendimento']:,.2f}")


def conferir_triado_sai_da_sobra(c: Conferencia) -> None:
    """Depois de respondido, o valor migra da sobra para o componente certo."""
    print()
    print("=" * 78)
    print("3. RESPONDIDO, SAI DA SOBRA E ENTRA NO LUGAR")
    print("=" * 78)

    for natureza, componente, sinal in (
            ("entrada_externa", "entradas", 1),
            ("saida_externa", "saidas", -1),
            ("interna", "interna", 1)):
        somas = fechamento.somar(
            movimentos(("outro", natureza, sinal * 5064.80)))
        c.exigir(abs(somas["nao_explicado"]) < 0.01,
                 f"triado como {natureza}, nao podia sobrar em nao_explicado")
        c.exigir(abs(abs(somas[componente]) - 5064.80) < 0.01,
                 f"{natureza} deveria somar 5064.80 em {componente}, veio "
                 f"{somas[componente]}")
        print(f"  {natureza:<16} -> {componente:<10} "
              f"R$ {somas[componente]:,.2f}")


def conferir_interna_soma_zero(c: Conferencia) -> None:
    """As duas pontas de uma transferencia entre contas suas se cancelam.

    E esta a checagem que pega "dinheiro sumindo entre duas contas": se sair
    de uma e nao entrar na outra, a soma deixa de ser zero.
    """
    print()
    print("=" * 78)
    print("4. TRANSFERENCIA ENTRE AS SUAS CONTAS SOMA ZERO")
    print("=" * 78)

    somas = fechamento.somar(movimentos(
        ("aporte", None, 10_000.00),      # saiu da corrente, entrou na corretora
        ("resgate", None, -10_000.00),    # e voltou
        ("outro", "interna", 2_500.00),
        ("outro", "interna", -2_500.00),
    ))
    c.exigir(abs(somas["interna"]) < 0.01,
             f"interna deveria fechar em zero, veio {somas['interna']}")
    c.exigir(abs(somas["nao_explicado"]) < 0.01, "nada podia sobrar aqui")
    print(f"  4 travessias, saldo interno R$ {somas['interna']:,.2f}")

    # E o contraste que da valor a checagem acima: uma ponta sem a outra TEM
    # de deixar resto. Sem isto, um `somar()` que devolvesse zero para tudo
    # passaria na checagem anterior sem fazer nada.
    torto = fechamento.somar(movimentos(("aporte", None, 10_000.00)))
    c.exigir(abs(torto["interna"] - 10_000.00) < 0.01,
             "uma ponta sozinha tem de deixar resto — senao a checagem acima "
             "nao prova nada")
    print(f"  1 ponta sozinha, saldo interno R$ {torto['interna']:,.2f} "
          f"(tem de sobrar mesmo)")


def conferir_compra_nao_e_fluxo(c: Conferencia) -> None:
    """Comprar um papel nao move dinheiro para dentro nem para fora."""
    print()
    print("=" * 78)
    print("5. COMPRAR SO TROCA A FORMA DO DINHEIRO")
    print("=" * 78)

    somas = fechamento.somar(movimentos(
        ("compra", None, -50_000.00),
        ("venda", None, 30_000.00),
    ))
    total = sum(somas[k] for k in fechamento.COMPONENTES) + somas["interna"]
    c.exigir(abs(total) < 0.01,
             f"compra e venda nao podem mover componente nenhum, moveu {total}")
    print(f"  R$ 80 mil operados, R$ {total:,.2f} de efeito na equação")


def conferir_medidores_batem(c: Conferencia) -> None:
    """Os dois jeitos de medir rendimento tem de dar o MESMO numero.

    Um vem de cima (carteira - aportado - abertura), o outro de baixo (soma do
    rendimento de cada papel, mes a mes). Sao caminhos independentes; quando
    discordam, um dos dois esta errado — e ate aqui era o de cima, por comparar
    patrimonio de agosto com transferencia de setembro.
    """
    print()
    print("=" * 78)
    print("6. OS DOIS MEDIDORES DE RENDIMENTO BATEM")
    print("=" * 78)

    # 2026-09 e 2026-12 estao aqui de proposito: sao meses DEPOIS do ultimo
    # saldo cadastrado. Pedir um mes que a carteira ainda nao alcanca nao pode
    # trazer o fluxo desse mes contra o patrimonio do mes anterior — e esse e
    # o caminho vivo, porque o Dashboard passa o mes corrente.
    for mes in (None, "2026-08", "2026-09", "2026-12", "2026-06", "2025-12"):
        conta = inv.conciliar(mes)
        distancia = abs(conta["diferenca"] - conta["rendimento_apurado"])
        c.exigir(distancia < 1.0,
                 f"em {mes or 'hoje'}: diferenca {conta['diferenca']:.2f} != "
                 f"rendimento apurado {conta['rendimento_apurado']:.2f} "
                 f"(distancia {distancia:.2f})")
        print(f"  {str(mes or 'hoje'):<9} ponta a ponta R$ "
              f"{conta['diferenca']:>12,.2f} = mes a mes R$ "
              f"{conta['rendimento_apurado']:>12,.2f}  "
              f"(foto de {conta['mes_referencia']})")

    # E o alinhamento tem de estar dito, nao acontecer por sorte.
    hoje = inv.conciliar(None)
    c.exigir(bool(hoje.get("mes_referencia")),
             "conciliar() tem de dizer de que mes e a foto que usou")
    futuro = inv.conciliar("2027-12")
    c.exigir(futuro["mes_referencia"] == hoje["mes_referencia"],
             f"pedir um mes futuro nao pode inventar uma foto mais nova: "
             f"veio {futuro['mes_referencia']}")
    print(f"  pedir 2027-12 usa a mesma foto de "
          f"{futuro['mes_referencia']} — nao inventa carteira")


def um_movimento_a_explicar():
    """Um movimento `outro` do banco, ou None. Usado por varias checagens.

    Procura pelo TIPO, nao pela descricao. A primeira versao procurava um
    texto especifico do extrato dele — o que amarrava a checagem a uma linha
    que so existe no banco de uma pessoa, e vazava o teor dela para quem
    lesse o codigo. `outro` e o balde do que o app nao soube classificar, que
    e exatamente o assunto destas checagens.
    """
    return banco.consultar_um(
        """SELECT * FROM investimentos_movimentos
            WHERE tipo_movimento = 'outro'
            ORDER BY ABS(valor) DESC LIMIT 1""")


def repor_na_fila(movimento) -> None:
    """Devolve um movimento ao estado "ainda nao classificado".

    POR QUE ISTO PRECISOU EXISTIR (2026-09-03). As checagens que usam o caso
    real liam o banco supondo que o movimento ainda estava na fila. No minuto
    em que ele triou de verdade — que e o app funcionando —, uma checagem
    FALHOU e outra passou sem provar nada:

        x antes de triar nao pode existir lancamento espelho
          "a fila esta vazia — tudo ja triado"

    Um teste que so passa enquanto o recurso nao foi usado nao protege nada.
    Agora cada checagem MONTA o estado de que precisa, dentro da copia
    descartavel, em vez de torcer para encontra-lo.
    """
    banco.executar(
        "UPDATE investimentos_movimentos SET natureza = NULL WHERE id = ?",
        (int(movimento["id"]),))
    banco.executar("DELETE FROM lancamentos WHERE id_unico = ?",
                   (fechamento.espelho_de(movimento),))


def conferir_caso_real(c: Conferencia) -> None:
    """O movimento que o app nao soube explicar: na fila, fora do rendimento.

    Escrita sobre o movimento de verdade de proposito — o valor exato saiu do
    extrato dele. Se um dia alguem "arrumar" o app de um jeito que engula essa
    quantia de novo, e aqui que vai aparecer.

    Roda em copia, e repoe o movimento na fila antes de olhar: o que se quer
    provar e o COMPORTAMENTO, nao o estado em que o banco por acaso esta.
    """
    print()
    print("=" * 78)
    print("7. O CASO QUE MOTIVOU TUDO ISTO")
    print("=" * 78)

    with banco_descartavel("conferir_fechamento"):
        movimento = um_movimento_a_explicar()
        if not movimento:
            c.exigir(True, "")
            print("  nenhum movimento `outro` neste banco — sem efeito")
            return

        repor_na_fila(movimento)
        esperado = abs(float(movimento["valor"]))

        fila = fechamento.movimentos_a_triar()
        na_fila = fila[fila["id"] == movimento["id"]]
        c.exigir(not na_fila.empty,
                 "reposto na fila, o movimento tinha de aparecer nela")
        if na_fila.empty:
            return

        valor = float(na_fila["valor"].iloc[0])
        conta = inv.conciliar(None)
        # Exige a PROPRIEDADE, nao um numero fixo: o valor que entra na fila e
        # o mesmo que sai do extrato, e e o mesmo que a tela mostra pendente.
        # Cravar a quantia amarraria a checagem ao extrato de uma pessoa.
        c.exigir(abs(valor - esperado) < 0.01,
                 f"o valor na fila mudou: extrato {esperado:.2f}, fila "
                 f"{valor:.2f}")
        c.exigir(conta["n_a_triar"] >= 1,
                 "conciliar() tem de contar a pendencia para a tela avisar")
        c.exigir(conta["situacao"] == "há dinheiro sem explicação",
                 f"com pendencia na fila a situacao tem de dizer isso, veio "
                 f"«{conta['situacao']}»")
        c.exigir(abs(conta["valor_a_triar"] - esperado) < 0.01,
                 f"o valor pendente na tela ({conta['valor_a_triar']:.2f}) tem "
                 f"de ser o do extrato ({esperado:.2f})")
        print(f"  movimento `outro` de R$ {valor:,.2f} está na fila")
        print(f"  situação da carteira: «{conta['situacao']}»")

        # E depois de classificado, a situacao TEM de mudar — senao o aviso
        # ficaria aceso para sempre e viraria ruido.
        fechamento.triar(int(movimento["id"]), "entrada_externa", "Indenização")
        depois = inv.conciliar(None)
        c.exigir(depois["n_a_triar"] == 0,
                 "classificado, a pendencia tinha de sumir")
        c.exigir(depois["situacao"] != "há dinheiro sem explicação",
                 f"classificado, a situacao nao pode continuar acusando: "
                 f"«{depois['situacao']}»")
        print(f"  classificado -> situação «{depois['situacao']}», "
              f"0 pendências")


def conferir_espelho(c: Conferencia) -> None:
    """Dinheiro que cruzou a fronteira vira lancamento; o que so andou, nao.

    Ele perguntou: "como os 5k que entraram foi receita extra, por que nao
    entra para os lancamentos?". Estas checagens sao a resposta virando regra.

    Roda num banco DESCARTAVEL: `triar()` grava, e uma checagem que suja o
    banco de verdade e uma checagem que ninguem roda duas vezes.
    """
    print()
    print("=" * 78)
    print("9. O QUE CRUZOU A FRONTEIRA VIRA LANCAMENTO")
    print("=" * 78)

    with banco_descartavel("conferir_fechamento"):
        movimento = um_movimento_a_explicar()
        if not movimento:
            c.exigir(True, "")
            print("  nenhum movimento `outro` neste banco — sem efeito")
            return

        repor_na_fila(movimento)
        chave = fechamento.espelho_de(movimento)

        def espelho():
            return banco.consultar_um(
                "SELECT * FROM lancamentos WHERE id_unico = ?", (chave,))

        c.exigir(espelho() is None,
                 "antes de triar nao pode existir lancamento espelho")

        # 1. entrada externa vira lancamento, com a natureza VINDA da categoria
        fechamento.triar(int(movimento["id"]), "entrada_externa", "Indenização")
        linha = espelho()
        c.exigir(linha is not None, "entrada externa tinha de virar lancamento")
        if linha:
            c.exigir(abs(float(linha["valor"]) - 5064.80) < 0.01,
                     f"valor do espelho errado: {linha['valor']}")
            c.exigir(linha["natureza"] == "Receita Extraordinária",
                     f"a natureza tem de vir da categoria, veio "
                     f"«{linha['natureza']}»")
            c.exigir(linha["origem"] == fechamento.ORIGEM_ESPELHO,
                     f"origem tem de dizer que veio da corretora, e nao "
                     f"«Manual»; veio «{linha['origem']}»")
            print(f"  entrada externa -> lançamento R$ {linha['valor']:,.2f} "
                  f"· {linha['categoria']} · {linha['natureza']}")

        # 2. triar de novo nao pode duplicar
        fechamento.triar(int(movimento["id"]), "entrada_externa", "Indenização")
        quantos = banco.consultar_um(
            "SELECT COUNT(*) n FROM lancamentos WHERE id_unico = ?", (chave,))
        c.exigir(int(quantos["n"]) == 1,
                 f"triar duas vezes criou {quantos['n']} lancamentos")
        print(f"  triado duas vezes -> {quantos['n']} lançamento (não duplica)")

        # 3. mudar de ideia troca a categoria, sem criar outra linha
        fechamento.triar(int(movimento["id"]), "entrada_externa",
                         "Outras Receitas")
        linha = espelho()
        c.exigir(linha and linha["categoria"] == "Outras Receitas",
                 "retriar tinha de atualizar a categoria")
        print(f"  retriado -> categoria agora «{linha['categoria']}»")

        # 4. E O QUE MAIS IMPORTA: interna NAO gera lancamento, e apaga o que
        #    existia. A outra ponta ja esta no extrato da conta corrente —
        #    somar aqui contaria o mesmo dinheiro duas vezes.
        fechamento.triar(int(movimento["id"]), "interna")
        c.exigir(espelho() is None,
                 "transferencia interna nao pode deixar lancamento — seria "
                 "contar o mesmo dinheiro duas vezes")
        print("  retriado como interna -> lançamento apagado (não conta 2x)")

        # 5. CATEGORIA QUE NAO EXISTE NAO GRAVA *NADA*.
        #    Nao basta levantar o erro: a primeira versao gravava a natureza e
        #    so depois olhava a categoria, entao o movimento saia da fila de
        #    triagem — parecia resolvido — sem lancamento nenhum do outro lado.
        #    Meia triagem gravada e pior que nenhuma. Por isso a checagem olha
        #    o ESTADO depois do erro, e nao so o erro.
        antes = banco.consultar_um(
            "SELECT natureza FROM investimentos_movimentos WHERE id = ?",
            (int(movimento["id"]),))["natureza"]
        try:
            fechamento.triar(int(movimento["id"]), "entrada_externa",
                             "Categoria Que Nao Existe")
            c.exigir(False, "triar aceitou uma categoria inventada")
        except ValueError as erro:
            c.exigir(True, "")
            print(f"  recusou categoria inventada: {erro}")

        depois = banco.consultar_um(
            "SELECT natureza FROM investimentos_movimentos WHERE id = ?",
            (int(movimento["id"]),))["natureza"]
        c.exigir(depois == antes,
                 f"triar que falhou nao pode deixar meia gravacao: natureza "
                 f"era {antes!r} e virou {depois!r}")
        c.exigir(espelho() is None,
                 "triar que falhou nao pode ter criado lancamento")
        print(f"  e não gravou nada: natureza segue {depois!r}")


def conferir_categorias_por_sentido(c: Conferencia) -> None:
    """Entrada externa so oferece receita; saida so oferece despesa."""
    print()
    print("=" * 78)
    print("10. A CATEGORIA TEM DE COMBINAR COM O SENTIDO DO DINHEIRO")
    print("=" * 78)

    entrada = fechamento.categorias_para("entrada_externa")
    saida = fechamento.categorias_para("saida_externa")

    c.exigir("Indenização" in entrada,
             "Indenizacao tem de estar entre as categorias de entrada")
    c.exigir("Indenização" not in saida,
             "Indenizacao nao e despesa")
    c.exigir(not (set(entrada) & set(saida)),
             f"nenhuma categoria pode servir aos dois sentidos: "
             f"{sorted(set(entrada) & set(saida))}")
    print(f"  entrada: {len(entrada)} categorias · saída: {len(saida)} · "
          f"nenhuma nas duas")


def conferir_ficha_do_imposto(c: Conferencia) -> None:
    """Indenizacao entra na declaracao como ISENTA, nao como tributavel.

    Ele disse que aquela receita nao era tributavel. Se a categoria caisse
    na ficha de tributaveis, o app faria ele pagar imposto sobre dinheiro
    isento — erro que so aparece depois da declaracao entregue.
    """
    print()
    print("=" * 78)
    print("11. INDENIZACAO NAO PAGA IMPOSTO")
    print("=" * 78)

    destino = imposto.DESTINO_DA_RECEITA.get("Indenização")
    c.exigir(destino is not None,
             "Indenizacao precisa de ficha propria; sem ela cai em triagem")
    if destino:
        c.exigir(destino["ficha"] == imposto.FICHA_ISENTA,
                 f"ficha errada: {destino['ficha']}")
        c.exigir("tributável" in destino["nota"],
                 "a nota tem de avisar que verba salarial da mesma origem "
                 "E tributavel — senao o nome vira isencao automatica")
        print(f"  ficha: {destino['ficha']}")


def conferir_sinal(c: Conferencia) -> None:
    """A resposta nao pode contradizer a direcao que o extrato mostra.

    Marcar a entrada de +R$ ···· como "saiu para fora" produzia uma despesa de
    valor POSITIVO — linha incoerente, que soma no mes em vez de subtrair.
    Da para "consertar" invertendo o sinal sozinho, mas ai o app inventaria uma
    despesa de cinco mil que nunca existiu. Quem sabe a direcao e o extrato.
    """
    print()
    print("=" * 78)
    print("13. O SINAL DO EXTRATO MANDA")
    print("=" * 78)

    with banco_descartavel("conferir_fechamento"):
        movimento = um_movimento_a_explicar()
        if not movimento:
            c.exigir(True, "")
            print("  sem o movimento neste banco — sem efeito")
            return

        repor_na_fila(movimento)
        mov_id = int(movimento["id"])
        antes = None   # reposto na fila, entao sem natureza gravada
        # A categoria sai do BANCO, nao de um nome escrito aqui. "Servicos"
        # e "Alimentacao" existem no banco dele e nao no de demonstracao — e a
        # checagem reprovava por isso, num defeito que era do teste.
        uma_despesa = fechamento.categorias_para("saida_externa")[0]
        uma_receita = fechamento.categorias_para("entrada_externa")[0]

        try:
            fechamento.triar(mov_id, "saida_externa", uma_despesa)
            c.exigir(False, "uma entrada nao podia virar saida")
        except ValueError as erro:
            c.exigir(True, "")
            print(f"  recusou: {erro}")

        depois = banco.consultar_um(
            "SELECT natureza FROM investimentos_movimentos WHERE id = ?",
            (mov_id,))["natureza"]
        c.exigir(depois == antes,
                 f"a recusa nao pode deixar meia gravacao: {antes!r} -> "
                 f"{depois!r}")

        # E a saida LEGITIMA, com valor negativo, tem de funcionar — senao a
        # trava acima teria virado uma proibicao geral.
        banco.executar(
            """INSERT INTO investimentos_movimentos
                 (id_unico, data, mes_competencia, descricao, valor,
                  tipo_movimento)
               VALUES ('saida-teste','2026-09-02','2026-09','PAGAMENTO',
                       -1200.00,'outro')""")
        saida_id = int(banco.consultar_um(
            "SELECT id FROM investimentos_movimentos "
            "WHERE id_unico='saida-teste'")["id"])
        fechamento.triar(saida_id, "saida_externa", uma_despesa)
        espelho = banco.consultar_um(
            "SELECT valor, natureza FROM lancamentos "
            "WHERE id_unico='corretora:saida-teste'")
        c.exigir(espelho is not None, "saida legitima tinha de virar lancamento")
        if espelho:
            c.exigir(float(espelho["valor"]) < 0,
                     f"despesa tem de ter valor negativo, veio "
                     f"{espelho['valor']}")
            c.exigir(espelho["natureza"] == "Despesa",
                     f"natureza errada: {espelho['natureza']}")
            print(f"  saída legítima (−1.200,00) -> lançamento "
                  f"R$ {espelho['valor']:,.2f} · {espelho['natureza']}")


def conferir_espelho_apagado(c: Conferencia) -> None:
    """Apagar o lancamento devolve o movimento para a fila, com o motivo.

    A tela de Lancamentos deixa apagar qualquer linha e Configuracoes deixa
    apagar todas. Sem esta regra, apagar o espelho deixava o movimento marcado
    como triado: sumia da fila, sumia da receita do mes, e NADA avisava — o
    mesmo "dinheiro sumindo no meio do caminho" que este modulo existe para
    impedir, so que criado por nos.
    """
    print()
    print("=" * 78)
    print("14. LANCAMENTO APAGADO DEVOLVE O MOVIMENTO PARA A FILA")
    print("=" * 78)

    with banco_descartavel("conferir_fechamento"):
        movimento = um_movimento_a_explicar()
        if not movimento:
            c.exigir(True, "")
            print("  sem o movimento neste banco — sem efeito")
            return

        repor_na_fila(movimento)
        mov_id = int(movimento["id"])
        chave = fechamento.espelho_de(movimento)
        fechamento.triar(mov_id, "entrada_externa", "Indenização")

        c.exigir(len(fechamento.movimentos_a_triar()) == 0,
                 "depois de triar, a fila tinha de esvaziar")
        entradas_antes = fechamento.por_componente()["entradas"]

        banco.executar("DELETE FROM lancamentos WHERE id_unico = ?", (chave,))

        fila = fechamento.movimentos_a_triar()
        componentes = fechamento.por_componente()
        c.exigir(len(fila) == 1,
                 f"apagar o lancamento tinha de devolver o movimento para a "
                 f"fila; fila tem {len(fila)}")
        if len(fila):
            c.exigir(fila.iloc[0]["motivo"] == "o lançamento foi apagado",
                     f"o motivo tem de explicar por que voltou: "
                     f"{fila.iloc[0]['motivo']!r}")
        c.exigir(abs(componentes["entradas"]) < 0.01,
                 f"sem o lancamento, nao pode continuar contando como entrada: "
                 f"{componentes['entradas']}")
        c.exigir(abs(componentes["nao_explicado"] - 5064.80) < 0.01,
                 f"o dinheiro tinha de voltar a ser «nao explicado», veio "
                 f"{componentes['nao_explicado']}")
        print(f"  entradas {entradas_antes:,.2f} -> "
              f"{componentes['entradas']:,.2f}")
        print(f"  não explicado 0,00 -> {componentes['nao_explicado']:,.2f} "
              f"· motivo «{fila.iloc[0]['motivo']}»")

        # E reclassificar resolve de novo.
        fechamento.triar(mov_id, "entrada_externa", "Indenização")
        c.exigir(len(fechamento.movimentos_a_triar()) == 0,
                 "reclassificar tinha de resolver de novo")

        # Interna nao precisa de lancamento, entao nao pode voltar para a fila.
        fechamento.triar(mov_id, "interna")
        fila = fechamento.movimentos_a_triar()
        c.exigir(fila.empty or mov_id not in list(fila["id"]),
                 "interna nao gera lancamento e por isso nao pode ser cobrada "
                 "por nao ter um")
        print("  reclassificado resolve · interna não é cobrada por espelho")


def conferir_leitura_da_tabela(c: Conferencia) -> None:
    """A tabela de triagem lida como a tela lê, com os casos de borda.

    Esta logica morava dentro do `if st.button(...)`, onde nenhum script
    alcanca. Os casos abaixo — categoria em branco, categoria do sentido
    errado, interna com categoria preenchida — so seriam descobertos por ele,
    usando. Por isso ela saiu da tela.
    """
    print()
    print("=" * 78)
    print("12. A TABELA DE TRIAGEM, LIDA COMO A TELA LE")
    print("=" * 78)

    def tabela(*linhas):
        return pd.DataFrame(
            [{"id": i, "Lançamento": desc, "O que foi isto?": nat,
              "Categoria": cat}
             for i, desc, nat, cat in linhas])

    entrada = fechamento.NATUREZAS["entrada_externa"]
    saida = fechamento.NATUREZAS["saida_externa"]
    interna = fechamento.NATUREZAS["interna"]
    # Uma categoria de despesa QUALQUER, tirada do banco em que a checagem
    # esta rodando. Escrever um nome aqui amarraria o teste a um cadastro.
    despesa_qualquer = fechamento.categorias_para("saida_externa")[0]

    respondidos, sem_cat, incomp = fechamento.ler_triagem(tabela(
        (1, "entrada de fora", entrada, "Indenização"),   # ok
        (2, "nao respondida", None, None),                # ignorada
        (3, "sem categoria", entrada, ""),                # falta categoria
        (4, "categoria errada", entrada, despesa_qualquer),  # sentido errado
        (5, "interna com cat", interna, "Indenização"),   # categoria descartada
        (6, "vazia mesmo", "", ""),                       # ignorada
    ))

    c.exigir((1, "entrada_externa", "Indenização") in respondidos,
             "a linha correta tinha de ser aceita")
    c.exigir(not any(l[0] == 2 for l in respondidos),
             "linha sem natureza nao pode ser respondida")
    c.exigir(sem_cat == ["sem categoria"],
             f"a linha 3 tinha de cair em «sem categoria», veio {sem_cat}")
    c.exigir(len(incomp) == 1 and despesa_qualquer in incomp[0],
             f"categoria de despesa numa entrada tinha de ser recusada: "
             f"{incomp}")
    c.exigir((5, "interna", None) in respondidos,
             "interna tem de vir com categoria None, nunca com a escolhida — "
             "senao a tela promete um lancamento que nao vai existir")
    c.exigir(not any(l[0] == 6 for l in respondidos),
             "linha totalmente em branco nao pode virar resposta")
    print(f"  6 linhas -> {len(respondidos)} aceitas, {len(sem_cat)} sem "
          f"categoria, {len(incomp)} incompatível")

    # O 'nan' que o pandas devolve para celula vazia nao pode virar categoria.
    so_nan = fechamento.ler_triagem(pd.DataFrame([
        {"id": 9, "Lançamento": "x", "O que foi isto?": entrada,
         "Categoria": float("nan")}]))
    c.exigir(so_nan[1] == ["x"],
             f"célula vazia vira NaN no pandas e não pode virar a categoria "
             f"«nan»; veio {so_nan}")
    print("  célula vazia (NaN) tratada como sem categoria, não como «nan»")

    # E o rotulo da coluna e contrato: se a tela renomear, isto quebra.
    vazio = fechamento.ler_triagem(pd.DataFrame([
        {"id": 1, "Lançamento": "x", "O que foi isto?": saida,
         "Categoria": despesa_qualquer}]))
    c.exigir(vazio[0] == [(1, "saida_externa", despesa_qualquer)],
             f"saida externa com categoria de despesa tinha de passar: {vazio}")
    print("  saída externa + categoria de despesa -> aceita")


def conferir_resposta_invalida(c: Conferencia) -> None:
    """Uma natureza que nao existe nao pode ser gravada."""
    print()
    print("=" * 78)
    print("8. RESPOSTA QUE NAO EXISTE NAO GRAVA")
    print("=" * 78)

    try:
        fechamento.triar(1, "qualquer_coisa")
        c.exigir(False, "triar aceitou uma natureza inventada")
        print("  x aceitou")
    except ValueError as erro:
        c.exigir(True, "")
        print(f"  recusou: {erro}")


def main() -> int:
    """Roda as oito conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("CONFERINDO O FECHAMENTO DE CAIXA")
    print()
    c = Conferencia()
    conferir_tipo_manda(c)
    conferir_sobra_aparece(c)
    conferir_triado_sai_da_sobra(c)
    conferir_interna_soma_zero(c)
    conferir_compra_nao_e_fluxo(c)
    conferir_medidores_batem(c)
    conferir_caso_real(c)
    conferir_resposta_invalida(c)
    conferir_espelho(c)
    conferir_categorias_por_sentido(c)
    conferir_ficha_do_imposto(c)
    conferir_leitura_da_tabela(c)
    conferir_sinal(c)
    conferir_espelho_apagado(c)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
