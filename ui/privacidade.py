"""privacidade.py — o olhinho: esconder os valores em R$ com um clique.

==============================================================================

O QUE ISTO E, E O QUE ISTO NAO E
--------------------------------
Isto NAO e seguranca. Nao ha senha, nao ha login, e nao deve haver: o banco e
um arquivo local que qualquer pessoa com acesso a este computador abre com um
programa gratuito. Uma senha na tela do Streamlit prometeria uma protecao que
ela nao entrega — e uma promessa falsa e pior que nenhuma.

O que isto e: uma cortina contra o OMBRO. Alguem sentou do lado, voce vai
compartilhar a tela numa reunião, o tablet ficou aberto na mesa. Um clique
esconde os valores, outro traz de volta. E exatamente esse problema, e so ele.

O ESTADO E POR APARELHO, E ISSO E DE PROPOSITO
-----------------------------------------------
A escolha mora em `st.session_state`, que no Streamlit e por SESSAO — ou seja,
por aba de navegador. Como este app aceita conexoes da rede local, o celular e
o computador sao sessoes diferentes: da para deixar o celular escondido e o
computador mostrando, ao mesmo tempo. Guardar no banco faria o contrario, e
seria pior: esconder no celular apagaria os numeros da sua propria tela.

Pelo mesmo motivo, a escolha se perde quando voce recarrega a pagina ou o app
reinicia. E ai vale o padrao seguro: **sessao nova nasce ESCONDIDA**.

A primeira versao abria mostrando, com o argumento de que um painel escondido
faz voce clicar toda vez. O argumento e verdadeiro e nao importa: o primeiro
desenho da tela e justamente o unico que voce nao controla, e se ele mostrar
os valores o painel ja vazou antes de voce poder reagir. Recurso de
privacidade falha FECHADO. Ele pediu a troca em 2026-08-28, e estava certo.

O QUE FICA ESCONDIDO
--------------------
    valores em R$        em cartao, texto, tabela, rotulo e tooltip
    valores nos graficos rotulo do eixo de valor, texto na barra, tooltip

O QUE CONTINUA VISIVEL, E POR QUE
---------------------------------
    percentuais          "38% em renda fixa" nao revela quanto voce tem, e sem
                         eles o grafico de alocacao vira enfeite
    quantidades          "18 papeis", "142 lancamentos" — contagem nao e valor
    datas e categorias   sao o unico jeito de continuar navegando

A FORMA DO NUMERO PERMANECE
---------------------------
A mascara e `R$ ••••`, e nao um espaco em branco. Uma celula vazia parece
defeito; a mascara diz "tem um valor aqui, e voce escolheu nao ver".

COMO USAR NUMA TELA NOVA
------------------------
    from ui import privacidade as priv

    priv.fmt_brl(1234.5)                 no lugar de formato.fmt_brl
    priv.fmt_brl_md(1234.5)              dentro de st.caption / st.markdown
    priv.grafico(fig)                    no lugar de st.plotly_chart
    priv.coluna_dinheiro("Valor")        no lugar de st.column_config.NumberColumn
    priv.mascarar(df, ["valor"])         antes de st.dataframe
    priv.editor(df, colunas_dinheiro=[]) no lugar de st.data_editor
"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from financas import formato

CHAVE = "valores_ocultos"

COMECA_OCULTO = True

MASCARA = "R$ ••••"
MASCARA_MD = "R\\$ ••••"
MASCARA_USD = "US$ ••••"

_DINHEIRO = re.compile(r"-?(?:US)?R?\\?\$\s?[\d.]+,\d{2}")


def ocultando() -> bool:
    """Diz se os valores estao escondidos nesta sessao.

    Sessao nova nasce ESCONDIDA (`COMECA_OCULTO`). O primeiro desenho da tela
    e o unico que voce nao controla — se ele mostrasse os valores, o painel
    ja teria vazado antes de voce poder clicar em qualquer coisa. Um recurso
    de privacidade falha FECHADO.

    O preco e um clique por abertura, porque o estado morre junto com a aba.
    Foi por isso que a primeira versao abria mostrando; era otimizar conforto
    num recurso que existe para proteger — e ele pediu o contrario, com razao.
    """
    return bool(st.session_state.get(CHAVE, COMECA_OCULTO))


def alternar() -> None:
    """Inverte o estado do olhinho."""
    st.session_state[CHAVE] = not ocultando()


def botao() -> None:
    """Desenha o olhinho no TOPO da barra lateral, logo abaixo do menu.

    Fica na barra lateral, e nao dentro de cada tela, porque a escolha vale
    para o app inteiro: esconder no Dashboard e navegar para o Patrimonio nao
    pode revelar nada.

    E fica no TOPO porque, desde que a sessao passou a nascer escondida
    (`COMECA_OCULTO`), este virou o primeiro clique de toda abertura. Botao
    que se usa sempre nao mora no rodape.

    Quando os valores estao ocultos ele sai em destaque (`type="primary"`):
    a acao disponivel e "mostrar", e ela deve saltar aos olhos.
    """
    escondido = ocultando()
    with st.sidebar:
        st.button(
            "👁 Mostrar valores" if escondido else "🙈 Esconder valores",
            key="botao_privacidade",
            use_container_width=True,
            type="primary" if escondido else "secondary",
            on_click=alternar,
            help=("Esconde os valores em R$ desta aba do navegador. "
                  "Não é senha: serve para quem está olhando por cima do seu "
                  "ombro, não para proteger o arquivo."),
        )


def fmt_brl(valor, sinal: bool = False) -> str:
    """`formato.fmt_brl`, mascarado quando o olhinho esta ligado."""
    if ocultando():
        return MASCARA
    return formato.fmt_brl(valor, sinal)


def fmt_brl_md(valor, sinal: bool = False) -> str:
    """`formato.fmt_brl_md`, mascarado quando o olhinho esta ligado.

    A mascara sai com o cifrao escapado pelo mesmo motivo que o valor de
    verdade: dois cifroes soltos num texto markdown viram formula LaTeX no
    Streamlit, e o trecho do meio desaparece da tela.
    """
    if ocultando():
        return MASCARA_MD
    return formato.fmt_brl_md(valor, sinal)


def texto(frase: str) -> str:
    r"""Mascara os valores em R$ de uma frase que ja veio pronta.

    POR QUE ISTO PRECISA EXISTIR: duas funcoes de `financas/` devolvem FRASE, e
    nao numero — `previsao.rotulo()` e `planejamento.alertas_da_projecao()`.
    Elas formatam o dinheiro la dentro, e nao podem consultar o olhinho: nada
    em `financas/` importa Streamlit, e essa regra vale mais do que a
    conveniencia. Entao a mascara e aplicada aqui, na saida.

    Reconhece as tres formas em que o dinheiro sai do projeto: `R$ ····`, a
    versao escapada para markdown `R\$ R$ ····`, e `R$ ····`.

    **E a moeda e preservada na mascara.** A primeira versao trocava tudo por
    `R$ ••••`, inclusive os dolares — escondia o numero e mentia o rotulo, que
    e o pior dos dois mundos: quem le continua sendo informado, e informado
    errado.
    """
    if not ocultando() or not frase:
        return frase

    def _trocar(achado):
        texto_achado = achado.group(0)
        if "US$" in texto_achado:
            return MASCARA_USD
        return MASCARA_MD if "\\" in texto_achado else MASCARA

    return _DINHEIRO.sub(_trocar, frase)


def fmt_usd(valor, sinal: bool = False) -> str:
    """`formato.fmt_usd`, mascarado quando o olhinho esta ligado.

    Precisa ser separada de `fmt_brl`: usar a mascara de real num valor em
    dolar diria a moeda ERRADA com o numero escondido — o pior dos dois
    mundos, porque o rotulo continua informando, e informa errado.
    """
    if ocultando():
        return MASCARA_USD
    return formato.fmt_usd(valor, sinal)


def mascarar(tabela: pd.DataFrame, colunas) -> pd.DataFrame:
    """Devolve a tabela com as colunas de dinheiro trocadas pela mascara.

    Sempre devolve uma COPIA: a tabela original continua com os numeros, e e
    dela que qualquer conta posterior tem de sair. Trocar no lugar faria o
    olhinho mudar o resultado de um calculo, que e exatamente o que ele nao
    pode fazer.

    Coluna que nao existe na tabela e ignorada em silencio — as telas montam
    colunas condicionalmente, e uma lista fixa nao teria como acompanhar.
    """
    if not ocultando():
        return tabela
    copia = tabela.copy()
    for coluna in colunas:
        if coluna in copia.columns:
            copia[coluna] = MASCARA
    return copia


def colunas_de_dinheiro(column_config) -> list[str]:
    """Acha, na configuracao de colunas, quais mostram dinheiro.

    POR QUE DESCOBRIR EM VEZ DE PERGUNTAR: sao mais de 50 tabelas no app, e
    uma lista de nomes por tela envelheceria na primeira coluna nova — em
    silencio, mostrando um valor que devia estar escondido.

    O `st.column_config.NumberColumn(...)` devolve um dicionario comum, com o
    formato dentro de `type_config`. Toda coluna em R$ deste projeto nasce com
    `format="R$ %.2f"` (direto ou via `componentes.config_moeda`), entao o
    proprio formato identifica a coluna. **A convencao virou contrato**: coluna
    de dinheiro declarada de outro jeito nao sera escondida.

    A MINICURVA TAMBEM CONTA. `LineChartColumn` desenha a serie de saldos de um
    papel e nao tem `format` nenhum — passaria batido pela regra do "R$" e
    deixaria a FORMA do patrimonio a mostra, que e quase tanto quanto o numero.
    Por isso o tipo `line_chart` entra aqui pelo tipo, e nao pelo formato.
    """
    achadas = []
    for nome, config in (column_config or {}).items():
        if not isinstance(config, dict):
            continue
        tipo = config.get("type_config") or {}
        formatacao = str(tipo.get("format") or "").replace("\\", "")
        if ("R$" in formatacao or "US$" in formatacao
                or tipo.get("type") in ("line_chart", "area_chart",
                                        "bar_chart")):
            achadas.append(nome)
    return achadas


def _config_mascarada(column_config, colunas):
    """Troca as colunas de dinheiro por colunas de texto, preservando o rotulo."""
    nova = dict(column_config or {})
    for nome in colunas:
        original = nova.get(nome) or {}
        nova[nome] = st.column_config.TextColumn(
            original.get("label") or nome,
            help=original.get("help"),
            disabled=True,
        )
    return nova


def coluna_dinheiro(rotulo: str, ajuda: str | None = None, **kwargs):
    """A configuracao de uma coluna em R$.

    E so um atalho para `st.column_config.NumberColumn` com o formato do
    projeto. Quem esconde e `tabela()` / `editor()`, na hora de desenhar —
    aqui a coluna continua numerica, porque a mesma configuracao e usada para
    calcular larguras e limites.
    """
    return st.column_config.NumberColumn(rotulo, format="R$ %.2f",
                                         help=ajuda, **kwargs)


def tabela(dados, **kwargs) -> None:
    """`st.dataframe` que respeita o olhinho.

    As colunas em R$ sao descobertas pelo `column_config` (ver
    `colunas_de_dinheiro`), mascaradas nos dados e trocadas por texto na
    configuracao. Tabela sem `column_config` passa direto: se ela mostra
    dinheiro, e porque ja veio formatada por `fmt_brl`, que mascara sozinho.
    """
    if ocultando():
        colunas = colunas_de_dinheiro(kwargs.get("column_config"))
        if colunas:
            if isinstance(dados, pd.DataFrame):
                dados = mascarar(dados, colunas)
            kwargs["column_config"] = _config_mascarada(
                kwargs.get("column_config"), colunas)
    st.dataframe(dados, **kwargs)


def grafico(fig, **kwargs) -> None:
    """Desenha o grafico, sem valores quando o olhinho esta ligado.

    Tira tres coisas, e as tres precisam sair juntas — deixar uma so ja
    entrega o numero:

      1. os rotulos do EIXO DE VALOR;
      2. o texto escrito sobre as barras;
      3. o tooltip do mouse.

    O texto ESCRITO NO MEIO do grafico (o total no buraco da rosca) e
    anotacao de layout, nao dado de serie — `update_traces` nao o alcanca, e
    por isso ele passa por `texto()` um a um.

    GRAFICO DE PERCENTUAL PASSA INTEIRO. Um grafico cujos valores sao
    porcentagem — alocacao contra meta, rentabilidade por papel, taxa de
    poupanca — nao revela quanto voce tem, e esconder o eixo dele so deixaria a
    tela ilegivel sem proteger nada. Quem sabe disso e o proprio grafico, que
    se marca com `fig.update_layout(meta={"valores": "percentual"})`. A marca e
    explicita de proposito: adivinhar pelo `ticksuffix` erraria no dia em que
    um grafico misturasse os dois.

    QUAL EIXO E O DE VALOR, sem precisar dizer: quem tem `orientation="h"` e
    barra deitada, e ali o valor esta no X; todo o resto tem o valor no Y. A
    resposta vem dos DADOS da figura, nao de uma lista de nomes de funcao que
    envelheceria na proxima tela.

    A primeira versao disto perguntava ao `tickprefix` do eixo Y, e estava
    errada: os graficos deitados zeram esse prefixo, mas `_estilo()` roda
    DEPOIS e o repoe. Todos os graficos chegavam aqui com `"R$ "`, e nos
    deitados o codigo escondia o eixo das categorias enquanto os valores
    seguiam na tela. O `conferir_privacidade` pegou.
    """
    if ocultando():
        esconder_valores_da_figura(fig)
    st.plotly_chart(fig, **kwargs)


# As figuras que passam inteiras pelo olhinho, porque nao ha dinheiro nelas.
#
#   "percentual"    o eixo e porcentagem — alocacao contra meta, ritmo da meta,
#                   rentabilidade. Esconder isso deixaria a tela ilegivel sem
#                   proteger nada: 68% nao diz quanto voce tem.
#   "sem_dinheiro"  o grafico mede outra unidade — o calendario de compras mede
#                   MESES DE ESPERA. Marca separada de proposito: chamar meses
#                   de "percentual" so para reaproveitar a excecao esconderia,
#                   no nome, a razao pela qual a excecao existe.
#
# A marca e sempre EXPLICITA, escrita pela funcao que monta a figura. Adivinhar
# pela aparencia do eixo erraria no dia em que um grafico misturasse os dois.
_MARCAS_SEM_DINHEIRO = ("percentual", "sem_dinheiro")


def esconder_valores_da_figura(fig):
    """Tira da figura tudo que mostra dinheiro, e devolve a propria figura.

    Esta separada de `grafico()` por um motivo so: `grafico()` termina em
    `st.plotly_chart`, que exige uma execucao do Streamlit, e assim
    `verificacao/conferir_privacidade.py` consegue conferir o tratamento de
    verdade em vez de uma copia dele.
    """
    marca = getattr(fig.layout, "meta", None) or {}
    if isinstance(marca, dict) and marca.get("valores") in _MARCAS_SEM_DINHEIRO:
        return fig

    deitado = any(getattr(serie, "orientation", None) == "h"
                  for serie in fig.data)
    if deitado:
        fig.update_xaxes(showticklabels=False)
    else:
        fig.update_yaxes(showticklabels=False)
    fig.update_traces(texttemplate=None, text=None,
                      hovertemplate=None, hoverinfo="skip")
    fig.update_layout(hovermode=False)
    for anotacao in fig.layout.annotations or ():
        if anotacao.text:
            anotacao.text = texto(anotacao.text)
    return fig


def editor(dados, **kwargs):
    """`st.data_editor` que respeita o olhinho, sem impedir a edicao do resto.

    Com o olhinho ligado, as colunas em R$ ficam mascaradas e travadas, e as
    outras continuam editaveis: da para corrigir a categoria de um lancamento
    sem que o valor apareca na tela.

    O PONTO DELICADO E O RETORNO. O `st.data_editor` devolve o que esta na
    tela — e o que esta na tela e `R$ ••••`. Se esse texto seguisse para o
    codigo que salva, a proxima gravacao escreveria a mascara onde havia
    dinheiro. **Um recurso de esconder valores nunca pode alterar valores.**
    Por isso, antes de devolver, as colunas mascaradas voltam a ter os numeros
    de origem, casadas pelo indice.

    Linha NOVA (nos editores com `num_rows="dynamic"`) nao existe no indice de
    origem e fica sem valor — que e o mesmo que teria se voce criasse a linha
    com o campo em branco.
    """
    if not ocultando():
        return st.data_editor(dados, **kwargs)

    colunas = colunas_de_dinheiro(kwargs.get("column_config"))
    if not colunas or not isinstance(dados, pd.DataFrame):
        return st.data_editor(dados, **kwargs)

    kwargs["column_config"] = _config_mascarada(kwargs.get("column_config"),
                                                colunas)
    editado = st.data_editor(mascarar(dados, colunas), **kwargs)

    editado = editado.copy()
    comuns = editado.index.intersection(dados.index)
    for coluna in colunas:
        editado[coluna] = pd.NA
        editado.loc[comuns, coluna] = dados.loc[comuns, coluna]
    return editado
