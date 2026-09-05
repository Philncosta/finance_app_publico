"""
conferir_previdencia.py — a conta do PGBL bate?
==============================================================================

POR QUE ESTE SCRIPT EXISTE
--------------------------
Esta e a unica tela do app que produz um numero que vira **dinheiro saindo da
conta**: "aporte R$ X em PGBL". Um erro aqui nao deixa um grafico feio — faz
voce aplicar o valor errado, e descobrir na declaracao do ano seguinte.

E as tabelas do IR mudam por lei, todo ano. Um script que confere a tabela
contra valores conhecidos e o que impede a de 2025 continuar rodando em 2028.

O QUE ELE CONFERE
-----------------
1. A tabela progressiva devolve o imposto certo nos pontos conhecidos.
2. O redutor da Lei 15.270/2025 bate nos dois extremos que a lei fixa.
3. Os tetos (12%, instrucao, dependente, desconto simplificado).
4. **As tres situacoes em que o PGBL nao economiza nada** — a parte que os
   simuladores comerciais nao mostram.
5. A economia sai da diferenca entre duas apuracoes, e nao de multiplicacao.
6. A tabela regressiva, a comparacao com o investimento comum e a
   comparacao com o VGBL — que e a certa para quem nao consegue deduzir.
7. Ano sem tabela devolve None, em vez de chutar.

A CONFERENCIA QUE VALE POR TODAS
--------------------------------
Pela tabela de 2026, quem tem R$ ···· de rendimento tributavel e entrega
a **simplificada** paga exatamente **R$ ····** de imposto — e R$ ····
e, ao centavo, o valor maximo do redutor que a lei criou.

Nao e coincidencia: a lei escolheu o numero para **zerar** o imposto de quem
ganha ate R$ ···· por mes. Se a tabela ou o redutor estiverem digitados
errados, essa igualdade quebra. E o teste 2 do bloco de tabelas.

Rode assim:

    .venv\\Scripts\\python -m verificacao.conferir_previdencia
"""

from __future__ import annotations

import sys

from financas.calculos import previdencia as prev
from verificacao.base import Conferencia


def _pessoa(**mudancas) -> dict:
    """Um contribuinte de teste, com os campos que a tabela `ir_ano` guarda."""
    base = {
        "rendimento_bruto": 0.0,
        "inss": 0.0,
        "irrf_retido": 0.0,
        "dependentes": 0,
        "despesas_medicas": 0.0,
        "despesas_instrucao": 0.0,
        "pensao_alimenticia": 0.0,
        "outras_deducoes": 0.0,
        "aportes_pgbl": 0.0,
        "contribui_inss": 1,
    }
    base.update(mudancas)
    return base


def conferir_tabela(placar: Conferencia) -> None:
    """A tabela progressiva e o redutor, contra valores conhecidos."""
    placar.exigir_igual(prev.imposto_pela_tabela(28467.20, "2025"),
                        0.0,
                        "2025: isento no topo da 1a faixa",
                        0.01)
    placar.exigir_igual(prev.imposto_pela_tabela(30000.0, "2025"),
                        114.96,
                        "2025: base 30.000 (faixa de 7,5%)",
                        0.01)
    placar.exigir_igual(prev.imposto_pela_tabela(100000.0, "2025"),
                        16646.22,
                        "2025: base 100.000 (faixa de 27,5%)",
                        0.01)

    placar.exigir_igual(prev.imposto_pela_tabela(29145.60, "2026"),
                        0.0,
                        "2026: isento no topo da 1a faixa",
                        0.01)
    placar.exigir_igual(prev.imposto_pela_tabela(100000.0, "2026"),
                        16595.34,
                        "2026: base 100.000 (faixa de 27,5%)",
                        0.01)

    placar.exigir_igual(prev.imposto_pela_tabela(-5000.0, "2026"),
                        0.0,
                        "base negativa nao gera credito",
                        0.01)

    placar.exigir_igual(prev.redutor_do_ano(60000.0, "2026"),
                        2694.15,
                        "redutor 2026: no piso, o maximo",
                        0.01)
    placar.exigir_igual(prev.redutor_do_ano(30000.0, "2026"),
                        2694.15,
                        "redutor 2026: abaixo do piso, o maximo",
                        0.01)
    placar.exigir_igual(prev.redutor_do_ano(88200.0, "2026"),
                        0.0,
                        "redutor 2026: no teto, zero",
                        0.01)
    placar.exigir_igual(prev.redutor_do_ano(150000.0, "2026"),
                        0.0,
                        "redutor 2026: acima do teto, zero",
                        0.01)
    placar.exigir_igual(prev.redutor_do_ano(74100.0, "2026"),
                        1347.08,
                        "redutor 2026: no meio da faixa, metade",
                        0.02)
    placar.exigir_igual(prev.redutor_do_ano(60000.0, "2025"),
                        0.0,
                        "redutor nao existia em 2025",
                        0.01)

    simplificada = prev.apurar(_pessoa(rendimento_bruto=60000.0), "2026")
    placar.exigir_igual(simplificada["simplificada_imposto"] + simplificada["redutor"],
                        2694.15,
                        "A CONFERENCIA QUE VALE POR TODAS: 60.000 na simplificada de 2026 "
        "paga exatamente o valor do redutor",
                        0.01)
    placar.exigir_igual(simplificada["imposto_devido"],
                        0.0,
                        "...e por isso o imposto devido fica ZERO",
                        0.01)

    placar.exigir_igual(prev.tabela_do_ano("2031"),
                        None,
                        "ano sem tabela devolve None")
    placar.exigir_igual(prev.imposto_pela_tabela(50000.0, "2031"),
                        None,
                        "imposto de ano sem tabela devolve None")
    placar.exigir_igual(prev.apurar(_pessoa(rendimento_bruto=100000.0), "2031"),
                        None,
                        "apurar de ano sem tabela devolve None")


def conferir_tetos(placar: Conferencia) -> None:
    """Os limites de deducao, um a um."""
    placar.exigir_igual(prev.teto_pgbl(100000.0),
                        12000.0,
                        "teto do PGBL e 12% do bruto",
                        0.01)
    placar.exigir_igual(prev.teto_pgbl(0.0),
                        0.0,
                        "teto do PGBL de renda zero e zero",
                        0.01)

    dados = _pessoa(rendimento_bruto=100000.0, dependentes=2,
                    despesas_instrucao=20000.0, despesas_medicas=5000.0,
                    inss=8000.0)
    deducoes = prev.deducoes_legais(dados, "2026")
    placar.exigir_igual(deducoes["instrucao"],
                        10684.50,
                        "instrucao: teto de 3.561,50 x 3 pessoas",
                        0.01)
    placar.exigir_igual(deducoes["instrucao_cortada"],
                        9315.50,
                        "instrucao: o que passou do teto aparece",
                        0.01)
    placar.exigir_igual(deducoes["dependentes"],
                        4550.16,
                        "dependentes: 2 x 2.275,08",
                        0.01)
    placar.exigir_igual(deducoes["medicas"],
                        5000.0,
                        "medicas nao tem teto",
                        0.01)

    acima = prev.deducoes_legais(
        _pessoa(rendimento_bruto=100000.0, aportes_pgbl=20000.0), "2026")
    placar.exigir_igual(acima["previdencia_pgbl"],
                        12000.0,
                        "aporte acima do teto e cortado no teto",
                        0.01)
    placar.exigir_igual(acima["pgbl_cortado"],
                        8000.0,
                        "e a sobra fica visivel, nao some",
                        0.01)


def conferir_quando_nao_vale(placar: Conferencia) -> None:
    """As tres situacoes em que o PGBL economiza ZERO. O coracao da tela."""
    sem_inss = _pessoa(rendimento_bruto=150000.0, inss=0.0, contribui_inss=0)
    resultado = prev.beneficio_do_aporte(sem_inss, "2026", 18000.0)
    placar.exigir_igual(resultado["economia"],
                        0.0,
                        "sem INSS: economia zero",
                        0.01)
    placar.exigir_igual(resultado["aporte_deduzido"],
                        0.0,
                        "sem INSS: nada deduzido",
                        0.01)
    placar.exigir("INSS" in resultado["motivo"],
                  "sem INSS: a tela recebe o motivo")

    magro = _pessoa(rendimento_bruto=120000.0, inss=5000.0)
    resultado = prev.beneficio_do_aporte(magro, "2026", 0.0)
    placar.exigir(prev.apurar(magro, "2026")["modelo"] == "simplificada",
                  "sem deducoes proprias, a simplificada ganha")
    placar.exigir_igual(resultado["economia"],
                        0.0,
                        "aporte zero economiza zero",
                        0.01)

    isento = _pessoa(rendimento_bruto=55000.0, inss=4000.0)
    apuracao = prev.apurar(isento, "2026")
    placar.exigir_igual(apuracao["imposto_devido"],
                        0.0,
                        "2026, renda de 55.000: o redutor ja zera o imposto",
                        0.01)
    resultado = prev.beneficio_do_aporte(isento, "2026", 6600.0)
    placar.exigir_igual(resultado["economia"],
                        0.0,
                        "e por isso o PGBL nao tem o que economizar",
                        0.01)
    placar.exigir("nao deve nada" in resultado["motivo"]
                        or "SIMPLIFICADA" in resultado["motivo"],
                  "com o motivo escrito")


def conferir_beneficio(placar: Conferencia) -> None:
    """A economia sai de duas apuracoes, e nao de `aporte x aliquota`."""
    dados = _pessoa(rendimento_bruto=150000.0, inss=12000.0,
                    despesas_medicas=9000.0, dependentes=1)
    aporte = prev.teto_pgbl(150000.0)
    resultado = prev.beneficio_do_aporte(dados, "2026", aporte)

    placar.exigir(resultado["modelo_com"] == "completa",
                  "com deducoes reais, a completa ganha")
    placar.exigir(resultado["economia"] > 0, "e o aporte economiza imposto")
    placar.exigir_igual(resultado["aporte_deduzido"],
                        aporte,
                        "o aporte inteiro coube no teto",
                        0.01)

    sem = prev.apurar(dados, "2026", aporte_pgbl=0.0)["imposto_devido"]
    com = prev.apurar(dados, "2026", aporte_pgbl=aporte)["imposto_devido"]
    placar.exigir_igual(resultado["economia"],
                        sem - com,
                        "economia = imposto sem - imposto com",
                        0.01)
    placar.exigir(0 < resultado["aliquota_efetiva"] <= 0.275 + 1e-9,
                  "aliquota efetiva fica entre 0 e 27,5%")

    atravessa = _pessoa(rendimento_bruto=70000.0, inss=6000.0,
                        despesas_medicas=8000.0)
    cruzando = prev.beneficio_do_aporte(atravessa, "2026",
                                        prev.teto_pgbl(70000.0))
    if cruzando["economia"] > 0:
        placar.exigir(cruzando["aliquota_efetiva"] < 0.275,
                      "deducao que atravessa faixa rende MENOS que 27,5% do aporte")


def conferir_recomendacao(placar: Conferencia) -> None:
    """O teto do ano, o que falta, e o prazo de 31/12."""
    dados = _pessoa(rendimento_bruto=150000.0, inss=12000.0,
                    despesas_medicas=9000.0, aportes_pgbl=5000.0)
    recomendacao = prev.quanto_aportar(dados, "2026")
    placar.exigir_igual(recomendacao["teto"], 18000.0, "teto do ano", 0.01)
    placar.exigir_igual(recomendacao["ja_aportado"],
                        5000.0,
                        "ja aportado",
                        0.01)
    placar.exigir_igual(recomendacao["falta"],
                        13000.0,
                        "falta ate o teto",
                        0.01)
    placar.exigir_igual(recomendacao["prazo"],
                        "2026-12-31",
                        "prazo e 31 de dezembro do ano-calendario")
    placar.exigir(recomendacao["vale_a_pena"],
                  "a recomendacao diz que vale a pena")

    excedeu = prev.quanto_aportar(
        _pessoa(rendimento_bruto=100000.0, aportes_pgbl=15000.0), "2026")
    placar.exigir_igual(excedeu["falta"],
                        0.0,
                        "aportou alem do teto: falta zero",
                        0.01)
    placar.exigir_igual(excedeu["excedeu"],
                        3000.0,
                        "e o excedente aparece",
                        0.01)


def conferir_resgate(placar: Conferencia) -> None:
    """A tabela regressiva e a comparacao com o investimento comum."""
    placar.exigir_igual(prev.aliquota_regressiva(1),
                        0.35,
                        "1 ano de aporte: 35%")
    placar.exigir_igual(prev.aliquota_regressiva(3), 0.30, "3 anos: 30%")
    placar.exigir_igual(prev.aliquota_regressiva(5), 0.25, "5 anos: 25%")
    placar.exigir_igual(prev.aliquota_regressiva(7), 0.20, "7 anos: 20%")
    placar.exigir_igual(prev.aliquota_regressiva(9), 0.15, "9 anos: 15%")
    placar.exigir_igual(prev.aliquota_regressiva(10), 0.10, "10 anos: 10%")
    placar.exigir_igual(prev.aliquota_regressiva(30),
                        0.10,
                        "30 anos: continua 10%")

    cedo = prev.comparar_com_alternativa(
        aporte=18000.0, economia=4950.0, anos=2, retorno_aa=0.10,
        reinveste_a_restituicao=False)
    placar.exigir(not cedo["pgbl_ganha"],
                  "sem reinvestir a restituicao e resgatando cedo, o PGBL perde")

    tarde = prev.comparar_com_alternativa(
        aporte=18000.0, economia=4950.0, anos=15, retorno_aa=0.10,
        reinveste_a_restituicao=True)
    placar.exigir_igual(tarde["aliquota_pgbl"],
                        0.10,
                        "aos 15 anos a aliquota do PGBL e 10%")
    placar.exigir(tarde["pgbl_ganha"],
                  "reinvestindo e esperando, o PGBL ganha")

    gastou = prev.comparar_com_alternativa(
        aporte=18000.0, economia=4950.0, anos=15, retorno_aa=0.10,
        reinveste_a_restituicao=False)
    placar.exigir(gastou["liquido_pgbl"] < tarde["liquido_pgbl"],
                  "A RESTITUICAO E O BENEFICIO: gasta-la piora o resultado")

    com_taxa = prev.comparar_com_alternativa(
        aporte=18000.0, economia=4950.0, anos=15, retorno_aa=0.10,
        taxa_adm_aa=0.015, reinveste_a_restituicao=True)
    placar.exigir(com_taxa["liquido_pgbl"] < tarde["liquido_pgbl"],
                  "a taxa de administracao come o resultado")

    curva = prev.curva_de_equilibrio(18000.0, 4950.0, 0.10, ate=20)
    placar.exigir_igual(len(curva), 20, "a curva tem um ano por linha")
    virada = prev.ano_de_virada(curva)
    placar.exigir(virada is not None and 1 <= virada <= 20,
                  "existe um ano de virada, e ele e razoavel")

    sem_beneficio = prev.curva_de_equilibrio(18000.0, 0.0, 0.10, ate=30)
    virada_sem = prev.ano_de_virada(sem_beneficio)
    placar.exigir(virada_sem is not None and virada_sem >= 10,
                  "sem deducao, contra um investimento comum o PGBL so ganha depois de "
        "muito tempo (10% sobre tudo x 15% sobre o ganho)")


def conferir_pgbl_contra_vgbl(placar: Conferencia) -> None:
    """A comparacao certa quando nao ha deducao — e o resultado exato dela."""
    aporte = 18000.0
    for anos in (3, 10, 20):
        sem = prev.comparar_com_vgbl(aporte, 0.0, anos, 0.10)
        placar.exigir(not sem["pgbl_ganha"],
                      f"sem deducao, aos {anos} anos o VGBL ganha do PGBL")
        placar.exigir_igual(-sem["diferenca"],
                            sem["aliquota"] * aporte,
                            f"...e ganha por exatamente a aliquota vezes o aporte ({anos} anos)",
                            0.02)

    com = prev.comparar_com_vgbl(aporte, 4950.0, 15, 0.10)
    placar.exigir(com["pgbl_ganha"],
                  "com a deducao reinvestida, o PGBL passa o VGBL")

    gastou = prev.comparar_com_vgbl(aporte, 4950.0, 15, 0.10,
                                    reinveste_a_restituicao=False)
    placar.exigir(not gastou["pgbl_ganha"],
                  "restituicao gasta em vez de reinvestida: o VGBL volta a ganhar")


def main() -> int:
    """Roda todas as checagens e imprime o resultado."""
    placar = Conferencia()
    conferir_tabela(placar)
    conferir_tetos(placar)
    conferir_quando_nao_vale(placar)
    conferir_beneficio(placar)
    conferir_recomendacao(placar)
    conferir_resgate(placar)
    conferir_pgbl_contra_vgbl(placar)

    print()
    print("=" * 78)
    print("  A CONTA DO PGBL BATE?")
    return placar.relatorio()


if __name__ == "__main__":
    sys.exit(main())
