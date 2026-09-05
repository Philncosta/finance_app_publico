"""
metas_compras.py — Objetivos de poupanca e lista de desejos.
==============================================================================

DUAS ABAS, DUAS NATUREZAS DE VONTADE
------------------------------------
    Metas            objetivos que exigem PLANO (reserva, entrada de imóvel)
    Futuras compras  vontades que so esperam PRECO (um notebook, um tênis)

O QUE LIGA AS DUAS: item caro nao e compra, e projeto. Acima do valor de corte
(R$ ···· por padrao), um item da lista de desejos pode virar meta com um
clique — levando o preco como valor alvo.

O NUMERO MAIS HONESTO DA TELA
-----------------------------
A "data prevista real". Voce define um prazo desejado, mas o app calcula
quando voce chega DE VERDADE no ritmo de aporte atual. Se voce guarda R$ ····
por mes para uma meta de R$ ····, a data prevista fica a 14 anos — mesmo que
o prazo desejado diga 2. Ver os dois lado a lado e o que transforma uma lista
de desejos num plano.

O VELOCIMETRO, E POR QUE ELE FICOU NO LUGAR DO TEXTO
-----------------------------------------------------
A pergunta que a tela precisa responder num relance e "estou no ritmo ou
nao?". Ela existia so como uma palavra ("atrasada") escondida num aviso. Agora
e um meio-circulo com a marca do 100% no meio: bate o olho e ve de que lado da
marca voce esta, sem ler numero nenhum.

Cada meta com prazo mostra o RITMO DO APORTE (o que voce decidiu guardar
dividido pelo que o prazo exige). Meta sem prazo nao tem ritmo — nao ha data
para cumprir —, entao mostra o PROGRESSO. O titulo do velocimetro diz qual
dos dois esta na tela, porque o mesmo desenho significando duas coisas sem
avisar seria pior que texto nenhum.

EDITAR E APAGAR: PERTO, E COM CONFIRMACAO
------------------------------------------
Cada meta se edita no proprio cartao (o lapis), e se apaga por um dialogo que
escreve o nome dela por extenso. A tabela de todas as metas continua existindo
no "modo avançado", para edicao em massa — mas com uma diferenca: la, remover
a linha nao apaga mais em silencio. A tela conta quantas sumiram, diz quais, e
so executa o DELETE se voce marcar a caixa. Exclusao implicita e o tipo de
comportamento que a pessoa so descobre no dia em que perde alguma coisa.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from financas import banco, precos
from financas.calculos import compras, investimentos as invest, metas, planejamento
from financas.formato import (fmt_num, fmt_pct, mes_para_indice, parse_data,
                              rotulo_mes, somar_meses, vazio)
from ui.privacidade import fmt_brl, fmt_brl_md
from ui import privacidade as priv
from ui import componentes as c
from ui import estado, graficos

def _texto_ou_none(valor) -> str | None:
    """Converte para texto limpo, ou `None` quando vazio.

    NUNCA use `str(x or "").strip()` para limpar um campo vindo de
    `st.data_editor`. Uma celula vazia chega como `NaN` do pandas, e
    `NaN or ""` devolve `NaN` (nao ""), porque `bool(NaN)` e `True`. O
    resultado e `str(NaN)` == a STRING "nan" gravada no banco — um prazo
    vazio virava, de verdade, o texto "nan" na coluna. `vazio()` (que trata
    None, NaN e a propria string "nan" como a mesma coisa) e a unica forma
    segura de checar isso.
    """
    return None if vazio(valor) else str(valor).strip() or None


def _numero_ou(valor, padrao: float) -> float:
    """Como `_texto_ou_none`, para numero: uma linha nova em branco tem `NaN`
    onde devia ter o padrao, e `NaN or 0` continua sendo `NaN` — mesma
    armadilha, agora num campo numerico em vez de texto."""
    return padrao if vazio(valor) else float(valor)


# ---------------------------------------------------------------------------
# Metas: gravar, editar num formulario, apagar com confirmacao
# ---------------------------------------------------------------------------

def _gravar_meta(valores: dict, id_meta: int | None = None) -> None:
    """INSERT ou UPDATE de UMA meta, a partir do formulario do cartao.

    Meta nova entra no FIM da fila (`ordem` = maior + 1), e nao no comeco:
    quem acabou de cadastrar ainda nao decidiu a prioridade dela, e empurrar
    o item novo para cima das metas ja pensadas mudaria a ordem que voce
    montou sem voce ter pedido.
    """
    campos = (
        valores["meta"], valores["tipo"], valores["valor_alvo"],
        valores["ja_acumulado"], valores["prazo"], valores["aporte_definido"],
        valores["prioridade"], valores["status"], valores["observacao"],
        valores["vinculo"],
    )
    if id_meta is None:
        ultima = banco.consultar_um("SELECT COALESCE(MAX(ordem), 0) AS m FROM metas")
        banco.executar(
            """INSERT INTO metas (meta, tipo, valor_alvo, ja_acumulado, prazo,
               aporte_definido, prioridade, status, observacao, vinculo, ordem)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (*campos, int(ultima["m"]) + 1),
        )
    else:
        banco.executar(
            """UPDATE metas SET meta=?, tipo=?, valor_alvo=?, ja_acumulado=?,
               prazo=?, aporte_definido=?, prioridade=?, status=?,
               observacao=?, vinculo=? WHERE id=?""",
            (*campos, int(id_meta)),
        )


def _campo_de_dinheiro(rotulo: str, valor: float, chave: str, travado: bool,
                       passo: float = 100.0, ajuda: str = "") -> float:
    """Um campo em R$ que SOME quando os valores estao escondidos.

    Some, e nao "fica desabilitado": um `number_input` desabilitado continua
    imprimindo o numero na tela — seria esconder o valor no grafico e na
    tabela e deixa-lo escrito no formulario ao lado.

    E quando some, DEVOLVE O VALOR GUARDADO, nao zero. E a mesma regra do
    `privacidade.editor`: um recurso de esconder valores nunca pode alterar
    valores. Salvar com o olhinho ligado regrava o mesmo numero.
    """
    if travado:
        st.caption(f"{rotulo.replace(' (R$)', '')}: **{fmt_brl_md(valor)}**"
                   + (f" — {ajuda}" if ajuda else ""))
        return valor
    return float(st.number_input(rotulo, min_value=0.0, step=passo,
                                 value=valor, key=chave,
                                 help=ajuda or None))


def _formulario_meta(prefixo: str, meta=None) -> dict | None:
    """Desenha os campos de uma meta e devolve os valores quando voce salva.

    Devolve `None` enquanto o botao nao foi clicado, e `None` tambem quando a
    validacao reprova — nesse caso o proprio formulario ja mostrou o motivo.

    O MESMO FORMULARIO SERVE PARA CRIAR E PARA EDITAR: `meta=None` nasce
    vazio. Um segundo formulario "de cadastro" acabaria divergindo do de
    edicao no primeiro campo novo.

    RECEBA A LINHA DO CADASTRO, NAO A CALCULADA. Numa meta vinculada ao
    patrimonio, `metas.calcular()` SUBSTITUI `ja_acumulado` pelo valor real da
    carteira. Se o formulario lesse dali, salvar gravaria esse valor derivado
    por cima do numero que voce digitou — e no dia em que voce desmarcasse o
    vinculo, encontraria a foto da carteira no lugar do seu numero. Editar le
    do cadastro; so a TELA mostra o derivado.

    E COM O OLHINHO LIGADO OS CAMPOS EM R$ FICAM TRAVADOS, pelo mesmo motivo
    que a tabela mascarada trava as colunas de dinheiro: um formulario que
    mostrasse R$ ···· num `number_input` seria uma porta aberta ao
    lado de uma porta trancada.
    """
    escondendo = priv.ocultando()

    def de(campo, padrao=None):
        if meta is None:
            return padrao
        valor = meta.get(campo)
        return padrao if vazio(valor) else valor

    if escondendo and meta is None:
        # Meta NOVA e caso a parte: nao ha valor guardado para preservar, entao
        # os campos travados nao estao escondendo nada — estao zerados. Dizer
        # "R$ ••••" aqui faria parecer que existe um numero por tras da mascara.
        st.warning("Com os valores escondidos, a meta nasce com **R$ 0,00** nos "
                   "campos de dinheiro. Clique em «Mostrar valores» na barra "
                   "lateral para preenchê-los agora, ou preencha depois pelo "
                   "lápis do cartão.")
    elif escondendo:
        st.caption("🙈 Valores escondidos: os campos em R$ estão travados. "
                   "Clique em «Mostrar valores» na barra lateral para editá-los.")

    nome = st.text_input("Meta", value=str(de("meta", "") or ""),
                         key=f"{prefixo}_nome")

    coluna_a, coluna_b = st.columns(2)
    with coluna_a:
        tipo_atual = str(de("tipo", metas.TIPOS[0]))
        tipo = st.selectbox(
            "Tipo", metas.TIPOS, key=f"{prefixo}_tipo",
            index=metas.TIPOS.index(tipo_atual) if tipo_atual in metas.TIPOS else 0)
        valor_alvo = _campo_de_dinheiro(
            "Valor alvo (R$)", float(de("valor_alvo", 0.0) or 0.0),
            f"{prefixo}_alvo", escondendo, passo=500.0)
        prazo = st.text_input(
            "Prazo desejado (AAAA-MM)", value=str(de("prazo", "") or ""),
            key=f"{prefixo}_prazo",
            help="deixe vazio para uma meta sem data — é uma resposta válida")
    with coluna_b:
        prioridade_atual = str(de("prioridade", "Média"))
        prioridade = st.selectbox(
            "Prioridade", metas.PRIORIDADES, key=f"{prefixo}_prioridade",
            index=(metas.PRIORIDADES.index(prioridade_atual)
                   if prioridade_atual in metas.PRIORIDADES else 1))
        aporte = _campo_de_dinheiro(
            "Aporte por mês (R$)", float(de("aporte_definido", 0.0) or 0.0),
            f"{prefixo}_aporte", escondendo, passo=50.0)
        status_atual = str(de("status", "Ativa"))
        status = st.selectbox(
            "Status", metas.STATUS_POSSIVEIS, key=f"{prefixo}_status",
            index=(metas.STATUS_POSSIVEIS.index(status_atual)
                   if status_atual in metas.STATUS_POSSIVEIS else 0))

    vinculada = st.checkbox(
        "Ligar ao patrimônio investido",
        value=(meta is not None
               and meta.get("vinculo") == metas.VINCULO_PATRIMONIO_INVESTIDO),
        key=f"{prefixo}_vinculo",
        help="Quando marcado, \"Já acumulado\" passa a ser o valor real da sua "
             "carteira agora — o mesmo número que o Dashboard mostra em "
             "\"Investido\". A meta se atualiza sozinha a cada aporte, resgate "
             "ou variação de mercado, em vez de depender de você digitar.")

    ja_acumulado = _campo_de_dinheiro(
        "Já acumulado (R$)", float(de("ja_acumulado", 0.0) or 0.0),
        f"{prefixo}_acumulado", escondendo or vinculada, passo=100.0,
        ajuda="ignorado enquanto a meta estiver ligada ao patrimônio")

    observacao = st.text_area(
        "Observação", value=str(de("observacao", "") or ""),
        key=f"{prefixo}_obs", height=70)

    if not st.button("Salvar", type="primary", key=f"{prefixo}_salvar",
                     width="stretch"):
        return None

    if not nome.strip():
        st.error("A meta precisa de um nome.")
        return None
    if prazo.strip() and mes_para_indice(prazo.strip()) is None:
        st.error(f"«{prazo}» não é um mês no formato AAAA-MM.")
        return None

    return {
        "meta": nome.strip(),
        "tipo": tipo,
        "valor_alvo": float(valor_alvo),
        "ja_acumulado": float(ja_acumulado),
        "prazo": prazo.strip() or None,
        "aporte_definido": float(aporte),
        "prioridade": prioridade,
        "status": status,
        "observacao": observacao.strip() or None,
        "vinculo": metas.VINCULO_PATRIMONIO_INVESTIDO if vinculada else None,
    }


@st.dialog("Excluir meta")
def _dialogo_excluir_meta(id_meta: int, nome: str) -> None:
    """Pergunta antes de apagar, escrevendo o nome da meta por extenso.

    O nome escrito importa: "Confirma excluir?" nao protege de nada quando
    voce clicou no lixo da linha errada. Ler «Entrada do apartamento» na
    caixa e o que faz o dedo parar.
    """
    st.write(f"Apagar a meta **{nome}**?")
    st.caption("Isso não pode ser desfeito. Se a ideia é só tirá-la da conta, "
               "mude o status para «Concluída» ou «Pausada» — assim ela sai "
               "dos totais e o histórico fica.")

    coluna_sim, coluna_nao = st.columns(2)
    with coluna_sim:
        if st.button("Apagar", type="primary", width="stretch",
                     key=f"confirma_apagar_{id_meta}"):
            banco.executar("DELETE FROM metas WHERE id = ?", (int(id_meta),))
            estado.limpar_cache()
            c.recado(f"Meta «{nome}» apagada.", "aviso")
            st.rerun()
    with coluna_nao:
        if st.button("Cancelar", width="stretch", key=f"cancela_apagar_{id_meta}"):
            st.rerun()


def _velocimetro_da_meta(meta) -> tuple[object, str]:
    """Escolhe o que o meio-circulo do cartao mede, e devolve (figura, legenda).

    Meta COM prazo mede ritmo: o aporte que voce definiu contra o que o prazo
    exige. Meta SEM prazo nao tem ritmo a cumprir, entao mede progresso. O
    titulo diz qual dos dois esta desenhado.
    """
    falta = float(meta.get("falta") or 0)
    necessario = float(meta.get("aporte_necessario") or 0)
    definido = float(meta.get("aporte_definido") or 0)
    tem_prazo = not vazio(meta.get("prazo"))

    if falta <= 0:
        return (graficos.velocimetro(1.0, "Progresso", teto=1.0, julgar=False),
                f"Alvo: {fmt_brl_md(meta.get('valor_alvo'))}  \nMeta cumprida")

    if tem_prazo and necessario > 0:
        return (graficos.velocimetro(definido / necessario, "Ritmo do aporte"),
                f"Necessário: {fmt_brl_md(necessario)}/mês  \n"
                f"Definido: {fmt_brl_md(definido)}/mês")

    return (graficos.velocimetro(float(meta.get("pct_concluido") or 0),
                                 "Progresso", teto=1.0, julgar=False),
            f"Alvo: {fmt_brl_md(meta.get('valor_alvo'))}  \n"
            f"Já tem: {fmt_brl_md(meta.get('ja_acumulado'))}")


df = estado.lancamentos()

c.cabecalho("Metas e compras", "Onde você quer chegar, e o que quer comprar")

# O aviso do run anterior. Tem de vir ANTES de qualquer coisa que possa
# chamar st.rerun() de novo — ver a docstring de c.recado().
c.mostrar_recado()

mes = estado.seletor_de_mes_topo()
if mes is None:
    mes = "2026-01"

projecao = planejamento.projecao_caixa(df, mes, 12) if not df.empty else pd.DataFrame()

aba_metas, aba_compras = st.tabs(["Metas", "Futuras compras"])


with aba_metas:
    cadastro_metas = estado.cadastro_metas()
    patrimonio_investido = estado.carteira_conciliacao(mes)["carteira_cadastrada"]
    calculadas = metas.calcular(cadastro_metas, mes,
                                 patrimonio_investido=patrimonio_investido)

    capacidade_sugerida = metas.capacidade_sugerida(projecao)
    capacidade_salva = banco.obter_parametro_num("capacidade_aporte_mensal", 0.0)

    col1, col2 = st.columns([1, 3])
    with col1:
        capacidade = st.number_input(
            "Quanto você consegue guardar por mês (R$)",
            min_value=0.0,
            value=float(round(capacidade_salva or capacidade_sugerida, 2)),
            step=100.0,
        )
        if capacidade != capacidade_salva:
            banco.definir_parametro("capacidade_aporte_mensal", capacidade)
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption(
            f"Sugestão baseada na sua projeção de caixa: "
            f"**{fmt_brl_md(capacidade_sugerida)}** por mês (mediana do saldo "
            f"projetado para os próximos 12 meses). Ajuste se você souber que "
            f"consegue mais ou menos que isso."
        )

    resumo = metas.resumo(calculadas, capacidade)

    c.linha_kpis([
        {"rotulo": "Metas ativas", "valor": str(resumo["n_metas"]),
         "ajuda": f"{resumo['n_atrasadas']} fora do prazo" if resumo["n_atrasadas"] else "todas no ritmo",
         "cor": "vermelha" if resumo["n_atrasadas"] else "verde"},
        {"rotulo": "Total a juntar", "valor": fmt_brl(resumo["total_falta"]),
         "ajuda": f"de {fmt_brl(resumo['total_alvo'])} no total"},
        {"rotulo": "Aporte necessário/mês", "valor": fmt_brl(resumo["aporte_necessario_total"]),
         "ajuda": "para cumprir TODOS os prazos desejados",
         "cor": "vermelha" if not resumo["viavel"] else "verde"},
        {"rotulo": "Sua capacidade", "valor": fmt_brl(capacidade),
         "delta": ("cobre tudo" if resumo["viavel"]
                   else f"faltam {fmt_brl(resumo['deficit'])}"),
         "delta_positivo": resumo["viavel"],
         "cor": "verde" if resumo["viavel"] else "amarela"},
    ])

    if resumo["n_metas"]:
        st.markdown("### O plano, em três leituras")
        painel = st.columns(3)
        with painel[0]:
            cobertura = (capacidade / resumo["aporte_necessario_total"]
                         if resumo["aporte_necessario_total"] else 1.0)
            with c.painel(chave="gauge_cobertura"):
                priv.grafico(
                    graficos.velocimetro(cobertura, "Cobertura da capacidade"),
                    width="stretch", key="metas_gauge_cobertura")
            st.caption(f"Necessário: {fmt_brl_md(resumo['aporte_necessario_total'])}/mês  \n"
                       f"Capacidade: {fmt_brl_md(capacidade)}/mês")
        with painel[1]:
            with c.painel(chave="gauge_progresso"):
                priv.grafico(
                    graficos.velocimetro(resumo["pct_geral"], "Progresso geral",
                                         teto=1.0, julgar=False),
                    width="stretch", key="metas_gauge_progresso")
            st.caption(f"Alvo: {fmt_brl_md(resumo['total_alvo'])}  \n"
                       f"Já tem: {fmt_brl_md(resumo['total_acumulado'])}")
        with painel[2]:
            no_ritmo = resumo["n_metas"] - resumo["n_atrasadas"]
            with c.painel(chave="gauge_ritmo"):
                priv.grafico(
                    graficos.velocimetro(no_ritmo / resumo["n_metas"],
                                         "Metas no ritmo", teto=1.0),
                    width="stretch", key="metas_gauge_ritmo")
            st.caption(f"Metas ativas: {resumo['n_metas']}  \n"
                       f"No ritmo: {no_ritmo}")

    if not resumo["viavel"] and resumo["n_metas"]:
        c.nota(
            f"Para cumprir todos os prazos você precisaria guardar "
            f"<strong>{fmt_brl(resumo['aporte_necessario_total'])}</strong> por "
            f"mês, mas a sua folga é de "
            f"<strong>{fmt_brl(capacidade)}</strong>. "
            f"Faltam <strong>{fmt_brl(resumo['deficit'])}</strong>. "
            f"Há três saídas: esticar os prazos, cortar gastos no "
            f"<strong>Planejamento</strong>, ou priorizar algumas metas e "
            f"deixar outras para depois."
        )

    titulo_lista, acao_nova = st.columns([3, 1])
    with titulo_lista:
        st.markdown("### Suas metas")
    with acao_nova:
        with st.popover("➕ Nova meta", width="stretch"):
            novos_valores = _formulario_meta("nova_meta")
            if novos_valores:
                _gravar_meta(novos_valores)
                estado.limpar_cache()
                c.recado(f"Meta «{novos_valores['meta']}» criada.")
                st.rerun()

    if calculadas.empty:
        c.aviso_vazio(
            "Nenhuma meta cadastrada ainda.",
            "Comece pela reserva de emergência: valor alvo de 6 meses de "
            "despesa, sem prazo. Use o botão «Nova meta» aqui em cima.")
    else:
        total_metas = len(calculadas)
        for posicao, (_, meta) in enumerate(calculadas.iterrows()):
            id_meta = int(meta["id"])
            with st.container(border=True, key=f"cartao_meta_{id_meta}"):
                medidor, corpo, acoes = st.columns([2, 5, 1.1])

                with medidor:
                    figura, legenda = _velocimetro_da_meta(meta)
                    priv.grafico(figura, width="stretch",
                                 key=f"gauge_meta_{id_meta}")
                    st.caption(legenda)

                with corpo:
                    st.markdown(f"**{meta['meta']}**")
                    st.caption(
                        f"{meta.get('tipo') or 'Meta'} · prioridade "
                        f"{meta.get('prioridade')} · {meta.get('status', 'Ativa')}"
                        + (" · ligada ao patrimônio"
                           if meta.get("vinculo") == metas.VINCULO_PATRIMONIO_INVESTIDO
                           else ""))

                    # Os MESMOS tres numeros, na mesma ordem — sem a moldura
                    # de cada um. `st.metric` desenha uma caixa com borda, e
                    # tres delas dentro do cartao da meta faziam caixa dentro
                    # de caixa dentro de caixa. `estatisticas` existe
                    # exatamente para o numero de apoio: "a ausencia de borda
                    # e o que os mantem no segundo plano".
                    c.estatisticas([
                        {"rotulo": "Alvo", "valor": fmt_brl(meta["valor_alvo"])},
                        {"rotulo": "Já tem", "valor": fmt_brl(meta["ja_acumulado"])},
                        {"rotulo": "Falta", "valor": fmt_brl(meta["falta"])},
                    ])

                    c.barra(meta["pct_concluido"], cor="primaria")

                    prazo = meta.get("prazo")
                    prevista = meta["data_prevista"]
                    rotulo_previsto = (
                        rotulo_mes(prevista)
                        if isinstance(prevista, str) and len(prevista) == 7
                        else str(prevista)
                    )
                    # A situacao, que era texto com emoji no fim da frase,
                    # vira pastilha. MESMA palavra, MESMO lugar — so a roupa
                    # muda, e a cor passa a dizer o que o emoji dizia.
                    cores_situacao = {
                        "no ritmo": "verde", "concluída": "verde",
                        "atrasada": "vermelha",
                        "sem aporte definido": "amarela",
                        "sem prazo": None,
                    }
                    # `data_prevista` e um mes OU um recado ("concluída", "sem
                    # aporte definido") — e o recado ja aparece no fim da
                    # linha. Escrever "chega em concluída ... concluída" seria
                    # a mesma palavra duas vezes na mesma frase.
                    partes_situacao = [
                        f"{fmt_pct(meta['pct_concluido'])} concluído",
                        f"prazo desejado "
                        f"{'sem data' if vazio(prazo) else rotulo_mes(prazo)}",
                    ]
                    if isinstance(prevista, str) and len(prevista) == 7:
                        partes_situacao.append(
                            f"chega em <strong>{rotulo_previsto}</strong>")
                    partes_situacao.append(
                        c.selo(str(meta["situacao"]),
                               cores_situacao.get(meta["situacao"])))
                    st.markdown(
                        f'<div class="legenda-cartao">'
                        f'{" · ".join(partes_situacao)}</div>',
                        unsafe_allow_html=True)

                    if meta["situacao"] == "atrasada":
                        st.warning(
                            f"No ritmo atual você chega em **{rotulo_previsto}**, "
                            f"depois do prazo desejado. Para cumprir o prazo, o "
                            f"aporte teria de subir para "
                            f"{fmt_brl_md(meta['aporte_necessario'])}/mês."
                        )
                    elif meta["situacao"] == "sem aporte definido":
                        st.info(
                            "Nenhum aporte mensal definido — sem isso a meta não "
                            "tem previsão de conclusão. Defina no lápis ao lado."
                        )

                with acoes:
                    with st.popover("✏️", width="stretch", help="editar esta meta"):
                        # A linha do CADASTRO, nao a calculada: ver a docstring
                        # de _formulario_meta. Numa meta vinculada, `meta` aqui
                        # traz o patrimonio real no lugar do `ja_acumulado`
                        # digitado, e salvar gravaria o derivado por cima.
                        bruta = cadastro_metas[
                            cadastro_metas["id"] == id_meta].iloc[0]
                        editados = _formulario_meta(f"edita_{id_meta}", bruta)
                        if editados:
                            _gravar_meta(editados, id_meta)
                            estado.limpar_cache()
                            c.recado(f"Meta «{editados['meta']}» salva.")
                            st.rerun()

                    if st.button("🗑️", key=f"apagar_{id_meta}", width="stretch",
                                 help="apagar esta meta"):
                        _dialogo_excluir_meta(id_meta, str(meta["meta"]))

                    subir, descer = st.columns(2)
                    with subir:
                        if st.button("▲", key=f"sobe_{id_meta}", width="stretch",
                                     disabled=posicao == 0, help="subir na lista"):
                            metas.mover(id_meta, -1)
                            estado.limpar_cache()
                            st.rerun()
                    with descer:
                        if st.button("▼", key=f"desce_{id_meta}", width="stretch",
                                     disabled=posicao == total_metas - 1,
                                     help="descer na lista"):
                            metas.mover(id_meta, +1)
                            estado.limpar_cache()
                            st.rerun()

        with st.expander("Ver todas as metas num gráfico só"):
            priv.grafico(graficos.progresso_metas(calculadas), width="stretch",
                         key="metas_compras_progresso_metas")

    vinculadas = (
        calculadas[calculadas.get("vinculo") == metas.VINCULO_PATRIMONIO_INVESTIDO]
        if not calculadas.empty else pd.DataFrame()
    )
    if not vinculadas.empty:
        meta_mensal = float(vinculadas["aporte_definido"].sum())
        st.markdown("### Aportou o que prometeu?")
        st.caption(
            "O que de fato saiu para a carteira, mês a mês, contra a meta "
            "mensal definida hoje — inclui aportes extras, como o da PLR. "
            "A linha usa o valor atual da meta em todos os meses, porque o "
            "app não guarda quando ela mudou de valor."
        )
        with c.painel(chave="aporte_vs_definido"):
            priv.grafico(
                graficos.aporte_do_mes_vs_meta(invest.movimentacoes(df),
                                               meta_mensal),
                width="stretch", key="metas_aporte_vs_definido",
            )

    if st.button("Distribuir minha capacidade pelas metas",
                 help="Divide o valor que você consegue guardar entre as "
                      "metas com prazo, proporcionalmente ao que cada uma exige."):
        ativas = calculadas[calculadas["situacao"] != "concluída"] \
            if not calculadas.empty else pd.DataFrame()
        # Meta sem prazo exige zero por mes (ver metas.calcular) e por isso
        # nao entra no rateio proporcional: ela levaria fatia nenhuma e o
        # aporte dela seria ZERADO por este botao. Melhor deixa-la de fora e
        # dizer isso do que apagar em silencio o que voce definiu a mao.
        com_prazo = (ativas[ativas["aporte_necessario"] > 0]
                     if not ativas.empty else pd.DataFrame())
        if ativas.empty or capacidade <= 0:
            st.warning("Defina a capacidade mensal e cadastre metas antes.")
        else:
            alvo_do_rateio = com_prazo if not com_prazo.empty else ativas
            total_necessario = float(alvo_do_rateio["aporte_necessario"].sum())
            for _, meta in alvo_do_rateio.iterrows():
                fatia = (
                    meta["aporte_necessario"] / total_necessario
                    if total_necessario else 1 / len(alvo_do_rateio)
                )
                banco.executar(
                    "UPDATE metas SET aporte_definido = ? WHERE id = ?",
                    (round(capacidade * fatia, 2), int(meta["id"])),
                )
            estado.limpar_cache()
            de_fora = len(ativas) - len(alvo_do_rateio)
            c.recado(
                f"{fmt_brl_md(capacidade)} distribuídos entre "
                f"{len(alvo_do_rateio)} metas, proporcionalmente ao que cada "
                f"uma exige."
                + (f" As {de_fora} sem prazo ficaram de fora, com o aporte que "
                   f"você já tinha definido." if de_fora else "")
            )
            st.rerun()

    with st.expander("Modo avançado — editar todas as metas numa tabela"):
        colunas_metas = ["id", "meta", "tipo", "valor_alvo", "ja_acumulado",
                         "prazo", "aporte_definido", "prioridade", "status"]
        if cadastro_metas.empty:
            base_edicao = pd.DataFrame(
                columns=colunas_metas + ["vinculada_ao_patrimonio"])
        else:
            base_edicao = cadastro_metas[colunas_metas].copy()
            base_edicao["vinculada_ao_patrimonio"] = (
                cadastro_metas["vinculo"] == metas.VINCULO_PATRIMONIO_INVESTIDO)
        base_edicao = base_edicao[
            ["id", "meta", "tipo", "valor_alvo", "ja_acumulado",
             "vinculada_ao_patrimonio", "prazo", "aporte_definido",
             "prioridade", "status"]
        ]

        editado_metas = priv.editor(
            base_edicao, hide_index=True, width="stretch", num_rows="dynamic",
            key="editor_metas",
            column_config={
                "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
                "meta": st.column_config.TextColumn("Meta", required=True, width="large"),
                "tipo": st.column_config.SelectboxColumn("Tipo", options=metas.TIPOS),
                "valor_alvo": st.column_config.NumberColumn(
                    "Valor alvo", format="R$ %.2f", min_value=0.0, step=500.0),
                "ja_acumulado": st.column_config.NumberColumn(
                    "Já acumulado", format="R$ %.2f", min_value=0.0, step=100.0,
                    help="Ignorado quando \"Ligar ao patrimônio\" estiver "
                         "marcado — nesse caso o app usa o valor real da "
                         "carteira, não este número."),
                "vinculada_ao_patrimonio": st.column_config.CheckboxColumn(
                    "Ligar ao patrimônio?",
                    help="Quando marcado, \"Já acumulado\" passa a ser o valor "
                         "real da sua carteira agora — o mesmo número que o "
                         "Dashboard mostra em \"Investido\". A meta se atualiza "
                         "sozinha a cada aporte, resgate ou variação de mercado, "
                         "em vez de depender de você digitar."),
                "prazo": st.column_config.TextColumn("Prazo", help="AAAA-MM", width="small"),
                "aporte_definido": st.column_config.NumberColumn(
                    "Aporte/mês", format="R$ %.2f", min_value=0.0, step=50.0),
                "prioridade": st.column_config.SelectboxColumn(
                    "Prioridade", options=metas.PRIORIDADES),
                "status": st.column_config.SelectboxColumn(
                    "Status", options=metas.STATUS_POSSIVEIS),
            },
        )

        sumiram_metas, apagar_metas = c.guarda_de_exclusao(
            editado_metas, cadastro_metas, "meta", "meta",
            "confirmar_exclusao_metas")

        if st.button("Salvar metas", type="primary"):
            for _, linha in editado_metas.iterrows():
                nome = _texto_ou_none(linha.get("meta")) or ""
                if not nome:
                    continue
                vinculo = (
                    metas.VINCULO_PATRIMONIO_INVESTIDO
                    if bool(linha.get("vinculada_ao_patrimonio")) else None
                )
                valores = (
                    nome, _texto_ou_none(linha.get("tipo")),
                    _numero_ou(linha.get("valor_alvo"), 0.0),
                    _numero_ou(linha.get("ja_acumulado"), 0.0),
                    _texto_ou_none(linha.get("prazo")),
                    _numero_ou(linha.get("aporte_definido"), 0.0),
                    _texto_ou_none(linha.get("prioridade")) or "Média",
                    _texto_ou_none(linha.get("status")) or "Ativa",
                    vinculo,
                )
                if pd.notna(linha.get("id")):
                    banco.executar(
                        """UPDATE metas SET meta=?, tipo=?, valor_alvo=?,
                           ja_acumulado=?, prazo=?, aporte_definido=?,
                           prioridade=?, status=?, vinculo=? WHERE id=?""",
                        (*valores, int(linha["id"])),
                    )
                else:
                    # `ordem` explicita, como no formulario do cartao: sem ela a
                    # meta nova nasce com o DEFAULT 0 e pula para o topo da
                    # lista, na frente das que voce ja tinha ordenado.
                    ultima = banco.consultar_um(
                        "SELECT COALESCE(MAX(ordem), 0) AS m FROM metas")
                    banco.executar(
                        """INSERT INTO metas (meta, tipo, valor_alvo, ja_acumulado,
                           prazo, aporte_definido, prioridade, status, vinculo,
                           ordem)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (*valores, int(ultima["m"]) + 1),
                    )

            if sumiram_metas and apagar_metas:
                for id_antigo in sumiram_metas:
                    banco.executar("DELETE FROM metas WHERE id = ?", (id_antigo,))
                c.recado(f"Metas salvas. {len(sumiram_metas)} apagada(s).",
                         "aviso")
            elif sumiram_metas:
                c.recado(
                    f"Metas salvas. As {len(sumiram_metas)} que você removeu da "
                    f"tabela continuam no banco — marque a caixa de confirmação "
                    f"para apagar de verdade.", "info")
            else:
                c.recado("Metas salvas.")

            estado.limpar_cache()
            st.rerun()


with aba_compras:
    cadastro_compras = estado.cadastro_compras()
    corte = banco.obter_parametro_num("corte_meta", 1000.0)
    calculadas_compras = compras.calcular(cadastro_compras, corte)
    indicadores = compras.indicadores(calculadas_compras)
    historico_de_precos = estado.historico_precos()
    resumos_de_preco = precos.resumos(historico_de_precos)

    n_no_menor = sum(
        1 for _, item in calculadas_compras.iterrows()
        if item.get("em_aberto")
        and resumos_de_preco.get(int(item["id"]), {}).get("no_menor_preco")
    ) if not calculadas_compras.empty else 0

    c.linha_kpis([
        {"rotulo": "Itens em aberto", "valor": str(indicadores["n_em_aberto"])},
        {"rotulo": "Valor em aberto", "valor": fmt_brl(indicadores["valor_em_aberto"]),
         "ajuda": "somando o melhor preço conhecido de cada um"},
        {"rotulo": "Já no preço alvo", "valor": str(indicadores["n_atingiram_alvo"]),
         "cor": "verde" if indicadores["n_atingiram_alvo"] else None,
         "ajuda": "chegaram no preço que você queria"},
        {"rotulo": "No menor preço já visto", "valor": str(n_no_menor),
         "cor": "verde" if n_no_menor else None,
         "ajuda": "desde que você começou a acompanhar"},
    ])

    capacidade_atual = banco.obter_parametro_num("capacidade_aporte_mensal", 0.0)
    if indicadores["valor_em_aberto"] > 0 and capacidade_atual > 0:
        meses_necessarios = compras.meses_para_juntar(
            indicadores["valor_em_aberto"], capacidade_atual)
        if meses_necessarios:
            c.nota(
                f"Comprando tudo o que está na lista, seriam "
                f"<strong>{fmt_brl(indicadores['valor_em_aberto'])}</strong>. "
                f"Guardando {fmt_brl(capacidade_atual)} por mês, isso levaria "
                f"<strong>{fmt_num(meses_necessarios, 1)} meses</strong> — e "
                f"nesse período nada iria para as suas metas."
            )

    st.markdown("### Lista de desejos")

    com_link = precos.rastreaveis()
    acao_busca, texto_busca = st.columns([1, 3])
    with acao_busca:
        buscar = st.button("🔄 Buscar preços agora", width="stretch",
                           disabled=com_link.empty,
                           type="primary" if not com_link.empty else "secondary")
    with texto_busca:
        st.caption(
            f"{len(com_link)} item(ns) em aberto têm link cadastrado. A busca lê "
            f"o preço que a própria loja publica na página (JSON-LD, Open Graph). "
            f"**Funciona em parte das lojas:** Amazon e Mercado Livre bloqueiam "
            f"acesso automático ou montam o preço por JavaScript — nesses o "
            f"preço continua sendo digitado. Cada item que falhar aparece aqui "
            f"com o motivo.")

    # O RELATORIO E GUARDADO, NAO IMPRESSO NA HORA. A busca muda `preco_atual`
    # no banco, e a lista abaixo ja foi lida do cache neste mesmo run — sem o
    # rerun, os cartoes mostrariam o preco velho ao lado do aviso do preco
    # novo. Mas imprimir antes do rerun tambem nao serve: o rerun redesenha a
    # pagina do zero e apaga o que acabou de ser escrito. Entao o relatorio
    # atravessa o rerun pelo estado da sessao, e fica na tela ate voce
    # dispensar — a lista de falhas ("a loja bloqueou") e justamente o que
    # voce precisa ler com calma, e ela sumiria no primeiro clique em
    # qualquer outra coisa.
    if buscar:
        with st.spinner(f"Consultando {len(com_link)} loja(s)…"):
            estado.guardar("compras_relatorio_precos", precos.atualizar())
        estado.limpar_cache()
        st.rerun()

    relatorio = estado.pegar("compras_relatorio_precos")
    if relatorio:
        for nome_item, antes, agora_preco in relatorio["mudaram"]:
            seta = "📉" if antes is not None and agora_preco < antes else "📈"
            de_para = ("" if antes is None
                       else f" (era {fmt_brl_md(antes)})")
            st.success(f"{seta} **{nome_item}**: {fmt_brl_md(agora_preco)}{de_para}")
        if relatorio["iguais"]:
            st.info(f"Sem mudança de preço: {', '.join(relatorio['iguais'])}.")
        for nome_item, motivo in relatorio["falhas"].items():
            st.warning(f"**{nome_item}**: {motivo}")
        if not relatorio["consultados"]:
            st.info("Nenhum item com link para consultar.")
        if st.button("Dispensar este relatório", key="dispensar_relatorio_precos"):
            estado.esquecer("compras_relatorio_precos")
            st.rerun()

    st.caption(
        f"Itens acima de {fmt_brl_md(corte)} são marcados como candidatos a virar "
        "meta: nesse valor, a compra deixa de ser 'quando der' e passa a "
        "exigir um plano."
    )

    if calculadas_compras.empty:
        c.aviso_vazio(
            "A lista de desejos está vazia.",
            "Use o «Modo avançado» abaixo para cadastrar o primeiro item. Com "
            "o link da loja preenchido, o app passa a acompanhar o preço.")
    else:
        em_aberto = calculadas_compras[calculadas_compras["em_aberto"]]
        fechados = calculadas_compras[~calculadas_compras["em_aberto"]]

        def _cartao_de_compra(item) -> None:
            """Um item da lista: preco alvo, preco de hoje e o menor ja visto.

            O MENOR JA VISTO E A NOVIDADE que faz a tela valer. "R$ ····" nao
            diz nada sozinho; "R$ ···· e o menor que ja vi foi R$ ···· em
            maio" diz se e hora de comprar ou de esperar.
            """
            id_item = int(item["id"])
            leitura = resumos_de_preco.get(id_item, {})
            with st.container(border=True, key=f"cartao_compra_{id_item}"):
                topo, meio, fim = st.columns([4, 3, 2])

                with topo:
                    st.markdown(f"**{item['item']}**")
                    partes = [str(item.get("prioridade") or "Média"),
                              str(item.get("status") or "Desejo")]
                    if not vazio(item.get("loja")):
                        partes.append(str(item["loja"]))
                    if not vazio(item.get("mes_alvo")):
                        partes.append(f"quero em {rotulo_mes(str(item['mes_alvo']))}")
                    st.caption(" · ".join(partes))

                    if item.get("atingiu_alvo"):
                        st.success("🎯 chegou no preço alvo")
                    elif leitura.get("no_menor_preco") and leitura.get("n_pontos", 0) > 1:
                        st.success("📉 é o menor preço desde que você acompanha")
                    elif not vazio(item.get("variacao")) and item["variacao"] > 0:
                        st.caption(f"▲ {fmt_pct(item['variacao'])} acima do alvo")

                with meio:
                    c.estatisticas([
                        {"rotulo": "Alvo", "valor": fmt_brl(item.get("preco_alvo"))},
                        {"rotulo": "Hoje", "valor": fmt_brl(item.get("preco_atual"))},
                    ])
                    if leitura.get("menor") is not None:
                        # A data vem 'AAAA-MM-DD' do banco; na tela o app
                        # escreve data em dd/mm/aaaa, como em todo o resto.
                        dia_menor = parse_data(leitura["data_menor"])
                        st.caption(
                            f"Menor já visto: **{fmt_brl_md(leitura['menor'])}** "
                            f"em {dia_menor.strftime('%d/%m/%Y') if dia_menor else leitura['data_menor']} · "
                            f"{leitura['n_pontos']} preço(s) em "
                            f"{leitura['dias_acompanhando']} dia(s)")
                    else:
                        st.caption("Sem histórico ainda — o primeiro preço "
                                   "salvo começa a curva.")

                with fim:
                    if not vazio(item.get("link")):
                        st.link_button("Abrir na loja", str(item["link"]),
                                       width="stretch")
                    if item.get("vira_meta"):
                        st.caption("💡 candidato a virar meta")

                if leitura.get("n_pontos", 0) > 1:
                    with st.expander("Ver a curva do preço"):
                        serie = historico_de_precos[
                            historico_de_precos["compra_id"] == id_item]
                        priv.grafico(
                            graficos.historico_preco(serie, item.get("preco_alvo")),
                            width="stretch", key=f"preco_hist_{id_item}")

        if not em_aberto.empty:
            projetos = em_aberto["projeto"].fillna("").astype(str)
            for nome_projeto in sorted(set(projetos), key=lambda p: (p == "", p)):
                grupo = em_aberto[projetos == nome_projeto]
                if nome_projeto:
                    total_projeto = float(grupo["preco_referencia"].sum())
                    st.markdown(f"#### {nome_projeto} · {fmt_brl_md(total_projeto)}")
                elif len(set(projetos)) > 1:
                    st.markdown("#### Desejos soltos")
                for _, item in grupo.iterrows():
                    _cartao_de_compra(item)

        if not fechados.empty:
            with st.expander(f"Comprados e descartados ({len(fechados)})"):
                priv.tabela(
                    fechados[["item", "status", "preco_referencia"]].rename(
                        columns={"item": "Item", "status": "Status",
                                 "preco_referencia": "Preço"}),
                    hide_index=True, width="stretch",
                    column_config={"Preço": c.config_moeda("Preço")},
                )

        st.markdown("### Quando comprar")
        st.caption(
            "Cada item entra no primeiro mês em que a sobra de caixa projetada "
            "cobre o preço dele, acumulando o que sobrou dos meses anteriores. "
            "A fila é rigorosa: um item caro segura os de trás até caber — se "
            "você quer o barato antes, mude a prioridade dele."
        )
        calendario = compras.calendario(calculadas_compras, projecao,
                                        capacidade_atual, mes, n_meses=12)
        if calendario.empty:
            st.caption("Nada em aberto com preço para agendar.")
        else:
            with c.painel(chave="calendario_compras"):
                priv.grafico(graficos.calendario_compras(calendario),
                             width="stretch", key="compras_calendario")

            visao_calendario = calendario.copy()
            visao_calendario["mes_sugerido"] = visao_calendario["mes_sugerido"].map(
                lambda m: "não cabe em 12 meses" if vazio(m) else rotulo_mes(str(m)))
            visao_calendario["mes_alvo"] = visao_calendario["mes_alvo"].map(
                lambda m: "—" if vazio(m) else rotulo_mes(str(m)))
            priv.tabela(
                visao_calendario[["item", "prioridade", "preco_referencia",
                                  "mes_alvo", "mes_sugerido", "cabe_no_alvo"]]
                .rename(columns={
                    "item": "Item", "prioridade": "Prioridade",
                    "preco_referencia": "Preço", "mes_alvo": "Você queria em",
                    "mes_sugerido": "Cabe em", "cabe_no_alvo": "No prazo?"}),
                hide_index=True, width="stretch",
                column_config={
                    "Preço": c.config_moeda("Preço"),
                    "No prazo?": st.column_config.CheckboxColumn(
                        "No prazo?", disabled=True),
                },
            )

        candidatos = calculadas_compras[
            calculadas_compras["em_aberto"] & calculadas_compras["vira_meta"]]
        if not candidatos.empty:
            st.markdown("### Transformar item em meta de poupança")
            col_item, col_prazo, col_botao = st.columns([3, 2, 2])
            with col_item:
                escolhido = st.selectbox(
                    "Item", candidatos["id"].tolist(),
                    format_func=lambda i: str(
                        candidatos[candidatos["id"] == i]["item"].iloc[0]),
                    key="compra_para_meta",
                )
            with col_prazo:
                prazo_meses = st.number_input(
                    "Em quantos meses", min_value=1, max_value=120, value=12)
            with col_botao:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Criar meta", width="stretch"):
                    compras.promover_para_meta(int(escolhido), mes, int(prazo_meses))
                    estado.limpar_cache()
                    c.recado(
                        f"Meta criada com prazo para "
                        f"{rotulo_mes(somar_meses(mes, int(prazo_meses)))}."
                    )
                    st.rerun()

    with st.expander("Modo avançado — editar a lista numa tabela"):
        colunas_compras = ["id", "item", "projeto", "mes_alvo", "categoria",
                           "prioridade", "loja", "link", "preco_alvo",
                           "preco_atual", "status", "observacao"]
        base_compras = (
            cadastro_compras[colunas_compras].copy() if not cadastro_compras.empty
            else pd.DataFrame(columns=colunas_compras)
        )

        editado_compras = priv.editor(
            base_compras, hide_index=True, width="stretch", num_rows="dynamic",
            key="editor_compras",
            column_config={
                "id": st.column_config.NumberColumn("id", disabled=True, width="small"),
                "item": st.column_config.TextColumn("Item", required=True, width="large"),
                "projeto": st.column_config.TextColumn(
                    "Projeto",
                    help="junte itens que caem juntos: «Casa nova», «Viagem ao "
                         "Chile». Deixe vazio para um desejo solto."),
                "mes_alvo": st.column_config.TextColumn(
                    "Mês-alvo", width="small",
                    help="AAAA-MM. Com data preenchida, o item passa a aparecer "
                         "na projeção de caixa do Planejamento."),
                "categoria": st.column_config.SelectboxColumn(
                    "Categoria", options=estado.lista_categorias()),
                "prioridade": st.column_config.SelectboxColumn(
                    "Prioridade", options=compras.PRIORIDADES),
                "loja": st.column_config.TextColumn("Loja"),
                "link": st.column_config.LinkColumn(
                    "Link",
                    help="a página do produto na loja — é dela que o botão "
                         "«Buscar preços agora» lê o preço"),
                "preco_alvo": st.column_config.NumberColumn(
                    "Preço alvo", format="R$ %.2f", min_value=0.0, step=50.0,
                    help="quanto você aceita pagar"),
                "preco_atual": st.column_config.NumberColumn(
                    "Preço hoje", format="R$ %.2f", min_value=0.0, step=50.0,
                    help="cada valor novo salvo aqui entra no histórico de preço"),
                "status": st.column_config.SelectboxColumn(
                    "Status", options=compras.STATUS_POSSIVEIS),
                "observacao": st.column_config.TextColumn("Observação"),
            },
        )

        sumiram_compras, apagar_compras = c.guarda_de_exclusao(
            editado_compras, cadastro_compras, "item", "item",
            "confirmar_exclusao_compras")

        if st.button("Salvar lista", type="primary"):
            # O preco que estava no banco ANTES deste salvamento, por item — e
            # com ele que cada linha e comparada para decidir se vale um ponto
            # novo no historico.
            precos_antes = {
                int(linha["id"]): (None if vazio(linha["preco_atual"])
                                   else float(linha["preco_atual"]))
                for _, linha in cadastro_compras.iterrows()
            } if not cadastro_compras.empty else {}

            # As reclamacoes de mes-alvo invalido sao ACUMULADAS, nao escritas
            # na hora: o st.rerun() no fim deste bloco apagaria cada uma delas.
            reclamacoes = []

            for _, linha in editado_compras.iterrows():
                nome = _texto_ou_none(linha.get("item")) or ""
                if not nome:
                    continue
                mes_alvo = _texto_ou_none(linha.get("mes_alvo")) or ""
                if mes_alvo and mes_para_indice(mes_alvo) is None:
                    reclamacoes.append(
                        f"«{nome}»: mês-alvo «{mes_alvo}» não é AAAA-MM — "
                        f"salvei sem data.")
                    mes_alvo = ""
                preco_atual = (float(linha["preco_atual"])
                               if pd.notna(linha.get("preco_atual")) else None)
                valores = (
                    nome,
                    _texto_ou_none(linha.get("projeto")),
                    mes_alvo or None,
                    _texto_ou_none(linha.get("categoria")),
                    _texto_ou_none(linha.get("prioridade")) or "Média",
                    _texto_ou_none(linha.get("loja")),
                    _texto_ou_none(linha.get("link")),
                    float(linha["preco_alvo"]) if pd.notna(linha.get("preco_alvo")) else None,
                    preco_atual,
                    _texto_ou_none(linha.get("status")) or "Desejo",
                    _texto_ou_none(linha.get("observacao")),
                )
                if pd.notna(linha.get("id")):
                    id_compra = int(linha["id"])
                    banco.executar(
                        """UPDATE futuras_compras SET item=?, projeto=?, mes_alvo=?,
                           categoria=?, prioridade=?, loja=?, link=?, preco_alvo=?,
                           preco_atual=?, status=?, observacao=? WHERE id=?""",
                        (*valores, id_compra),
                    )
                else:
                    id_compra = banco.executar(
                        """INSERT INTO futuras_compras
                           (item, projeto, mes_alvo, categoria, prioridade, loja,
                            link, preco_alvo, preco_atual, status, observacao)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        valores,
                    )
                # O preco digitado a mao vale tanto quanto o buscado: e ele que
                # constroi o historico de quem nunca clicar em "Buscar precos".
                #
                # SO QUE NAO A CADA SALVAMENTO. `registrar` carimba `fonte` e
                # `obtido_em` mesmo quando o preco nao mudou — e salvar a tabela
                # depois de corrigir o NOME de um item reescreveria "conferido
                # agora, fonte manual" num preco que veio da loja em julho.
                # Registra quando o preco mudou, ou quando o item ainda nao tem
                # historico nenhum (o caso de todo item cadastrado antes desta
                # tela existir).
                anterior = precos_antes.get(id_compra)
                mudou = anterior is None or abs(anterior - (preco_atual or 0)) >= 0.005
                if preco_atual and (mudou or id_compra not in resumos_de_preco):
                    precos.registrar(id_compra, preco_atual, "manual")

            if sumiram_compras and apagar_compras:
                for id_antigo in sumiram_compras:
                    banco.executar("DELETE FROM futuras_compras WHERE id = ?",
                                   (id_antigo,))
                    banco.executar("DELETE FROM precos_compras WHERE compra_id = ?",
                                   (id_antigo,))
                c.recado(f"Lista salva. {len(sumiram_compras)} item(ns) "
                         f"apagado(s).", "aviso")
            elif sumiram_compras:
                c.recado(
                    f"Lista salva. Os {len(sumiram_compras)} que você removeu da "
                    f"tabela continuam no banco — marque a caixa de confirmação "
                    f"para apagar de verdade.", "info")
            else:
                c.recado("Lista salva.")

            if reclamacoes:
                anterior = st.session_state.get(c.CHAVE_RECADO, ("info", ""))[1]
                separador = "\n\n"
                c.recado(separador.join([anterior, *reclamacoes]).strip(),
                         "aviso")

            estado.limpar_cache()
            st.rerun()
