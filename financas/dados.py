"""
dados.py — A ponte entre o banco e os calculos.
==============================================================================

POR QUE ESTE ARQUIVO EXISTE
---------------------------
O banco guarda o dado CRU. Os calculos e graficos precisam do dado ENRIQUECIDO:
com a grande categoria junto, com a data ja convertida, com colunas derivadas
como "é parcelado?" e "dia do mes".

Se cada pagina fizesse esse enriquecimento por conta propria, o mesmo codigo
apareceria em dez lugares — e no dia em que a regra mudasse, nove deles
ficariam desatualizados. Entao concentramos tudo aqui.

O QUE E UM DataFrame
--------------------
E a "tabela em memoria" do pandas. Pense numa planilha: tem colunas com nome e
linhas numeradas. A diferenca e que ele sabe fazer sozinho coisas como "somar
a coluna valor agrupando por categoria" numa linha de codigo.

O caminho do dado no projeto e sempre este:

    SQLite  ->  dados.py (enriquece)  ->  calculos/ (calcula)  ->  paginas/ (mostra)

REGRA IMPORTANTE: nenhum arquivo desta pasta importa `streamlit`. Isso e o que
permite testar tudo no terminal. O cache do Streamlit fica em ui/estado.py.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from financas import banco, config


def carregar_lancamentos() -> pd.DataFrame:
    """Le TODOS os lancamentos e devolve o DataFrame pronto para uso.

    O SQL ja faz o LEFT JOIN com categorias para trazer a grande categoria
    junto. "LEFT" join significa: traga todos os lancamentos, mesmo os que
    tiverem uma categoria que nao esta no cadastro (nesse caso a grande
    categoria vem vazia, e o codigo abaixo preenche com "Outros"). Um join
    normal (INNER) sumiria com essas linhas em silencio — que e exatamente o
    tipo de perda de dado que nao se percebe.
    """
    df = banco.df(
        """
        SELECT l.id, l.id_unico, l.data, l.hora, l.mes_competencia,
               l.descricao, l.portador, l.valor,
               l.categoria, l.tipo, l.natureza, l.origem,
               l.parcela_atual, l.parcela_total, l.chave_parcelamento,
               l.fitid, l.saldo_apos, l.observacao, l.regra_aplicada,
               c.grande_categoria,
               ct.nome AS conta
        FROM lancamentos l
        LEFT JOIN categorias c ON c.nome = l.categoria
        LEFT JOIN contas     ct ON ct.id  = l.conta_id
        ORDER BY l.data DESC, l.id DESC
        """
    )
    return enriquecer(df)


COLUNAS_DERIVADAS = (
    "data_dt", "dia", "dia_semana", "ano", "grande_categoria",
    "e_parcelado", "e_primeira_parcela", "e_parcela_herdada",
    "e_despesa", "e_receita", "e_investimento", "valor_abs",
)


def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta as colunas derivadas que os calculos esperam.

    Trabalhamos numa COPIA (`df.copy()`) para nunca alterar o DataFrame que
    quem chamou passou. Modificar o objeto de outra pessoa sem avisar e uma
    fonte classica de bug dificil de rastrear.

    As colunas acrescentadas estao em `COLUNAS_DERIVADAS`, e valem TAMBEM para
    o DataFrame vazio — e essa a razao de a lista existir num lugar so.
    """
    if df.empty:
        for coluna in COLUNAS_DERIVADAS:
            if coluna not in df.columns:
                df[coluna] = pd.Series(dtype="object")
        return df

    df = df.copy()

    df["data_dt"] = pd.to_datetime(df["data"], errors="coerce")
    df["dia"] = df["data_dt"].dt.day
    df["dia_semana"] = df["data_dt"].dt.dayofweek
    df["ano"] = df["mes_competencia"].str.slice(0, 4)

    df["grande_categoria"] = df["grande_categoria"].fillna("Outros")
    df["categoria"] = df["categoria"].fillna("Outros")
    df["tipo"] = df["tipo"].fillna(config.TIPO_VARIAVEL)
    df["natureza"] = df["natureza"].fillna(config.NATUREZA_DESPESA)
    df["origem"] = df["origem"].fillna(config.ORIGEM_MANUAL)
    df["parcela_atual"] = df["parcela_atual"].fillna(1).astype(int)
    df["parcela_total"] = df["parcela_total"].fillna(1).astype(int)

    df["e_parcelado"] = df["parcela_total"] > 1
    df["e_primeira_parcela"] = df["e_parcelado"] & (df["parcela_atual"] == 1)
    df["e_parcela_herdada"] = df["e_parcelado"] & (df["parcela_atual"] > 1)
    df["e_despesa"] = df["natureza"].isin(config.NATUREZAS_DESPESA)
    df["e_receita"] = df["natureza"].isin(config.NATUREZAS_RECEITA)
    df["e_investimento"] = df["natureza"] == config.NATUREZA_INVESTIMENTO

    df["valor_abs"] = df["valor"].abs()

    return df


def despesas(df: pd.DataFrame) -> pd.DataFrame:
    """So o que e gasto de verdade (exclui pagamento de fatura e investimento)."""
    if df.empty:
        return df
    return df[df["e_despesa"]]


def receitas(df: pd.DataFrame) -> pd.DataFrame:
    """So o que e entrada de dinheiro (receita comum + extraordinaria)."""
    if df.empty:
        return df
    return df[df["e_receita"]]


def do_mes(df: pd.DataFrame, mes: str) -> pd.DataFrame:
    """Filtra um mes de competencia ("2026-08")."""
    if df.empty or not mes:
        return df
    return df[df["mes_competencia"] == mes]


def do_cartao(df: pd.DataFrame) -> pd.DataFrame:
    """So o que veio da fatura do cartao."""
    if df.empty:
        return df
    return df[df["origem"] == config.ORIGEM_FATURA]


def da_conta(df: pd.DataFrame) -> pd.DataFrame:
    """So o que veio do extrato da conta corrente."""
    if df.empty:
        return df
    return df[df["origem"] == config.ORIGEM_EXTRATO]


def total_despesa(df: pd.DataFrame) -> float:
    """Total gasto, como numero POSITIVO.

    Os valores estao negativos no banco (saiu dinheiro), mas na tela a gente
    diz "gastei R$ ····", nao "gastei menos R$ ····". O sinal de
    menos vira aqui, uma vez so.
    """
    if df.empty:
        return 0.0
    return float(-despesas(df)["valor"].sum())


def total_receita(df: pd.DataFrame, incluir_extraordinaria: bool = True) -> float:
    """Total recebido, como numero positivo.

    `incluir_extraordinaria=False` deixa de fora PLR, indenizacao e afins. Isso
    importa porque um PLR de R$ ···· faz o mes parecer normal quando na
    verdade foi excepcional — a planilha antiga separava os dois e a gente
    manteve a separacao.
    """
    if df.empty:
        return 0.0
    if incluir_extraordinaria:
        return float(receitas(df)["valor"].sum())
    recorrente = df[df["natureza"] == config.NATUREZA_RECEITA]
    return float(recorrente["valor"].sum())


def total_extraordinaria(df: pd.DataFrame) -> float:
    """So a receita extraordinaria (PLR, indenizacao, restituicao)."""
    if df.empty:
        return 0.0
    extra = df[df["natureza"] == config.NATUREZA_RECEITA_EXTRA]
    return float(extra["valor"].sum())


def saldo(df: pd.DataFrame) -> float:
    """Receita menos despesa. Positivo = sobrou dinheiro no mes."""
    return total_receita(df) - total_despesa(df)


def por_categoria(df: pd.DataFrame, coluna: str = "categoria") -> pd.DataFrame:
    """Agrupa as DESPESAS por categoria (ou por grande_categoria).

    Devolve um DataFrame com [categoria, total, quantidade, percentual],
    do maior gasto para o menor — que e a ordem util para ler.
    """
    gastos = despesas(df)
    if gastos.empty:
        return pd.DataFrame(columns=[coluna, "total", "quantidade", "percentual"])

    agrupado = (
        gastos.groupby(coluna)
        .agg(total=("valor", lambda s: -s.sum()), quantidade=("valor", "size"))
        .reset_index()
        .sort_values("total", ascending=False)
    )
    soma = agrupado["total"].sum()
    agrupado["percentual"] = agrupado["total"] / soma if soma else 0.0
    return agrupado


def por_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Serie mensal com receita, despesa, saldo e acumulado.

    E a base do grafico de historico e do resumo anual.
    """
    if df.empty:
        return pd.DataFrame(columns=["mes", "receita", "receita_extra",
                                     "despesa", "saldo", "acumulado",
                                     "quantidade"])

    agrupado = (
        df.groupby("mes_competencia")
        .apply(lambda g: pd.Series({
            "receita": total_receita(g),
            "receita_extra": total_extraordinaria(g),
            "despesa": total_despesa(g),
            "quantidade": float(len(g)),
        }), include_groups=False)
        .reset_index()
        .rename(columns={"mes_competencia": "mes"})
        .sort_values("mes")
    )
    agrupado["saldo"] = agrupado["receita"] - agrupado["despesa"]
    agrupado["acumulado"] = agrupado["saldo"].cumsum()
    return agrupado


def meses_disponiveis() -> list[str]:
    """Todos os meses que existem no banco, do mais novo para o mais antigo.

    Tinha um parametro `apenas_com_lancamento` que NUNCA era usado no corpo da
    funcao — a consulta ja lista so meses que tem lancamento. Um parametro que
    nao faz nada e pior que nenhum: quem le acredita que existe uma alternativa.
    """
    linhas = banco.consultar(
        "SELECT DISTINCT mes_competencia AS m FROM lancamentos "
        "ORDER BY mes_competencia DESC"
    )
    return [linha["m"] for linha in linhas if linha["m"]]


# Ate onde o seletor de mes enxerga para a frente. Doze meses porque e o
# horizonte natural de um orcamento: cobre o ano inteiro pela frente, incluindo
# o 13o e as parcelas mais longas, sem virar uma lista interminavel.
HORIZONTE_DO_SELETOR = 12


def meses_para_seletor(horizonte: int = HORIZONTE_DO_SELETOR) -> list[str]:
    """Meses que o seletor do topo oferece: o historico MAIS o futuro previsto.

    POR QUE ISTO NAO E `meses_disponiveis()`
    ----------------------------------------
    Aquela lista sai de `SELECT DISTINCT mes_competencia FROM lancamentos`, ou
    seja: um mes so existe depois que alguma linha cai nele. Isso e o certo
    para as telas que olham o PASSADO — filtrar Lancamentos por um mes vazio,
    ou pedir o Patrimonio de um mes que nao aconteceu, nao devolve nada util.

    Mas prende o seletor do topo no presente. Em 01/09/2026 o ultimo mes do
    banco era setembro, entao a seta ▶ nascia desabilitada e nao havia como
    olhar outubro — mesmo o app SABENDO que R$ ···· de parcelas caem la.

    A informacao existia e era inalcancavel: `previsao.do_mes()` e
    `composicao_do_mes()` ja montam o mes futuro inteiro a partir dos fixos
    cadastrados e das parcelas em aberto, sem precisar de lancamento nenhum.

    O QUE ESTA FUNCAO GARANTE
    -------------------------
    1. todo mes que tem lancamento continua na lista (nada some);
    2. o mes CORRENTE sempre aparece, mesmo recem-virado e ainda vazio;
    3. mais `horizonte` meses a frente dele, sempre.

    Devolve na mesma ordem de `meses_disponiveis()` — do mais novo para o mais
    antigo — porque e assim que os seletores da tela ja esperam receber.
    """
    from financas.formato import somar_meses

    tudo = set(meses_disponiveis())
    passo = mes_corrente()
    for _ in range(int(horizonte) + 1):
        if passo:
            tudo.add(passo)
            passo = somar_meses(passo, 1)
    return sorted(tudo, reverse=True)


def mes_corrente() -> str:
    """O mes de hoje, no formato 'AAAA-MM'."""
    return date.today().strftime("%Y-%m")


def mes_esta_em_andamento(mes: str | None) -> bool:
    """O mes ainda esta acontecendo? Entao os numeros dele nao sao fechamento.

    Vale para o mes corrente E para os futuros — quem precisa separar os dois
    usa `mes_e_futuro`.
    """
    return bool(mes) and mes >= mes_corrente()


def mes_e_futuro(mes: str | None) -> bool:
    """O mes ainda NEM COMECOU.

    Diferente de `mes_esta_em_andamento`, que tambem e verdade para o mes
    corrente. A distincao aparece na tela e nao e cosmetica:

      - mes corrente   comecou, tem despesa lancada e ainda vai ter receita
      - mes futuro     nao comecou; o que houver ali chegou por antecipacao

    Em 25/08/2026 o dashboard chamava setembro de "Mes em andamento · dados
    ate 21/08" — falso duas vezes. Setembro so tinha a fatura, importada
    adiantada, e nenhuma linha de extrato.
    """
    return bool(mes) and mes > mes_corrente()


def meses_fechados(serie, minimo_lancamentos: int = 5):
    """Filtra uma serie mensal, deixando so os meses que ja ACONTECERAM.

    O MESMO DEFEITO APARECEU EM QUATRO LUGARES antes deste helper existir:
    a taxa de poupanca, o comparativo anual, a projecao de caixa e a escolha
    do mes padrao. Todos liam meses incompletos como se fossem fechados.

    Um mes vale para media/comparacao quando passa em DOIS testes:

    1. TEM MOVIMENTO DE VERDADE — pelo menos `minimo_lancamentos` linhas.
       Um mes futuro com tres parcelas agendadas nao e um mes vivido.

    2. JA TERMINOU — o mes corrente tem a despesa contratada mas ainda nao a
       receita inteira. Em 23/08/2026, agosto tinha R$ ···· de receita
       recorrente porque o salario cai dia 24: incluir esse mes na media
       derrubava a projecao de ~R$ ···· para R$ ····

    Espera um DataFrame com a coluna `mes` (e opcionalmente `quantidade`),
    como o que `por_mes()` devolve.
    """
    if serie is None or serie.empty:
        return serie
    filtrada = serie
    if "quantidade" in filtrada.columns:
        filtrada = filtrada[filtrada["quantidade"] >= minimo_lancamentos]

    em_andamento = filtrada["mes"].map(mes_esta_em_andamento).astype(bool)
    return filtrada[~em_andamento]


def mes_mais_recente() -> str | None:
    """O mes mais recente que ja ACONTECEU e tem movimento de verdade.

    Duas condicoes, e cada uma existe por um motivo diferente:

    1. PELO MENOS 5 LANCAMENTOS — parcelas futuras criam lancamentos la em
       2026-12. Abrir o painel em dezembro, com 3 parcelas agendadas, daria a
       impressao de que o app esta vazio.

    2. NAO PASSAR DO MES CORRENTE — este e o que faltava, e o estrago era
       maior. Em 22/08/2026 a funcao devolvia setembro, porque a fatura de
       setembro ja estava fechada e tinha 47 lancamentos. So que setembro
       ainda nao tinha salario: o painel abria mostrando
       **243,5% de comprometimento** e saldo negativo, como se o mes tivesse
       sido pessimo. Ele nem tinha comecado.

       Um mes futuro sempre parece catastrofico, porque as despesas ja
       contratadas chegam antes da receita. Nao e informacao, e ilusao de
       otica.

    Quando voce ESCOLHE um mes em andamento no seletor, ele aparece — a
    funcao so decide onde ABRIR. A tela avisa com uma tarja (ver
    `mes_esta_em_andamento`).
    """
    limite = mes_corrente()
    linha = banco.consultar_um(
        "SELECT mes_competencia AS m FROM lancamentos "
        "WHERE mes_competencia <= ? "
        "GROUP BY mes_competencia HAVING COUNT(*) >= 5 "
        "ORDER BY mes_competencia DESC LIMIT 1",
        (limite,)
    )
    if linha:
        return linha["m"]
    linha = banco.consultar_um(
        "SELECT MAX(mes_competencia) AS m FROM lancamentos")
    return linha["m"] if linha else None


def carregar_categorias() -> pd.DataFrame:
    """O cadastro de categorias com a grande categoria e a cor."""
    return banco.df(
        """SELECT c.nome, c.grande_categoria, c.natureza_padrao, c.ativa, c.ordem,
                  g.cor
           FROM categorias c
           LEFT JOIN grandes_categorias g ON g.nome = c.grande_categoria
           ORDER BY c.ordem, c.nome"""
    )


def lista_categorias(ativas: bool = True) -> list[str]:
    """So os nomes das categorias, para preencher menus suspensos."""
    sql = "SELECT nome FROM categorias"
    if ativas:
        sql += " WHERE ativa = 1"
    sql += " ORDER BY ordem, nome"
    return [linha["nome"] for linha in banco.consultar(sql)]


def lista_grandes_categorias() -> list[str]:
    """Os nomes das grandes categorias, na ordem cadastrada."""
    return [
        linha["nome"]
        for linha in banco.consultar(
            "SELECT nome FROM grandes_categorias ORDER BY ordem, nome")
    ]


def cores_por_grande_categoria() -> dict[str, str]:
    """Mapa {grande categoria: cor}, para os graficos manterem a mesma cor."""
    return {
        linha["nome"]: linha["cor"] or config.CORES_TEMA["neutra"]
        for linha in banco.consultar("SELECT nome, cor FROM grandes_categorias")
    }


def cores_por_categoria() -> dict[str, str]:
    """Mapa {categoria: cor da sua grande categoria}."""
    cores = cores_por_grande_categoria()
    return {
        linha["nome"]: cores.get(linha["grande_categoria"], config.CORES_TEMA["neutra"])
        for linha in banco.consultar("SELECT nome, grande_categoria FROM categorias")
    }
