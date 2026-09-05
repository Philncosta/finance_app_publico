"""
conferir_documentacao.py — mede se o codigo esta explicado.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Documentacao envelhece em silencio. Um calculo errado quebra um numero na
tela e voce descobre; uma funcao sem explicacao nao quebra nada — ela so fica
la, esperando o dia em que voce nao lembra mais por que ela existe.

Como este projeto e, antes de tudo, material de estudo, a explicacao e parte
do produto. Entao ela tambem se confere.

O QUE ELE MEDE
--------------
1. TODA funcao publica tem docstring?
   Esta e a meta de verdade, e tem de dar ZERO. A docstring e a unica
   documentacao que fica ao lado do codigo e viaja junto quando ele muda.

2. Quais funcoes nao aparecem em docs/, README ou CHANGELOG?
   Este numero e alto de proposito e NAO e uma meta. `docs/` explica
   conceitos e decisoes — nao e manual de referencia. Se cada funcao virasse
   um paragrafo, o guia dobraria e ninguem leria. O numero serve para voce
   olhar a lista e perceber se algum CONCEITO importante escapou.

3. Todo guia de docs/ esta no indice do README?
   Um guia fora do indice e um guia que nao existe.

COMO ELE LE O CODIGO — o modulo `ast`
-------------------------------------
`ast` e o proprio Python lendo Python: ele devolve a arvore que o
interpretador usa para executar o arquivo.

    arvore = ast.parse(codigo)
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef):
            no.name                  # o nome da funcao
            ast.get_docstring(no)    # a docstring, ou None

Poderia ser um `grep "def "`? Poderia, e erraria: pegaria a palavra "def"
dentro de um comentario, dentro de uma string, e nao saberia distinguir uma
funcao de topo de uma funcao aninhada. O `ast` sabe, porque le a mesma
estrutura que o Python executa.

Usamos `arvore.body` (e nao `ast.walk`) justamente para pegar SO as funcoes de
topo — as que outro arquivo pode chamar. Funcao aninhada e detalhe interno.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_documentacao
"""

from __future__ import annotations

import ast
import io
import os
import sys

from financas import config

PASTAS_CODIGO = ["financas", "ui", "migracao", "verificacao", "analises"]


def _ler(caminho: str) -> str:
    """O conteudo do arquivo, ou vazio se ele nao existir.

    O CHANGELOG **nao vai** para a copia publica de proposito — `publicar.py`
    o deixa de fora porque ele concentra 76% dos valores em reais do projeto.
    Quem clonasse o repositorio publico via esta checagem estourar com
    `FileNotFoundError` antes da primeira linha de relatorio. Um script que
    existe para conferir a documentacao nao pode quebrar por causa de um
    arquivo que alguem decidiu, com razao, nao publicar.
    """
    try:
        return io.open(caminho, encoding="utf-8").read()
    except FileNotFoundError:
        return ""


def texto_da_documentacao() -> tuple[str, str, str]:
    """Devolve (texto dos guias, README, CHANGELOG) como tres strings.

    Juntar tudo num texto so e o suficiente aqui: a pergunta e "esta palavra
    aparece em algum lugar?", nao "em qual linha de qual arquivo?".
    """
    raiz = config.RAIZ
    guias = ""
    pasta_docs = os.path.join(raiz, "docs")
    for nome in sorted(os.listdir(pasta_docs)):
        if nome.endswith(".md"):
            guias += _ler(os.path.join(pasta_docs, nome))
    return (guias,
            _ler(os.path.join(raiz, "README.md")),
            _ler(os.path.join(raiz, "CHANGELOG.md")))


def funcoes_publicas() -> list[tuple[str, str, bool]]:
    """Lista (arquivo, nome, tem_docstring) de cada funcao publica de topo."""
    achadas = []
    for pasta in PASTAS_CODIGO:
        for raiz_atual, _, nomes in os.walk(os.path.join(config.RAIZ, pasta)):
            if "__pycache__" in raiz_atual:
                continue
            for nome_arquivo in sorted(nomes):
                if not nome_arquivo.endswith(".py"):
                    continue
                caminho = os.path.join(raiz_atual, nome_arquivo)
                rel = os.path.relpath(caminho, config.RAIZ).replace(os.sep, "/")
                try:
                    arvore = ast.parse(_ler(caminho))
                except SyntaxError as erro:
                    print(f"  !! {rel} nao compila: {erro}")
                    continue
                for no in arvore.body:
                    if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    if no.name.startswith("_"):
                        continue
                    achadas.append((rel, no.name, bool(ast.get_docstring(no))))
    return achadas


def main() -> int:
    """Imprime o relatorio. Sai com 1 se alguma funcao publica esta sem docstring."""
    guias, readme, changelog = texto_da_documentacao()
    tudo = guias + readme + changelog
    achadas = funcoes_publicas()

    sem_docstring = [f"{a}::{n}" for a, n, tem in achadas if not tem]
    sem_mencao = [f"{a}::{n}" for a, n, _ in achadas if n not in tudo]

    print()
    print("=" * 78)
    print("  A DOCUMENTAÇÃO ESTÁ EM DIA?")
    print("=" * 78)
    print()
    print(f"  funções públicas no código        : {len(achadas)}")
    print(f"  SEM docstring  (meta: 0)          : {len(sem_docstring)}")
    print(f"  não citadas em texto nenhum       : {len(sem_mencao)}  "
          f"(informativo, não é meta)")

    if sem_docstring:
        print()
        print("  PRECISAM DE DOCSTRING:")
        for item in sem_docstring:
            print(f"    x {item}")

    print()
    print("  OS GUIAS:")
    pasta_docs = os.path.join(config.RAIZ, "docs")
    fora_do_indice = 0
    for nome in sorted(os.listdir(pasta_docs)):
        if not nome.endswith(".md"):
            continue
        linhas = len(_ler(os.path.join(pasta_docs, nome)).splitlines())
        no_indice = nome in readme
        fora_do_indice += 0 if no_indice else 1
        marca = "" if no_indice else "   *** FORA DO ÍNDICE DO README ***"
        print(f"    {nome:<44} {linhas:>4} linhas{marca}")

    print()
    print("=" * 78)
    if sem_docstring or fora_do_indice:
        print(f"  FALTA FECHAR: {len(sem_docstring)} docstring(s), "
              f"{fora_do_indice} guia(s) fora do índice")
        print("=" * 78)
        return 1
    print("  TUDO EXPLICADO — nenhuma função pública sem docstring")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
