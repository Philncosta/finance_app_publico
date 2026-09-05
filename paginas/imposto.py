"""
imposto.py — o que voce precisa para declarar o Imposto de Renda.
==============================================================================

ESTA TELA ORGANIZA E CONFERE. ELA NAO APURA O SEU IMPOSTO.
----------------------------------------------------------
Nao emite DARF, nao apura ganho de capital, nao substitui contador. Ela junta
o que este app sabe de um ano inteiro e — o mais importante — **mostra onde
falta dado**.

A UNICA EXCECAO E A ABA "PREVIDENCIA (PGBL)", e ela confirma a regra: ali o
imposto e calculado, mas so depois que VOCE digita o bruto do informe. Ela nao
adivinha o dado que falta — ela pede.

POR QUE ELA E UMA TELA E NAO UMA ABA DE INVESTIMENTOS
-----------------------------------------------------
O IR cruza RENDA (salario, PLR) com PATRIMONIO (a carteira em 31/12). Nenhuma
das duas telas existentes cobre as duas metades.

AS TRES COISAS QUE ELA EXISTE PARA DIZER
----------------------------------------
1. A PLR nao se soma ao salario — ficha separada, imposto definitivo.
2. O app ve o LIQUIDO; a declaracao usa o BRUTO do informe.
3. A carteira no exterior nao tem informe — ali voce esta sozinho.

Cada uma dessas aparece na tela em destaque, nao em nota de rodape.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from financas import banco
from financas.calculos import imposto as calc
from financas.calculos import investimentos as inv
from financas.calculos import previdencia as prev
from financas.formato import fmt_num, fmt_pct, rotulo_mes
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import graficos
from ui import estado

df = estado.lancamentos()

c.cabecalho("Imposto de renda", "O que declarar, onde declarar, e o que falta")
c.mostrar_recado()

anos = calc.anos_disponiveis(df)
if not anos:
    c.aviso_vazio("Nenhum lançamento na base ainda.",
                  "Importe seus extratos na tela **Importar arquivos**.")
    st.stop()

col_ano, col_aviso = st.columns([1, 3], gap="medium")
with col_ano:
    ano = st.selectbox("Ano-calendário", anos, key="imposto_ano")
with col_aviso:
    st.caption(
        "**Ano-calendário** é o ano em que o dinheiro entrou — a declaração "
        "dele é entregue no ano seguinte. O de 2026 ainda está em andamento; "
        "olhar para ele agora serve para você chegar em 2027 com tudo pronto."
    )

resumo = calc.resumo(df, ano)

c.nota(
    "Os valores desta tela são <b>líquidos</b> — o que caiu na conta, já sem "
    "IRRF e sem INSS. A declaração usa o valor <b>bruto</b>, que está no "
    "informe de rendimentos da empresa e é maior. Use esta tela para "
    "<b>conferir</b> o informe, nunca para substituí-lo."
)

aba_renda, aba_bens, aba_retido, aba_pgbl, aba_como = st.tabs(
    ["O que entrou", "Bens e direitos", "Imposto já retido",
     "Previdência (PGBL)", "Como declarar"]
)

with aba_renda:
    rendimentos = resumo["rendimentos"]
    if rendimentos.empty:
        c.aviso_vazio(f"Nenhuma receita registrada em {ano}.")
    else:
        por_ficha = resumo["por_ficha"]
        c.linha_kpis([
            {"rotulo": "Tributável",
             "valor": fmt_brl(por_ficha.get(calc.FICHA_TRIBUTAVEL, 0.0)),
             "ajuda": "entra na tabela progressiva", "cor": "azul"},
            {"rotulo": "Tributação exclusiva",
             "valor": fmt_brl(por_ficha.get(calc.FICHA_EXCLUSIVA, 0.0)),
             "ajuda": "imposto já foi definitivo"},
            # Este cartao faltava, e o dinheiro isento ficava so na tabela de
            # baixo: os tres numeros de cima nao somavam o total. Um resumo que
            # nao fecha ensina a desconfiar do resumo.
            {"rotulo": "Isento",
             "valor": fmt_brl(por_ficha.get(calc.FICHA_ISENTA, 0.0)),
             "ajuda": "declara e não paga"},
            {"rotulo": "Precisa de triagem",
             "valor": fmt_brl(por_ficha.get(calc.FICHA_TRIAGEM, 0.0)),
             "ajuda": "só você sabe o que é",
             "cor": "vermelha" if por_ficha.get(calc.FICHA_TRIAGEM) else None},
        ])

        plr = rendimentos[rendimentos["categoria"] == "PLR"]
        if not plr.empty:
            valor_plr = float(plr["valor"].sum())
            c.nota(
                f"<b>Sua PLR de {ano} foi "
                f"{fmt_brl(valor_plr)} — e ela NÃO se soma ao salário.</b>"
                f"<br><br>"
                f"A participação nos lucros tem tabela própria e imposto "
                f"definitivo na fonte. Na declaração ela vai em "
                f"<b>«Rendimentos sujeitos à tributação exclusiva/definitiva»</b>, "
                f"item <b>11 — Participação nos lucros ou resultados</b>."
                f"<br><br>"
                f"Somar ao rendimento tributável empurraria "
                f"{fmt_brl(valor_plr)} para a tabela progressiva e faria você "
                f"pagar imposto indevido."
                f"<br><br>"
                f"<b>E a PLR também tem IRRF retido na fonte</b>, por uma "
                f"tabela própria — separada da tabela do salário. A ficha pede "
                f"<b>dois números</b>: o valor <b>bruto</b> num campo e o "
                f"<b>imposto retido</b> em outro. Os {fmt_brl(valor_plr)} acima "
                f"são o <b>líquido</b> que caiu na conta, então os dois campos "
                f"vêm do informe da empresa — não daqui."
            )

        st.markdown("**Cada receita e onde ela entra**")
        visao = rendimentos[["categoria", "valor", "lancamentos", "ficha",
                             "codigo"]].copy()
        priv.tabela(
            visao.rename(columns={
                "categoria": "Categoria", "valor": "Valor líquido",
                "lancamentos": "Lançamentos", "ficha": "Ficha da declaração",
                "codigo": "Item",
            }),
            hide_index=True, width="stretch",
            column_config={"Valor líquido": c.config_moeda(
                "Valor líquido", "o que caiu na conta, não o bruto do informe")},
        )

        for _, linha in rendimentos.iterrows():
            if linha["ficha"] == calc.FICHA_TRIAGEM:
                st.warning(
                    f"**{linha['categoria']} — {fmt_brl(linha['valor'])} em "
                    f"{linha['lancamentos']} lançamento(s).** {linha['nota']}\n\n"
                    f"Abra a tela **Lançamentos**, filtre por esta categoria "
                    f"e veja linha a linha. Reembolso e dinheiro de terceiros "
                    f"não são renda e não entram na declaração como tal."
                )

with aba_bens:
    bens = resumo["bens"]
    if bens.empty:
        c.aviso_vazio(
            f"Nenhuma posição registrada em dezembro de {ano}.",
            "Importe o arquivo de posição da corretora na tela **Importar**.",
        )
    else:
        faltando = resumo["faltando"]
        custo_conhecido = float(
            bens[bens["fonte_custo"].isin(["extrato", "manual"])]["custo"]
            .fillna(0).sum())

        c.linha_kpis([
            {"rotulo": f"Papéis em 31/12/{ano}", "valor": fmt_num(len(bens), 0),
             "cor": "azul"},
            {"rotulo": "Custo conhecido", "valor": fmt_brl(custo_conhecido),
             "ajuda": "só o que tem origem confiável"},
            {"rotulo": "Sem custo confiável", "valor": fmt_num(len(faltando), 0),
             "ajuda": "precisa da nota ou do informe",
             "cor": "vermelha" if len(faltando) else "verde"},
        ])

        previa = sorted({m for m in bens["mes_do_dado"] if m and m != f"{ano}-12"})
        if previa:
            st.info(
                f"**Isto é uma prévia, não a posição de 31/12/{ano}.** "
                f"Dezembro ainda não aconteceu, então o app está mostrando a "
                f"foto mais recente que tem "
                f"({', '.join(rotulo_mes(m) for m in previa)}). Serve para "
                f"você se organizar agora; o número da declaração só existe "
                f"depois do fechamento do ano."
            )

        c.nota(
            "A ficha <b>Bens e Direitos</b> pede o <b>custo de aquisição</b> — "
            "o que você pagou — e nunca o valor de mercado. Um título que "
            "você comprou por R$ 20.000 e hoje vale R$ 24.000 continua "
            "entrando como R$ 20.000; a valorização só vira imposto quando "
            "você vende.<br><br>"
            "Por isso a coluna <b>Custo</b> é a que importa aqui. O valor de "
            "mercado está junto só para você reconhecer o papel."
        )

        brasil = bens[~bens["exterior"]]
        exterior = bens[bens["exterior"]]

        def _tabela_bens(tabela: pd.DataFrame, chave: str) -> None:
            visao = tabela[["nome", "classe", "quantidade", "custo",
                            "fonte_custo", "valor_mercado"]].copy()
            visao["fonte_custo"] = visao["fonte_custo"].map({
                "extrato": "extrato da corretora",
                "manual": "você informou",
                "valor_aplicado": "⚠️ coluna que muda sozinha",
            })
            priv.tabela(
                visao.rename(columns={
                    "nome": "Aplicação", "classe": "Classe",
                    "quantidade": "Quantidade", "custo": "Custo",
                    "fonte_custo": "De onde veio o custo",
                    "valor_mercado": "Valor de mercado",
                }),
                hide_index=True, width="stretch", key=chave,
                column_config={
                    "Custo": c.config_moeda(
                        "Custo", "vazio = não sei, e isso é diferente de zero"),
                    "Valor de mercado": c.config_moeda(
                        "Valor de mercado", "NÃO vai na declaração"),
                },
            )

        if not brasil.empty:
            st.markdown("**No Brasil (XP)**")
            _tabela_bens(brasil, "imposto_bens_brasil")
            st.caption(
                "Para estes existe **informe de rendimentos da corretora**, e "
                "a Receita exige que você use o documento oficial. O que está "
                "aqui serve para conferir se o informe bate com a sua conta."
            )

        if not exterior.empty:
            st.markdown("**No exterior (XP Global)**")
            _tabela_bens(exterior, "imposto_bens_exterior")
            st.error(
                "**Para a conta internacional não existe informe de "
                "rendimentos — ninguém vai te mandar.** Você declara por conta "
                "própria, e a reconstrução que este app fez (quantidade × "
                "cotação, conferida contra o seu print) é a única fonte que "
                "você tem.\n\n"
                "Desde a Lei 14.754/2023, aplicação financeira no exterior é "
                "tributada a **15%**, apurada na declaração anual — e **sem a "
                "faixa de isenção** que existe para ações brasileiras. "
                "Prejuízo também precisa ser declarado: é ele que compensa "
                "ganho futuro."
            )

        if not faltando.empty:
            st.markdown("---")
            st.markdown("### O que falta para esta ficha ficar pronta")
            st.warning(
                f"**{len(faltando)} de {len(bens)} papéis estão sem custo "
                f"confiável.** Sem isso a ficha Bens e Direitos não sai "
                f"correta.\n\n"
                f"Dois casos diferentes caem aqui: os que **não têm custo "
                f"nenhum**, e os que têm um custo vindo da coluna *Valor "
                f"aplicado* da corretora — a mesma que já se provou mudar de "
                f"um mês para o outro sem você movimentar nada. Ela não serve "
                f"de prova."
            )

            st.markdown("**Informe o custo que você pagou**")
            st.caption(
                "Onde encontrar: nota de corretagem, informe de rendimentos "
                "da XP, ou o extrato do mês da compra. Corretagem, "
                "liquidação e emolumentos **entram no custo**."
            )

            editor = faltando[["nome", "quantidade", "valor_mercado",
                               "custo"]].copy()
            meses_destino = list(faltando["mes_do_dado"])
            editor["custo"] = editor["custo"].astype("float64")
            editado = priv.editor(
                editor.rename(columns={
                    "nome": "Aplicação", "quantidade": "Quantidade",
                    "valor_mercado": "Valor de mercado", "custo": "Custo pago",
                }),
                hide_index=True, width="stretch", key="imposto_editor_custo",
                disabled=["Aplicação", "Quantidade", "Valor de mercado"],
                column_config={
                    "Valor de mercado": c.config_moeda("Valor de mercado"),
                    "Custo pago": st.column_config.NumberColumn(
                        "Custo pago", format="%.2f", min_value=0.0,
                        help="deixe vazio se ainda não souber"),
                },
            )

            col_salvar, col_extrato = st.columns([1, 1], gap="medium")
            with col_salvar:
                if st.button("Salvar os custos informados", width="stretch",
                             key="imposto_salvar_custo"):
                    gravados = 0
                    recusados: list[str] = []
                    for posicao_linha, (_, original) in enumerate(
                            faltando.iterrows()):
                        novo = editado.iloc[posicao_linha]["Custo pago"]
                        antigo = original["custo"]
                        mudou = (pd.notna(novo)
                                 and (pd.isna(antigo) or float(novo) != float(antigo)))
                        if not mudou:
                            continue
                        papel = banco.consultar_um(
                            "SELECT id FROM investimentos WHERE nome = ?",
                            (original["nome"],))
                        if papel:
                            destino = meses_destino[posicao_linha]
                            if calc.salvar_custo(int(papel["id"]), destino,
                                                 float(novo), fonte="manual"):
                                gravados += 1
                            else:
                                recusados.append(str(original["nome"]))
                    estado.limpar_cache()
                    for nome_recusado in recusados:
                        st.error(
                            f"**{nome_recusado}: não gravei.** Não existe foto "
                            f"de saldo no mês de destino, então não há onde "
                            f"guardar o custo. Importe a posição da corretora "
                            f"daquele mês primeiro."
                        )
                    if gravados:
                        c.recado(f"{gravados} custo(s) gravado(s).")
                        st.rerun()
                    elif not recusados:
                        st.info("Nenhum valor novo para gravar.")

            with col_extrato:
                inicio_extrato, _ = inv.periodo_do_extrato_da_corretora()
                alcanca = bool(inicio_extrato and f"{ano}-12" >= inicio_extrato)
                if st.button("Tentar buscar no extrato", width="stretch",
                             key="imposto_buscar_custo", disabled=not alcanca):
                    achados = 0
                    destinos = list(faltando["mes_do_dado"])
                    for posicao_linha, (_, original) in enumerate(
                            faltando.iterrows()):
                        papel = banco.consultar_um(
                            "SELECT id FROM investimentos WHERE nome = ?",
                            (original["nome"],))
                        if not papel:
                            continue
                        destino = destinos[posicao_linha]
                        valor = calc.custo_pelo_extrato(int(papel["id"]), destino)
                        if valor and calc.salvar_custo(int(papel["id"]), destino,
                                                       valor, fonte="extrato"):
                            achados += 1
                    estado.limpar_cache()
                    if achados:
                        c.recado(f"{achados} custo(s) reconstruído(s) das "
                                   f"linhas de compra do extrato.")
                        st.rerun()
                    else:
                        st.info(
                            "Nada encontrado. O extrato da corretora só "
                            "nomeia fundos; para Tesouro Direto ele escreve "
                            "apenas «COMPRA TESOURO DIRETO CLIENTES», sem "
                            "dizer qual título."
                        )
                if not alcanca:
                    st.caption(
                        f"O extrato da corretora só começa em "
                        f"{rotulo_mes(inicio_extrato) if inicio_extrato else '—'}. "
                        f"Para {ano} não há linha de compra para consultar."
                    )

with aba_retido:
    retido = resumo["retido"]
    if retido.empty:
        c.aviso_vazio(
            f"Nenhum imposto retido registrado em {ano}.",
            "Estes valores vêm do extrato da corretora, importado na tela "
            "**Importar arquivos**.",
        )
    else:
        c.linha_kpis([
            {"rotulo": "Definitivo",
             "valor": fmt_brl(abs(resumo["total_retido_definitivo"])),
             "ajuda": "já acabou, não volta", "cor": "azul"},
            {"rotulo": "Antecipação (come-cotas)",
             "valor": fmt_brl(abs(resumo["total_retido_antecipacao"])),
             "ajuda": "adiantamento do resgate futuro"},
        ])
        c.nota(
            "Os dois somam dinheiro que saiu, mas significam coisas "
            "diferentes.<br><br>"
            "<b>Definitivo</b> é o IRRF sobre o cupom do Tesouro Direto: "
            "acabou ali, não gera restituição nem imposto a pagar depois.<br>"
            "<b>Antecipação</b> é o come-cotas, cobrado em maio e novembro nos "
            "fundos — ele adianta parte do imposto que você pagaria no "
            "resgate.<br><br>"
            "Somar os dois num número só faria parecer que você pagou imposto "
            "a mais do que pagou."
        )
        visao = retido.copy()
        visao["especie"] = visao["especie"].map({
            "definitivo": "definitivo (cupom de Tesouro)",
            "antecipacao": "antecipação (come-cotas)",
        })
        priv.tabela(
            visao.rename(columns={
                "data": "Data", "descricao": "Descrição",
                "valor": "Valor", "especie": "Espécie"}),
            hide_index=True, width="stretch",
            column_config={"Valor": c.config_moeda("Valor")},
        )

with aba_pgbl:
    st.markdown("### PGBL: quanto dá para deduzir, e o que isso custa depois")

    c.nota(
        "Esta é a única aba que <b>calcula imposto</b> — e ela só consegue "
        "porque você traz o número que falta. O teto de 12% é sobre a renda "
        "<b>bruta tributável</b>, e este app só enxerga o líquido. Os campos "
        "abaixo vêm do seu <b>informe de rendimentos</b>, uma vez por ano."
        "<br><br>"
        "Ela não recomenda plano, corretora nem produto. Faz a aritmética do "
        "imposto sobre os seus números e mostra os dois lados dela."
    )

    tabela_do_ano = prev.tabela_do_ano(ano)
    if tabela_do_ano is None:
        c.aviso_vazio(
            f"Não tenho a tabela do imposto de {ano}.",
            "As tabelas cadastradas são **"
            + "**, **".join(prev.anos_com_tabela())
            + "**. Usar a tabela de outro ano daria um número plausível e "
              "errado — e ninguém perceberia.")
    else:
        dados_ir = prev.dados_do_ano(ano)

        salario_liquido = 0.0
        if not resumo["rendimentos"].empty:
            do_salario = resumo["rendimentos"][
                resumo["rendimentos"]["categoria"] == "Salário"]
            if not do_salario.empty:
                salario_liquido = float(do_salario["valor"].sum())

        sugestao_saude = prev.gasto_por_grande_categoria(df, ano, "Saúde")
        sugestao_educacao = prev.gasto_por_grande_categoria(df, ano, "Educação")

        with st.expander(
                f"Os números do informe de {ano}"
                + ("" if dados_ir["preenchido"] else "  ·  **ainda em branco**"),
                expanded=not dados_ir["preenchido"] and not priv.ocultando()):

            if priv.ocultando():
                st.caption(
                    "Os valores estão ocultos, e o formulário do informe é feito "
                    "de campos editáveis — não há como mascarar um campo sem "
                    "que a máscara vire o valor salvo. Clique em **Mostrar "
                    "valores** na barra lateral para preencher ou corrigir."
                )
            else:

                st.caption(
                    f"O app viu **{fmt_brl_md(salario_liquido)}** de salário "
                    f"líquido em {ano}. O bruto do informe é maior — ele inclui "
                    f"o INSS e o IRRF que foram descontados antes de o dinheiro "
                    f"cair na conta. **Não some PLR nem 13º:** os dois têm "
                    f"tributação exclusiva e ficam de fora da base dos 12%."
                )

                with st.form("form_ir_ano"):
                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        campo_bruto = st.number_input(
                            "Rendimento bruto tributável (R$)", min_value=0.0,
                            value=float(dados_ir.get("rendimento_bruto") or 0.0),
                            step=1000.0,
                            help="Salário + férias, do informe. Sem PLR e sem 13º.")
                        campo_inss = st.number_input(
                            "INSS descontado no ano (R$)", min_value=0.0,
                            value=float(dados_ir.get("inss") or 0.0), step=100.0)
                        campo_irrf = st.number_input(
                            "IRRF já retido (R$)", min_value=0.0,
                            value=float(dados_ir.get("irrf_retido") or 0.0),
                            step=100.0,
                            help="Só o retido sobre o salário. O da PLR é outro.")
                    with col_b:
                        campo_dependentes = st.number_input(
                            "Dependentes", min_value=0, max_value=20,
                            value=int(dados_ir.get("dependentes") or 0), step=1)
                        campo_medicas = st.number_input(
                            "Despesas médicas (R$)", min_value=0.0,
                            value=float(dados_ir.get("despesas_medicas") or 0.0),
                            step=100.0,
                            help="Consulta, exame, plano, dentista, psicólogo. "
                                 "Farmácia NÃO entra.")
                        campo_instrucao = st.number_input(
                            "Despesas com instrução (R$)", min_value=0.0,
                            value=float(dados_ir.get("despesas_instrucao") or 0.0),
                            step=100.0,
                            help="Escola, faculdade, pós. Curso livre e idioma "
                                 "NÃO entram.")
                    with col_c:
                        campo_pensao = st.number_input(
                            "Pensão alimentícia judicial (R$)", min_value=0.0,
                            value=float(dados_ir.get("pensao_alimenticia") or 0.0),
                            step=100.0)
                        campo_outras = st.number_input(
                            "Outras deduções (R$)", min_value=0.0,
                            value=float(dados_ir.get("outras_deducoes") or 0.0),
                            step=100.0)
                        campo_aportes = st.number_input(
                            "Já aportado em PGBL neste ano (R$)", min_value=0.0,
                            value=float(dados_ir.get("aportes_pgbl") or 0.0),
                            step=500.0)

                    campo_inss_check = st.checkbox(
                        "Contribuo para o INSS (ou regime próprio), ou já sou "
                        "aposentado",
                        value=bool(dados_ir.get("contribui_inss", 1)),
                        help="É a porta de entrada da dedução de 12%. Sem isso "
                             "ela simplesmente não existe.")

                    st.caption(
                        f"**Ponto de partida a conferir, tirado dos seus "
                        f"lançamentos de {ano}:** Saúde "
                        f"{fmt_brl_md(sugestao_saude)} · Educação "
                        f"{fmt_brl_md(sugestao_educacao)}. Não copie direto — "
                        f"a Receita aceita despesa **médica**, não gasto com "
                        f"saúde: farmácia e academia ficam de fora; em educação, "
                        f"curso livre, idioma e material escolar também."
                    )

                    if st.form_submit_button("Salvar os números do ano",
                                             type="primary"):
                        prev.salvar_dados_do_ano(ano, {
                            "rendimento_bruto": campo_bruto,
                            "inss": campo_inss,
                            "irrf_retido": campo_irrf,
                            "dependentes": campo_dependentes,
                            "despesas_medicas": campo_medicas,
                            "despesas_instrucao": campo_instrucao,
                            "pensao_alimenticia": campo_pensao,
                            "outras_deducoes": campo_outras,
                            "aportes_pgbl": campo_aportes,
                            "contribui_inss": 1 if campo_inss_check else 0,
                        })
                        estado.limpar_cache()
                        c.recado("Guardado.")
                        st.rerun()

        if not dados_ir["preenchido"]:
            c.aviso_vazio(
                "Preencha o rendimento bruto do informe para ver a conta.",
                "Sem o bruto não há teto de 12%, e um teto chutado vira "
                "aporte do tamanho errado.")
        else:
            apuracao = prev.apurar(dados_ir, ano)
            recomendacao = prev.quanto_aportar(dados_ir, ano)

            c.secao("O teto e o que falta",
                    "12% da renda bruta tributável, e o prazo é 31/12")
            c.linha_kpis([
                {"rotulo": "Teto do ano (12%)",
                 "valor": fmt_brl(recomendacao["teto"]),
                 "ajuda": f"sobre {fmt_brl(dados_ir['rendimento_bruto'])} "
                          f"de bruto", "cor": "azul"},
                {"rotulo": "Já aportado",
                 "valor": fmt_brl(recomendacao["ja_aportado"]),
                 "ajuda": "informado por você"},
                {"rotulo": "Falta até 31/12",
                 "valor": fmt_brl(recomendacao["falta"]),
                 "ajuda": (f"{recomendacao['dias_ate_o_prazo']} dias · "
                           f"{fmt_brl(recomendacao['por_mes_ate_o_prazo'])}/mês"
                           if not recomendacao["prazo_vencido"]
                           else "o prazo deste ano já passou"),
                 "cor": "verde" if recomendacao["falta"] > 0 else None},
                {"rotulo": "Economia no teto",
                 "valor": fmt_brl(recomendacao["economia_no_teto"]),
                 "ajuda": (f"{fmt_pct(recomendacao['aliquota_efetiva'])} "
                           f"efetivos sobre o aporte"
                           if recomendacao["vale_a_pena"]
                           else "não há imposto a economizar"),
                 "cor": "verde" if recomendacao["vale_a_pena"] else "vermelha"},
            ])

            if recomendacao["excedeu"] > 0:
                st.error(
                    f"Você aportou {fmt_brl_md(recomendacao['excedeu'])} acima "
                    f"do teto. Esse excedente **não deduz nada** — e no "
                    f"resgate será tributado como PGBL, sobre o valor total. "
                    f"É o pior dos dois mundos.")

            if not recomendacao["vale_a_pena"]:
                st.warning(
                    f"**Para {ano}, o PGBL não economiza imposto nenhum.** "
                    f"{recomendacao['motivo']}")

            c.secao("Completa ou simplificada",
                    "a pergunta que decide se o PGBL vale alguma coisa")
            st.markdown(
                "O desconto simplificado **substitui todas as deduções** — "
                "inclusive a previdência. Se ele ganhar para você, o PGBL "
                "vale exatamente zero, por mais que você aporte."
            )

            comparacao = pd.DataFrame([
                {"Modelo": "Completa (deduções legais)",
                 "Deduções": apuracao["deducoes"]["total"],
                 "Base de cálculo": apuracao["completa_base"],
                 "Imposto devido": apuracao["completa_imposto"]},
                {"Modelo": "Simplificada (desconto de 20%)",
                 "Deduções": apuracao["simplificada_desconto"],
                 "Base de cálculo": apuracao["simplificada_base"],
                 "Imposto devido": apuracao["simplificada_imposto"]},
            ])
            priv.tabela(
                comparacao, hide_index=True, width="stretch",
                column_config={
                    "Deduções": c.config_moeda("Deduções"),
                    "Base de cálculo": c.config_moeda("Base de cálculo"),
                    "Imposto devido": c.config_moeda("Imposto devido"),
                })

            vencedor = ("**completa**" if apuracao["modelo"] == "completa"
                        else "**simplificada**")
            st.caption(
                f"Pela tabela de {ano} ({apuracao['lei']}), a declaração "
                f"{vencedor} paga menos: "
                f"{fmt_brl_md(apuracao['imposto_devido'])} de imposto contra "
                f"{fmt_brl_md(apuracao['irrf_retido'])} já retido — "
                + ("**a restituir " if apuracao["saldo"] < 0
                   else "**a pagar ")
                + fmt_brl_md(abs(apuracao["saldo"])) + "**."
            )

            if apuracao["redutor"] > 0:
                st.caption(
                    f"Inclui o **redutor da Lei 15.270/2025**: "
                    f"{fmt_brl_md(apuracao['redutor'])} abatidos do imposto. "
                    f"Ele olha para o rendimento bruto, não para a base — "
                    f"aportar em PGBL **não o aumenta**."
                )

            detalhe = apuracao["deducoes"]
            with st.expander("De onde vem cada dedução da completa"):
                linhas_deducao = pd.DataFrame([
                    {"Dedução": "INSS", "Valor": detalhe["inss"]},
                    {"Dedução": "Dependentes", "Valor": detalhe["dependentes"]},
                    {"Dedução": "Despesas médicas", "Valor": detalhe["medicas"]},
                    {"Dedução": "Instrução (já no teto)",
                     "Valor": detalhe["instrucao"]},
                    {"Dedução": "Pensão alimentícia", "Valor": detalhe["pensao"]},
                    {"Dedução": "Outras", "Valor": detalhe["outras"]},
                    {"Dedução": "PGBL", "Valor": detalhe["previdencia_pgbl"]},
                    {"Dedução": "TOTAL", "Valor": detalhe["total"]},
                ])
                priv.tabela(
                    linhas_deducao, hide_index=True, width="stretch",
                    column_config={"Valor": c.config_moeda("Valor")})
                if detalhe["instrucao_cortada"] > 0:
                    st.caption(
                        f"Instrução: {fmt_brl_md(detalhe['instrucao_cortada'])} "
                        f"ficaram de fora, porque o teto é "
                        f"{fmt_brl_md(detalhe['instrucao_teto'])} "
                        f"({fmt_brl_md(3561.50)} por pessoa)."
                    )

            c.secao("Simulador", "quanto muda se o aporte for outro")
            teto_slider = max(recomendacao["teto"], 1000.0)
            if priv.ocultando():
                aporte_simulado = float(recomendacao["teto"])
                st.caption(
                    "Simulando o **teto do ano**. O controle deslizante do "
                    "aporte mostra o valor em R$ ao lado da alça, e por isso "
                    "ele só aparece com os valores visíveis."
                )
            else:
                aporte_simulado = st.slider(
                    "Aporte em PGBL no ano (R$)", min_value=0.0,
                    max_value=float(round(teto_slider * 1.5, 2)),
                    value=float(recomendacao["teto"]),
                    step=max(100.0, round(teto_slider / 60, -2)),
                    key="pgbl_slider_aporte")

            beneficio = prev.beneficio_do_aporte(dados_ir, ano, aporte_simulado)
            c.linha_kpis([
                {"rotulo": "Deduz de verdade",
                 "valor": fmt_brl(beneficio["aporte_deduzido"]),
                 "ajuda": (f"{fmt_brl(beneficio['aporte_perdido'])} passaram "
                           f"do teto" if beneficio["aporte_perdido"] > 0
                           else "tudo dentro do teto"),
                 "pequeno": True,
                 "cor": "vermelha" if beneficio["aporte_perdido"] > 0 else None},
                {"rotulo": "Imposto sem o aporte",
                 "valor": fmt_brl(beneficio["imposto_sem"]), "pequeno": True},
                {"rotulo": "Imposto com o aporte",
                 "valor": fmt_brl(beneficio["imposto_com"]), "pequeno": True},
                {"rotulo": "Economia",
                 "valor": fmt_brl(beneficio["economia"]),
                 "ajuda": f"{fmt_pct(beneficio['aliquota_efetiva'])} efetivos",
                 "pequeno": True,
                 "cor": "verde" if beneficio["economia"] > 0 else None},
            ])

            if beneficio["motivo"]:
                st.info(beneficio["motivo"])
            elif 0 < beneficio["aliquota_efetiva"] < 0.274:
                st.caption(
                    f"**Repare que a economia não é 27,5% do aporte, e sim "
                    f"{fmt_pct(beneficio['aliquota_efetiva'])}.** A dedução "
                    f"derruba a base e atravessa faixa da tabela: parte dela "
                    f"é abatida a 27,5%, parte a uma alíquota menor. Por isso "
                    f"a conta aqui é a diferença entre dois impostos "
                    f"apurados, nunca `aporte × alíquota`."
                )

            c.secao("O outro lado: o imposto que você adia, e não deixa de pagar",
                    "no resgate, o PGBL é tributado sobre o TOTAL — aporte mais rendimento")
            st.markdown(
                "É esta a parte que os simuladores das seguradoras não "
                "mostram, e é ela que decide se a economia de hoje sobrevive."
            )

            col_1, col_2, col_3, col_4 = st.columns(4)
            with col_1:
                anos_ate_resgate = st.slider("Anos até o resgate", 1, 35, 15,
                                             key="pgbl_anos")
            with col_2:
                retorno = st.slider("Retorno esperado (% a.a.)", 0.0, 20.0,
                                    10.0, 0.5, key="pgbl_retorno") / 100
            with col_3:
                taxa_adm = st.slider("Taxa de adm. do plano (% a.a.)", 0.0, 3.0,
                                     0.8, 0.1, key="pgbl_taxa") / 100
            with col_4:
                reinveste = st.checkbox("Reinvisto a restituição", value=True,
                                        key="pgbl_reinveste")

            contra_vgbl = prev.comparar_com_vgbl(
                beneficio["aporte_deduzido"] or aporte_simulado,
                beneficio["economia"], anos_ate_resgate, retorno, taxa_adm,
                reinveste_a_restituicao=reinveste)

            c.linha_kpis([
                {"rotulo": "Alíquota no resgate",
                 "valor": fmt_pct(contra_vgbl["aliquota"]),
                 "ajuda": "tabela regressiva, pelo tempo do aporte",
                 "pequeno": True},
                {"rotulo": "PGBL líquido",
                 "valor": fmt_brl(contra_vgbl["liquido_pgbl"]),
                 "ajuda": "com a restituição reinvestida" if reinveste
                          else "restituição gasta, não reinvestida",
                 "pequeno": True},
                {"rotulo": "VGBL líquido",
                 "valor": fmt_brl(contra_vgbl["liquido_vgbl"]),
                 "ajuda": "mesma aplicação, imposto só sobre o ganho",
                 "pequeno": True},
                {"rotulo": "Diferença",
                 "valor": fmt_brl(contra_vgbl["diferenca"], sinal=True),
                 "ajuda": "a favor do PGBL" if contra_vgbl["pgbl_ganha"]
                          else "a favor do VGBL",
                 "pequeno": True,
                 "cor": "verde" if contra_vgbl["pgbl_ganha"] else "vermelha"},
            ])

            st.markdown(
                "**A comparação certa é com o VGBL**, não com um CDB: é a "
                "mesma aplicação, o mesmo prazo e a mesma tabela regressiva. "
                "Muda uma coisa só — o PGBL deduz na entrada e paga imposto "
                "sobre o **total** na saída; o VGBL não deduz e paga só sobre "
                "o **ganho**.\n\n"
                "A diferença entre os dois é sempre a alíquota vezes o "
                "próprio aporte. Daí sai a regra inteira, e ela cabe numa "
                f"linha: **sem a dedução, o VGBL ganha do PGBL por "
                f"{fmt_brl_md(contra_vgbl['imposto_extra_do_pgbl'])} — "
                f"{fmt_pct(contra_vgbl['aliquota'])} do aporte. Sempre.**"
            )

            curva = prev.curva_de_equilibrio(
                beneficio["aporte_deduzido"] or aporte_simulado,
                beneficio["economia"], retorno, taxa_adm,
                reinveste_a_restituicao=reinveste, ate=35)
            virada = prev.ano_de_virada(curva)

            figura = graficos.linha_comparacao_previdencia(curva)
            with c.painel(chave="pgbl_curva"):
                priv.grafico(figura, width="stretch", key="pgbl_curva")

            if virada:
                st.caption(
                    f"Contra um investimento comum (15% sobre o ganho), este "
                    f"aporte passa a valer mais no **ano {virada}**. Antes "
                    f"disso a alíquota regressiva ainda está alta, e o "
                    f"imposto sobre o principal pesa mais que a restituição."
                )
            else:
                st.caption(
                    "Nos 35 anos simulados o PGBL não passa o investimento "
                    "comum. Com estes números, a economia de imposto não "
                    "cobre o que se paga no resgate."
                )

            st.info(
                "Três \"se\" decidem tudo, e nenhum deles é sobre o plano: "
                "**se** você entrega a declaração completa, **se** fica até a "
                "alíquota de 10% (dez anos), e **se** reinveste a "
                "restituição. Desmarque o reinvestimento acima e veja o que "
                "acontece — a restituição é o benefício inteiro.")

            c.secao("Ano a ano", "o teto de cada ano, e o que falta em cada um")
            panorama = prev.panorama()
            visao_panorama = panorama.rename(columns={
                "ano": "Ano", "rendimento_bruto": "Bruto tributável",
                "teto": "Teto (12%)", "ja_aportado": "Aportado",
                "falta": "Falta", "economia_no_teto": "Economia no teto",
                "modelo": "Declaração", "preenchido": "Informe",
            })
            priv.tabela(
                visao_panorama[["Ano", "Informe", "Bruto tributável",
                                "Teto (12%)", "Aportado", "Falta",
                                "Economia no teto", "Declaração"]],
                hide_index=True, width="stretch",
                column_config={
                    "Informe": st.column_config.CheckboxColumn("Informe"),
                    "Bruto tributável": c.config_moeda("Bruto tributável"),
                    "Teto (12%)": c.config_moeda("Teto (12%)"),
                    "Aportado": c.config_moeda("Aportado"),
                    "Falta": c.config_moeda("Falta"),
                    "Economia no teto": c.config_moeda("Economia no teto"),
                })
            st.caption(
                "Ano com o informe em branco aparece zerado — o teto sai do "
                "bruto, e o bruto vem do informe. Só existem linhas para os "
                "anos cuja tabela do IR está cadastrada: **"
                + "**, **".join(prev.anos_com_tabela()) + "**."
            )

with aba_como:
    st.markdown("### Como declarar — o porquê antes do como")

    c.nota(
        "Esta aba explica <b>onde cada coisa entra</b> e <b>por quê</b>. Ela "
        "não calcula o seu imposto e não substitui um contador — e isso não é "
        "formalidade: apurar imposto exige o informe oficial e regras que "
        "mudam todo ano."
    )

    st.markdown("#### 1. Renda: duas fichas, e a diferença custa dinheiro")
    st.markdown(
        "A declaração separa o que você recebeu em duas famílias, e a "
        "diferença entre elas é **quando o imposto foi calculado**.\n\n"
        "- **Rendimentos Tributáveis** — o salário. O imposto é recalculado "
        "no ajuste anual, somando tudo o que você ganhou no ano. É daqui que "
        "sai restituição ou imposto a pagar.\n"
        "- **Tributação exclusiva/definitiva** — a **PLR** e os rendimentos "
        "de aplicação financeira. O imposto já foi calculado na fonte, por "
        "tabela própria, e **acabou**. Não entra no ajuste, não gera "
        "restituição.\n\n"
        "**Por isso somar a PLR ao salário é um erro caro:** você jogaria um "
        "valor já tributado dentro da tabela progressiva, subindo sua "
        "alíquota sobre todo o resto."
    )

    st.markdown("#### 2. Bens: custo, nunca valor de mercado")
    st.markdown(
        "A ficha **Bens e Direitos** é uma fotografia do que você tinha em "
        "**31 de dezembro**, avaliada pelo que você **pagou**.\n\n"
        "A razão é simples: a Receita cobra imposto sobre **ganho "
        "realizado**. Enquanto você não vende, a valorização não existe para "
        "ela. Se você declarasse pelo valor de mercado, a diferença entre um "
        "ano e outro apareceria como patrimônio surgido do nada — e você "
        "teria de explicar de onde veio.\n\n"
        "Corretagem, taxa de liquidação e emolumentos **entram no custo**."
    )

    st.markdown("#### 3. O exterior é a parte em que você está sozinho")
    st.markdown(
        "Para a XP-Brasil existe informe de rendimentos, e a Receita exige "
        "que você use o documento oficial da corretora.\n\n"
        "**Para a conta Global não existe informe.** Desde a Lei "
        "14.754/2023, aplicação financeira no exterior é tributada a **15%** "
        "na declaração anual, **sem a faixa de isenção mensal** que ações "
        "brasileiras têm. E prejuízo precisa ser declarado — é ele que "
        "compensa ganho futuro.\n\n"
        "A posição internacional deste app foi reconstruída de "
        "`quantidade × cotação`, conferida contra o seu print da corretora. "
        "É a melhor fonte que você tem, e ela vale **enquanto você não operar "
        "lá de novo** — no dia em que operar, as quantidades precisam ser "
        "atualizadas à mão."
    )

    st.markdown("#### 4. O que buscar fora deste app")
    st.markdown(
        "| Documento | Onde | Para quê |\n"
        "|---|---|---|\n"
        "| Informe de rendimentos da empresa | RH ou portal do funcionário | "
        "salário **bruto**, INSS e IRRF |\n"
        "| Informe da XP-Brasil | app ou site da corretora | posição oficial "
        "em 31/12 e imposto retido |\n"
        "| Notas de corretagem | corretora | custo de aquisição, quando o "
        "informe não detalha |\n"
        "| **XP Global** | **não existe** | você reconstrói — é para isso que "
        "esta tela serve |"
    )

    with st.expander("Por que esta tela não calcula o imposto"):
        st.markdown(
            "Três motivos, todos concretos:\n\n"
            "1. **O app vê o líquido.** Sem o bruto do informe, qualquer "
            "cálculo de imposto sobre salário estaria errado desde a "
            "primeira linha.\n"
            "2. **Falta o custo de boa parte da carteira.** Ganho de capital "
            "é `venda − custo`; sem custo confiável não há ganho confiável.\n"
            "3. **As regras mudam.** Faixa de isenção, alíquota e prazo "
            "mudam por lei. Um número calculado aqui envelheceria em "
            "silêncio — que é exatamente o tipo de erro que este projeto "
            "passa o tempo todo tentando evitar.\n\n"
            "O que a tela faz em vez disso é mais útil e mais honesto: "
            "**deixar você chegar no contador com tudo separado, conferido "
            "e com os buracos apontados.**\n\n"
            "**A exceção é a aba Previdência**, e ela confirma a regra: lá o "
            "imposto é calculado, mas só depois que **você** digita o bruto "
            "do informe. Ela resolve o motivo 1 pedindo o dado que falta, em "
            "vez de adivinhá-lo — e o motivo 3 guardando cada tabela com o "
            "ano e a lei a que pertence, recusando-se a calcular um ano cuja "
            "tabela ela não conhece."
        )

c.rodape_atualizado(len(df))
