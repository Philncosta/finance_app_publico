"""
planejamento.py — Orcamento, simulador de cortes e projecao de caixa.
==============================================================================

TRES ABAS, TRES PERGUNTAS
-------------------------
    Orçamento    "Estou dentro do que planejei este mês?"
    Simulador    "E se eu cortasse 20% de Comida? Quanto sobraria?"
    Projeção     "Com o que já sei hoje, como fica meu saldo em 18 meses?"

SOBRE A PROJECAO
----------------
Ela nao adivinha. Soma quatro coisas ja conhecidas: salario previsto, gastos
fixos cadastrados, parcelas ja contratadas e a MEDIANA do gasto variavel
recente.

Usamos mediana, e nao media, por um motivo concreto: em fevereiro voce
comprou uma moto de R$ ···· num Pix so. A media de 6 meses sobe de
R$ ···· para R$ ···· por causa disso e a projecao passa a supor que voce
compra uma moto todo mes. A mediana ignora esse tipo de evento unico.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from financas import banco, dados
from financas.calculos import fixos, planejamento, previsao
from financas.formato import rotulo_mes
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado, graficos

df = estado.lancamentos()

c.cabecalho("Planejamento", "Orçamento, simulação e projeção de caixa")
c.mostrar_recado()

if df.empty:
    c.aviso_vazio("Sem lançamentos ainda.")
    st.stop()

mes = estado.seletor_de_mes_topo()

aba_orcamento, aba_simulador, aba_projecao = st.tabs(
    ["Orçamento do mês", "Simulador de cenários", "Projeção de caixa"]
)


with aba_orcamento:
    comparacao = planejamento.orcado_vs_real(df, mes)

    if comparacao.empty:
        c.aviso_vazio(
            "Nenhum orçamento definido ainda.",
            "Use a tabela abaixo para definir quanto pretende gastar em cada "
            "grande categoria.",
        )
    else:
        total_orcado = float(comparacao["orcado"].sum())
        total_real = float(comparacao["real"].sum())
        estourados = comparacao[comparacao["situacao"] == "estourou"]

        c.linha_kpis([
            {"rotulo": "Orçado no mês", "valor": fmt_brl(total_orcado), "cor": "azul"},
            {"rotulo": "Gasto real", "valor": fmt_brl(total_real),
             "cor": "vermelha" if total_real > total_orcado else "verde"},
            {"rotulo": "Diferença", "valor": fmt_brl(total_orcado - total_real),
             "ajuda": "sobrou" if total_orcado >= total_real else "estourou",
             "cor": "verde" if total_orcado >= total_real else "vermelha"},
            {"rotulo": "Categorias estouradas", "valor": str(len(estourados)),
             "cor": "vermelha" if len(estourados) else "verde",
             "ajuda": f"de {len(comparacao)} com meta"},
        ])

        with c.painel(chave="orcado_vs_real"):
            priv.grafico(graficos.orcado_vs_real(comparacao),
                         width="stretch", key="planejamento_orcado_vs_real")

        st.markdown("**Detalhe por grande categoria**")
        tabela = comparacao.copy()
        tabela["pct_usado"] = tabela["pct_usado"] * 100
        priv.tabela(
            tabela.rename(columns={
                "grande_categoria": "Grande categoria", "orcado": "Orçado",
                "real": "Real", "diferenca": "Sobra", "pct_usado": "% usado",
                "situacao": "Situação",
            }),
            hide_index=True, width="stretch",
            column_config={
                "Orçado": c.config_moeda("Orçado"),
                "Real": c.config_moeda("Real"),
                "Sobra": c.config_moeda("Sobra", "negativo = estourou"),
                "% usado": c.config_percentual("% usado"),
            },
        )

    st.markdown("---")
    st.markdown("### Definir o orçamento")
    st.caption(
        f"As metas valem a partir de {rotulo_mes(mes)} e são herdadas pelos "
        "meses seguintes até você mudar de novo."
    )

    grandes = estado.lista_grandes_categorias()
    metas_atuais = planejamento.orcamento_do_mes(mes)

    medias = planejamento.media_por_grande_categoria(df, mes, 6)
    mapa_medias = dict(zip(medias["grande_categoria"], medias["media_mensal"])) \
        if not medias.empty else {}

    para_editar = pd.DataFrame({
        "Grande categoria": grandes,
        "Meta (R$)": [float(metas_atuais.get(g, 0.0)) for g in grandes],
        "Média 6M": [round(float(mapa_medias.get(g, 0.0)), 2) for g in grandes],
    })

    editado_orcamento = priv.editor(
        para_editar, hide_index=True, width="stretch", key="editor_orcamento",
        column_config={
            "Grande categoria": st.column_config.TextColumn(disabled=True),
            "Meta (R$)": st.column_config.NumberColumn(
                "Meta (R$)", format="R$ %.2f", min_value=0.0, step=50.0),
            "Média 6M": st.column_config.NumberColumn(
                "Média 6M", format="R$ %.2f", disabled=True,
                help="quanto você realmente gastou por mês, em média"),
        },
    )

    col_salvar, col_copiar = st.columns([1, 1])
    with col_salvar:
        if st.button("Salvar orçamento", type="primary", width="stretch"):
            valores = dict(zip(editado_orcamento["Grande categoria"],
                               editado_orcamento["Meta (R$)"]))
            planejamento.salvar_orcamento(mes, valores)
            estado.limpar_cache()
            c.recado(f"Orçamento de {rotulo_mes(mes)} salvo.")
            st.rerun()
    with col_copiar:
        if st.button("Usar a média de 6 meses como meta", width="stretch"):
            valores = dict(zip(editado_orcamento["Grande categoria"],
                               editado_orcamento["Média 6M"]))
            planejamento.salvar_orcamento(mes, valores)
            estado.limpar_cache()
            c.recado("Metas preenchidas com a média dos últimos 6 meses.")
            st.rerun()


with aba_simulador:
    st.markdown("### E se eu cortasse?")
    st.caption(
        "Mexa nos controles e veja o efeito no seu saldo mensal. A base é o "
        "gasto médio dos últimos 6 meses de cada grande categoria."
    )

    receita_padrao = banco.obter_parametro_num("salario_previsto", 0.0)
    if not receita_padrao:
        serie = dados.por_mes(df)
        if not serie.empty and "quantidade" in serie.columns:
            reais = serie[serie["quantidade"] >= 5].tail(6)
            if not reais.empty:
                receita_padrao = float(
                    (reais["receita"] - reais["receita_extra"]).mean())

    receita_simulada = st.number_input(
        "Receita mensal considerada (R$)",
        min_value=0.0, value=float(round(receita_padrao, 2)), step=100.0,
        help="Por padrão, a média da sua receita recorrente. Mude para simular "
             "um aumento, uma queda ou uma renda extra.",
    )

    base = planejamento.media_por_grande_categoria(df, mes, 6)

    if base.empty:
        c.aviso_vazio("Não há histórico suficiente para simular.")
    else:
        st.markdown("**Ajuste cada grande categoria**")
        ajustes = {}
        colunas = st.columns(3)
        for indice, (_, linha) in enumerate(base.iterrows()):
            categoria = linha["grande_categoria"]
            with colunas[indice % 3]:
                percentual = st.slider(
                    f"{categoria} · {fmt_brl(linha['media_mensal'])}",
                    min_value=-80, max_value=50, value=0, step=5,
                    format="%d%%", key=f"slider_{categoria}",
                )
                ajustes[categoria] = percentual / 100

        resultado = planejamento.simular(df, mes, ajustes, receita_simulada, 6)

        st.markdown("---")
        c.linha_kpis([
            {"rotulo": "Gasto hoje (média)", "valor": fmt_brl(resultado["total_atual"])},
            {"rotulo": "Gasto simulado", "valor": fmt_brl(resultado["total_simulado"]),
             "cor": "azul"},
            {"rotulo": "Economia por mês", "valor": fmt_brl(resultado["economia"]),
             "cor": "verde" if resultado["economia"] > 0 else None,
             "ajuda": f"{fmt_brl(resultado['economia'] * 12)} por ano"},
            {"rotulo": "Saldo simulado", "valor": fmt_brl(resultado["saldo_simulado"]),
             "cor": "verde" if resultado["saldo_simulado"] >= 0 else "vermelha",
             "delta": f"era {fmt_brl(resultado['saldo_atual'])}",
             "delta_positivo": resultado["saldo_simulado"] > resultado["saldo_atual"]},
        ])

        if resultado["economia"] > 0:
            c.nota(
                f"Cortando o que você marcou, sobrariam "
                f"<strong>{fmt_brl(resultado['economia'])}</strong> por mês — "
                f"<strong>{fmt_brl(resultado['economia'] * 12)}</strong> em um ano. "
                f"Esse é o valor que poderia ir para as metas."
            )

        with c.painel(chave="simulacao"):
            priv.grafico(graficos.simulacao(resultado["tabela"]),
                         width="stretch", key="planejamento_simulacao")


with aba_projecao:
    st.markdown("### Como fica o caixa daqui pra frente")

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        n_meses = st.slider("Meses à frente", 6, 24, 18, key="proj_meses")
    with col2:
        salario_projecao = st.number_input(
            "Salário previsto (R$)",
            min_value=0.0,
            value=float(round(banco.obter_parametro_num("salario_previsto", 0.0), 2)),
            step=100.0,
            help="Deixe zero para o app usar a média da sua receita recorrente.",
        )
    with col3:
        from financas.calculos import patrimonio as calc_patrimonio
        posicao = calc_patrimonio.posicao_atual(df, mes)
        saldo_inicial = st.number_input(
            "Saldo em conta hoje (R$)",
            value=float(round(posicao["saldo_conta"], 2)), step=100.0,
            help="Ponto de partida do saldo acumulado.",
        )

    if salario_projecao and salario_projecao != banco.obter_parametro_num("salario_previsto", 0.0):
        banco.definir_parametro("salario_previsto", salario_projecao)

    planejados = planejamento.gastos_planejados(mes, n_meses)
    total_planejado = float(planejados["valor"].sum()) if not planejados.empty else 0.0

    incluir_planejados = st.toggle(
        "Descontar o que eu já planejei",
        value=False, key="proj_incluir_planejados",
        help="Viagens, mobília e compras grandes que você marcou com mês-alvo "
             "nas telas de Metas e de Futuras compras.",
        disabled=planejados.empty,
    )
    if planejados.empty:
        st.caption(
            "Nada planejado com data dentro da janela. Para uma viagem ou "
            "uma compra grande aparecer aqui, cadastre em **Metas e compras** "
            "com um prazo — meta do tipo *Compra à vista*, ou item da lista "
            "de desejos com **mês-alvo**."
        )

    projecao = planejamento.projecao_caixa(
        df, mes, n_meses,
        salario_previsto=salario_projecao or None,
        saldo_inicial=saldo_inicial,
        incluir_planejados=incluir_planejados,
    )

    if projecao.empty:
        c.aviso_vazio("Não foi possível montar a projeção.")
    else:
        media_saldo = float(projecao["saldo_mes"].median())
        pior = projecao.loc[projecao["saldo_acumulado"].idxmin()]

        if not planejados.empty:
            if incluir_planejados:
                st.success(
                    f"**{fmt_brl_md(total_planejado)} de gasto planejado "
                    f"estão descontados** na projeção abaixo, cada um no mês "
                    f"em que você marcou."
                )
            else:
                st.warning(
                    f"**Você tem {fmt_brl_md(total_planejado)} planejados que "
                    f"NÃO estão nesta projeção.** Ligue o botão acima para ver "
                    f"o caixa com eles dentro — é a diferença entre o que você "
                    f"gasta todo mês e o que vai gastar de uma vez."
                )
            with st.expander(f"O que está planejado ({len(planejados)} item(ns))"):
                visao_plan = planejados.copy()
                visao_plan["mes"] = visao_plan["mes"].map(rotulo_mes)
                priv.tabela(
                    visao_plan.rename(columns={
                        "mes": "Mês", "descricao": "O quê",
                        "valor": "Valor", "origem": "De onde vem"}),
                    hide_index=True, width="stretch",
                    column_config={"Valor": c.config_moeda("Valor")},
                )
                st.caption(
                    "Metas de **Reserva**, **Acumular** e **Financiamento** "
                    "não entram aqui de propósito: elas são plano de "
                    "poupança, que se espalha por muitos meses. Tratá-las "
                    "como despesa de um mês só inventaria um rombo que não "
                    "existe."
                )

        c.linha_kpis([
            {"rotulo": "Saldo mensal típico", "valor": fmt_brl(media_saldo),
             "ajuda": "mediana dos meses projetados",
             "cor": "verde" if media_saldo >= 0 else "vermelha"},
            {"rotulo": "Fatura prevista do mês",
             "valor": fmt_brl(float(projecao["fixos_cartao"].iloc[0]
                                    + projecao["parcelas_cartao"].iloc[0])),
             "ajuda": f"já vendido em {rotulo_mes(projecao['mes'].iloc[0])} "
                      f"antes de comprar nada"},
            {"rotulo": "Pior momento",
             "valor": fmt_brl(float(pior["saldo_acumulado"])),
             "ajuda": f"em {rotulo_mes(pior['mes'])}",
             "cor": "vermelha" if pior["saldo_acumulado"] < 0 else "verde"},
            {"rotulo": "Saldo ao final",
             "valor": fmt_brl(float(projecao["saldo_acumulado"].iloc[-1])),
             "ajuda": f"em {rotulo_mes(projecao['mes'].iloc[-1])}",
             "cor": "verde" if projecao["saldo_acumulado"].iloc[-1] >= 0 else "vermelha"},
        ])

        for aviso in planejamento.alertas_da_projecao(projecao):
            st.warning(priv.texto(aviso))

        with c.painel("De que é feita a despesa de cada mês"):
            priv.grafico(graficos.projecao_caixa(projecao),
                         width="stretch", key="planejamento_projecao_caixa")

        with c.painel("Saldo acumulado projetado"):
            priv.grafico(graficos.linha_saldo_projetado(projecao),
                         width="stretch", key="planejamento_linha_saldo_projetado")

        with st.expander("Tabela da projeção"):
            colunas_visiveis = ["mes", "receita_prevista", "fixos_conta",
                                "fixos_cartao", "parcelas_cartao",
                                "outras_variaveis", "total_despesas",
                                "saldo_mes", "saldo_acumulado"]
            priv.tabela(
                projecao[colunas_visiveis]
                .assign(mes=projecao["mes"].map(rotulo_mes)).rename(columns={
                    "mes": "Mês", "receita_prevista": "Receita",
                    "fixos_conta": "Fixos (conta)",
                    "fixos_cartao": "Fixos (cartão)",
                    "parcelas_cartao": "Parcelas",
                    "outras_variaveis": "Outras", "total_despesas": "Despesa total",
                    "saldo_mes": "Saldo do mês", "saldo_acumulado": "Acumulado",
                }),
                hide_index=True, width="stretch",
                column_config={
                    coluna: c.config_moeda(coluna) for coluna in
                    ["Receita", "Fixos (conta)", "Fixos (cartão)", "Parcelas",
                     "Outras", "Despesa total", "Saldo do mês", "Acumulado"]
                },
            )
            st.caption(
                "**Fixos (conta)** sai direto da conta — boleto, Pix, débito. "
                "**Fixos (cartão)** e **Parcelas** caem na mesma fatura: somados, "
                "são o quanto do seu cartão já está comprometido antes de você "
                "comprar qualquer coisa. **Outras** é a mediana do seu gasto "
                "variável não parcelado dos últimos 6 meses — mediana, para que "
                "uma compra grande e única não distorça todos os meses à frente."
            )

        with st.expander("Item a item: o que compõe a despesa de cada mês"):
            meses_projetados = list(projecao["mes"])
            mes_item = st.selectbox(
                "Mês", meses_projetados, format_func=rotulo_mes,
                key="proj_mes_item")
            composicao = previsao.composicao_do_mes(df, mes_item, mes_base=mes)
            resumo_item = previsao.resumo_da_composicao(composicao)

            if composicao.empty:
                c.aviso_vazio("Nada projetado para este mês.")
            else:
                variavel_do_mes = float(
                    projecao[projecao["mes"] == mes_item]
                    ["outras_variaveis"].iloc[0])
                c.linha_kpis([
                    {"rotulo": "Já contratado",
                     "valor": fmt_brl(resumo_item["total"]),
                     "ajuda": "fixo + parcela, item a item"},
                    {"rotulo": "Cartão", "valor": fmt_brl(resumo_item["cartao"]),
                     "ajuda": "cai na fatura"},
                    {"rotulo": "Conta", "valor": fmt_brl(resumo_item["conta"]),
                     "ajuda": "boleto, Pix, débito"},
                    {"rotulo": "Variável (média)",
                     "valor": fmt_brl(variavel_do_mes),
                     "ajuda": "não está na tabela abaixo"},
                ])
                visao_comp = composicao.copy()
                visao_comp["item"] = visao_comp.apply(
                    lambda l: c.rotulo_com_fixo(l["fixo"], l["item"]), axis=1)
                priv.tabela(
                    visao_comp[["item", "categoria", "forma", "valor",
                                "situacao"]].rename(columns={
                        "item": "Item", "categoria": "Categoria",
                        "forma": "Forma", "valor": "Valor",
                        "situacao": "Situação"}),
                    hide_index=True, width="stretch",
                    column_config={"Valor": c.config_moeda("Valor")},
                )
                st.caption(
                    f"**{resumo_item['linhas']} linhas somam "
                    f"{fmt_brl_md(resumo_item['total'])}** — é o que já está "
                    f"contratado para {rotulo_mes(mes_item)}, e é o mesmo "
                    f"número que o Dashboard mostra em *Despesa*.\n\n"
                    f"A *Despesa total* da tabela acima é maior porque soma "
                    f"também **{fmt_brl_md(variavel_do_mes)}** de gasto "
                    f"variável — a sua mediana dos últimos 6 meses fechados. "
                    f"Ele não aparece linha a linha porque não existe ainda: "
                    f"é padrão de comportamento, não compromisso. **É também a "
                    f"parte que você mais consegue mudar.**"
                )

        with st.expander("De onde vêm os gastos fixos deste mês"):
            meses_projetados = list(projecao["mes"])
            mes_detalhe = st.selectbox(
                "Mês", meses_projetados, format_func=rotulo_mes,
                key="proj_mes_detalhe")
            detalhe = fixos.situacao_no_mes(
                estado.cadastro_fixos(), df, mes_detalhe, mes)
            if detalhe.empty:
                c.aviso_vazio("Nenhum gasto fixo cadastrado.")
            else:
                priv.tabela(
                    detalhe[["item", "forma_pagamento", "cadastrado",
                             "entra_na_previsao", "situacao", "motivo"]].rename(
                        columns={
                            "item": "Item", "forma_pagamento": "Como paga",
                            "cadastrado": "Cadastrado",
                            "entra_na_previsao": "Entra",
                            "situacao": "Situação", "motivo": "Por quê"}),
                    hide_index=True, width="stretch",
                    column_config={
                        "Cadastrado": c.config_moeda("Cadastrado"),
                        "Entra": c.config_moeda("Entra"),
                    },
                )
                st.caption(
                    "Um item cadastrado que já está sendo projetado como "
                    "parcela do cartão entra com zero: a parcela é fato "
                    "contratado e o cadastro é estimativa, então quando os "
                    "dois descrevem a mesma despesa, o fato manda."
                )
