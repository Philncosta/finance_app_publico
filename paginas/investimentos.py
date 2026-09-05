"""
investimentos.py — A carteira: cadastrar, acompanhar e medir rendimento.
==============================================================================

POR QUE ESTA TELA TEM DUAS METADES
----------------------------------
O extrato da conta corrente sabe dizer quanto dinheiro SAIU para a conta de
investimento. Ele nao sabe em QUE voce aplicou, quanto aquilo VALE hoje, nem
quanto RENDEU — isso vive na corretora.

    METADE AUTOMÁTICA   sai dos lançamentos importados. Zero trabalho.
    METADE MANUAL       você anota o saldo de cada aplicação, uma vez por mês.

A aba **Carteira** cruza as duas e diz se batem.

A ROTINA DE DOIS MINUTOS
------------------------
Uma vez por mês: abra a corretora, veja quanto cada aplicação vale, e digite
na aba *Atualizar saldos*. O app já sabe quanto você aportou (veio do
extrato), então ele calcula o rendimento sozinho.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from financas import banco, cambio, cotacoes, dados, indices
from financas.calculos import investimentos as calc
from financas.calculos import fechamento
from financas.leitores.extrato_xp_xlsx import DESCRICAO_TIPOS
from financas.formato import (fmt_num, fmt_pct, normalizar_texto,
                              rotulo_mes, somar_meses, vazio)
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import analise, estado, graficos


def _texto_ou_none(valor) -> str | None:
    """Converte para texto limpo, ou `None` quando vazio.

    Uma célula vazia do `st.data_editor` chega como `NaN` do pandas, e
    `NaN or ""` continua sendo `NaN` (porque `bool(NaN)` é `True`) — daí
    `str(x or "")` gravar a STRING "nan" no banco em vez de None. `vazio()`
    é a única forma segura de checar isso.
    """
    return None if vazio(valor) else str(valor).strip() or None


df = estado.lancamentos()

desempenho = estado.carteira_desempenho()
conciliacao = estado.carteira_conciliacao(None)
evolucao_carteira = estado.carteira_evolucao()
carteira_vs_cdi = estado.carteira_contra_indice("CDI")
grade_rentabilidade = estado.carteira_rentabilidade_mensal()
cadastro = calc.cadastro()
movimentacoes = calc.fluxo_externo_por_mes()

posicao = estado.carteira_posicao(None)
alocacao = estado.carteira_alocacao(None, "classe", posicao)
alocacao_macro = estado.carteira_alocacao(None, "macro", posicao)

abertas = desempenho[desempenho["saldo"] > 0]
encerradas = desempenho[desempenho["saldo"] <= 0]

mes_corrente = dados.mes_corrente()
mes_da_foto = str(abertas["mes_do_saldo"].max()) if not abertas.empty else None

c.cabecalho(
    "Investimentos",
    f"Posição de {rotulo_mes(mes_da_foto)} · {len(abertas)} papéis"
    if mes_da_foto else "O que você tem aplicado e quanto rendeu",
)
c.mostrar_recado()

(aba_carteira, aba_rentabilidade, aba_analise, aba_rebalanceamento,
 aba_manutencao) = st.tabs(
    ["Carteira", "Rentabilidade", "Análise do papel", "Rebalanceamento",
     "Manutenção"]
)


def _rotulo_pct(valor, casas: int = 1, sinal: bool = False) -> str:
    """Percentual formatado, ou travessão quando o número não existe.

    Vazio e zero são coisas diferentes: 0,0% diz "não rendeu", e o que a
    carteira tem em vários papéis é "não dá para saber".
    """
    if vazio(valor):
        return "—"
    texto = fmt_pct(float(valor), casas)
    return f"+{texto}" if sinal and float(valor) > 0 else texto


def _tabela_de_papeis(tabela, chave: str) -> None:
    """Desenha um grupo de papéis com saldo, preço e rentabilidade.

    A coluna **Em US$** só aparece quando o grupo tem papel em moeda
    estrangeira. Numa carteira em que 8 dos 11 papéis são em reais, uma coluna
    vazia na maioria das linhas é ruído — e `saldo` já é o valor na moeda do
    papel quando ele é brasileiro.
    """
    colunas = ["nome", "quantidade", "preco_medio", "preco_atual", "saldo",
               "participacao", "rent_mes", "rent_12m", "rent_total",
               "rendimento_confiavel", "curva", "mes_do_saldo"]
    tem_moeda = tabela["saldo_moeda"].notna().any()
    if tem_moeda:
        colunas.insert(5, "saldo_moeda")
    visao = tabela[colunas].copy()
    visao["participacao"] = visao["participacao"] * 100
    for coluna in ("rent_mes", "rent_12m", "rent_total"):
        visao[coluna] = visao[coluna] * 100

    configuracao = {
        "Papel": st.column_config.TextColumn("Papel", width="medium"),
        "Quant.": st.column_config.NumberColumn("Quant.", format="%.4f"),
        "Preço médio": c.config_moeda(
            "Preço médio", "do que você lançou em Manutenção → Lançar compras"),
        "Preço atual": c.config_moeda(
            "Preço atual", "convertido para reais pela cotação de hoje"),
        "Saldo": c.config_moeda("Saldo"),
        "Em US$": c.config_dolar(
            "Em US$", "o mesmo saldo na moeda em que o papel é cotado"),
        "% carteira": st.column_config.NumberColumn("% carteira", format="%.1f%%"),
        "No mês": st.column_config.NumberColumn("No mês", format="%.1f%%"),
        "12 meses": st.column_config.NumberColumn("12 meses", format="%.1f%%"),
        "Total": st.column_config.NumberColumn(
            "Total", format="%.1f%%",
            help="Rentabilidade composta dos meses de fonte confiável"),
        "Ganho": c.config_moeda(
            "Ganho", "só os meses de fonte confiável; vazio quando não há"),
        "Curva": st.column_config.LineChartColumn(
            "Curva", help="Saldo dos últimos 12 meses"),
        "Foto de": st.column_config.TextColumn("Foto de", width="small"),
    }
    priv.tabela(
        visao.rename(columns={
            "nome": "Papel", "quantidade": "Quant.",
            "preco_medio": "Preço médio", "preco_atual": "Preço atual",
            "saldo": "Saldo", "saldo_moeda": "Em US$",
            "participacao": "% carteira",
            "rent_mes": "No mês", "rent_12m": "12 meses",
            "rent_total": "Total", "rendimento_confiavel": "Ganho",
            "curva": "Curva", "mes_do_saldo": "Foto de",
        }),
        hide_index=True, width="stretch", column_config=configuracao,
        key=f"tabela_papeis_{chave}",
    )


with aba_carteira:
    # DINHEIRO SEM EXPLICACAO APARECE ANTES DE QUALQUER NUMERO BONITO.
    # O valor nao entra em "Ganho acumulado" — e justamente por nao entrar em
    # lugar nenhum que ele precisa aparecer aqui. Absorver a sobra no
    # rendimento era o defeito; deixar a sobra invisivel seria o mesmo defeito
    # com outra roupa.
    if conciliacao.get("n_a_triar"):
        c.tarja(
            f"{conciliacao['n_a_triar']} movimentação(ões) da corretora, "
            f"somando {fmt_brl(conciliacao['valor_a_triar'])}, ainda não têm "
            f"explicação — não estão contadas como ganho nem como aporte. "
            f"Classifique em Manutenção → Movimentações.",
            "aviso")

    if abertas.empty:
        c.aviso_vazio(
            "Nenhuma aplicação com saldo ainda.",
            "Cadastre em **Manutenção → Cadastro** e informe os saldos em "
            "**Manutenção → Atualizar saldos**.")
    else:
        total_carteira = float(abertas["saldo"].sum())
        aportado = float(conciliacao.get("aportado_liquido") or 0.0)
        ganho = float(conciliacao.get("rendimento_apurado") or 0.0)
        rent_carteira = (float(grade_rentabilidade["acumulado"].iloc[-1])
                         if not grade_rentabilidade.empty else None)
        rent_mes_carteira = (float(evolucao_carteira["rendimento_pct"].iloc[-1])
                             if not evolucao_carteira.empty else None)
        sombra = (float(carteira_vs_cdi["referencia"].iloc[-1])
                  if not carteira_vs_cdi.empty
                  and pd.notna(carteira_vs_cdi["referencia"].iloc[-1]) else None)

        c.destaque([
            {"rotulo": "Patrimônio investido", "valor": fmt_brl(total_carteira),
             "ajuda": f"{len(abertas)} papéis",
             "dica": "A soma das aplicações. Não inclui o dinheiro da conta "
                     "corrente — isso é a tela de Patrimônio."},
            {"rotulo": "Ganho acumulado", "valor": fmt_brl(ganho),
             "cor": "verde" if ganho >= 0 else "vermelha",
             "ajuda": f"sobre {fmt_brl(aportado)} aportados",
             "dica": "Carteira menos o que você mandou para ela, descontado o "
                     "saldo que já existia quando o acompanhamento começou."},
            {"rotulo": "Rentabilidade total", "valor": _rotulo_pct(rent_carteira),
             "cor": ("verde" if rent_carteira and rent_carteira >= 0
                     else "vermelha" if rent_carteira else None),
             "ajuda": "composta, mês a mês",
             "dica": "Juros compostos multiplicam, não somam. E o cálculo usa "
                     "só os meses de fonte confiável."},
        ])

        st.markdown("")
        c.estatisticas([
            {"rotulo": "No mês", "valor": _rotulo_pct(rent_mes_carteira, 2),
             "cor": ("verde" if rent_mes_carteira and rent_mes_carteira >= 0
                     else "vermelha" if rent_mes_carteira else None)},
            {"rotulo": "Aportado (líquido)", "valor": fmt_brl(aportado),
             "ajuda": "conta corrente ⇄ corretora"},
            {"rotulo": "Se rendesse CDI",
             "valor": fmt_brl(sombra) if sombra else "—",
             "ajuda": (f"{fmt_brl(total_carteira - sombra, sinal=True)} de "
                       f"diferença" if sombra else "sem série do CDI"),
             "cor": ("verde" if sombra and total_carteira >= sombra
                     else "vermelha" if sombra else None),
             "dica": "A mesma carteira, com os mesmos aportes, rendendo o CDI. "
                     "Comparar reais com reais — uma taxa solta ao lado de um "
                     "valor não compara nada."},
            {"rotulo": "Desatualizados",
             "valor": fmt_num(int(abertas["desatualizado"].sum()), 0),
             "ajuda": "papéis com saldo de um mês anterior",
             "cor": "vermelha" if int(abertas["desatualizado"].sum()) else None},
        ])

        dolar, dia_do_dolar = cambio.cotacao_dolar()
        em_dolar = total_carteira / dolar if dolar else None
        so_em_dolar = float(abertas["saldo_moeda"].fillna(0).sum())
        c.estatisticas([
            {"rotulo": "A carteira em dólar",
             "valor": priv.fmt_usd(em_dolar) if em_dolar else "—",
             "ajuda": (f"pelo PTAX de {dia_do_dolar} · R$ {dolar:.4f}"
                       if dolar else "sem cotação guardada"),
             "dica": "É o patrimônio inteiro convertido pela cotação de hoje. "
                     "Ele sobe e desce com o câmbio mesmo quando nenhum papel "
                     "se mexe — não confunda com rentabilidade."},
            {"rotulo": "Já está em dólar",
             "valor": priv.fmt_usd(so_em_dolar),
             "ajuda": (f"{fmt_pct(so_em_dolar / em_dolar)} da carteira"
                       if em_dolar else ""),
             "dica": "A parte que é cotada em dólar de verdade — os papéis da "
                     "conta internacional. O resto é real convertido."},
        ])

        c.secao("Como o patrimônio cresceu",
                "quanto foi dinheiro seu e quanto foi ganho")
        with c.painel(chave="patrimonio_aportado"):
            priv.grafico(
                graficos.patrimonio_aportado_e_ganho(
                    estado.recortar_serie(evolucao_carteira), carteira_vs_cdi),
                width="stretch", key="investimentos_patrimonio_aportado")

        c.secao("Onde está o dinheiro")
        por_macro = (abertas.groupby("macro", dropna=False)
                     .agg(saldo=("saldo", "sum"), papeis=("id", "size"))
                     .reset_index()
                     .sort_values("saldo", ascending=False))
        por_macro["macro"] = por_macro["macro"].fillna("(sem classe)")
        por_macro["percentual"] = por_macro["saldo"] / total_carteira * 100

        col_rosca, col_lista = st.columns([1, 1], gap="large")
        with col_rosca:
            with c.painel(chave="rosca_macro"):
                priv.grafico(
                    graficos.carteira_por_tipo(por_macro.rename(columns={
                        "macro": "tipo", "papeis": "quantidade"}).assign(
                            participacao=por_macro["percentual"] / 100)),
                    width="stretch", key="investimentos_rosca_macro")
        with col_lista:
            priv.tabela(
                por_macro.rename(columns={
                    "macro": "Classe", "saldo": "Valor",
                    "papeis": "Papéis", "percentual": "% da carteira"}),
                hide_index=True, width="stretch",
                column_config={
                    "Valor": c.config_moeda("Valor"),
                    "% da carteira": st.column_config.ProgressColumn(
                        "% da carteira", format="%.1f%%", min_value=0,
                        max_value=100),
                },
                key="investimentos_lista_macro")

        # ------------------------------------------------- ver por outro eixo
        # A mesma carteira, cortada de outro jeito. `desempenho_da_carteira`
        # nao traz `data_vencimento` nem `liquidez` — o cadastro traz, e e
        # deles que sai a faixa de prazo.
        c.secao("Ver por outro eixo",
                "a mesma carteira, cortada por prazo, indexador ou liquidez — "
                "tudo derivado do que já está no cadastro")

        # `tema` tem de entrar aqui: `desempenho_da_carteira` nao o carrega, e
        # sem ele o eixo de tema lia sempre vazio — a rosca dizia "(sem tema)
        # 100%" com os papeis etiquetados.
        colunas_cadastro = [c_ for c_ in ("id", "tema", "data_vencimento",
                                          "liquidez")
                            if c_ in cadastro.columns]
        detalhado = abertas.merge(cadastro[colunas_cadastro], on="id", how="left")

        macros_na_carteira = sorted(
            {str(m) for m in abertas["macro"].dropna().unique()})
        classes_na_carteira = sorted(
            {str(k) for k in abertas["classe"].dropna().unique()})

        col_filtro, col_eixo = st.columns([1, 1])
        with col_filtro:
            escolha = st.selectbox(
                "Ver",
                ["Toda a carteira"]
                + [f"Macro · {m}" for m in macros_na_carteira]
                + [f"Classe · {k}" for k in classes_na_carteira],
                key="drill_filtro",
                help="Escolha um pedaço da carteira para abrir por dentro.")
        with col_eixo:
            rotulos = {calc.ROTULOS_DIMENSAO[d]: d for d in calc.DIMENSOES}
            eixo = rotulos[st.selectbox(
                "agrupada por", list(rotulos), index=2, key="drill_eixo",
                help="Prazo junta o indexador com o tempo até o vencimento: "
                     "«IPCA+ Longo». Liquidez diária vem antes de tudo, porque "
                     "esse dinheiro você alcança hoje.")]

        if escolha.startswith("Macro · "):
            recorte = detalhado[detalhado["macro"] == escolha[8:]]
        elif escolha.startswith("Classe · "):
            recorte = detalhado[detalhado["classe"] == escolha[9:]]
        else:
            recorte = detalhado

        if recorte.empty:
            c.aviso_vazio("Nada com saldo neste recorte.")
        else:
            recorte = recorte.copy()
            recorte["balde"] = [
                calc.balde_de(dict(papel), eixo, mes_da_foto, papel.get("macro"))
                for _, papel in recorte.iterrows()
            ]
            por_balde = (recorte.groupby("balde")
                         .agg(saldo=("saldo", "sum"), papeis=("id", "size"))
                         .reset_index()
                         .sort_values("saldo", ascending=False))
            total_recorte = float(por_balde["saldo"].sum())
            por_balde["percentual"] = (por_balde["saldo"] / total_recorte * 100
                                       if total_recorte else 0.0)

            col_rosca_eixo, col_tabela_eixo = st.columns([1, 1], gap="large")
            with col_rosca_eixo:
                with c.painel(chave="rosca_eixo"):
                    priv.grafico(
                        graficos.rosca_alocacao(
                            por_balde["balde"].tolist(),
                            por_balde["saldo"].tolist()),
                        width="stretch", key="investimentos_rosca_eixo")
            with col_tabela_eixo:
                priv.tabela(
                    por_balde.rename(columns={
                        "balde": calc.ROTULOS_DIMENSAO[eixo], "saldo": "Valor",
                        "papeis": "Papéis", "percentual": "% do recorte"}),
                    hide_index=True, width="stretch",
                    column_config={
                        "Valor": c.config_moeda("Valor"),
                        "% do recorte": st.column_config.ProgressColumn(
                            "% do recorte", format="%.1f%%",
                            min_value=0, max_value=100),
                    },
                    key="investimentos_tabela_eixo")

            with st.expander(f"Os {len(recorte)} papéis deste recorte, "
                             f"um por linha"):
                lista_papeis = recorte[["nome", "balde", "classe", "saldo"]].copy()
                lista_papeis["percentual"] = (
                    lista_papeis["saldo"] / total_recorte * 100
                    if total_recorte else 0.0)
                priv.tabela(
                    lista_papeis.sort_values("saldo", ascending=False).rename(
                        columns={"nome": "Papel",
                                 "balde": calc.ROTULOS_DIMENSAO[eixo],
                                 "classe": "Classe", "saldo": "Valor",
                                 "percentual": "% do recorte"}),
                    hide_index=True, width="stretch",
                    column_config={
                        "Valor": c.config_moeda("Valor"),
                        "% do recorte": st.column_config.ProgressColumn(
                            "% do recorte", format="%.1f%%",
                            min_value=0, max_value=100),
                    },
                    key="investimentos_papeis_do_eixo")

        c.secao("Meus papéis", "cada aplicação, o que ela vale e como foi")
        for macro in por_macro["macro"]:
            do_grupo = abertas[abertas["macro"].fillna("(sem classe)") == macro]
            valor_grupo = float(do_grupo["saldo"].sum())
            medidos = do_grupo[do_grupo["rent_total"].notna()]
            rent_grupo = None
            if not medidos.empty and valor_grupo > 0:
                pesos = medidos["saldo"] / medidos["saldo"].sum()
                rent_grupo = float((medidos["rent_total"] * pesos).sum())
            titulo = (f"{macro} · {len(do_grupo)} papéis · "
                      f"{fmt_brl(valor_grupo)} · "
                      f"{fmt_pct(valor_grupo / total_carteira)} da carteira"
                      f" · {_rotulo_pct(rent_grupo)}")
            with st.expander(titulo, expanded=True):
                _tabela_de_papeis(do_grupo.sort_values("saldo", ascending=False),
                                  chave=normalizar_texto(str(macro)))

        sem_medida = abertas[abertas["rent_total"].isna()]
        com_buraco = abertas[abertas["meses_ignorados"] > 0]
        if not sem_medida.empty or not com_buraco.empty:
            recados = []
            for _, papel in sem_medida.iterrows():
                recados.append(
                    f"**{papel['nome']}** ainda não tem rentabilidade: só há "
                    f"{int(papel['meses_medidos'])} mês de dado, e o primeiro "
                    f"mês de um papel é aporte, não medição.")
            for _, papel in com_buraco.iterrows():
                recados.append(
                    f"**{papel['nome']}** mede "
                    f"{int(papel['meses_medidos'])} meses e ignora "
                    f"{int(papel['meses_ignorados'])} — nesses a origem do "
                    f"aporte não era confiável.")
            st.info("\n\n".join(recados))

        c.secao("Quem carregou e quem atrapalhou",
                "rentabilidade acumulada de cada papel")
        with c.painel(chave="retorno_por_papel"):
            priv.grafico(graficos.retorno_por_papel(abertas), width="stretch",
                         key="investimentos_retorno_por_papel")

        if not encerradas.empty:
            with st.expander(f"Posições encerradas ({len(encerradas)})"):
                _tabela_de_papeis(encerradas, chave="encerradas")
                st.caption(
                    "Papéis que já foram vendidos ou venceram. Ficam aqui para "
                    "o histórico não sumir, e fora da tabela de cima para não "
                    "encher de linhas zeradas o que você olha todo dia.")

        with st.expander("Entenda esta tela"):
            st.markdown(
                "**Por que não há seletor de mês.** Carteira não se olha por "
                "mês: a pergunta é *quanto eu tenho hoje*. A tela mostra "
                "sempre a foto mais recente de cada papel, e a coluna "
                "**Foto de** avisa quando a de algum papel é mais velha.\n\n"
                "**Rentabilidade não é saldo ÷ aportado.** Essa conta parece "
                "certa e mente quando o papel tem entrada e saída "
                "frequentes — no Trend DI ela dá +213%, contra 7,7% da conta "
                "correta. O que a tela mostra é a composição dos retornos "
                "mensais: `(1+r₁)×(1+r₂)×…−1`.\n\n"
                "**Mês de fonte ruim é ignorado, e contado.** Quando o app não "
                "consegue saber se uma variação foi rendimento ou dinheiro "
                "novo, ele não chuta: descarta o mês e diz quantos descartou.\n\n"
                "**Preço médio vem de você.** Ele sai das compras lançadas em "
                "*Manutenção → Lançar compras*. A coluna \"Valor aplicado\" da "
                "corretora não serve: ela muda sozinha, sem você ter "
                "movimentado nada.\n\n"
                "**Preço médio e preço atual estão os dois em reais**, mesmo "
                "para papel americano. Comparar um preço em real com um preço "
                "em dólar faria o IREN parecer 80% mais barato só pela troca "
                "de moeda."
            )


with aba_rentabilidade:
    if evolucao_carteira.empty:
        c.aviso_vazio("Sem histórico de carteira ainda.")
    else:
        doze = evolucao_carteira.tail(12)
        rent_12m = 1.0
        for pct in doze["rendimento_pct"]:
            rent_12m *= (1 + float(pct))
        rent_12m -= 1
        rent_total = (float(grade_rentabilidade["acumulado"].iloc[-1])
                      if not grade_rentabilidade.empty else None)
        rent_mes = float(evolucao_carteira["rendimento_pct"].iloc[-1])

        meses_todos = [str(m) for m in evolucao_carteira["mes"]]

        disponiveis = indices.disponiveis() or ["CDI"]
        escolhidos = st.multiselect(
            "Comparar com", disponiveis,
            default=[n for n in ("CDI", "IBOV", "S&P 500") if n in disponiveis]
            or disponiveis[:1],
            key="rentabilidade_indices",
            help="A carteira vira uma linha; cada índice vira uma carteira-"
                 "sombra que recebeu os mesmos aportes e rendeu aquele índice.")
        principal = escolhidos[0] if escolhidos else "CDI"

        ref_total = indices.acumulado(principal, meses_todos)
        ref_12m = indices.acumulado(principal, [str(m) for m in doze["mes"]])
        ref_mes = indices.acumulado(principal, [meses_todos[-1]])

        def _contra_cdi(propria, do_indice):
            if vazio(propria) or do_indice is None:
                return f"sem série do {principal} para comparar"
            diferenca = float(propria) - do_indice
            palavra = "acima" if diferenca >= 0 else "abaixo"
            return f"{fmt_pct(abs(diferenca))} {palavra} do {principal}"

        c.destaque([
            {"rotulo": "Rentabilidade total", "valor": _rotulo_pct(rent_total),
             "ajuda": _contra_cdi(rent_total, ref_total),
             "cor": ("verde" if rent_total and rent_total >= 0
                     else "vermelha" if rent_total else None)},
            {"rotulo": "Últimos 12 meses", "valor": _rotulo_pct(rent_12m),
             "ajuda": _contra_cdi(rent_12m, ref_12m),
             "cor": "verde" if rent_12m >= 0 else "vermelha"},
            {"rotulo": "No mês", "valor": _rotulo_pct(rent_mes, 2),
             "ajuda": _contra_cdi(rent_mes, ref_mes),
             "cor": "verde" if rent_mes >= 0 else "vermelha"},
        ])

        c.nota(
            "Os cartões acima comparam com o <b>" + principal + "</b>, o "
            "primeiro da sua seleção. <b>Papel a papel a régua é outra</b>, e "
            "escolhida pelo tipo de risco: NTN-B contra o <b>IPCA</b>, "
            "pós-fixado contra o <b>CDI</b>, ação brasileira contra o "
            "<b>IBOV</b> e papel internacional contra o <b>S&P 500 em reais</b>."
        )

        c.secao("A carteira e as sombras",
                "cada índice recebe os mesmos aportes e resgates que você fez")

        comparacao = evolucao_carteira[["mes", "saldo"]].copy()
        for nome in escolhidos:
            sombra = estado.carteira_contra_indice(nome)
            if sombra.empty:
                continue
            comparacao = comparacao.merge(
                sombra[["mes", "referencia"]].rename(
                    columns={"referencia": nome}), on="mes", how="left")

        with c.painel(chave="carteira_vs_indices"):
            priv.grafico(
                graficos.carteira_contra_indices(
                    estado.recortar_serie(comparacao), escolhidos),
                width="stretch", key="rentabilidade_carteira_vs_indices")

        placar = []
        real = float(evolucao_carteira["saldo"].iloc[-1])
        for nome in escolhidos:
            if nome not in comparacao.columns:
                continue
            valor = comparacao[nome].iloc[-1]
            if pd.isna(valor):
                placar.append({"Índice": nome, "Onde estaria": None,
                               "Diferença": None, "O que é": indices.descricao(nome)})
                continue
            placar.append({"Índice": nome, "Onde estaria": float(valor),
                           "Diferença": real - float(valor),
                           "O que é": indices.descricao(nome)})
        if placar:
            priv.tabela(
                pd.DataFrame(placar), hide_index=True, width="stretch",
                column_config={
                    "Onde estaria": c.config_moeda(
                        "Onde estaria", "o que a carteira valeria se tivesse "
                                        "rendido esse índice"),
                    "Diferença": c.config_moeda(
                        "Diferença", "positivo = você foi melhor que o índice"),
                },
                key="rentabilidade_placar_indices")
            st.caption(
                "Célula vazia é índice com mês faltando na série — o IPCA sai "
                "com cerca de um mês de atraso, e a sombra dele fica em aberto "
                "até o número sair. Melhor um buraco visível que uma linha "
                "caindo ao chão."
            )

        c.secao("Mês a mês", "cada mês do ano, o ano fechado e o acumulado")
        if grade_rentabilidade.empty:
            c.aviso_vazio("Sem meses suficientes para montar a grade.")
        else:
            grade = grade_rentabilidade.copy()
            nomes = {"ano": "Ano"}
            for numero in range(1, 13):
                rotulo = calc.ABREV_MES[numero - 1]
                nomes[f"m{numero:02d}"] = rotulo
                grade[f"m{numero:02d}"] = grade[f"m{numero:02d}"] * 100
            grade["no_ano"] = grade["no_ano"] * 100
            grade["acumulado"] = grade["acumulado"] * 100
            nomes["no_ano"] = "No ano"
            nomes["acumulado"] = "Acumulado"

            configuracao = {calc.ABREV_MES[n - 1]: st.column_config.NumberColumn(
                calc.ABREV_MES[n - 1], format="%.1f%%") for n in range(1, 13)}
            configuracao["No ano"] = st.column_config.NumberColumn(
                "No ano", format="%.1f%%")
            configuracao["Acumulado"] = st.column_config.NumberColumn(
                "Acumulado", format="%.1f%%",
                help="Desde o primeiro mês até o fim daquele ano")
            configuracao["Ano"] = st.column_config.TextColumn("Ano", width="small")

            priv.tabela(grade.rename(columns=nomes), hide_index=True,
                        width="stretch", column_config=configuracao,
                        key="rentabilidade_grade")
            st.caption(
                "Célula vazia é mês sem dado, não mês de rentabilidade zero. "
                "E o acumulado **compõe** os meses: 1,82% seguido de 1,34% dá "
                "3,18%, não 3,16%."
            )

        c.secao("Papel a papel")
        if cadastro.empty:
            c.aviso_vazio("Cadastre uma aplicação primeiro.")
        else:
            escolhido = st.selectbox(
                "Aplicação", cadastro["id"].tolist(),
                format_func=lambda i: cadastro.loc[
                    cadastro["id"] == i, "nome"].iloc[0],
                key="investimento_rentabilidade")

            historico = calc.evolucao(int(escolhido))
            ficha = cadastro[cadastro["id"] == escolhido].iloc[0]

            if historico.empty:
                c.aviso_vazio("Esta aplicação ainda não tem saldo registrado.")
            else:
                resultado = calc.desempenho_do_papel(int(escolhido), 999,
                                                     ficha["classe"])
                saldo_atual = float(historico["saldo"].iloc[-1])
                medido = resultado["meses_considerados"] > 1

                c.estatisticas([
                    {"rotulo": "Saldo atual", "valor": fmt_brl(saldo_atual)},
                    {"rotulo": "Rendimento acumulado",
                     "valor": fmt_brl(resultado["rendimento"]) if medido else "—",
                     "cor": ("verde" if medido and resultado["rendimento"] >= 0
                             else "vermelha" if medido else None)},
                    {"rotulo": "Rentabilidade",
                     "valor": (_rotulo_pct(resultado["rentabilidade"])
                               if medido else "—"),
                     "ajuda": f"{resultado['meses_considerados']} meses medidos"},
                    {"rotulo": "Média por mês",
                     "valor": (_rotulo_pct(resultado["media_mensal"], 2)
                               if medido else "—"),
                     "dica": "Média geométrica — a que, composta, devolve o "
                             "acumulado."},
                ])

                if resultado["indice"] and resultado["rent_indice"] is not None:
                    diferenca = resultado["vs_indice"]
                    palavra = "acima" if diferenca >= 0 else "abaixo"
                    st.markdown(
                        f"Contra o **{resultado['indice']}**, que fez "
                        f"{fmt_pct(resultado['rent_indice'])} nos mesmos "
                        f"{len(resultado['meses'])} meses: "
                        f"**{fmt_pct(abs(diferenca))} {palavra}**."
                    )
                    if resultado["meses_faltando"]:
                        st.warning(
                            f"A comparação cobre "
                            f"{resultado['meses_do_indice']} dos "
                            f"{len(resultado['meses'])} meses — falta "
                            f"{', '.join(resultado['meses_faltando'][:3])}. "
                            f"O IPCA sai com um mês de atraso."
                        )
                elif not resultado["indice"]:
                    st.caption(
                        f"**Sem régua para este papel.** {ficha['classe']} não "
                        f"tem índice que sirva de comparação, e mostrar um "
                        f"errado é pior que não mostrar nenhum."
                    )

                if resultado["meses_ignorados"]:
                    st.warning(
                        f"**{resultado['meses_ignorados']} meses ficaram de "
                        f"fora** do cálculo. Neles o app não conseguiu separar "
                        f"rendimento de dinheiro novo — a regra olha a "
                        f"**procedência** do dado, não o resultado, para não "
                        f"escolher a dedo os meses que ficam bonitos."
                    )

                ticker = None if vazio(ficha.get("ticker")) else str(ficha["ticker"])
                if ticker:
                    serie_preco = estado.papel_serie_preco(ticker)
                    if not serie_preco.empty:
                        c.secao(f"Preço de {ticker}",
                                f"{len(serie_preco)} fechamentos diários")
                        with c.painel(chave="preco_papel"):
                            priv.grafico(
                                graficos.preco_do_papel(serie_preco, ticker),
                                width="stretch", key="rentabilidade_preco_papel")
                        st.caption(
                            "Este é o único gráfico diário do app — os outros "
                            "são mensais porque é a granularidade que os dados "
                            "têm. Tesouro e fundo não têm cotação pública."
                        )

                with c.painel(chave="aportes_e_rendimento"):
                    priv.grafico(graficos.aportes_e_rendimento(historico),
                                 width="stretch",
                                 key="rentabilidade_aportes_e_rendimento")

                with st.expander("Histórico mês a mês"):
                    visao = historico.copy()
                    visao["rendimento_pct"] = visao["rendimento_pct"] * 100
                    visao["mes"] = visao["mes"].map(rotulo_mes)
                    priv.tabela(
                        visao[["mes", "saldo_anterior", "aporte", "resgate",
                               "saldo", "rendimento", "rendimento_pct",
                               "confiavel"]].rename(columns={
                                   "mes": "Mês", "saldo_anterior": "Saldo anterior",
                                   "aporte": "Aporte", "resgate": "Resgate",
                                   "saldo": "Saldo", "rendimento": "Rendimento",
                                   "rendimento_pct": "Rend. %",
                                   "confiavel": "Fonte confiável"}),
                        hide_index=True, width="stretch",
                        column_config={
                            "Saldo anterior": c.config_moeda("Saldo anterior"),
                            "Aporte": c.config_moeda("Aporte"),
                            "Resgate": c.config_moeda("Resgate"),
                            "Saldo": c.config_moeda("Saldo"),
                            "Rendimento": c.config_moeda("Rendimento"),
                            "Rend. %": st.column_config.NumberColumn(
                                "Rend. %", format="%.2f%%"),
                            "Fonte confiável": st.column_config.CheckboxColumn(
                                "Fonte confiável", disabled=True),
                        },
                        key="rentabilidade_historico")


with aba_analise:
    analise.desenhar(desempenho)


with aba_rebalanceamento:
    nivel_escolhido = st.radio(
        "Olhar por", ["Classe", "Macro"], horizontal=True,
        key="rebal_nivel",
        help="Classe é o detalhe (NTN-B, ETF, Ação BR). Macro é o "
             "agrupamento (Renda Fixa, Renda Variável, Internacional).",
    )
    nivel = "macro" if nivel_escolhido == "Macro" else "classe"

    soma_metas = calc.soma_das_metas(nivel)

    # A POSICAO VEM ANTES DA META, E APARECE MESMO SEM META NENHUMA.
    # Antes, quem nao tinha meta cadastrada via so o aviso de "cadastre suas
    # metas" — a tela de rebalanceamento nao mostrava a carteira que ele tem.
    # E "como estou hoje" e a metade da pergunta que nao depende de nada.
    alocacao_hoje = estado.carteira_alocacao(mes_corrente, nivel)
    metas_do_nivel = calc.metas(nivel)

    ideal, atual = st.columns(2)
    with ideal:
        with c.painel("Carteira ideal", "as metas que você cadastrou"):
            priv.grafico(
                graficos.rosca_alocacao(
                    metas_do_nivel["nome"].tolist() if not metas_do_nivel.empty else [],
                    metas_do_nivel["percentual_alvo"].tolist() if not metas_do_nivel.empty else [],
                    mostrar_total=False,
                    vazio_texto="Nenhuma meta cadastrada ainda"),
                width="stretch", key=f"rebal_rosca_ideal_{nivel}")
    with atual:
        with c.painel("Minha carteira", f"posição de hoje, por {nivel}"):
            priv.grafico(
                graficos.rosca_alocacao(
                    alocacao_hoje["nome"].tolist() if not alocacao_hoje.empty else [],
                    alocacao_hoje["saldo"].tolist() if not alocacao_hoje.empty else [],
                    vazio_texto="Importe a posição da corretora"),
                width="stretch", key=f"rebal_rosca_atual_{nivel}")

    if soma_metas <= 0:
        c.aviso_vazio(
            f"Você ainda não definiu metas de alocação por {nivel}.",
            "A carteira acima é a que você tem. Para o app calcular **para "
            "onde mandar o aporte**, vá em **Cadastro → Metas de alocação** e "
            "diga quanto quer ter em cada uma.",
        )
    else:
        if abs(soma_metas - 1) > 0.005:
            st.warning(
                f"Suas metas de {nivel} somam **{fmt_pct(soma_metas)}**, e não "
                f"100%. A conta continua funcionando, mas os percentuais-alvo "
                f"só fazem sentido quando somam o total da carteira. "
                f"Ajuste em Cadastro → Metas de alocação."
            )

        coluna_aporte, coluna_resumo = st.columns([1, 2])

        with coluna_aporte:
            ja_aportado = float(
                calc.sugerir_aportes_do_mes(df, mes_corrente).get("aportado", 0) or 0)
            aporte = st.number_input(
                "Aporte deste mês (R$)",
                min_value=0.0, step=100.0,
                value=float(max(0.0, round(ja_aportado, 2))),
                key="rebal_aporte",
                help="Quanto você vai investir agora. A sugestão inicial é o "
                     "que já saiu da conta corrente para investimento neste "
                     "mês, segundo o extrato. Mude à vontade.",
            )

        tabela_rebal = calc.rebalancear(aporte, None, nivel)
        total_hoje = float(tabela_rebal["saldo"].sum()) if not tabela_rebal.empty else 0.0

        with coluna_resumo:
            fora = tabela_rebal[~tabela_rebal["dentro_faixa"]] if not tabela_rebal.empty else tabela_rebal
            c.linha_kpis([
                {"rotulo": "Carteira hoje", "valor": fmt_brl(total_hoje),
                 "ajuda": "Soma de tudo que está aplicado."},
                {"rotulo": "Depois do aporte", "valor": fmt_brl(total_hoje + aporte),
                 "ajuda": "É sobre este total que as metas são calculadas."},
                {"rotulo": "Fora da faixa", "valor": f"{len(fora)}",
                 "ajuda": "Quantas classes estão além da tolerância da meta."},
            ])

        if tabela_rebal.empty:
            c.aviso_vazio("Carteira vazia.",
                          "Importe a posição da corretora na tela de Importar.")
        else:
            st.markdown("#### Para onde mandar o aporte")

            recebem = tabela_rebal[tabela_rebal["aportar"] > 0.005]
            if aporte <= 0:
                st.info("Informe um valor de aporte acima para ver a divisão.")
            elif recebem.empty:
                st.success(
                    "Nenhuma classe está abaixo da meta — a carteira já está "
                    "equilibrada. O aporte pode entrar seguindo as metas."
                )
            else:
                linhas_texto = [
                    f"- **{linha['nome']}**: {fmt_brl_md(linha['aportar'])}"
                    f"  ({fmt_pct(linha['percentual'])} → "
                    f"{fmt_pct(linha['percentual_depois'])}, "
                    f"meta {fmt_pct(linha['percentual_alvo'])})"
                    for _, linha in recebem.iterrows()
                ]
                st.markdown("\n".join(linhas_texto))

            with c.painel(chave="rebalanceamento_aporte"):
                priv.grafico(graficos.rebalanceamento_aporte(tabela_rebal),
                             width="stretch",
                             key="investimentos_rebalanceamento_aporte")

            visao = tabela_rebal.copy()
            visao["percentual"] = visao["percentual"] * 100
            visao["percentual_alvo"] = visao["percentual_alvo"] * 100
            visao["desvio"] = visao["desvio"] * 100
            visao["percentual_depois"] = visao["percentual_depois"] * 100
            visao["situacao"] = [
                "na faixa" if dentro else ("acima" if desvio > 0 else "abaixo")
                for dentro, desvio in zip(tabela_rebal["dentro_faixa"],
                                          tabela_rebal["desvio"])
            ]
            priv.tabela(
                visao[["nome", "saldo", "percentual", "percentual_alvo",
                       "desvio", "situacao", "aportar", "percentual_depois"]]
                .rename(columns={
                    "nome": "Classe" if nivel == "classe" else "Macro",
                    "saldo": "Saldo hoje", "percentual": "% atual",
                    "percentual_alvo": "% meta", "desvio": "Desvio",
                    "situacao": "Situação", "aportar": "Aportar",
                    "percentual_depois": "% depois",
                }),
                hide_index=True, width="stretch",
                column_config={
                    "Saldo hoje": c.config_moeda("Saldo hoje"),
                    "Aportar": c.config_moeda("Aportar"),
                    "% atual": c.config_percentual("% atual"),
                    "% meta": c.config_percentual("% meta"),
                    "Desvio": c.config_percentual("Desvio"),
                    "% depois": c.config_percentual("% depois"),
                },
            )

            c.nota(
                "Uma classe pode <b>receber dinheiro e mesmo assim cair de "
                "percentual</b>. Não é erro: o aporte aumenta o total da "
                "carteira (o denominador) ao mesmo tempo em que enche cada "
                "fatia. Quem estava quase na meta perde para a diluição; quem "
                "estava muito atrás é atendido primeiro. No conjunto, a "
                "carteira sempre se aproxima das metas."
            )

            with c.painel("Atual × meta"):
                priv.grafico(graficos.alocacao_atual_vs_meta(tabela_rebal),
                             width="stretch", key="investimentos_alocacao_vs_meta")

            if aporte > 0:
                st.markdown("#### No ritmo deste aporte")
                prazos = calc.meses_para_meta(aporte, None, nivel)
                pendentes = prazos[prazos["meses"].apply(lambda v: bool(v))]
                if pendentes.empty:
                    st.success("Todas as classes já estão dentro da faixa.")
                else:
                    for _, linha in pendentes.iterrows():
                        if not linha["alcancavel"]:
                            st.markdown(
                                f"- **{linha['nome']}**: não chega à faixa "
                                f"em 30 anos neste ritmo."
                            )
                        else:
                            meses_faltando = int(linha["meses"])
                            quando = somar_meses(mes_corrente, meses_faltando)
                            st.markdown(
                                f"- **{linha['nome']}** entra na faixa em "
                                f"**{meses_faltando} mês(es)** "
                                f"— por volta de {rotulo_mes(quando)}."
                            )
                    c.nota(
                        "Esta projeção <b>ignora o rendimento</b> de propósito. "
                        "Supor um retorno deixaria o prazo mais bonito e menos "
                        "confiável; sem ele, o número é o pior caso realista."
                    )


with aba_manutencao:
    sub_saldos, sub_compras, sub_cadastro, sub_movimentos = st.tabs(
        ["Atualizar saldos", "Lançar compras", "Cadastro",
         "Movimentações"]
    )

    with sub_saldos:
        col_mes, col_explica = st.columns([1, 3], gap="medium")
        with col_mes:
            _meses_possiveis = estado.meses() or [mes_corrente]
            if mes_corrente not in _meses_possiveis:
                _meses_possiveis = _meses_possiveis + [mes_corrente]
            _meses_possiveis = sorted(set(_meses_possiveis), reverse=True)
            mes = st.selectbox(
                "Mês da foto", _meses_possiveis,
                index=_meses_possiveis.index(mes_corrente),
                format_func=rotulo_mes, key="saldos_mes")
        with col_explica:
            st.caption(
                "**Este é o único lugar da tela com escolha de mês**, e aqui "
                "ela é parte do registro: você está gravando a foto de um mês, "
                "não olhando para ele. O resto da página mostra sempre o mais "
                "recente."
            )

        st.markdown(f"### Saldos de {rotulo_mes(mes)}")

        _com_ticker = cotacoes.tickers_cadastrados()
        if _com_ticker:
            col_recalcular, col_aviso_cot = st.columns([1, 2], gap="medium")
            with col_recalcular:
                if st.button("Recalcular saldos pela cotação",
                             key="btn_recalcular_cotacao", width="stretch",
                             help="Reescreve o saldo dos papéis que têm "
                                  "ticker e quantidade, usando o fechamento "
                                  "do fim deste mês."):
                    try:
                        aplicado = calc.atualizar_saldos_por_cotacao(mes)
                    except ValueError as erro:
                        st.error(str(erro))
                    else:
                        estado.limpar_cache()
                        c.recado(
                            f"{aplicado['atualizados']} saldo(s) de "
                            f"{rotulo_mes(mes)} recalculado(s).")
                        if aplicado["ignorados"]:
                            st.warning(
                                "Sem cotação ou sem quantidade: "
                                + ", ".join(aplicado["ignorados"][:6]))
                        st.rerun()
            with col_aviso_cot:
                st.caption(
                    "**Buscar** cotação e índice agora fica na barra "
                    "lateral, em *Atualizar dados de fora* — é global e não "
                    "depende de mês. Este botão é o outro lado: ele **aplica** "
                    "a cotação já guardada ao mês selecionado acima, e "
                    "reescreve a foto dele."
                )
            st.divider()

        if cadastro.empty:
            c.aviso_vazio(
                "Nenhuma aplicação cadastrada ainda.",
                "Vá na aba **Cadastro** e registre as suas aplicações primeiro.",
            )
        else:
            sugestao = calc.sugerir_aportes_do_mes(df, mes)
            if sugestao["aportado"] or sugestao["resgatado"]:
                c.nota(
                    f"Em {rotulo_mes(mes)}, segundo o extrato, saíram "
                    f"<strong>{fmt_brl(sugestao['aportado'])}</strong> da conta "
                    f"para investimento e voltaram "
                    f"<strong>{fmt_brl(sugestao['resgatado'])}</strong>. "
                    f"Distribua esses valores entre as aplicações abaixo — a soma "
                    f"da coluna Aporte deveria bater com esse total."
                )

            st.caption(
                "Abra a corretora, veja quanto cada aplicação vale hoje e digite "
                "na coluna **Saldo**. As colunas Aporte e Resgate são o que entrou "
                "e saiu **daquela aplicação** neste mês — é o que permite separar "
                "rendimento de dinheiro novo."
            )

            registros_do_mes = {}
            todos_saldos = calc.saldos()
            if not todos_saldos.empty:
                do_mes = todos_saldos[todos_saldos["mes"] == mes]
                registros_do_mes = {
                    int(linha["investimento_id"]): linha
                    for _, linha in do_mes.iterrows()
                }

            mes_anterior = somar_meses(mes, -1)
            saldos_anteriores = {}
            if not todos_saldos.empty and mes_anterior:
                anterior = todos_saldos[todos_saldos["mes"] == mes_anterior]
                saldos_anteriores = {
                    int(linha["investimento_id"]): float(linha["saldo"])
                    for _, linha in anterior.iterrows()
                }

            linhas_editor = []
            for _, investimento in cadastro.iterrows():
                identificador = int(investimento["id"])
                registro = registros_do_mes.get(identificador)
                linhas_editor.append({
                    "id": identificador,
                    "Aplicação": investimento["nome"],
                    "Saldo anterior": saldos_anteriores.get(identificador, 0.0),
                    "Saldo": float(registro["saldo"]) if registro is not None else 0.0,
                    "Aporte": float(registro["aporte"]) if registro is not None else 0.0,
                    "Resgate": float(registro["resgate"]) if registro is not None else 0.0,
                })

            tabela_saldos = pd.DataFrame(linhas_editor)
            tabela_saldos["Rendimento"] = (
                tabela_saldos["Saldo"] - tabela_saldos["Saldo anterior"]
                - tabela_saldos["Aporte"] + tabela_saldos["Resgate"]
            )

            editado_saldos = priv.editor(
                tabela_saldos, hide_index=True, width="stretch",
                key=f"editor_saldos_{mes}",
                column_config={
                    "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
                    "Aplicação": st.column_config.TextColumn("Aplicação", disabled=True,
                                                             width="large"),
                    "Saldo anterior": st.column_config.NumberColumn(
                        "Saldo anterior", format="R$ %.2f", disabled=True,
                        help=f"o saldo de {rotulo_mes(mes_anterior) if mes_anterior else '—'}"),
                    "Saldo": st.column_config.NumberColumn(
                        "Saldo", format="R$ %.2f", min_value=0.0, step=100.0,
                        help="quanto vale HOJE, na corretora"),
                    "Aporte": st.column_config.NumberColumn(
                        "Aporte", format="R$ %.2f", min_value=0.0, step=100.0,
                        help="quanto você pôs nesta aplicação neste mês"),
                    "Resgate": st.column_config.NumberColumn(
                        "Resgate", format="R$ %.2f", min_value=0.0, step=100.0),
                    "Rendimento": st.column_config.NumberColumn(
                        "Rendimento", format="R$ %.2f", disabled=True,
                        help="saldo − saldo anterior − aporte + resgate"),
                },
            )

            soma_aportes = float(editado_saldos["Aporte"].sum())
            soma_resgates = float(editado_saldos["Resgate"].sum())
            soma_saldos = float(editado_saldos["Saldo"].sum())

            col_a, col_b = st.columns([1, 3])
            with col_a:
                if st.button("Salvar saldos", type="primary", width="stretch"):
                    gravados = 0
                    for _, linha in editado_saldos.iterrows():
                        if (linha["Saldo"] == 0 and linha["Aporte"] == 0
                                and linha["Resgate"] == 0):
                            calc.apagar_saldo(int(linha["id"]), mes)
                            continue
                        calc.salvar_saldo(
                            int(linha["id"]), mes,
                            float(linha["Saldo"]), float(linha["Aporte"]),
                            float(linha["Resgate"]),
                        )
                        gravados += 1
                    estado.limpar_cache()
                    c.recado(f"{gravados} saldo(s) salvo(s) para {rotulo_mes(mes)}.")
                    st.rerun()

            with col_b:
                diferenca_aporte = soma_aportes - sugestao["aportado"]
                st.caption(
                    f"Total na tabela — saldo: **{fmt_brl_md(soma_saldos)}** · "
                    f"aportes: **{fmt_brl_md(soma_aportes)}** · "
                    f"resgates: **{fmt_brl_md(soma_resgates)}**"
                )
                if abs(diferenca_aporte) > 1 and sugestao["aportado"]:
                    st.caption(
                        f"A soma dos aportes está "
                        f"{fmt_brl_md(abs(diferenca_aporte))} "
                        f"{'acima' if diferenca_aporte > 0 else 'abaixo'} do que o "
                        f"extrato registrou. Não é erro — pode haver aporte feito "
                        f"por outro caminho —, mas vale conferir."
                    )


    with sub_compras:
        st.markdown("### Lançar uma compra")
        c.nota(
            "É daqui que sai o <b>preço médio</b>. O saldo mensal diz quanto o "
            "papel <b>vale</b>; só a compra diz quanto você <b>pagou</b>.<br><br>"
            "E é o mesmo número que a ficha <b>Bens e Direitos</b> do Imposto "
            "de Renda pede — hoje ela mostra quase tudo sem custo. A coluna "
            "\"Valor aplicado\" da corretora não resolve: ela muda sozinha, "
            "sem você ter movimentado nada."
        )

        if cadastro.empty:
            c.aviso_vazio("Cadastre uma aplicação primeiro.")
        else:
            with st.form("form_compra"):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    papel_compra = st.selectbox(
                        "Aplicação", cadastro["id"].tolist(),
                        format_func=lambda i: cadastro.loc[
                            cadastro["id"] == i, "nome"].iloc[0],
                        key="compra_papel")
                    data_compra = st.date_input("Data da compra",
                                                key="compra_data")
                with col_b:
                    quantidade_compra = st.number_input(
                        "Quantidade", min_value=0.0, value=0.0, step=1.0,
                        format="%.6f",
                        help="Deixe zero para fundo, que não tem cota unitária.")
                    preco_compra = st.number_input(
                        "Preço unitário", min_value=0.0, value=0.0, step=1.0,
                        format="%.4f",
                        help="Na moeda do papel: dólar para papel americano.")
                with col_c:
                    custos_compra = st.number_input(
                        "Corretagem e taxas", min_value=0.0, value=0.0,
                        step=1.0, format="%.2f")
                    total_compra = st.number_input(
                        "Ou o valor total", min_value=0.0, value=0.0,
                        step=100.0, format="%.2f",
                        help="Use este campo quando não houver quantidade.")

                fator_compra = st.number_input(
                    "Fator de ajuste (grupamento / desdobramento)",
                    min_value=0.0, value=1.0, step=0.25, format="%.4f",
                    help="1,0 é o normal. O IRE fez grupamento 1:4 em "
                         "20/03/2026 — uma compra anterior a essa data precisa "
                         "de 0,25 para a quantidade comparar com a de hoje.")

                if st.form_submit_button("Lançar compra", type="primary"):
                    try:
                        calc.salvar_compra(
                            int(papel_compra), data_compra.isoformat(),
                            quantidade_compra or None, preco_compra or None,
                            custos=custos_compra,
                            valor_total=total_compra or None,
                            fator_ajuste=fator_compra)
                        ponte = calc.sincronizar_custo_no_saldo(
                            int(papel_compra))
                        estado.limpar_cache()
                        recado = "Compra lançada."
                        if ponte["gravados"]:
                            recado += (f" O custo de aquisição foi levado para "
                                       f"{ponte['gravados']} mês(es) — a ficha "
                                       f"Bens e Direitos do IR usa ele.")
                        if ponte["preservados"]:
                            recado += (f" {ponte['preservados']} mês(es) "
                                       f"mantiveram o custo que veio do extrato "
                                       f"da corretora, que é fonte melhor.")
                        c.recado(recado)
                        st.rerun()
                    except ValueError as erro:
                        st.error(str(erro))

            lancadas = calc.compras()
            if lancadas.empty:
                st.caption("Nenhuma compra lançada ainda.")
            else:
                st.markdown("#### Compras lançadas")
                visao_compras = lancadas[[
                    "id", "nome", "data", "quantidade", "valor_unitario",
                    "custos", "valor_total", "moeda", "cambio_usado",
                    "valor_total_brl", "fator_ajuste"]].copy()
                priv.tabela(
                    visao_compras.rename(columns={
                        "id": "id", "nome": "Papel", "data": "Data",
                        "quantidade": "Quant.", "valor_unitario": "Preço unit.",
                        "custos": "Taxas", "valor_total": "Total (moeda)",
                        "moeda": "Moeda", "cambio_usado": "Câmbio",
                        "valor_total_brl": "Total (R$)",
                        "fator_ajuste": "Ajuste"}),
                    hide_index=True, width="stretch",
                    column_config={
                        "id": st.column_config.NumberColumn("id", width="small"),
                        "Quant.": st.column_config.NumberColumn(
                            "Quant.", format="%.6f"),
                        "Total (R$)": c.config_moeda("Total (R$)"),
                        "Câmbio": st.column_config.NumberColumn(
                            "Câmbio", format="%.4f"),
                        "Ajuste": st.column_config.NumberColumn(
                            "Ajuste", format="%.4f"),
                    },
                    key="tabela_compras")

                col_apagar, col_resumo = st.columns([1, 2], gap="large")
                with col_apagar:
                    alvo = st.selectbox(
                        "Apagar a compra número", lancadas["id"].tolist(),
                        key="compra_apagar")
                    if st.button("Apagar compra", key="btn_apagar_compra"):
                        dono = int(lancadas.loc[lancadas["id"] == alvo,
                                                "investimento_id"].iloc[0])
                        calc.apagar_compra(int(alvo))
                        calc.sincronizar_custo_no_saldo(dono)
                        estado.limpar_cache()
                        st.rerun()
                with col_resumo:
                    resumo_custos = []
                    for identificador in lancadas["investimento_id"].unique():
                        medio = calc.custo_medio(int(identificador))
                        if not medio:
                            continue
                        nome_papel = cadastro.loc[
                            cadastro["id"] == identificador, "nome"]
                        resumo_custos.append({
                            "Papel": (nome_papel.iloc[0] if len(nome_papel)
                                      else str(identificador)),
                            "Quant.": medio["quantidade"],
                            "Custo total": medio["custo_total_brl"],
                            "Preço médio": medio["preco_medio_brl"],
                            "Lotes": medio["lotes"],
                        })
                    if resumo_custos:
                        priv.tabela(
                            pd.DataFrame(resumo_custos), hide_index=True,
                            width="stretch",
                            column_config={
                                "Custo total": c.config_moeda("Custo total"),
                                "Preço médio": c.config_moeda("Preço médio"),
                                "Quant.": st.column_config.NumberColumn(
                                    "Quant.", format="%.6f"),
                            },
                            key="tabela_custo_medio")


    with sub_cadastro:
        st.markdown("### Suas aplicações")
        st.caption(
            "Registre cada aplicação uma vez. Depois é só atualizar o saldo "
            "mensalmente na aba anterior."
        )

        _classes = calc.classes()
        lista_classes = [""] + (list(_classes["nome"]) if not _classes.empty else [])
        _temas = calc.temas()
        lista_temas = [""] + (list(_temas["nome"]) if not _temas.empty else [])
        colunas_cadastro = ["id", "nome", "ticker", "tipo", "classe", "tema",
                            "moeda", "instituicao", "indexador",
                            "taxa_contratada", "data_inicio",
                            "data_vencimento", "liquidez", "objetivo", "ativo"]
        base = (
            cadastro[colunas_cadastro].copy() if not cadastro.empty
            else pd.DataFrame(columns=colunas_cadastro)
        )
        if not base.empty:
            base["ativo"] = base["ativo"].fillna(1).astype(bool)
            # A sugestao do provedor, ao lado do campo e TRAVADA. Ela mostra o
            # que o yfinance diz (sector · industry) sem nunca gravar nada —
            # para a IREN ela diz "Financial Services", e e por estar errada
            # que precisa ficar visivel em vez de virar o valor.
            base.insert(
                base.columns.get_loc("tema") + 1, "sugestao_provedor",
                [calc.sugestao_de_tema(tk) for tk in base["ticker"]])

        editado_cadastro = priv.editor(
            base, hide_index=True, width="stretch", num_rows="dynamic",
            key="editor_investimentos",
            column_config={
                "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
                "nome": st.column_config.TextColumn(
                    "Aplicação", required=True, width="large",
                    help="ex: CDB Banco XP 110% CDI"),
                "ticker": st.column_config.TextColumn(
                    "Ticker", width="small",
                    help="Símbolo para buscar a cotação. B3 leva .SA (TASA3.SA); "
                         "bolsa americana vai direto (IREN). Vazio = acompanhado "
                         "à mão, como Tesouro e fundos."),
                "tipo": st.column_config.SelectboxColumn("Tipo", options=calc.TIPOS),
                "classe": st.column_config.SelectboxColumn(
                    "Classe", options=lista_classes,
                    help="É o que decide o rebalanceamento e a leitura de risco."),
                "tema": st.column_config.SelectboxColumn(
                    "Tema", options=lista_temas,
                    help="A que este papel te EXPÕE — datacenters, metais, "
                         "bolsa ampla. É outro eixo, não um filho da classe: "
                         "«Datacenters» pode juntar uma ação, um REIT e um "
                         "ETF. Deixe vazio na renda fixa."),
                "sugestao_provedor": st.column_config.TextColumn(
                    "O provedor diz", disabled=True, width="medium",
                    help="Setor e indústria segundo o yfinance. É a "
                         "classificação CONTÁBIL da empresa, não a exposição: "
                         "para a IREN ele diz «Financial Services», e ela é um "
                         "datacenter de IA. Está aqui para você comparar, e "
                         "nunca preenche o Tema sozinho."),
                "moeda": st.column_config.SelectboxColumn(
                    "Moeda", options=["BRL", "USD"], width="small",
                    help="Em USD, o saldo é digitado em dólar e convertido pelo "
                         "PTAX do fim do mês."),
                "instituicao": st.column_config.TextColumn("Instituição"),
                "indexador": st.column_config.SelectboxColumn(
                    "Indexador", options=calc.INDEXADORES),
                "taxa_contratada": st.column_config.NumberColumn(
                    "Taxa", format="%.4f", step=0.01,
                    help="1,10 para 110% do CDI · 0,12 para 12% ao ano"),
                "data_inicio": st.column_config.TextColumn(
                    "Início", help="AAAA-MM-DD", width="small"),
                "data_vencimento": st.column_config.TextColumn(
                    "Vencimento", help="AAAA-MM-DD — vazio se não tem", width="small"),
                "liquidez": st.column_config.SelectboxColumn(
                    "Liquidez", options=calc.LIQUIDEZ),
                "objetivo": st.column_config.TextColumn(
                    "Objetivo", help="para que esse dinheiro serve"),
                "ativo": st.column_config.CheckboxColumn("Ativa"),
            },
        )

        if st.button("Salvar cadastro", type="primary", key="salvar_investimentos"):
            salvos = 0
            for _, linha in editado_cadastro.iterrows():
                nome = _texto_ou_none(linha.get("nome")) or ""
                if not nome:
                    continue
                calc.salvar({
                    "id": int(linha["id"]) if pd.notna(linha.get("id")) else None,
                    "nome": nome,
                    "ticker": (_texto_ou_none(linha.get("ticker")) or "").upper() or None,
                    "classe": _texto_ou_none(linha.get("classe")),
                    "tema": _texto_ou_none(linha.get("tema")),
                    "moeda": _texto_ou_none(linha.get("moeda")) or "BRL",
                    "tipo": _texto_ou_none(linha.get("tipo")) or "Renda Fixa",
                    "instituicao": _texto_ou_none(linha.get("instituicao")),
                    "indexador": _texto_ou_none(linha.get("indexador")),
                    "taxa_contratada": (
                        float(linha["taxa_contratada"])
                        if pd.notna(linha.get("taxa_contratada")) else None),
                    "data_inicio": _texto_ou_none(linha.get("data_inicio")),
                    "data_vencimento": _texto_ou_none(linha.get("data_vencimento")),
                    "liquidez": _texto_ou_none(linha.get("liquidez")),
                    "objetivo": _texto_ou_none(linha.get("objetivo")),
                    "ativo": 1 if linha.get("ativo", True) else 0,
                    "observacao": None,
                })
                salvos += 1

            ids_na_tela = {int(i) for i in editado_cadastro["id"].dropna()}
            if not cadastro.empty:
                for id_antigo in cadastro["id"]:
                    if int(id_antigo) not in ids_na_tela:
                        calc.apagar(int(id_antigo))

            estado.limpar_cache()
            c.recado(f"{salvos} aplicação(ões) salva(s).")
            st.rerun()

        with st.expander("Exemplos de como preencher"):
            st.markdown(
                """
    | Aplicação | Tipo | Indexador | Taxa | Liquidez |
    |---|---|---|---|---|
    | CDB Banco XP 110% CDI | Renda Fixa | CDI | 1,10 | Diária |
    | Tesouro Selic 2029 | Tesouro Direto | Selic | 1,00 | Diária |
    | Tesouro IPCA+ 2035 | Tesouro Direto | IPCA+ | 0,06 | No vencimento |
    | Fundo XP Macro | Fundo | Variável | — | D+30 |
    | Ações (carteira) | Renda Variável | Variável | — | Diária |

    **Taxa** é opcional e serve só de lembrete do que você contratou — o
    rendimento de verdade sai da diferença entre os saldos que você informar, não
    da taxa. Assim funciona mesmo para renda variável, onde não existe taxa.
                """
            )

        with st.expander("Os temas de exposição (edite a lista)"):
            st.caption(
                "Tema é a que o papel te **expõe**, e é um eixo separado da "
                "classe: «Datacenters» pode juntar uma ação, um REIT e um ETF. "
                "A lista é sua — acrescente na última linha vazia. Um tema em "
                "uso por algum papel não pode ser removido daqui sem antes "
                "trocar o tema daquele papel."
            )
            base_temas = (_temas[["nome", "ordem"]].copy() if not _temas.empty
                          else pd.DataFrame(columns=["nome", "ordem"]))
            editado_temas = priv.editor(
                base_temas, hide_index=True, width="stretch",
                num_rows="dynamic", key="editor_temas",
                column_config={
                    "nome": st.column_config.TextColumn(
                        "Tema", required=True, width="large"),
                    "ordem": st.column_config.NumberColumn(
                        "Ordem", step=1, width="small",
                        help="só a ordem em que aparecem na caixa de seleção"),
                },
            )

            em_uso = set()
            if not cadastro.empty and "tema" in cadastro.columns:
                em_uso = {str(t_) for t_ in cadastro["tema"].dropna()}

            if st.button("Salvar temas", key="salvar_temas"):
                nomes_na_tela = {
                    str(l["nome"]).strip()
                    for _, l in editado_temas.iterrows()
                    if not vazio(l.get("nome"))
                }
                # Um tema em uso nao pode simplesmente sumir: os papeis que o
                # apontam ficariam com um valor que nao existe mais na lista, e
                # a caixa de selecao apareceria vazia sem explicar por que.
                orfaos = sorted(em_uso - nomes_na_tela)
                if orfaos:
                    c.recado(
                        f"Não salvei: {', '.join(f'«{o}»' for o in orfaos)} "
                        f"está em uso por algum papel. Troque o tema daquele "
                        f"papel primeiro.", "aviso")
                else:
                    banco.executar("DELETE FROM temas_ativo")
                    banco.executar_muitos(
                        "INSERT OR IGNORE INTO temas_ativo (nome, ordem) "
                        "VALUES (?, ?)",
                        [(str(l["nome"]).strip(),
                          int(l["ordem"]) if pd.notna(l.get("ordem")) else 99)
                         for _, l in editado_temas.iterrows()
                         if not vazio(l.get("nome"))],
                    )
                    c.recado(f"{len(nomes_na_tela)} tema(s) salvo(s).")
                estado.limpar_cache()
                st.rerun()

        st.markdown("---")
        st.markdown("### Metas de alocação")
        st.caption(
            "Quanto da carteira você quer em cada classe. É isto — e só isto — "
            "que a aba **Rebalanceamento** usa para decidir para onde mandar o "
            "aporte. Enquanto estiver tudo em zero, aquela aba fica em branco."
        )

        nivel_meta = st.radio(
            "Definir metas por", ["Classe", "Macro"], horizontal=True,
            key="meta_nivel",
            help="Você pode usar os dois, mas normalmente escolhe-se um. "
                 "Classe dá mais controle; Macro é mais simples de manter.",
        )
        nivel_alvo = "macro" if nivel_meta == "Macro" else "classe"

        universo = (calc.macros() if nivel_alvo == "macro" else calc.classes())
        metas_atuais = calc.metas(nivel_alvo)
        mapa_metas = {linha["nome"]: (linha["percentual_alvo"], linha["tolerancia"])
                      for _, linha in metas_atuais.iterrows()}

        saldos_por_nome = {}
        tabela_hoje = alocacao_macro if nivel_alvo == "macro" else alocacao
        if not tabela_hoje.empty:
            saldos_por_nome = dict(zip(tabela_hoje["nome"], tabela_hoje["percentual"]))

        editor = pd.DataFrame([
            {
                "Nome": linha["nome"],
                "Hoje %": round(saldos_por_nome.get(linha["nome"], 0.0) * 100, 2),
                "Meta %": round(mapa_metas.get(linha["nome"], (0.0, 0.05))[0] * 100, 2),
                "Tolerância (pp)": round(
                    mapa_metas.get(linha["nome"], (0.0, 0.05))[1] * 100, 1),
            }
            for _, linha in universo.iterrows()
        ])

        editado = priv.editor(
            editor, hide_index=True, width="stretch", key="editor_metas",
            column_config={
                "Nome": st.column_config.TextColumn("Nome", disabled=True),
                "Hoje %": st.column_config.NumberColumn(
                    "Hoje %", disabled=True, format="%.2f%%",
                    help="Quanto você tem hoje nessa classe."),
                "Meta %": st.column_config.NumberColumn(
                    "Meta %", min_value=0.0, max_value=100.0, step=1.0,
                    format="%.2f%%", help="Quanto você QUER ter."),
                "Tolerância (pp)": st.column_config.NumberColumn(
                    "Tolerância (pp)", min_value=0.0, max_value=50.0, step=0.5,
                    format="%.1f",
                    help="Em pontos percentuais. Com meta 20% e tolerância 5, "
                         "qualquer coisa entre 15% e 25% conta como 'na faixa'."),
            },
        )

        soma_editada = float(editado["Meta %"].sum())
        if abs(soma_editada - 100) < 0.005:
            st.success(f"As metas somam {soma_editada:.2f}%.")
        elif soma_editada == 0:
            st.info("Nenhuma meta definida ainda.")
        else:
            st.warning(
                f"As metas somam **{soma_editada:.2f}%**, e não 100%. "
                f"{'Faltam' if soma_editada < 100 else 'Sobram'} "
                f"**{abs(100 - soma_editada):.2f} pontos**."
            )

        coluna_salvar, coluna_limpar = st.columns([1, 1])
        with coluna_salvar:
            if st.button("Salvar metas", type="primary", key="salvar_metas"):
                for _, linha in editado.iterrows():
                    alvo = float(linha["Meta %"] or 0) / 100
                    tolerancia = float(linha["Tolerância (pp)"] or 0) / 100
                    if alvo > 0:
                        calc.salvar_meta(nivel_alvo, linha["Nome"], alvo, tolerancia)
                    else:
                        calc.apagar_meta(nivel_alvo, linha["Nome"])
                c.recado("Metas salvas.")
                st.rerun()
        with coluna_limpar:
            if st.button("Apagar todas as metas", key="limpar_metas"):
                for _, linha in universo.iterrows():
                    calc.apagar_meta(nivel_alvo, linha["nome"])
                st.rerun()

        c.nota(
            "Meta <strong>zerada é o mesmo que não ter meta</strong>: a classe "
            "some do rebalanceamento em vez de aparecer como permanentemente "
            "estourada. Para tirar dinheiro de uma classe, defina a meta que você "
            "quer e deixe os aportes seguintes corrigirem — o app nunca sugere "
            "vender."
        )


    with sub_movimentos:
        # ─── O QUE O APP NAO SOUBE CLASSIFICAR ─────────────────────────────
        # Ele pediu que nao houvesse "dinheiro sumindo no meio do caminho".
        # Para isso o app precisa primeiro ser capaz de DIZER que nao sabe.
        # `TED - RECEBIMENTO EXTERNO` de R$ ···· pode ser uma venda, uma
        # heranca ou um reembolso — o texto nao decide, e chutar erraria
        # em silencio, que e o defeito que estamos consertando. Entao pergunta.
        a_triar = fechamento.movimentos_a_triar()
        if not a_triar.empty:
            with c.painel(
                    "Dinheiro que eu não soube explicar",
                    f"{len(a_triar)} movimentação(ões) sem classificação"):
                st.markdown(
                    "A corretora registrou isto, e nenhuma regra do app se "
                    "aplica. Enquanto ficar aqui, o valor aparece como "
                    "**não explicado** na conciliação — de propósito, para "
                    "não virar rendimento por descuido.\n\n"
                    "Dinheiro que **cruzou a fronteira** do seu patrimônio "
                    "(entrou ou saiu de fora) também vira lançamento, para "
                    "contar como receita ou despesa do mês — por isso a "
                    "categoria. **Transferência entre contas suas não vira "
                    "lançamento**: a outra ponta já está no extrato da conta "
                    "corrente, e somá-la de novo contaria o mesmo dinheiro "
                    "duas vezes."
                )

                # As duas listas juntas, porque uma coluna de tabela tem UMA
                # lista de opções. A validação no salvamento é que impede
                # entrada externa receber categoria de despesa.
                categorias_possiveis = sorted(set(
                    fechamento.categorias_para("entrada_externa")
                    + fechamento.categorias_para("saida_externa")))

                # Uma linha pode estar aqui porque nunca foi classificada ou
                # porque o lançamento dela foi apagado depois. São situações
                # diferentes e a coluna «Por quê» diz qual — sem isso, ver de
                # novo algo que você já respondeu pareceria defeito.
                reaparecidas = int(
                    (a_triar["motivo"] == "o lançamento foi apagado").sum())
                if reaparecidas:
                    c.tarja(
                        f"{reaparecidas} movimentação(ões) voltou(voltaram) "
                        f"para esta lista porque o lançamento que a(s) "
                        f"explicava foi apagado. Classifique de novo, ou o "
                        f"dinheiro fica sem explicação.", "aviso")

                painel_triagem = a_triar[
                    ["id", "data", "descricao", "valor", "motivo"]].copy()
                painel_triagem["natureza"] = ""
                painel_triagem["categoria"] = ""

                editado_triagem = priv.editor(
                    painel_triagem.rename(columns={
                        "data": "Data", "descricao": "Lançamento",
                        "valor": "Valor", "motivo": "Por quê",
                        "natureza": "O que foi isto?",
                        "categoria": "Categoria"}),
                    hide_index=True, width="stretch", key="triagem_movimentos",
                    disabled=["id", "Data", "Lançamento", "Valor", "Por quê"],
                    column_config={
                        "id": None,
                        "Valor": c.config_moeda("Valor"),
                        "Por quê": st.column_config.TextColumn(
                            "Por quê", width="small"),
                        "O que foi isto?": st.column_config.SelectboxColumn(
                            "O que foi isto?",
                            options=list(fechamento.NATUREZAS.values()),
                            required=False, width="large"),
                        "Categoria": st.column_config.SelectboxColumn(
                            "Categoria",
                            help="Só para entrada ou saída externa — é ela que "
                                 "decide a ficha do imposto de renda.",
                            options=categorias_possiveis,
                            required=False, width="medium"),
                    },
                )

                if st.button("Classificar", type="primary",
                             key="btn_triar_movimentos"):
                    (respondidos, sem_categoria,
                     incompativel) = fechamento.ler_triagem(editado_triagem)

                    if incompativel:
                        c.recado("Categoria incompatível: "
                                 + "; ".join(incompativel), "aviso")
                    elif sem_categoria:
                        c.recado(
                            "Dinheiro que entrou ou saiu de fora precisa de "
                            "categoria, para virar lançamento do mês: "
                            + ", ".join(sem_categoria), "aviso")
                    elif not respondidos:
                        c.recado("Escolha o que foi cada movimentação antes "
                                 "de classificar.", "aviso")
                    else:
                        viraram = 0
                        for movimento_id, natureza, categoria in respondidos:
                            fechamento.triar(movimento_id, natureza, categoria)
                            viraram += bool(categoria)
                        estado.limpar_cache()
                        aviso = (f"{len(respondidos)} movimentação(ões) "
                                 f"classificada(s).")
                        if viraram:
                            aviso += (f" {viraram} virou(viraram) lançamento e "
                                      f"já conta(m) como receita ou despesa "
                                      f"do mês.")
                        c.recado(aviso)
                    st.rerun()

        resumo_tipos = calc.resumo_movimentos()
        if resumo_tipos.empty:
            c.aviso_vazio(
                "Nenhuma movimentação da conta de investimento importada.",
                "Na tela **Importar**, suba o arquivo `Extrato NNNNNNN ….xlsx` "
                "que a corretora exporta.",
            )
        else:
            st.markdown("#### Resumo por tipo")
            visao_resumo = resumo_tipos.copy()
            visao_resumo["significado"] = visao_resumo["tipo_movimento"].map(
                lambda t: DESCRICAO_TIPOS.get(t, ""))
            priv.tabela(
                visao_resumo.rename(columns={
                    "tipo_movimento": "Tipo", "quantidade": "Qtd.",
                    "soma": "Total", "significado": "O que é",
                }),
                hide_index=True, width="stretch",
                column_config={"Total": c.config_moeda("Total")},
            )

            st.markdown("#### Lançamentos")
            coluna_mes, coluna_tipo = st.columns(2)
            with coluna_mes:
                meses_disponiveis = sorted(
                    calc.movimentos()["mes_competencia"].unique(), reverse=True)
                filtro_mes = st.selectbox(
                    "Mês", ["(todos)"] + [rotulo_mes(m) for m in meses_disponiveis],
                    key="mov_inv_mes")
            with coluna_tipo:
                filtro_tipo = st.selectbox(
                    "Tipo", ["(todos)"] + list(resumo_tipos["tipo_movimento"]),
                    key="mov_inv_tipo")

            mes_filtrado = None
            if filtro_mes != "(todos)":
                mes_filtrado = meses_disponiveis[
                    [rotulo_mes(m) for m in meses_disponiveis].index(filtro_mes)]

            lista_movimentos = calc.movimentos(
                mes_filtrado, None if filtro_tipo == "(todos)" else filtro_tipo)

            if lista_movimentos.empty:
                st.info("Nenhuma movimentação com esses filtros.")
            else:
                priv.tabela(
                    lista_movimentos[["data", "descricao", "tipo_movimento",
                                      "valor", "saldo_apos"]].rename(columns={
                        "data": "Data", "descricao": "Lançamento",
                        "tipo_movimento": "Tipo", "valor": "Valor",
                        "saldo_apos": "Saldo depois",
                    }),
                    hide_index=True, width="stretch",
                    column_config={
                        "Valor": c.config_moeda("Valor"),
                        "Saldo depois": c.config_moeda("Saldo depois"),
                    },
                )
                st.caption(f"{len(lista_movimentos)} movimentação(ões).")

            with c.painel(chave="movimentacoes_conta"):
                priv.grafico(
                    graficos.movimentacoes_investimento(movimentacoes),
                    width="stretch", key="investimentos_movimentacoes_conta")
