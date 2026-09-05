"""
estado.py — Cache dos dados e o que o app "lembra" entre um clique e outro.
==============================================================================

COMO O STREAMLIT FUNCIONA (a parte que confunde no comeco)
-----------------------------------------------------------
Toda vez que voce mexe em QUALQUER COISA na tela — clica num botao, muda o mes
no menu, digita numa caixa — o Streamlit roda O SCRIPT INTEIRO DE NOVO, de cima
para baixo.

Isso e otimo (o codigo fica simples e linear, sem "quando clicar faca isso"),
mas tem duas consequencias:

    1. Ler o banco de novo a cada clique seria lento.  -> resolvido com CACHE
    2. Variaveis normais se perdem a cada rerun.       -> resolvido com ESTADO

CACHE (@st.cache_data)
----------------------
Marca uma funcao como "o resultado disto pode ser guardado". Na primeira
chamada ela roda de verdade; nas seguintes, o Streamlit devolve o resultado
guardado sem executar nada.

    @st.cache_data(ttl=60)
    def carregar():
        return banco.df("SELECT ...")

O `ttl=60` significa "guarde por 60 segundos". Depois disso ele le de novo.
Escolhemos um tempo curto de proposito: os dados mudam quando VOCE importa ou
edita, e nesses momentos chamamos `limpar_cache()` explicitamente. O ttl e so
uma rede de seguranca, para nada ficar velho por muito tempo.

ESTADO (st.session_state)
-------------------------
Um dicionario que SOBREVIVE aos reruns. E onde guardamos "qual mes esta
selecionado" ou "qual arquivo esta em revisao na tela de importacao".

POR QUE ESTE ARQUIVO ESTA EM ui/ E NAO EM financas/
----------------------------------------------------
Porque `@st.cache_data` e `st.session_state` sao do Streamlit, e a pasta
`financas/` e proposital e rigorosamente livre de Streamlit — e o que permite
testar os calculos no terminal. Toda a "cola" com o Streamlit mora aqui.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from financas import banco, dados, precos, regras
from financas.calculos import compras, financiamento, fixos, metas, parcelas

TTL = 60


@st.cache_resource
def preparar_banco() -> dict:
    """Cria/atualiza as tabelas e semeia os padroes. Roda UMA VEZ por sessao.

    Usa `@st.cache_resource` (e nao `cache_data`) porque nao esta guardando um
    dado para reusar: esta garantindo que um EFEITO aconteca so uma vez. E a
    diferenca entre os dois decoradores:

        cache_data     guarda um VALOR (uma tabela, um numero)
        cache_resource guarda um RECURSO ou um efeito unico (conexao, setup)
    """
    resumo = banco.inicializar()
    resumo["regras_essenciais"] = regras.garantir_regras_essenciais()
    return resumo


@st.cache_data(ttl=TTL, show_spinner=False)
def lancamentos() -> pd.DataFrame:
    """Todos os lancamentos, ja enriquecidos. E a base de quase toda tela."""
    return dados.carregar_lancamentos()


@st.cache_data(ttl=TTL, show_spinner=False)
def meses() -> list[str]:
    """Meses que TEM lancamento, do mais recente para o mais antigo.

    Para o seletor do topo use `meses_do_seletor()`, que enxerga o futuro.
    Esta aqui e a certa para filtrar o que ja aconteceu.
    """
    return dados.meses_disponiveis()


@st.cache_data(ttl=TTL, show_spinner=False)
def meses_do_seletor() -> list[str]:
    """A lista do seletor do topo: o historico mais 12 meses a frente.

    Separada de `meses()` de proposito — ver `dados.meses_para_seletor`.
    """
    return dados.meses_para_seletor()


@st.cache_data(ttl=TTL, show_spinner=False)
def mes_padrao() -> str | None:
    """O mes que abre selecionado: o mais recente com movimento de verdade."""
    return dados.mes_mais_recente()


@st.cache_data(ttl=TTL, show_spinner=False)
def categorias() -> pd.DataFrame:
    """O cadastro de categorias, com a grande categoria de cada uma."""
    return dados.carregar_categorias()


@st.cache_data(ttl=TTL, show_spinner=False)
def lista_categorias() -> list[str]:
    """So os NOMES das categorias ativas — para preencher menus."""
    return dados.lista_categorias()


@st.cache_data(ttl=TTL, show_spinner=False)
def naturezas_por_categoria() -> dict[str, str]:
    """{nome da categoria: natureza padrao dela}.

    A natureza de um lancamento e HERDADA da categoria — e a importacao ja
    respeitava isso, mas a edicao manual nao. Trocar a categoria e deixar a
    natureza velha faz a linha continuar contando como receita quando virou
    transferencia, ou vice-versa; e natureza e o que decide tudo no painel.

    Ver o uso em `paginas/lancamentos.py`.
    """
    tabela = categorias()
    if tabela.empty or "natureza_padrao" not in tabela.columns:
        return {}
    return {str(linha["nome"]): str(linha["natureza_padrao"])
            for _, linha in tabela.iterrows()
            if linha.get("natureza_padrao")}


@st.cache_data(ttl=TTL, show_spinner=False)
def lista_grandes_categorias() -> list[str]:
    """So os NOMES das grandes categorias — para preencher menus."""
    return dados.lista_grandes_categorias()


@st.cache_data(ttl=TTL, show_spinner=False)
def cores_categoria() -> dict[str, str]:
    """{categoria: cor}. A MESMA cor em todas as telas e o que deixa
    voce reconhecer uma categoria sem ler a legenda."""
    return dados.cores_por_categoria()


@st.cache_data(ttl=TTL, show_spinner=False)
def cores_grande_categoria() -> dict[str, str]:
    """{grande categoria: cor}. Ver `cores_categoria`."""
    return dados.cores_por_grande_categoria()


@st.cache_data(ttl=TTL, show_spinner=False)
def cadastro_fixos() -> pd.DataFrame:
    """Os gastos fixos cadastrados, com a grande categoria junto."""
    return fixos.cadastro()


@st.cache_data(ttl=TTL, show_spinner=False)
def cadastro_metas() -> pd.DataFrame:
    """As metas de poupanca cadastradas."""
    return metas.cadastro()


@st.cache_data(ttl=TTL, show_spinner=False)
def cadastro_compras() -> pd.DataFrame:
    """A lista de compras futuras (a lista de desejos)."""
    return compras.cadastro()


@st.cache_data(ttl=TTL, show_spinner=False)
def historico_precos() -> pd.DataFrame:
    """Todos os pontos de preco de todos os itens da lista de desejos.

    Uma consulta so para a lista inteira, em vez de uma por item: a aba de
    compras desenha 20 cartoes numa passada, e 20 idas ao banco por rerun
    seriam 20 idas por tecla digitada.
    """
    return precos.historico()


@st.cache_data(ttl=TTL, show_spinner=False)
def cenario_financiamento() -> dict:
    """As premissas do simulador de financiamento."""
    return financiamento.cenario_padrao()


@st.cache_data(ttl=TTL, show_spinner=False)
def conjunto_regras():
    """As regras carregadas para a memoria (usado na importacao)."""
    return regras.carregar_regras()


@st.cache_data(ttl=TTL, show_spinner=False)
def carteira_posicao(mes: str | None) -> pd.DataFrame:
    """A foto da carteira num mes: cada papel com o saldo mais recente."""
    from financas.calculos import investimentos

    return investimentos.posicao(mes)


@st.cache_data(ttl=TTL, show_spinner=False)
def carteira_evolucao() -> pd.DataFrame:
    """A carteira inteira mes a mes, com aporte, resgate e rendimento."""
    from financas.calculos import investimentos

    return investimentos.evolucao_carteira()


@st.cache_data(ttl=TTL, show_spinner=False)
def carteira_conciliacao(mes: str | None) -> dict:
    """A conferencia entre a carteira cadastrada e o que os lancamentos dizem.

    So recebe o mes: `conciliar()` le tudo do banco por conta propria. Ela
    tinha um parametro de DataFrame que nunca era usado, e ele foi removido —
    ver a docstring dela.
    """
    from financas.calculos import investimentos

    return investimentos.conciliar(mes)


@st.cache_data(ttl=TTL, show_spinner=False)
def carteira_alocacao(mes: str | None, nivel: str = "classe",
                      _carteira: pd.DataFrame | None = None) -> pd.DataFrame:
    """A carteira agrupada por classe (ou macro), comparada com a meta.

    `_carteira` (com underscore, fora da chave de cache) e a foto que a tela
    ja tem na mao. Passando, as duas chamadas seguidas — uma por classe, outra
    por macro — param de remontar a mesma `posicao()` duas vezes.
    """
    from financas.calculos import investimentos

    return investimentos.alocacao_atual(mes, nivel, _carteira)


@st.cache_data(ttl=TTL, show_spinner=False)
def carteira_contra_indice(nome_indice: str = "CDI") -> pd.DataFrame:
    """A carteira ao lado de uma carteira-sombra que so rende o indice."""
    from financas.calculos import investimentos

    return investimentos.carteira_contra_indice(nome_indice)


def impressao_da_pasta(pasta) -> str:
    """Uma marca barata que muda quando a pasta muda: nome, tamanho e data.

    Serve de CHAVE DE CACHE para `arquivos_da_pasta`, que precisa ler cada
    arquivo para calcular o hash e custa 741 ms com os 70 arquivos dele. Esta
    aqui so lista o diretorio — microssegundos — e basta para saber se vale a
    pena refazer a conta.
    """
    from pathlib import Path

    caminho = Path(pasta)
    if not caminho.is_dir():
        return ""
    partes = []
    for arquivo in sorted(caminho.iterdir()):
        if arquivo.is_file():
            info = arquivo.stat()
            partes.append(f"{arquivo.name}:{info.st_size}:{int(info.st_mtime)}")
    return "|".join(partes)


@st.cache_data(ttl=600, show_spinner=False)
def arquivos_da_pasta(pasta: str, impressao: str) -> pd.DataFrame:
    """Os arquivos da pasta, com a marca de quais ja foram importados.

    `impressao` nao e usada dentro da funcao — ela existe so para entrar na
    CHAVE do cache. E o padrao inverso do `_carteira` em `carteira_alocacao`:
    la o underscore TIRA o argumento da chave; aqui o argumento existe apenas
    para compor a chave. Sem ele, o cache guardaria a lista velha por dez
    minutos depois de voce jogar um arquivo novo na pasta.
    """
    from financas import importador

    return importador.estado_da_pasta(pasta)


@st.cache_data(ttl=TTL, show_spinner=False)
def cobertura_de_importacao() -> pd.DataFrame:
    """Quando cada tipo de arquivo entrou pela ultima vez."""
    from financas import importador

    return importador.cobertura_por_tipo()


@st.cache_data(ttl=TTL, show_spinner=False)
def carteira_desempenho(mes: str | None = None) -> pd.DataFrame:
    """Uma linha por papel, com saldo, rentabilidade e comparacao com o indice.

    E a consulta mais cara da tela de Investimentos — 273 ms com os 18 papeis
    dele, porque calcula a evolucao de cada um. O cache e o que faz a tela
    responder a cliques sem refazer tudo; sem ele, cada rolagem custaria isso.
    """
    from financas.calculos import investimentos

    return investimentos.desempenho_da_carteira(mes)


@st.cache_data(ttl=TTL, show_spinner=False)
def carteira_rentabilidade_mensal() -> pd.DataFrame:
    """A grade ano x mes da rentabilidade da carteira."""
    from financas.calculos import investimentos

    return investimentos.rentabilidade_por_mes_e_ano()


@st.cache_data(ttl=TTL, show_spinner=False)
def papel_serie_preco(ticker: str, desde: str | None = None) -> pd.DataFrame:
    """O historico de fechamento diario de um papel com ticker."""
    from financas import cotacoes

    return cotacoes.serie(ticker, desde)


def limpar_cache() -> None:
    """Joga fora tudo que estava guardado, forcando releitura do banco.

    CHAME SEMPRE DEPOIS DE ESCREVER NO BANCO — importar, editar, apagar,
    restaurar backup. Se esquecer, a tela continua mostrando o dado antigo e
    parece que a alteracao nao funcionou.

    SAO DUAS MEMORIAS, E A SEGUNDA E FACIL DE ESQUECER:

      - o cache do Streamlit, que guarda a LEITURA do banco;
      - a memoria de `calculos/parcelas.py`, que guarda um CALCULO derivado.

    A segunda entrou em 2026-08-23 para o Dashboard parar de refazer a mesma
    conta doze vezes por clique. Ela se invalida por uma impressao digital do
    conteudo (tamanho, soma dos valores, soma das parcelas, data maior) — o que
    cobre importacao e exclusao, mas **nao cobre reclassificacao**: mudar a
    categoria de um lancamento nao mexe em nenhum daqueles quatro numeros, e a
    tabela de parcelamentos carrega `categoria` e `grande_categoria`.

    Por isso ela e limpa aqui, explicitamente. Impressao digital resolve o caso
    comum; a limpeza explicita resolve o resto.
    """
    st.cache_data.clear()
    parcelas.limpar_memoria()


def pegar(chave: str, padrao=None):
    """Le um valor do estado da sessao, com padrao se ainda nao existir."""
    return st.session_state.get(chave, padrao)


def guardar(chave: str, valor) -> None:
    """Guarda um valor que precisa sobreviver ao proximo rerun."""
    st.session_state[chave] = valor


def esquecer(chave: str) -> None:
    """Apaga um valor do estado (usado ao cancelar uma importacao)."""
    st.session_state.pop(chave, None)


CHAVE_MES = "mes_selecionado"
CHAVE_WIDGET_MES = "widget_mes_topo"


def mes_selecionado() -> str | None:
    """O mes escolhido, valido em todas as telas.

    Guardar isso no estado (e nao em cada pagina) e o que faz voce trocar o
    mes no Dashboard e o Planejamento ja abrir naquele mesmo mes.

    Pode ser chamada ANTES de o menu ser desenhado — e e o que o Dashboard
    faz, para o titulo ja sair com o mes certo.

    A validacao usa `meses_do_seletor()`, a MESMA lista que o seletor oferece.
    Tem de ser a mesma: se aqui usasse `meses()` (so o passado), escolher um
    mes futuro seria desfeito na mesma execucao — o valor cairia no `if atual
    not in disponiveis` e voltaria para o padrao. O mes escolhido tem de ser
    valido segundo a lista de onde ele veio.
    """
    disponiveis = meses_do_seletor()

    atual = st.session_state.get(CHAVE_WIDGET_MES)

    if not atual or atual not in disponiveis:
        atual = st.session_state.get(CHAVE_MES)

    if atual and atual in disponiveis:
        return atual

    padrao = mes_padrao()
    if padrao:
        guardar(CHAVE_MES, padrao)
    return padrao


def seletor_de_mes_topo() -> str | None:
    """O seletor de mes no TOPO da pagina, com setas para andar mes a mes.

    Fica em cima, e nao na barra lateral, porque o mes e o controle principal
    de quase toda tela — escondido embaixo do menu, ninguem acha.

    As setas existem porque a comparacao mais comum e com o mes anterior:
    clicar em ◀ e mais rapido (e mais obvio) que abrir a lista e procurar.

    POR QUE OS BOTOES SAO CRIADOS ANTES DO MENU
    -------------------------------------------
    Nao e capricho de layout — `st.columns` deixa preencher as colunas em
    qualquer ordem. E que, ao clicar numa seta, precisamos escrever em
    `st.session_state[CHAVE_WIDGET_MES]`, e o Streamlit PROIBE escrever numa
    chave depois que o widget dono dela ja foi criado naquela execucao.

    Criando os botoes primeiro e chamando `st.rerun()` logo em seguida, o menu
    nem chega a ser desenhado naquela passada; na seguinte ele ja nasce com o
    mes novo.

    Sao duas chaves de estado porque o Streamlit descarta a chave de um
    widget quando ele sai da tela, e trocar de pagina faz isso: com uma chave
    so, ir do Dashboard para o Planejamento apagaria o mes escolhido.
    CHAVE_WIDGET_MES tem o valor da execucao atual; CHAVE_MES sobrevive a
    troca de pagina.
    """
    disponiveis = meses_do_seletor()
    if not disponiveis:
        return None

    from financas.formato import rotulo_mes

    ordenados = sorted(disponiveis)
    atual = mes_selecionado()
    posicao = ordenados.index(atual) if atual in ordenados else len(ordenados) - 1

    colunas = st.columns([2, 0.5, 0.5, 5], gap="small",
                         vertical_alignment="bottom")

    with colunas[1]:
        voltar = st.button("◀", key="mes_voltar", disabled=posicao == 0,
                           help="mês anterior", width="stretch")
    with colunas[2]:
        avancar = st.button("▶", key="mes_avancar",
                            disabled=posicao >= len(ordenados) - 1,
                            help="próximo mês", width="stretch")

    if voltar or avancar:
        novo = ordenados[posicao - 1 if voltar else posicao + 1]
        guardar(CHAVE_MES, novo)
        st.session_state[CHAVE_WIDGET_MES] = novo
        st.rerun()

    parametros = {}
    if CHAVE_WIDGET_MES not in st.session_state:
        parametros["index"] = disponiveis.index(atual) if atual in disponiveis else 0

    with colunas[0]:
        st.selectbox(
            "Mês de referência", disponiveis,
            format_func=rotulo_mes, key=CHAVE_WIDGET_MES, **parametros,
        )

    escolhido = st.session_state.get(CHAVE_WIDGET_MES, atual)
    if escolhido:
        guardar(CHAVE_MES, escolhido)
    return escolhido


CHAVE_PERIODO = "periodo_selecionado"
CHAVE_WIDGET_PERIODO = "widget_periodo"
CHAVE_FUTURO = "periodo_inclui_futuro"

PERIODOS = {
    "Últimos 6 meses": 6,
    "Últimos 12 meses": 12,
    "Últimos 24 meses": 24,
    "Tudo": None,
}
PERIODO_PADRAO = "Últimos 12 meses"


def periodo_selecionado() -> str:
    """O rotulo do periodo escolhido. Mesma logica de duas chaves do mes."""
    atual = st.session_state.get(CHAVE_WIDGET_PERIODO)
    if atual not in PERIODOS:
        atual = st.session_state.get(CHAVE_PERIODO)
    return atual if atual in PERIODOS else PERIODO_PADRAO


def inclui_futuro() -> bool:
    """Os graficos devem passar do mes corrente?"""
    valor = st.session_state.get(CHAVE_FUTURO)
    return True if valor is None else bool(valor)


def seletor_de_periodo() -> str:
    """Desenha o controle de periodo na barra lateral. Chame uma vez por tela."""
    from financas.formato import rotulo_mes

    opcoes = list(PERIODOS.keys())
    extras_radio = ({} if CHAVE_WIDGET_PERIODO in st.session_state
                    else {"index": opcoes.index(periodo_selecionado())})
    extras_check = ({} if CHAVE_FUTURO in st.session_state
                    else {"value": True})

    with st.sidebar:
        st.markdown("---")
        st.caption("PERÍODO DOS GRÁFICOS")
        escolha = st.radio(
            "Período", opcoes,
            key=CHAVE_WIDGET_PERIODO,
            label_visibility="collapsed",
            **extras_radio,
        )
        st.checkbox(
            "Incluir meses futuros", key=CHAVE_FUTURO,
            help="Parcelas já contratadas criam lançamentos até dez/2026. "
                 "Ligado, os gráficos mostram esses meses numa faixa cinza, "
                 "para não se confundirem com o que já aconteceu.",
            **extras_check,
        )

        inicio, fim = calcular_limites(meses(), escolha, inclui_futuro())
        if inicio:
            st.caption(f"{rotulo_mes(inicio)} → {rotulo_mes(fim)}")

    guardar(CHAVE_PERIODO, escolha)
    return escolha


def calcular_limites(disponiveis: list[str], rotulo: str,
                     com_futuro: bool) -> tuple[str | None, str | None]:
    """(mes_inicio, mes_fim) do periodo — funcao PURA, sem Streamlit.

    Separada de `limites_do_periodo` de proposito: assim da para testar a
    regra no terminal, sem precisar de uma sessao aberta.

    A PRIMEIRA LINHA E A MAIS IMPORTANTE. `meses()` devolve a lista do mais
    recente para o mais antigo, e esta funcao precisa dela crescente. Sem o
    `sorted`, `disponiveis[-1]` pegava o mes MAIS ANTIGO como fim e a janela
    virava "abr/2024 ate abr/2024" — o grafico inteiro reduzido a um ponto.
    Ordenar aqui deixa a funcao correta para qualquer ordem que chegue, em vez
    de depender de quem chama lembrar disso.
    """
    if not disponiveis:
        return (None, None)

    disponiveis = sorted(disponiveis)
    fim = disponiveis[-1] if com_futuro else dados.mes_corrente()
    ate = [m for m in disponiveis if m <= fim]
    if not ate:
        ate = disponiveis
    fim = ate[-1]

    quantos = PERIODOS.get(rotulo)
    if quantos is None:
        return (ate[0], fim)

    inicio = ate[-quantos] if len(ate) >= quantos else ate[0]
    return (inicio, fim)


def limites_do_periodo() -> tuple[str | None, str | None]:
    """(mes_inicio, mes_fim) do periodo escolhido, lendo o estado da sessao."""
    return calcular_limites(meses(), periodo_selecionado(), inclui_futuro())


def recortar_serie(serie):
    """Corta uma serie mensal (com coluna `mes`) no periodo escolhido."""
    if serie is None or serie.empty or "mes" not in serie.columns:
        return serie
    inicio, fim = limites_do_periodo()
    if inicio is None:
        return serie
    return serie[(serie["mes"] >= inicio) & (serie["mes"] <= fim)]


def recortar_lancamentos(df):
    """Corta um DataFrame de lancamentos no periodo escolhido.

    Usa `mes_competencia`, que e o mes em que o lancamento CONTA — nao a data
    da compra. Uma parcela de uma compra de 2024 que cai em 2026 pertence a
    2026, e e assim que ela tem de aparecer no grafico.
    """
    if df is None or df.empty or "mes_competencia" not in df.columns:
        return df
    inicio, fim = limites_do_periodo()
    if inicio is None:
        return df
    return df[(df["mes_competencia"] >= inicio) & (df["mes_competencia"] <= fim)]
