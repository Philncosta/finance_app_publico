"""
importar.py — Trazer fatura, extrato CSV e extrato OFX para dentro do sistema.
==============================================================================

O FLUXO DA TELA
---------------
    1. Voce sobe um arquivo (ou escolhe da pasta)
    2. O app le, deduplica e sugere a categoria de cada linha
    3. VOCE REVISA na tabela e corrige o que quiser
    4. Clica em Importar — so ai entra no banco
    5. Um backup e gerado automaticamente

A ETAPA 3 E A RAZAO DE ESTA TELA EXISTIR. Importar direto seria mais rapido,
mas classificacao automatica erra, e erro que entra sem ser visto vira numero
errado no painel meses depois. A revisao custa 30 segundos e evita isso.

SOBRE O ESTADO ENTRE CLIQUES
----------------------------
Lembre que o Streamlit roda o script inteiro a cada clique. Se a previa
ficasse numa variavel normal, ela sumiria assim que voce mexesse em qualquer
coisa. Por isso ela e guardada em `st.session_state` (via `estado.guardar`),
que sobrevive aos reruns.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from financas import backup, banco, config, importador
from financas.calculos import investimentos as calc_inv
from financas.formato import fmt_num, rotulo_mes, somar_meses
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado

CHAVE_PREVIA = "importar_previa"
CHAVE_META = "importar_meta"
CHAVE_XP = "importar_previa_xp"

c.cabecalho("Importar arquivos",
            "Fatura CSV · Extrato CSV · Extrato OFX · Planilhas da corretora")


with st.expander("Como exportar os arquivos do banco", expanded=False):
    st.markdown(
        """
**Fatura do cartão (CSV)**
No app ou site do banco, abra a fatura e procure por *Exportar* ou *Baixar*.
Escolha CSV. O arquivo vem com nome tipo `Fatura2026-01-05.csv` — **mantenha
esse nome**, porque é dele que sai o mês de competência da fatura.

**Extrato da conta (CSV ou OFX)**
Em *Extrato*, escolha o período e exporte. Se o banco oferecer as duas opções,
**prefira o OFX**: ele traz um código único por transação, o que torna a
detecção de duplicata perfeita.

**Períodos que se sobrepõem não são problema.** O app compara cada transação
com o que já existe — inclusive quando a mesma transação vem de um arquivo CSV
e de um OFX diferentes. Nada é contado duas vezes.
        """
    )


aba_upload, aba_pasta = st.tabs(["Enviar arquivo", "Ler de uma pasta"])

arquivo_para_ler = None

with aba_upload:
    enviados = st.file_uploader(
        "Solte aqui a fatura, o extrato ou a planilha da corretora",
        type=["csv", "ofx", "xlsx"],
        accept_multiple_files=False,
        key="uploader_arquivo",
    )
    if enviados is not None:
        arquivo_para_ler = ("bytes", enviados.getvalue(), enviados.name)

with aba_pasta:
    st.caption(
        "Útil quando os arquivos já estão numa pasta do computador — por "
        "exemplo a pasta de Downloads ou uma pasta do OneDrive."
    )
    pasta_padrao = banco.obter_parametro_pasta(
        "pasta_importacao", config.PASTA_ARQUIVOS_ORIGINAIS)
    pasta_texto = st.text_input("Pasta", value=pasta_padrao, key="pasta_importacao")

    if pasta_texto and pasta_texto != pasta_padrao:
        banco.definir_parametro("pasta_importacao", pasta_texto)

    da_pasta = estado.arquivos_da_pasta(
        pasta_texto, estado.impressao_da_pasta(pasta_texto))

    if da_pasta.empty:
        st.info(
            "Nenhum arquivo importável encontrado nessa pasta. São aceitos: "
            + ", ".join(f"`{e}`" for e in importador.EXTENSOES_ACEITAS) + "."
        )
    else:
        faltando = da_pasta[~da_pasta["importado"]]
        ja_entraram = da_pasta[da_pasta["importado"]]

        c.estatisticas([
            {"rotulo": "Na pasta", "valor": fmt_num(len(da_pasta), 0)},
            {"rotulo": "Já passaram por aqui",
             "valor": fmt_num(len(ja_entraram), 0),
             "cor": "verde" if len(ja_entraram) else None,
             "dica": "A marca vem do mesmo hash que a deduplicação usa — "
                     "arquivo renomeado continua sendo reconhecido."},
            {"rotulo": "Nunca abertos", "valor": fmt_num(len(faltando), 0),
             "cor": "amarela" if len(faltando) else None,
             "dica": "Nunca abertos POR ESTA TELA. Não quer dizer que falte "
                     "dado: o conteúdo pode ter entrado por outro arquivo que "
                     "cobria o mesmo período."},
        ])

        c.nota(
            "<b>\"Nunca aberto\" não é o mesmo que \"falta importar\".</b> "
            "Esta lista registra ARQUIVOS que passaram por esta tela, não "
            "linhas que existem no banco. Os seus extratos se sobrepõem — o "
            "mesmo gasto costuma aparecer em dois ou três arquivos —, então "
            "um arquivo que nunca foi aberto pode estar 100% duplicado. "
            "Abrir para conferir é barato: a deduplicação mostra quantas "
            "linhas são novas antes de gravar qualquer coisa."
        )

        somente_novos = st.checkbox(
            "Mostrar só os que nunca foram abertos", value=bool(len(faltando)),
            key="pasta_so_novos")
        visiveis = faltando if somente_novos else da_pasta

        if visiveis.empty:
            st.success("Todos os arquivos desta pasta já passaram por aqui.")
        else:
            escolhido = st.selectbox(
                "Arquivo", visiveis["caminho"].tolist(),
                format_func=lambda caminho: next(
                    (f"{'✓ ' if linha['importado'] else ''}{linha['nome']}"
                     f"  ·  {linha['modificado']}"
                     for _, linha in visiveis.iterrows()
                     if linha["caminho"] == caminho), caminho),
                key="arquivo_da_pasta",
            )
            escolhido_linha = visiveis[visiveis["caminho"] == escolhido]
            if not escolhido_linha.empty and escolhido_linha["importado"].iloc[0]:
                st.warning(
                    f"Este arquivo já foi importado em "
                    f"**{escolhido_linha['importado_em'].iloc[0]}**. Ler de novo "
                    f"é seguro — as duplicatas são detectadas —, mas "
                    f"provavelmente não vai trazer nada novo."
                )
            if st.button("Ler este arquivo", type="primary", key="ler_da_pasta"):
                arquivo_para_ler = ("caminho", None, str(escolhido))

        with st.expander(f"Todos os arquivos da pasta ({len(da_pasta)})"):
            visao_pasta = da_pasta[["nome", "importado", "tipo", "modificado",
                                    "importado_em", "linhas_novas"]].copy()
            priv.tabela(
                visao_pasta.rename(columns={
                    "nome": "Arquivo", "importado": "Já aberto",
                    "tipo": "Tipo", "modificado": "Modificado",
                    "importado_em": "Importado em",
                    "linhas_novas": "Linhas novas"}),
                hide_index=True, width="stretch",
                column_config={
                    "Já aberto": st.column_config.CheckboxColumn(
                        "Já aberto", disabled=True),
                    "Linhas novas": st.column_config.NumberColumn(
                        "Linhas novas", format="%d"),
                },
                key="tabela_pasta")

    cobertura = estado.cobertura_de_importacao()
    if not cobertura.empty:
        c.secao("O que já entrou de cada tipo",
                "um tipo que sumiu há dois meses salta aos olhos")
        priv.tabela(
            cobertura.rename(columns={
                "tipo": "Tipo", "arquivos": "Arquivos",
                "linhas_novas": "Linhas novas",
                "ultimo_arquivo": "Último arquivo",
                "ultima_importacao": "Última importação"}),
            hide_index=True, width="stretch",
            column_config={
                "Arquivos": st.column_config.NumberColumn("Arquivos", format="%d"),
                "Linhas novas": st.column_config.NumberColumn(
                    "Linhas novas", format="%d"),
            },
            key="tabela_cobertura")
        st.caption(
            "O app não sabe quando a sua fatura fecha nem quando você baixa a "
            "posição — então ele não inventa um calendário. O que ele mostra é "
            "quando cada tipo entrou pela última vez."
        )


if arquivo_para_ler:
    modo, conteudo, nome = arquivo_para_ler

    vencimento_informado = (estado.pegar("mes_fatura_manual") or "").strip()
    competencia_informada = (somar_meses(vencimento_informado, -1)
                             if vencimento_informado else None)

    with st.spinner("Lendo o arquivo..."):
        if modo == "bytes":
            resultado, tipo = importador.ler(
                dados_bytes=conteudo, nome_arquivo=nome,
                mes_competencia=competencia_informada)
            digest = hashlib.sha256(conteudo).hexdigest()
        else:
            resultado, tipo = importador.ler(
                caminho=nome, mes_competencia=competencia_informada)
            from financas.formato import hash_arquivo
            digest = hash_arquivo(nome)
            nome = Path(nome).name

    ja_visto = importador.ja_importado_por_hash(digest)
    if ja_visto:
        st.warning(
            f"Este arquivo já foi importado em **{ja_visto['importado_em']}** "
            f"({ja_visto['linhas_novas']} linhas novas na época). Pode importar "
            f"de novo — as duplicatas serão detectadas."
        )

    if resultado.erros:
        for erro in resultado.erros:
            st.error(erro)
        if tipo == importador.TIPO_FATURA or "mes da fatura" in " ".join(resultado.erros):
            st.info(
                "Se este é um arquivo de fatura, informe abaixo o mês de "
                "**vencimento** — a data que aparece no nome do arquivo e na "
                "própria fatura — e envie o arquivo de novo."
            )
            st.text_input("Mês de vencimento da fatura (AAAA-MM)",
                          key="mes_fatura_manual", placeholder="2026-09")
            if competencia_informada:
                st.caption(
                    f"Vencimento {rotulo_mes(vencimento_informado)} → as compras "
                    f"contam em **{rotulo_mes(competencia_informada)}**, que é o "
                    f"mês em que foram feitas."
                )
    elif tipo in (importador.TIPO_POSICAO_XP, importador.TIPO_EXTRATO_XP):
        estado.guardar(CHAVE_XP, {"resultado": resultado, "tipo": tipo,
                                  "nome": nome, "sha256": digest})
        estado.guardar(CHAVE_PREVIA, None)
    else:
        previa = importador.preparar(resultado, estado.conjunto_regras())
        estado.guardar(CHAVE_PREVIA, previa)
        estado.guardar(CHAVE_XP, None)
        estado.guardar(CHAVE_META, {
            "nome": nome, "tipo": tipo, "sha256": digest,
            "meta": resultado.meta, "avisos": resultado.avisos,
        })


previa_xp = estado.pegar(CHAVE_XP)

if previa_xp is not None:
    resultado_xp = previa_xp["resultado"]
    tipo_xp = previa_xp["tipo"]
    meta_xp = resultado_xp.meta

    st.markdown("---")
    st.markdown(f"### Revisão · `{previa_xp['nome']}`")
    st.caption(" · ".join(p for p in [meta_xp.get("tipo"),
                                      f"conta {meta_xp.get('conta')}"
                                      if meta_xp.get("conta") else "",
                                      meta_xp.get("periodo")] if p))

    for aviso in resultado_xp.avisos[:5]:
        st.warning(aviso)

    if tipo_xp == importador.TIPO_POSICAO_XP:
        c.linha_kpis([
            {"rotulo": "Ativos", "valor": str(len(resultado_xp.linhas)),
             "pequeno": True},
            {"rotulo": "Total investido",
             "valor": fmt_brl(meta_xp.get("soma_ativos")),
             "cor": "verde", "pequeno": True},
            {"rotulo": "Saldo em conta",
             "valor": fmt_brl(meta_xp.get("saldo_disponivel")),
             "pequeno": True, "ajuda": "parado, sem aplicação"},
            {"rotulo": "Mês", "valor": rotulo_mes(meta_xp.get("mes_competencia")),
             "cor": "azul", "pequeno": True},
        ])

        st.caption(
            "Confira se o total acima é o mesmo que a corretora mostra. "
            "Se bater, a carteira foi lida inteira."
        )

        tabela_xp = pd.DataFrame([
            {
                "Ativo": linha["nome"],
                "Classe": (calc_inv.classificar_papel(
                    linha["nome"], linha.get("grupo"))[1] or "— sem classe —"),
                "Valor": linha["valor"],
                "Aplicado": linha.get("valor_aplicado"),
                "Ganho": (None if linha.get("valor_aplicado") is None
                          else linha["valor"] - linha["valor_aplicado"]),
                "Vencimento": linha.get("vencimento") or "",
            }
            for linha in resultado_xp.linhas
        ])
        priv.tabela(
            tabela_xp, hide_index=True, width="stretch",
            column_config={
                "Valor": c.config_moeda("Valor"),
                "Aplicado": c.config_moeda("Aplicado"),
                "Ganho": c.config_moeda("Ganho"),
            },
        )

        sem_classe = int((tabela_xp["Classe"] == "— sem classe —").sum())
        if sem_classe:
            st.info(
                f"{sem_classe} ativo(s) não foram classificados pelo nome. "
                f"Eles entram assim mesmo, e você pode definir a classe em "
                f"**Investimentos → Cadastro**. Ações e stock picks caem aqui, "
                f"porque não há padrão no nome que os identifique."
            )

        c.nota(
            "Importar a posição também <strong>corrige a tela de "
            "Patrimônio</strong>: o total lido vira o saldo aplicado do mês, "
            "no lugar da estimativa que o app fazia a partir do que saiu da "
            "conta corrente."
        )

    else:
        por_tipo = {}
        for linha in resultado_xp.linhas:
            alvo = por_tipo.setdefault(linha["tipo_movimento"], [0, 0.0])
            alvo[0] += 1
            alvo[1] += linha["valor"]

        c.linha_kpis([
            {"rotulo": "Movimentações", "valor": str(len(resultado_xp.linhas)),
             "pequeno": True},
            {"rotulo": "Aportes",
             "valor": fmt_brl(por_tipo.get("aporte", [0, 0])[1]),
             "cor": "verde", "pequeno": True},
            {"rotulo": "Compras",
             "valor": fmt_brl(por_tipo.get("compra", [0, 0])[1]),
             "pequeno": True},
            {"rotulo": "Período", "valor": f"{meta_xp.get('inicio')} a "
                                           f"{meta_xp.get('fim')}",
             "cor": "azul", "pequeno": True},
        ])

        priv.tabela(
            pd.DataFrame([
                {"Data": linha["data"], "Lançamento": linha["descricao"],
                 "Tipo": linha["tipo_movimento"], "Valor": linha["valor"],
                 "Saldo depois": linha.get("saldo_apos")}
                for linha in resultado_xp.linhas
            ]),
            hide_index=True, width="stretch",
            column_config={
                "Valor": c.config_moeda("Valor"),
                "Saldo depois": c.config_moeda("Saldo depois"),
            },
        )

        c.nota(
            "Nada disto entra no Dashboard. Comprar um título não é despesa — "
            "é dinheiro mudando de lugar dentro do seu patrimônio. Estas "
            "linhas vão para a aba <strong>Movimentações</strong> da tela de "
            "Investimentos."
        )

    if st.button("Importar para o banco", type="primary", key="btn_importar_xp"):
        with st.spinner("Gravando..."):
            resumo_xp = importador.gravar_arquivo_xp(
                resultado_xp, tipo_xp, previa_xp["nome"], previa_xp["sha256"])
            info_backup = backup.criar(sufixo="import")
            caminho_backup = (info_backup["caminho_nuvem"]
                              or info_backup["caminho_local"])

        if tipo_xp == importador.TIPO_POSICAO_XP:
            st.success(
                f"Posição de {rotulo_mes(resumo_xp['mes'])} importada: "
                f"{resumo_xp['criados']} ativo(s) cadastrado(s) e "
                f"{resumo_xp['atualizados']} atualizado(s)."
            )
            for novo in resumo_xp.get("novos", []):
                st.caption(f"novo: {novo}")
        else:
            st.success(
                f"{resumo_xp['gravados']} movimentação(ões) gravada(s)."
                + (f" {resumo_xp['ignorados']} já existiam e foram ignoradas."
                   if resumo_xp["ignorados"] else "")
            )
        if caminho_backup:
            st.caption(f"Backup automático: `{caminho_backup}`")

        estado.guardar(CHAVE_XP, None)
        estado.limpar_cache()
        st.rerun()


previa = estado.pegar(CHAVE_PREVIA)
meta_arquivo = estado.pegar(CHAVE_META, {})

if previa is not None and not previa.empty:
    st.markdown("---")
    resumo = importador.resumo_previa(previa)
    meta = meta_arquivo.get("meta", {})

    st.markdown(f"### Revisão · `{meta_arquivo.get('nome', '')}`")

    descricao = [meta.get("tipo", "")]
    if meta.get("banco"):
        descricao.append(meta["banco"])
    if meta.get("periodo"):
        descricao.append(meta["periodo"])
    if meta.get("mes_competencia"):
        descricao.append(f"competência {rotulo_mes(meta['mes_competencia'])}")
    st.caption(" · ".join(p for p in descricao if p))

    c.linha_kpis([
        {"rotulo": "Lidas", "valor": str(resumo["total"]), "pequeno": True},
        {"rotulo": "Novas", "valor": str(resumo["novos"]),
         "cor": "verde", "pequeno": True,
         "ajuda": "serão gravadas"},
        {"rotulo": "Já existiam", "valor": str(resumo["duplicados"]),
         "cor": "amarela", "pequeno": True,
         "ajuda": "ignoradas automaticamente"},
        {"rotulo": "Sem regra", "valor": str(resumo["sem_regra"]),
         "cor": "azul", "pequeno": True,
         "ajuda": "caíram no padrão; confira"},
    ])

    if resumo["novos"]:
        st.caption(
            f"Entradas: {fmt_brl_md(resumo['entradas'])} · "
            f"Saídas: {fmt_brl_md(resumo['saidas'])} · "
            f"Líquido: {fmt_brl_md(resumo['valor_novos'])}"
        )

    for aviso in meta_arquivo.get("avisos", [])[:5]:
        st.warning(aviso)

    if resumo["duplicados"]:
        cruzadas = int((previa["motivo"] == "já existe vinda de outro arquivo").sum())
        detalhe = (
            f" — sendo **{cruzadas}** que já tinham entrado por outro arquivo "
            f"(um extrato CSV e um OFX que se sobrepõem, por exemplo)"
            if cruzadas else ""
        )
        st.info(
            f"**{resumo['duplicados']}** linha(s) já estão no banco{detalhe}. "
            f"Elas vêm desmarcadas e não serão gravadas."
        )

    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        exibir = st.radio(
            "Mostrar", ["Só as novas", "Tudo", "Só sem regra"],
            key="filtro_previa", horizontal=False,
        )

    visao = previa
    if exibir == "Só as novas":
        visao = previa[previa["status"] == importador.STATUS_NOVO]
    elif exibir == "Só sem regra":
        visao = previa[previa["regra"] == ""]

    with col_f2:
        st.caption(
            "Marque ou desmarque a coluna **Importar** para escolher linha a "
            "linha. Corrija Categoria, Tipo e Natureza aqui se a sugestão "
            "estiver errada — a correção é gravada junto."
        )

    colunas_visiveis = ["importar", "status", "data", "descricao", "valor",
                        "categoria", "tipo", "natureza", "regra", "motivo"]
    editado = priv.editor(
        visao[colunas_visiveis],
        hide_index=True,
        width="stretch",
        height=440,
        key="editor_previa",
        column_config={
            "importar": st.column_config.CheckboxColumn("Importar", width="small"),
            "status": st.column_config.TextColumn("Status", disabled=True, width="small"),
            "data": st.column_config.TextColumn("Data", disabled=True, width="small"),
            "descricao": st.column_config.TextColumn("Descrição", disabled=True, width="large"),
            "valor": st.column_config.NumberColumn("Valor", format="R$ %.2f", disabled=True),
            "categoria": st.column_config.SelectboxColumn(
                "Categoria", options=estado.lista_categorias(), required=True),
            "tipo": st.column_config.SelectboxColumn("Tipo", options=config.TIPOS),
            "natureza": st.column_config.SelectboxColumn("Natureza", options=config.NATUREZAS),
            "regra": st.column_config.TextColumn("Regra aplicada", disabled=True, width="medium"),
            "motivo": st.column_config.TextColumn("Por que duplicada", disabled=True, width="medium"),
        },
    )

    col_a, col_b, col_c = st.columns([2, 2, 3])
    with col_a:
        importar_agora = st.button("Importar selecionadas", type="primary",
                                   width="stretch")
    with col_b:
        if st.button("Cancelar", width="stretch"):
            estado.esquecer(CHAVE_PREVIA)
            estado.esquecer(CHAVE_META)
            st.rerun()
    with col_c:
        fazer_backup = st.checkbox("Gerar backup depois de importar", value=True)

    if importar_agora:
        completa = previa.copy()
        completa.update(editado)

        com_resultado = importador.gravar(
            completa,
            nome_arquivo=meta_arquivo.get("nome", ""),
            sha256=meta_arquivo.get("sha256", ""),
            tipo=meta_arquivo.get("tipo", ""),
        )
        estado.limpar_cache()

        if com_resultado["gravados"]:
            st.success(
                f"**{com_resultado['gravados']}** lançamento(s) importado(s) "
                f"com sucesso."
            )
            if com_resultado["duplicados_no_banco"]:
                st.warning(
                    f"{com_resultado['duplicados_no_banco']} linha(s) foram "
                    f"recusadas pelo banco por já existirem. Isso é a segunda "
                    f"camada de proteção agindo — nada foi duplicado."
                )
            if fazer_backup:
                with st.spinner("Gerando backup..."):
                    info = backup.criar(sufixo="import")
                destino = info["caminho_nuvem"] or info["caminho_local"]
                st.info(f"Backup gravado em `{destino}`")
        else:
            st.warning(
                "Nada foi importado — todas as linhas selecionadas já existiam "
                "no banco."
            )

        estado.esquecer(CHAVE_PREVIA)
        estado.esquecer(CHAVE_META)

elif previa is not None and previa.empty:
    st.warning("O arquivo foi lido, mas não tinha nenhuma transação válida.")


st.markdown("---")
st.markdown("### Importações anteriores")

historico = importador.historico(30)
if historico.empty:
    st.caption("Nenhuma importação registrada ainda.")
else:
    priv.tabela(
        historico.rename(columns={
            "nome": "Arquivo", "tipo": "Tipo", "mes_referencia": "Mês",
            "linhas_lidas": "Lidas", "linhas_novas": "Novas",
            "linhas_dup": "Duplicadas", "importado_em": "Quando",
        }),
        hide_index=True, width="stretch", height=260,
    )
