"""
componentes.py — Pecas visuais reaproveitadas em todas as telas.
==============================================================================

POR QUE ISTO EXISTE
-------------------
O cartao de indicador aparece umas 40 vezes no app. Se cada pagina montasse o
seu, seriam 40 copias do mesmo HTML — e mudar a aparencia significaria editar
40 lugares (e esquecer alguns).

Aqui cada peca e uma funcao. A pagina escreve:

    componentes.card_kpi("Saldo do mês", fmt_brl(4467.61), cor="verde")

e nao precisa saber nada de HTML.

REGRA DE SEGURANCA
------------------
Todo texto que vem de fora (descricao de lancamento, nome de categoria) passa
por `escapar_html()` antes de entrar no HTML. Ver a explicacao em ui/tema.py.
"""

from __future__ import annotations

from contextlib import contextmanager

import streamlit as st

from financas import config
from financas.formato import fmt_pct, normalizar_texto, vazio
from ui.privacidade import fmt_brl
from ui.tema import escapar_html

FAIXAS = {
    "verde": "faixa-verde",
    "vermelha": "faixa-vermelha",
    "amarela": "faixa-amarela",
    "azul": "faixa-azul",
    None: "",
}

TONS = {
    "verde": "tom-verde",
    "vermelha": "tom-vermelha",
    "amarela": "tom-amarela",
    "azul": "tom-azul",
    None: "",
}


def _marca_dica(dica: str) -> str:
    """O '?' discreto que guarda a explicacao no `title` do HTML.

    POR QUE ISTO EXISTE: as explicacoes longas ("cada barra e um dia do mes,
    concentracao no comeco costuma ser conta fixa...") sao uteis na primeira
    vez e viram ruido na centesima. Aqui elas continuam a um passe de mouse de
    distancia, sem ocupar uma linha na tela.
    """
    if not dica:
        return ""
    return f'<span class="dica" title="{escapar_html(dica)}">?</span>'


def cabecalho(titulo: str, subtitulo: str = "", icone: str = "") -> None:
    """O titulo grande no topo de cada pagina."""
    st.markdown(
        f"""
        <div class="cabecalho-pagina">
          <div>
            <p class="cabecalho-titulo">{escapar_html(icone)} {escapar_html(titulo)}</p>
            <div class="cabecalho-sub">{escapar_html(subtitulo)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def card_kpi(rotulo: str, valor: str, ajuda: str = "", delta: str = "",
             delta_positivo: bool | None = None, cor: str | None = None,
             pequeno: bool = False, dica: str = "") -> None:
    """Desenha um cartao com um numero grande.

    Parametros:
        rotulo  o titulo pequeno em cima ("SALDO DO MÊS")
        valor   o numero grande, JA FORMATADO ("R$ ····")
        ajuda   a linha explicativa embaixo
        delta   a variacao ("+16,5% vs média 3M")
        delta_positivo  True pinta de verde, False de vermelho, None de cinza.
                        Fica separado do texto porque nem sempre "para cima" e
                        bom: gasto subindo e ruim, receita subindo e boa. Quem
                        chama decide o significado.
        cor     "verde" | "vermelha" | "amarela" | "azul" — a faixa lateral
        dica    texto longo que vira um "?" ao lado do rotulo

    QUANDO USAR ESTE E QUANDO USAR `estatisticas`: o cartao chama atencao, e
    so funciona se for excecao. Numa tela com dezesseis cartoes iguais nenhum
    deles destaca nada — foi o que aconteceu com o Dashboard ate 2026-08-22.
    Para o numero de apoio, use `estatisticas`, que nao tem moldura.
    """
    classe_faixa = FAIXAS.get(cor, "")
    classe_valor = "kpi-valor pequeno" if pequeno else "kpi-valor"

    partes = [
        f'<div class="cartao {classe_faixa}">',
        f'<div class="kpi-rotulo">{escapar_html(rotulo)}{_marca_dica(dica)}</div>',
        f'<div class="{classe_valor}">{escapar_html(valor)}</div>',
    ]
    if delta:
        classe_delta = (
            "positivo" if delta_positivo is True
            else "negativo" if delta_positivo is False
            else "neutro"
        )
        partes.append(
            f'<div class="kpi-delta {classe_delta}">{escapar_html(delta)}</div>')
    if ajuda:
        partes.append(f'<div class="kpi-ajuda">{escapar_html(ajuda)}</div>')
    partes.append("</div>")

    st.markdown("".join(partes), unsafe_allow_html=True)


def linha_kpis(itens: list[dict]) -> None:
    """Desenha varios cartoes lado a lado, em colunas de largura igual.

    `itens` e uma lista de dicionarios com os mesmos campos de `card_kpi`.
    Usar isto em vez de montar as colunas a mao garante espacamento igual em
    todas as telas.
    """
    if not itens:
        return
    colunas = st.columns(len(itens), gap="small")
    for coluna, item in zip(colunas, itens):
        with coluna:
            card_kpi(**item)


def destaque(itens: list[dict]) -> None:
    """A faixa de numeros grandes do topo — dois ou tres, no maximo.

    E o "onde eu estou" da tela: o que voce quer saber antes de qualquer
    detalhe. Sem moldura, sem sombra, separados por um filete vertical.

    A ausencia de cartao E o desenho. Um numero grande e sozinho no branco
    pesa mais que o mesmo numero dentro de uma caixa igual a outras quinze.

    Cada item aceita: rotulo, valor, ajuda, cor, dica.
    """
    if not itens:
        return
    blocos = []
    for item in itens:
        tom = TONS.get(item.get("cor"), "")
        partes = [
            f'<div class="destaque-item">',
            f'<div class="destaque-rotulo">{escapar_html(item["rotulo"])}'
            f'{_marca_dica(item.get("dica", ""))}</div>',
            f'<div class="destaque-valor {tom}">{escapar_html(item["valor"])}</div>',
        ]
        if item.get("ajuda"):
            partes.append(
                f'<div class="destaque-ajuda">{escapar_html(item["ajuda"])}</div>')
        partes.append("</div>")
        blocos.append("".join(partes))

    st.markdown(f'<div class="destaque">{"".join(blocos)}</div>',
                unsafe_allow_html=True)


def estatisticas(itens: list[dict]) -> None:
    """Numeros de apoio, lado a lado, SEM moldura.

    A diferenca para `linha_kpis` e so visual, e e o ponto: rotulo pequeno em
    cima, valor medio embaixo, nada de borda, sombra ou faixa colorida. Serve
    para os quatro ou cinco numeros que sustentam a leitura sem disputar
    atencao com o principal.

    Cada item aceita: rotulo, valor, ajuda, cor, dica.
    """
    if not itens:
        return
    colunas = st.columns(len(itens), gap="medium")
    for coluna, item in zip(colunas, itens):
        with coluna:
            tom = TONS.get(item.get("cor"), "")
            partes = [
                '<div class="estatistica">',
                f'<div class="estatistica-rotulo">{escapar_html(item["rotulo"])}'
                f'{_marca_dica(item.get("dica", ""))}</div>',
                f'<div class="estatistica-valor {tom}">'
                f'{escapar_html(item["valor"])}</div>',
            ]
            if item.get("ajuda"):
                partes.append(
                    f'<div class="estatistica-ajuda">'
                    f'{escapar_html(item["ajuda"])}</div>')
            partes.append("</div>")
            st.markdown("".join(partes), unsafe_allow_html=True)


def _chave_de_painel(titulo: str, chave: str | None) -> str:
    """O `key` do container, que o Streamlit transforma na classe `st-key-…`.

    E por essa classe que o CSS acha o cartao. Sem ela nao ha como distinguir
    um `st.container(border=True)` dos outros 45 blocos verticais da pagina:
    o Streamlit nao marca o container com borda de nenhuma forma estavel — so
    com um hash de emotion, que muda de versao para versao.
    """
    if chave:
        return f"painel_{chave}"
    bruto = normalizar_texto(titulo).replace(" ", "_")
    return f"painel_{''.join(ch for ch in bruto if ch.isalnum() or ch == '_')}"


@contextmanager
def painel(titulo: str = "", ajuda: str = "", dica: str = "",
           chave: str | None = None):
    """Um cartao branco com titulo, para o grafico (ou a tabela) morar dentro.

    Use como bloco:

        with c.painel("Da receita ao saldo"):
            priv.grafico(graficos.cascata_do_mes(...))

    POR QUE ISTO EXISTE. Ate agora o padrao era um `st.markdown("#### titulo")`
    solto e, embaixo, o grafico solto no fundo cinza. Funciona, mas nada diz
    onde um assunto termina e o outro comeca: com oito graficos na tela, a
    pagina vira uma lista de desenhos empilhados.

    O cartao e o que faz o titulo PERTENCER ao grafico. E o mesmo motivo pelo
    qual as referencias de dashboard que ele mandou tem tudo dentro de caixa —
    nao e enfeite, e agrupamento.

    ELE NAO ACRESCENTA INFORMACAO: o titulo que vai aqui e o mesmo `####` que
    ja estava na linha de cima. Muda de lugar, nao de conteudo.

    Por dentro e o `st.container(border=True)` do proprio Streamlit — o mesmo
    que os cartoes de meta ja usavam. Assim o visual de cartao e um so, e nao
    dois parecidos que um dia divergem.

    `chave` so e necessaria quando o painel nao tem titulo (o titulo vira a
    chave sozinho). Duas chaves iguais na mesma tela derrubam o Streamlit, que
    e o jeito dele de avisar — melhor do que dois cartoes disputando estado.
    """
    with st.container(border=True, key=_chave_de_painel(titulo, chave)):
        if titulo:
            partes = [
                '<div class="painel-cabeca">',
                f'<div class="painel-titulo">{escapar_html(titulo)}'
                f'{_marca_dica(dica)}</div>',
            ]
            if ajuda:
                partes.append(
                    f'<div class="painel-ajuda">{escapar_html(ajuda)}</div>')
            partes.append("</div>")
            st.markdown("".join(partes), unsafe_allow_html=True)
        yield


def ids_removidos(editado, original) -> list[int]:
    """Quais `id` do banco sumiram da tabela editada.

    Separada de `guarda_de_exclusao` porque e a UNICA parte que decide o que
    vai ser apagado — e, sozinha, ela nao toca no Streamlit, entao da para
    provar num script (ver `verificacao/conferir_exclusao.py`). O resto e
    aviso e caixa de marcar.

    Uma linha NOVA nao tem `id` (vem `NaN`), e por isso `dropna()`: sem ele, o
    `int(NaN)` quebraria — e uma linha que voce acabou de criar nunca pode
    contar como "linha que sumiu".
    """
    if original is None or original.empty:
        return []
    if editado is None or "id" not in getattr(editado, "columns", []):
        return []
    na_tela = {int(i) for i in editado["id"].dropna()}
    return [int(i) for i in original["id"] if int(i) not in na_tela]


def guarda_de_exclusao(editado, original, coluna_nome: str, singular: str,
                       chave: str) -> tuple[list[int], bool]:
    """Pergunta antes de deixar a tabela apagar o que sumiu dela.

    O `st.data_editor` com `num_rows="dynamic"` deixa remover linhas, e o
    padrao do app sempre foi: o `id` que sumiu da tela vira `DELETE` no
    Salvar. Silenciosamente. E o tipo de comportamento que ninguem descobre
    ate o dia em que perde alguma coisa — foi exatamente a duvida dele que
    trouxe isto a tona ("e se eu apagar uma linha?").

    Chame LOGO DEPOIS do editor e ANTES do botao de salvar: o Streamlit
    desenha de cima para baixo, e o aviso precisa existir na tela antes de
    voce ter onde clicar.

        sumiram, pode_apagar = c.guarda_de_exclusao(
            editado, cadastro, "item", "gasto fixo", "confirmar_exclusao_fixos")

    Devolve `(ids_removidos, confirmado)`. Sem a confirmacao, quem chama deve
    NAO apagar — as linhas voltam a aparecer no proximo desenho, que e a
    forma mais clara de dizer "nao apaguei".

    `coluna_nome` e a coluna que da nome a linha, para o aviso citar o que
    vai sumir: "«Aluguel», «Internet»" diz muito mais que "2 linhas".
    """
    sumiram = ids_removidos(editado, original)
    if not sumiram:
        return [], False

    nomes = ", ".join(
        f"«{escapar_html(str(original[original['id'] == i][coluna_nome].iloc[0]))}»"
        for i in sumiram)
    st.warning(
        f"Você removeu {len(sumiram)} linha(s) da tabela: {nomes}. "
        f"Salvar sem marcar a caixa abaixo **mantém** {'esse' if len(sumiram) == 1 else 'esses'} "
        f"{singular}{'' if len(sumiram) == 1 else 's'} no banco — "
        f"{'ele volta' if len(sumiram) == 1 else 'eles voltam'} a aparecer na tabela.")
    confirmado = st.checkbox(
        f"Confirmo apagar {len(sumiram)} {singular}{'' if len(sumiram) == 1 else 's'} "
        f"do banco", key=chave)
    return sumiram, confirmado


def selo(texto: str, cor: str | None = None) -> str:
    """A pastilha de status. DEVOLVE o HTML, nao desenha.

    Devolve em vez de desenhar porque o selo quase nunca aparece sozinho: ele
    entra no meio de uma frase que ja existe ("27,4% concluido · ... · no
    ritmo"). Uma funcao que desenhasse quebraria a linha em duas.

    Quem chama monta a frase e passa por `st.markdown(..., unsafe_allow_html)`.
    O texto do selo vai escapado daqui, entao pode vir do banco sem medo.

    `cor`: "verde" | "vermelha" | "amarela" | "azul" | None (neutro).
    """
    classe = f"selo selo-{cor}" if cor in FAIXAS and cor else "selo"
    return f'<span class="{classe}">{escapar_html(texto)}</span>'


def secao(titulo: str, dica: str = "") -> None:
    """O titulo de uma secao — menor que um h3, com um filete a esquerda.

    Seis `### Titulo` seguidos, todos do mesmo tamanho, nao criam hierarquia
    nenhuma: a tela vira uma lista de blocos igualmente importantes. Este
    componente da o tom de "divisoria", nao de "titulo".
    """
    st.markdown(
        f'<div class="secao">{escapar_html(titulo)}{_marca_dica(dica)}</div>',
        unsafe_allow_html=True)


def tarja(texto: str, tipo: str = "aviso") -> None:
    """Uma faixa fina de contexto, discreta. `tipo`: "aviso" | "info"."""
    st.markdown(
        f'<div class="tarja tarja-{escapar_html(tipo)}">{escapar_html(texto)}</div>',
        unsafe_allow_html=True)


def barra(percentual: float, cor: str | None = None, teto: float = 1.0) -> None:
    """Uma barrinha de progresso fina, colorida conforme o quanto foi usado.

    Quando nao se informa a cor, ela e escolhida sozinha:
        ate 80%   verde   (tranquilo)
        80 a 100% ambar   (atencao)
        acima     vermelho (estourou)

    A largura desenhada e limitada a 100%, senao uma barra de 300% vazaria
    para fora do cartao. O NUMERO continua sendo mostrado por inteiro ao lado.
    """
    if vazio(percentual):
        percentual = 0.0
    fracao = max(0.0, float(percentual))
    largura = min(100.0, (fracao / teto) * 100 if teto else 0)

    if cor is None:
        if fracao > teto:
            cor_hex = config.CORES_TEMA["perigo"]
        elif fracao >= teto * 0.8:
            cor_hex = config.CORES_TEMA["alerta"]
        else:
            cor_hex = config.CORES_TEMA["sucesso"]
    else:
        cor_hex = config.CORES_TEMA.get(cor, cor)

    st.markdown(
        f'<div class="barra-fundo"><div class="barra-preenchida" '
        f'style="width:{largura:.1f}%;background:{cor_hex}"></div></div>',
        unsafe_allow_html=True,
    )


def card_meta(titulo: str, atual: float, alvo: float,
              ajuda: str = "", cor: str | None = None) -> None:
    """Cartao com valor, meta e barra de progresso — usado em orcamento e metas."""
    fracao = atual / alvo if alvo else 0.0
    classe = FAIXAS.get(cor, "")

    st.markdown(
        f"""
        <div class="cartao {classe}">
          <div class="kpi-rotulo">{escapar_html(titulo)}</div>
          <div class="kpi-valor pequeno">{escapar_html(fmt_brl(atual))}</div>
          <div class="kpi-ajuda">de {escapar_html(fmt_brl(alvo))}
               · {escapar_html(fmt_pct(fracao))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    barra(fracao)
    if ajuda:
        st.caption(ajuda)


def nota(texto_html: str) -> None:
    """Uma caixinha de observacao, com barra azul na esquerda.

    ATENCAO 1 — HTML: este e o unico componente que aceita HTML pronto, porque
    as paginas precisam de negrito no meio da frase. Passe SOMENTE texto
    escrito por voce no codigo; conteudo vindo do banco tem de passar por
    `escapar_html()` antes.

    ATENCAO 2 — O CIFRAO: aqui use `fmt_brl`, NUNCA `fmt_brl_md`.

    A regra completa, verificada na tela (nao e teoria):

        onde                                    sem escape   com escape
        ------------------------------------    ----------   ----------
        st.caption / st.markdown / st.info      come o valor   correto
        st.markdown(unsafe_allow_html=True)     correto        mostra "R\\$"

    O motivo: quando o texto esta dentro de uma tag HTML de bloco (o `<div>`
    daqui), o interpretador de markdown passa o conteudo adiante sem
    processar. Como o markdown nao roda, a formula LaTeX nao e detectada — e
    a contrabarra do escape tambem nao e consumida, aparecendo na tela.
    """
    st.markdown(f'<div class="nota">{texto_html}</div>', unsafe_allow_html=True)


def config_moeda(rotulo: str, ajuda: str | None = None):
    """Configuracao de coluna de dinheiro para st.dataframe / st.data_editor.

    O `format` usa a sintaxe do JavaScript (o Streamlit desenha a tabela no
    navegador), entao nao da para usar o nosso `fmt_brl`. "R$ %.2f" ao menos
    poe o simbolo certo e duas casas.
    """
    return st.column_config.NumberColumn(rotulo, format="R$ %.2f", help=ajuda)


def config_dolar(rotulo: str, ajuda: str | None = None):
    """Configuracao de coluna em dolar. Igual a de real, com o simbolo certo.

    Existe por duas razoes, e a segunda e a que importa: o simbolo certo, e o
    reconhecimento pelo olhinho. `privacidade.colunas_de_dinheiro()` acha a
    coluna pelo FORMATO, entao uma coluna em dolar declarada como texto ou como
    numero puro passaria batido e ficaria a mostra.
    """
    return st.column_config.NumberColumn(rotulo, format="US$ %.2f", help=ajuda)


def config_percentual(rotulo: str, ajuda: str | None = None):
    """Configuracao de coluna de porcentagem."""
    return st.column_config.NumberColumn(rotulo, format="%.1f%%", help=ajuda)


def config_data(rotulo: str, ajuda: str | None = None):
    """Configuracao de coluna de data.

    CUIDADO CONHECIDO: o DateColumn QUEBRA se a coluna ainda estiver como
    texto (que e como o SQLite guarda). Antes de usar no editor:

        df["data"] = pd.to_datetime(df["data"])       # antes de mostrar
        ...
        df["data"] = df["data"].dt.strftime("%Y-%m-%d")   # antes de salvar
    """
    return st.column_config.DateColumn(rotulo, format="DD/MM/YYYY", help=ajuda)


def aviso_vazio(mensagem: str, dica: str = "") -> None:
    """Mensagem amigavel quando nao ha dado para mostrar.

    Uma tela vazia sem explicacao parece defeito. Com uma frase dizendo o que
    fazer, vira instrucao.
    """
    st.info(mensagem + (f"\n\n{dica}" if dica else ""))


def rotulo_com_fixo(fixo: str, item: str) -> str:
    """Junta o nome do gasto fixo a descricao do lancamento, sem repetir.

    A composicao do mes guarda as duas coisas de proposito: `item` e a
    descricao crua do banco, e `fixo` diz a que item do cadastro ela pertence.
    Mostrar as duas e o que deixa a mesma despesa reconhecivel de um mes para o
    outro — "Aluguel · Pix enviado para Eduardo Moreira de Lima" em
    agosto, "Aluguel" em setembro.

    Mas quando um nome ja contem o outro, repetir polui em vez de esclarecer:
    "VIDAL PARKING MANOBRIS (estacionamento moto) · VIDAL PARKING MANOBRIS".
    Nesse caso vence o mais informativo, que e sempre o mais longo.
    """
    if not fixo:
        return item
    if not item:
        return fixo
    curto, longo = sorted((fixo, item), key=len)
    if normalizar_texto(curto) in normalizar_texto(longo):
        return longo
    return f"{fixo} · {item}"


def rodape_atualizado(quantidade: int, mes: str = "") -> None:
    """Rodape discreto dizendo o que esta sendo mostrado."""
    contexto = f" · mês {mes}" if mes else ""
    st.caption(f"{quantidade} lançamentos considerados{contexto}")


CHAVE_RECADO = "_recado_pendente"


def recado(texto: str, tipo: str = "sucesso") -> None:
    """Guarda um aviso para aparecer DEPOIS do `st.rerun()`.

    O PROBLEMA QUE ISTO RESOLVE, e ele existia em silencio:

        banco.executar(...)
        st.success("Metas salvas.")   # nunca chegou a ser vista
        st.rerun()

    `st.rerun()` interrompe a execucao e redesenha a pagina do zero. Tudo que
    foi escrito na tela naquele run e jogado fora junto — inclusive a mensagem
    escrita uma linha antes. Testado na tela: depois de salvar, "Metas salvas."
    nao aparecia em lugar nenhum.

    Passa despercebido porque o efeito acontece: a meta E salva, a linha some,
    a tabela atualiza. So a confirmacao se perde — e com ela os recados que
    NAO sao redundantes com a tela, como "as 2 metas que voce removeu
    continuam no banco".

    A saida e o aviso atravessar o rerun pelo estado da sessao. Guarde com
    `recado()` antes do `st.rerun()`; mostre com `mostrar_recado()` no topo da
    pagina, onde ele aparece no run seguinte e se consome sozinho.
    """
    st.session_state[CHAVE_RECADO] = (tipo, texto)


def mostrar_recado() -> None:
    """Mostra e consome o aviso guardado por `recado()`. Chame no topo da tela."""
    pendente = st.session_state.pop(CHAVE_RECADO, None)
    if not pendente:
        return
    tipo, texto = pendente
    {"sucesso": st.success, "aviso": st.warning,
     "info": st.info}.get(tipo, st.success)(texto)
