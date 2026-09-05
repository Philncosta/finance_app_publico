"""
conferir_exclusao.py — prova que a tabela nao apaga nada por conta propria.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Tres telas do app editam um cadastro numa tabela com `num_rows="dynamic"`, e
o padrao sempre foi: o `id` que sumisse da tela virava `DELETE` no Salvar. Sem
aviso. Ninguem descobre isso ate o dia em que perde alguma coisa — e foi
exatamente a duvida dele ("e se eu apagar uma linha?") que trouxe o
comportamento a tona.

Hoje quem decide o que sera apagado e `componentes.ids_removidos`. Se ela
errar para MAIS, o app apaga o que voce nao mandou apagar. Se errar para
MENOS, o app finge que apagou e a linha reaparece. Os dois lados doem, e
nenhum dos dois aparece numa conferida no olho.

O QUE ELE CONFERE
------------------
1. NADA REMOVIDO       tabela igual a origem -> lista vazia
2. UMA REMOVIDA        acha exatamente o id que sumiu
3. VARIAS REMOVIDAS    acha todas, e so elas
4. LINHA NOVA          linha sem id (NaN) nao conta como removida, e nao quebra
5. TUDO REMOVIDO       tabela esvaziada devolve todos os ids
6. ORIGEM VAZIA        cadastro vazio nunca gera exclusao
7. SEM COLUNA ID       tabela sem `id` nao gera exclusao (falha fechada)
8. ORDEM NAO IMPORTA   linha reordenada na tela nao conta como removida

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_exclusao
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ui.componentes import ids_removidos
from verificacao.base import Conferencia


def cadastro(*ids) -> pd.DataFrame:
    """Um cadastro de mentira, com os ids pedidos."""
    return pd.DataFrame({"id": list(ids),
                         "item": [f"Item {i}" for i in ids]})


def main() -> int:
    """Roda as oito conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("CONFERINDO O GUARDA DE EXCLUSAO DAS TABELAS")
    print()
    c = Conferencia()
    origem = cadastro(1, 2, 3, 4)

    print("=" * 78)
    print("1 a 3. O QUE SUMIU DA TELA, E SO ISSO")
    print("=" * 78)
    c.exigir(ids_removidos(origem.copy(), origem) == [],
             "tabela intacta nao deveria gerar exclusao nenhuma")
    print("  nada removido            -> []")

    sem_o_dois = origem[origem["id"] != 2]
    c.exigir(ids_removidos(sem_o_dois, origem) == [2],
             f"deveria achar [2], veio {ids_removidos(sem_o_dois, origem)}")
    print("  removida a linha 2       -> [2]")

    sem_dois_e_quatro = origem[~origem["id"].isin([2, 4])]
    achados = ids_removidos(sem_dois_e_quatro, origem)
    c.exigir(achados == [2, 4], f"deveria achar [2, 4], veio {achados}")
    print("  removidas as linhas 2 e 4-> [2, 4]")

    print()
    print("=" * 78)
    print("4. LINHA NOVA (id VAZIO) NAO CONTA COMO REMOVIDA")
    print("=" * 78)
    # E o caso que quebraria com `int(NaN)` se nao houvesse o dropna().
    com_nova = pd.concat(
        [origem, pd.DataFrame({"id": [np.nan], "item": ["Recem-criado"]})],
        ignore_index=True)
    try:
        achados = ids_removidos(com_nova, origem)
    except Exception as erro:
        achados = f"EXCECAO {type(erro).__name__}: {erro}"
    c.exigir(achados == [],
             f"linha nova nao deveria gerar exclusao, veio {achados!r}")
    print(f"  4 linhas + 1 nova sem id -> {achados}")

    nova_e_sem_o_um = pd.concat(
        [origem[origem["id"] != 1],
         pd.DataFrame({"id": [np.nan], "item": ["Recem-criado"]})],
        ignore_index=True)
    achados = ids_removidos(nova_e_sem_o_um, origem)
    c.exigir(achados == [1],
             f"criar uma e apagar outra deveria achar [1], veio {achados}")
    print(f"  cria uma e remove a 1    -> {achados}")

    print()
    print("=" * 78)
    print("5 a 8. OS EXTREMOS")
    print("=" * 78)
    achados = ids_removidos(origem.iloc[0:0], origem)
    c.exigir(achados == [1, 2, 3, 4],
             f"tabela esvaziada deveria devolver todos, veio {achados}")
    print(f"  tabela esvaziada         -> {achados}")

    c.exigir(ids_removidos(origem, cadastro()) == [],
             "cadastro vazio nunca pode gerar exclusao")
    print("  cadastro de origem vazio -> []")

    sem_coluna = pd.DataFrame({"item": ["a", "b"]})
    c.exigir(ids_removidos(sem_coluna, origem) == [],
             "tabela sem coluna `id` deveria falhar FECHADA (nao apagar nada)")
    print("  tabela sem coluna id     -> [] (falha fechada)")

    embaralhada = origem.iloc[::-1].reset_index(drop=True)
    c.exigir(ids_removidos(embaralhada, origem) == [],
             "reordenar linhas na tela nao pode contar como remover")
    print("  linhas reordenadas       -> []")

    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
