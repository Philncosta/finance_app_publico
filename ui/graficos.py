"""
graficos.py — Todos os graficos do app, em Plotly.
==============================================================================

POR QUE TODOS OS GRAFICOS FICAM AQUI
------------------------------------
Duas razoes praticas:

1. CONSISTENCIA. Todos passam pela mesma funcao de acabamento (`_estilo`), o
   que garante a mesma fonte, a mesma altura, a mesma grade e as mesmas cores
   em todas as telas. Grafico feito "cada um do seu jeito" e o que faz um
   painel parecer amador.

2. TESTABILIDADE. Cada funcao recebe um DataFrame e devolve uma figura. Nao le
   banco, nao chama Streamlit. Da para gerar qualquer grafico num script e
   salvar como imagem, sem abrir o app.

A REGRA DE COR
--------------
Cada grande categoria tem UMA cor, definida no cadastro e usada em todos os
graficos. "Casa" e sempre indigo, "Comida" e sempre ambar. Isso permite bater
o olho e reconhecer a categoria sem ler a legenda.

Para valores, a convencao e fixa em todo o app:
    verde    = entrou dinheiro / sobrou
    vermelho = saiu dinheiro / estourou
    indigo   = neutro, informativo
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from financas import config
from financas.formato import fmt_brl, rotulo_mes, vazio

MODELO = "plotly_white"

CORES = config.CORES_TEMA


def _estilo(fig: go.Figure, altura: int = 320, titulo: str = "",
            legenda: bool = True, margem_topo: int = 40) -> go.Figure:
    """Aplica o acabamento padrao a qualquer figura.

    Detalhes que fazem diferenca visual:
      - fundo TRANSPARENTE (`rgba(0,0,0,0)`), para o grafico assumir a cor do
        cartao em que estiver, em vez de mostrar um retangulo branco por cima;
      - legenda deitada em cima, que economiza espaco horizontal;
      - `hovermode="x unified"` mostra todos os valores daquele ponto numa
        caixinha so, em vez de uma por serie.
    """
    layout = dict(
        template=MODELO,
        height=altura,
        separators=",.",
        margin=dict(l=10, r=10, t=margem_topo if titulo else 20, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                  size=12, color=CORES["texto"]),
        showlegend=legenda,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, title_text=""),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="white", bordercolor=CORES["borda"],
                        font_size=12),
    )
    if titulo:
        layout["title"] = dict(
            text=titulo, font=dict(size=15, color=CORES["texto"]),
            x=0, xanchor="left",
        )

    fig.update_layout(**layout)

    # Barra com canto arredondado. E o unico acabamento das referencias que
    # entra aqui, e entra num lugar so — os 40 graficos ganham de uma vez, sem
    # nenhum deles precisar saber disso. O raio e pequeno de proposito: em
    # barra empilhada, cada segmento arredonda, e um raio grande separaria
    # visualmente pedacos que sao a mesma coluna.
    fig.update_traces(marker_cornerradius=4, selector=dict(type="bar"))

    # Sem linha de eixo: a grade horizontal ja da a referencia, e a linha
    # somava um segundo tracado dizendo a mesma coisa.
    fig.update_xaxes(showgrid=False, showline=False, zeroline=False)
    fig.update_yaxes(gridcolor=CORES["borda"], zeroline=False,
                     tickprefix="R$ ", separatethousands=True)
    return fig


def marcar_futuro(fig: go.Figure, meses) -> go.Figure:
    """Sombreia os meses que ainda nao aconteceram.

    POR QUE ISTO IMPORTA: parcelas ja contratadas criam lancamentos ate
    dez/2026. Um grafico que vai ate la, sem marcacao, faz o futuro parecer
    passado — e um mes futuro SEMPRE parece pessimo, porque a despesa
    contratada ja esta la e a receita ainda nao.

    A faixa cinza clara diz "daqui pra frente e previsao", sem tirar o dado da
    tela. Nada de linha tracejada em cada serie: com quatro series viraria
    poluicao, e a faixa resolve de uma vez.

    `meses` e a lista de rotulos do eixo x, na ordem em que aparecem — os
    graficos daqui usam eixo de CATEGORIA (jan/2026, fev/2026...), nao de
    data, entao a faixa e posicionada por INDICE.
    """
    from financas.dados import mes_esta_em_andamento

    if not len(meses):
        return fig

    primeiro_futuro = None
    for indice, mes in enumerate(meses):
        if mes_esta_em_andamento(mes):
            primeiro_futuro = indice
            break
    if primeiro_futuro is None:
        return fig

    fig.add_vrect(
        x0=primeiro_futuro - 0.5, x1=len(meses) - 0.5,
        fillcolor=CORES["neutra"], opacity=0.07,
        line_width=0, layer="below",
        annotation_text="ainda não aconteceu",
        annotation_position="top left",
        annotation_font=dict(size=10, color=CORES["texto_fraco"]),
    )
    return fig


def _sem_dados(mensagem: str = "Sem dados para o período") -> go.Figure:
    """Figura vazia com um recado no meio.

    Devolver isto em vez de `None` mantem o layout inteiro: a pagina desenha o
    grafico do mesmo tamanho e nao "pula" quando falta dado.
    """
    fig = go.Figure()
    fig.add_annotation(text=mensagem, showarrow=False,
                       font=dict(size=13, color=CORES["texto_fraco"]))
    fig.update_layout(
        template=MODELO, height=280,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=20, b=10),
    )
    return fig


def _cores_para(nomes, mapa: dict[str, str] | None) -> list[str]:
    """Traduz uma lista de categorias na lista de cores correspondente.

    Quem nao esta no mapa recebe uma cor da paleta, escolhida pela posicao —
    assim nunca fica sem cor e nunca fica cinza demais.
    """
    mapa = mapa or {}
    cores = []
    for posicao, nome in enumerate(nomes):
        cores.append(mapa.get(nome, config.PALETA[posicao % len(config.PALETA)]))
    return cores


def rosca_fixo_parcelado_variavel(fixo: float, parcelado: float,
                                  variavel: float) -> go.Figure:
    """Rosca: quanto do mes foi fixo, quanto parcelado e quanto variavel.

    Responde "quanto do meu gasto eu conseguiria mudar no mes que vem?".
    O buraco no meio (`hole`) nao e enfeite: ele deixa espaco para o total,
    que e a informacao que a pessoa procura primeiro.
    """
    valores = [fixo, parcelado, variavel]
    if sum(valores) <= 0:
        return _sem_dados()

    fig = go.Figure(go.Pie(
        labels=["Fixo", "Parcelado", "Variável (à vista)"],
        values=valores,
        hole=0.62,
        marker=dict(colors=[CORES["primaria"], CORES["alerta"], CORES["secundaria"]],
                    line=dict(color="white", width=2)),
        textinfo="percent",
        textfont=dict(size=12, color="white"),
        hovertemplate="<b>%{label}</b><br>%{value:,.2f}<br>%{percent}<extra></extra>",
        sort=False,
    ))
    fig.add_annotation(
        text=f"<b>{fmt_brl(sum(valores))}</b><br>"
             f"<span style='font-size:11px;color:{CORES['texto_fraco']}'>no mês</span>",
        showarrow=False, font=dict(size=15, color=CORES["texto"]),
    )
    return _estilo(fig, altura=300, legenda=True)


def pizza_por_grande_categoria(df_categorias: pd.DataFrame,
                               mapa_cores: dict | None = None) -> go.Figure:
    """Rosca do gasto do mes por grande categoria."""
    if df_categorias.empty:
        return _sem_dados()

    nomes = df_categorias["grande_categoria"].tolist()
    fig = go.Figure(go.Pie(
        labels=nomes,
        values=df_categorias["total"],
        hole=0.55,
        marker=dict(colors=_cores_para(nomes, mapa_cores),
                    line=dict(color="white", width=2)),
        textinfo="label+percent",
        textposition="outside",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    total = df_categorias["total"].sum()
    fig.add_annotation(
        text=f"<b>{fmt_brl(total)}</b>",
        showarrow=False, font=dict(size=14, color=CORES["texto"]),
    )
    return _estilo(fig, altura=340, legenda=False)


def barras_por_categoria(df_categorias: pd.DataFrame, coluna: str = "categoria",
                         mapa_cores: dict | None = None,
                         limite: int = 12) -> go.Figure:
    """Barras horizontais do gasto por categoria, da maior para a menor.

    HORIZONTAIS de proposito: nome de categoria e texto, e texto se le
    deitado. Em barra vertical, "Serviços Domésticos" viraria um rotulo
    girado 45 graus que ninguem consegue ler.
    """
    if df_categorias.empty:
        return _sem_dados()

    dados_grafico = df_categorias.head(limite).iloc[::-1]
    nomes = dados_grafico[coluna].tolist()

    fig = go.Figure(go.Bar(
        y=nomes,
        x=dados_grafico["total"],
        orientation="h",
        marker=dict(color=_cores_para(nomes, mapa_cores), line=dict(width=0)),
        text=[fmt_brl(v) for v in dados_grafico["total"]],
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    altura = max(280, 34 * len(dados_grafico) + 60)
    return _estilo(fig, altura=altura, legenda=False)


def barras_por_dia(df_mes: pd.DataFrame) -> go.Figure:
    """Gasto por dia do mes — mostra onde o dinheiro concentra.

    Todos os 31 dias aparecem, mesmo os sem gasto. Sem isso o eixo pularia de
    3 para 7 e daria a impressao errada de que os dias foram seguidos.
    """
    if df_mes.empty:
        return _sem_dados()

    gastos = df_mes[df_mes["e_despesa"]] if "e_despesa" in df_mes else df_mes
    if gastos.empty:
        return _sem_dados()

    por_dia = gastos.groupby("dia")["valor"].sum().mul(-1)
    todos_dias = range(1, 32)
    valores = [float(por_dia.get(dia, 0.0)) for dia in todos_dias]

    fig = go.Figure(go.Bar(
        x=list(todos_dias), y=valores,
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        hovertemplate="Dia %{x}<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(title_text="dia do mês", dtick=2, showgrid=False)
    return _estilo(fig, altura=260, legenda=False)


def historico_receita_despesa(df_mensal: pd.DataFrame,
                              n_meses: int | None = 12) -> go.Figure:
    """Barras de receita e despesa por mes, com a linha do saldo por cima.

    E o grafico que mais conta historia: onde as barras se cruzam, o mes
    fechou no vermelho.
    """
    if df_mensal.empty:
        return _sem_dados()

    dados_grafico = df_mensal if n_meses is None else df_mensal.tail(n_meses)
    rotulos = [rotulo_mes(m) for m in dados_grafico["mes"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Receita", x=rotulos, y=dados_grafico["receita"],
        marker=dict(color=CORES["sucesso"], line=dict(width=0)),
        hovertemplate="Receita<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Despesa", x=rotulos, y=dados_grafico["despesa"],
        marker=dict(color=CORES["perigo"], line=dict(width=0)),
        hovertemplate="Despesa<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Saldo", x=rotulos, y=dados_grafico["saldo"],
        mode="lines+markers",
        line=dict(color=CORES["texto"], width=2.5),
        marker=dict(size=6),
        hovertemplate="Saldo<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.25)
    marcar_futuro(fig, list(dados_grafico["mes"]))
    return _estilo(fig, altura=340)


def linha_saldo_acumulado(df_mensal: pd.DataFrame) -> go.Figure:
    """Linha do saldo acumulado — o dinheiro somado ao longo do tempo.

    A area preenchida abaixo da linha ajuda a ler a tendencia. `tozeroy`
    preenche ate a linha do zero, entao um trecho abaixo de zero fica
    visivelmente "afundado".
    """
    if df_mensal.empty:
        return _sem_dados()

    rotulos = [rotulo_mes(m) for m in df_mensal["mes"]]
    fig = go.Figure(go.Scatter(
        x=rotulos, y=df_mensal["acumulado"],
        mode="lines+markers", fill="tozeroy",
        line=dict(color=CORES["primaria"], width=2.5),
        fillcolor="rgba(79,70,229,.10)",
        marker=dict(size=5),
        hovertemplate="R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=CORES["neutra"], line_width=1)
    marcar_futuro(fig, list(df_mensal["mes"]))
    return _estilo(fig, altura=300, legenda=False)


def evolucao_por_grande_categoria(df: pd.DataFrame, n_meses: int | None = 6,
                                  mapa_cores: dict | None = None) -> go.Figure:
    """Barras empilhadas: como cada grande categoria evoluiu mes a mes."""
    if df.empty:
        return _sem_dados()

    gastos = df[df["e_despesa"]] if "e_despesa" in df else df
    if gastos.empty:
        return _sem_dados()

    tabela = (
        gastos.groupby(["mes_competencia", "grande_categoria"])["valor"]
        .sum().mul(-1).reset_index()
    )
    todos_os_meses = sorted(tabela["mes_competencia"].unique())
    meses_recentes = todos_os_meses if n_meses is None else todos_os_meses[-n_meses:]
    tabela = tabela[tabela["mes_competencia"].isin(meses_recentes)]
    if tabela.empty:
        return _sem_dados()

    fig = go.Figure()
    categorias = sorted(tabela["grande_categoria"].unique())
    cores = _cores_para(categorias, mapa_cores)

    for categoria, cor in zip(categorias, cores):
        recorte = tabela[tabela["grande_categoria"] == categoria]
        serie = recorte.set_index("mes_competencia")["valor"].reindex(
            meses_recentes, fill_value=0)
        fig.add_trace(go.Bar(
            name=categoria, x=[rotulo_mes(m) for m in meses_recentes], y=serie.values,
            marker=dict(color=cor, line=dict(width=0)),
            hovertemplate=f"<b>{categoria}</b><br>R$ %{{y:,.2f}}<extra></extra>",
        ))

    fig.update_layout(barmode="stack", bargap=0.28)
    marcar_futuro(fig, list(meses_recentes))
    return _estilo(fig, altura=360)


def barras_parcelas_futuras(df_grade: pd.DataFrame) -> go.Figure:
    """Quanto de parcela ja contratada cai em cada mes a frente."""
    if df_grade.empty or df_grade["total"].sum() <= 0:
        return _sem_dados("Nenhuma parcela em aberto — o cartão está limpo daqui pra frente")

    rotulos = [rotulo_mes(m) for m in df_grade["mes"]]
    fig = go.Figure(go.Bar(
        x=rotulos, y=df_grade["total"],
        marker=dict(color=CORES["alerta"], line=dict(width=0)),
        text=[fmt_brl(v) if v > 0 else "" for v in df_grade["total"]],
        textposition="outside", textfont=dict(size=10),
        customdata=df_grade["quantidade"],
        hovertemplate="R$ %{y:,.2f}<br>%{customdata} parcelas<extra></extra>",
    ))
    return _estilo(fig, altura=300, legenda=False)


def barras_parcelamentos_ativos(df_ativos: pd.DataFrame,
                                limite: int = 12) -> go.Figure:
    """Saldo a vencer de cada parcelamento ativo, do maior para o menor."""
    if df_ativos.empty:
        return _sem_dados("Nenhum parcelamento ativo")

    dados_grafico = df_ativos.head(limite).iloc[::-1]
    rotulos = [
        f"{d[:26]} ({int(a)}/{int(t)})"
        for d, a, t in zip(dados_grafico["descricao"],
                           dados_grafico["ultima_faturada"],
                           dados_grafico["parcela_total"])
    ]
    fig = go.Figure(go.Bar(
        y=rotulos, x=dados_grafico["total_a_vencer"], orientation="h",
        marker=dict(color=CORES["alerta"], line=dict(width=0)),
        text=[fmt_brl(v) for v in dados_grafico["total_a_vencer"]],
        textposition="outside", textfont=dict(size=10),
        customdata=dados_grafico["parcelas_restantes"],
        hovertemplate="<b>%{y}</b><br>a vencer R$ %{x:,.2f}"
                      "<br>%{customdata} parcelas restantes<extra></extra>",
    ))
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    altura = max(280, 32 * len(dados_grafico) + 60)
    return _estilo(fig, altura=altura, legenda=False)


def projecao_caixa(df_projecao: pd.DataFrame) -> go.Figure:
    """Composicao das despesas projetadas + a linha da receita prevista.

    As barras empilhadas mostram DE QUE e feita a despesa de cada mes futuro,
    e a linha mostra a receita. Onde a pilha passa da linha, o mes fecha no
    vermelho — da para ver sem ler numero nenhum.
    """
    if df_projecao.empty:
        return _sem_dados()

    rotulos = [rotulo_mes(m) for m in df_projecao["mes"]]
    fig = go.Figure()

    for nome, coluna, cor in [
        ("Fixos na conta", "fixos_conta", CORES["primaria"]),
        ("Fixos no cartão", "fixos_cartao", CORES["alerta_clara"]),
        ("Parcelas do cartão", "parcelas_cartao", CORES["alerta"]),
        ("Outras variáveis", "outras_variaveis", CORES["secundaria"]),
    ]:
        if coluna not in df_projecao.columns:
            continue
        fig.add_trace(go.Bar(
            name=nome, x=rotulos, y=df_projecao[coluna],
            marker=dict(color=cor, line=dict(width=0)),
            hovertemplate=f"{nome}<br>R$ %{{y:,.2f}}<extra></extra>",
        ))

    fig.add_trace(go.Scatter(
        name="Receita prevista", x=rotulos, y=df_projecao["receita_prevista"],
        mode="lines+markers",
        line=dict(color=CORES["sucesso"], width=2.5),
        marker=dict(size=6),
        hovertemplate="Receita<br>R$ %{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(barmode="stack", bargap=0.25)
    return _estilo(fig, altura=380)


def linha_saldo_projetado(df_projecao: pd.DataFrame) -> go.Figure:
    """O saldo acumulado que a projecao preve, com o zero destacado."""
    if df_projecao.empty:
        return _sem_dados()

    rotulos = [rotulo_mes(m) for m in df_projecao["mes"]]
    valores = df_projecao["saldo_acumulado"]
    cor = CORES["perigo"] if (valores < 0).any() else CORES["sucesso"]

    fig = go.Figure(go.Scatter(
        x=rotulos, y=valores, mode="lines+markers", fill="tozeroy",
        line=dict(color=cor, width=2.5), marker=dict(size=5),
        fillcolor="rgba(239,68,68,.08)" if (valores < 0).any() else "rgba(16,185,129,.08)",
        hovertemplate="R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dot", line_color=CORES["neutra"], line_width=1)
    return _estilo(fig, altura=280, legenda=False)


def orcado_vs_real(df: pd.DataFrame) -> go.Figure:
    """Barras lado a lado: quanto foi planejado x quanto foi gasto."""
    if df.empty:
        return _sem_dados()

    dados_grafico = df.iloc[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Orçado", y=dados_grafico["grande_categoria"], x=dados_grafico["orcado"],
        orientation="h", marker=dict(color=CORES["borda"], line=dict(width=0)),
        hovertemplate="Orçado<br>R$ %{x:,.2f}<extra></extra>",
    ))
    cores_real = [
        CORES["perigo"] if s == "estourou"
        else CORES["alerta"] if s == "atenção"
        else CORES["neutra"] if s == "sem meta"
        else CORES["sucesso"]
        for s in dados_grafico["situacao"]
    ]
    fig.add_trace(go.Bar(
        name="Real", y=dados_grafico["grande_categoria"], x=dados_grafico["real"],
        orientation="h", marker=dict(color=cores_real, line=dict(width=0)),
        hovertemplate="Real<br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    altura = max(300, 46 * len(dados_grafico) + 60)
    return _estilo(fig, altura=altura)


def simulacao(df_simulacao: pd.DataFrame) -> go.Figure:
    """Compara o gasto medio atual com o simulado, por grande categoria."""
    if df_simulacao.empty:
        return _sem_dados()

    dados_grafico = df_simulacao.iloc[::-1]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Hoje (média 6M)", y=dados_grafico["grande_categoria"],
        x=dados_grafico["media_mensal"], orientation="h",
        marker=dict(color=CORES["borda"], line=dict(width=0)),
        hovertemplate="Hoje<br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Simulado", y=dados_grafico["grande_categoria"],
        x=dados_grafico["simulado"], orientation="h",
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        hovertemplate="Simulado<br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    altura = max(300, 46 * len(dados_grafico) + 60)
    return _estilo(fig, altura=altura)


def patrimonio(df_evolucao: pd.DataFrame) -> go.Figure:
    """Barras empilhadas: quanto esta em conta e quanto esta aplicado."""
    if df_evolucao.empty:
        return _sem_dados()

    rotulos = [rotulo_mes(m) for m in df_evolucao["mes"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Em conta", x=rotulos, y=df_evolucao["saldo_conta"],
        marker=dict(color=CORES["secundaria"], line=dict(width=0)),
        hovertemplate="Em conta<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Aplicado", x=rotulos, y=df_evolucao["saldo_aplicado"],
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        hovertemplate="Aplicado<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="stack", bargap=0.28)
    marcar_futuro(fig, list(df_evolucao["mes"]))
    return _estilo(fig, altura=340)


def aporte_do_mes_vs_meta(df_movimentacoes: pd.DataFrame,
                           meta_mensal: float) -> go.Figure:
    """Barra por mes: aportou mais ou menos que a meta mensal definida?

    Responde "cumpri o habito este mes?" em vez de "quanto falta para o
    alvo final?" — que e o `progresso_metas` acima. Verde quando o mes bateu
    a meta, cinza quando nao bateu; a linha tracejada marca a meta ATUAL.

    A LINHA E UNICA PARA TODOS OS MESES, DE PROPOSITO. O app nao guarda
    historico de quando a meta mudou de valor — so o valor atual. Desenhar a
    linha atual sobre meses antigos e uma simplificacao honesta: ela mostra
    "como este mes se compara ao que voce quer AGORA", nao uma reconstrucao
    fictícia do que valia em cada mes passado.
    """
    if df_movimentacoes.empty:
        return _sem_dados("Nenhum aporte registrado ainda")

    dados_grafico = df_movimentacoes.tail(12)
    rotulos = [rotulo_mes(m) for m in dados_grafico["mes"]]
    bateu = dados_grafico["aportado"] >= meta_mensal
    cores = [CORES["sucesso"] if b else CORES["borda"] for b in bateu]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Aportado no mês", x=rotulos, y=dados_grafico["aportado"],
        marker=dict(color=cores, line=dict(width=0)),
        hovertemplate="R$ %{y:,.2f}<extra></extra>",
    ))
    if meta_mensal > 0:
        fig.add_hline(
            y=meta_mensal, line_dash="dash", line_color=CORES["texto_fraco"],
            line_width=1.5,
            annotation_text=f"meta: {fmt_brl(meta_mensal)}",
            annotation_position="top left",
        )
    fig.update_layout(showlegend=False, bargap=0.35)
    return _estilo(fig, altura=260)


def progresso_metas(df_metas: pd.DataFrame) -> go.Figure:
    """Barras empilhadas por meta: o que ja tem x o que falta."""
    if df_metas.empty:
        return _sem_dados("Nenhuma meta cadastrada")

    dados_grafico = df_metas.iloc[::-1]
    nomes = [str(m)[:36] for m in dados_grafico["meta"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Já acumulado", y=nomes, x=dados_grafico["ja_acumulado"],
        orientation="h", marker=dict(color=CORES["sucesso"], line=dict(width=0)),
        hovertemplate="Acumulado<br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Falta", y=nomes, x=dados_grafico["falta"],
        orientation="h", marker=dict(color=CORES["borda"], line=dict(width=0)),
        hovertemplate="Falta<br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="stack", bargap=0.35)
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    altura = max(260, 48 * len(dados_grafico) + 60)
    return _estilo(fig, altura=altura)


def amortizacao_por_ano(df_anual: pd.DataFrame) -> go.Figure:
    """Barras empilhadas: quanto de cada ano foi juro e quanto abateu a divida.

    E a imagem que explica por que nos primeiros anos a divida "nao anda":
    a barra vermelha (juros) domina, e a verde (amortizacao) e um fiozinho.
    """
    if df_anual.empty:
        return _sem_dados()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Amortização", x=df_anual["ano"], y=df_anual["amortizacao"],
        marker=dict(color=CORES["sucesso"], line=dict(width=0)),
        hovertemplate="Ano %{x}<br>Amortizado R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Juros", x=df_anual["ano"], y=df_anual["juros"],
        marker=dict(color=CORES["perigo"], line=dict(width=0)),
        hovertemplate="Ano %{x}<br>Juros R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Seguros e taxas", x=df_anual["ano"], y=df_anual["seguros"],
        marker=dict(color=CORES["neutra"], line=dict(width=0)),
        hovertemplate="Ano %{x}<br>Seguros R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="stack", bargap=0.2)
    fig.update_xaxes(title_text="ano do contrato", tickprefix="")
    return _estilo(fig, altura=340)


def saldo_devedor(df_tabela: pd.DataFrame) -> go.Figure:
    """A curva do saldo devedor caindo ao longo do contrato."""
    if df_tabela.empty:
        return _sem_dados()

    fig = go.Figure(go.Scatter(
        x=df_tabela["parcela"], y=df_tabela["saldo_final"],
        mode="lines", fill="tozeroy",
        line=dict(color=CORES["primaria"], width=2.5),
        fillcolor="rgba(79,70,229,.10)",
        hovertemplate="Parcela %{x}<br>Saldo R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(title_text="parcela", tickprefix="")
    return _estilo(fig, altura=300, legenda=False)


def heatmap_dia_semana(df: pd.DataFrame) -> go.Figure:
    """Mapa de calor: em que dia da semana voce gasta mais, mes a mes.

    NOVO — a planilha nao tinha. Revela padrao de habito que a soma mensal
    esconde: sexta e sabado costumam concentrar gasto variavel, e ver isso
    desenhado e mais convincente do que ler numa tabela.
    """
    if df.empty:
        return _sem_dados()

    gastos = df[df["e_despesa"]] if "e_despesa" in df else df
    if gastos.empty or "dia_semana" not in gastos:
        return _sem_dados()

    nomes_dias = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
    tabela = (
        gastos.groupby(["mes_competencia", "dia_semana"])["valor"]
        .sum().mul(-1).reset_index()
    )
    if tabela.empty:
        return _sem_dados()

    meses = sorted(tabela["mes_competencia"].unique())[-8:]
    tabela = tabela[tabela["mes_competencia"].isin(meses)]

    matriz = tabela.pivot(index="dia_semana", columns="mes_competencia",
                          values="valor").reindex(range(7)).fillna(0)

    fig = go.Figure(go.Heatmap(
        z=matriz.values,
        x=[rotulo_mes(m) for m in matriz.columns],
        y=nomes_dias,
        colorscale=[[0, "#EEF2FF"], [0.5, "#818CF8"], [1, "#3730A3"]],
        hovertemplate="%{y} · %{x}<br>R$ %{z:,.2f}<extra></extra>",
        colorbar=dict(title="", thickness=10, tickprefix="R$ "),
    ))
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(tickprefix="")
    return _estilo(fig, altura=300, legenda=False)


def top_estabelecimentos(df: pd.DataFrame, limite: int = 10) -> go.Figure:
    """Os lugares onde mais dinheiro foi gasto no periodo.

    NOVO — a planilha agrupava so por categoria. Ver o ESTABELECIMENTO e o que
    faz reconhecer "eu gasto isso tudo ali?".
    """
    if df.empty:
        return _sem_dados()

    gastos = df[df["e_despesa"]] if "e_despesa" in df else df
    if gastos.empty:
        return _sem_dados()

    agrupado = (
        gastos.assign(lugar=gastos["descricao"].str[:28])
        .groupby("lugar")["valor"].sum().mul(-1)
        .sort_values(ascending=False).head(limite).iloc[::-1]
    )
    if agrupado.empty:
        return _sem_dados()

    fig = go.Figure(go.Bar(
        y=agrupado.index.tolist(), x=agrupado.values, orientation="h",
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        text=[fmt_brl(v) for v in agrupado.values],
        textposition="outside", textfont=dict(size=10),
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    altura = max(280, 30 * len(agrupado) + 60)
    return _estilo(fig, altura=altura, legenda=False)


def cascata_do_mes(receita: float, receita_extra: float, despesa_fixa: float,
                   despesa_variavel: float, despesa_parcelada: float) -> go.Figure:
    """Grafico de cascata: da receita ate o saldo, passo a passo.

    NOVO — mostra o CAMINHO do dinheiro no mes, e nao so o comeco e o fim.
    Cada barra parte de onde a anterior terminou, entao da para ver qual
    parcela do gasto derrubou mais o saldo.
    """
    if receita + receita_extra <= 0 and despesa_fixa + despesa_variavel <= 0:
        return _sem_dados()

    rotulos = ["Receita", "Extraordinária", "Gastos fixos",
               "Parcelas", "Variáveis", "Saldo"]
    valores = [receita, receita_extra, -despesa_fixa,
               -despesa_parcelada, -despesa_variavel, 0]
    medidas = ["relative", "relative", "relative", "relative", "relative", "total"]

    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=medidas,
        x=rotulos,
        y=valores,
        connector=dict(line=dict(color=CORES["borda"], width=1)),
        increasing=dict(marker=dict(color=CORES["sucesso"])),
        decreasing=dict(marker=dict(color=CORES["perigo"])),
        totals=dict(marker=dict(color=CORES["primaria"])),
        text=[fmt_brl(abs(v)) if v else "" for v in valores],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(tickprefix="")
    return _estilo(fig, altura=340, legenda=False)


def gastos_fixos_por_categoria(df_resumo: pd.DataFrame,
                               mapa_cores: dict | None = None) -> go.Figure:
    """Barras do gasto fixo cadastrado por grande categoria."""
    if df_resumo.empty:
        return _sem_dados("Nenhum gasto fixo cadastrado")

    dados_grafico = df_resumo.iloc[::-1]
    nomes = dados_grafico["grande_categoria"].tolist()
    fig = go.Figure(go.Bar(
        y=nomes, x=dados_grafico["total"], orientation="h",
        marker=dict(color=_cores_para(nomes, mapa_cores), line=dict(width=0)),
        text=[fmt_brl(v) for v in dados_grafico["total"]],
        textposition="outside", textfont=dict(size=10),
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    altura = max(260, 34 * len(dados_grafico) + 60)
    return _estilo(fig, altura=altura, legenda=False)


def carteira_evolucao(df_evolucao: pd.DataFrame,
                      nome_referencia: str | None = None) -> go.Figure:
    """Como o valor total da carteira andou, mes a mes.

    A area preenchida ajuda a ler a tendencia; os marcadores mostram os meses
    que voce de fato registrou (um trecho reto e longo costuma ser saldo nao
    atualizado, nao carteira parada).

    Se `df_evolucao` tiver a coluna `referencia`, desenha junto a CARTEIRA-
    SOMBRA: os mesmos aportes rendendo o indice (ver
    `investimentos.carteira_contra_indice`). Linha tracejada e sem
    preenchimento de proposito — ela e uma hipotese, nao dinheiro que existiu,
    e o desenho precisa dizer isso sem legenda.
    """
    if df_evolucao.empty:
        return _sem_dados("Nenhum saldo registrado ainda")

    rotulos = [rotulo_mes(m) for m in df_evolucao["mes"]]
    fig = go.Figure(go.Scatter(
        x=rotulos, y=df_evolucao["saldo"],
        mode="lines+markers", fill="tozeroy",
        line=dict(color=CORES["primaria"], width=2.5),
        fillcolor="rgba(79,70,229,.10)",
        marker=dict(size=6),
        name="Sua carteira",
        hovertemplate="R$ %{y:,.2f}<extra></extra>",
    ))

    tem_referencia = bool("referencia" in df_evolucao.columns
                          and df_evolucao["referencia"].notna().any())
    if tem_referencia:
        fig.add_trace(go.Scatter(
            x=rotulos, y=df_evolucao["referencia"],
            mode="lines",
            line=dict(color=CORES["texto_fraco"], width=1.8, dash="dash"),
            name=f"Se rendesse {nome_referencia or 'o índice'}",
            hovertemplate="R$ %{y:,.2f}<extra></extra>",
        ))

    marcar_futuro(fig, list(df_evolucao["mes"]))
    return _estilo(fig, altura=300, legenda=tem_referencia)


def carteira_por_tipo(df_tipos: pd.DataFrame) -> go.Figure:
    """Rosca da composicao da carteira por tipo de investimento."""
    if df_tipos.empty or df_tipos["saldo"].sum() <= 0:
        return _sem_dados("Cadastre investimentos para ver a composição")

    nomes = df_tipos["tipo"].tolist()
    fig = go.Figure(go.Pie(
        labels=nomes, values=df_tipos["saldo"], hole=0.58,
        marker=dict(colors=_cores_para(nomes, None),
                    line=dict(color="white", width=2)),
        textinfo="label+percent", textposition="outside",
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    ))
    total = df_tipos["saldo"].sum()
    fig.add_annotation(
        text=f"<b>{fmt_brl(total)}</b><br>"
             f"<span style='font-size:11px;color:{CORES['texto_fraco']}'>na carteira</span>",
        showarrow=False, font=dict(size=14, color=CORES["texto"]),
    )
    return _estilo(fig, altura=340, legenda=False)


def aportes_e_rendimento(df_evolucao: pd.DataFrame) -> go.Figure:
    """Barras de aporte e resgate por mes, com a linha do rendimento.

    Separar as tres coisas responde a pergunta que importa: o que fez a
    carteira crescer foi VOCE colocando dinheiro, ou foi ela rendendo?
    """
    if df_evolucao.empty:
        return _sem_dados("Nenhum saldo registrado ainda")

    rotulos = [rotulo_mes(m) for m in df_evolucao["mes"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Aporte", x=rotulos, y=df_evolucao["aporte"],
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        hovertemplate="Aporte<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Resgate", x=rotulos, y=df_evolucao["resgate"],
        marker=dict(color=CORES["alerta"], line=dict(width=0)),
        hovertemplate="Resgate<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Rendimento", x=rotulos, y=df_evolucao["rendimento"],
        mode="lines+markers",
        line=dict(color=CORES["sucesso"], width=2.5),
        marker=dict(size=6),
        hovertemplate="Rendimento<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.25)
    marcar_futuro(fig, list(df_evolucao["mes"]))
    return _estilo(fig, altura=320)


def movimentacoes_investimento(df_movimentacoes: pd.DataFrame) -> go.Figure:
    """O que o EXTRATO diz que foi para investimento, mes a mes.

    Diferente do grafico acima: este nao depende de voce cadastrar nada — sai
    direto dos lancamentos importados. A linha mostra o acumulado.
    """
    if df_movimentacoes.empty:
        return _sem_dados("Nenhuma transferência de investimento encontrada")

    rotulos = [rotulo_mes(m) for m in df_movimentacoes["mes"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Enviado para investimento", x=rotulos,
        y=df_movimentacoes["aportado"],
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        hovertemplate="Enviado<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Resgatado", x=rotulos, y=df_movimentacoes["resgatado"],
        marker=dict(color=CORES["alerta"], line=dict(width=0)),
        hovertemplate="Resgatado<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Acumulado líquido", x=rotulos, y=df_movimentacoes["acumulado"],
        mode="lines+markers",
        line=dict(color=CORES["texto"], width=2.5),
        marker=dict(size=5),
        hovertemplate="Acumulado<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.25)
    return _estilo(fig, altura=330)


def alocacao_atual_vs_meta(df_alocacao: pd.DataFrame) -> go.Figure:
    """Barras deitadas: quanto voce tem em cada classe x quanto queria ter.

    A barra clara e a META, desenhada atras; a colorida e o ATUAL, na frente.
    Sobrepostas (`barmode="overlay"`) em vez de lado a lado de proposito: assim
    da para ver de relance se o atual "encheu" a meta ou passou dela, que e a
    pergunta que a tela responde.

    A cor diz a situacao:
        verde    dentro da faixa de tolerancia
        ambar    abaixo da meta (falta comprar)
        vermelho acima da meta (exposicao maior que a desejada)
    """
    if df_alocacao.empty:
        return _sem_dados("Defina as metas de alocação para ver o gráfico")

    dados_grafico = df_alocacao.iloc[::-1]

    cores = [
        CORES["sucesso"] if dentro
        else CORES["perigo"] if desvio > 0
        else CORES["alerta"]
        for dentro, desvio in zip(dados_grafico["dentro_faixa"],
                                  dados_grafico["desvio"])
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Meta", y=dados_grafico["nome"], x=dados_grafico["percentual_alvo"],
        orientation="h", marker=dict(color=CORES["borda"], line=dict(width=0)),
        hovertemplate="Meta: %{x:.1%}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Atual", y=dados_grafico["nome"], x=dados_grafico["percentual"],
        orientation="h", width=0.45,
        marker=dict(color=cores, line=dict(width=0)),
        hovertemplate="Atual: %{x:.1%}<extra></extra>",
    ))

    fig.update_layout(barmode="overlay", bargap=0.35)
    altura = max(280, 44 * len(dados_grafico) + 70)
    fig = _estilo(fig, altura=altura)
    fig.update_xaxes(showgrid=True, tickformat=".0%", tickprefix="")
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    fig.update_layout(meta={"valores": "percentual"})
    return fig


def rebalanceamento_aporte(df_rebalanceamento: pd.DataFrame) -> go.Figure:
    """Barras de quanto do aporte vai para cada classe.

    So mostra quem recebe alguma coisa: uma classe que ja passou da meta
    aparecendo com barra zero so ocupa espaco e confunde.
    """
    recebem = df_rebalanceamento[df_rebalanceamento["aportar"] > 0.005]
    if recebem.empty:
        return _sem_dados("Nenhuma classe precisa de aporte neste momento")

    dados_grafico = recebem.iloc[::-1]
    fig = go.Figure(go.Bar(
        y=dados_grafico["nome"], x=dados_grafico["aportar"], orientation="h",
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        text=[fmt_brl(v) for v in dados_grafico["aportar"]],
        textposition="outside",
        hovertemplate="Aportar<br>R$ %{x:,.2f}<extra></extra>",
    ))
    altura = max(260, 44 * len(dados_grafico) + 70)
    fig = _estilo(fig, altura=altura, legenda=False)
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    return fig


def variacoes_do_mes(df_variacao: pd.DataFrame) -> go.Figure:
    """Barras divergentes: o que subiu e o que caiu contra o mes anterior.

    O ZERO NO MEIO E O DESENHO. Uma barra para a direita e gasto que subiu,
    para a esquerda e gasto que caiu — o olho le a direcao antes de ler o
    numero, que e exatamente a ordem em que a pergunta se faz ("piorou ou
    melhorou?", depois "quanto?").

    Vermelho para o que subiu e verde para o que caiu, e nao o contrario:
    aqui a variavel e DESPESA, entao subir e ruim. Essa inversao e a mesma
    logica do `delta_positivo` dos cartoes.
    """
    if df_variacao.empty:
        return _sem_dados("Sem mês anterior para comparar")

    dados_grafico = df_variacao.iloc[::-1]
    cores = [CORES["perigo"] if v > 0 else CORES["sucesso"]
             for v in dados_grafico["variacao"]]

    rotulos = []
    for _, linha in dados_grafico.iterrows():
        if linha["variacao_pct"] is None:
            rotulos.append(f"{fmt_brl(linha['variacao'])} (novo)")
        else:
            rotulos.append(
                f"{fmt_brl(linha['variacao'])} ({linha['variacao_pct']:+.0%})")

    fig = go.Figure(go.Bar(
        y=dados_grafico["grande_categoria"], x=dados_grafico["variacao"],
        orientation="h", marker=dict(color=cores, line=dict(width=0)),
        text=rotulos, textposition="outside",
        customdata=list(zip(dados_grafico["anterior"], dados_grafico["atual"])),
        hovertemplate=("%{y}<br>antes R$ %{customdata[0]:,.2f}"
                       "<br>agora R$ %{customdata[1]:,.2f}<extra></extra>"),
    ))
    fig.add_vline(x=0, line_width=1, line_color=CORES["texto_fraco"])

    altura = max(260, 42 * len(dados_grafico) + 70)
    fig = _estilo(fig, altura=altura, legenda=False)
    fig.update_xaxes(showgrid=True, zeroline=False)
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    return fig


def taxa_de_poupanca(df_taxa: pd.DataFrame) -> go.Figure:
    """Quanto por cento da receita sobrou, mes a mes, com a tendencia.

    As BARRAS sao o mes; a LINHA e a media movel de 3 meses. As duas juntas
    porque uma sozinha engana: so as barras e ruido puro (a receita dele
    oscila de R$ ···· a R$ ····), so a linha esconde que houve mes no
    vermelho.

    O eixo e cortado em −100%: um mes magro pode dar −153%, e deixar a escala
    livre espremeria todos os outros meses numa faixa ilegivel por causa de um
    ponto so.
    """
    if df_taxa.empty:
        return _sem_dados("Sem meses suficientes para calcular")

    cores = [CORES["sucesso"] if t >= 0 else CORES["perigo"]
             for t in df_taxa["taxa"]]
    rotulos = [rotulo_mes(m) for m in df_taxa["mes"]]

    parciais = (list(df_taxa["parcial"].fillna(False).astype(bool))
                if "parcial" in df_taxa.columns else [False] * len(df_taxa))
    padroes = ["/" if parcial else "" for parcial in parciais]
    rotulos = [f"{r} *" if parcial else r
               for r, parcial in zip(rotulos, parciais)]

    valores = [fmt_brl(v) for v in df_taxa["saldo"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="No mês", x=rotulos, y=df_taxa["taxa"],
        marker=dict(color=cores, line=dict(width=0),
                    pattern=dict(shape=padroes, solidity=0.35,
                                 fgcolor="white")),
        text=valores, textposition="auto", textfont=dict(size=10),
        cliponaxis=False,
        customdata=df_taxa[["saldo", "receita", "despesa"]].to_numpy(),
        hovertemplate=("<b>%{x}</b><br>sobrou %{y:.1%}"
                       "<br>= R$ %{customdata[0]:,.2f}"
                       "<br><br>receita R$ %{customdata[1]:,.2f}"
                       "<br>despesa R$ %{customdata[2]:,.2f}<extra></extra>"),
    ))
    fig.add_trace(go.Scatter(
        name="Média de 3 meses", x=rotulos, y=df_taxa["media_movel"],
        mode="lines", line=dict(color=CORES["primaria"], width=2.5),
        hovertemplate="média 3M<br>%{y:.1%}<extra></extra>",
    ))
    fig.add_hline(y=0, line_width=1, line_color=CORES["texto_fraco"])

    fig = _estilo(fig, altura=300)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(tickformat=".0%", tickprefix="",
                     range=[max(-1.5, float(df_taxa["taxa"].min()) - 0.22),
                            float(df_taxa["taxa"].max()) + 0.22])
    return fig


def comparativo_anual(df_anos: pd.DataFrame) -> go.Figure:
    """Receita e despesa MEDIAS por mes, um par de barras por ano.

    Por que a media mensal e nao o total: os anos tem tamanhos diferentes
    (2024 comeca em abril, 2026 esta pela metade). Comparar totais faria 2026
    parecer um ano fraco por um motivo que nao tem nada a ver com o dinheiro.
    """
    if df_anos.empty:
        return _sem_dados("Sem anos completos para comparar")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Receita / mês", x=df_anos["ano"], y=df_anos["receita_media"],
        marker=dict(color=CORES["sucesso"], line=dict(width=0)),
        hovertemplate="%{x}<br>receita média R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Despesa / mês", x=df_anos["ano"], y=df_anos["despesa_media"],
        marker=dict(color=CORES["perigo"], line=dict(width=0)),
        hovertemplate="%{x}<br>despesa média R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.35, bargroupgap=0.08)

    for indice, (_, linha) in enumerate(df_anos.iterrows()):
        taxa = (linha["saldo"] / linha["receita"]) if linha["receita"] else 0
        fig.add_annotation(
            x=indice, y=max(linha["receita_media"], linha["despesa_media"]),
            text=f"guardou {taxa:.0%}", showarrow=False, yshift=18,
            font=dict(size=11, color=CORES["texto_fraco"]),
        )

    fig = _estilo(fig, altura=300)
    fig.update_xaxes(showgrid=False)
    return fig


def receita_rateada(df_rateado: pd.DataFrame,
                    n_meses: int | None = 14) -> go.Figure:
    """A mesma receita x despesa, com o PLR DILUIDO pelos 12 meses seguintes.

    O par deste grafico e `historico_receita_despesa`, e a graca esta em ver os
    dois lado a lado:

        COMO ENTROU   fev/2026 com R$ ···· e jul/2026 com R$ ····
                      A realidade do extrato — foi isso que caiu na conta.

        RATEADO       os mesmos meses com R$ ···· e R$ ····
                      A remuneracao de verdade, sem o susto do mes do bonus.

    Nenhum dos dois e mais correto: sao perguntas diferentes. O primeiro
    responde "quanto entrou?", o segundo "quanto eu ganho?".

    O desenho e igual ao do par de proposito — mesmas cores, mesma altura,
    mesma ordem das series. Dois graficos so se comparam quando a unica coisa
    diferente entre eles e o dado.
    """
    if df_rateado.empty:
        return _sem_dados()

    dados_grafico = df_rateado if n_meses is None else df_rateado.tail(n_meses)
    rotulos = [rotulo_mes(m) for m in dados_grafico["mes"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Receita rateada", x=rotulos, y=dados_grafico["receita_rateada"],
        marker=dict(color=CORES["sucesso"], line=dict(width=0)),
        hovertemplate="Receita rateada<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Despesa", x=rotulos, y=dados_grafico["despesa"],
        marker=dict(color=CORES["perigo"], line=dict(width=0)),
        hovertemplate="Despesa<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        name="Saldo", x=rotulos, y=dados_grafico["saldo"],
        mode="lines+markers",
        line=dict(color=CORES["texto"], width=2.5),
        marker=dict(size=6),
        hovertemplate="Saldo<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.25)
    marcar_futuro(fig, list(dados_grafico["mes"]))
    return _estilo(fig, altura=340)


def linha_comparacao_previdencia(df_curva: pd.DataFrame) -> go.Figure:
    """Duas linhas: o liquido do PGBL e o do investimento comum, ano a ano.

    O que esta figura existe para mostrar e o CRUZAMENTO — o ano em que uma
    linha passa a outra. Por isso as duas comecam no mesmo eixo e nao ha
    barra: o olho compara altura de linha muito melhor que altura de barra
    quando a pergunta e "quando vira?".

    Espera as colunas de `previdencia.curva_de_equilibrio`: anos,
    liquido_pgbl, liquido_fora.
    """
    if df_curva.empty:
        return _sem_dados("Sem dados para comparar")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_curva["anos"], y=df_curva["liquido_pgbl"],
        mode="lines", name="PGBL (líquido)",
        line=dict(color=CORES["primaria"], width=2.5),
        hovertemplate="PGBL<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df_curva["anos"], y=df_curva["liquido_fora"],
        mode="lines", name="Investimento comum (líquido)",
        line=dict(color=CORES["neutra"], width=2.5, dash="dash"),
        hovertemplate="Fora do plano<br>R$ %{y:,.2f}<extra></extra>",
    ))

    viradas = df_curva[df_curva["pgbl_ganha"]]
    if not viradas.empty:
        ano = int(viradas.iloc[0]["anos"])
        fig.add_vline(x=ano, line_dash="dot", line_color=CORES["sucesso"],
                      line_width=1.5)

    fig.update_xaxes(title_text="anos até o resgate", tickprefix="")
    return _estilo(fig, altura=320)


def patrimonio_aportado_e_ganho(df_carteira: pd.DataFrame,
                                referencia: pd.DataFrame | None = None) -> go.Figure:
    """Responde: quanto do que eu tenho foi dinheiro meu, e quanto foi ganho?

    Barras empilhadas — o aportado embaixo, o ganho em cima — porque a soma
    das duas E o patrimonio, e a altura de cada pedaco responde a pergunta sem
    ler numero nenhum. Uma linha de saldo sozinha mostra o total e esconde a
    composicao dele: dois patrimonios iguais, um construido com aporte e outro
    com rendimento, desenham a mesma curva.

    O ganho e o ACUMULADO ate cada mes, e pode ser negativo — nesses meses a
    barra desce abaixo do zero, que e a leitura certa: o patrimonio esta abaixo
    do que foi colocado nele.

    `referencia` e a carteira-sombra (`carteira_contra_indice`), desenhada por
    cima como linha tracejada. Ela responde "e se eu tivesse deixado tudo no
    CDI?" — comparacao que so faz sentido em reais, nunca com uma taxa solta.
    """
    if df_carteira.empty:
        return _sem_dados("Sem histórico de carteira")

    dados_grafico = df_carteira.copy()
    liquido = dados_grafico["aporte"].fillna(0) - dados_grafico["resgate"].fillna(0)
    dados_grafico["aportado"] = liquido.cumsum()
    dados_grafico["ganho"] = dados_grafico["saldo"] - dados_grafico["aportado"]
    rotulos = [rotulo_mes(m) for m in dados_grafico["mes"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=rotulos, y=dados_grafico["aportado"], name="Valor aportado",
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        hovertemplate="Aportado<br>R$ %{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=rotulos, y=dados_grafico["ganho"], name="Ganho acumulado",
        marker=dict(color=CORES["sucesso"], line=dict(width=0)),
        hovertemplate="Ganho<br>R$ %{y:,.2f}<extra></extra>",
    ))

    if referencia is not None and not referencia.empty:
        casado = dados_grafico.merge(referencia[["mes", "referencia"]],
                                     on="mes", how="left")
        fig.add_trace(go.Scatter(
            x=rotulos, y=casado["referencia"], name="Se rendesse CDI",
            mode="lines", line=dict(color=CORES["neutra"], width=2, dash="dash"),
            hovertemplate="No CDI<br>R$ %{y:,.2f}<extra></extra>",
        ))

    fig.update_layout(barmode="relative", bargap=0.25)
    marcar_futuro(fig, list(dados_grafico["mes"]))
    return _estilo(fig, altura=340)


def preco_do_papel(df_serie: pd.DataFrame, nome: str = "") -> go.Figure:
    """Responde: como o preco deste papel andou, dia a dia?

    E o unico grafico DIARIO do app, e existe porque para tres papeis existe
    dado diario — tres anos dele, guardado e nunca mostrado. Para o resto da
    carteira a granularidade continua mensal, porque e a que os dados tem.

    O eixo aqui e de DATA, e nao de categoria como nos demais graficos: sao
    centenas de pontos, e um eixo de categoria os trataria como rotulos.
    """
    if df_serie.empty:
        return _sem_dados("Sem cotação guardada para este papel")

    fig = go.Figure(go.Scatter(
        x=pd.to_datetime(df_serie["data"]), y=df_serie["fechamento"],
        mode="lines", fill="tozeroy",
        line=dict(color=CORES["primaria"], width=2),
        fillcolor="rgba(79,70,229,.08)",
        hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.2f}<extra></extra>",
    ))
    fig.update_yaxes(tickprefix="", separatethousands=True)
    fig.update_xaxes(showgrid=False)
    figura = _estilo(fig, altura=280, titulo=nome, legenda=False)
    figura.update_yaxes(tickprefix="")
    return figura


def retorno_por_papel(df_desempenho: pd.DataFrame) -> go.Figure:
    """Responde: quem esta me carregando, e quem esta me atrapalhando?

    Barras divergentes com a linha do zero visivel: o olho le a DIRECAO antes
    do numero, que e a ordem em que a pergunta se faz.

    Papel sem mes medido simplesmente nao aparece — desenhar uma barra de
    tamanho zero para ele diria "ficou parado", e a verdade e "nao da para
    saber". A tela conta esses papeis embaixo do grafico.
    """
    if df_desempenho.empty or "rent_total" not in df_desempenho.columns:
        return _sem_dados("Sem rentabilidade medida ainda")

    medidos = df_desempenho[df_desempenho["rent_total"].notna()]
    medidos = medidos[medidos["saldo"] > 0].sort_values("rent_total")
    if medidos.empty:
        return _sem_dados("Nenhum papel tem mês medido ainda")

    cores = [CORES["sucesso"] if v >= 0 else CORES["perigo"]
             for v in medidos["rent_total"]]
    fig = go.Figure(go.Bar(
        y=medidos["nome"], x=medidos["rent_total"] * 100, orientation="h",
        marker=dict(color=cores, line=dict(width=0)),
        text=[f"{v * 100:,.1f}%" for v in medidos["rent_total"]],
        textposition="outside", textfont=dict(size=11),
        hovertemplate="<b>%{y}</b><br>%{x:,.1f}%<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=CORES["neutra"], line_width=1)
    altura = max(260, 32 * len(medidos) + 60)
    figura = _estilo(fig, altura=altura, legenda=False)
    figura.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    figura.update_xaxes(ticksuffix="%")
    figura.update_layout(meta={"valores": "percentual"})
    return figura


def carteira_contra_indices(df_carteira: pd.DataFrame,
                            colunas_indices: list[str]) -> go.Figure:
    """Responde: a minha carteira ficou na frente ou atras de cada régua?

    A carteira em linha cheia; cada indice como uma carteira-sombra tracejada,
    que recebeu os MESMOS aportes e resgates e rendeu o indice. Sao todas
    curvas de REAIS — desenhar uma taxa junto de um valor nao compara nada,
    porque as escalas nao se falam.

    Todas partem do mesmo ponto no primeiro mes e so se separam a partir do
    segundo. E o unico jeito de a comparacao ser justa: a carteira-sombra nao
    "acerta o comeco", ela acompanha.

    Mes em que um indice nao tem dado vira buraco na linha daquele indice, e
    nao zero — o IPCA sai com um mes de atraso, e uma queda ao chao no ultimo
    mes seria mentira. `connectgaps=False` deixa o buraco a mostra.
    """
    if df_carteira.empty:
        return _sem_dados("Sem histórico de carteira")

    rotulos = [rotulo_mes(m) for m in df_carteira["mes"]]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=rotulos, y=df_carteira["saldo"], name="Sua carteira",
        mode="lines", fill="tozeroy",
        line=dict(color=CORES["primaria"], width=3),
        fillcolor="rgba(79,70,229,.08)",
        hovertemplate="Carteira<br>R$ %{y:,.2f}<extra></extra>",
    ))

    tons = [CORES["sucesso"], CORES["alerta"], CORES["perigo"],
            CORES["secundaria"], CORES["neutra"], "#8B5CF6"]
    for posicao, nome in enumerate(colunas_indices):
        if nome not in df_carteira.columns:
            continue
        fig.add_trace(go.Scatter(
            x=rotulos, y=df_carteira[nome], name=nome, mode="lines",
            connectgaps=False,
            line=dict(color=tons[posicao % len(tons)], width=2, dash="dash"),
            hovertemplate=f"{nome}<br>R$ %{{y:,.2f}}<extra></extra>",
        ))

    marcar_futuro(fig, list(df_carteira["mes"]))
    return _estilo(fig, altura=380)


def velocimetro(fracao, titulo: str = "", teto: float = 1.5,
                invertido: bool = False, julgar: bool = True,
                altura: int = 175) -> go.Figure:
    """Meio-circulo com a porcentagem no meio: cumpri o plano ou nao?

    `fracao` e o realizado dividido pelo planejado, em FRACAO (1.0 = 100%,
    como em `c.barra` e `fmt_pct`) — a funcao multiplica por 100 para
    desenhar. O `teto` tambem e fracao: 1.5 = o ponteiro vai ate 150%.

    O RISQUINHO EM 100% E O PONTO DO GRAFICO. Sem ele o meio-circulo e so
    decoracao: "68%" nao diz nada sozinho, porque nao ha nada na tela dizendo
    onde ficaria o suficiente. Com a marca, bate o olho e ve de que lado dela
    voce esta.

    `invertido=True` inverte o juizo, para o indicador em que passar de 100% e
    o problema (gastar 130% do orcamento), e nao a conquista.

    A COR SEGUE A CONVENCAO DA CASA: verde cumpriu, ambar esta perto,
    vermelho nao cumpriu. E o numero e percentual — por isso a figura se marca
    com `meta={"valores": "percentual"}`, que e o que faz o olhinho deixar ela
    passar inteira (ver ui/privacidade.py). Os valores em R$ que acompanham o
    velocimetro ficam FORA dele, em `st.caption`, onde o olhinho os alcanca.

    `julgar=False` DESLIGA a cor de juizo e usa o indigo neutro. E para o
    indicador que mede ANDAMENTO, nao cumprimento: uma meta 27% concluida nao
    esta reprovada, esta no meio do caminho. Pintar isso de vermelho seria o
    painel repreendendo alguem por estar comecando.
    """
    valor = 0.0 if vazio(fracao) else float(fracao) * 100
    limite = max(1.0, float(teto) * 100)

    if not julgar:
        cor = CORES["primaria"]
    elif invertido:
        cor = (CORES["sucesso"] if valor <= 100
               else CORES["alerta"] if valor <= 120 else CORES["perigo"])
    else:
        cor = (CORES["sucesso"] if valor >= 100
               else CORES["alerta"] if valor >= 80 else CORES["perigo"])

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        # O VALOR VAI INTEIRO, sem teto. O Plotly ja para de desenhar a barra
        # no fim do eixo sozinho; limitar aqui limitaria tambem o NUMERO, e um
        # aporte de 500% do necessario apareceria escrito como 225%. Um painel
        # que arredonda a propria escala para caber no desenho mente no unico
        # lugar onde ninguem desconfia — o numero grande no meio.
        value=valor,
        number=dict(suffix="%", valueformat=",.1f",
                    font=dict(size=30, color=CORES["texto"])),
        gauge=dict(
            shape="angular",
            axis=dict(range=[0, limite], tickvals=[0, limite],
                      tickfont=dict(size=10, color=CORES["texto_fraco"]),
                      tickwidth=0, ticklen=2),
            bar=dict(color=cor, thickness=0.62, line=dict(width=0)),
            bgcolor=CORES["borda"],
            borderwidth=0,
            threshold=dict(value=min(100, limite), thickness=0.85,
                           line=dict(color=CORES["texto_fraco"], width=2)),
        ),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))

    fig.update_layout(
        template=MODELO, height=altura, separators=",.",
        margin=dict(l=18, r=18, t=34 if titulo else 12, b=4),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                  size=12, color=CORES["texto"]),
        showlegend=False,
        meta={"valores": "percentual"},
    )
    if titulo:
        fig.update_layout(title=dict(
            text=titulo, x=0.5, xanchor="center", y=0.97, yanchor="top",
            font=dict(size=13, color=CORES["texto_fraco"])))
    return fig


def historico_preco(df_historico: pd.DataFrame,
                    preco_alvo: float | None = None,
                    altura: int = 200) -> go.Figure:
    """A curva do preco de um item da lista de desejos, em degrau.

    EM DEGRAU (`line_shape="hv"`), NAO EM RETA. Como so os pontos de MUDANCA
    sao gravados (ver financas/precos.py), ligar 4.299 de julho a 3.999 de
    agosto com uma reta desenharia uma queda gradual que nunca aconteceu. O
    preco ficou parado em 4.299 ate o dia em que virou 3.999 — e e isso que o
    degrau mostra.

    O menor preco ja visto ganha marcador proprio: e o numero contra o qual
    voce compara o preco de hoje.
    """
    if df_historico is None or df_historico.empty:
        return _sem_dados("Sem histórico de preço ainda")

    dados = df_historico.sort_values("data")
    precos = dados["preco"].astype(float)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dados["data"], y=precos, name="Preço", mode="lines+markers",
        line=dict(color=CORES["primaria"], width=2, shape="hv"),
        marker=dict(size=6, color=CORES["primaria"]),
        hovertemplate="%{x}<br>R$ %{y:,.2f}<extra></extra>",
    ))

    linha_menor = dados.loc[precos.idxmin()]
    fig.add_trace(go.Scatter(
        x=[linha_menor["data"]], y=[float(linha_menor["preco"])],
        name="Menor já visto", mode="markers",
        marker=dict(size=11, color=CORES["sucesso"], symbol="circle",
                    line=dict(color="white", width=2)),
        hovertemplate="Menor já visto<br>R$ %{y:,.2f}<extra></extra>",
    ))

    if preco_alvo and float(preco_alvo) > 0:
        fig.add_hline(
            y=float(preco_alvo), line=dict(color=CORES["sucesso"], width=1.5,
                                           dash="dash"),
            annotation_text=f"alvo {fmt_brl(preco_alvo)}",
            annotation_position="top left",
            annotation_font=dict(size=10, color=CORES["sucesso"]),
        )

    fig.update_xaxes(showgrid=False)
    return _estilo(fig, altura=altura, legenda=False)


def calendario_compras(df_calendario: pd.DataFrame,
                       n_meses: int = 12) -> go.Figure:
    """Quanto tempo falta ate cada item da lista caber no orcamento.

    Uma barra deitada por item, do mes atual ate o mes em que ele cabe. Barra
    curta = compra logo; barra longa = a fila esta na frente. Quem nao cabe no
    horizonte aparece com a barra cheia e o rotulo dizendo isso — some da tela
    seria esconder justamente o item que voce precisa reavaliar.

    A cor e a PRIORIDADE, nao o prazo: e ela que define a fila, e ver um item
    "Baixa" na frente de um "Alta" e o sinal de que a prioridade esta errada.
    """
    if df_calendario is None or df_calendario.empty:
        return _sem_dados("Nada em aberto na lista de desejos")

    dados = df_calendario.iloc[::-1]
    cor_por_prioridade = {"Alta": CORES["perigo"], "Média": CORES["alerta"],
                          "Baixa": CORES["neutra"]}

    nomes, esperas, cores, textos, detalhes, tramas = [], [], [], [], [], []
    for _, item in dados.iterrows():
        nomes.append(str(item["item"])[:34])
        cores.append(cor_por_prioridade.get(item.get("prioridade"),
                                            CORES["secundaria"]))
        if vazio(item.get("mes_sugerido")):
            esperas.append(n_meses)
            textos.append(f"não cabe em {n_meses} meses")
            detalhes.append("não cabe no horizonte")
            tramas.append("/")      # barra listrada: a data e hipotetica
        else:
            espera = int(item["meses_de_espera"])
            esperas.append(max(espera, 0.25))     # 0 meses ainda tem de aparecer
            marca = "" if item.get("cabe_no_alvo", True) else " ⚠"
            textos.append(f"{rotulo_mes(str(item['mes_sugerido']))}{marca}")
            detalhes.append(f"{espera} mês(es) de espera")
            tramas.append("")

    fig = go.Figure(go.Bar(
        y=nomes, x=esperas, orientation="h",
        marker=dict(color=cores, line=dict(width=0),
                    pattern=dict(shape=tramas, solidity=0.35,
                                 fgcolor="rgba(255,255,255,.55)")),
        text=textos,
        # "auto", e nao "outside": a barra de quem nao cabe vai ate o fim do
        # eixo, e o rotulo dela por fora cairia fora da area desenhada — que
        # e exatamente o item cuja explicacao voce mais precisa ler.
        textposition="auto", textfont=dict(size=11),
        customdata=detalhes,
        hovertemplate="<b>%{y}</b><br>%{customdata}<extra></extra>",
    ))

    # Nao ha um real nesta figura: o eixo mede MESES, o rotulo e um mes do
    # calendario e o eixo de baixo e o nome do item. Por isso ela se declara
    # "sem_dinheiro" e passa inteira pelo olhinho — escondida, viraria um
    # punhado de barras sem legenda, sem proteger nada (ver ui/privacidade.py).
    fig.update_layout(bargap=0.35, meta={"valores": "sem_dinheiro"})
    altura = max(240, 34 * len(dados) + 70)
    fig = _estilo(fig, altura=altura, legenda=False)
    fig.update_xaxes(title_text="meses até caber no orçamento", showgrid=True,
                     dtick=1, range=[0, n_meses + 0.6])
    fig.update_yaxes(tickprefix="", separatethousands=False,
                     gridcolor="rgba(0,0,0,0)")
    return fig


def rosca_alocacao(nomes, valores, titulo: str = "",
                   mostrar_total: bool = True,
                   vazio_texto: str = "Sem dados") -> go.Figure:
    """Rosca de composicao, generica: recebe listas em vez de um DataFrame.

    `carteira_por_tipo` ja desenha uma rosca, mas amarrada as colunas `tipo` e
    `saldo`. Esta serve a QUALQUER eixo — macro, classe, prazo, indexador — e
    e a mesma peca usada nas duas roscas do rebalanceamento (a ideal, que vem
    de percentuais, e a atual, que vem de reais). Duas funcoes quase iguais
    acabariam divergindo no dia em que uma ganhasse um acabamento.

    `mostrar_total=False` para a rosca da carteira IDEAL: ali os valores sao
    percentuais de meta, e escrever "100%" no buraco nao acrescenta nada.
    """
    valores = [float(v or 0) for v in valores]
    if not nomes or sum(valores) <= 0:
        return _sem_dados(vazio_texto)

    nomes = [str(n) for n in nomes]
    fig = go.Figure(go.Pie(
        labels=nomes, values=valores, hole=0.58, sort=False,
        marker=dict(colors=_cores_para(nomes, None),
                    line=dict(color="white", width=2)),
        textinfo="percent", textposition="inside",
        insidetextorientation="horizontal",
        hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
    ))
    if mostrar_total:
        total = sum(valores)
        fig.add_annotation(
            text=f"<b>{fmt_brl(total)}</b><br>"
                 f"<span style='font-size:11px;color:{CORES['texto_fraco']}'>"
                 f"na carteira</span>",
            showarrow=False, font=dict(size=13, color=CORES["texto"]))

    fig = _estilo(fig, altura=300, titulo=titulo, legenda=True)
    fig.update_layout(legend=dict(orientation="v", yanchor="middle", y=0.5,
                                  xanchor="left", x=1.02, font=dict(size=11)))
    return fig
