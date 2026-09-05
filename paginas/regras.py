"""
regras.py — Editar as regras que categorizam tudo automaticamente.
==============================================================================

A REGRA DE OURO: A ORDEM IMPORTA
--------------------------------
As regras sao lidas DE CIMA PARA BAIXO e a PRIMEIRA que casar vence. As de
baixo nem chegam a ser testadas.

Isso nao e detalhe tecnico, e a logica em si. Exemplo real do seu extrato:

    ordem 5:  "XP EMPREGADORA", acima de R$ ···· entrando  -> PLR
    ordem 6:  "XP EMPREGADORA", qualquer valor,     entrando  -> Salário

O salario de todo mes cai na regra 6. So o PLR anual, que passa de 50 mil,
cai na 5. Se voce inverter as duas, o PLR passa a ser classificado como
salario e o painel perde a distincao entre receita normal e extraordinaria.

Regra ESPECIFICA em cima. Regra GENERICA embaixo.

O QUE ESTA TELA TEM QUE A PLANILHA NAO TINHA
--------------------------------------------
1. TESTAR contra o historico: quantos lancamentos cada regra pegaria hoje.
   Mostra regra morta (nunca casa) e regra canibal (engole o que deveria cair
   numa mais especifica).
2. SUGERIR regras novas a partir do que ficou sem classificacao — usando a
   categoria que VOCE mesmo escolheu a mao nas vezes anteriores.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from financas import banco, config, regras as motor
from financas.formato import fmt_pct, rotulo_mes, vazio
from ui.privacidade import fmt_brl
from ui import privacidade as priv
from ui import componentes as c
from ui import estado


def _texto_ou_none(valor) -> str | None:
    """Converte para texto limpo, ou `None` quando vazio.

    Uma célula vazia do `st.data_editor` chega como `NaN` do pandas, e
    `NaN or ""` continua sendo `NaN` (porque `bool(NaN)` é `True`) — daí
    `str(x or "")` gravar a STRING "nan" no banco em vez de None. `vazio()`
    é a única forma segura de checar isso.
    """
    return None if vazio(valor) else str(valor).strip() or None


def _numero_ou(valor, padrao: float) -> float:
    """Como `_texto_ou_none`, para número: célula vazia tem `NaN` onde devia
    ter o padrão, e `NaN or 0` continua sendo `NaN` — mesma armadilha."""
    return padrao if vazio(valor) else float(valor)


SEM_ESCOLHA = "— decidir depois —"

c.cabecalho("Regras", "Como cada transação ganha categoria automaticamente")
c.mostrar_recado()

c.nota(
    "As regras são lidas <strong>de cima para baixo</strong> e a "
    "<strong>primeira que casar vence</strong>. Coloque as regras específicas "
    "em cima e as genéricas embaixo. A coluna <strong>Ordem</strong> controla "
    "isso — números menores são testados primeiro."
)

(aba_triagem, aba_fatura, aba_extrato,
 aba_teste, aba_sugestoes) = st.tabs(
    ["Triagem", "Regras da fatura", "Regras do extrato", "Testar", "Sugestões"]
)


with aba_fatura:
    st.caption(
        "Aplicadas nas compras do cartão. A comparação ignora acentos e "
        "maiúsculas: a palavra-chave `DROGA` casa com «Drogaria Tamoio»."
    )

    regras_fatura = banco.df(
        "SELECT id, ordem, palavra_chave, categoria, tipo, ativa "
        "FROM regras_fatura ORDER BY ordem, id"
    )

    editado_fatura = priv.editor(
        regras_fatura, hide_index=True, width="stretch", num_rows="dynamic",
        height=520, key="editor_regras_fatura",
        column_config={
            "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
            "ordem": st.column_config.NumberColumn(
                "Ordem", min_value=1, step=1, width="small",
                help="menor = testada primeiro"),
            "palavra_chave": st.column_config.TextColumn(
                "Palavra-chave", required=True, width="large",
                help="trecho que precisa aparecer na descrição"),
            "categoria": st.column_config.SelectboxColumn(
                "Categoria", options=estado.lista_categorias(), required=True),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=config.TIPOS),
            "ativa": st.column_config.CheckboxColumn("Ativa"),
        },
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Salvar regras da fatura", type="primary", width="stretch"):
            for _, linha in editado_fatura.iterrows():
                palavra = _texto_ou_none(linha.get("palavra_chave")) or ""
                if not palavra:
                    continue
                valores = (
                    int(_numero_ou(linha.get("ordem"), 999)), palavra,
                    linha.get("categoria"),
                    _texto_ou_none(linha.get("tipo")) or config.TIPO_VARIAVEL,
                    1 if linha.get("ativa", True) else 0,
                )
                if pd.notna(linha.get("id")):
                    banco.executar(
                        "UPDATE regras_fatura SET ordem=?, palavra_chave=?, "
                        "categoria=?, tipo=?, ativa=? WHERE id=?",
                        (*valores, int(linha["id"])),
                    )
                else:
                    banco.executar(
                        "INSERT INTO regras_fatura "
                        "(ordem, palavra_chave, categoria, tipo, ativa) "
                        "VALUES (?,?,?,?,?)",
                        valores,
                    )
            ids_na_tela = {int(i) for i in editado_fatura["id"].dropna()}
            for id_antigo in regras_fatura["id"]:
                if int(id_antigo) not in ids_na_tela:
                    banco.executar("DELETE FROM regras_fatura WHERE id = ?",
                                   (int(id_antigo),))
            estado.limpar_cache()
            c.recado("Regras da fatura salvas.")
            st.rerun()
    with col2:
        st.caption(
            f"{len(regras_fatura)} regras cadastradas. Para reordenar, mude o "
            "número na coluna Ordem e salve — a tabela é reordenada ao recarregar."
        )


with aba_extrato:
    st.caption(
        "Aplicadas nas movimentações da conta corrente. Além da palavra-chave, "
        "elas olham o **valor mínimo** e o **sentido** do dinheiro — é o que "
        "permite a mesma origem virar coisas diferentes."
    )

    regras_extrato = banco.df(
        "SELECT id, ordem, palavra_chave, valor_min_abs, sinal, categoria, "
        "tipo, natureza, ativa FROM regras_extrato ORDER BY ordem, id"
    )

    editado_extrato = priv.editor(
        regras_extrato, hide_index=True, width="stretch", num_rows="dynamic",
        height=520, key="editor_regras_extrato",
        column_config={
            "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
            "ordem": st.column_config.NumberColumn("Ordem", min_value=1, step=1, width="small"),
            "palavra_chave": st.column_config.TextColumn(
                "Palavra-chave", required=True, width="large"),
            "valor_min_abs": st.column_config.NumberColumn(
                "Valor mínimo", format="R$ %.2f", min_value=0.0, step=100.0,
                help="a regra só vale se o valor absoluto for igual ou maior"),
            "sinal": st.column_config.SelectboxColumn(
                "Sentido", options=config.SINAIS,
                help="Entrada = dinheiro entrando · Saída = saindo · Ambos = tanto faz"),
            "categoria": st.column_config.SelectboxColumn(
                "Categoria", options=estado.lista_categorias(), required=True),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=config.TIPOS),
            "natureza": st.column_config.SelectboxColumn(
                "Natureza", options=config.NATUREZAS),
            "ativa": st.column_config.CheckboxColumn("Ativa"),
        },
    )

    if st.button("Salvar regras do extrato", type="primary"):
        for _, linha in editado_extrato.iterrows():
            palavra = _texto_ou_none(linha.get("palavra_chave")) or ""
            if not palavra:
                continue
            valores = (
                int(_numero_ou(linha.get("ordem"), 999)), palavra,
                _numero_ou(linha.get("valor_min_abs"), 0.0),
                _texto_ou_none(linha.get("sinal")) or config.SINAL_AMBOS,
                linha.get("categoria"),
                _texto_ou_none(linha.get("tipo")) or config.TIPO_VARIAVEL,
                _texto_ou_none(linha.get("natureza")) or config.NATUREZA_DESPESA,
                1 if linha.get("ativa", True) else 0,
            )
            if pd.notna(linha.get("id")):
                banco.executar(
                    "UPDATE regras_extrato SET ordem=?, palavra_chave=?, "
                    "valor_min_abs=?, sinal=?, categoria=?, tipo=?, natureza=?, "
                    "ativa=? WHERE id=?",
                    (*valores, int(linha["id"])),
                )
            else:
                banco.executar(
                    "INSERT INTO regras_extrato (ordem, palavra_chave, "
                    "valor_min_abs, sinal, categoria, tipo, natureza, ativa) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    valores,
                )
        ids_na_tela = {int(i) for i in editado_extrato["id"].dropna()}
        for id_antigo in regras_extrato["id"]:
            if int(id_antigo) not in ids_na_tela:
                banco.executar("DELETE FROM regras_extrato WHERE id = ?",
                               (int(id_antigo),))
        estado.limpar_cache()
        c.recado("Regras do extrato salvas.")
        st.rerun()

    with st.expander("Exemplo de como o valor mínimo e o sentido trabalham juntos"):
        st.markdown(
            """
Estas duas regras existem no seu cadastro, nesta ordem:

| Ordem | Palavra-chave | Valor mín. | Sentido | Vira |
|---|---|---|---|---|
| 5 | XP EMPREGADORA | R$ 50.000 | Entrada | **PLR** (Receita Extraordinária) |
| 6 | XP EMPREGADORA | R$ 0 | Entrada | **Salário** (Receita) |

Um depósito de R$ 4.180 não atinge os R$ 50.000, então pula a regra 5 e cai
na 6 → Salário. Um depósito de R$ 61.240 atinge, então para na regra 5 → PLR.

Se você inverter a ordem, **os dois** viram Salário — porque a regra genérica
casaria primeiro e a específica nunca seria testada.
            """
        )


with aba_teste:
    st.markdown("### Quantos lançamentos cada regra pegaria hoje")
    st.caption(
        "Roda todas as regras contra o histórico inteiro, na ordem real. "
        "Serve para achar regra morta (nunca casa) e regra canibal (uma "
        "genérica em cima engolindo o que deveria cair numa específica abaixo)."
    )

    origem_teste = st.radio(
        "Testar as regras de", [config.ORIGEM_FATURA, config.ORIGEM_EXTRATO],
        horizontal=True, key="origem_teste",
    )

    if st.button("Rodar teste", type="primary"):
        with st.spinner("Testando contra o histórico..."):
            resultado = motor.testar_contra_historico(origem_teste)
        estado.guardar("resultado_teste_regras", resultado)
        estado.guardar("origem_teste_regras", origem_teste)

    resultado = estado.pegar("resultado_teste_regras")
    if resultado and estado.pegar("origem_teste_regras") == origem_teste:
        tabela = pd.DataFrame(resultado)
        com_ordem = tabela[tabela["ordem"].notna()]
        sem_regra = tabela[tabela["ordem"].isna()]

        mortas = com_ordem[com_ordem["acertos"] == 0]
        total_pego = int(com_ordem["acertos"].sum())
        total_sem = int(sem_regra["acertos"].iloc[0]) if not sem_regra.empty else 0
        total = total_pego + total_sem

        c.linha_kpis([
            {"rotulo": "Regras cadastradas", "valor": str(len(com_ordem)), "pequeno": True},
            {"rotulo": "Regras que pegam algo", "valor": str(len(com_ordem) - len(mortas)),
             "cor": "verde", "pequeno": True},
            {"rotulo": "Regras mortas", "valor": str(len(mortas)),
             "cor": "amarela" if len(mortas) else "verde", "pequeno": True,
             "ajuda": "nunca casam com nada"},
            {"rotulo": "Sem nenhuma regra", "valor": str(total_sem),
             "ajuda": f"{fmt_pct(total_sem / total if total else 0)} do histórico",
             "cor": "azul", "pequeno": True},
        ])

        st.markdown("**Regras que mais pegam**")
        ativas = com_ordem[com_ordem["acertos"] > 0].sort_values(
            "acertos", ascending=False)
        priv.tabela(
            ativas.rename(columns={
                "ordem": "Ordem", "palavra_chave": "Palavra-chave",
                "categoria": "Categoria", "acertos": "Lançamentos",
            }),
            hide_index=True, width="stretch", height=320,
        )

        if not mortas.empty:
            st.markdown("**Regras que nunca casam com nada**")
            st.caption(
                "Ou a loja mudou de nome no extrato, ou uma regra mais acima "
                "está pegando essas transações antes. Não fazem mal, mas "
                "poluem a lista."
            )
            priv.tabela(
                mortas[["ordem", "palavra_chave", "categoria"]].rename(columns={
                    "ordem": "Ordem", "palavra_chave": "Palavra-chave",
                    "categoria": "Categoria",
                }),
                hide_index=True, width="stretch", height=240,
            )


with aba_sugestoes:
    st.markdown("### Regras que valeria a pena criar")
    st.caption(
        "Estabelecimentos que aparecem várias vezes no seu histórico e que "
        "nenhuma regra reconhece. A categoria sugerida **não é um palpite**: é "
        "a que você mesmo escolheu à mão nas vezes anteriores."
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        origem_sugestao = st.radio(
            "Analisar", [config.ORIGEM_FATURA, config.ORIGEM_EXTRATO],
            horizontal=True, key="origem_sugestao",
        )
    with col2:
        minimo = st.slider("Aparecer pelo menos N vezes", 2, 10, 2,
                           key="minimo_sugestao")

    if st.button("Buscar sugestões", type="primary"):
        with st.spinner("Analisando o histórico..."):
            sugestoes = motor.sugerir_regras(origem_sugestao, minimo)
        estado.guardar("sugestoes_regras", sugestoes)
        estado.guardar("origem_sugestoes", origem_sugestao)

    sugestoes = estado.pegar("sugestoes_regras")
    if sugestoes is not None and estado.pegar("origem_sugestoes") == origem_sugestao:
        if not sugestoes:
            st.success(
                "Nenhuma sugestão: todo estabelecimento recorrente já tem regra."
            )
        else:
            st.caption(f"{len(sugestoes)} sugestão(ões). Marque as que quiser criar.")

            tabela_sugestoes = pd.DataFrame(sugestoes)
            tabela_sugestoes.insert(0, "criar", False)
            tabela_sugestoes["concordancia"] = tabela_sugestoes["concordancia"] * 100

            editado_sugestoes = priv.editor(
                tabela_sugestoes[["criar", "palavra_chave", "ocorrencias",
                                  "valor_total", "categoria_sugerida",
                                  "tipo_sugerido", "concordancia", "exemplo"]],
                hide_index=True, width="stretch", height=420,
                key="editor_sugestoes",
                column_config={
                    "criar": st.column_config.CheckboxColumn("Criar", width="small"),
                    "palavra_chave": st.column_config.TextColumn(
                        "Palavra-chave", width="medium"),
                    "ocorrencias": st.column_config.NumberColumn("Vezes", width="small"),
                    "valor_total": c.config_moeda("Valor total"),
                    "categoria_sugerida": st.column_config.SelectboxColumn(
                        "Categoria", options=estado.lista_categorias()),
                    "tipo_sugerido": st.column_config.SelectboxColumn(
                        "Tipo", options=config.TIPOS),
                    "concordancia": c.config_percentual(
                        "Concordância",
                        "quanto das vezes você usou essa mesma categoria"),
                    "exemplo": st.column_config.TextColumn(
                        "Exemplo real", disabled=True, width="large"),
                },
            )

            escolhidas = editado_sugestoes[editado_sugestoes["criar"]]
            if not escolhidas.empty:
                st.caption(f"{len(escolhidas)} regra(s) selecionada(s).")
            if st.button(f"Criar {len(escolhidas)} regra(s)",
                         type="primary", disabled=escolhidas.empty):
                for _, linha in escolhidas.iterrows():
                    if origem_sugestao == config.ORIGEM_FATURA:
                        motor.adicionar_regra_fatura(
                            linha["palavra_chave"], linha["categoria_sugerida"],
                            linha["tipo_sugerido"])
                    else:
                        motor.adicionar_regra_extrato(
                            linha["palavra_chave"], linha["categoria_sugerida"],
                            linha["tipo_sugerido"])
                estado.limpar_cache()
                estado.esquecer("sugestoes_regras")
                c.recado(
                    f"{len(escolhidas)} regra(s) criada(s) no fim da lista. "
                    f"Elas valem para as PRÓXIMAS importações — os lançamentos "
                    f"que já estão no banco continuam como estão."
                )
                st.rerun()

            st.caption(
                "As regras novas entram no **fim** da lista, com a menor "
                "prioridade. Assim elas nunca roubam transações de uma regra "
                "específica que você já tinha ajustado."
            )


with aba_triagem:
    c.nota(
        "Aqui você resolve o que caiu em <strong>Outros</strong>. Cada linha é "
        "um estabelecimento, não um lançamento — escolher a categoria de uma "
        "linha conserta <strong>todos</strong> os lançamentos dele de uma vez, "
        "e ainda cria a regra para as próximas importações."
    )

    cobertura = motor.cobertura_da_triagem()
    if cobertura["linhas"] == 0:
        st.success("Nada em Outros. Todos os lançamentos têm categoria.")
    else:
        c.linha_kpis([
            {"rotulo": "Lançamentos em Outros", "valor": f"{cobertura['linhas']}",
             "pequeno": True},
            {"rotulo": "Valor", "valor": fmt_brl(cobertura["valor"]),
             "cor": "amarela", "pequeno": True},
            {"rotulo": "Estabelecimentos", "valor": f"{cobertura['grupos']}",
             "ajuda": "cada um é uma decisão", "pequeno": True},
        ])

        quantos = st.slider(
            "Quantos estabelecimentos mostrar", 10, 150, 30, step=10,
            key="triagem_quantos",
            help="Estão ordenados do que mais pesa para o que menos pesa. "
                 "As primeiras 25 costumam cobrir metade do valor.",
        )

        grupos = motor.grupos_sem_categoria(limite=quantos)
        if grupos.empty:
            st.info("Nada para triar.")
        else:
            peso_mostrado = grupos["valor_total"].abs().sum()
            peso_total = abs(cobertura["valor"]) or 1
            st.caption(
                f"Os {len(grupos)} da tela cobrem "
                f"**{peso_mostrado / peso_total:.0%}** do valor que falta "
                f"classificar."
            )

            tabela = grupos.copy()
            tabela.insert(0, "categoria", SEM_ESCOLHA)
            tabela["tipo"] = config.TIPO_VARIAVEL
            tabela["criar_regra"] = True
            tabela["periodo"] = (tabela["primeiro_mes"].map(rotulo_mes) + " a "
                                 + tabela["ultimo_mes"].map(rotulo_mes))

            editado = priv.editor(
                tabela[["chave", "ocorrencias", "valor_total", "categoria",
                        "tipo", "criar_regra", "periodo", "exemplo"]],
                hide_index=True, width="stretch", height=520,
                key="editor_triagem",
                column_config={
                    "chave": st.column_config.TextColumn(
                        "Estabelecimento", disabled=True, width="medium"),
                    "ocorrencias": st.column_config.NumberColumn(
                        "Linhas", disabled=True, width="small"),
                    "valor_total": c.config_moeda("Valor"),
                    "categoria": st.column_config.SelectboxColumn(
                        "Categoria", options=[SEM_ESCOLHA] + estado.lista_categorias(),
                        width="medium",
                        help="Deixe em branco o que você não quiser decidir agora."),
                    "tipo": st.column_config.SelectboxColumn(
                        "Tipo", options=config.TIPOS, width="small"),
                    "criar_regra": st.column_config.CheckboxColumn(
                        "Criar regra", width="small",
                        help="Marca para a próxima importação já classificar "
                             "sozinha. Desmarque se for um gasto único."),
                    "periodo": st.column_config.TextColumn(
                        "Período", disabled=True, width="small"),
                    "exemplo": st.column_config.TextColumn(
                        "Como aparece no arquivo", disabled=True, width="large"),
                },
            )

            escolhidas = editado[editado["categoria"] != SEM_ESCOLHA]
            linhas_afetadas = int(escolhidas["ocorrencias"].sum()) if not escolhidas.empty else 0

            if not escolhidas.empty:
                st.caption(
                    f"{len(escolhidas)} decisão(ões) → **{linhas_afetadas} "
                    f"lançamento(s)** serão reclassificados."
                )

            if st.button(f"Aplicar {len(escolhidas)} decisão(ões)",
                         type="primary", disabled=escolhidas.empty,
                         key="botao_triagem"):
                total_linhas = 0
                total_regras = 0
                recusadas = []
                with st.spinner("Reclassificando..."):
                    for _, linha in escolhidas.iterrows():
                        natureza = (config.NATUREZA_RECEITA
                                    if linha["valor_total"] > 0
                                    else config.NATUREZA_DESPESA)
                        resultado = motor.aplicar_triagem(
                            linha["chave"], linha["categoria"], linha["tipo"],
                            natureza=natureza,
                            criar_regra=bool(linha["criar_regra"]))
                        total_linhas += resultado["atualizados"]
                        total_regras += 1 if resultado["regra_criada"] else 0
                        if resultado.get("regra_recusada"):
                            recusadas.append(resultado["regra_recusada"])
                estado.limpar_cache()
                c.recado(
                    f"**{total_linhas} lançamento(s)** reclassificados e "
                    f"**{total_regras} regra(s)** criadas. O passado foi "
                    f"corrigido e as próximas importações já sabem o caminho."
                )
                if recusadas:
                    st.warning(
                        f"Para {len(recusadas)} deles **não criei regra**: "
                        f"`{'`, `'.join(recusadas)}`. A palavra pegaria "
                        f"lançamentos de outro estabelecimento, e uma regra "
                        f"assim erraria em toda importação futura. "
                        f"Os lançamentos foram reclassificados do mesmo jeito."
                    )
                st.rerun()

            c.nota(
                "Não persiga 100%. Nos seus dados, <strong>416 "
                "estabelecimentos aparecem uma única vez</strong> — decidir "
                "cada compra de R$ 40 custa mais do que o número melhora. "
                "Resolva os que pesam e deixe a cauda em Outros."
            )
