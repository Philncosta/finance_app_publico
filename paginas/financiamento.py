"""
financiamento.py — Simulador de financiamento imobiliario.
==============================================================================

O QUE ESTA TELA MOSTRA
----------------------
Voce preenche as premissas do contrato e ve, mes a mes, quanto de cada
prestacao vira juro e quanto abate a divida. E, principalmente, o que acontece
se voce adiantar parcelas.

OS DOIS SISTEMAS, EM UMA FRASE CADA
-----------------------------------
    PRICE  prestacao FIXA do comeco ao fim. Previsivel, mas paga mais juros.
    SAC    prestacao COMECA MAIOR e vai caindo. Pesa mais no inicio, mas o
           total de juros e bem menor.

O CUSTO QUE QUASE TODO SIMULADOR ESCONDE
----------------------------------------
Alem dos juros, todo financiamento imobiliario cobra:
    MIP  seguro de morte e invalidez (% sobre o saldo devedor)
    DFI  seguro de danos ao imovel (% sobre o valor do imovel)
    taxa de administracao (valor fixo por mes)

Por isso a tela separa "prestação" (o que abate divida + juro) de
"desembolso" (o que sai de verdade da sua conta). A diferenca entre os dois
costuma ser de 5% a 10%.
"""

from __future__ import annotations

import streamlit as st

from financas.calculos import financiamento as calc
from financas.formato import fmt_num, fmt_pct
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado, graficos

c.cabecalho("Financiamento", "Simulador de financiamento imobiliário")

cenario = dict(estado.cenario_financiamento())


with st.container(border=True, key="cartao_cenario"):
    st.markdown("**Premissas do contrato**")

    linha1 = st.columns([2, 2, 2, 2])
    with linha1[0]:
        cenario["valor_imovel"] = st.number_input(
            "Valor do imóvel (R$)", min_value=0.0,
            value=float(cenario.get("valor_imovel") or 0), step=10000.0)
    with linha1[1]:
        cenario["valor_entrada"] = st.number_input(
            "Entrada (R$)", min_value=0.0,
            value=float(cenario.get("valor_entrada") or 0), step=5000.0,
            help="recursos próprios + FGTS")
    with linha1[2]:
        cenario["prazo_meses"] = st.number_input(
            "Prazo (meses)", min_value=12, max_value=420,
            value=int(cenario.get("prazo_meses") or 360), step=12)
    with linha1[3]:
        cenario["sistema"] = st.selectbox(
            "Sistema", calc.SISTEMAS,
            index=calc.SISTEMAS.index(cenario.get("sistema", "PRICE"))
            if cenario.get("sistema") in calc.SISTEMAS else 0)

    linha2 = st.columns([2, 2, 2, 2])
    with linha2[0]:
        cenario["juros_aa"] = st.number_input(
            "Juros ao ano (%)", min_value=0.0, max_value=30.0,
            value=float(cenario.get("juros_aa") or 0.105) * 100, step=0.1) / 100
    with linha2[1]:
        cenario["conversao_taxa"] = st.selectbox(
            "Conversão para taxa mensal", calc.CONVERSOES,
            index=calc.CONVERSOES.index(cenario.get("conversao_taxa"))
            if cenario.get("conversao_taxa") in calc.CONVERSOES else 0,
            help="Equivalente é o padrão dos contratos imobiliários no Brasil.")
    with linha2[2]:
        cenario["seguro_mip_am"] = st.number_input(
            "MIP (% a.m. sobre o saldo)", min_value=0.0, max_value=1.0,
            value=float(cenario.get("seguro_mip_am") or 0.00025) * 100,
            step=0.005, format="%.4f") / 100
    with linha2[3]:
        cenario["seguro_dfi_am"] = st.number_input(
            "DFI (% a.m. sobre o imóvel)", min_value=0.0, max_value=1.0,
            value=float(cenario.get("seguro_dfi_am") or 0.0001) * 100,
            step=0.005, format="%.4f") / 100

    linha3 = st.columns([2, 6])
    with linha3[0]:
        cenario["taxa_adm_mes"] = st.number_input(
            "Taxa de administração (R$/mês)", min_value=0.0,
            value=float(cenario.get("taxa_adm_mes") or 25), step=5.0)

    taxa_mensal = calc.taxa_mensal(cenario["juros_aa"], cenario["conversao_taxa"])
    with linha3[1]:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(
            f"Taxa mensal aplicada: **{taxa_mensal * 100:.4f}% a.m.** · "
            f"Valor financiado: **{fmt_brl_md(cenario['valor_imovel'] - cenario['valor_entrada'])}** · "
            f"LTV: **{fmt_pct((cenario['valor_imovel'] - cenario['valor_entrada']) / cenario['valor_imovel'] if cenario['valor_imovel'] else 0)}**"
        )


with st.container(border=True, key="cartao_resultado"):
    st.markdown("**Adiantar parcelas (amortização extraordinária)**")
    st.caption(
        "Dinheiro extra jogado no saldo devedor. É onde a economia de juros "
        "aparece de forma mais dramática — vale testar valores pequenos."
    )

    linha = st.columns([2, 2, 2, 2, 2])
    with linha[0]:
        cenario["aporte_extra_mes"] = st.number_input(
            "Aporte extra mensal (R$)", min_value=0.0,
            value=float(cenario.get("aporte_extra_mes") or 0), step=100.0)
    with linha[1]:
        cenario["aporte_inicio"] = st.number_input(
            "A partir da parcela nº", min_value=1,
            value=int(cenario.get("aporte_inicio") or 1), step=1)
    with linha[2]:
        cenario["aporte_pontual"] = st.number_input(
            "Aporte único (R$)", min_value=0.0,
            value=float(cenario.get("aporte_pontual") or 0), step=1000.0,
            help="13º, FGTS, bônus")
    with linha[3]:
        cenario["aporte_pontual_parcela"] = st.number_input(
            "Na parcela nº", min_value=1,
            value=int(cenario.get("aporte_pontual_parcela") or 12), step=1)
    with linha[4]:
        cenario["efeito_aporte"] = st.selectbox(
            "Efeito", calc.EFEITOS_APORTE,
            index=calc.EFEITOS_APORTE.index(cenario.get("efeito_aporte"))
            if cenario.get("efeito_aporte") in calc.EFEITOS_APORTE else 0,
            help="Reduzir prazo economiza mais juros. Reduzir parcela alivia "
                 "o orçamento mensal.")


tabela = calc.tabela(cenario)
resumo = calc.resumo(cenario)

if tabela.empty:
    c.aviso_vazio(
        "Preencha o valor do imóvel e a entrada para simular.",
        "O valor financiado precisa ser maior que zero.",
    )
    st.stop()

st.markdown("### Resumo do contrato")

c.linha_kpis([
    {"rotulo": "1ª prestação", "valor": fmt_brl(resumo["primeira_prestacao"]),
     "ajuda": f"desembolso real: {fmt_brl(resumo['primeiro_desembolso'])}",
     "cor": "azul"},
    {"rotulo": "Última prestação", "valor": fmt_brl(resumo["ultima_prestacao"]),
     "ajuda": "PRICE mantém fixa; SAC vai caindo"},
    {"rotulo": "Total de juros", "valor": fmt_brl(resumo["total_juros"]),
     "ajuda": f"{fmt_pct(resumo['total_juros'] / resumo['valor_financiado'] if resumo['valor_financiado'] else 0)} do valor financiado",
     "cor": "vermelha"},
    {"rotulo": "Prazo efetivo", "valor": f"{resumo['prazo_efetivo']} meses",
     "ajuda": f"{fmt_num(resumo['prazo_efetivo'] / 12, 1)} anos"},
])

c.linha_kpis([
    {"rotulo": "Valor financiado", "valor": fmt_brl(resumo["valor_financiado"]),
     "pequeno": True},
    {"rotulo": "Seguros e taxas", "valor": fmt_brl(resumo["total_seguros_taxas"]),
     "ajuda": "MIP + DFI + administração", "pequeno": True},
    {"rotulo": "Custo total do financiamento", "valor": fmt_brl(resumo["custo_total"]),
     "ajuda": "amortização + juros + seguros", "pequeno": True, "cor": "vermelha"},
    {"rotulo": "Custo total com a entrada", "valor": fmt_brl(resumo["custo_com_entrada"]),
     "ajuda": f"por um imóvel de {fmt_brl(cenario['valor_imovel'])}",
     "pequeno": True, "cor": "vermelha"},
])

if resumo["juros_economizados"] > 0:
    c.nota(
        f"Com os aportes que você configurou, o financiamento termina "
        f"<strong>{resumo['meses_economizados']} meses antes</strong> "
        f"({fmt_num(resumo['meses_economizados'] / 12, 1)} anos) e você deixa "
        f"de pagar <strong>{fmt_brl(resumo['juros_economizados'])}</strong> "
        f"de juros."
    )
else:
    custo_extra = resumo["custo_total"] - resumo["valor_financiado"]
    c.nota(
        f"Neste contrato você pagaria <strong>{fmt_brl(custo_extra)}</strong> "
        f"além do valor financiado — "
        f"{fmt_pct(custo_extra / resumo['valor_financiado'] if resumo['valor_financiado'] else 0)} "
        f"a mais. Experimente colocar um aporte extra mensal acima para ver o "
        f"efeito."
    )


st.markdown("### PRICE x SAC, no mesmo contrato")

comparacao = []
for sistema in calc.SISTEMAS:
    alternativo = dict(cenario)
    alternativo["sistema"] = sistema
    resumo_alt = calc.resumo(alternativo)
    comparacao.append({
        "Sistema": sistema,
        "1ª prestação": resumo_alt["primeira_prestacao"],
        "Última prestação": resumo_alt["ultima_prestacao"],
        "Total de juros": resumo_alt["total_juros"],
        "Custo total": resumo_alt["custo_total"],
        "Prazo": resumo_alt["prazo_efetivo"],
    })

import pandas as pd  # noqa: E402

df_comparacao = pd.DataFrame(comparacao)
priv.tabela(
    df_comparacao, hide_index=True, width="stretch",
    column_config={
        "1ª prestação": c.config_moeda("1ª prestação"),
        "Última prestação": c.config_moeda("Última prestação"),
        "Total de juros": c.config_moeda("Total de juros"),
        "Custo total": c.config_moeda("Custo total"),
    },
)

diferenca_juros = abs(df_comparacao["Total de juros"].iloc[0]
                      - df_comparacao["Total de juros"].iloc[1])
diferenca_primeira = abs(df_comparacao["1ª prestação"].iloc[0]
                         - df_comparacao["1ª prestação"].iloc[1])
st.caption(
    f"O SAC economiza **{fmt_brl_md(diferenca_juros)}** em juros, mas exige "
    f"**{fmt_brl_md(diferenca_primeira)}** a mais na primeira prestação. "
    f"A pergunta prática é: você aguenta a prestação inicial do SAC sem "
    f"apertar o orçamento?"
)


col1, col2 = st.columns([1, 1], gap="medium")
with col1:
    with c.painel("Composição de cada ano: juros x amortização"):
        priv.grafico(graficos.amortizacao_por_ano(calc.por_ano(tabela)),
                     width="stretch", key="financiamento_amortizacao_por_ano")
    st.caption(
        "Nos primeiros anos a barra vermelha (juros) domina e a verde "
        "(amortização) é fina. É por isso que a dívida parece não andar no "
        "começo — e por que adiantar parcela cedo economiza tanto."
    )
with col2:
    with c.painel("Saldo devedor ao longo do contrato"):
        priv.grafico(graficos.saldo_devedor(tabela), width="stretch",
                     key="financiamento_saldo_devedor")


with st.expander(f"Tabela de amortização completa ({len(tabela)} parcelas)"):
    priv.tabela(
        tabela.rename(columns={
            "parcela": "Nº", "saldo_inicial": "Saldo devedor",
            "juros": "Juros", "amortizacao": "Amortização",
            "amortizacao_extra": "Aporte extra", "prestacao": "Prestação",
            "mip": "MIP", "dfi": "DFI", "taxa_adm": "Taxa adm.",
            "desembolso": "Desembolso", "saldo_final": "Saldo após",
        }),
        hide_index=True, width="stretch", height=420,
        column_config={
            coluna: c.config_moeda(coluna) for coluna in
            ["Saldo devedor", "Juros", "Amortização", "Aporte extra",
             "Prestação", "MIP", "DFI", "Taxa adm.", "Desembolso", "Saldo após"]
        },
    )
    st.caption(
        "**Prestação** = juros + amortização (o que o contrato cobra de dívida). "
        "**Desembolso** = prestação + seguros + taxa + aporte extra (o que sai "
        "da sua conta de verdade)."
    )

    csv_bytes = tabela.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button("Baixar tabela em CSV", csv_bytes,
                       file_name="financiamento.csv", mime="text/csv")


st.markdown("---")
col_nome, col_salvar = st.columns([3, 1])
with col_nome:
    cenario["nome"] = st.text_input(
        "Nome deste cenário", value=cenario.get("nome") or "Meu cenário")
with col_salvar:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Salvar cenário", type="primary", width="stretch"):
        calc.salvar_cenario(cenario)
        estado.limpar_cache()
        st.success("Cenário salvo.")
