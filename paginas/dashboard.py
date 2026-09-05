"""
dashboard.py — A tela principal: onde eu estou e como o mes esta indo.
==============================================================================

A ORDEM DAS PERGUNTAS
---------------------
    1. Onde eu estou?          patrimonio, carteira, reserva
    2. Como foi o mes?         sobrou ou faltou
    3. Do que o mes foi feito? fixo, parcelado, variavel, cartao
    4. O que mudou?            contra o mes anterior, por categoria
    5. Para onde foi?          categoria, dia, estabelecimento
    6. E a trajetoria?         o ano, a taxa de poupanca, ano a ano

Comeca pelo patrimonio de proposito: e o numero que responde "estou bem?".
O mes responde "como estou indo", que e outra pergunta — importante, mas
segunda.

POR QUE ESTA TELA FOI REDESENHADA (2026-08-22)
-----------------------------------------------
A versao anterior tinha DEZESSEIS cartoes de indicador identicos, em quatro
fileiras de quatro, e seis titulos de secao do mesmo tamanho. Quando tudo tem
o mesmo peso visual, nada se destaca — o olho nao sabe por onde comecar.

A regra agora e:

    `destaque`      o numero que responde a pergunta da secao   (1 ou 2)
    `estatisticas`  os numeros de apoio, sem moldura            (3 a 5)
    `card_kpi`      so quando algo precisa mesmo gritar         (raro)

E as explicacoes longas viraram o "?" ao lado do rotulo, mais um bloco
recolhido no fim da pagina. Elas continuam ali — so pararam de ocupar a tela
toda vez que voce abre o app.

COMO UMA PAGINA STREAMLIT FUNCIONA
----------------------------------
E um script comum, lido de cima para baixo. Cada `st.alguma_coisa()` desenha
um pedaco na tela, na ordem em que aparece no codigo.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from financas import dados
from financas.calculos import kpis, previsao
from financas.calculos import patrimonio as calc_patrimonio
from financas.formato import fmt_num, fmt_pct, rotulo_mes, somar_meses
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado, graficos


df = estado.lancamentos()

if df.empty:
    c.cabecalho("Dashboard", "Seu painel financeiro")
    c.aviso_vazio(
        "Ainda não há lançamentos no banco.",
        "Vá em **Importar arquivos** e envie uma fatura ou um extrato para começar.",
    )
    st.stop()

mes = estado.mes_selecionado()

if not mes:
    c.aviso_vazio("Nenhum mês disponível.")
    st.stop()

painel = kpis.painel(df, mes)
resultado = painel["resultado"]
composicao = painel["composicao"]
cartao = painel["cartao"]
fixvar = painel["fixos_variaveis"]
tendencia = painel["tendencia"]

do_mes = dados.do_mes(df, mes)
mes_seguinte = somar_meses(mes, 1)
mes_anterior = somar_meses(mes, -1)

c.cabecalho("Dashboard", f"{rotulo_mes(mes)} · {resultado['quantidade']} lançamentos")

estado.seletor_de_mes_topo()

if dados.mes_e_futuro(mes):
    c.tarja(
        "Mês que ainda não começou — o que aparece aqui chegou por "
        "antecipação (a fatura do cartão). Ainda não há receita nem "
        "lançamento de extrato, então o saldo não significa nada.", "aviso")
elif dados.mes_esta_em_andamento(mes):
    hoje = date.today().isoformat()
    ultima = do_mes["data"].max() if not do_mes.empty else None
    ultima = min(ultima, hoje) if ultima else hoje
    c.tarja(
        f"Mês em andamento · dados até {ultima[8:10]}/{ultima[5:7]} — "
        f"os números ainda vão mudar.", "aviso")


c.secao("Onde eu estou")

posicao = calc_patrimonio.posicao_atual(df, mes)
conciliacao = estado.carteira_conciliacao(mes)
tem_terceiros = abs(posicao.get("capital_terceiros", 0.0)) > 0.005

itens_topo = [
    {
        "rotulo": "Seu patrimônio" if tem_terceiros else "Patrimônio",
        "valor": fmt_brl(posicao["patrimonio_proprio"]),
        "ajuda": (f"nas contas há {fmt_brl(posicao['patrimonio_total'])}, "
                  f"incluindo o que não é seu" if tem_terceiros
                  else "em conta mais aplicado"),
        "cor": "verde",
        "dica": ("Tudo que está nas suas contas menos o dinheiro de terceiros "
                 "que você administra. É o que sobra se você devolver."
                 if tem_terceiros else
                 "Saldo em conta mais o que está aplicado."),
    },
    {
        "rotulo": "Investido",
        "valor": fmt_brl(conciliacao["carteira_cadastrada"]),
        "ajuda": f"rendeu {fmt_brl(conciliacao['rendimento_apurado'])} no período",
        "dica": "A carteira na corretora, pela última posição importada.",
    },
    {
        "rotulo": "Reserva cobre",
        "valor": f"{fmt_num(posicao['meses_de_reserva'], 1)} meses",
        "ajuda": f"gastando {fmt_brl(posicao['despesa_media'])}/mês",
        "cor": ("verde" if posicao["situacao"] == "confortável"
                else "amarela" if posicao["situacao"] == "razoável"
                else "vermelha"),
        "dica": ("Por quantos meses o seu patrimônio sustenta o seu padrão de "
                 "vida sem nenhuma receita. Usa a mediana da despesa, não a "
                 "média, para um mês atípico não distorcer."),
    },
]
c.destaque(itens_topo)

with c.painel(chave="patrimonio"):
    priv.grafico(
        graficos.patrimonio(estado.recortar_serie(calc_patrimonio.evolucao(df))),
        width="stretch", key="dashboard_patrimonio")


c.secao("O mês")

prev = previsao.do_mes(df, mes)

saldo = prev["saldo_total"] if prev["tem_previsao"] else resultado["saldo"]
receita_exibida = (prev["receita_total"] if prev["tem_previsao"]
                   else resultado["receita_total"])
despesa_exibida = (prev["despesa_total"] if prev["tem_previsao"]
                   else resultado["despesa"])
taxa_mes = (saldo / receita_exibida) if receita_exibida else 0.0

# O COMPROMETIMENTO TEM DE FALAR DA MESMA BASE DOS NUMEROS AO LADO.
#
# Ele usava `resultado["comprometimento"]`, que e despesa REALIZADA sobre
# receita REALIZADA — enquanto Saldo, Receita e Despesa, nos cartoes vizinhos,
# ja vinham com previsao. Em 03/09/2026 a faixa mostrava:
#
#     Receita R$ ···· · Despesa R$ ···· · Comprometimento 120,8%
#
# Quem divide os dois numeros que estao na tela acha 76,5%, e a dica ainda
# dizia "despesa dividida por receita". Ele perguntou exatamente isso.
#
# A conta que denuncia: comprometimento e taxa de poupanca sao duas fatias da
# MESMA receita, entao tem de somar 100%. Somavam 144,3%.
comprometimento_exibido = (
    (despesa_exibida / receita_exibida) if receita_exibida else 0.0)

if prev["tem_previsao"]:
    de_onde = ("de um valor que **você informou** em Planejamento"
               if prev["origem_receita"] == "informado"
               else "da **mediana** da sua receita recorrente dos últimos "
                    "6 meses fechados")
    st.info(
        f"**Este mês ainda não acabou, então parte destes números é "
        f"previsão** — {priv.texto(previsao.rotulo(prev))}.\n\n"
        f"A previsão é sempre **o que falta**: conforme o dinheiro de verdade "
        f"entra, ela encolhe sozinha, e nada conta duas vezes. Quando o mês "
        f"fechar, sobra só o que aconteceu.\n\n"
        f"A receita prevista vem {de_onde}."
    )
    if prev["previsao_desatualizada"]:
        st.warning(
            f"**A previsão pode estar desatualizada.** No último mês fechado "
            f"entraram {fmt_brl_md(prev['recorrente_recente'])} de receita "
            f"recorrente, bem diferente do que está sendo previsto.\n\n"
            f"Se a sua renda mudou de patamar — aumento, promoção, corte — a "
            f"mediana leva cerca de **3 meses** para acompanhar. Para valer "
            f"já, informe o novo valor em **Planejamento → Salário previsto**; "
            f"para voltar ao automático, zere aquele campo."
        )

c.destaque([
    {
        "rotulo": "Saldo do mês",
        "valor": fmt_brl(saldo),
        "ajuda": (f"guardou {fmt_pct(taxa_mes)} do que entrou"
                  + (" · com previsão" if prev["tem_previsao"] else "")),
        "cor": "verde" if saldo >= 0 else "vermelha",
        "dica": "Receita menos despesa. Não inclui o que foi para investimento.",
    },
])

c.estatisticas([
    {
        "rotulo": "Receita",
        "valor": fmt_brl(receita_exibida),
        "ajuda": (
            f"{fmt_brl(prev['receita_prevista'])} ainda previstos"
            if prev["receita_prevista"] > 0.01
            else f"{fmt_brl(resultado['receita_extraordinaria'])} extraordinária"
            if resultado["tem_extraordinaria"] else "toda recorrente"
        ),
    },
    {
        "rotulo": "Despesa",
        "valor": fmt_brl(despesa_exibida),
        "ajuda": (f"{fmt_brl(prev['despesa_prevista'])} ainda previstos"
                  if prev["despesa_prevista"] > 0.01
                  else f"{fmt_pct(fixvar['pct_fixo'])} é gasto fixo"),
    },
    {
        "rotulo": "Comprometimento",
        "valor": fmt_pct(comprometimento_exibido),
        "ajuda": ("da receita do mês, com previsão" if prev["tem_previsao"]
                  else "da receita foi consumida"),
        "cor": (
            "vermelha" if comprometimento_exibido > 1
            else "amarela" if comprometimento_exibido > 0.85
            else None
        ),
        "dica": "A Despesa dividida pela Receita, os dois cartões ao lado. "
                "Acima de 100% você gastou mais do que entrou. Com o mês em "
                "andamento, os três incluem a previsão — e este mais o "
                "«guardou» do saldo somam 100%.",
    },
    {
        "rotulo": "Fatura do cartão",
        "valor": fmt_brl(cartao["total_mes"]),
        "ajuda": f"{fmt_pct(cartao['pct_da_despesa'])} da despesa",
    },
])

if resultado["tem_extraordinaria"]:
    saldo_recorrente = resultado["saldo_recorrente"]
    c.nota(
        f"Este mês teve <strong>{fmt_brl(resultado['receita_extraordinaria'])}"
        f"</strong> de receita extraordinária (PLR, indenização ou similar). "
        f"Sem ela, o saldo seria <strong>{fmt_brl(saldo_recorrente)}</strong> — "
        f"{'ainda positivo' if saldo_recorrente >= 0 else 'negativo'}. "
        f"É esse o número que vale para planejar os próximos meses."
    )


c.secao("Do que o mês foi feito",
        "Separa o que você decidiu gastar agora do que já estava contratado. "
        "Duas pessoas com o mesmo gasto total têm liberdades bem diferentes.")

c.estatisticas([
    {
        "rotulo": "Gasto novo",
        "valor": fmt_brl(composicao["gasto_novo"]),
        "ajuda": "decisões deste mês",
        "dica": "Inclui a primeira parcela de uma compra parcelada — a decisão "
                "de comprar foi tomada agora.",
    },
    {
        "rotulo": "Parcelas herdadas",
        "valor": fmt_brl(composicao["parcelas_herdadas"]),
        "ajuda": "de compras anteriores",
    },
    {
        "rotulo": "Fixo do mês",
        "valor": fmt_brl(fixvar["fixo"]),
        "ajuda": "aluguel, contas, assinaturas",
        "dica": "O que se repete todo mês, pago ou ainda por pagar. Os meses "
                "seguintes ficam em **Os próximos meses**, mais abaixo.",
    },
    {
        "rotulo": "Novo comprometimento",
        "valor": fmt_brl(composicao["novo_comprometimento"]),
        "ajuda": "dívida futura criada agora",
        "cor": "vermelha" if composicao["novo_comprometimento"] > 0 else None,
        "dica": "Soma das parcelas futuras geradas pelas compras parceladas "
                "deste mês. É o quanto de liberdade você abriu mão.",
    },
])

col_a, col_b = st.columns([1, 1], gap="medium")
with col_a:
    with c.painel("Fixo, parcelado ou escolha do mês"):
        priv.grafico(
            graficos.rosca_fixo_parcelado_variavel(
                fixvar["fixo"], fixvar["parcelado"],
                max(0.0, fixvar["variavel"] - fixvar["parcelado"]),
            ),
            width="stretch", key="dashboard_rosca_fixo_parcelado_variavel")
with col_b:
    with c.painel("Da receita ao saldo"):
        priv.grafico(
            graficos.cascata_do_mes(
                resultado["receita_recorrente"],
                resultado["receita_extraordinaria"],
                fixvar["fixo"],
                fixvar["parcelado"],
                max(0.0, fixvar["variavel"] - fixvar["parcelado"]),
            ),
            width="stretch", key="dashboard_cascata_do_mes")


if prev["futuro"] and prev["despesa_realizada"] <= 0.01:
    st.caption(
        f"**A comparação com {rotulo_mes(mes_anterior)} aparece quando o mês "
        f"começar.** Comparar um mês sem nenhum gasto realizado com a média "
        f"dos anteriores só produziria −100% em tudo."
    )
else:
    c.secao("O que mudou", f"Comparação com {rotulo_mes(mes_anterior)}, por grande "
                       f"categoria. Ordenado pelo tamanho da mudança, não pelo "
                       f"tamanho do gasto.")

    variacao = tendencia["variacao_3m"]
    c.estatisticas([
        {
            "rotulo": "Média 3 meses",
            "valor": fmt_brl(tendencia["despesa_media_3m"]),
            "ajuda": f"{min(3, tendencia['meses_considerados'])} meses anteriores",
        },
        {
            "rotulo": "Este mês vs média",
            "valor": fmt_pct(variacao, 1),
            "ajuda": ("acima do normal" if variacao > 0.05
                      else "abaixo do normal" if variacao < -0.05
                      else "dentro do normal"),
            "cor": ("vermelha" if variacao > 0.15
                    else "verde" if variacao < 0 else "amarela"),
        },
        {
            "rotulo": f"Previsão {rotulo_mes(mes_seguinte)}",
            "valor": fmt_brl(tendencia["previsao_proximo"]),
            "ajuda": "média 3M + parcelas contratadas",
            "dica": "Não é uma projeção sofisticada: é a média recente mais o que "
                    "já se sabe que vai cair. Serve para não ser pego de surpresa.",
        },
        {
            "rotulo": "Parcelamentos ativos",
            "valor": fmt_num(cartao["n_parcelamentos"]),
            "ajuda": f"maior: {fmt_brl(cartao['maior_parcelamento'])}",
        },
    ])

    with c.painel(chave="variacoes_do_mes"):
        priv.grafico(
            graficos.variacoes_do_mes(kpis.variacao_por_categoria(df, mes)),
            width="stretch", key="dashboard_variacoes_do_mes")


c.secao("Para onde o dinheiro foi",
        "Cada real do mês em uma linha, com nome e situação. O total daqui é "
        "o mesmo número que aparece em Despesa, lá em cima.")

composicao_mes = previsao.composicao_do_mes(df, mes)
resumo_comp = previsao.resumo_da_composicao(composicao_mes)

if resumo_comp["a_vir"] > 0.01:
    st.info(
        f"**{fmt_brl_md(resumo_comp['a_vir'])} deste mês ainda não "
        f"aconteceram** e estão somados abaixo: contas fixas que ainda vão "
        f"vencer e parcelas já contratadas. Conforme o dinheiro de verdade "
        f"entra, cada linha vira **lançado** sem mudar o total.\n\n"
        f"**Só entra aqui o que já está contratado.** Gasto variável — mercado, "
        f"comida, uma compra que você ainda vai decidir fazer — não está nesta "
        f"conta, então o saldo previsto é o seu **melhor caso**. A projeção com "
        f"a sua média de gasto variável está em "
        f"**Planejamento → Projeção de caixa**."
    )

cores_gc = estado.cores_grande_categoria()
cores_cat = estado.cores_categoria()

aba1, aba2, aba3, aba4, aba5 = st.tabs(
    ["Por grande categoria", "Item a item", "Por categoria", "Dia a dia",
     "Onde você mais gastou"]
)

with aba1:
    col1, col2 = st.columns([1, 1], gap="medium")
    por_gc = previsao.composicao_por(composicao_mes, "grande_categoria")
    with col1:
        with c.painel(chave="pizza_grande_categoria"):
            priv.grafico(
                graficos.pizza_por_grande_categoria(por_gc, cores_gc),
                width="stretch", key="dashboard_pizza_por_grande_categoria")
    with col2:
        if not por_gc.empty:
            tabela = por_gc.copy()
            tabela["percentual"] = tabela["percentual"] * 100
            priv.tabela(
                tabela.rename(columns={
                    "grande_categoria": "Grande categoria",
                    "total": "Total",
                    "quantidade": "Nº",
                    "percentual": "% do mês",
                }),
                hide_index=True,
                width="stretch",
                column_config={
                    "Total": c.config_moeda("Total"),
                    "% do mês": c.config_percentual("% do mês"),
                },
            )

with aba2:
    if composicao_mes.empty:
        c.aviso_vazio("Nada neste mês ainda.")
    else:
        c.estatisticas([
            {
                "rotulo": "Já lançado",
                "valor": fmt_brl(resumo_comp["realizado"]),
                "ajuda": "aconteceu de verdade",
            },
            {
                "rotulo": "Ainda vai cair",
                "valor": fmt_brl(resumo_comp["a_vir"]),
                "ajuda": "fixo e parcela contratada",
            },
            {
                "rotulo": "Sai pelo cartão",
                "valor": fmt_brl(resumo_comp["cartao"]),
                "ajuda": "cai na fatura",
            },
            {
                "rotulo": "Sai pela conta",
                "valor": fmt_brl(resumo_comp["conta"]),
                "ajuda": "boleto, Pix, débito",
            },
        ])

        visao = composicao_mes.copy()
        visao["item"] = visao.apply(
            lambda l: c.rotulo_com_fixo(l["fixo"], l["item"]), axis=1)
        priv.tabela(
            visao[["item", "categoria", "forma", "valor", "situacao"]].rename(
                columns={"item": "Item", "categoria": "Categoria",
                         "forma": "Forma", "valor": "Valor",
                         "situacao": "Situação"}),
            hide_index=True,
            width="stretch",
            column_config={"Valor": c.config_moeda("Valor")},
        )
        st.caption(
            f"**{resumo_comp['linhas']} linhas somam "
            f"{fmt_brl_md(resumo_comp['total'])}** — o mesmo valor do cartão "
            f"*Despesa*. Quando um gasto fixo é pago, ele aparece aqui com a "
            f"descrição do banco e o nome do item na frente, para você seguir "
            f"a mesma linha de um mês para o outro."
        )

with aba3:
    with c.painel(chave="barras_por_categoria"):
        priv.grafico(
            graficos.barras_por_categoria(
                previsao.composicao_por(composicao_mes, "categoria"),
                "categoria", cores_cat),
            width="stretch", key="dashboard_barras_por_categoria")

with aba4:
    with c.painel(chave="barras_por_dia"):
        priv.grafico(graficos.barras_por_dia(do_mes),
                     width="stretch", key="dashboard_barras_por_dia")
    with c.painel(chave="heatmap_dia_semana"):
        priv.grafico(graficos.heatmap_dia_semana(df),
                     width="stretch", key="dashboard_heatmap_dia_semana")

with aba5:
    with c.painel(chave="top_estabelecimentos"):
        priv.grafico(graficos.top_estabelecimentos(do_mes),
                     width="stretch", key="dashboard_top_estabelecimentos")


c.secao("A trajetória")

tabela_taxa = kpis.taxa_de_poupanca(df)
taxa_agregada = kpis.taxa_de_poupanca_agregada(tabela_taxa)
tabela_anos = kpis.comparativo_anual(df)

c.destaque([
    {
        "rotulo": "Taxa de poupança",
        "valor": fmt_pct(taxa_agregada),
        "ajuda": (f"de tudo que entrou em "
                  f"{int((~tabela_taxa['parcial']).sum())} meses fechados"),
        "cor": "verde" if taxa_agregada > 0.15 else "amarela",
        "dica": "Soma dos saldos dividida pela soma das receitas. Não é a "
                "média das taxas mensais: a receita oscila muito, e uma média "
                "de percentuais trataria um mês magro como se pesasse igual a "
                "um mês gordo.",
    },
])

with c.painel("Quanto sobrou, mês a mês"):
    priv.grafico(graficos.taxa_de_poupanca(estado.recortar_serie(tabela_taxa)),
                 width="stretch", key="dashboard_taxa_de_poupanca")

with c.painel("Ano a ano"):
    priv.grafico(graficos.comparativo_anual(tabela_anos),
                 width="stretch", key="dashboard_comparativo_anual")

with c.painel("Receita × despesa"):
    rateado = kpis.serie_rateando_plr(df)
    aba_entrada, aba_rateado = st.tabs(["Como entrou", "PLR rateada no ano"])

    with aba_entrada:
        priv.grafico(
            graficos.historico_receita_despesa(
                estado.recortar_serie(dados.por_mes(df)), n_meses=None),
            width="stretch", key="dashboard_historico_receita_despesa")
        st.caption("O que caiu na conta, no mês em que caiu. O mês do PLR "
                   "aparece como um pico.")

    with aba_rateado:
        priv.grafico(graficos.receita_rateada(
                            estado.recortar_serie(rateado), n_meses=None),
                        width="stretch", key="dashboard_receita_rateada")
        futuro = float(rateado["rateio_futuro"].iloc[0]) if not rateado.empty else 0.0
        st.caption(
            "O mesmo dinheiro, diluído pelos **12 meses do ano em que caiu** — a "
            "remuneração de verdade, sem o susto do mês do bônus. Todo mês do "
            "mesmo ano recebe a mesma parcela, então dá para comparar janeiro com "
            "julho sem que um deles carregue sobra do ano anterior."
            + (f" {fmt_brl(futuro)} cai em meses que não estão na base e não "
               f"aparecem aqui." if futuro > 0.005 else "")
        )
        st.caption(
            "**Ano em andamento sobe quando a segunda PLR chega** — e sobe para o "
            "ano inteiro de uma vez, porque a parcela é do ano, não do mês."
        )

serie_do_ano = dados.por_mes(df)
serie_do_ano = serie_do_ano[serie_do_ano["mes"].str.startswith(mes[:4])]
with c.painel("Saldo acumulado no ano"):
    priv.grafico(graficos.linha_saldo_acumulado(serie_do_ano),
                 width="stretch", key="dashboard_linha_saldo_acumulado")

with c.painel("Evolução por grande categoria"):
    priv.grafico(
        graficos.evolucao_por_grande_categoria(
            estado.recortar_lancamentos(df), None, cores_gc),
        width="stretch", key="dashboard_evolucao_por_grande_categoria")

with st.expander(f"O ano de {mes[:4]}, mês a mês e por trimestre"):
    anos = kpis.anos_disponiveis(df)
    ano_atual = mes[:4]
    ano = st.selectbox(
        "Ano", anos,
        index=anos.index(ano_atual) if ano_atual in anos else 0,
        key="dashboard_ano",
    )
    resumo = kpis.resumo_anual(df, ano)
    tabela_ano = resumo[[
        "rotulo", "receita", "receita_extra", "despesa", "saldo",
        "acumulado", "comprometimento",
    ]].copy()
    tabela_ano["comprometimento"] = tabela_ano["comprometimento"] * 100

    priv.tabela(
        tabela_ano.rename(columns={
            "rotulo": "Mês",
            "receita": "Receita",
            "receita_extra": "Extraordinária",
            "despesa": "Despesa",
            "saldo": "Saldo",
            "acumulado": "Acumulado",
            "comprometimento": "Comprom.",
        }),
        hide_index=True, width="stretch",
        column_config={
            "Receita": c.config_moeda("Receita"),
            "Extraordinária": c.config_moeda("Extraordinária"),
            "Despesa": c.config_moeda("Despesa"),
            "Saldo": c.config_moeda("Saldo"),
            "Acumulado": c.config_moeda("Acumulado"),
            "Comprom.": c.config_percentual("Comprom.", "despesa ÷ receita"),
        },
    )
    st.caption(
        "As linhas de trimestre somam os três meses acima delas. "
        "A coluna Acumulado soma os saldos desde janeiro."
    )


with st.expander("Entenda esta tela"):
    st.markdown(
        """
**Onde eu estou** — o patrimônio é o saldo em conta mais o que está aplicado.
Quando existe dinheiro de terceiros sob sua gestão, o número em destaque é o
que sobra depois de devolver; o total das contas aparece na legenda. A reserva
é medida em **meses de despesa**, porque R$ 100 mil significam coisas
diferentes para quem gasta R$ 3 mil e para quem gasta R$ 15 mil por mês.

**Gasto novo × parcela herdada** — a diferença entre o que você decidiu agora
e o que já estava contratado. Dois meses com a mesma despesa total podem ter
liberdades opostas: um deles você consegue cortar, o outro já foi decidido.

**O que mudou** — comparar com a média de 3 meses diz o tamanho da diferença;
comparar categoria a categoria diz **onde** ela aconteceu, que é o que permite
fazer alguma coisa a respeito.

**Dia a dia** — cada barra é um dia. Concentração no começo do mês costuma ser
conta fixa; concentração no fim de semana costuma ser gasto variável. O mapa
de calor mostra hábito, não evento.

**Taxa de poupança** — quanto por cento da receita sobrou. As barras são o mês,
a linha é a média de 3 meses. Meses em andamento ficam de fora: eles têm a
despesa contratada mas ainda não a receita inteira, e sempre pareceriam
péssimos.

**Ano a ano** — em médias mensais, não em totais. Os anos têm tamanhos
diferentes aqui (2024 começa em abril), e comparar totais faria um ano parecer
fraco por um motivo que não tem nada a ver com dinheiro.
        """
    )

c.rodape_atualizado(len(df), mes)
