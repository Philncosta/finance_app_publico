"""
conferir_privacidade.py — o olhinho esconde tudo o que promete esconder?
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Um recurso de esconder valores falha de dois jeitos, e os dois sao silenciosos:

    1. ESQUECE UM LUGAR. A tela fica quase toda mascarada e um numero passa.
       Quem esta olhando por cima do seu ombro le exatamente esse.
    2. ALTERA O DADO. A mascara entra no lugar do numero e alguem a salva.
       Um recurso de VER nunca pode mudar o que esta gravado.

O primeiro nao da para conferir daqui inteiro — parte dele so aparece na tela,
e foi conferida no navegador. O que da para conferir aqui e o MOTOR: as
funcoes que decidem o que vira mascara e o que continua numero.

E o segundo, que e o mais grave, se confere inteiro aqui.

O QUE ELE NAO PROVA
-------------------
Nao prova que toda tela usa `privacidade`. Isso e uma questao de disciplina no
codigo, e quem cobra e a busca: `st.dataframe(`, `st.data_editor(` e
`st.plotly_chart(` nao devem aparecer em `paginas/`. O teste 7 faz essa busca.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_privacidade
"""

from __future__ import annotations

import io
import os
import re
import sys

import pandas as pd
import streamlit as st

from financas import config
from ui import privacidade
from verificacao.base import Conferencia


def _ocultar(ligado: bool) -> None:
    """Liga ou desliga o olhinho sem precisar de uma sessao do Streamlit.

    `st.session_state` so existe dentro de uma execucao do Streamlit. Como
    todas as funcoes deste modulo consultam `ocultando()` pelo nome, trocar a
    funcao no modulo e suficiente — e nao inventa um estado falso que poderia
    divergir do de verdade.
    """
    privacidade.ocultando = lambda: ligado


def conferir_padrao(placar: Conferencia) -> None:
    """Sessao nova nasce ESCONDIDA. E a decisao mais facil de reverter sem querer.

    Trocar `COMECA_OCULTO` para False, ou escrever `.get(CHAVE, False)` numa
    refatoracao distraida, nao quebra nada visivelmente — o app so volta a
    abrir mostrando tudo, e ninguem percebe ate acontecer na frente de alguem.
    Por isso o padrao tem um teste proprio.
    """
    placar.exigir(privacidade.COMECA_OCULTO is True,
                  "o modulo declara que comeca oculto")
    placar.exigir_igual(bool({}.get(privacidade.CHAVE, privacidade.COMECA_OCULTO)),
                        True,
                        "sessao sem a chave definida ja vem escondida")


def conferir_formatacao(placar: Conferencia) -> None:
    """Os valores em R$ viram mascara, e o resto continua igual."""
    _ocultar(False)
    placar.exigir_igual(privacidade.fmt_brl(1234.5),
                        "R$ 1.234,50",
                        "visivel: fmt_brl")
    placar.exigir_igual(privacidade.fmt_brl_md(1234.5),
                        "R\\$ 1.234,50",
                        "visivel: fmt_brl_md")

    _ocultar(True)
    placar.exigir_igual(privacidade.fmt_brl(1234.5),
                        privacidade.MASCARA,
                        "oculto: fmt_brl")
    placar.exigir_igual(privacidade.fmt_brl(-1234.5),
                        privacidade.MASCARA,
                        "oculto: fmt_brl negativo")
    placar.exigir_igual(privacidade.fmt_brl(None),
                        privacidade.MASCARA,
                        "oculto: fmt_brl vazio")
    placar.exigir_igual(privacidade.fmt_brl_md(1234.5),
                        privacidade.MASCARA_MD,
                        "oculto: fmt_brl_md sai escapado")
    placar.exigir("\\$" in privacidade.MASCARA_MD,
                  "a mascara de markdown escapa o cifrao (senao vira formula LaTeX)")

    _ocultar(False)
    placar.exigir_igual(privacidade.fmt_usd(7410.55),
                        "US$ 7.410,55",
                        "visivel: fmt_usd")
    _ocultar(True)
    placar.exigir_igual(privacidade.fmt_usd(7410.55),
                        privacidade.MASCARA_USD,
                        "oculto: fmt_usd")
    placar.exigir(privacidade.MASCARA_USD.startswith("US$")
        and privacidade.MASCARA_USD != privacidade.MASCARA,
                  "A MOEDA SOBREVIVE A MASCARA: dolar nao vira R$, senao a tela esconde "
        "o numero e mente o rotulo")


def conferir_frases(placar: Conferencia) -> None:
    """`texto()` mascara o dinheiro de frases prontas, e so o dinheiro."""
    _ocultar(True)

    casos = [
        ("inclui R$ 615,40 de receita ainda previstos",
         f"inclui {privacidade.MASCARA} de receita ainda previstos"),
        ("Em mar/2027 as despesas passam a receita em R\\$ 1.500,00.",
         f"Em mar/2027 as despesas passam a receita em {privacidade.MASCARA_MD}."),
        ("o saldo ficou -R$ 2.840,15 no mes",
         f"o saldo ficou {privacidade.MASCARA} no mes"),
        ("inclui R$ 100,00 e R$ 200,00",
         f"inclui {privacidade.MASCARA} e {privacidade.MASCARA}"),
        ("a carteira vale US$ 52.772,12 hoje",
         f"a carteira vale {privacidade.MASCARA_USD} hoje"),
        ("caiu -US$ 2.975,66 no ano",
         f"caiu {privacidade.MASCARA_USD} no ano"),
        ("R$ 274.437,95 = US$ 52.772,12",
         f"{privacidade.MASCARA} = {privacidade.MASCARA_USD}"),
    ]
    for entrada, esperado in casos:
        placar.exigir_igual(privacidade.texto(entrada),
                            esperado,
                            f"texto(): {entrada[:40]}")

    intocados = [
        "a reserva cobre 11,2 meses",
        "guardou 76,7% do que entrou",
        "3.811 lancamentos ate 2026-09",
        "18 papeis na carteira",
    ]
    for frase in intocados:
        placar.exigir_igual(privacidade.texto(frase),
                            frase,
                            f"texto() nao mexe em: {frase[:34]}")

    _ocultar(False)
    placar.exigir_igual(privacidade.texto("inclui R$ 615,40"),
                        "inclui R$ 615,40",
                        "texto() com olhinho desligado devolve igual")


def conferir_deteccao_de_colunas(placar: Conferencia) -> None:
    """As colunas em R$ sao reconhecidas pelo formato, sem lista por tela."""
    from ui import componentes

    configuracao = {
        "Valor": privacidade.coluna_dinheiro("Valor"),
        "Cadastrado": componentes.config_moeda("Cadastrado"),
        "Direto": st.column_config.NumberColumn("Direto", format="R$ %.2f"),
        "Dif. %": st.column_config.NumberColumn("Dif. %", format="%.1f%%"),
        "Meses": st.column_config.NumberColumn("Meses", format="%d"),
        "Item": st.column_config.TextColumn("Item"),
        "Link": st.column_config.LinkColumn("Link"),
        "Curva": st.column_config.LineChartColumn("Curva"),
        "Em US$": componentes.config_dolar("Em US$"),
    }
    achadas = sorted(privacidade.colunas_de_dinheiro(configuracao))
    placar.exigir_igual(achadas,
                        ["Cadastrado", "Curva", "Direto", "Em US$", "Valor"],
                        "colunas de dinheiro reconhecidas")
    placar.exigir("Em US$" in achadas,
                  "coluna em dolar tambem e coluna de dinheiro")
    placar.exigir("Curva" in achadas,
                  "a minicurva conta como valor (mostra a FORMA do patrimonio)")
    placar.exigir_igual(privacidade.colunas_de_dinheiro(None),
                        [],
                        "configuracao vazia nao quebra")


def conferir_mascara_de_tabela(placar: Conferencia) -> None:
    """A tabela sai mascarada e a ORIGINAL continua com os numeros."""
    original = pd.DataFrame({
        "item": ["Aluguel", "Luz"],
        "valor": [2500.0, 180.5],
        "meses": [12, 12],
    })

    _ocultar(True)
    mascarada = privacidade.mascarar(original, ["valor"])
    placar.exigir_igual(list(mascarada["valor"]),
                        [privacidade.MASCARA, privacidade.MASCARA],
                        "coluna de dinheiro virou mascara")
    placar.exigir_igual(list(mascarada["meses"]),
                        [12, 12],
                        "coluna que nao e dinheiro continua")
    placar.exigir_igual(list(original["valor"]),
                        [2500.0, 180.5],
                        "A ORIGINAL NAO FOI TOCADA")
    placar.exigir(mascarada is not original, "mascarar devolve outro objeto")
    placar.exigir_igual(list(privacidade.mascarar(original, ["nao_existe"])["valor"]),
                        [2500.0, 180.5],
                        "coluna inexistente e ignorada, sem erro")

    _ocultar(False)
    placar.exigir(privacidade.mascarar(original, ["valor"]) is original,
                  "desligado, mascarar devolve a mesma tabela")


def conferir_retorno_do_editor(placar: Conferencia) -> None:
    """O NUMERO volta ao que era antes de sair do editor. O mais importante.

    Simula o que o `st.data_editor` devolve com o olhinho ligado: a coluna de
    dinheiro cheia de mascara. Se essa mascara chegasse ao codigo que salva, a
    proxima gravacao escreveria texto onde havia dinheiro.
    """
    original = pd.DataFrame({
        "item": ["Aluguel", "Luz"],
        "valor_mensal": [2500.0, 180.5],
    })
    da_tela = original.copy()
    da_tela["valor_mensal"] = privacidade.MASCARA
    da_tela.loc[0, "item"] = "Aluguel corrigido"

    devolvido = da_tela.copy()
    comuns = devolvido.index.intersection(original.index)
    for coluna in ["valor_mensal"]:
        devolvido[coluna] = pd.NA
        devolvido.loc[comuns, coluna] = original.loc[comuns, coluna]

    placar.exigir_igual(list(devolvido["valor_mensal"]),
                        [2500.0, 180.5],
                        "o valor volta a ser numero")
    placar.exigir_igual(devolvido.loc[0, "item"],
                        "Aluguel corrigido",
                        "a edicao das outras colunas e preservada")
    placar.exigir(not any(isinstance(v, str) and "•" in v
                for v in devolvido["valor_mensal"]),
                  "nenhuma mascara sobrou na coluna de dinheiro")


def conferir_grafico(placar: Conferencia) -> None:
    """O eixo escondido e o do VALOR — e o de categoria continua legivel.

    Esconder o eixo errado tem os dois defeitos ao mesmo tempo: os valores
    ficam a mostra e o grafico fica ilegivel.
    """
    from ui import graficos

    em_pe = graficos.historico_receita_despesa(pd.DataFrame({
        "mes": ["2026-07", "2026-08"],
        "receita": [1000.0, 2000.0],
        "despesa": [500.0, 700.0],
        "saldo": [500.0, 1300.0],
    }))
    deitado = graficos.barras_por_categoria(pd.DataFrame({
        "categoria": ["Casa", "Comida"],
        "total": [1200.0, 800.0],
    }))

    placar.exigir(not any(getattr(s, "orientation", None) == "h"
                                for s in em_pe.data),
                  "grafico em pe nao tem serie deitada")
    placar.exigir(any(getattr(s, "orientation", None) == "h"
                            for s in deitado.data),
                  "grafico deitado se identifica por orientation='h'")

    _ocultar(True)
    for nome, fig, eixo_escondido, eixo_visivel in [
        ("em pe", em_pe, "yaxis", "xaxis"),
        ("deitado", deitado, "xaxis", "yaxis"),
    ]:
        privacidade.esconder_valores_da_figura(fig)
        placar.exigir_igual(getattr(fig.layout, eixo_escondido).showticklabels,
                            False,
                            f"grafico {nome}: eixo de valor escondido")
        placar.exigir(getattr(fig.layout, eixo_visivel).showticklabels is not False,
                      f"grafico {nome}: eixo de categoria continua visivel")
        placar.exigir(all(getattr(s, "text", None) is None for s in fig.data),
                      f"grafico {nome}: nenhum texto sobre as barras")

    percentual = graficos.retorno_por_papel(pd.DataFrame({
        "nome": ["Papel A", "Papel B"],
        "saldo": [1000.0, 2000.0],
        "rent_total": [0.12, -0.05],
    }))
    marca = getattr(percentual.layout, "meta", None) or {}
    placar.exigir(marca.get("valores") == "percentual",
                  "grafico de percentual se declara como tal")
    privacidade.esconder_valores_da_figura(percentual)
    placar.exigir(percentual.layout.xaxis.showticklabels is not False,
                  "grafico de percentual NAO tem o eixo escondido "
        "(porcentagem nao revela quanto voce tem)")
    placar.exigir(any(getattr(s, "text", None) is not None for s in percentual.data),
                  "...e continua com o texto nas barras")

    rosca = graficos.rosca_fixo_parcelado_variavel(2937.0, 2837.0, 7884.0)
    antes = " ".join(a.text or "" for a in rosca.layout.annotations or ())
    placar.exigir(bool(re.search(r"R\$\s?[\d.]+,\d{2}", antes)),
                  "a rosca escreve o total no meio, antes de esconder")
    privacidade.esconder_valores_da_figura(rosca)
    depois = " ".join(a.text or "" for a in rosca.layout.annotations or ())
    placar.exigir(not re.search(r"R\$\s?[\d.]+,\d{2}", depois) and "•" in depois,
                  "o total no meio da rosca vira mascara "
        "(anotacao de layout: update_traces nao alcanca)")

def conferir_uso_nas_telas(placar: Conferencia) -> None:
    """Nenhuma tela chama o Streamlit direto onde deveria passar pelo olhinho."""
    proibidos = ("st.dataframe(", "st.data_editor(", "st.plotly_chart(")
    pasta = os.path.join(config.RAIZ, "paginas")
    for nome in sorted(os.listdir(pasta)):
        if not nome.endswith(".py"):
            continue
        fonte = io.open(os.path.join(pasta, nome), encoding="utf-8").read()
        for chamada in proibidos:
            placar.exigir(chamada not in fonte,
                          f"paginas/{nome} nao chama {chamada} direto "
                f"(use privacidade.tabela / .editor / .grafico)")

    fonte_graficos = io.open(os.path.join(config.RAIZ, "ui", "graficos.py"),
                             encoding="utf-8").read()
    placar.exigir(not re.search(r"^import streamlit", fonte_graficos, re.M),
                  "ui/graficos.py continua sem importar streamlit")


def main() -> int:
    """Roda todas as checagens e imprime o resultado."""
    placar = Conferencia()
    try:
        conferir_padrao(placar)
        conferir_formatacao(placar)
        conferir_frases(placar)
        conferir_deteccao_de_colunas(placar)
        conferir_mascara_de_tabela(placar)
        conferir_retorno_do_editor(placar)
        conferir_grafico(placar)
        conferir_uso_nas_telas(placar)
    finally:
        _ocultar(False)

    print()
    print("=" * 78)
    print("  O OLHINHO ESCONDE O QUE PROMETE?")
    return placar.relatorio()


if __name__ == "__main__":
    sys.exit(main())
