"""
conferir_metas.py — prova que a meta vinculada ao patrimonio nao mente.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Uma meta como "chegar a R$ ···· investido" so faz sentido se o "ja
acumulado" for o valor REAL da carteira, nao um numero digitado uma vez e
esquecido. `vinculo = "patrimonio_investido"` existe para isso: a conta
IGNORA o que esta no cadastro e usa o patrimonio de verdade.

Uma troca de fonte de dado desse tipo e facil de fazer pela metade — trocar
o `ja_acumulado` mas esquecer de propagar para `falta`, `pct_concluido`,
`situacao`, `resumo()`. O numero "Ja tem" mostraria uma coisa e "Falta"
mostraria outra que nao fecha com ele.

O QUE ELE CONFERE
------------------
1. VINCULO SUBSTITUI    a meta vinculada usa patrimonio_investido, nao o
                        campo digitado
2. SEM VINCULO NAO MUDA meta comum continua usando o campo digitado (regressao)
3. PROPAGACAO           falta, pct_concluido e situacao usam o valor efetivo,
                        nao o original
4. RESUMO SOMA CERTO    resumo() soma o valor efetivo de cada meta
5. IDA E VOLTA NO BANCO gravar com vinculo e ler de volta preserva o vinculo
6. SEM RENDIMENTO       a projecao e soma linear — nunca multiplica

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_metas
"""

from __future__ import annotations


import pandas as pd

from financas import banco, config
from financas.calculos import metas
from financas.formato import vazio
from verificacao.base import Conferencia, banco_descartavel


def _meta(**kwargs) -> dict:
    """Uma linha de meta com valores padrao, so sobrescrevendo o que importa."""
    base = {
        "id": 1, "meta": "Teste", "tipo": "Acumular", "valor_alvo": 100_000.0,
        "ja_acumulado": 10_000.0, "prazo": None, "aporte_definido": 700.0,
        "prioridade": "Média", "status": "Ativa", "vinculo": None,
    }
    base.update(kwargs)
    return base


def conferir_vinculo_substitui(c: Conferencia) -> None:
    """A meta vinculada ignora o digitado e usa o patrimonio real."""
    print("=" * 78)
    print("1. VINCULO SUBSTITUI O DIGITADO")
    print("=" * 78)

    df = pd.DataFrame([_meta(vinculo="patrimonio_investido",
                             ja_acumulado=10_000.0)])
    resultado = metas.calcular(df, "2026-08", patrimonio_investido=234_567.89)
    linha = resultado.iloc[0]

    c.exigir(abs(float(linha["ja_acumulado"]) - 234_567.89) < 0.01,
             f"vinculada deveria usar 234567.89, veio {linha['ja_acumulado']}")
    c.exigir(abs(float(linha["ja_acumulado"]) - 10_000.0) > 1,
             "o valor digitado (10.000) vazou para o resultado")
    print(f"  digitado R$ 10.000,00 -> efetivo R$ {linha['ja_acumulado']:,.2f}")


def conferir_sem_vinculo_nao_muda(c: Conferencia) -> None:
    """Meta comum continua usando o campo digitado — sem regressao."""
    print()
    print("=" * 78)
    print("2. META SEM VINCULO NAO MUDA (REGRESSAO)")
    print("=" * 78)

    df = pd.DataFrame([_meta(vinculo=None, ja_acumulado=42_000.0)])
    resultado = metas.calcular(df, "2026-08", patrimonio_investido=999_999.0)
    linha = resultado.iloc[0]

    c.exigir(abs(float(linha["ja_acumulado"]) - 42_000.0) < 0.01,
             f"sem vinculo deveria manter 42000.0, veio {linha['ja_acumulado']}")

    sem_patrimonio = metas.calcular(df, "2026-08", patrimonio_investido=None)
    c.exigir(
        abs(float(sem_patrimonio.iloc[0]["ja_acumulado"]) - 42_000.0) < 0.01,
        "sem patrimonio_investido nenhum, o campo digitado tem de prevalecer")
    print("  meta comum ignora o patrimonio_investido, com ou sem ele disponível")


def conferir_propagacao(c: Conferencia) -> None:
    """falta, pct_concluido e situacao usam o valor EFETIVO, nao o digitado."""
    print()
    print("=" * 78)
    print("3. A SUBSTITUICAO SE PROPAGA (FALTA, %, SITUACAO)")
    print("=" * 78)

    df = pd.DataFrame([_meta(vinculo="patrimonio_investido",
                             valor_alvo=1_000_000.0, ja_acumulado=1.0,
                             aporte_definido=700.0)])
    resultado = metas.calcular(df, "2026-08", patrimonio_investido=250_000.0)
    linha = resultado.iloc[0]

    c.exigir(abs(float(linha["falta"]) - 750_000.0) < 0.01,
             f"falta deveria usar o efetivo (750.000), veio {linha['falta']}")
    c.exigir(abs(float(linha["pct_concluido"]) - 0.25) < 0.001,
             f"pct_concluido deveria ser 25%, veio {linha['pct_concluido']}")
    c.exigir(linha["situacao"] in ("sem prazo", "no ritmo", "atrasada"),
             f"situacao inesperada: {linha['situacao']}")
    c.exigir(linha["meses_no_ritmo"] is not None and linha["meses_no_ritmo"] > 0,
             "sem prazo definido, o app ainda deveria estimar 'chega em'")
    print(f"  falta R$ {linha['falta']:,.2f} · {linha['pct_concluido']*100:.0f}% "
          f"concluído · chega em {linha['meses_no_ritmo']} meses no ritmo atual")


def conferir_resumo(c: Conferencia) -> None:
    """resumo() soma o valor efetivo de cada meta, vinculada ou nao."""
    print()
    print("=" * 78)
    print("4. RESUMO SOMA O VALOR EFETIVO")
    print("=" * 78)

    df = pd.DataFrame([
        _meta(id=1, meta="Vinculada", vinculo="patrimonio_investido",
              valor_alvo=1_000_000.0, ja_acumulado=1.0, aporte_definido=700.0),
        _meta(id=2, meta="Solta", vinculo=None, valor_alvo=20_000.0,
              ja_acumulado=5_000.0, aporte_definido=300.0),
    ])
    calculadas = metas.calcular(df, "2026-08", patrimonio_investido=250_000.0)
    resumo = metas.resumo(calculadas, capacidade_mensal=1_500.0)

    esperado_acumulado = 250_000.0 + 5_000.0
    c.exigir(abs(resumo["total_acumulado"] - esperado_acumulado) < 0.01,
             f"total_acumulado esperado {esperado_acumulado}, veio "
             f"{resumo['total_acumulado']}")
    c.exigir(abs(resumo["aporte_definido_total"] - 1_000.0) < 0.01,
             f"aporte_definido_total esperado 1000.0, veio "
             f"{resumo['aporte_definido_total']}")
    print(f"  acumulado total R$ {resumo['total_acumulado']:,.2f} "
          f"(250.000 vinculado + 5.000 digitado)")


def conferir_ida_e_volta_no_banco(c: Conferencia) -> None:
    """Gravar uma meta com vinculo e ler de volta preserva o vinculo."""
    print()
    print("=" * 78)
    print("5. O VINCULO SOBREVIVE A GRAVACAO E LEITURA")
    print("=" * 78)
    with banco_descartavel("conferir_metas"):
        banco.executar(
            """INSERT INTO metas (meta, tipo, valor_alvo, ja_acumulado,
               aporte_definido, prioridade, status, vinculo)
               VALUES (?,?,?,?,?,?,?,?)""",
            ("Meta de teste", "Acumular", 1_000_000.0, 0.0, 700.0,
             "Alta", "Ativa", metas.VINCULO_PATRIMONIO_INVESTIDO),
        )
        lido = metas.cadastro()
        linha = lido[lido["meta"] == "Meta de teste"]
        c.exigir(not linha.empty, "a meta gravada nao apareceu na leitura")
        if not linha.empty:
            c.exigir(
                linha.iloc[0]["vinculo"] == metas.VINCULO_PATRIMONIO_INVESTIDO,
                f"vinculo deveria voltar como "
                f"{metas.VINCULO_PATRIMONIO_INVESTIDO!r}, veio "
                f"{linha.iloc[0]['vinculo']!r}")
    print("  gravado com vinculo, lido de volta com o mesmo vinculo")


def conferir_sem_rendimento(c: Conferencia) -> None:
    """A projecao e soma linear: nunca multiplica, nunca capitaliza."""
    print()
    print("=" * 78)
    print("6. A PROJECAO E SOMA, NUNCA JURO COMPOSTO")
    print("=" * 78)

    df = pd.DataFrame([_meta(valor_alvo=100_000.0, ja_acumulado=0.0,
                             aporte_definido=1_000.0)])
    resultado = metas.calcular(df, "2026-08", patrimonio_investido=None)
    linha = resultado.iloc[0]

    esperado_ingenuo = 100_000.0 / 1_000.0
    c.exigir(linha["meses_no_ritmo"] == esperado_ingenuo,
             f"esperava exatamente {esperado_ingenuo} meses (soma pura), "
             f"veio {linha['meses_no_ritmo']}")

    reconstituido = float(linha["aporte_definido"]) * linha["meses_no_ritmo"]
    c.exigir(abs(reconstituido - 100_000.0) < 1_000.0,
             f"aporte x meses deveria reconstituir ~100.000 sem juro, "
             f"deu {reconstituido}")
    print(f"  R$ 1.000/mês para R$ 100.000: {linha['meses_no_ritmo']} meses "
          f"exatos, sem rendimento nenhum embutido")


def conferir_prazo_misto_nao_vira_nan_solto(c: Conferencia) -> None:
    """Meta sem prazo, ao lado de meta com prazo, não pode quebrar quem lê.

    ACHADO NA TELA, NAO NO CODIGO ISOLADO. `pd.DataFrame(linhas)` decide o
    tipo de cada coluna olhando TODAS as linhas de uma vez. Uma meta sem
    `meses_restantes` (None) ao lado de uma meta com prazo (um inteiro) faz o
    pandas promover a coluna inteira para float64 — e o `None` da meta sem
    prazo vira `NaN`, nao continua `None`.

    A tela quebrou com `ValueError: cannot convert float NaN to integer`
    porque checava `is not None`, e `float('nan') is not None` e `True`. A
    correcao foi trocar por `vazio()`, que trata None e NaN como a mesma
    coisa — exatamente o motivo de `vazio()` existir (`financas/formato.py`).

    Este teste nao prova que a tela esta certa (ele nao importa `paginas/`),
    prova a PARTE que `calculos/metas.py` e responsavel por: que o valor da
    meta sem prazo continua identificavel como vazio por `vazio()`, seja qual
    for a representacao interna do pandas.
    """
    print()
    print("=" * 78)
    print("7. META SEM PRAZO AO LADO DE META COM PRAZO NAO VIRA ARMADILHA")
    print("=" * 78)

    df = pd.DataFrame([
        _meta(id=1, meta="Com prazo", prazo="2027-01", aporte_definido=500.0),
        _meta(id=2, meta="Sem prazo (a meta grande)", prazo=None,
              vinculo="patrimonio_investido", aporte_definido=700.0),
    ])
    resultado = metas.calcular(df, "2026-08", patrimonio_investido=100_000.0)
    sem_prazo = resultado[resultado["meta"] == "Sem prazo (a meta grande)"].iloc[0]
    com_prazo = resultado[resultado["meta"] == "Com prazo"].iloc[0]

    c.exigir(vazio(sem_prazo["meses_restantes"]),
             f"meta sem prazo deveria ser vazia em meses_restantes, veio "
             f"{sem_prazo['meses_restantes']!r} (tipo "
             f"{type(sem_prazo['meses_restantes']).__name__})")
    c.exigir(not vazio(com_prazo["meses_restantes"]),
             "meta COM prazo não pode virar vazia só por estar ao lado de "
             "uma que não tem")
    try:
        int(sem_prazo["meses_restantes"]) if not vazio(
            sem_prazo["meses_restantes"]) else None
    except (TypeError, ValueError) as erro:
        c.exigir(False, f"vazio() não bastou para evitar o int() quebrar: {erro}")
    print(f"  meses_restantes da meta sem prazo: {sem_prazo['meses_restantes']!r} "
          f"— vazio() diz {vazio(sem_prazo['meses_restantes'])}")

    # SEM DATA NAO HA EXIGENCIA MENSAL. Ate 2026-09 este campo trazia a FALTA
    # inteira — a meta do milhao aparecia exigindo R$ ···· por mes, e a soma
    # de resumo() ia junto: "sua capacidade cobre 0,1% do plano". O botao de
    # distribuir tambem seguia esse numero e entregava quase tudo para ela.
    c.exigir(float(sem_prazo["aporte_necessario"]) == 0.0,
             f"meta sem prazo nao exige aporte mensal nenhum, mas veio "
             f"{sem_prazo['aporte_necessario']}")
    c.exigir(float(com_prazo["aporte_necessario"]) > 0,
             "meta com prazo continua exigindo aporte mensal")

    prazo_agora = metas.calcular(
        pd.DataFrame([_meta(prazo="2026-08", ja_acumulado=90_000.0,
                            valor_alvo=100_000.0)]), "2026-08").iloc[0]
    c.exigir(abs(float(prazo_agora["aporte_necessario"]) - 10_000.0) < 0.01,
             f"prazo NESTE mes continua exigindo o que falta de uma vez, veio "
             f"{prazo_agora['aporte_necessario']}")
    print(f"  aporte_necessario: sem prazo = "
          f"{sem_prazo['aporte_necessario']:,.2f} · com prazo = "
          f"{com_prazo['aporte_necessario']:,.2f} · prazo neste mês = "
          f"{prazo_agora['aporte_necessario']:,.2f}")


def main() -> int:
    """Roda as seis conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("#" * 78)
    print("#  CONFERINDO A META VINCULADA AO PATRIMONIO")
    print("#" * 78)
    print()
    c = Conferencia()
    conferir_vinculo_substitui(c)
    conferir_sem_vinculo_nao_muda(c)
    conferir_propagacao(c)
    conferir_resumo(c)
    conferir_ida_e_volta_no_banco(c)
    conferir_sem_rendimento(c)
    conferir_prazo_misto_nao_vira_nan_solto(c)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
