"""
regras.py — O motor que adivinha a categoria de cada transacao.
==============================================================================

O PROBLEMA QUE ELE RESOLVE
--------------------------
O banco manda "DL*UBERRIDES" ou "Pix enviado para Raia Drogasil S/A". Voce
quer ver "Transporte" e "Saúde". Categorizar 500 linhas na mao por mes nao e
sustentavel.

A solucao (a mesma da planilha, que ja tinha 148 regras) e uma LISTA DE REGRAS
lida DE CIMA PARA BAIXO. A primeira que casar vence, e as de baixo nem sao
testadas. Isso e importante: a ORDEM das regras faz parte da logica, nao e
detalhe. Regra especifica em cima, regra generica embaixo.

DOIS TIPOS DE REGRA
-------------------
FATURA (mais simples) — so a palavra-chave importa:

    palavra-chave "DROGA"  ->  categoria "Saúde",  tipo "Variável"

EXTRATO (mais esperta) — porque no extrato a mesma palavra pode significar
coisas diferentes. Alem da palavra, a regra olha o VALOR e o SENTIDO:

    "XP EMPREGADORA", acima de R$ ···· entrando  ->  PLR
    "XP EMPREGADORA", qualquer valor,     entrando  ->  Salário

Como a primeira vence, o salario de todo mes cai na segunda regra, e so o PLR
anual (que passa de 50 mil) cai na primeira. Um jeito simples e eficaz de
resolver um caso que daria muito trabalho de outra forma.

COMO A COMPARACAO E FEITA
-------------------------
Os dois lados passam por `normalizar_texto()`: viram MAIUSCULO, perdem acento
e espaco duplo. Assim "Drogaria Tamoio", "DROGARIA  TAMOIO" e "drogaria
tamoio" sao a mesma coisa. Depois e um simples "a palavra-chave esta contida
na descricao?".

Nao usamos expressao regular de proposito: voce vai cadastrar regras na tela, e
"contém" e uma ideia que qualquer pessoa entende sem aprender sintaxe nova.
"""

from __future__ import annotations

import re

import pandas as pd

from dataclasses import dataclass

from financas import banco, config
from financas.formato import normalizar_texto


@dataclass
class Classificacao:
    """O que o motor decidiu sobre uma transacao.

    O campo `regra` guarda o texto da regra que casou ("DROGA -> Saúde"). Ele
    aparece na tela de importacao e fica gravado no lancamento. Serve para
    voce ENTENDER por que aquilo foi parar naquela categoria — e, quando
    estiver errado, saber exatamente qual regra ajustar.
    """

    categoria: str
    tipo: str
    natureza: str
    regra: str | None = None

    @property
    def automatica(self) -> bool:
        """True quando alguma regra casou; False quando caiu no padrao."""
        return self.regra is not None


REGRAS_FATURA_ESSENCIAIS = [
    (1, "Pagamento de fatura", "Pagamento de Fatura", "Variável"),
    (2, "Pagamentos Validos", "Pagamento de Fatura", "Variável"),
    (3, "Credito em confian", "Outros", "Variável"),
    (4, "99FOOD", "Alimentação", "Variável"),
    (5, "IFD*", "Alimentação", "Variável"),
]


def garantir_regras_essenciais() -> int:
    """Insere as regras essenciais que ainda nao existirem. Devolve quantas criou.

    Compara pela palavra-chave normalizada, entao rodar de novo nao duplica —
    e, se voce editar ou apagar uma delas de proposito, ela NAO volta sozinha
    (a comparacao e por palavra-chave, e uma regra editada continua existindo).
    """
    existentes = {
        normalizar_texto(linha["palavra_chave"])
        for linha in banco.consultar("SELECT palavra_chave FROM regras_fatura")
    }
    novas = [
        (ordem, palavra, categoria, tipo)
        for ordem, palavra, categoria, tipo in REGRAS_FATURA_ESSENCIAIS
        if normalizar_texto(palavra) not in existentes
    ]
    if not novas:
        return 0

    banco.executar("UPDATE regras_fatura SET ordem = ordem + 10")
    return banco.executar_muitos(
        "INSERT INTO regras_fatura (ordem, palavra_chave, categoria, tipo, ativa) "
        "VALUES (?,?,?,?,1)",
        novas,
    )


@dataclass
class ConjuntoDeRegras:
    """Todas as regras + a tabela de categorias, ja prontas para uso.

    POR QUE CARREGAR TUDO DE UMA VEZ: classificar 500 linhas consultando o
    banco a cada linha seria 500 idas ao disco. Carregando uma vez e
    comparando em memoria, a importacao inteira leva milissegundos.

    As palavras-chave ja vem NORMALIZADAS aqui dentro, para nao repetir esse
    trabalho a cada uma das 500 comparacoes.
    """

    fatura: list[dict]
    extrato: list[dict]
    natureza_por_categoria: dict[str, str]


def carregar_regras() -> ConjuntoDeRegras:
    """Le as regras do banco e devolve prontas para classificar."""
    fatura = [
        {
            "palavra": normalizar_texto(linha["palavra_chave"]),
            "original": linha["palavra_chave"],
            "categoria": linha["categoria"],
            "tipo": linha["tipo"] or config.TIPO_VARIAVEL,
        }
        for linha in banco.consultar(
            "SELECT palavra_chave, categoria, tipo FROM regras_fatura "
            "WHERE ativa = 1 ORDER BY ordem, id"
        )
    ]

    extrato = [
        {
            "palavra": normalizar_texto(linha["palavra_chave"]),
            "original": linha["palavra_chave"],
            "valor_min_abs": linha["valor_min_abs"] or 0.0,
            "sinal": linha["sinal"] or config.SINAL_AMBOS,
            "categoria": linha["categoria"],
            "tipo": linha["tipo"] or config.TIPO_VARIAVEL,
            "natureza": linha["natureza"] or config.NATUREZA_DESPESA,
        }
        for linha in banco.consultar(
            "SELECT palavra_chave, valor_min_abs, sinal, categoria, tipo, natureza "
            "FROM regras_extrato WHERE ativa = 1 ORDER BY ordem, id"
        )
    ]

    natureza_por_categoria = {
        linha["nome"]: linha["natureza_padrao"]
        for linha in banco.consultar("SELECT nome, natureza_padrao FROM categorias")
    }

    return ConjuntoDeRegras(fatura, extrato, natureza_por_categoria)


def _sinal_combina(regra_sinal: str, valor: float) -> bool:
    """Confere se o sentido do dinheiro bate com o que a regra exige.

    Lembre da convencao: valor negativo = saiu, positivo = entrou.
    """
    if regra_sinal == config.SINAL_AMBOS:
        return True
    if regra_sinal == config.SINAL_ENTRADA:
        return valor > 0
    if regra_sinal == config.SINAL_SAIDA:
        return valor < 0
    return True


def classificar_fatura(descricao: str, valor: float,
                       regras: ConjuntoDeRegras) -> Classificacao:
    """Decide categoria/tipo/natureza de uma linha de FATURA.

    A natureza nao vem da regra: ela e deduzida da categoria escolhida, usando
    a coluna `natureza_padrao` do cadastro de categorias. Assim voce configura
    "Pagamento de Fatura e natureza Pagamento" UMA vez, em Configuracoes, e
    todas as regras que apontam para essa categoria herdam isso.
    """
    alvo = normalizar_texto(descricao)

    for regra in regras.fatura:
        if regra["palavra"] and regra["palavra"] in alvo:
            categoria = regra["categoria"]
            return Classificacao(
                categoria=categoria,
                tipo=regra["tipo"],
                natureza=regras.natureza_por_categoria.get(
                    categoria, config.NATUREZA_DESPESA
                ),
                regra=f'{regra["original"]} → {categoria}',
            )

    return Classificacao(
        categoria="Outros",
        tipo=config.TIPO_VARIAVEL,
        natureza=config.NATUREZA_DESPESA,
        regra=None,
    )


def classificar_extrato(descricao: str, valor: float,
                        regras: ConjuntoDeRegras) -> Classificacao:
    """Decide categoria/tipo/natureza de uma linha de EXTRATO.

    Testa as tres condicoes de cada regra, nesta ordem (a mais barata
    primeiro, para descartar rapido):

        1. a palavra-chave esta na descricao?
        2. o valor absoluto atinge o minimo exigido?
        3. o sentido (entrada/saida) bate?
    """
    alvo = normalizar_texto(descricao)
    valor_abs = abs(valor)

    for regra in regras.extrato:
        if not regra["palavra"] or regra["palavra"] not in alvo:
            continue
        if valor_abs < regra["valor_min_abs"]:
            continue
        if not _sinal_combina(regra["sinal"], valor):
            continue

        detalhe = regra["original"]
        if regra["valor_min_abs"] > 0:
            detalhe += f" (≥ {regra['valor_min_abs']:.0f})"
        if regra["sinal"] != config.SINAL_AMBOS:
            detalhe += f" [{regra['sinal']}]"
        return Classificacao(
            categoria=regra["categoria"],
            tipo=regra["tipo"],
            natureza=regra["natureza"],
            regra=f'{detalhe} → {regra["categoria"]}',
        )

    if valor > 0:
        return Classificacao("Outras Receitas", config.TIPO_VARIAVEL,
                             config.NATUREZA_RECEITA, None)
    return Classificacao("Outros", config.TIPO_VARIAVEL,
                         config.NATUREZA_DESPESA, None)


def classificar(linha: dict, regras: ConjuntoDeRegras) -> Classificacao:
    """Classifica uma linha normalizada, escolhendo o motor certo pela origem."""
    if linha.get("origem") == config.ORIGEM_FATURA:
        return classificar_fatura(linha["descricao"], linha["valor"], regras)
    return classificar_extrato(linha["descricao"], linha["valor"], regras)


def testar_contra_historico(origem: str = config.ORIGEM_FATURA) -> list[dict]:
    """Mostra quantos lancamentos do historico cada regra pegaria hoje.

    ISSO A PLANILHA NAO FAZIA. Serve para tres coisas:

      - achar regra MORTA: cadastrada, mas que nunca casa com nada (talvez a
        loja mudou de nome no extrato);
      - achar regra CANIBAL: uma regra generica la em cima engolindo o que
        deveria cair numa especifica mais abaixo;
      - conferir antes de mexer: voce ve o efeito de reordenar sem precisar
        reimportar nada.

    Devolve uma lista com {ordem, palavra_chave, categoria, acertos}.
    """
    regras = carregar_regras()
    lista = regras.fatura if origem == config.ORIGEM_FATURA else regras.extrato

    lancamentos = banco.consultar(
        "SELECT descricao, valor FROM lancamentos WHERE origem = ?", (origem,)
    )
    alvos = [(normalizar_texto(l["descricao"]), l["valor"]) for l in lancamentos]

    contagem = [0] * len(lista)
    sem_regra = 0

    for alvo, valor in alvos:
        for indice, regra in enumerate(lista):
            if not regra["palavra"] or regra["palavra"] not in alvo:
                continue
            if origem == config.ORIGEM_EXTRATO:
                if abs(valor) < regra["valor_min_abs"]:
                    continue
                if not _sinal_combina(regra["sinal"], valor):
                    continue
            contagem[indice] += 1
            break
        else:
            sem_regra += 1

    saida = [
        {
            "ordem": indice + 1,
            "palavra_chave": regra["original"],
            "categoria": regra["categoria"],
            "acertos": contagem[indice],
        }
        for indice, regra in enumerate(lista)
    ]
    saida.append({
        "ordem": None,
        "palavra_chave": "(nenhuma regra casou)",
        "categoria": "—",
        "acertos": sem_regra,
    })
    return saida


def sugerir_regras(origem: str = config.ORIGEM_FATURA,
                   minimo_ocorrencias: int = 2) -> list[dict]:
    """Sugere regras novas a partir do que NENHUMA regra pegou.

    A IDEIA: se o mesmo estabelecimento aparece varias vezes no seu historico
    e nenhuma regra o reconhece, ele merece uma regra. E, melhor ainda, o
    proprio historico ja diz qual categoria usar — e a que voce escolheu a mao
    nas vezes anteriores.

    Entao a sugestao nao e um palpite meu: e a sua propria decisao passada,
    transformada em regra. Voce ve na tela de Regras, confere e aceita com um
    clique (ou ignora).

    Parametros:
        minimo_ocorrencias — so sugere quem apareceu pelo menos N vezes, para
                             nao encher a tela com compra de uma vez so.

    Devolve, do mais frequente para o menos:
        {palavra_chave, ocorrencias, valor_total, categoria_sugerida,
         tipo_sugerido, concordancia}

    `concordancia` e a fracao das vezes em que voce usou a categoria sugerida
    (1.0 = sempre a mesma; 0.6 = voce variou, olhe com atencao).
    """
    from collections import Counter, defaultdict

    regras_atuais = carregar_regras()
    lancamentos = banco.consultar(
        "SELECT descricao, valor, categoria, tipo FROM lancamentos WHERE origem = ?",
        (origem,),
    )

    ocorrencias: Counter = Counter()
    valores: Counter = Counter()
    categorias: dict[str, Counter] = defaultdict(Counter)
    tipos: dict[str, Counter] = defaultdict(Counter)
    exemplo: dict[str, str] = {}

    for linha in lancamentos:
        classificacao = (
            classificar_fatura(linha["descricao"], linha["valor"], regras_atuais)
            if origem == config.ORIGEM_FATURA
            else classificar_extrato(linha["descricao"], linha["valor"], regras_atuais)
        )
        if classificacao.automatica:
            continue

        chave = normalizar_texto(linha["descricao"])[:22].strip()
        if not chave:
            continue

        ocorrencias[chave] += 1
        valores[chave] += abs(linha["valor"] or 0)
        exemplo.setdefault(chave, linha["descricao"])
        if linha["categoria"]:
            categorias[chave][linha["categoria"]] += 1
        if linha["tipo"]:
            tipos[chave][linha["tipo"]] += 1

    sugestoes = []
    for chave, quantidade in ocorrencias.most_common():
        if quantidade < minimo_ocorrencias:
            continue
        contagem_categorias = categorias.get(chave)
        if not contagem_categorias:
            continue
        categoria, vezes = contagem_categorias.most_common(1)[0]
        contagem_tipos = tipos.get(chave)
        tipo = (contagem_tipos.most_common(1)[0][0]
                if contagem_tipos else config.TIPO_VARIAVEL)

        sugestoes.append({
            "palavra_chave": chave,
            "exemplo": exemplo[chave],
            "ocorrencias": quantidade,
            "valor_total": valores[chave],
            "categoria_sugerida": categoria,
            "tipo_sugerido": tipo,
            "concordancia": vezes / quantidade,
        })
    return sugestoes


def adicionar_regra_fatura(palavra_chave: str, categoria: str,
                           tipo: str = config.TIPO_VARIAVEL) -> int:
    """Cadastra uma regra de fatura no fim da lista (menor prioridade).

    Entra no fim de proposito: uma regra nova nunca deve roubar transacoes de
    uma regra especifica que voce ja tinha ajustado.
    """
    ultima = banco.consultar_um("SELECT COALESCE(MAX(ordem), 0) AS m FROM regras_fatura")
    return banco.executar(
        "INSERT INTO regras_fatura (ordem, palavra_chave, categoria, tipo, ativa) "
        "VALUES (?,?,?,?,1)",
        (int(ultima["m"]) + 1, palavra_chave, categoria, tipo),
    )


def adicionar_regra_extrato(palavra_chave: str, categoria: str,
                            tipo: str = config.TIPO_VARIAVEL,
                            natureza: str = config.NATUREZA_DESPESA,
                            valor_min_abs: float = 0.0,
                            sinal: str = config.SINAL_AMBOS) -> int:
    """Cadastra uma regra de extrato no fim da lista (menor prioridade)."""
    ultima = banco.consultar_um("SELECT COALESCE(MAX(ordem), 0) AS m FROM regras_extrato")
    return banco.executar(
        "INSERT INTO regras_extrato "
        "(ordem, palavra_chave, valor_min_abs, sinal, categoria, tipo, natureza, ativa) "
        "VALUES (?,?,?,?,?,?,?,1)",
        (int(ultima["m"]) + 1, palavra_chave, valor_min_abs, sinal,
         categoria, tipo, natureza),
    )


INTERMEDIARIOS = ("MP", "PG", "PAG", "ZIG", "PICPAY", "IFD", "DL", "EC",
                  "MERPAGO", "SUMUP", "STONE", "CIELO")


def chave_de_grupo(descricao: str) -> str:
    """Reduz uma descricao ao ESTABELECIMENTO, para juntar as variacoes.

    O mesmo lugar aparece escrito de varias formas no arquivo do banco:

        "UBER   *UBER   *TRIP"  |
        "UBER* PENDING"         |->  todos viram  "UBER"
        "UBER* TRIP"            |

    E um Pix para uma pessoa vira o nome dela, sem o "Pix enviado para".
    """
    texto = normalizar_texto(descricao)
    if not texto:
        return ""

    pessoa = re.match(
        r"^(?:PIX|TED)\s+(?:ENVIAD[OA]|RECEBID[OA]|DEVOLVID[OA])\s+(?:PARA|DE)\s+(.*)$",
        texto)
    if pessoa:
        nome = " ".join(pessoa.group(1).split()[:3])
        return f"PIX/TED {nome}".strip()

    if "*" in texto:
        prefixo = texto.split("*")[0].strip()
        if prefixo in INTERMEDIARIOS:
            return prefixo
        return prefixo[:22].strip() or texto[:22].strip()

    return texto[:22].strip()


def grupos_sem_categoria(categoria_alvo: str = "Outros",
                         limite: int = 60) -> pd.DataFrame:
    """Junta os lancamentos sem categoria por estabelecimento.

    Devolve, do que mais pesa para o que menos pesa:
        chave, exemplo, ocorrencias, valor_total, origem, primeiro_mes,
        ultimo_mes, e_pessoa

    `limite` corta a lista: mostrar 458 grupos de uma vez nao ajuda ninguem.
    """
    colunas = ["chave", "exemplo", "ocorrencias", "valor_total", "origem",
               "primeiro_mes", "ultimo_mes", "e_pessoa"]

    linhas = banco.consultar(
        """SELECT descricao, valor, origem, mes_competencia
           FROM lancamentos WHERE categoria = ?""",
        (categoria_alvo,))
    if not linhas:
        return pd.DataFrame(columns=colunas)

    grupos: dict[str, dict] = {}
    for linha in linhas:
        chave = chave_de_grupo(linha["descricao"])
        if not chave:
            continue
        alvo = grupos.setdefault(chave, {
            "chave": chave, "exemplo": linha["descricao"], "ocorrencias": 0,
            "valor_total": 0.0, "origens": set(),
            "primeiro_mes": linha["mes_competencia"],
            "ultimo_mes": linha["mes_competencia"],
        })
        alvo["ocorrencias"] += 1
        alvo["valor_total"] += float(linha["valor"] or 0)
        alvo["origens"].add(linha["origem"])
        alvo["primeiro_mes"] = min(alvo["primeiro_mes"], linha["mes_competencia"])
        alvo["ultimo_mes"] = max(alvo["ultimo_mes"], linha["mes_competencia"])

    tabela = pd.DataFrame([
        {
            "chave": g["chave"],
            "exemplo": g["exemplo"],
            "ocorrencias": g["ocorrencias"],
            "valor_total": g["valor_total"],
            "origem": "/".join(sorted(g["origens"])),
            "primeiro_mes": g["primeiro_mes"],
            "ultimo_mes": g["ultimo_mes"],
            "e_pessoa": g["chave"].startswith("PIX/TED"),
        }
        for g in grupos.values()
    ], columns=colunas)

    tabela["peso"] = tabela["valor_total"].abs()
    return (tabela.sort_values("peso", ascending=False)
            .drop(columns=["peso"]).head(limite).reset_index(drop=True))


def cobertura_da_triagem(categoria_alvo: str = "Outros") -> dict:
    """Quanto do problema ainda falta: linhas, valor e quantos grupos existem."""
    linha = banco.consultar_um(
        """SELECT COUNT(*) n, COALESCE(SUM(valor), 0) s
           FROM lancamentos WHERE categoria = ?""", (categoria_alvo,))
    todos = grupos_sem_categoria(categoria_alvo, limite=100000)
    return {
        "linhas": int(linha["n"]),
        "valor": float(linha["s"]),
        "grupos": int(len(todos)),
    }


def _descricoes_que_contem(palavra: str) -> list[str]:
    """Descricoes que contem a palavra, comparando do MESMO jeito que o motor.

    POR QUE ISTO NAO E UM `WHERE ... LIKE` — a armadilha do UPPER() do SQLite:

        UPPER('Pedrao')  ->  'PEDRAO'    certo
        UPPER('Pedrão')  ->  'PEDRãO'    o "a" com til passa batido
        UPPER('Saude')   ->  'SAUDE'     certo
        UPPER('Saúde')   ->  'SAúDE'     idem

    O UPPER() do SQLite so conhece o alfabeto ASCII. O `.upper()` do Python
    conhece acento. Misturar os dois — que era o que este arquivo fazia — cria
    uma comparacao que nunca casa: o Python manda "%SAÚDE%" e o banco tem
    "SAúDE" guardado.

    Nenhuma palavra-chave cadastrada tem acento hoje, entao isto nunca chegou a
    classificar nada errado. Mas a primeira regra escrita com acento falharia
    em silencio, que e o pior tipo de falha.

    A correcao e comparar em Python com `normalizar_texto`, a MESMA funcao que
    `classificar()` usa. Assim a checagem de seguranca enxerga exatamente o que
    o motor vai enxergar — que e o unico jeito de ela significar alguma coisa.
    """
    alvo = normalizar_texto(palavra)
    if not alvo:
        return []
    return [linha["descricao"]
            for linha in banco.consultar("SELECT descricao FROM lancamentos")
            if alvo in normalizar_texto(linha["descricao"])]


def _pega_fora_do_grupo(palavra: str, chave: str) -> str | None:
    """Devolve um exemplo do que a palavra pegaria FORA do grupo, ou None."""
    if not palavra:
        return "vazia"
    for descricao in _descricoes_que_contem(palavra):
        if chave_de_grupo(descricao) != chave:
            return descricao
    return None


def palavra_chave_segura(palavra: str, chave: str) -> str | None:
    """Ajusta a palavra-chave para ela nao pegar mais do que devia.

    O BUG QUE ISTO EVITA — aconteceu de verdade em 2026-08-22:

    A triagem agrupa "PAG*CLAUDIO", "PAG*SUPERTICKET" etc. sob a chave "PAG".
    Ao virar regra, "PAG" passou a casar tambem com **"PAGAMENTO PARA MERCADO
    PAGO"** — porque a comparacao e por trecho contido, em qualquer posicao.
    Resultado: R$ ···· de pagamento foram parar em Viagem.

    A checagem e direta: a palavra pega alguma linha cuja chave de grupo seja
    OUTRA? Se pega, tentamos a variante com asterisco ("PAG*"), que so casa com
    o padrao do intermediario. Se nem assim, devolvemos None — melhor ficar sem
    regra do que com uma regra que classifica errado toda importacao futura.
    """
    if not palavra:
        return None
    if _pega_fora_do_grupo(palavra, chave) is None:
        return palavra

    com_asterisco = f"{palavra}*"
    if _pega_fora_do_grupo(com_asterisco, chave) is None:
        if _descricoes_que_contem(com_asterisco):
            return com_asterisco
    return None


def aplicar_triagem(chave: str, categoria: str, tipo: str,
                    natureza: str | None = None,
                    criar_regra: bool = True,
                    categoria_alvo: str = "Outros") -> dict:
    """Aplica uma decisao da triagem: conserta o passado e ensina o futuro.

    Sao duas coisas, e as duas importam:

      1. RETROATIVO — todos os lancamentos daquele estabelecimento que estao
         em "Outros" passam para a categoria escolhida. Sem isso, os graficos
         de 2024-2025 continuariam errados.

      2. REGRA — a proxima importacao ja classifica sozinha. Sem isso, voce
         faria a mesma escolha de novo no mes que vem.

    Devolve {atualizados, regra_criada, regra_recusada}.

    `regra_recusada` traz a palavra que seria usada quando ela pegaria coisa de
    fora do grupo — ver `palavra_chave_segura`. Nesse caso o passado e
    corrigido do mesmo jeito; so nao nasce regra para o futuro.
    """
    linhas = banco.consultar(
        "SELECT id, descricao, origem FROM lancamentos WHERE categoria = ?",
        (categoria_alvo,))
    alvos = [l for l in linhas if chave_de_grupo(l["descricao"]) == chave]
    if not alvos:
        return {"atualizados": 0, "regra_criada": False}

    natureza = natureza or config.NATUREZA_DESPESA
    banco.executar_muitos(
        "UPDATE lancamentos SET categoria = ?, tipo = ?, natureza = ? WHERE id = ?",
        [(categoria, tipo, natureza, l["id"]) for l in alvos])

    regra_criada = False
    regra_recusada = None
    if criar_regra:
        palavra = chave[len("PIX/TED "):] if chave.startswith("PIX/TED ") else chave
        palavra = palavra.strip()
        bruta = palavra
        palavra = palavra_chave_segura(palavra, chave)
        if not palavra:
            regra_recusada = bruta
        origens = {l["origem"] for l in alvos}
        if palavra:
            if config.ORIGEM_FATURA in origens:
                ja = banco.consultar_um(
                    "SELECT id FROM regras_fatura WHERE UPPER(palavra_chave)=UPPER(?)",
                    (palavra,))
                if not ja:
                    adicionar_regra_fatura(palavra, categoria, tipo)
                    regra_criada = True
            if config.ORIGEM_EXTRATO in origens:
                ja = banco.consultar_um(
                    "SELECT id FROM regras_extrato WHERE UPPER(palavra_chave)=UPPER(?)",
                    (palavra,))
                if not ja:
                    adicionar_regra_extrato(palavra, categoria, tipo, natureza)
                    regra_criada = True

    return {"atualizados": len(alvos), "regra_criada": regra_criada,
            "regra_recusada": regra_recusada}


CHAVE_PORTADORES = "portadores_categoria"


def portadores_com_categoria() -> dict[str, str]:
    """Le o mapa {trecho do nome do portador: categoria}. Vazio se nao houver."""
    import json

    bruto = banco.obter_parametro(CHAVE_PORTADORES)
    if not bruto:
        return {}
    try:
        return {k.upper(): v for k, v in json.loads(bruto).items()}
    except (ValueError, AttributeError):
        return {}


def definir_portador_categoria(trecho_do_nome: str, categoria: str | None) -> dict:
    """Liga (ou desliga) a regra de portador. `categoria=None` remove."""
    import json

    mapa = portadores_com_categoria()
    chave = trecho_do_nome.strip().upper()
    if categoria:
        mapa[chave] = categoria
    else:
        mapa.pop(chave, None)
    banco.definir_parametro(CHAVE_PORTADORES, json.dumps(mapa, ensure_ascii=False))
    return mapa


def categoria_por_portador(portador: str | None) -> str | None:
    """Devolve a categoria do portador, se ele tiver uma. Senao None."""
    if not portador:
        return None
    alvo = normalizar_texto(portador)
    for trecho, categoria in portadores_com_categoria().items():
        if normalizar_texto(trecho) in alvo:
            return categoria
    return None
