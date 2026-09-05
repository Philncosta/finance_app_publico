"""
lancamentos.py — A tabela de tudo: buscar, filtrar, corrigir e lancar a mao.
==============================================================================

O QUE ESTA TELA FAZ
-------------------
E o equivalente a aba Base_Dados da planilha, mas com filtro de verdade e
edicao direta. Quatro coisas:

    1. FILTRAR    achar lancamentos por mes, categoria, texto, valor
    2. CORRIGIR   trocar a categoria de varias linhas de uma vez
    3. LANCAR     registrar um gasto que nao veio de arquivo (dinheiro, Pix
                  de outro banco, uma divisao de conta)
    4. EXPORTAR   levar o recorte para CSV ou Excel

SOBRE O st.data_editor
----------------------
E uma tabela EDITAVEL. Voce mexe nas celulas e ele devolve o DataFrame
alterado quando o script roda de novo. Nao salva sozinho no banco — a
gravacao acontece quando voce clica em Salvar, e isso e proposital: evita
gravar no meio de uma edicao.

A ARMADILHA DA COLUNA DE DATA
-----------------------------
O SQLite guarda data como TEXTO. Se voce entregar esse texto direto para um
`DateColumn`, o Streamlit quebra. Entao o caminho e sempre:

    pd.to_datetime(...)      antes de mostrar
    .dt.strftime("%Y-%m-%d") antes de salvar
"""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from financas import banco, config, dados
from financas.formato import mes_de, rotulo_mes
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado

df = estado.lancamentos()

c.cabecalho("Lançamentos", "Todo o histórico, filtrável e editável")
c.mostrar_recado()

if df.empty:
    c.aviso_vazio(
        "Ainda não há lançamentos.",
        "Use **Importar arquivos** ou cadastre um lançamento manual aqui embaixo.",
    )


with st.container(border=True, key="cartao_filtros"):
    st.markdown("**Filtros**")

    mapa_macro = dict(zip(estado.categorias()["nome"],
                          estado.categorias()["grande_categoria"]))

    linha1 = st.columns([2, 2, 2, 2, 2])
    with linha1[0]:
        meses_opcoes = ["Todos"] + estado.meses()
        mes_filtro = st.selectbox(
            "Mês", meses_opcoes,
            format_func=lambda m: "Todos os meses" if m == "Todos" else rotulo_mes(m),
            key="lanc_mes",
        )
    with linha1[1]:
        macro_filtro = st.selectbox(
            "Grande categoria", ["Todas"] + estado.lista_grandes_categorias(),
            key="lanc_macro",
            help="o agrupamento largo — Veículo, Casa, Comida…",
        )
    with linha1[2]:
        if macro_filtro == "Todas":
            micros = estado.lista_categorias()
        else:
            micros = [c for c in estado.lista_categorias()
                      if mapa_macro.get(c) == macro_filtro]
        categoria_filtro = st.selectbox(
            "Categoria", ["Todas"] + micros, key="lanc_cat",
            help="a categoria detalhada",
        )
    with linha1[3]:
        natureza_filtro = st.selectbox(
            "Natureza", ["Todas"] + config.NATUREZAS, key="lanc_nat")
    with linha1[4]:
        origem_filtro = st.selectbox(
            "Origem", ["Todas"] + config.ORIGENS, key="lanc_org")

    linha2 = st.columns([3, 2, 2])
    with linha2[0]:
        busca = st.text_input(
            "Buscar na descrição", placeholder="ex: uber, drogaria, pix...",
            key="lanc_busca")
    with linha2[1]:
        tipo_filtro = st.selectbox("Tipo", ["Todos"] + config.TIPOS, key="lanc_tipo")
    with linha2[2]:
        so_parceladas = st.checkbox("Só parceladas", key="lanc_parc")

filtrado = df.copy()

if mes_filtro != "Todos":
    filtrado = filtrado[filtrado["mes_competencia"] == mes_filtro]
if macro_filtro != "Todas":
    filtrado = filtrado[filtrado["grande_categoria"] == macro_filtro]
if categoria_filtro != "Todas":
    filtrado = filtrado[filtrado["categoria"] == categoria_filtro]
if natureza_filtro != "Todas":
    filtrado = filtrado[filtrado["natureza"] == natureza_filtro]
if origem_filtro != "Todas":
    filtrado = filtrado[filtrado["origem"] == origem_filtro]
if tipo_filtro != "Todos":
    filtrado = filtrado[filtrado["tipo"] == tipo_filtro]
if so_parceladas:
    filtrado = filtrado[filtrado["e_parcelado"]]
if busca.strip():
    filtrado = filtrado[
        filtrado["descricao"].str.contains(busca.strip(), case=False, na=False)
    ]


receita = dados.total_receita(filtrado)
despesa = dados.total_despesa(filtrado)
saldo = receita - despesa

movimentacao = float(
    filtrado[~filtrado["e_receita"] & ~filtrado["e_despesa"]]["valor"].sum()
) if not filtrado.empty else 0.0

c.linha_kpis([
    {"rotulo": "Lançamentos", "valor": f"{len(filtrado)}", "pequeno": True},
    {"rotulo": "Receita", "valor": fmt_brl(receita), "cor": "verde",
     "ajuda": "natureza Receita e Receita Extraordinária", "pequeno": True},
    {"rotulo": "Despesa", "valor": fmt_brl(-despesa), "cor": "vermelha",
     "ajuda": "natureza Despesa; estorno abate", "pequeno": True},
    {"rotulo": "Saldo", "valor": fmt_brl(saldo),
     "ajuda": "receita menos despesa",
     "cor": "verde" if saldo >= 0 else "vermelha", "pequeno": True},
    {"rotulo": "Movimentação", "valor": fmt_brl(movimentacao),
     "ajuda": "investimento, pagamento de fatura e transferência — "
              "dinheiro que mudou de lugar, fora do saldo",
     "cor": "azul", "pequeno": True},
])

if abs(movimentacao) > 0.01:
    st.caption(
        f"O recorte tem {fmt_brl_md(abs(movimentacao))} de **movimentação** — "
        "aporte para investimento, pagamento de fatura e transferência. Não "
        "entra no saldo de propósito: esse dinheiro não foi ganho nem gasto, "
        "só mudou de lugar."
    )

st.markdown("")


if filtrado.empty:
    c.aviso_vazio("Nenhum lançamento com esses filtros.",
                  "Tente afrouxar a busca ou mudar o mês.")
else:
    st.markdown("### Editar lançamentos")
    st.caption(
        "Mexa nas células de Categoria, Tipo, Natureza ou Observação e clique "
        "em **Salvar alterações**. As demais colunas são somente leitura, "
        "porque vêm do arquivo do banco e mudá-las quebraria a deduplicação."
    )
    st.caption(
        "A **Grande categoria** não é editável aqui de propósito: ela vem "
        "amarrada à categoria pelo cadastro (Pedágio está sempre em Veículo). "
        "Trocando a categoria, o macro acompanha sozinho. Para mudar a que "
        "macro uma categoria pertence, vá em **Configurações → Categorias** — "
        "assim a regra vale para todos os lançamentos de uma vez."
    )

    colunas_tabela = ["id", "data", "descricao", "valor",
                      "grande_categoria", "categoria", "tipo",
                      "natureza", "origem", "parcela_atual", "parcela_total",
                      "observacao"]
    para_editar = filtrado[colunas_tabela].copy()
    para_editar["data"] = pd.to_datetime(para_editar["data"], errors="coerce")
    para_editar["parcela"] = (
        para_editar["parcela_atual"].astype(str) + "/"
        + para_editar["parcela_total"].astype(str)
    )
    para_editar = para_editar.drop(columns=["parcela_atual", "parcela_total"])

    editado = priv.editor(
        para_editar,
        hide_index=True,
        width="stretch",
        height=460,
        key="editor_lancamentos",
        column_config={
            "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
            "data": c.config_data("Data"),
            "descricao": st.column_config.TextColumn("Descrição", disabled=True, width="large"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", disabled=True),
            "grande_categoria": st.column_config.TextColumn(
                "Grande categoria", disabled=True, width="small",
                help="vem amarrada à categoria; mude em Configurações"),
            "categoria": st.column_config.SelectboxColumn(
                "Categoria", options=estado.lista_categorias(), required=True),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=config.TIPOS),
            "natureza": st.column_config.SelectboxColumn("Natureza", options=config.NATUREZAS),
            "origem": st.column_config.TextColumn("Origem", disabled=True, width="small"),
            "parcela": st.column_config.TextColumn("Parc.", disabled=True, width="small"),
            "observacao": st.column_config.TextColumn("Observação", width="medium"),
        },
    )

    col_salvar, col_info = st.columns([1, 4])
    with col_salvar:
        if st.button("Salvar alterações", type="primary", width="stretch"):
            original = para_editar.set_index("id")
            novo = editado.set_index("id")
            campos = ["categoria", "tipo", "natureza", "observacao"]

            naturezas_padrao = estado.naturezas_por_categoria()
            alteracoes = []
            herdadas: list[str] = []
            for id_lanc in novo.index:
                if id_lanc not in original.index:
                    continue
                mudou = {
                    campo: novo.loc[id_lanc, campo]
                    for campo in campos
                    if str(novo.loc[id_lanc, campo]) != str(original.loc[id_lanc, campo])
                }
                if "categoria" in mudou and "natureza" not in mudou:
                    padrao = naturezas_padrao.get(str(mudou["categoria"]))
                    if padrao and padrao != str(original.loc[id_lanc, "natureza"]):
                        mudou["natureza"] = padrao
                        herdadas.append(
                            f"«{mudou['categoria']}» → natureza {padrao}")
                if mudou:
                    alteracoes.append((id_lanc, mudou))

            if not alteracoes:
                st.info("Nada mudou.")
            else:
                for id_lanc, mudou in alteracoes:
                    atribuicoes = ", ".join(f"{campo} = ?" for campo in mudou)
                    banco.executar(
                        f"UPDATE lancamentos SET {atribuicoes}, atualizado_em = ? "
                        f"WHERE id = ?",
                        (*mudou.values(), banco.agora(), int(id_lanc)),
                    )
                estado.limpar_cache()
                c.recado(f"{len(alteracoes)} lançamento(s) atualizado(s).")
                if herdadas:
                    st.info(
                        "**A natureza acompanhou a categoria** em "
                        f"{len(herdadas)} lançamento(s): "
                        + "; ".join(sorted(set(herdadas)))
                        + ". Se algum deles for exceção, mude a natureza à mão."
                    )
                st.rerun()

    with col_info:
        st.caption(
            "Corrigir a categoria aqui muda **só este lançamento**. Para que "
            "os próximos venham certos sozinhos, cadastre a palavra-chave na "
            "tela de **Regras**."
        )


if not filtrado.empty:
    with st.expander("Trocar a categoria de todos os lançamentos filtrados"):
        st.caption(
            f"Isto altera os **{len(filtrado)} lançamentos** que estão passando "
            "pelos filtros acima. Útil depois de descobrir que uma loja inteira "
            "estava na categoria errada."
        )
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            nova_categoria = st.selectbox(
                "Nova categoria", estado.lista_categorias(), key="massa_cat")
        with col2:
            novo_tipo = st.selectbox(
                "Novo tipo", ["(não mudar)"] + config.TIPOS, key="massa_tipo")
        with col3:
            st.markdown("<br>", unsafe_allow_html=True)
            confirmar = st.button("Aplicar", key="massa_aplicar")

        if confirmar:
            ids = [int(i) for i in filtrado["id"].tolist()]
            marcadores = ",".join("?" * len(ids))
            padrao_massa = estado.naturezas_por_categoria().get(nova_categoria)
            if padrao_massa:
                banco.executar(
                    f"UPDATE lancamentos SET categoria = ?, natureza = ?, "
                    f"atualizado_em = ? WHERE id IN ({marcadores})",
                    (nova_categoria, padrao_massa, banco.agora(), *ids),
                )
            else:
                banco.executar(
                    f"UPDATE lancamentos SET categoria = ?, atualizado_em = ? "
                    f"WHERE id IN ({marcadores})",
                    (nova_categoria, banco.agora(), *ids),
                )
            if novo_tipo != "(não mudar)":
                banco.executar(
                    f"UPDATE lancamentos SET tipo = ? WHERE id IN ({marcadores})",
                    (novo_tipo, *ids),
                )
            estado.limpar_cache()
            c.recado(
                f"{len(ids)} lançamentos movidos para «{nova_categoria}»"
                + (f", com natureza **{padrao_massa}**." if padrao_massa else ".")
            )
            st.rerun()


st.markdown("---")
st.markdown("### Novo lançamento manual")
st.caption(
    "Para o que não aparece em fatura nem em extrato: dinheiro vivo, um Pix "
    "de outro banco, uma divisão de conta com alguém."
)

with st.form("form_lancamento_manual", clear_on_submit=True):
    linha1 = st.columns([2, 3, 2])
    with linha1[0]:
        data_manual = st.date_input("Data", format="DD/MM/YYYY")
    with linha1[1]:
        descricao_manual = st.text_input("Descrição", placeholder="ex: Almoço com a equipe")
    with linha1[2]:
        valor_manual = st.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")

    linha2 = st.columns([2, 2, 2, 2])
    with linha2[0]:
        natureza_manual = st.selectbox("Natureza", config.NATUREZAS)
    with linha2[1]:
        categoria_manual = st.selectbox("Categoria", estado.lista_categorias())
    with linha2[2]:
        tipo_manual = st.selectbox("Tipo", config.TIPOS, index=1)
    with linha2[3]:
        parcelas_manual = st.number_input("Repetir por N meses", min_value=1,
                                          max_value=60, value=1, step=1)

    observacao_manual = st.text_input("Observação (opcional)")
    enviado = st.form_submit_button("Adicionar lançamento", type="primary")

if enviado:
    if not descricao_manual.strip() or valor_manual <= 0:
        st.error("Preencha a descrição e um valor maior que zero.")
    else:
        from financas.formato import chave_hash, somar_meses

        entrada = natureza_manual in (config.NATUREZA_RECEITA,
                                      config.NATUREZA_RECEITA_EXTRA)
        valor_com_sinal = valor_manual if entrada else -valor_manual

        mes_base = mes_de(data_manual)
        carimbo = banco.agora()
        registros = []

        for numero in range(1, int(parcelas_manual) + 1):
            mes_lancamento = somar_meses(mes_base, numero - 1)
            id_unico = chave_hash(
                "MANUAL", mes_lancamento, data_manual.isoformat(),
                descricao_manual.strip(), valor_com_sinal, numero,
            )
            registros.append((
                id_unico, data_manual.isoformat(), None, mes_lancamento,
                descricao_manual.strip(), None, valor_com_sinal,
                categoria_manual, tipo_manual, natureza_manual,
                config.ORIGEM_MANUAL, None,
                numero, int(parcelas_manual),
                None, None, None,
                observacao_manual.strip() or None, "lançamento manual",
                carimbo, carimbo,
            ))

        antes = banco.contar("lancamentos")
        banco.executar_muitos(
            """INSERT OR IGNORE INTO lancamentos
               (id_unico, data, hora, mes_competencia, descricao, portador, valor,
                categoria, tipo, natureza, origem, conta_id,
                parcela_atual, parcela_total, chave_parcelamento,
                fitid, saldo_apos, observacao, regra_aplicada,
                criado_em, atualizado_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            registros,
        )
        gravados = banco.contar("lancamentos") - antes
        estado.limpar_cache()

        if gravados:
            texto_meses = (f" em {parcelas_manual} meses"
                           if parcelas_manual > 1 else "")
            c.recado(f"{gravados} lançamento(s) adicionado(s){texto_meses}.")
            st.rerun()
        else:
            st.warning("Esse lançamento já existia (mesma data, descrição e valor).")


st.markdown("---")
col_exportar, col_apagar = st.columns(2)

with col_exportar:
    st.markdown("**Exportar o recorte filtrado**")
    if not filtrado.empty:
        colunas_exportar = ["data", "mes_competencia", "descricao", "portador",
                            "valor", "categoria", "grande_categoria", "tipo",
                            "natureza", "origem", "parcela_atual",
                            "parcela_total", "observacao"]
        exportavel = filtrado[colunas_exportar]

        csv_bytes = exportavel.to_csv(
            index=False, sep=";", decimal=",", encoding="utf-8-sig"
        ).encode("utf-8-sig")
        st.download_button(
            "Baixar CSV", csv_bytes,
            file_name=f"lancamentos_{mes_filtro}.csv",
            mime="text/csv", width="stretch",
        )

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as escritor:
            exportavel.to_excel(escritor, index=False, sheet_name="Lançamentos")
        st.download_button(
            "Baixar Excel", buffer.getvalue(),
            file_name=f"lancamentos_{mes_filtro}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

with col_apagar:
    st.markdown("**Apagar um lançamento**")
    st.caption("Digite o `id` que aparece na primeira coluna da tabela.")
    col_id, col_botao = st.columns([2, 1])
    with col_id:
        id_apagar = st.number_input("id", min_value=0, step=1,
                                    label_visibility="collapsed")
    with col_botao:
        if st.button("Apagar", key="apagar_lanc"):
            if id_apagar <= 0:
                st.error("Informe um id válido.")
            else:
                alvo = banco.consultar_um(
                    "SELECT descricao, valor FROM lancamentos WHERE id = ?",
                    (int(id_apagar),),
                )
                if alvo is None:
                    st.error(f"Não existe lançamento com id {int(id_apagar)}.")
                else:
                    banco.executar("DELETE FROM lancamentos WHERE id = ?",
                                   (int(id_apagar),))
                    estado.limpar_cache()
                    c.recado(
                        f"Apagado: {alvo['descricao']} ({fmt_brl_md(alvo['valor'])})")
                    st.rerun()

c.rodape_atualizado(len(filtrado), mes_filtro if mes_filtro != "Todos" else "")
