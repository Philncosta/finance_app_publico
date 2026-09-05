"""
conferir_tudo.py — roda todas as conferencias e devolve um placar so.
==============================================================================

POR QUE ISTO PRECISOU EXISTIR (2026-09-04)
------------------------------------------
O `__init__.py` desta pasta ja dizia, desde sempre:

    "Cada script imprime um relatorio e termina com codigo 0 (tudo certo) ou 1
     (alguma conta nao fecha). Isso permite rodar todos de uma vez sem ler
     tudo."

Permitia — mas o script que faz isso nunca existiu. Na pratica, cada vez que
alguem queria a foto inteira, escrevia um laco de shell na mao. Uma promessa na
documentacao sem a coisa do lado e uma armadilha: quem le acredita que existe e
nao procura.

DESCOBRE SOZINHO OS SCRIPTS
---------------------------
Usa `pkgutil` em vez de uma lista escrita a mao. Uma lista teria de ser
atualizada a cada conferencia nova — e o dia em que alguem esquecer, a suite
passa a dizer "tudo certo" sem rodar a checagem que importava. Uma lista que
pode ficar desatualizada e pior que nenhuma lista.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_tudo
"""

from __future__ import annotations

import importlib
import io
import pkgutil
import sys
import time
from contextlib import redirect_stdout

import verificacao

# O proprio runner nao e uma conferencia.
IGNORAR = {"conferir_tudo"}

# Frases com que os scripts anunciam sucesso. Sao duas porque
# `conferir_documentacao` nao conta checagens: ele confere uma propriedade
# ("nenhuma funcao publica sem docstring"), e forcar um numero ali seria
# inventar uma metrica para caber no formato.
SINAIS_DE_SUCESSO = ("TUDO CERTO", "TUDO EXPLICADO")


def scripts() -> list[str]:
    """Os modulos `conferir_*` desta pasta, em ordem alfabetica."""
    return sorted(
        nome for _, nome, _ in pkgutil.iter_modules(verificacao.__path__)
        if nome.startswith("conferir_") and nome not in IGNORAR
    )


def rodar(nome: str) -> tuple[int, int, str, float]:
    """Roda uma conferencia calada. Devolve (codigo, checagens, saida, seg).

    A saida e capturada em vez de impressa porque a graca de rodar tudo e
    caber numa tela. Quando algo falha, ai sim o texto inteiro daquele script
    aparece — que e o momento em que voce quer ler.
    """
    modulo = importlib.import_module(f"verificacao.{nome}")
    buffer = io.StringIO()
    inicio = time.perf_counter()
    try:
        with redirect_stdout(buffer):
            codigo = int(modulo.main() or 0)
    except Exception as erro:              # o script quebrou, nao so falhou
        return 2, 0, f"{buffer.getvalue()}\n  EXCECAO: {erro!r}", \
               time.perf_counter() - inicio
    segundos = time.perf_counter() - inicio

    saida = buffer.getvalue()
    checagens = 0
    for linha in saida.splitlines():
        if "checagens" in linha and any(s in linha for s in SINAIS_DE_SUCESSO):
            for pedaco in linha.replace("—", " ").split():
                if pedaco.isdigit():
                    checagens = int(pedaco)
                    break
    return codigo, checagens, saida, segundos


def main() -> int:
    """Roda tudo, imprime uma linha por script e o total. 0 se tudo passou."""
    print()
    print("#" * 78)
    print("#  CONFERINDO O APP INTEIRO")
    print("#" * 78)
    print()

    total = 0
    falhados: list[tuple[str, str]] = []
    comeco = time.perf_counter()

    for nome in scripts():
        codigo, checagens, saida, segundos = rodar(nome)
        total += checagens
        rotulo = nome.replace("conferir_", "")
        if codigo == 0:
            marca = (f"{checagens:>6} checagens" if checagens
                     else f"{'ok':>6}          ")
            print(f"  {rotulo:<20} {marca}   {segundos:>5.1f}s")
        else:
            print(f"  {rotulo:<20} {'FALHOU':>6}              {segundos:>5.1f}s")
            falhados.append((rotulo, saida))

    print()
    print("=" * 78)
    if falhados:
        print(f"FALHOU — {len(falhados)} de {len(scripts())} scripts, "
              f"{total} checagens rodadas")
        print("=" * 78)
        for rotulo, saida in falhados:
            print()
            print(f"### {rotulo} " + "#" * (72 - len(rotulo)))
            print(saida)
        return 1

    print(f"TUDO CERTO — {len(scripts())} scripts, {total:,} checagens, "
          f"{time.perf_counter() - comeco:.1f}s")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
