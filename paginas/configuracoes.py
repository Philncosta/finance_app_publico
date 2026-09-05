"""
configuracoes.py — Categorias, contas, backup e manutencao.
==============================================================================

O QUE FICA AQUI
---------------
Tudo que voce ajusta uma vez e raramente volta a mexer:

    Categorias   o vocabulario do sistema (e a cor de cada grupo)
    Contas       de onde o dinheiro sai e entra
    Backup       gerar, listar e restaurar
    Manutencao   informacoes do banco e limpeza

A PARTE MAIS IMPORTANTE E O BACKUP
----------------------------------
O banco (`financas.db`) fica LOCAL, na pasta do projeto. O que vai para a
nuvem e um `.zip` com um CSV por tabela.

Por que nao mandar o `.db` direto para o OneDrive? Porque banco de dados
aberto e sincronizacao automatica nao combinam: enquanto o app roda, o SQLite
mantem arquivos auxiliares com escritas ainda nao gravadas, e o OneDrive pode
copiar o arquivo no meio do caminho. O `.zip` e um arquivo fechado — depois de
gravado nao muda mais — e ainda por cima e legivel no Excel se um dia este
programa nao existir.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from financas import backup, banco, config
from financas import regras as motor_regras
from financas.formato import fmt_num, vazio
from ui import componentes as c
from ui import estado
from ui import privacidade as priv


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


c.cabecalho("Configurações", "Categorias, contas, backup e manutenção")
c.mostrar_recado()

aba_categorias, aba_contas, aba_backup, aba_manutencao = st.tabs(
    ["Categorias", "Contas", "Backup e restauração", "Manutenção"]
)


def _detectar_renomeacoes(antes, depois) -> list[tuple[str, str]]:
    """Compara a tabela antes e depois da edicao e devolve o que foi renomeado.

    O `st.data_editor` PRESERVA O INDICE das linhas que voce editou — linhas
    novas ganham indices que nao existiam antes. Entao um indice presente nos
    dois lados, com `nome` diferente, e uma renomeacao; um indice so no lado
    de depois e uma criacao.

    E a unica forma de distinguir "renomeei Manutencao para Moto" de "criei
    Moto e apaguei Manutencao" — o texto sozinho nao conta essa diferenca.
    """
    if antes is None or antes.empty:
        return []
    renomeadas = []
    for indice, linha_antes in antes.iterrows():
        if indice not in depois.index:
            continue
        nome_antes = str(linha_antes.get("nome") or "").strip()
        nome_depois = str(depois.loc[indice].get("nome") or "").strip()
        if nome_antes and nome_depois and nome_antes != nome_depois:
            renomeadas.append((nome_antes, nome_depois))
    return renomeadas


with aba_categorias:
    st.markdown("### Grandes categorias")
    st.caption(
        "O agrupamento largo, usado no orçamento e nos gráficos. A **cor** "
        "definida aqui é usada em TODAS as telas — é o que permite reconhecer "
        "uma categoria de bate-olho sem ler a legenda."
    )

    grandes = banco.df(
        "SELECT nome, cor, ordem FROM grandes_categorias ORDER BY ordem, nome")

    editado_grandes = priv.editor(
        grandes, hide_index=True, width="stretch", num_rows="dynamic",
        key="editor_grandes",
        column_config={
            "nome": st.column_config.TextColumn("Nome", required=True),
            "cor": st.column_config.TextColumn(
                "Cor", help="código hexadecimal, ex: #4F46E5", width="small"),
            "ordem": st.column_config.NumberColumn("Ordem", min_value=0, step=1,
                                                   width="small"),
        },
    )

    if st.button("Salvar grandes categorias", type="primary"):
        renomeados = _detectar_renomeacoes(grandes, editado_grandes)
        movidos = 0
        for antigo_nome, novo_nome in renomeados:
            for _, quantidade in banco.renomear_grande_categoria(
                    antigo_nome, novo_nome).items():
                movidos += quantidade

        for indice, linha in editado_grandes.iterrows():
            nome = _texto_ou_none(linha.get("nome")) or ""
            if not nome:
                continue
            banco.executar(
                "INSERT INTO grandes_categorias (nome, cor, ordem) VALUES (?,?,?) "
                "ON CONFLICT(nome) DO UPDATE SET cor=excluded.cor, ordem=excluded.ordem",
                (nome, _texto_ou_none(linha.get("cor")) or config.CORES_TEMA["neutra"],
                 int(_numero_ou(linha.get("ordem"), 0))),
            )
        estado.limpar_cache()
        if renomeados:
            nomes = ", ".join(f"{a} → {b}" for a, b in renomeados)
            st.success(f"Renomeado: {nomes}. {movidos} registro(s) movidos junto.")
        else:
            st.success("Grandes categorias salvas.")
        st.rerun()

    st.markdown("---")
    st.markdown("### Categorias")
    st.caption(
        "O detalhe. Cada categoria pertence a uma grande categoria e tem uma "
        "**natureza padrão** — que é o que o sistema assume quando uma regra "
        "da fatura aponta para ela."
    )

    categorias = banco.df(
        "SELECT nome, grande_categoria, natureza_padrao, ativa, ordem "
        "FROM categorias ORDER BY ordem, nome"
    )
    categorias["ativa"] = categorias["ativa"].astype(bool)

    editado_categorias = priv.editor(
        categorias, hide_index=True, width="stretch", num_rows="dynamic",
        height=480, key="editor_categorias",
        column_config={
            "nome": st.column_config.TextColumn("Categoria", required=True),
            "grande_categoria": st.column_config.SelectboxColumn(
                "Grande categoria", options=estado.lista_grandes_categorias(),
                required=True),
            "natureza_padrao": st.column_config.SelectboxColumn(
                "Natureza padrão", options=config.NATUREZAS),
            "ativa": st.column_config.CheckboxColumn(
                "Ativa", help="desmarcada, some dos menus mas o histórico continua"),
            "ordem": st.column_config.NumberColumn("Ordem", min_value=0, step=1,
                                                   width="small"),
        },
    )

    if st.button("Salvar categorias", type="primary", key="salvar_categorias"):
        renomeadas = _detectar_renomeacoes(categorias, editado_categorias)
        movidos = 0
        for antigo_nome, novo_nome in renomeadas:
            for _, quantidade in banco.renomear_categoria(
                    antigo_nome, novo_nome).items():
                movidos += quantidade

        for _, linha in editado_categorias.iterrows():
            nome = _texto_ou_none(linha.get("nome")) or ""
            if not nome:
                continue
            banco.executar(
                """INSERT INTO categorias
                   (nome, grande_categoria, natureza_padrao, ativa, ordem)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(nome) DO UPDATE SET
                     grande_categoria=excluded.grande_categoria,
                     natureza_padrao=excluded.natureza_padrao,
                     ativa=excluded.ativa, ordem=excluded.ordem""",
                (nome, linha.get("grande_categoria"),
                 _texto_ou_none(linha.get("natureza_padrao")) or config.NATUREZA_DESPESA,
                 1 if linha.get("ativa", True) else 0,
                 int(_numero_ou(linha.get("ordem"), 0))),
            )
        estado.limpar_cache()
        if renomeadas:
            nomes = ", ".join(f"{a} → {b}" for a, b in renomeadas)
            st.success(
                f"Renomeado: {nomes}. **{movidos} registro(s)** foram movidos "
                f"junto — lançamentos, gastos fixos e regras.")
        else:
            st.success("Categorias salvas.")
        st.rerun()

    with st.expander("Quantos lançamentos usam cada categoria"):
        uso = banco.df(
            """SELECT categoria, COUNT(*) AS quantidade,
                      SUM(CASE WHEN valor < 0 THEN -valor ELSE 0 END) AS total_gasto
               FROM lancamentos WHERE categoria IS NOT NULL
               GROUP BY categoria ORDER BY quantidade DESC"""
        )
        if uso.empty:
            st.caption("Nenhum lançamento ainda.")
        else:
            priv.tabela(
                uso.rename(columns={
                    "categoria": "Categoria", "quantidade": "Lançamentos",
                    "total_gasto": "Total gasto",
                }),
                hide_index=True, width="stretch", height=320,
                column_config={"Total gasto": c.config_moeda("Total gasto")},
            )
            st.caption(
                "Categoria com zero lançamento pode ser desativada sem "
                "prejuízo. Categoria muito usada com nome genérico (como "
                "«Outros») é sinal de que faltam regras."
            )


with aba_contas:
    st.markdown("### Contas e cartões")
    st.caption(
        "De onde o dinheiro sai e entra. O cartão de crédito também é uma "
        "conta aqui — isso permite ter mais de um cartão no futuro sem "
        "mudar nada na estrutura."
    )

    contas = banco.df("SELECT id, nome, tipo, banco, ativo FROM contas ORDER BY id")
    contas["ativo"] = contas["ativo"].astype(bool)

    editado_contas = priv.editor(
        contas, hide_index=True, width="stretch", num_rows="dynamic",
        key="editor_contas",
        column_config={
            "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
            "nome": st.column_config.TextColumn("Nome", required=True),
            "tipo": st.column_config.SelectboxColumn(
                "Tipo", options=["Conta Corrente", "Cartão de Crédito",
                                 "Investimento", "Dinheiro"]),
            "banco": st.column_config.TextColumn("Instituição"),
            "ativo": st.column_config.CheckboxColumn("Ativa"),
        },
    )

    if st.button("Salvar contas", type="primary"):
        for _, linha in editado_contas.iterrows():
            nome = _texto_ou_none(linha.get("nome")) or ""
            if not nome:
                continue
            valores = (nome, _texto_ou_none(linha.get("tipo")) or "Conta Corrente",
                       _texto_ou_none(linha.get("banco")),
                       1 if linha.get("ativo", True) else 0)
            if pd.notna(linha.get("id")):
                banco.executar(
                    "UPDATE contas SET nome=?, tipo=?, banco=?, ativo=? WHERE id=?",
                    (*valores, int(linha["id"])),
                )
            else:
                banco.executar(
                    "INSERT INTO contas (nome, tipo, banco, ativo) VALUES (?,?,?,?)",
                    valores,
                )
        estado.limpar_cache()
        c.recado("Contas salvas.")
        st.rerun()

    st.caption(
        "**Atenção:** os nomes «Conta Corrente XP» e «Cartão XP» são usados "
        "pela importação para ligar cada arquivo à sua conta. Se renomear, "
        "os lançamentos antigos continuam ligados corretamente, mas as "
        "próximas importações ficarão sem conta até você ajustar o código."
    )

    st.markdown("---")
    st.markdown("### Cartão adicional com categoria própria")
    c.nota(
        "Quando outra pessoa usa um cartão adicional no seu nome, as compras "
        "dela se misturam com as suas — e <strong>nenhuma palavra-chave "
        "separa</strong>, porque ela compra nos mesmos lugares. O que separa é "
        "a coluna <strong>portador</strong>, que a fatura já traz. "
        "Aqui você diz qual portador vai para qual categoria."
    )

    mapa = motor_regras.portadores_com_categoria()
    if mapa:
        for trecho, categoria in sorted(mapa.items()):
            col_nome, col_cat, col_botao = st.columns([2, 2, 1])
            col_nome.text_input("Portador", value=trecho, disabled=True,
                                key=f"port_nome_{trecho}")
            col_cat.text_input("Vai para", value=categoria, disabled=True,
                               key=f"port_cat_{trecho}")
            with col_botao:
                st.write("")
                if st.button("Remover", key=f"port_del_{trecho}"):
                    motor_regras.definir_portador_categoria(trecho, None)
                    estado.limpar_cache()
                    st.rerun()
    else:
        st.caption("Nenhum portador com categoria própria.")

    c.secao("Dinheiro que não é seu")
    atual_terceiros = config.categoria_terceiros()
    col_terceiros, col_nota = st.columns([2, 3], gap="medium")
    with col_terceiros:
        escolhida = st.text_input(
            "Categoria de dinheiro de terceiros", value=atual_terceiros,
            key="cfg_categoria_terceiros",
            help="Lançamentos nesta categoria ficam fora de receita, fora de "
                 "despesa e fora do patrimônio.")
        if escolhida.strip() and escolhida.strip() != atual_terceiros:
            banco.definir_parametro("categoria_terceiros", escolhida.strip())
            estado.limpar_cache()
            st.success(f"Passa a valer para **{escolhida.strip()}**.")
    with col_nota:
        c.nota(
            "É dinheiro que está na sua conta mas pertence a outra pessoa — "
            "de alguém que pediu para você investir por ele, por exemplo. Ele "
            "não é receita quando entra, não é despesa quando sai, e "
            "<b>não entra no seu patrimônio</b> em momento nenhum.<br><br>"
            "O nome fica aqui, e não no código, por dois motivos: ele "
            "costuma ser o nome de uma pessoa, e quem clonar este projeto "
            "tem outro terceiro — ou nenhum.")

    with st.form("novo_portador"):
        col_a, col_b = st.columns([2, 2])
        trecho_novo = col_a.text_input(
            "Trecho do nome do portador",
            placeholder="Um pedaço do nome, como vem na fatura",
            help="Um pedaço do nome do portador do cartão adicional, sem "
                 "acento, do jeito que aparece na fatura. O trecho basta: um "
                 "primeiro nome já pega o nome completo.")
        categoria_nova = col_b.selectbox(
            "Categoria", estado.lista_categorias(), key="port_cat_nova")
        if st.form_submit_button("Adicionar", type="primary"):
            if trecho_novo.strip():
                motor_regras.definir_portador_categoria(
                    trecho_novo.strip(), categoria_nova)
                estado.limpar_cache()
                c.recado(
                    f"Compras de '{trecho_novo.strip()}' passam a cair em "
                    f"{categoria_nova} nas próximas importações. Os "
                    f"lançamentos que já estão no banco continuam como estão — "
                    f"use a Triagem ou a tela de Lançamentos para ajustá-los."
                )
                st.rerun()
            else:
                st.warning("Informe um trecho do nome do portador.")


with aba_backup:
    st.markdown("### Onde o backup é gravado")

    pasta_atual = banco.obter_parametro(
        "pasta_backup", str(config.PASTA_BACKUP_NUVEM_PADRAO))

    col_pasta, col_botao = st.columns([3, 1])
    with col_pasta:
        nova_pasta = st.text_input(
            "Pasta na nuvem", value=pasta_atual,
            help="Uma pasta que o OneDrive (ou outro serviço) sincroniza.",
        )
    with col_botao:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Salvar pasta", width="stretch"):
            banco.definir_parametro("pasta_backup", nova_pasta)
            c.recado("Pasta salva.")
            st.rerun()

    caminho_nuvem = Path(pasta_atual)
    if caminho_nuvem.exists():
        st.success(f"Pasta encontrada: `{pasta_atual}`")
    else:
        st.warning(
            f"A pasta `{pasta_atual}` ainda não existe. Ela será criada no "
            f"primeiro backup. Se o caminho estiver errado, o backup local "
            f"acontece do mesmo jeito — só a cópia na nuvem é pulada."
        )

    c.nota(
        "O banco (<code>financas.db</code>) fica <strong>local</strong>. O que "
        "vai para a nuvem é um <strong>.zip com um CSV por tabela</strong>. "
        "Isso evita corrupção (arquivo fechado nunca é sincronizado pela "
        "metade) e mantém seus dados legíveis no Excel mesmo sem este programa."
    )

    st.markdown("### Gerar backup agora")
    col_gerar, col_info = st.columns([1, 3])
    with col_gerar:
        if st.button("Fazer backup", type="primary", width="stretch"):
            with st.spinner("Gerando..."):
                info = backup.criar()
            st.success(
                f"Backup com {info['linhas']} linhas de {info['tabelas']} "
                f"tabelas ({info['tamanho_kb']:.0f} KB)."
            )
            st.caption(f"Local: `{info['caminho_local']}`")
            if info["caminho_nuvem"]:
                st.caption(f"Nuvem: `{info['caminho_nuvem']}`")
            else:
                st.warning("Não foi possível copiar para a pasta da nuvem.")
    with col_info:
        st.caption(
            f"Um backup também é gerado automaticamente ao final de toda "
            f"importação. Os {config.MAX_BACKUPS} mais recentes são mantidos; "
            f"os mais antigos são apagados sozinhos."
        )

    st.markdown("### Backups disponíveis")
    lista = backup.listar()

    if not lista:
        st.caption("Nenhum backup ainda.")
    else:
        tabela_backups = pd.DataFrame([
            {
                "Arquivo": b["nome"],
                "Quando": b["quando"].strftime("%d/%m/%Y %H:%M"),
                "Tamanho (KB)": round(b["tamanho_kb"], 1),
                "Pasta": b["local"],
            }
            for b in lista
        ])
        priv.tabela(tabela_backups, hide_index=True, width="stretch", height=280)

        st.markdown("### Restaurar um backup")
        st.caption(
            "Antes de restaurar, o app copia o banco atual para "
            "`dados/backups/antes_de_....db`. Se algo der errado, o estado "
            "anterior está guardado."
        )

        col_escolha, col_modo = st.columns([3, 2])
        with col_escolha:
            escolhido = st.selectbox(
                "Backup", [b["caminho"] for b in lista],
                format_func=lambda caminho: Path(caminho).name,
                key="backup_escolhido",
            )
        with col_modo:
            modo = st.radio(
                "Modo", ["Substituir tudo", "Juntar com o atual"],
                key="modo_restauracao",
                help="Substituir apaga o conteúdo atual. Juntar acrescenta o "
                     "que faltar, ignorando duplicatas.",
            )

        conteudo = backup.conteudo(escolhido)
        if conteudo:
            resumo_texto = " · ".join(
                f"{tabela}: {linhas}" for tabela, linhas in conteudo.items()
                if linhas > 0
            )
            st.caption(f"Este backup contém — {resumo_texto}")

        confirmacao = st.text_input(
            "Para confirmar, digite RESTAURAR", key="confirma_restauracao",
            help="Uma trava contra clique acidental.",
        )
        if st.button("Restaurar backup", type="primary",
                     disabled=confirmacao.strip().upper() != "RESTAURAR"):
            with st.spinner("Restaurando..."):
                resultado = backup.restaurar(
                    escolhido, apagar_antes=(modo == "Substituir tudo"))
            estado.limpar_cache()
            st.success(
                f"Restaurado. O banco tem agora "
                f"{resultado['tabelas'].get('lancamentos', 0)} lançamentos."
            )
            st.caption(f"Cópia do estado anterior: `{resultado['copia_de_seguranca']}`")


with aba_manutencao:
    st.markdown("### Informações do banco")

    caminho_banco = config.CAMINHO_BANCO
    tamanho_kb = caminho_banco.stat().st_size / 1024 if caminho_banco.exists() else 0

    c.linha_kpis([
        {"rotulo": "Lançamentos", "valor": fmt_num(banco.contar("lancamentos")),
         "pequeno": True},
        {"rotulo": "Tamanho do banco", "valor": f"{tamanho_kb:.0f} KB", "pequeno": True},
        {"rotulo": "Tabelas", "valor": str(len(banco.tabelas())), "pequeno": True},
        {"rotulo": "Regras", "valor": str(banco.contar("regras_fatura")
                                          + banco.contar("regras_extrato")),
         "pequeno": True},
    ])

    st.caption(f"Arquivo: `{caminho_banco}`")

    st.markdown("**Linhas por tabela**")
    priv.tabela(
        pd.DataFrame([
            {"Tabela": tabela, "Linhas": banco.contar(tabela)}
            for tabela in banco.tabelas()
        ]),
        hide_index=True, width="stretch", height=300,
    )

    st.markdown("---")
    st.markdown("### Parâmetros salvos")
    parametros = banco.df("SELECT chave, valor FROM parametros ORDER BY chave")
    editado_parametros = priv.editor(
        parametros, hide_index=True, width="stretch", key="editor_parametros",
        column_config={
            "chave": st.column_config.TextColumn("Parâmetro", disabled=True),
            "valor": st.column_config.TextColumn("Valor"),
        },
    )
    if st.button("Salvar parâmetros"):
        for _, linha in editado_parametros.iterrows():
            banco.definir_parametro(linha["chave"], linha["valor"])
        estado.limpar_cache()
        c.recado("Parâmetros salvos.")
        st.rerun()

    st.markdown("---")
    st.markdown("### Limpeza")
    st.caption(
        "Ações que apagam dados. Todas fazem uma cópia de segurança antes, "
        "mas confira se você tem um backup recente."
    )

    with st.expander("Apagar TODOS os lançamentos"):
        st.warning(
            "Isto apaga o histórico inteiro. Categorias, regras, gastos fixos "
            "e metas são preservados. Faça um backup antes."
        )
        confirmacao_limpeza = st.text_input(
            "Digite APAGAR TUDO para confirmar", key="confirma_limpeza")
        if st.button("Apagar todos os lançamentos", type="primary",
                     disabled=confirmacao_limpeza.strip().upper() != "APAGAR TUDO"):
            copia = banco.copia_de_seguranca_rapida()
            quantidade = banco.contar("lancamentos")
            banco.executar("DELETE FROM lancamentos")
            banco.executar("DELETE FROM arquivos_importados")
            estado.limpar_cache()
            st.success(f"{quantidade} lançamentos apagados.")
            st.caption(f"Cópia de segurança: `{copia}`")

    with st.expander("Compactar o banco (VACUUM)"):
        st.caption(
            "Depois de apagar muitos registros, o arquivo continua ocupando o "
            "mesmo espaço. O VACUUM reorganiza e libera o espaço não usado. "
            "É seguro e não altera nenhum dado."
        )
        if st.button("Compactar"):
            antes_kb = caminho_banco.stat().st_size / 1024
            import sqlite3
            conexao = sqlite3.connect(str(caminho_banco), isolation_level=None)
            conexao.execute("VACUUM")
            conexao.close()
            depois_kb = caminho_banco.stat().st_size / 1024
            st.success(
                f"Banco compactado: {antes_kb:.0f} KB → {depois_kb:.0f} KB "
                f"({antes_kb - depois_kb:.0f} KB liberados)."
            )
