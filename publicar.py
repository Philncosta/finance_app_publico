"""
publicar.py — Gera uma cópia do projeto pronta para ser vista por outra pessoa.
==============================================================================

O QUE ELE FAZ
-------------
Escreve, numa pasta NOVA, uma versão do painel sem nenhum dado seu:

    código + documentação  copiados como estão
    extratos e faturas     NÃO copiados
    seu banco de dados     NÃO copiado
    banco de demonstração  gerado do zero, com dados inventados

Rode assim:

    .venv\\Scripts\\python publicar.py
    .venv\\Scripts\\python publicar.py --destino "C:\\caminho\\que\\eu\\quero"

POR QUE UMA CÓPIA NOVA, E NÃO LIMPAR O HISTÓRICO DO GIT
-------------------------------------------------------
Esta é a decisão mais importante do arquivo, e ela evita a parte perigosa.

O caminho "óbvio" seria reescrever o histórico do repositório com
`git filter-repo`, apagando os arquivos pessoais de todos os commits passados.
Isso funciona, e cobra caro: **muda o hash de todo commit**, exige
`push --force`, e qualquer cópia antiga do repositório passa a divergir da
nova sem avisar. Se algo der errado no meio, o que se perde é o histórico
inteiro do projeto.

O que este script faz custa nada disso. O repositório PRIVADO continua
intacto, com todo o histórico e todos os arquivos originais — que é onde eles
devem estar. A pasta gerada aqui é um projeto **novo**, sem passado: ela nasce
limpa porque nunca teve nada dentro. Não há o que apagar.

    repositório privado    tudo, para sempre, como está hoje
    pasta publicada        só o código, sem passado nenhum

Você inicia um `git init` na pasta gerada e publica ELA. As duas vidas seguem
separadas.

O QUE ISSO NÃO RESOLVE, DITO SEM RODEIO
---------------------------------------
Se o repositório privado já foi público em algum momento, ou se alguém já o
clonou, os arquivos continuam onde estiveram. Nada aqui alcança uma cópia que
já saiu da sua máquina. Este script cuida do que vai para FRENTE.

MANTER A CÓPIA ATUALIZADA
-------------------------
Rode de novo. Ele reescreve a pasta de destino do zero, e você faz um commit
novo no repositório público. A pasta é descartável de propósito: nada nela é
editado à mão, então nada nela se perde ao ser regerado.
"""

from __future__ import annotations

import argparse
import ast
import io
import random
import re
import shutil
import sqlite3
import sys
import tokenize
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

NAO_COPIAR = {
    "arquivos_originais",
    "migracao",
    "dados",
    ".venv",
    ".git",
    ".claude",
    "__pycache__",
    ".pytest_cache",
    ".streamlit",
}

NAO_COPIAR_ARQUIVOS = {
    ".db", ".db-wal", ".db-shm", ".xlsx", ".xlsm", ".csv", ".ofx", ".pdf",
    ".zip",
}

SEMENTE = 20260829

ARQUIVOS_FORA = {"CHANGELOG.md", "nomes.txt"}
"""Arquivos que ficam de fora mesmo sendo texto, e por que.

O CHANGELOG concentra 294 dos 387 valores em reais do projeto — 76% da sua
vida financeira em um arquivo so. Ele e um diario de decisoes SUAS sobre
dinheiro SEU, e e justamente o arquivo que menos serve a quem clona: ninguem
precisa saber por que voce rateou a PLR de agosto para entender como o app
funciona.

Tirar ele resolve tres quartos da exposicao numerica sem custar nada de
utilidade. Quem quiser mesmo assim publica com `--com-changelog`.

Os outros 93 valores estao na documentacao tecnica, e ali eles PAGAM o que
custam: "o Trend DI recebeu X e devolveu Y em 29 meses" e o que prova que
dividir saldo por aporte nao mede rentabilidade. Sem o numero, vira opiniao.
Essa escolha e sua — veja `--sem-numeros`.
"""

SUBSTITUICOES_PADRAO = "nomes.txt"
"""Arquivo com as trocas, uma por linha, no formato `de=para`.

    Fulano=Ana
    Beltrano=Bruno
    00000000=00000000

NAO E SO PARA NOME. E para qualquer string exata que identifique voce e nao
devia estar num repositorio publico — nome de pessoa, numero de conta, numero
de agencia. A entrada do numero de conta acima existe porque ele JA vazou uma
vez: estava em cinco arquivos de codigo como exemplo ilustrativo em docstring
("Conta: 00000000 | 22/08/2026") e em duas linhas de documentacao, e nenhuma
das outras camadas deste script o pegava — nao e caminho, nao e nome, nao e
valor em reais. Foi corrigido na FONTE (os exemplos agora usam 12345678), e a
linha aqui e a rede de seguranca contra o numero real voltar a aparecer.

POR QUE NUM ARQUIVO DE FORA, E NAO AQUI DENTRO. Se a lista morasse no codigo,
ela iria junto na copia — e uma lista de "isto nao pode aparecer" e, ela
propria, o dado que nao pode aparecer. O arquivo fica no `.gitignore`, entao
ele nunca e versionado nem copiado.

Sem o arquivo, o script AVISA e segue: ele nao tem como adivinhar o que e seu.
Com o arquivo, ele troca cada entrada e depois CONFERE que nenhuma sobrou —
se sobrar, a copia e reprovada em vez de publicada.
"""


def ler_substituicoes(caminho: Path) -> dict[str, str]:
    """Le o arquivo `de=para`. Devolve vazio (com aviso) se ele nao existir."""
    if not caminho.exists():
        return {}
    trocas = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        de, _, para = linha.partition("=")
        if de.strip():
            trocas[de.strip()] = para.strip() or "[nome removido]"
    return trocas


def trocar_nomes(destino: Path, trocas: dict[str, str]) -> int:
    """Troca cada nome pelo substituto, respeitando maiuscula e minuscula.

    Faz as tres formas em que um nome aparece nos arquivos: `BRUNO` num
    extrato copiado para dentro de uma docstring, `Bruno` no texto corrido e
    `bruno` em nome de coisa. Trocar so a forma exata deixaria as outras
    duas passarem, que e o jeito mais comum de um scrub falhar.
    """
    if not trocas:
        return 0
    alterados = 0
    for arquivo in destino.rglob("*"):
        if not arquivo.is_file() or arquivo.suffix.lower() not in _TEXTO:
            continue
        texto = original = arquivo.read_text(encoding="utf-8", errors="ignore")
        for de, para in trocas.items():
            texto = texto.replace(de.upper(), para.upper())
            texto = texto.replace(de.capitalize(), para.capitalize())
            texto = texto.replace(de.lower(), para.lower())
        if texto != original:
            arquivo.write_text(texto, encoding="utf-8")
            alterados += 1
    return alterados


# Qualquer forma de dinheiro escrita em prosa: com centavos ou sem, com
# separador de milhar ou sem, em reais ou em dolar, seguida ou nao de "mil".
_DINHEIRO = re.compile(
    # com o cifrao na frente: "R$ ····", "R$ ····", "R$ ····"
    r"(?:R\$|US\$)\s?\d[\d.,]*(?:\s?mil(?:hões|hoes|hão|hao)?)?"
    # ou sem cifrao nenhum, no formato brasileiro com centavos: "R$ ····".
    # Faltava, e era por onde passavam os numeros reais escritos no meio da
    # frase — "somar R$ ···· (dolares) com R$ ···· (reais)".
    r"|\b\d{1,3}(?:\.\d{3})+,\d{2}\b")


def _linhas_de_prosa(src: str) -> set[int]:
    """As linhas de um .py que sao comentario ou docstring — e so elas.

    POR QUE NAO MASCARAR O ARQUIVO INTEIRO (2026-09-04). Ha string de codigo
    que CONTEM dinheiro e faz parte do funcionamento: o texto de ajuda que a
    tela mostra ("R$ ···· significam coisas diferentes para quem gasta
    R$ ····"), e o print de um script de migracao. Sao numeros genericos,
    escritos para explicar, nao extratos de ninguem — e trocar por `····`
    estragaria a explicacao dentro do app publicado.

    O que interessa mascarar e a PROSA: docstring e comentario, que e onde os
    numeros de verdade dele foram parar, como prova de argumento.
    """
    linhas: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                linhas.update(range(tok.start[0], tok.end[0] + 1))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return linhas

    try:
        arvore = ast.parse(src)
    except SyntaxError:
        return linhas
    for no in ast.walk(arvore):
        if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef,
                           ast.AsyncFunctionDef)) and ast.get_docstring(no):
            primeiro = no.body[0]
            linhas.update(range(primeiro.lineno, primeiro.end_lineno + 1))
    return linhas


def mascarar_numeros(destino: Path) -> int:
    """Troca valor em dinheiro por `R$ ····` na PROSA, deixando o codigo de pe.

    Serve para quem prefere documentacao menos convincente a documentacao que
    conta quanto ele tem. A frase continua legivel — "o fundo recebeu R$ ····
    e devolveu R$ ····" ainda diz que houve rotatividade —, mas o leitor perde
    a escala, que e o que torna o exemplo memoravel.

    DUAS COISAS QUE ESTA FUNCAO NAO FAZIA (2026-09-04). Ela varria so `*.md` e
    exigia centavos no padrao. Resultado: **405 valores em reais continuavam na
    copia publica** depois de rodar com `--sem-numeros` — entre eles os que
    estavam em docstring de `.py`, e todos os redondos (`R$ ····`). A opcao
    prometia "todo valor em reais" e entregava a minoria.

    Nao e o padrao de proposito: e uma troca, nao uma melhoria.
    """
    alterados = 0
    for arquivo in destino.rglob("*"):
        if not arquivo.is_file() or arquivo.suffix.lower() not in _TEXTO:
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")

        if arquivo.suffix.lower() == ".py":
            prosa = _linhas_de_prosa(texto)
            if not prosa:
                continue
            linhas = texto.splitlines(keepends=True)
            novo = "".join(
                _DINHEIRO.sub("R$ ····", l) if i in prosa else l
                for i, l in enumerate(linhas, 1))
        else:
            novo = _DINHEIRO.sub("R$ ····", texto)

        if novo != texto:
            arquivo.write_text(novo, encoding="utf-8")
            alterados += 1
    return alterados


_COPIAR_CHANGELOG = [False]
_MASCARAR_NUMEROS = [False]


def _copiavel(caminho: Path) -> bool:
    """Decide se um arquivo entra na cópia.

    A lista de exclusão é por EXTENSÃO, não por nome. Nome muda; extensão de
    planilha continua sendo planilha. Um `.csv` novo que aparecer amanhã na
    pasta já nasce fora da cópia, sem ninguém lembrar de atualizar nada.
    """
    if any(parte in NAO_COPIAR for parte in caminho.parts):
        return False
    if caminho.name in ARQUIVOS_FORA and not _COPIAR_CHANGELOG[0]:
        return False
    if caminho.name == "nomes.txt":
        return False
    return caminho.suffix.lower() not in NAO_COPIAR_ARQUIVOS


def copiar_codigo(destino: Path) -> int:
    """Copia código e documentação. Devolve quantos arquivos entraram."""
    copiados = 0
    for origem in RAIZ.rglob("*"):
        if not origem.is_file():
            continue
        relativo = origem.relative_to(RAIZ)
        if not _copiavel(relativo):
            continue
        alvo = destino / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, alvo)
        copiados += 1
    return copiados


GRANDES = [
    ("Casa", "#4F46E5"), ("Comida", "#F59E0B"), ("Transporte", "#10B981"),
    ("Saúde", "#EF4444"), ("Lazer", "#8B5CF6"), ("Renda", "#22C55E"),
    ("Investimentos", "#0EA5E9"),
]

CATEGORIAS = [
    ("Moradia", "Casa", "Despesa"),
    ("Contas de casa", "Casa", "Despesa"),
    ("Mercado", "Comida", "Despesa"),
    ("Restaurante", "Comida", "Despesa"),
    ("Transporte", "Transporte", "Despesa"),
    ("Plano de saúde", "Saúde", "Despesa"),
    ("Farmácia", "Saúde", "Despesa"),
    ("Assinaturas", "Lazer", "Despesa"),
    ("Passeio", "Lazer", "Despesa"),
    ("Salário", "Renda", "Receita"),
    ("Aportes", "Investimentos", "Investimento"),
]

VARIAVEIS = [
    ("Mercado", "Compra do mês", 120, 620),
    ("Restaurante", "Almoço", 28, 140),
    ("Transporte", "Corrida de aplicativo", 12, 75),
    ("Farmácia", "Farmácia", 20, 180),
    ("Assinaturas", "Streaming", 20, 60),
    ("Passeio", "Cinema", 30, 220),
]

FIXOS_DEMO = [
    ("Aluguel", "Moradia", 2200.0, 5, "Aluguel"),
    ("Condomínio", "Moradia", 480.0, 10, "Condomínio"),
    ("Luz e internet", "Contas de casa", 320.0, 15, "Luz e internet"),
    ("Plano de saúde", "Plano de saúde", 640.0, 20, "Plano de saúde"),
    ("Streaming", "Assinaturas", 55.0, 25, "Streaming"),
]
"""Os mesmos itens que `_lancamentos_demo` repete todo mes.

Sem isto o dashboard abria com "-0,0% e gasto fixo": os lancamentos existiam e
a tabela que os RECONHECE como fixos estava vazia. Um numero negativo com zero
virgula zero e a cara de um app quebrado — e a primeira coisa que quem clona
ia ver.

As duas listas precisam continuar batendo. Se uma mudar sozinha, o painel
volta a discordar de si mesmo.
"""

PAPEIS_DEMO = [
    ("Tesouro Selic 2029", "Tesouro Selic", "Renda Fixa", "BRL", None, 45000.0),
    ("CDB Banco Exemplo", "CDB", "Renda Fixa", "BRL", None, 22000.0),
    ("Fundo DI Exemplo", "Fundo DI", "Caixa", "BRL", None, 18000.0),
    ("Ação BR Exemplo", "Ação BR", "Renda Variável", "BRL", "PETR4.SA", 9000.0),
]


def _lancamentos_demo(sorteio: random.Random) -> list[tuple]:
    """Dois anos de lançamentos plausíveis, com sazonalidade e nenhum nome real.

    Os valores são inventados, mas não são aleatórios puros: salário fixo,
    moradia estável, alimentação e lazer oscilando. Dado de demonstração que
    não tem forma nenhuma deixa todos os gráficos do app parecendo ruído, e aí
    quem abrir não entende o que a tela quer mostrar.
    """
    linhas = []
    hoje = date.today().replace(day=1)
    mes = (hoje - timedelta(days=730)).replace(day=1)

    # Os mesmos itens de FIXOS_DEMO, com o dia de vencimento junto.
    fixos = [(item, categoria, valor, dia)
             for item, categoria, valor, dia, _ in FIXOS_DEMO]

    while mes <= hoje:
        competencia = mes.isoformat()[:7]

        if not (mes.year == hoje.year and mes.month == hoje.month
                and hoje.day < 5):
            linhas.append((f"{competencia}-05", "Salário", 8500.0, "Salário",
                           "Receita", competencia))
        if mes.month == 12:
            linhas.append((f"{competencia}-20", "Décimo terceiro", 8500.0,
                           "Salário", "Receita Extraordinária", competencia))

        # O MES CORRENTE PARA NO DIA DE HOJE, como um extrato de verdade.
        #
        # Antes, todo fixo era lancado no dia 10 de TODO mes, inclusive o que
        # ainda esta acontecendo. Resultado: nenhum gasto fixo aparecia como
        # "previsto" — e `conferir_previsao` reprovava a demonstracao com
        # "a transicao nao esta sendo exercitada". A suite ia vermelha para
        # quem clonasse o projeto, num defeito do DADO de exemplo, nao do app.
        #
        # Com dias espalhados (5, 10, 15, 20, 25) e o corte em hoje, sempre ha
        # fixo ja pago e fixo a vencer no mes corrente — que e a situacao que a
        # tela existe para mostrar.
        for descricao, categoria, valor, dia in fixos:
            if mes.year == hoje.year and mes.month == hoje.month \
                    and dia > hoje.day:
                continue
            linhas.append((f"{competencia}-{dia:02d}", descricao, -valor,
                           categoria, "Despesa", competencia))

        for _ in range(sorteio.randint(9, 18)):
            categoria, descricao, piso, teto = sorteio.choice(VARIAVEIS)
            valor = round(sorteio.uniform(piso, teto), 2)
            limite = (hoje.day if mes.year == hoje.year
                      and mes.month == hoje.month else 28)
            if limite < 1:
                continue
            dia = f"{sorteio.randint(1, limite):02d}"
            linhas.append((f"{competencia}-{dia}", descricao, -valor,
                           categoria, "Despesa", competencia))

        linhas.append((f"{competencia}-15", "Aporte mensal", -1500.0,
                       "Aportes", "Investimento", competencia))

        mes = (mes.replace(day=28) + timedelta(days=7)).replace(day=1)

    return linhas


_MARCA_AVISO_PRIVADO = "ESTE REPOSITÓRIO PRECISA CONTINUAR"

_AVISO_COPIA_PUBLICA = """> ## Esta é a cópia pública, sem dados pessoais
>
> Gerada automaticamente por `publicar.py` a partir de um repositório privado.
> Não contém arquivos de extrato, banco de dados real, nem nome de pessoa
> nenhum — só código, documentação e um banco de **demonstração**, com dados
> inventados, para você ver o app funcionando antes de usar com os seus.
>
> Quer usar com os seus dados? Clone, rode, e importe os seus arquivos —
> tudo fica no seu computador, dentro do seu próprio banco local."""


def reescrever_aviso_privado(destino: Path) -> bool:
    """Troca o aviso "mantenha isto privado" pelo aviso certo para uma cópia.

    O README original avisa, em letras grandes, que aquele repositório precisa
    continuar privado — porque ele lista `arquivos_originais/` e
    `migracao/semente/` como o motivo. Copiado sem ajuste para a pasta
    pública, o aviso vira uma MENTIRA às avessas: ele aparece bem no topo do
    repositório que você acabou de tornar público, apontando para pastas que
    nem existem ali, e dizendo a quem olha o código pela primeira vez que algo
    deu errado.

    Isto não é um caminho de máquina nem um nome de pessoa — é um TEXTO
    escrito para o contexto errado. Nenhuma das outras camadas deste script
    pegaria isso: `neutralizar_caminhos` procura caminho, `trocar_nomes`
    procura nome, `mascarar_numeros` procura valor em reais. Um aviso de
    segurança que ficou obsoleto não é nenhuma das três coisas.

    Devolve `True` se encontrou e trocou o aviso.
    """
    caminho = destino / "README.md"
    if not caminho.exists():
        return False
    texto = caminho.read_text(encoding="utf-8")
    linhas = texto.splitlines()

    inicio = next((i for i, linha in enumerate(linhas)
                   if _MARCA_AVISO_PRIVADO in linha), None)
    if inicio is None:
        return False

    fim = inicio
    while fim < len(linhas) and linhas[fim].startswith(">"):
        fim += 1

    linhas[inicio:fim] = _AVISO_COPIA_PUBLICA.splitlines()
    caminho.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return True


def liberar_banco_demo_no_git(destino: Path) -> None:
    """Faz o `.gitignore` copiado abrir uma exceção para o banco de demonstração.

    O `.gitignore` do projeto original ignora `dados/financas.db` de propósito
    — é assim que o SEU banco, com seus dados, nunca vai para o git. Copiado
    sem ajuste para a pasta pública, esse mesmo motivo vira um problema
    diferente: o banco de DEMONSTRAÇÃO, gerado por este script exatamente para
    dar a quem clonar algo para ver, cairia na mesma regra e nunca chegaria ao
    GitHub. A pasta pública subiria com o app funcionando e a tela vazia.

    A saída é uma exceção `!dados/financas.db` logo depois da regra que
    ignora — sintaxe padrão do git, "ignore tudo isso, exceto isto". Ela entra
    só na cópia; o `.gitignore` do seu projeto continua intocado.
    """
    caminho = destino / ".gitignore"
    if not caminho.exists():
        return
    texto = caminho.read_text(encoding="utf-8")
    linha_alvo = "dados/financas.db\n"
    if linha_alvo not in texto or "!dados/financas.db" in texto:
        return
    texto = texto.replace(linha_alvo,
                          linha_alvo + "!dados/financas.db\n", 1)
    caminho.write_text(texto, encoding="utf-8")


def gerar_banco_demo(caminho: Path) -> dict:
    """Cria o banco de demonstração do zero. Devolve o que foi gravado.

    Ele usa as MIGRAÇÕES de verdade, não um schema escrito à parte. Se as duas
    coisas fossem separadas, a demonstração envelheceria em silêncio: uma
    tabela nova entraria no app e o banco de exemplo continuaria sem ela, e o
    erro só apareceria para quem clonasse o projeto.
    """
    sys.path.insert(0, str(RAIZ))
    from financas import banco, config

    if caminho.exists():
        caminho.unlink()
    caminho.parent.mkdir(parents=True, exist_ok=True)

    original = config.CAMINHO_BANCO
    config.CAMINHO_BANCO = caminho
    try:
        banco.aplicar_migracoes(caminho)

        sorteio = random.Random(SEMENTE)
        conexao = sqlite3.connect(caminho)

        for ordem, (nome, cor) in enumerate(GRANDES, start=1):
            conexao.execute(
                "INSERT OR IGNORE INTO grandes_categorias (nome, cor, ordem) "
                "VALUES (?,?,?)", (nome, cor, ordem))

        for ordem, (nome, grande, natureza) in enumerate(CATEGORIAS, start=1):
            conexao.execute(
                "INSERT OR IGNORE INTO categorias "
                "(nome, grande_categoria, natureza_padrao, ativa, ordem) "
                "VALUES (?,?,?,1,?)", (nome, grande, natureza, ordem))

        conexao.execute(
            "INSERT OR IGNORE INTO contas (nome, tipo) VALUES (?,?)",
            ("Conta corrente", "corrente"))

        lancamentos = _lancamentos_demo(sorteio)
        conexao.executemany(
            "INSERT INTO lancamentos "
            "(id_unico, data, descricao, valor, categoria, natureza, "
            " mes_competencia, origem) "
            "VALUES (?,?,?,?,?,?,?,'demo')",
            [(f"demo-{i}",) + linha for i, linha in enumerate(lancamentos)])

        for nome, classe, _macro, moeda, ticker, saldo in PAPEIS_DEMO:
            cursor = conexao.execute(
                "INSERT INTO investimentos "
                "(nome, tipo, classe, moeda, ticker, ativo) "
                "VALUES (?,?,?,?,?,1)",
                (nome, classe, classe, moeda, ticker))
            papel = cursor.lastrowid
            valor = saldo * 0.72
            mes = date.today().replace(day=1) - timedelta(days=700)
            while mes <= date.today().replace(day=1):
                valor *= 1 + sorteio.uniform(0.002, 0.014)
                conexao.execute(
                    "INSERT INTO investimentos_saldos "
                    "(investimento_id, mes, saldo) VALUES (?,?,?)",
                    (papel, mes.isoformat()[:7], round(valor, 2)))
                mes = (mes.replace(day=28) + timedelta(days=7)).replace(day=1)

        inicio = (date.today().replace(day=1)
                  - timedelta(days=730)).replace(day=1).isoformat()[:7]
        for item, categoria, valor, dia, chave in FIXOS_DEMO:
            conexao.execute(
                "INSERT INTO gastos_fixos "
                "(item, categoria, valor_mensal, dia, inicio, reajuste_aa, "
                " ativo, parcelado, chave_historico) "
                "VALUES (?,?,?,?,?,0,1,0,?)",
                (item, categoria, valor, dia, inicio, chave))

        conexao.execute(
            "INSERT OR REPLACE INTO parametros (chave, valor) VALUES (?,?)",
            ("categoria_terceiros", config.CATEGORIA_TERCEIROS_PADRAO))

        conexao.commit()
        contagem = {
            tabela: conexao.execute(
                f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
            for tabela in ("lancamentos", "investimentos",
                           "investimentos_saldos", "categorias")
        }
        conexao.close()
        return contagem
    finally:
        config.CAMINHO_BANCO = original



CAMINHO_GENERICO = "CAMINHO\\PARA\\finance_app"

_TEXTO = (".py", ".md", ".txt", ".toml", ".bat")


def neutralizar_caminhos(destino: Path) -> int:
    """Troca os caminhos da sua máquina por um genérico, DENTRO DA CÓPIA.

    A documentação está cheia de linhas prontas para copiar e colar:

        cd C:\\Users\\SeuNome\\Phil\\finance_app && .venv\\Scripts\\streamlit run app.py

    Isso é útil para você e é duas coisas ruins para quem clonar: mostra o seu
    nome de usuário — que costuma ser o seu nome — e é um caminho que não
    existe na máquina dele.

    A troca acontece só na cópia. Os seus arquivos continuam com o caminho que
    de fato funciona aí, que é o motivo de ele estar escrito assim.

    Devolve quantos arquivos foram alterados.
    """
    padrao = re.compile(r"[A-Za-z]:[\\/]Users[\\/][^\\/\s'\"`)\]]+"
                        r"(?:[\\/][^\s'\"`)\]]*)*")

    alterados = 0
    for arquivo in destino.rglob("*"):
        if not arquivo.is_file() or arquivo.suffix.lower() not in _TEXTO:
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        novo = padrao.sub(_generico, texto)
        if novo != texto:
            arquivo.write_text(novo, encoding="utf-8")
            alterados += 1
    return alterados


def _generico(achado) -> str:
    """Mantem o final do caminho, que costuma ser a informacao util.

    `CAMINHO/PARA/OneDrive/Backup/x.zip` vira `CAMINHO/PARA/Backup/x.zip`:
    quem le continua entendendo que e uma pasta de backup com um zip dentro,
    sem saber de quem.
    """
    inteiro = achado.group(0)
    separador = "\\" if "\\" in inteiro else "/"
    partes = [parte for parte in re.split(r"[\\/]", inteiro) if parte]
    cauda = partes[3:] if len(partes) > 3 else []
    if not cauda:
        return CAMINHO_GENERICO
    return separador.join(["CAMINHO", "PARA"] + cauda)

def conferir(destino: Path, banco_demo: Path,
             nomes: tuple = ()) -> list[str]:
    """Varre a cópia procurando o que não devia ter ido junto.

    Uma checagem DEPOIS de copiar, e não confiança na lista de exclusão. A
    lista é uma intenção; isto é uma medição. Se alguém acrescentar um arquivo
    numa pasta que ninguém lembrou de excluir, é aqui que aparece.

    O banco de demonstração é a única exceção, e por construção: ele é `.db`
    dentro de `dados/`, as duas coisas que a varredura procura. Ele passa
    porque foi ESTE script que o escreveu, do zero, com dados inventados.

    SOBRE O PADRÃO MONTADO A MÃO. Os pedaços de "c:" + barra + "users" são
    juntados em tempo de execução de propósito. Escrito por extenso, o texto
    procurado apareceria no código-fonte deste arquivo — e a varredura
    acusaria a si mesma, que foi exatamente o que aconteceu na primeira vez
    que ela rodou. Montado assim, `publicar.py` continua sendo verificado
    como qualquer outro.
    """
    suspeitos = []
    molde = "c:%susers%s"
    proibidos = tuple(molde % (sep, sep) for sep in (chr(92), "/"))

    for arquivo in destino.rglob("*"):
        if not arquivo.is_file() or arquivo == banco_demo:
            continue
        relativo = arquivo.relative_to(destino)
        if arquivo.suffix.lower() in NAO_COPIAR_ARQUIVOS:
            suspeitos.append(f"arquivo de dado copiado: {relativo}")
        elif any(parte in NAO_COPIAR for parte in relativo.parts):
            suspeitos.append(f"pasta excluída copiada: {relativo}")

    for fonte in destino.rglob("*"):
        if not fonte.is_file() or fonte.suffix.lower() not in _TEXTO:
            continue
        texto = fonte.read_text(encoding="utf-8", errors="ignore").lower()
        if any(proibido in texto for proibido in proibidos):
            suspeitos.append(
                f"caminho da máquina em {fonte.relative_to(destino)}")

    for fonte in destino.rglob("*"):
        if not fonte.is_file() or fonte.suffix.lower() not in _TEXTO:
            continue
        texto = fonte.read_text(encoding="utf-8", errors="ignore").lower()
        for marca in nomes:
            if marca.lower() in texto:
                suspeitos.append(
                    f"identificador pessoal em {fonte.relative_to(destino)}: "
                    f"{marca}")

    # A MEDICAO QUE FALTAVA. `--sem-numeros` prometia tirar todo valor em
    # reais e deixou 405 passarem, porque ninguem conferiu DEPOIS. A opcao
    # agora e cobrada: se ela foi pedida, valor com centavo nenhum pode
    # sobrar. Centavo e o corte porque numero de extrato tem centavo, e numero
    # de exemplo ("R$ ····") e redondo — e os redondos que sobram no codigo
    # sao texto de ajuda da propria tela, nao dado de ninguem.
    if _MASCARAR_NUMEROS[0]:
        com_centavo = re.compile(r"(?:R\$|US\$)\s?\d[\d.]*,\d{2}")
        for fonte in destino.rglob("*"):
            if not fonte.is_file() or fonte.suffix.lower() not in _TEXTO:
                continue
            texto = fonte.read_text(encoding="utf-8", errors="ignore")
            if fonte.suffix.lower() == ".py":
                # So a prosa, pela mesma razao de `mascarar_numeros`: o que
                # sobra no codigo e valor INVENTADO de teste (R$ ····) ou
                # texto de ajuda da tela. Cobrar isso reprovaria a copia por
                # causa de numero que nunca foi de ninguem.
                prosa = _linhas_de_prosa(texto)
                achados = [m for i, l in enumerate(texto.splitlines(), 1)
                           if i in prosa for m in com_centavo.findall(l)]
            else:
                achados = com_centavo.findall(texto)
            if achados:
                suspeitos.append(
                    f"valor em dinheiro sobrou em {fonte.relative_to(destino)}"
                    f": {achados[0]}" + (f" (+{len(achados)-1})"
                                         if len(achados) > 1 else ""))

    readme = destino / "README.md"
    if readme.exists() and _MARCA_AVISO_PRIVADO in readme.read_text(
            encoding="utf-8", errors="ignore"):
        suspeitos.append(
            "README.md ainda tem o aviso 'mantenha isto privado' — ele "
            "escapou de reescrever_aviso_privado()")

    return suspeitos


def main() -> int:
    """Copia o código, gera o banco de exemplo e confere o resultado."""
    argumentos = argparse.ArgumentParser(
        description="Gera uma cópia publicável do painel, sem dados pessoais.")
    argumentos.add_argument(
        "--destino", default=str(RAIZ.parent / "finance_app_publico"),
        help="Pasta a criar. Ela é APAGADA e reescrita a cada execução.")
    argumentos.add_argument(
        "--com-changelog", action="store_true",
        help="Inclui o CHANGELOG.md, que concentra 76% dos valores em reais "
             "do projeto. Fora por padrão.")
    argumentos.add_argument(
        "--sem-numeros", action="store_true",
        help="Troca todo valor em reais da documentação por R$ ····. Deixa os "
             "textos menos convincentes, e é essa a troca.")
    opcoes = argumentos.parse_args()
    _COPIAR_CHANGELOG[0] = opcoes.com_changelog
    _MASCARAR_NUMEROS[0] = opcoes.sem_numeros

    destino = Path(opcoes.destino).resolve()
    if destino == RAIZ:
        print("ERRO: o destino não pode ser a própria pasta do projeto.")
        return 1

    print(f"Destino: {destino}")
    if destino.exists():
        print("  a pasta já existe — vai ser apagada e reescrita")
        shutil.rmtree(destino)

    copiados = copiar_codigo(destino)
    print(f"  {copiados} arquivos de código e documentação copiados")

    if reescrever_aviso_privado(destino):
        print("  aviso 'mantenha isto privado' trocado pelo aviso da cópia pública")

    trocados = neutralizar_caminhos(destino)
    print(f"  {trocados} arquivos tiveram caminhos da máquina trocados")

    if opcoes.sem_numeros:
        mascarados = mascarar_numeros(destino)
        print(f"  valores em reais mascarados em {mascarados} arquivos")

    trocas = ler_substituicoes(RAIZ / SUBSTITUICOES_PADRAO)
    if trocas:
        alterados = trocar_nomes(destino, trocas)
        print(f"  {len(trocas)} nome(s) trocado(s) em {alterados} arquivos")
    else:
        print(f"  AVISO: sem {SUBSTITUICOES_PADRAO} — nenhum nome foi trocado.")
        print(f"         Crie o arquivo com uma linha 'Fulano=Ana' por nome.")

    banco_demo = destino / "dados" / "financas.db"
    contagem = gerar_banco_demo(banco_demo)
    liberar_banco_demo_no_git(destino)
    print(f"  banco de demonstração: {contagem['lancamentos']} lançamentos, "
          f"{contagem['investimentos']} papéis, "
          f"{contagem['investimentos_saldos']} saldos mensais "
          f"(liberado do .gitignore)")

    problemas = conferir(destino, banco_demo, tuple(trocas))
    print()
    if problemas:
        print(f"ATENÇÃO — {len(problemas)} coisa(s) que não deviam estar lá:")
        for problema in problemas[:20]:
            print(f"  x {problema}")
        return 1

    print("Nada pessoal na cópia. Para publicar:")
    print()
    print(f'    cd "{destino}"')
    print("    git init && git add -A")
    print('    git commit -m "Painel financeiro"')
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
