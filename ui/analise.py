"""analise.py — a ficha de um papel, com as ressalvas coladas nos números.

==============================================================================

O QUE ESTA TELA RESPONDE
------------------------
    A empresa aguenta? (caixa, dívida, fôlego)
    Está cara?         (múltiplos — SÓ quando existe lucro)
    Quanto eu tenho de verdade nela? (exposição, contando alavancagem)

Ela aceita **qualquer ticker**, não só os da carteira. É para pesquisar um
papel antes de comprar, que é quando a pergunta importa.

A REGRA QUE ORGANIZA A TELA INTEIRA
-----------------------------------
**Campo que não existe vira frase, não vira vazio.** Um traço num cartão de
P/L faz você pensar que o app falhou em buscar. A verdade é outra e é
informação: *a empresa dá prejuízo, então múltiplo de lucro não existe*.

Vale para os três casos que aparecem de verdade:

    empresa no prejuízo   -> some o bloco de múltiplos, entra o fôlego de caixa
    ETF comum             -> não tem balanço próprio, e a tela diz isso
    ETF alavancado        -> não tem balanço nenhum, e o nome do fundo mente
                             sobre o retorno no período

POR QUE NÃO TEM NOTA, ESTRELA NEM SNOWFLAKE PREENCHIDO A FORÇA
--------------------------------------------------------------
O floco do Simply Wall St pontua valor, futuro, saúde, passado e dividendos. As
notas dele saem de modelo proprietário (fair value por fluxo de caixa
descontado, com premissas que não são publicadas). Reproduzir a APARENCIA sem o
modelo daria um desenho bonito com número inventado dentro — que é pior que
não ter desenho.

O que dá para desenhar com honestidade é o floco **do que a fonte de fato
entrega**: cada eixo é um número medido, e o eixo sem dado fica encolhido, à
vista. Papel sem lucro tem o eixo de valuation vazio porque ele é vazio.
"""

from __future__ import annotations

import re

import streamlit as st

from financas import cotacoes, fundamentos
from financas.calculos import investimentos as calc
from financas.formato import fmt_num, fmt_pct, vazio
from ui import componentes as c
from ui import graficos
from ui import privacidade as priv

_MOEDA = {"USD": "US$", "BRL": "R$", "EUR": "€"}

# Codigo da B3: quatro letras e um ou dois digitos — PETR4, BBAS3, DIVO11.
# Ticker americano nao tem essa forma (sao so letras: AAPL, NVDA), entao da
# para distinguir os dois OFFLINE, sem precisar perguntar a fonte.
_CODIGO_B3 = re.compile(r"^[A-Z]{4}\d{1,2}$")


def _com_sufixo_da_bolsa(ticker: str) -> str:
    """Acrescenta `.SA` quando o codigo e da B3 e veio sem sufixo.

    POR QUE ISTO EXISTE. O campo dizia, na ajuda atras do "?", que papel do
    Brasil leva `.SA`. Ele digitou `DIVO11`, o Yahoo respondeu 404, e a tela
    disse "nao achei fundamentos" — tecnicamente verdade, e inutil: o dado
    existe, so estava com outro nome (`DIVO11.SA`).

    Ajuda que so aparece quando voce clica no "?" nao e ajuda para quem ja
    digitou. Normalizar na entrada resolve para todo mundo, e sem chute: a
    forma "4 letras + digito" so existe na B3.
    """
    return f"{ticker}{cotacoes.SUFIXO_B3}" if _CODIGO_B3.match(ticker) else ticker


def _grande(valor, moeda: str = "USD") -> str:
    """Bilhão vira 'bi'. Ninguém lê 6.084.700.160 sem contar os dígitos."""
    if vazio(valor):
        return "—"
    simbolo = _MOEDA.get(moeda, moeda or "")
    valor = float(valor)
    for corte, sufixo in ((1e12, "tri"), (1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(valor) >= corte:
            return f"{simbolo} {valor / corte:,.2f} {sufixo}".replace(",", "@") \
                .replace(".", ",").replace("@", ".")
    return f"{simbolo} {valor:,.2f}".replace(",", "@").replace(".", ",") \
        .replace("@", ".")


def _pct(valor, casas: int = 1) -> str:
    """Percentual, ou travessão. Nunca 0% para dizer 'não sei'."""
    return "—" if vazio(valor) else fmt_pct(valor, casas)


def _escolher_ticker(desempenho) -> str | None:
    """Selectbox com os papéis da carteira + campo livre para pesquisar outro."""
    da_carteira = []
    if desempenho is not None and not desempenho.empty:
        for _, papel in desempenho.iterrows():
            if not vazio(papel.get("ticker")):
                da_carteira.append(str(papel["ticker"]).upper())
    da_carteira = sorted(set(da_carteira))

    coluna_lista, coluna_livre = st.columns([2, 2], gap="medium")
    with coluna_lista:
        escolhido = st.selectbox(
            "Papel da carteira", ["—"] + da_carteira, index=0,
            key="analise_da_carteira",
            help="Os papéis com ticker cadastrado. Tesouro e fundo não têm "
                 "ticker público, então não aparecem aqui.")
    with coluna_livre:
        digitado = st.text_input(
            "Ou pesquise qualquer ticker", key="analise_digitado",
            placeholder="AAPL, NVDA, PETR4, DIVO11…",
            help="Serve para olhar um papel antes de comprar. Código da B3 "
                 "pode ir sem o .SA — o app acrescenta.").strip().upper()

        if digitado:
            com_sufixo = _com_sufixo_da_bolsa(digitado)
            if com_sufixo != digitado:
                st.caption(f"Procurando como **{com_sufixo}** — é assim que a "
                           f"fonte chama papel da B3.")
            digitado = com_sufixo

    return digitado or (None if escolhido == "—" else escolhido)


def _preco(ticker: str) -> tuple[float | None, str | None]:
    """O fechamento mais recente. Busca uma vez se o papel nunca passou por aqui.

    Papel de FORA da carteira nao tem historico gravado — e sem preco, "alvo
    dos analistas contra o preco de hoje" fica em branco justamente na tela
    feita para pesquisar o que voce ainda nao tem. Uma busca, e o resultado
    fica guardado para a proxima.
    """
    preco, dia = cotacoes.preco_em(ticker)
    if preco is not None:
        return preco, dia
    cotacoes.atualizar([ticker])
    return cotacoes.preco_em(ticker)


def _tem_balanco(ficha: dict) -> bool:
    """Existe empresa por trás deste papel?

    Um ETF — alavancado ou não — não tem caixa, dívida nem receita próprios. Sem
    esta porteira, a tela desenhava "A empresa aguenta?" com três cartões
    vazios em cima de um fundo, que é justamente o vazio-sem-explicação que
    este arquivo existe para não fazer. Quando não há balanço, quem responde é
    a frase em `motivos`.
    """
    return any(not vazio(ficha.get(campo))
               for campo in ("caixa", "divida", "receita", "fluxo_de_caixa"))


def _cartoes_de_saude(ficha: dict) -> None:
    """Os números que valem quando a empresa ainda não dá lucro."""
    moeda = ficha.get("moeda") or "USD"
    folego = ficha.get("folego_meses")

    if vazio(folego):
        rotulo_folego, apoio_folego = "—", (
            "gera caixa, ou não informa" if ficha.get("fluxo_de_caixa") is None
            else "gera caixa em vez de queimar")
    else:
        rotulo_folego = f"{folego:.0f} meses".replace(".", ",")
        apoio_folego = "de caixa no ritmo de queima atual"

    c.destaque([
        {"rotulo": "Fôlego de caixa", "valor": rotulo_folego,
         "ajuda": apoio_folego},
        {"rotulo": "Caixa", "valor": _grande(ficha.get("caixa"), moeda),
         "ajuda": f"dívida de {_grande(ficha.get('divida'), moeda)}"},
        {"rotulo": "Receita cresce",
         "valor": _pct(ficha.get("crescimento_receita")),
         "ajuda": f"margem {_pct(ficha.get('margem'))}"},
    ])

    if ficha.get("divida_maior_que_caixa"):
        contraste = (f"A dívida é maior que o caixa — "
                     f"{_grande(ficha.get('divida'), moeda)} contra "
                     f"{_grande(ficha.get('caixa'), moeda)}. ")
        if vazio(folego):
            c.tarja(
                contraste + "Como a empresa gera caixa em vez de queimar, isso "
                "por si só não é sinal de aperto: empresa lucrativa costuma "
                "tomar dívida barata de propósito, e paga com o que produz. O "
                "que importa aqui é o custo dela, não o tamanho.", "info")
        else:
            c.tarja(
                contraste + "Numa empresa que ainda queima dinheiro, isso quer "
                "dizer que o próximo passo dela depende de conseguir dinheiro "
                "de fora: emitir ação (que dilui quem já é sócio) ou tomar "
                "mais dívida.", "aviso")


def _cartoes_de_valuation(ficha: dict) -> None:
    """Só aparece quando há lucro. Sem lucro, múltiplo de lucro é ruído."""
    c.destaque([
        {"rotulo": "P/L", "valor": (
            "—" if vazio(ficha.get("pl")) else fmt_num(ficha["pl"], 1)),
         "ajuda": "preço dividido pelo lucro dos 12 meses"},
        {"rotulo": "P/L projetado", "valor": (
            "—" if vazio(ficha.get("pl_projetado"))
            else fmt_num(ficha["pl_projetado"], 1)),
         "ajuda": "sobre o lucro que os analistas esperam"},
        {"rotulo": "Preço / patrimônio", "valor": (
            "—" if vazio(ficha.get("preco_sobre_patrimonio"))
            else fmt_num(ficha["preco_sobre_patrimonio"], 2)),
         "ajuda": f"retorno sobre patrimônio {_pct(ficha.get('retorno_patrimonio'))}"},
    ])


def _alvo_dos_analistas(ficha: dict, preco_hoje: float | None) -> None:
    """O alvo, sempre com o número de analistas do lado."""
    alvo, quantos = ficha.get("alvo"), ficha.get("analistas")
    if vazio(alvo):
        return

    moeda = _MOEDA.get(ficha.get("moeda") or "USD", "")
    distancia = None
    if preco_hoje:
        distancia = alvo / preco_hoje - 1

    c.secao("O que os analistas projetam")
    c.estatisticas([
        {"rotulo": "Alvo médio", "valor": f"{moeda} {fmt_num(alvo, 2)}"},
        {"rotulo": "Faixa", "valor": (
            f"{fmt_num(ficha.get('alvo_min'), 2)} – "
            f"{fmt_num(ficha.get('alvo_max'), 2)}"
            if not vazio(ficha.get("alvo_min")) else "—")},
        {"rotulo": "Contra o preço de hoje", "valor": _pct(distancia)},
        {"rotulo": "Analistas cobrindo",
         "valor": "—" if vazio(quantos) else str(int(quantos))},
    ])
    c.nota(
        "Alvo de analista é <b>opinião com prazo</b>, normalmente doze meses, e "
        "costuma ficar acima do preço: quem cobre um papel raramente publica "
        "que ele não vale a pena. Serve para saber o que o mercado espera, "
        "não como previsão.")


def _decaimento_do_alavancado(ficha: dict, ticker: str) -> None:
    """Mostra, com o dado dele, que 2x por dia não é 2x no período."""
    alavanca = ficha.get("alavancagem") or {}
    alvo = alavanca.get("subjacente")
    if not alvo:
        return

    serie_papel = cotacoes.serie(ticker)
    serie_alvo = cotacoes.serie(alvo)
    if serie_papel.empty or serie_alvo.empty:
        return

    def por_dia(serie):
        return {str(linha["data"])[:10]: float(linha["fechamento"])
                for _, linha in serie.iterrows()}

    precos_papel, precos_alvo = por_dia(serie_papel), por_dia(serie_alvo)
    comuns = sorted(set(precos_papel) & set(precos_alvo))
    if len(comuns) < 30:
        return

    inicio, fim = comuns[0], comuns[-1]
    retorno_papel = precos_papel[fim] / precos_papel[inicio] - 1
    retorno_alvo = precos_alvo[fim] / precos_alvo[inicio] - 1
    conta = fundamentos.decaimento(retorno_papel, retorno_alvo,
                                   alavanca["fator"])

    c.secao(f"{abs(alavanca['fator'])}x por dia não é "
            f"{abs(alavanca['fator'])}x no período")
    c.estatisticas([
        {"rotulo": f"{alvo} no período", "valor": _pct(retorno_alvo)},
        {"rotulo": f"{abs(alavanca['fator'])}x disso seria",
         "valor": _pct(conta["esperado"])},
        {"rotulo": f"{ticker} entregou", "valor": _pct(conta["real"])},
        {"rotulo": "Diferença",
         "valor": f"{conta['diferenca'] * 100:+.1f}".replace(".", ",") + " p.p."},
    ])
    c.nota(
        f"Medido em <b>{len(comuns)} pregões</b>, de {inicio} a {fim}. O fundo "
        f"cumpre o que promete todo dia — o que ele não promete é o período. "
        f"Cair 10% e subir 10% devolve o papel normal a 99% do que era, e o "
        f"alavancado 2x a 96%. Repita isso por meses e o buraco é esse aí. "
        f"Quanto mais o {alvo} oscila, maior ele fica.")


def _exposicao(desempenho) -> None:
    """Quanto a carteira aposta em cada papel-alvo, somando a alavancagem."""
    tabela = calc.exposicao_economica(desempenho)
    if tabela.empty or not (tabela["via_alavancado"] > 0).any():
        return

    c.secao("Quanto você tem de verdade em cada papel")
    mostrar = tabela.rename(columns={
        "papel": "Papel", "direta": "Posição direta",
        "via_alavancado": "Via fundo alavancado", "exposicao": "Exposição real",
        "participacao": "% da carteira"})
    priv.tabela(
        mostrar[["Papel", "Posição direta", "Via fundo alavancado",
                 "Exposição real", "% da carteira"]],
        key="analise_exposicao", width="stretch",
        hide_index=True,
        column_config={
            "Posição direta": st.column_config.NumberColumn(format="R$ %.2f"),
            "Via fundo alavancado": st.column_config.NumberColumn(format="R$ %.2f"),
            "Exposição real": st.column_config.NumberColumn(format="R$ %.2f"),
            "% da carteira": st.column_config.NumberColumn(format="%.2f%%"),
        })
    c.nota(
        "A tabela de posições lista o fundo alavancado como uma linha própria, "
        "com o valor dele. Mas ele é uma aposta <b>no mesmo papel</b>, com o "
        "movimento multiplicado — então a exposição real é maior que a soma "
        "das linhas. É a diferença entre o que você vê e o que você carrega.<br><br>"
        "Isto conta só o mesmo papel-alvo, que é fato. Papéis diferentes que "
        "andam juntos — dois do mesmo setor, por exemplo — não entram aqui, "
        "porque isso seria estimativa, não medição.")


def desenhar(desempenho=None) -> None:
    """Monta a aba inteira: escolha do papel, ficha, ressalvas e exposição."""
    ticker = _escolher_ticker(desempenho)

    _exposicao(desempenho)

    if not ticker:
        c.aviso_vazio(
            "Escolha um papel da carteira ou digite um ticker.",
            "Serve tanto para o que você já tem quanto para pesquisar antes "
            "de comprar.")
        return

    coluna_botao, coluna_estado = st.columns([1, 3], gap="medium")
    with coluna_botao:
        buscar_agora = st.button("Buscar dados de novo", key="analise_buscar",
                                 width="stretch",
                                 help="Balanço muda por trimestre, então o "
                                      "guardado do dia serve. Use se quiser "
                                      "forçar.")

    with st.spinner(f"Lendo os fundamentos de {ticker}…"):
        ficha = fundamentos.ficha(ticker, buscar_agora=buscar_agora)

    if not ficha.get("tem_dado"):
        # A mensagem antiga listava três causas possíveis e nenhuma saída. A
        # causa mais comum tem conserto de um caractere, e é a que vem primeiro.
        pistas = []
        if not ticker.endswith(cotacoes.SUFIXO_B3):
            pistas.append(
                f"Se for papel da B3, o nome na fonte leva `.SA` — tente "
                f"**{ticker}{cotacoes.SUFIXO_B3}**. Códigos no formato PETR4 "
                f"ou DIVO11 o app já converte sozinho; siglas fora desse "
                f"formato, não.")
        pistas.append(
            "Tesouro Direto e fundo brasileiro **não têm** ficha pública — não "
            "é falha, é que não existe cotação nem balanço para eles.")
        pistas.append("E se a rede estiver fora, nada chega aqui.")

        c.aviso_vazio(f"Não achei fundamentos para **{ticker}**.",
                      "\n\n".join(pistas))
        return

    with coluna_estado:
        st.caption(f"Dados de **{ficha['obtido_em']}** · fonte Yahoo Finance "
                   f"pelo `yfinance`, que não é oficial")

    st.markdown(f"### {ficha.get('nome') or ticker}")
    setor = " · ".join(x for x in (ficha.get("setor"), ficha.get("industria"))
                       if x)
    if setor:
        st.caption(setor)

    for aviso in ficha.get("avisos", []):
        c.tarja(aviso.replace("**", ""), "aviso")

    preco_hoje, dia_preco = _preco(ticker)

    if _tem_balanco(ficha):
        c.secao("A empresa aguenta?")
        _cartoes_de_saude(ficha)

    if ficha.get("da_lucro"):
        c.secao("Está cara?")
        _cartoes_de_valuation(ficha)
    for motivo in ficha.get("motivos", []):
        c.tarja(motivo.replace("**", ""), "info")

    _decaimento_do_alavancado(ficha, ticker)
    _alvo_dos_analistas(ficha, preco_hoje)

    if preco_hoje:
        c.secao(f"Preço de {ticker}")
        st.caption(f"Fechamento de {dia_preco}")
        serie = cotacoes.serie(ticker)
        if not serie.empty:
            priv.grafico(graficos.preco_do_papel(serie, ticker),
                         width="stretch", key="analise_preco_papel")

    if ficha.get("resumo"):
        with st.expander("O que a empresa faz, nas palavras dela"):
            st.caption(ficha["resumo"])
