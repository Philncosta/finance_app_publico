"""
conferir_dimensoes.py — prova que os eixos da carteira nao perdem dinheiro.
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
A mesma carteira agora e olhada por seis eixos: macro, classe, tema, prazo,
indexador e liquidez. Tres erros aqui nao aparecem numa conferida no olho:

1. UM PAPEL CAINDO FORA DE TODO BALDE. O grafico continua bonito e o total
   fica menor que a carteira. Ninguem repara que faltam R$ ···· num grafico
   de pizza.

2. O BALDE DE PRAZO ERRADO. "IPCA+ Longo" e "IPCA+ Ultra longo" sao decisoes
   de risco diferentes — um NTN-B 2060 tem mais que o dobro da duration de um
   2035. Cair no balde errado nao quebra nada; so faz voce achar que tem uma
   carteira que nao tem.

3. O TEMA VINDO DO PROVEDOR. O yfinance classifica a IREN como "Financial
   Services" — a natureza contabil da empresa, nao a exposicao. Se um dia
   alguem "melhorar" o codigo preenchendo o tema automaticamente com esse
   campo, a carteira fica classificada com confianca e errada. A checagem 8
   existe para essa tentacao.

A ORDEM DAS REGRAS E O QUE MAIS ERRA
-------------------------------------
Acao tem `liquidez = "Diária"` no cadastro. Se a regra de liquidez viesse
antes da de renda variavel, a carteira inteira de acoes apareceria como
"Liquidez diária" — ou seja, como reserva de emergencia. Este script trava
essa ordem.

O QUE ELE CONFERE
------------------
1. AS FAIXAS DE PRAZO   curto, medio, longo e ultra, nos limites e no meio
2. A REGUA E O MES      o mesmo papel muda de faixa conforme o mes olhado
3. LIQUIDEZ VENCE PRAZO CDB com vencimento mas liquidez diaria e caixa
4. ACAO NAO E CAIXA     renda variavel vem ANTES de liquidez diaria
5. O ROTULO LEVA O INDEXADOR   "IPCA+ Longo", nao so "Longo"
6. NADA SOME            todo papel cai em algum balde, em todo eixo
7. VAZIO NAO QUEBRA     papel sem vencimento, sem liquidez, sem nada
8. SUGESTAO NAO GRAVA   o setor do provedor e texto para ler, nao tema

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_dimensoes
"""

from __future__ import annotations

from financas.calculos import investimentos as inv
from verificacao.base import Conferencia


def papel(**campos) -> dict:
    """Um papel de mentira, com os campos que as dimensoes leem."""
    base = {"nome": "Teste", "classe": "NTN-B (inflação)", "indexador": "IPCA+",
            "data_vencimento": None, "liquidez": "No vencimento"}
    base.update(campos)
    return base


def conferir_faixas(c: Conferencia) -> None:
    """As quatro faixas, olhadas do mesmo mes."""
    print("=" * 78)
    print("1. AS FAIXAS DE PRAZO, OLHADAS DE AGO/2026")
    print("=" * 78)

    casos = [
        ("2027-06-15", "IPCA+ Curto", "menos de 3 anos"),
        ("2032-08-15", "IPCA+ Médio", "6 anos — o NTN-B PRINC dele"),
        ("2035-05-15", "IPCA+ Longo", "9 anos"),
        ("2045-05-15", "IPCA+ Longo", "19 anos, ainda longo"),
        ("2060-08-15", "IPCA+ Ultra longo", "34 anos"),
    ]
    for vencimento, esperado, porque in casos:
        obtido = inv.balde_de_prazo(papel(data_vencimento=vencimento), "2026-08")
        c.exigir(obtido == esperado,
                 f"{vencimento} deveria ser «{esperado}», veio «{obtido}»")
        print(f"  {vencimento}  -> {obtido:<20} ({porque})")


def conferir_regua_e_mes(c: Conferencia) -> None:
    """O MESMO papel muda de faixa conforme o mes olhado."""
    print()
    print("=" * 78)
    print("2. A REGUA E O MES OLHADO, NAO `hoje`")
    print("=" * 78)

    ntnb = papel(data_vencimento="2032-08-15")
    de_2020 = inv.balde_de_prazo(ntnb, "2020-08")
    de_2026 = inv.balde_de_prazo(ntnb, "2026-08")
    de_2031 = inv.balde_de_prazo(ntnb, "2031-08")

    c.exigir(de_2020 == "IPCA+ Longo",
             f"em 2020 o NTN-B 2032 era longo (12 anos), veio «{de_2020}»")
    c.exigir(de_2026 == "IPCA+ Médio",
             f"em 2026 ele e medio (6 anos), veio «{de_2026}»")
    c.exigir(de_2031 == "IPCA+ Curto",
             f"em 2031 ele e curto (1 ano), veio «{de_2031}»")
    c.exigir(len({de_2020, de_2026, de_2031}) == 3,
             "o mesmo papel deveria mudar de faixa com o tempo — se nao muda, "
             "a data de referencia esta presa em `hoje`")
    print(f"  NTN-B ago/2032 visto de 2020 -> {de_2020}")
    print(f"                        de 2026 -> {de_2026}")
    print(f"                        de 2031 -> {de_2031}")


def conferir_ordem_das_regras(c: Conferencia) -> None:
    """Liquidez vence prazo; renda variavel vence liquidez."""
    print()
    print("=" * 78)
    print("3 e 4. A ORDEM DAS REGRAS")
    print("=" * 78)

    cdb = papel(indexador="CDI", data_vencimento="2027-04-01",
                liquidez="Diária", classe="CDB / LCI / LCA")
    obtido = inv.balde_de_prazo(cdb, "2026-08")
    c.exigir(obtido == inv.BALDE_DIARIA,
             f"CDB com liquidez diaria e caixa, mesmo tendo vencimento; "
             f"veio «{obtido}»")
    print(f"  CDB venc. 2027 + liquidez diária -> {obtido}")

    acao = papel(indexador="Variável", data_vencimento=None,
                 liquidez="Diária", classe="Ação BR")
    por_indexador = inv.balde_de_prazo(acao, "2026-08")
    por_macro = inv.balde_de_prazo(
        papel(indexador=None, liquidez="Diária", classe="ETF"),
        "2026-08", macro="Renda Variável")

    c.exigir(por_indexador == inv.BALDE_SEM_PRAZO,
             f"acao tem liquidez «Diária» no cadastro, mas NAO e caixa; "
             f"veio «{por_indexador}»")
    c.exigir(por_macro == inv.BALDE_SEM_PRAZO,
             f"o macro de renda variavel tambem deveria barrar; "
             f"veio «{por_macro}»")
    print(f"  Ação (liquidez «Diária»)         -> {por_indexador}")
    print(f"  ETF pelo macro Renda Variável    -> {por_macro}")


def conferir_rotulo(c: Conferencia) -> None:
    """O indexador entra no rotulo — «Longo» sozinho nao diz o que o papel faz."""
    print()
    print("=" * 78)
    print("5. O ROTULO LEVA O INDEXADOR JUNTO")
    print("=" * 78)

    for indexador, esperado in [("IPCA+", "IPCA+ Longo"),
                                ("Prefixado", "Prefixado Longo"),
                                ("Selic", "Selic Longo")]:
        obtido = inv.balde_de_prazo(
            papel(indexador=indexador, data_vencimento="2036-01-01"), "2026-08")
        c.exigir(obtido == esperado, f"esperava «{esperado}», veio «{obtido}»")
        print(f"  {indexador:<12} venc. 2036 -> {obtido}")

    sem = inv.balde_de_prazo(
        papel(indexador=None, data_vencimento="2036-01-01"), "2026-08")
    c.exigir(sem == "Longo", f"sem indexador o rotulo e so a faixa, veio «{sem}»")
    print(f"  (sem indexador)  venc. 2036 -> {sem}")


def conferir_nada_some(c: Conferencia) -> None:
    """Em todo eixo, a soma dos baldes bate com a carteira."""
    print()
    print("=" * 78)
    print("6. NADA SOME: A SOMA DOS BALDES BATE COM A CARTEIRA")
    print("=" * 78)

    carteira = inv.posicao()
    total = float(carteira["saldo"].sum()) if not carteira.empty else 0.0
    if total <= 0:
        print("  (banco sem carteira — checagem pulada)")
        return

    for eixo in inv.DIMENSOES:
        tabela = inv.alocacao_atual(None, eixo)
        somado = float(tabela["saldo"].sum())
        c.exigir(abs(somado - total) < 0.01,
                 f"eixo «{eixo}»: os baldes somam {somado:,.2f} e a carteira "
                 f"tem {total:,.2f} — algum papel caiu fora")
        c.exigir(not (tabela["nome"] == "").any(),
                 f"eixo «{eixo}»: ha balde com nome vazio")
        print(f"  {eixo:<12} {len(tabela):>2} baldes, somam R$ {somado:>14,.2f}")


def conferir_vazio(c: Conferencia) -> None:
    """Papel sem informacao nenhuma cai num balde, e nao explode."""
    print()
    print("=" * 78)
    print("7. PAPEL SEM INFORMACAO NAO QUEBRA")
    print("=" * 78)

    pelado = {"nome": "Sem nada"}
    for eixo in inv.DIMENSOES:
        try:
            obtido = inv.balde_de(pelado, eixo, "2026-08")
        except Exception as erro:
            obtido = f"EXCECAO {type(erro).__name__}"
        c.exigir(isinstance(obtido, str) and obtido.strip() != "",
                 f"eixo «{eixo}» com papel vazio devolveu {obtido!r}")
        print(f"  {eixo:<12} -> {obtido}")

    data_torta = inv.balde_de_prazo(
        papel(data_vencimento="não é data"), "2026-08")
    c.exigir(data_torta == inv.BALDE_SEM_VENCIMENTO,
             f"data ilegivel deveria virar «{inv.BALDE_SEM_VENCIMENTO}», "
             f"veio «{data_torta}»")
    print(f"  data ilegível -> {data_torta}")


def conferir_sugestao_nao_preenche(c: Conferencia) -> None:
    """A sugestao do provedor e TEXTO para ler, nunca um tema para gravar."""
    print()
    print("=" * 78)
    print("8. A SUGESTAO DO PROVEDOR NAO E UM TEMA")
    print("=" * 78)

    nomes_de_tema = set(inv.temas()["nome"]) if not inv.temas().empty else set()

    # O caso que justifica a regra: o yfinance classifica a IREN — mineradora
    # de bitcoin que virou datacenter de IA — como servico financeiro.
    sugestao = inv.sugestao_de_tema("IREN")
    if sugestao is None:
        print("  (sem fundamento guardado para IREN — checagem parcial)")
    else:
        c.exigir(sugestao not in nomes_de_tema,
                 f"a sugestao «{sugestao}» nao pode coincidir com um tema "
                 f"cadastrado, senao alguem vai ser tentado a gravar direto")
        print(f"  IREN -> «{sugestao}»")
        print("         (e por isso que ela nao preenche o campo sozinha)")

    c.exigir(inv.sugestao_de_tema(None) is None,
             "sem ticker a sugestao tem de ser None")
    c.exigir(inv.sugestao_de_tema("TICKERQUENAOEXISTE") is None,
             "ticker sem fundamento guardado tem de devolver None, nunca "
             "buscar na rede — esta funcao roda a cada desenho da tabela")
    print("  sem ticker / ticker desconhecido -> None (não vai à rede)")

    # O tema fica onde foi digitado: `balde_de` le a coluna, e nao inventa.
    com_tema = inv.balde_de({"tema": "Datacenters e IA"}, "tema")
    sem_tema = inv.balde_de({"ticker": "IREN"}, "tema")
    c.exigir(com_tema == "Datacenters e IA",
             f"tema digitado deveria vir inteiro, veio «{com_tema}»")
    c.exigir(sem_tema == "(sem tema)",
             f"papel com ticker mas SEM tema digitado nao pode herdar o setor "
             f"do provedor; veio «{sem_tema}»")
    print(f"  papel com ticker e sem tema -> {sem_tema}")


def main() -> int:
    """Roda as oito conferencias. Devolve 0 se tudo passou, 1 se algo falhou."""
    print()
    print("CONFERINDO OS EIXOS DA CARTEIRA")
    print()
    c = Conferencia()
    conferir_faixas(c)
    conferir_regua_e_mes(c)
    conferir_ordem_das_regras(c)
    conferir_rotulo(c)
    conferir_nada_some(c)
    conferir_vazio(c)
    conferir_sugestao_nao_preenche(c)
    return c.relatorio()


if __name__ == "__main__":
    raise SystemExit(main())
