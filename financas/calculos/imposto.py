"""O que voce precisa saber para declarar o Imposto de Renda.

POR QUE ESTE MODULO EXISTE — E O QUE ELE NAO FAZ
================================================
Ele **organiza e confere**. Nao calcula imposto devido, nao emite DARF, nao
apura ganho de capital e nao substitui contador. Isso nao e modestia: apurar
imposto exige dados que este app nao tem (o bruto do salario, o informe
oficial da corretora) e regras que mudam todo ano.

O que ele faz e o que ninguem mais faz por voce: juntar, de um ano-calendario
inteiro, **o que entrou, o que voce tinha em 31/12 e quanto ja foi retido** —
e, principalmente, **apontar onde falta dado**.

AS TRES COISAS QUE ESTE MODULO EXISTE PARA DIZER
================================================

**1. A PLR NAO SE SOMA AO SALARIO.**
Ela tem tributacao exclusiva na fonte e vai numa ficha separada da
declaracao — "Rendimentos sujeitos a tributacao exclusiva/definitiva",
codigo 11. Somar a PLR ao rendimento tributavel faz voce pagar imposto que
nao deve. Com R$ ···· de PLR em 2025, e o erro mais caro possivel aqui.

**2. ESTE APP VE O LIQUIDO. A DECLARACAO USA O BRUTO.**
"Salario R$ ····" e o que CAIU NA CONTA, ja sem IRRF e sem INSS. O
numero da declaracao e maior e vem do informe da empresa. **O app nao produz
o numero da declaracao — ele produz o numero para voce CONFERIR.** Confundir
os dois e a armadilha mais facil desta tela, e por isso `rendimentos()`
devolve tudo marcado com `liquido=True`.

**Vale para a PLR tambem**, e isso surpreende: como o imposto dela e
definitivo, e facil supor que se declara o que caiu na conta. Nao. A ficha
pede o **valor bruto** num campo e o **IRRF retido** em outro — a PLR tem
tabela de retencao propria, separada da tabela do salario. Os dois numeros
estao no informe da empresa; o app so tem o liquido.

**3. A CARTEIRA NO EXTERIOR NAO TEM INFORME.**
Ninguem manda. Para a XP-Brasil existe informe de rendimentos; para a conta
Global, nao existe nada. E este app ja reconstruiu aquela posicao uma vez,
papel a papel. Por isso `bens_e_direitos()` devolve o exterior separado.

O CUSTO E O PROBLEMA CENTRAL
============================
O IR pede o bem pelo **custo de aquisicao**, nunca pelo valor de mercado. E o
custo, neste banco, quase nao existe: em 31/12/2025 havia UM papel de nove com
custo — e vindo da coluna "Valor aplicado" da corretora, a que muda sozinha.

A regra aqui e a mesma do resto do projeto: **custo desconhecido volta `None`,
nunca 0,0**. Zero se leria como "custou nada"; a verdade e "nao sei". A coluna
`fonte_custo` (migracao 11) diz de onde veio cada um.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from financas import banco
from financas.calculos import investimentos as _inv

FICHA_TRIBUTAVEL = "Rendimentos Tributáveis Recebidos de Pessoa Jurídica"
FICHA_EXCLUSIVA = "Rendimentos sujeitos à tributação exclusiva/definitiva"
FICHA_ISENTA = "Rendimentos Isentos e Não Tributáveis"
FICHA_TRIAGEM = "Precisa de triagem"

DESTINO_DA_RECEITA: dict[str, dict] = {
    "Salário": {
        "ficha": FICHA_TRIBUTAVEL,
        "codigo": None,
        "nota": ("O valor aqui é o LÍQUIDO que caiu na conta. A declaração "
                 "usa o BRUTO do informe da empresa, que é maior."),
    },
    "PLR": {
        "ficha": FICHA_EXCLUSIVA,
        "codigo": "11 - Participação nos lucros ou resultados",
        "nota": ("NÃO some ao salário. A PLR tem tabela própria e imposto "
                 "definitivo na fonte — declarar como tributável faz pagar "
                 "imposto indevido. E ela se declara pelo BRUTO, com o IRRF "
                 "retido num campo separado; o valor aqui é o líquido."),
    },
    "Rendimentos": {
        "ficha": FICHA_EXCLUSIVA,
        "codigo": "06 - Rendimentos de aplicações financeiras",
        "nota": "Juro da conta corrente, com IRRF já retido na fonte.",
    },
    "Indenização": {
        "ficha": FICHA_ISENTA,
        "codigo": None,
        "nota": ("Indenização não é renda: repõe uma perda, não acrescenta "
                 "patrimônio. Entra na declaração e NÃO paga imposto.\n\n"
                 "CUIDADO COM O QUE VEM DA MESMA ORIGEM. Se ela também pagou "
                 "salário atrasado, férias ou 13º, essa parte É tributável e "
                 "não pertence aqui — separe em Salário. A sentença ou o "
                 "acordo diz quanto é de cada coisa; o extrato não diz."),
    },
}


def anos_disponiveis(df_lancamentos: pd.DataFrame) -> list[str]:
    """Os anos-calendario que existem na base, do mais novo para o mais velho."""
    if df_lancamentos.empty or "mes_competencia" not in df_lancamentos.columns:
        return []
    anos = {str(m)[:4] for m in df_lancamentos["mes_competencia"] if m}
    return sorted((a for a in anos if a.isdigit() and len(a) == 4), reverse=True)


def rendimentos(df_lancamentos: pd.DataFrame, ano: str) -> pd.DataFrame:
    """O que entrou no ano, agrupado por categoria e por ficha da declaracao.

    Colunas: categoria, valor, lancamentos, ficha, codigo, nota, liquido

    `liquido` e sempre True e existe para a tela nao esquecer de avisar: estes
    sao valores de EXTRATO, ja com imposto retido. Ver o topo do modulo.

    Categoria que nao esta em `DESTINO_DA_RECEITA` cai na ficha "Precisa de
    triagem" — de proposito. Um palpite errado aqui vira erro de declaracao,
    e "nao sei" e uma resposta melhor.
    """
    colunas = ["categoria", "valor", "lancamentos", "ficha", "codigo",
               "nota", "liquido"]
    if df_lancamentos.empty:
        return pd.DataFrame(columns=colunas)

    tabela = df_lancamentos.copy()
    tabela = tabela[tabela["mes_competencia"].astype(str).str[:4] == str(ano)]
    tabela = tabela[tabela["natureza"].isin(["Receita", "Receita Extraordinária"])]
    if tabela.empty:
        return pd.DataFrame(columns=colunas)

    linhas = []
    for categoria, grupo in tabela.groupby("categoria", dropna=False):
        nome = str(categoria) if categoria is not None else "(sem categoria)"
        destino = DESTINO_DA_RECEITA.get(nome, {
            "ficha": FICHA_TRIAGEM,
            "codigo": None,
            "nota": ("Só você sabe o que é isto. Reembolso e dinheiro de "
                     "terceiros não são renda; venda de bem e doação têm "
                     "fichas próprias."),
        })
        linhas.append({
            "categoria": nome,
            "valor": float(grupo["valor"].sum()),
            "lancamentos": int(len(grupo)),
            "ficha": destino["ficha"],
            "codigo": destino["codigo"],
            "nota": destino["nota"],
            "liquido": True,
        })
    tabela_final = pd.DataFrame(linhas, columns=colunas)
    return tabela_final.sort_values("valor", ascending=False)


def total_por_ficha(df_rendimentos: pd.DataFrame) -> dict[str, float]:
    """Quanto vai em cada ficha da declaracao.

    A prova de que a PLR nao vazou para o rendimento tributavel e simplesmente
    olhar este dicionario: as duas fichas tem de existir separadas.
    """
    if df_rendimentos.empty:
        return {}
    return {str(ficha): float(grupo["valor"].sum())
            for ficha, grupo in df_rendimentos.groupby("ficha")}


def bens_e_direitos(ano: str) -> pd.DataFrame:
    """A posicao em 31/12 do ano, com CUSTO e valor de mercado lado a lado.

    Colunas: nome, classe, macro, exterior, quantidade, custo, fonte_custo,
             valor_mercado, moeda, mes_do_dado

    Ano invalido ou no futuro devolve tabela vazia, e a guarda e explicita
    de proposito: `investimentos.posicao()` arrasta o ultimo saldo conhecido
    para a frente quando o mes pedido nao tem foto — certo para a carteira,
    errado para o IR. Sem a guarda, `posicao('2099-12')` devolvia a carteira
    inteira como se voce a tivesse em 31/12/2099, e um ano ilegivel era pior
    ainda: a comparacao de mes e de TEXTO, e 'nao-e-ano-12' e maior que
    qualquer mes de verdade. O ano corrente passa, porque ver a posicao de
    hoje como previa e util e a tela avisa que e previa.

    `custo` volta `None` quando nao se sabe — nunca 0,0. E `fonte_custo` diz
    de onde veio: 'extrato' (linha de compra de verdade), 'manual' (voce
    digitou) ou 'valor_aplicado' (a coluna da corretora que muda sozinha, e
    que serve so como ultimo recurso).

    A declaracao pede o bem pelo custo. O valor de mercado vem junto so para
    voce reconhecer o papel e perceber diferencas grandes — ele NAO vai na
    ficha de Bens e Direitos.
    """
    colunas = ["nome", "classe", "macro", "exterior", "quantidade", "custo",
               "fonte_custo", "valor_mercado", "moeda", "mes_do_dado"]

    if not (isinstance(ano, str) or isinstance(ano, int)):
        return pd.DataFrame(columns=colunas)
    ano = str(ano)
    if not (len(ano) == 4 and ano.isdigit()):
        return pd.DataFrame(columns=colunas)
    if int(ano) > date.today().year:
        return pd.DataFrame(columns=colunas)

    mes = f"{ano}-12"
    posicao = _inv.posicao(mes)
    if posicao.empty:
        return pd.DataFrame(columns=colunas)
    posicao = posicao[posicao["saldo"] > 0]
    if posicao.empty:
        return pd.DataFrame(columns=colunas)

    linhas = []
    for _, papel in posicao.iterrows():
        cadastrado = banco.consultar_um(
            "SELECT classe, moeda FROM investimentos WHERE id = ?",
            (int(papel["id"]),))
        mes_do_dado = papel.get("mes_do_saldo") or mes
        detalhe = banco.consultar_um(
            """SELECT custo_aplicado, fonte_custo, quantidade
                 FROM investimentos_saldos
                WHERE investimento_id = ? AND mes = ?""",
            (int(papel["id"]), mes_do_dado))
        classe = cadastrado["classe"] if cadastrado else None
        macro = _inv.macro_da_classe(classe)
        custo = (float(detalhe["custo_aplicado"])
                 if detalhe and detalhe["custo_aplicado"] is not None else None)
        linhas.append({
            "nome": papel["nome"],
            "classe": classe,
            "macro": macro,
            "exterior": (macro or "").strip().lower() == "internacional",
            "quantidade": (float(detalhe["quantidade"])
                           if detalhe and detalhe["quantidade"] is not None
                           else None),
            "custo": custo,
            "fonte_custo": (detalhe["fonte_custo"] if detalhe else None),
            "valor_mercado": float(papel["saldo"]),
            "moeda": (cadastrado["moeda"] if cadastrado else None) or "BRL",
            "mes_do_dado": mes_do_dado,
        })
    return pd.DataFrame(linhas, columns=colunas).sort_values(
        "valor_mercado", ascending=False)


def custos_faltando(df_bens: pd.DataFrame) -> pd.DataFrame:
    """Os papeis sem custo confiavel — o que impede a declaracao de sair.

    Entram dois casos, e eles sao diferentes:

      - `custo` e None            -> nao existe custo nenhum
      - `fonte_custo` e           -> existe, mas veio da coluna que muda
        'valor_aplicado'             sozinha e nao serve de prova

    Os dois exigem a mesma acao (buscar a nota ou o informe), por isso saem
    na mesma lista.
    """
    if df_bens.empty:
        return df_bens
    sem_custo = df_bens["custo"].isna()
    fonte_fraca = df_bens["fonte_custo"] == "valor_aplicado"
    return df_bens[sem_custo | fonte_fraca]


def imposto_retido(ano: str) -> pd.DataFrame:
    """O IRRF que a corretora ja reteve no ano, linha a linha.

    Colunas: data, descricao, valor, especie

    `especie` separa duas coisas que a tela nao pode misturar:

      'definitivo'   IRRF sobre cupom de Tesouro Direto. Ja acabou: nao gera
                     restituicao nem imposto a pagar depois.
      'antecipacao'  come-cotas de fundo, cobrado em maio e novembro. E
                     adiantamento do imposto do resgate futuro.

    Quem le um total sem essa separacao acha que pagou imposto a mais.
    """
    colunas = ["data", "descricao", "valor", "especie"]
    linhas = []
    for linha in banco.consultar(
            """SELECT data, descricao, valor FROM investimentos_movimentos
                WHERE tipo_movimento = 'imposto' AND substr(data, 1, 4) = ?
                ORDER BY data""", (str(ano),)):
        descricao = (linha["descricao"] or "").upper()
        especie = "definitivo" if "TESOURO" in descricao else "antecipacao"
        linhas.append({"data": linha["data"], "descricao": linha["descricao"],
                       "valor": float(linha["valor"] or 0), "especie": especie})
    return pd.DataFrame(linhas, columns=colunas)


def existe_saldo(investimento_id: int, mes: str) -> bool:
    """Ha foto de saldo para este papel neste mes?

    `investimentos_saldos` so tem linha para os meses que foram registrados.
    Quem vai GRAVAR precisa perguntar isto antes, senao escreve no vazio.
    """
    return banco.consultar_um(
        "SELECT 1 FROM investimentos_saldos WHERE investimento_id = ? AND mes = ?",
        (int(investimento_id), mes)) is not None


def salvar_custo(investimento_id: int, mes: str, custo: float | None,
                 fonte: str = "manual") -> bool:
    """Grava o custo de aquisicao de um papel num mes. Devolve SE gravou.

    `custo=None` apaga o valor E a procedencia — util para desfazer um numero
    errado sem deixar a fonte apontando para nada.

    POR QUE ELA DEVOLVE bool, E NAO None
    ------------------------------------
    Isto e um UPDATE, e UPDATE numa linha que nao existe casa com zero linhas
    **sem erro nenhum**. Como `investimentos_saldos` so tem linha nos meses
    fotografados, gravar o custo em '2026-12' durante agosto de 2026 fazia a
    tela dizer "salvo" e nao salvava nada.

    Foi encontrado por teste, nao na tela — que e o unico jeito de achar um
    defeito que nao levanta erro.

    Falhar alto e a unica opcao decente quando a alternativa e mentir baixo:
    a mesma regra de `salvar_saldo`, que recusa gravar dolar sem cotacao.
    Quem chama deve usar `bens_e_direitos()['mes_do_dado']`, que sempre aponta
    para um mes que existe.
    """
    if not existe_saldo(investimento_id, mes):
        return False
    if custo is None:
        banco.executar(
            """UPDATE investimentos_saldos
                  SET custo_aplicado = NULL, fonte_custo = NULL
                WHERE investimento_id = ? AND mes = ?""",
            (int(investimento_id), mes))
    else:
        banco.executar(
            """UPDATE investimentos_saldos
                  SET custo_aplicado = ?, fonte_custo = ?
                WHERE investimento_id = ? AND mes = ?""",
            (float(custo), fonte, int(investimento_id), mes))
    return True


def custo_pelo_extrato(investimento_id: int, ate_o_mes: str) -> float | None:
    """Soma as COMPRAS daquele papel no extrato da corretora, ate um mes.

    Esta e a fonte boa de custo: linha de compra e dinheiro de verdade saindo,
    com data. Devolve `None` quando o extrato nao alcanca o papel — e ele so
    alcanca de jan/2026 em diante, entao a maior parte da carteira dele fica
    de fora e precisa de digitacao.

    **So responde para papeis que NASCERAM dentro da cobertura do extrato.**
    Um papel mais velho que o extrato teria o custo somado pela metade, e o
    resultado sairia com o rotulo 'extrato' — errado e com cara de confiavel.

    Nao serve para Tesouro Direto: o extrato escreve so "COMPRA TESOURO DIRETO
    CLIENTES", sem dizer QUAL titulo. Mesmo limite que `_movimentos_do_papel`.
    """
    inicio, _fim = _inv.periodo_do_extrato_da_corretora()
    if not inicio or ate_o_mes < inicio:
        return None
    papel = banco.consultar_um(
        "SELECT nome FROM investimentos WHERE id = ?", (int(investimento_id),))
    if not papel:
        return None

    primeiro = banco.consultar_um(
        """SELECT MIN(mes) AS m FROM investimentos_saldos
            WHERE investimento_id = ? AND saldo > 0""",
        (int(investimento_id),))
    if not primeiro or not primeiro["m"] or primeiro["m"] < inicio:
        return None
    total = 0.0
    achou = False
    for mes in _meses_entre(inicio, ate_o_mes):
        movimento = _inv._movimentos_do_papel(papel["nome"], mes)
        if movimento is None:
            continue
        aporte, _resgate = movimento
        if aporte:
            total += aporte
            achou = True
    return total if achou else None


def _meses_entre(inicio: str, fim: str) -> list[str]:
    """Todos os 'AAAA-MM' de inicio ate fim, inclusive."""
    if not inicio or not fim or inicio > fim:
        return []
    meses = []
    ano, mes = int(inicio[:4]), int(inicio[5:7])
    while f"{ano:04d}-{mes:02d}" <= fim:
        meses.append(f"{ano:04d}-{mes:02d}")
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    return meses


def resumo(df_lancamentos: pd.DataFrame, ano: str) -> dict:
    """Tudo que a tela precisa para o ano, num dicionario so.

    Devolve {ano, rendimentos, por_ficha, bens, faltando, retido,
             total_retido_definitivo, total_retido_antecipacao,
             tem_exterior}.
    """
    df_rendimentos = rendimentos(df_lancamentos, ano)
    bens = bens_e_direitos(ano)
    retido = imposto_retido(ano)
    definitivo = float(retido[retido["especie"] == "definitivo"]["valor"].sum()) \
        if not retido.empty else 0.0
    antecipacao = float(retido[retido["especie"] == "antecipacao"]["valor"].sum()) \
        if not retido.empty else 0.0
    return {
        "ano": str(ano),
        "rendimentos": df_rendimentos,
        "por_ficha": total_por_ficha(df_rendimentos),
        "bens": bens,
        "faltando": custos_faltando(bens),
        "retido": retido,
        "total_retido_definitivo": definitivo,
        "total_retido_antecipacao": antecipacao,
        "tem_exterior": bool(not bens.empty and bens["exterior"].any()),
    }
