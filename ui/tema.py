"""
tema.py — A aparencia do app: cores, cartoes, espacamento.
==============================================================================

O QUE ESTE ARQUIVO FAZ
----------------------
O Streamlit ja vem com um visual pronto, mas bem generico. Aqui injetamos CSS
para chegar no visual das referencias que voce escolheu: fundo claro, cartoes
brancos arredondados com sombra suave, azul/indigo de destaque.

O QUE E CSS
-----------
E a linguagem que descreve a APARENCIA de uma pagina: cor, tamanho, borda,
espaco. O Python monta a estrutura ("aqui vai um titulo, ali um numero") e o
CSS decide como isso aparece.

COMO O CSS ENTRA NUMA PAGINA STREAMLIT
--------------------------------------
Pelo `st.markdown(..., unsafe_allow_html=True)`. O nome assusta, mas o
"unsafe" so quer dizer "confie no HTML que estou passando". Como o HTML e
escrito por nos aqui neste arquivo — e nunca montado com texto digitado por
alguem — nao ha risco.

REGRA DE OURO: SEM DADO DO USUARIO DENTRO DE HTML CRU
------------------------------------------------------
Se um lancamento se chamasse `<script>...`, jogar esse texto direto no HTML
seria um problema de seguranca. Por isso `card_kpi()` e companhia passam todo
texto por `escapar_html()` antes de montar a marcacao.
"""

from __future__ import annotations

import html

import streamlit as st

from financas import config


CSS = """
<style>
/* ---------------------------------------------------------------- base -- */
.stApp {
    background-color: %(fundo)s;
}

/* Tira o espaco enorme que o Streamlit deixa no topo da pagina. */
.block-container {
    padding-top: 2.2rem;
    padding-bottom: 3rem;
    max-width: 1400px;
}

/* Esconde o menu de hamburguer e o rodape "Made with Streamlit". */
#MainMenu, footer {visibility: hidden;}

h1, h2, h3, h4 {
    color: %(texto)s;
    font-weight: 700;
    letter-spacing: -0.02em;
}
h1 { font-size: 1.85rem; margin-bottom: .2rem; }
h2 { font-size: 1.25rem; margin-top: 1.6rem; }
h3 { font-size: 1rem; font-weight: 600; margin-top: 1.4rem; }
h4 { font-size: .88rem; font-weight: 600; color: %(texto_fraco)s; }

/* ------------------------------------------------------------ sidebar -- */
/* O FUNDO E AS CORES DOS WIDGETS NAO ESTAO AQUI: estao em `[theme.sidebar]`
   no .streamlit/config.toml. E de la que o Streamlit recolore o radio, o
   checkbox, o expander, o st.code e as captions — coisas que, pintadas so
   pelo CSS, ficariam com texto quase preto sobre o indigo. Aqui fica so o
   que e nosso: espacamento e o bloco da marca. */
section[data-testid="stSidebar"] .block-container { padding-top: 1.5rem; }

.marca { padding: .2rem 0 1.1rem 0; }
.marca-titulo {
    font-size: 1.2rem; font-weight: 700; letter-spacing: -.02em;
    color: %(sidebar_texto)s;
}
.marca-sub { font-size: .78rem; color: %(sidebar_texto_fraco)s; margin-top: .1rem; }

/* O item ativo do menu vira pastilha, em vez de um fundo cinza quase igual
   ao resto. Num menu de 13 linhas, saber onde voce esta e a unica coisa que
   ele precisa responder rapido. */
section[data-testid="stSidebar"] a[data-testid="stSidebarNavLink"] {
    border-radius: 10px;
}
section[data-testid="stSidebar"] a[aria-current="page"] {
    background: %(sidebar_ativo)s !important;
}
section[data-testid="stSidebar"] a[aria-current="page"] span,
section[data-testid="stSidebar"] a[aria-current="page"] * {
    color: #FFFFFF !important;
    font-weight: 600;
}

/* -------------------------------------------------------------- cards -- */
/* A classe .cartao e a base visual de quase tudo: KPI, blocos, avisos. */
/* Uma sombra so, fraca, e nada de levantar no hover.
   A sombra dupla + o `translateY` faziam cada cartao pedir atencao; com
   dezesseis deles na tela, o efeito somado era de template. */
.cartao {
    background: %(cartao)s;
    border: 1px solid %(borda)s;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    box-shadow: 0 1px 2px rgba(15,23,42,.05);
    height: 100%%;
}

.kpi-rotulo {
    font-size: .74rem;
    font-weight: 600;
    letter-spacing: .04em;
    text-transform: uppercase;
    color: %(texto_fraco)s;
    margin-bottom: .35rem;
    display: flex; align-items: center; gap: .35rem;
}
.kpi-valor {
    font-size: 1.62rem;
    font-weight: 700;
    color: %(texto)s;
    line-height: 1.15;
    letter-spacing: -0.03em;
}
.kpi-valor.pequeno { font-size: 1.25rem; }
.kpi-ajuda {
    font-size: .78rem;
    color: %(texto_fraco)s;
    margin-top: .3rem;
    line-height: 1.35;
}
.kpi-delta { font-size: .82rem; font-weight: 600; margin-top: .25rem; }
.positivo { color: %(sucesso)s; }
.negativo { color: %(perigo)s; }
.neutro   { color: %(texto_fraco)s; }

/* A faixa colorida na esquerda do cartao, que diz o estado num relance. */
.cartao.faixa-verde    { border-left: 4px solid %(sucesso)s; }
.cartao.faixa-vermelha { border-left: 4px solid %(perigo)s; }
.cartao.faixa-amarela  { border-left: 4px solid %(alerta)s; }
.cartao.faixa-azul     { border-left: 4px solid %(primaria)s; }

/* ----------------------------------------------------------- destaque -- */
/* A faixa de numeros grandes do topo. Sem moldura de proposito: um numero
   grande sozinho no branco pesa mais que o mesmo numero numa caixa igual a
   outras quinze. O filete vertical separa sem desenhar caixa. */
.destaque {
    display: flex;
    gap: 2.6rem;
    align-items: flex-start;
    flex-wrap: wrap;
    margin: .2rem 0 1.5rem;
}
.destaque-item { position: relative; padding-left: 1.4rem; }
.destaque-item:first-child { padding-left: 0; }
.destaque-item:not(:first-child)::before {
    content: ""; position: absolute; left: 0; top: .35rem; bottom: .35rem;
    width: 1px; background: %(borda)s;
}
.destaque-rotulo {
    font-size: .72rem; font-weight: 600; letter-spacing: .06em;
    text-transform: uppercase; color: %(texto_fraco)s; margin-bottom: .3rem;
}
.destaque-valor {
    font-size: 2.4rem; font-weight: 700; line-height: 1.05;
    letter-spacing: -.035em; color: %(texto)s;
    font-variant-numeric: tabular-nums;
}
.destaque-ajuda {
    font-size: .8rem; color: %(texto_fraco)s; margin-top: .35rem;
}

/* ------------------------------------------------------- estatisticas -- */
/* Numeros de apoio. A ausencia de borda e o que os mantem no segundo plano. */
.estatistica { padding: .1rem 0 .4rem; }
.estatistica-rotulo {
    font-size: .72rem; font-weight: 600; letter-spacing: .04em;
    text-transform: uppercase; color: %(texto_fraco)s; margin-bottom: .2rem;
}
.estatistica-valor {
    font-size: 1.28rem; font-weight: 600; color: %(texto)s;
    letter-spacing: -.02em; line-height: 1.2;
    font-variant-numeric: tabular-nums;
}
.estatistica-ajuda {
    font-size: .76rem; color: %(texto_fraco)s; margin-top: .18rem;
    line-height: 1.35;
}

/* Tons de texto, para destaque/estatistica, que nao tem faixa lateral. */
.tom-verde    { color: %(sucesso)s !important; }
.tom-vermelha { color: %(perigo)s  !important; }
.tom-amarela  { color: %(alerta)s  !important; }
.tom-azul     { color: %(primaria)s !important; }

/* ------------------------------------------------------------ painel --- */
/* O cartao que embrulha um grafico. O `stVerticalBlockBorderWrapper` e o
   `st.container(border=True)` do Streamlit — o mesmo usado pelos cartoes de
   meta. Estilizar ele aqui faz cartao e painel terem UM visual, nao dois
   parecidos. */
/* A classe `st-key-painel_*` vem do `key` que `c.painel()` passa ao
   container. E o unico jeito estavel de achar um `st.container(border=True)`:
   o Streamlit nao o marca com nada alem de um hash de emotion, que muda de
   versao para versao. A borda e o raio ja vem do config.toml; aqui so o fundo
   branco e a sombra, que sao o que transforma a moldura em cartao. */
div[class*="st-key-painel_"],
div[class*="st-key-cartao_"] {
    background: %(cartao)s;
    box-shadow: 0 1px 2px rgba(15,23,42,.05);
    padding: .9rem 1.1rem;
}
/* O EXPANDER TAMBEM E UM CARTAO. Ele ja vinha com borda e canto arredondado
   do config.toml, mas com fundo TRANSPARENTE — o que o deixava como um
   retangulo vazado ao lado de cartoes brancos, na mesma pagina. Superficie de
   conteudo e branca sobre o cinza; e uma regra so, e vale para os 30
   expanders do app. */
div[data-testid="stExpander"] details {
    background: %(cartao)s;
}

.painel-cabeca { margin-bottom: .35rem; }
.painel-titulo {
    font-size: .95rem; font-weight: 600; color: %(texto)s;
    letter-spacing: -.01em; line-height: 1.3;
}
.painel-ajuda {
    font-size: .78rem; color: %(texto_fraco)s; margin-top: .12rem;
    line-height: 1.4;
}

/* -------------------------------------------------------------- selo --- */
/* Fundo claro com texto escuro da mesma familia: le-se como etiqueta, nao
   como botao. Cor cheia faria uma pastilha de status competir com o numero
   que ela esta qualificando. */
.selo {
    display: inline-block; font-size: .72rem; font-weight: 600;
    padding: .1rem .5rem; border-radius: 999px; line-height: 1.5;
    background: #F1F5F9; color: %(texto_fraco)s; white-space: nowrap;
}
/* A legenda do rodape do cartao, onde o selo entra no meio da frase. Repete
   o tamanho e a cor do `st.caption`, porque a frase e a mesma — so deixou de
   ser caption para poder conter HTML. */
.legenda-cartao {
    font-size: .8rem; color: %(texto_fraco)s; line-height: 1.7;
    margin-top: .2rem;
}
.legenda-cartao strong { color: %(texto)s; font-weight: 600; }

.selo-verde    { background: #DCFCE7; color: #166534; }
.selo-vermelha { background: #FEE2E2; color: #991B1B; }
.selo-amarela  { background: #FEF3C7; color: #92400E; }
.selo-azul     { background: #E0E7FF; color: #3730A3; }

/* ------------------------------------------------------------- secao --- */
/* Divisoria, nao titulo. Seis `h3` iguais nao criam hierarquia — criam uma
   lista de blocos igualmente importantes. */
.secao {
    font-size: .78rem; font-weight: 700; letter-spacing: .09em;
    text-transform: uppercase; color: %(texto_fraco)s;
    margin: 2.1rem 0 .9rem; padding-left: .6rem;
    border-left: 3px solid %(primaria)s; line-height: 1.6;
}

/* -------------------------------------------------------------- dica --- */
.dica {
    display: inline-flex; align-items: center; justify-content: center;
    width: 14px; height: 14px; margin-left: .35rem;
    border: 1px solid %(borda)s; border-radius: 50%%;
    font-size: .62rem; font-weight: 700; color: %(texto_fraco)s;
    cursor: help; vertical-align: middle; text-transform: none;
    letter-spacing: 0;
}
.dica:hover { border-color: %(primaria)s; color: %(primaria)s; }

/* ------------------------------------------------------------- tarja --- */
.tarja {
    font-size: .8rem; padding: .5rem .8rem; border-radius: 8px;
    margin: -.4rem 0 1.1rem; display: inline-block;
}
.tarja-aviso { background: #FEF3C7; color: #78350F; }
.tarja-info  { background: #EFF6FF; color: #1E3A5F; }

/* ------------------------------------------------------ barra de meta -- */
.barra-fundo {
    background: #E2E8F0;
    border-radius: 999px;
    height: 8px;
    overflow: hidden;
    margin-top: .45rem;
}
.barra-preenchida { height: 100%%; border-radius: 999px; transition: width .3s ease; }

/* -------------------------------------------------------------- abas --- */
.stTabs [data-baseweb="tab-list"] { gap: .3rem; border-bottom: 1px solid %(borda)s; }
.stTabs [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0;
    padding: .5rem 1rem;
    font-weight: 600;
    font-size: .9rem;
}

/* ------------------------------------------------------------ tabelas -- */
/* Borda e raio saem de `borderColor` e `baseRadius` no config.toml. O que
   sobra aqui e o `overflow`, que corta o conteudo no canto arredondado — sem
   ele a primeira celula vaza para fora da curva. */
div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
    overflow: hidden;
}

/* ------------------------------------------------------------ botoes --- */
/* O raio vem de `baseRadius`; a cor do primario, de `primaryColor`. Aqui so
   o peso do texto e a transicao. */
.stButton > button {
    font-weight: 600;
    transition: all .15s ease;
}

/* ------------------------------------------------ metricas do Streamlit - */
div[data-testid="stMetric"] {
    background: %(cartao)s;
    border: 1px solid %(borda)s;
    border-radius: 14px;
    padding: .85rem 1rem;
    box-shadow: 0 1px 2px rgba(15,23,42,.04);
}
div[data-testid="stMetricLabel"] p {
    font-size: .74rem !important;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .04em;
    color: %(texto_fraco)s;
}

/* O VALOR ENCOLHE PARA CABER, EM VEZ DE SER CORTADO.
   O padrao do Streamlit e `font-size: 36px` com `white-space: nowrap` e
   `text-overflow: ellipsis`. Numa caixa estreita (157px nos cartoes de meta),
   "R$ 1.000.000,00" ocupa 234px e vira "R$ 1.000.0…".
   Num painel de dinheiro isso nao e so feio, e ERRADO: os digitos sumidos nao
   deixam rastro, e "R$ 1.000.0…" se le como mil reais e pouco.
   `cqi` = 1%% da largura do CONTAINER (o proprio cartao da metrica, marcado
   com `container-type` abaixo). Entao a fonte acompanha a caixa: 22px numa de
   157px, e o teto de 2.25rem devolve o tamanho original nas caixas largas.
   E se ainda assim nao couber — um numero absurdamente longo —, `white-space:
   normal` faz o texto QUEBRAR em duas linhas. Ficar feio e aceitavel; perder
   digito, nao. */
div[data-testid="stMetric"] { container-type: inline-size; }
div[data-testid="stMetricValue"],
div[data-testid="stMetricValue"] > div {
    font-size: 1.4rem !important;                       /* navegador sem cqi */
    font-size: clamp(0.95rem, 14cqi, 2.25rem) !important;
    line-height: 1.15 !important;
    white-space: normal !important;
    overflow-wrap: anywhere;
    text-overflow: clip !important;
}

/* --------------------------------------------------------- cabecalho --- */
.cabecalho-pagina {
    display: flex; align-items: flex-start; justify-content: space-between;
    gap: 1rem; margin-bottom: 1.1rem;
}
.cabecalho-titulo { font-size: 1.85rem; font-weight: 700; letter-spacing: -.03em;
                    color: %(texto)s; margin: 0; }
.cabecalho-sub { color: %(texto_fraco)s; font-size: .92rem; margin-top: .2rem; }

/* ------------------------------------------------------------ divisor -- */
hr { border-color: %(borda)s; margin: 1.6rem 0 1.2rem; }

/* ------------------------------------------------------------ caixinha - */
.nota {
    background: #F8FAFC;
    border: 1px solid %(borda)s;
    border-left: 4px solid %(primaria)s;
    border-radius: 10px;
    padding: .7rem .9rem;
    font-size: .86rem;
    color: %(texto_fraco)s;
    line-height: 1.5;
}
.nota strong { color: %(texto)s; }
</style>
"""


def aplicar() -> None:
    """Injeta o CSS na pagina. Chame uma vez, no comeco de cada tela.

    O `%` no fim substitui os marcadores `%(primaria)s` do CSS pelas cores
    definidas em `config.CORES_TEMA` — assim as cores vivem num lugar so e
    valem para o CSS e para os graficos ao mesmo tempo.

    (Repare que no CSS acima os `%` literais aparecem dobrados: `100%%`. E
    porque `%` e o caractere de substituicao; dobrar significa "quero um
    sinal de porcentagem de verdade aqui".)
    """
    st.markdown(CSS % config.CORES_TEMA, unsafe_allow_html=True)


def escapar_html(texto) -> str:
    """Deixa qualquer texto seguro para entrar dentro de HTML.

    Troca `<` por `&lt;`, `&` por `&amp;` e assim por diante. Se a descricao de
    um lancamento tiver um sinal de menor, ela aparece como texto em vez de
    ser interpretada como marcacao.

    Use SEMPRE que colocar conteudo variavel dentro de um `st.markdown` com
    `unsafe_allow_html=True`.
    """
    if texto is None:
        return ""
    return html.escape(str(texto))
