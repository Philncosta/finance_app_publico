"""
patrimonio.py — Quanto voce tem, e por quantos meses isso te sustenta.
==============================================================================

A PERGUNTA CENTRAL
------------------
Nao e "quanto eu tenho?" — e "por quanto tempo eu aguento sem renda?".

R$ ···· parados nao significam nada isolados. Para quem gasta R$ ···· por
mes sao 12 meses de tranquilidade; para quem gasta R$ ····, sao menos de
tres. Por isso a reserva e medida em MESES DE DESPESA.

DE ONDE VEM CADA NUMERO
-----------------------
SALDO EM CONTA — do extrato importado (o proprio banco informa o saldo depois
de cada transacao) ou do valor que voce digitar. O que voce digita tem
prioridade.

SALDO APLICADO — estimado, acumulando aportes, resgates e rendimentos. Voce
pode corrigir qualquer mes digitando o valor real da corretora.
"""

from __future__ import annotations

import streamlit as st

from financas import banco
from financas.calculos import patrimonio as calc
from financas.formato import fmt_num, fmt_pct, rotulo_mes
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado, graficos

df = estado.lancamentos()

c.cabecalho("Patrimônio", "Reserva de emergência e evolução do que você tem")
c.mostrar_recado()

if df.empty:
    c.aviso_vazio("Sem lançamentos ainda.")
    st.stop()

mes = estado.seletor_de_mes_topo()

posicao = calc.posicao_atual(df, mes)
evolucao = calc.evolucao(df)

tem_terceiros = abs(posicao.get("capital_terceiros", 0.0)) > 0.005

tem_saldo_aplicado_informado = bool(
    banco.consultar_um(
        """SELECT 1 FROM investimentos_saldos WHERE mes <= ? LIMIT 1""",
        (mes or "9999-12",))
    or banco.consultar_um(
        """SELECT 1 FROM patrimonio_mensal
           WHERE saldo_aplicado_manual IS NOT NULL AND mes <= ? LIMIT 1""",
        (mes or "9999-12",)))


CORES_SITUACAO = {
    "crítica": "vermelha",
    "frágil": "vermelha",
    "razoável": "amarela",
    "confortável": "verde",
    "sem dados": None,
}

c.linha_kpis([
    {
        "rotulo": "Em conta",
        "valor": fmt_brl(posicao["saldo_conta"]),
        "ajuda": "dinheiro líquido, disponível hoje",
        "cor": "azul",
    },
    {
        "rotulo": "Aplicado",
        "valor": fmt_brl(posicao["saldo_aplicado"]),
        "ajuda": ("informado pela corretora ou por você"
                  if tem_saldo_aplicado_informado
                  else "estimado pelas transferências de investimento"),
        "cor": "azul",
    },
    {
        "rotulo": "Seu patrimônio" if tem_terceiros else "Patrimônio total",
        "valor": fmt_brl(posicao["patrimonio_proprio"]),
        "ajuda": (f"nas contas há {fmt_brl(posicao['patrimonio_total'])}, "
                  f"incluindo o que não é seu" if tem_terceiros
                  else f"posição em {rotulo_mes(posicao['mes'])}"),
        "cor": "verde",
    },
    {
        "rotulo": "Reserva cobre",
        "valor": f"{fmt_num(posicao['meses_de_reserva'], 1)} meses",
        "ajuda": f"gastando {fmt_brl(posicao['despesa_media'])}/mês",
        "delta": posicao["situacao"],
        "delta_positivo": posicao["situacao"] == "confortável",
        "cor": CORES_SITUACAO.get(posicao["situacao"]),
    },
])

if tem_terceiros:
    terceiros = posicao["capital_terceiros"]
    st.markdown("### Dentro e fora do patrimônio")
    c.linha_kpis([
        {"rotulo": "Nas suas contas",
         "valor": fmt_brl(posicao["patrimonio_total"]),
         "ajuda": "tudo que está lá, seu e de terceiros", "pequeno": True},
        {"rotulo": "De terceiros",
         "valor": fmt_brl(terceiros),
         "ajuda": "emprestado, sob sua gestão",
         "cor": "amarela", "pequeno": True},
        {"rotulo": "Seu patrimônio",
         "valor": fmt_brl(posicao["patrimonio_proprio"]),
         "ajuda": "o que sobra se você devolver",
         "cor": "verde", "pequeno": True},
    ])
    c.nota(
        f"Esses <strong>{fmt_brl(terceiros)}</strong> entram e saem da sua "
        f"conta e são investidos junto com o seu dinheiro, mas não são renda "
        f"nem despesa sua — e não contam como patrimônio. "
        f"A <strong>reserva de emergência é calculada sobre o seu "
        f"patrimônio</strong>: numa emergência esse dinheiro pode precisar "
        f"voltar, então contá-lo diria que você aguenta mais tempo do que "
        f"aguenta de verdade."
    )

st.markdown("### Meta de reserva de emergência")

col_meta, col_barra = st.columns([1, 3])
with col_meta:
    meta_meses = st.number_input(
        "Meses de despesa", min_value=1, max_value=36,
        value=int(posicao["meta_meses"]), step=1,
        help="Quantos meses de despesa você quer ter guardados. "
             "Três é o mínimo comum; seis é o mais recomendado.",
    )
    if meta_meses != posicao["meta_meses"]:
        banco.definir_parametro("meta_reserva_meses", meta_meses)
        estado.limpar_cache()
        st.rerun()

with col_barra:
    alvo = meta_meses * posicao["despesa_media"]
    st.markdown(
        f"**{fmt_brl_md(posicao['patrimonio_proprio'])}** de "
        f"**{fmt_brl_md(alvo)}** ({fmt_pct(posicao['pct_da_meta'])})"
    )
    c.barra(posicao["pct_da_meta"])
    if posicao["falta_para_meta"] > 0:
        st.caption(
            f"Faltam {fmt_brl_md(posicao['falta_para_meta'])} para chegar em "
            f"{meta_meses} meses de reserva."
        )
    else:
        st.caption("Meta atingida. A partir daqui, o dinheiro pode ir para outros objetivos.")

c.nota(
    f"A reserva é calculada sobre uma despesa mensal de "
    f"<strong>{fmt_brl(posicao['despesa_media'])}</strong>, que é a "
    f"<strong>mediana</strong> dos seus últimos meses — não a média. "
    f"A mediana ignora meses atípicos (como a compra da moto em fevereiro), "
    f"então representa melhor um mês normal da sua vida."
)


st.markdown("### Evolução mês a mês")
with c.painel(chave="evolucao_patrimonio"):
    priv.grafico(graficos.patrimonio(estado.recortar_serie(evolucao)),
                 width="stretch", key="patrimonio_patrimonio")

if not evolucao.empty:
    total_aportes = float(evolucao["aportes"].sum())
    total_resgates = float(evolucao["resgates"].sum())
    total_rendimentos = float(evolucao["rendimentos"].sum())

    c.linha_kpis([
        {"rotulo": "Total aportado", "valor": fmt_brl(total_aportes),
         "ajuda": "saiu da conta para investir", "pequeno": True},
        {"rotulo": "Total resgatado", "valor": fmt_brl(total_resgates),
         "ajuda": "voltou do investimento", "pequeno": True},
        {"rotulo": "Aporte líquido", "valor": fmt_brl(total_aportes - total_resgates),
         "cor": "verde" if total_aportes > total_resgates else "vermelha",
         "pequeno": True},
        {"rotulo": "Rendimentos", "valor": fmt_brl(total_rendimentos),
         "ajuda": "o dinheiro trabalhando", "cor": "verde", "pequeno": True},
    ])

    st.markdown("**Detalhe por mês**")
    tabela = evolucao.copy()
    tabela["mes_rotulo"] = tabela["mes"].map(rotulo_mes)
    priv.tabela(
        tabela[["mes_rotulo", "saldo_conta", "aportes", "resgates",
                "rendimentos", "saldo_aplicado", "patrimonio_total",
                "capital_terceiros", "patrimonio_proprio",
                "origem_saldo"]].rename(columns={
            "mes_rotulo": "Mês", "saldo_conta": "Em conta",
            "aportes": "Aportes", "resgates": "Resgates",
            "rendimentos": "Rendimentos", "saldo_aplicado": "Aplicado",
            "patrimonio_total": "Nas contas",
            "capital_terceiros": "De terceiros",
            "patrimonio_proprio": "Seu",
            "origem_saldo": "Fonte do saldo",
        }),
        hide_index=True, width="stretch", height=380,
        column_config={
            coluna: c.config_moeda(coluna) for coluna in
            ["Em conta", "Aportes", "Resgates", "Rendimentos", "Aplicado",
             "Nas contas", "De terceiros", "Seu"]
        },
    )
    st.caption(
        "**Fonte do saldo**: `informado` = você digitou · `extrato` = veio do "
        "arquivo do banco · `repetido` = não havia dado naquele mês, então "
        "repetimos o último conhecido."
    )


st.markdown("---")
st.markdown("### Corrigir um saldo")
st.caption(
    "Use quando o valor estimado não bater com o extrato ou com a corretora. "
    "O valor informado passa a ter prioridade sobre o estimado."
)

with st.form("form_saldo_patrimonio"):
    colunas = st.columns([2, 2, 2, 2])
    with colunas[0]:
        mes_corrigir = st.selectbox(
            "Mês", estado.meses(), format_func=rotulo_mes, key="patr_mes")
    with colunas[1]:
        novo_conta = st.number_input("Saldo em conta (R$)", value=0.0, step=100.0)
    with colunas[2]:
        novo_aplicado = st.number_input("Saldo aplicado (R$)", value=0.0, step=100.0)
    with colunas[3]:
        st.markdown("<br>", unsafe_allow_html=True)
        salvar_saldo = st.form_submit_button("Salvar", type="primary")

if salvar_saldo:
    calc.salvar_saldo(
        mes_corrigir,
        novo_conta if novo_conta else None,
        novo_aplicado if novo_aplicado else None,
    )
    estado.limpar_cache()
    c.recado(f"Saldo de {rotulo_mes(mes_corrigir)} atualizado.")
    st.rerun()

with st.expander("Saldo aplicado inicial (antes do primeiro mês do histórico)"):
    st.caption(
        "Se você já tinha dinheiro investido antes do período que está no "
        "sistema, informe aqui. Esse valor é o ponto de partida da estimativa."
    )
    inicial = st.number_input(
        "Saldo aplicado antes do histórico (R$)",
        value=float(banco.obter_parametro_num("saldo_aplicado_inicial", 0.0)),
        step=1000.0, key="saldo_inicial_aplicado",
    )
    if st.button("Salvar saldo inicial"):
        banco.definir_parametro("saldo_aplicado_inicial", inicial)
        estado.limpar_cache()
        c.recado("Saldo inicial salvo.")
        st.rerun()
