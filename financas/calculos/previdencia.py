"""previdencia.py — PGBL, VGBL e a conta que os simuladores nao mostram.

==============================================================================

O QUE ESTE MODULO FAZ
---------------------
Responde tres perguntas, nesta ordem — e a ordem importa, porque a segunda so
faz sentido se a primeira der "completa":

    1. Para voce, a declaracao COMPLETA ganha da SIMPLIFICADA?
    2. Se ganha, qual o teto legal do aporte em PGBL, e quanto ele economiza?
    3. Essa economia sobrevive ao resgate, la na frente?

O QUE ELE NAO FAZ
-----------------
Nao recomenda plano, corretora nem produto, e nao substitui contador. Ele faz
a ARITMETICA DO IMPOSTO sobre os numeros que voce informar, e mostra os dois
lados dela. A escolha continua sendo sua.

AS QUATRO COISAS QUE ESTE MODULO EXISTE PARA DIZER
==================================================

**1. NA DECLARACAO SIMPLIFICADA, O PGBL VALE EXATAMENTE ZERO.**
O desconto simplificado (20% da renda, ate um teto) SUBSTITUI todas as
deducoes — inclusive a previdencia complementar. Por isso `apurar()` calcula
os dois modelos sempre, e `beneficio_do_aporte()` devolve economia zero
quando a simplificada ganha. Um simulador que pula esta pergunta pode
prometer economia que nao existe.

**2. O BENEFICIO NAO E 27,5%.**
A deducao derruba a base e pode atravessar faixa: parte abatida a 27,5%,
parte a 22,5%. Por isso a economia e sempre calculada como DIFERENCA entre
dois impostos apurados de verdade, nunca como `aporte x aliquota`. A
`aliquota_efetiva` devolvida e o resultado da conta, nao a entrada dela.

**3. O PGBL NAO E DESCONTO. E ADIAMENTO.**
No resgate, o IR do PGBL incide sobre o **valor total** — aporte mais
rendimento. O VGBL so sobre o rendimento. A economia de hoje e um emprestimo
que se paga depois, e se paga menos SE voce ficar na tabela regressiva ate os
10% (dez anos) e SE reinvestir a restituicao. E o que
`comparar_com_alternativa()` poe lado a lado.

**4. ABAIXO DE R$ ···· DE RENDIMENTO TRIBUTAVEL EM 2026, NAO HA O QUE
ECONOMIZAR.** O redutor da Lei 15.270/2025 ja zera o imposto ate ali. Nao da
para economizar imposto que nao existe — e nenhum simulador diz isso.

DE ONDE VEM CADA NUMERO
=======================
As tabelas sao da Receita Federal. Elas mudam por lei, e por isso ficam numa
constante datada, com o ano que cada uma vale — nunca "a tabela atual".

    ano-calendario 2025   Lei 15.191/2025    (declaracao entregue em 2026)
    ano-calendario 2026   Lei 15.270/2025    (declaracao entregue em 2027)

Ano sem tabela cadastrada devolve `None` e a tela avisa. **Nao se usa a
tabela do ano passado no lugar**: erraria em silencio, que e o defeito que
este projeto mais persegue.

A ARMADILHA CENTRAL: O BRUTO
============================
O teto de 12% e sobre a **renda bruta tributavel sujeita ao ajuste anual** —
e este app so ve o LIQUIDO que caiu na conta. E a mesma advertencia que abre
a tela de Imposto, e aqui ela e ainda mais cara, porque o erro vira um aporte
de tamanho errado.

Por isso nada aqui adivinha o bruto. Os numeros vem do **informe de
rendimentos**, digitados uma vez por ano e guardados na tabela `ir_ano`.

E ATENCAO AO QUE **NAO** ENTRA NA BASE DOS 12%: PLR e 13o salario tem
tributacao exclusiva e ficam de fora. Somar a PLR ali inflaria o teto e faria
voce aportar mais do que pode deduzir — o excedente nao volta, so fica preso
num plano de previdencia.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from financas import banco

LIMITE_PGBL = 0.12

TABELAS: dict[str, dict] = {
    "2025": {
        "lei": "Lei 15.191/2025",
        "faixas": [
            (28467.20, 0.000, 0.00),
            (33919.80, 0.075, 2135.04),
            (45012.60, 0.150, 4679.03),
            (55976.16, 0.225, 8054.97),
            (float("inf"), 0.275, 10853.78),
        ],
        "desconto_simplificado": 0.20,
        "teto_simplificado": 16754.34,
        "dependente": 2275.08,
        "teto_instrucao": 3561.50,
        "redutor": None,
    },
    "2026": {
        "lei": "Lei 15.270/2025",
        "faixas": [
            (29145.60, 0.000, 0.00),
            (33919.80, 0.075, 2185.92),
            (45012.60, 0.150, 4729.91),
            (55976.16, 0.225, 8105.85),
            (float("inf"), 0.275, 10904.66),
        ],
        "desconto_simplificado": 0.20,
        "teto_simplificado": 17640.00,
        "dependente": 2275.08,
        "teto_instrucao": 3561.50,
        "redutor": {
            "piso": 60000.00,
            "teto": 88200.00,
            "valor_maximo": 2694.15,
        },
    },
}

CAMPOS_DO_ANO = [
    "rendimento_bruto", "inss", "irrf_retido", "dependentes",
    "despesas_medicas", "despesas_instrucao", "pensao_alimenticia",
    "outras_deducoes", "aportes_pgbl", "contribui_inss",
]


def anos_com_tabela() -> list[str]:
    """Os anos-calendario cuja tabela do IR esta cadastrada aqui."""
    return sorted(TABELAS)


def tabela_do_ano(ano) -> dict | None:
    """A tabela do ano, ou None se ela nao existe neste modulo.

    Devolver None e deliberado. A alternativa — cair na tabela do ano anterior
    — produziria um numero plausivel e errado, e ninguem perceberia.
    """
    return TABELAS.get(str(ano))


def imposto_pela_tabela(base: float, ano) -> float | None:
    """O imposto anual devido sobre uma base de calculo, pela tabela do ano.

    E a tabela progressiva por FAIXAS, na forma que a Receita publica:
    aliquota da faixa em que a base cai, menos a "parcela a deduzir" — que e o
    atalho que embute o imposto menor das faixas anteriores.

    Base negativa ou zero devolve 0,0: deducao maior que a renda nao gera
    credito.
    """
    tabela = tabela_do_ano(ano)
    if tabela is None:
        return None
    base = max(0.0, float(base or 0.0))
    for limite, aliquota, parcela in tabela["faixas"]:
        if base <= limite:
            return round(max(0.0, base * aliquota - parcela), 2)
    return 0.0


def redutor_do_ano(rendimento_tributavel: float, ano) -> float:
    """A reducao da Lei 15.270/2025, que vale a partir do ano-calendario 2026.

    A lei fixa DOIS pontos e diz que entre eles a reducao e linear:

        rendimento ate R$ ····     reducao de R$ ····
        rendimento de R$ ····      reducao de R$ ····

    O coeficiente sai desses dois pontos, e nao de uma constante copiada — se
    a lei mudar um dos extremos, muda so ali em cima.

    DOIS DETALHES QUE MUDAM A CONTA DO PGBL:

      1. O redutor olha para o RENDIMENTO TRIBUTAVEL, nao para a base depois
         das deducoes. Aportar em PGBL **nao aumenta** o redutor.
      2. Ele e limitado ao imposto devido (ver `apurar`), entao nao vira
         restituicao extra.

    Junte os dois e sai a conclusao que nenhum simulador mostra: com ate
    R$ ···· de rendimento tributavel em 2026, o imposto ja e zero, e o PGBL
    nao tem o que economizar.
    """
    tabela = tabela_do_ano(ano)
    if tabela is None or not tabela.get("redutor"):
        return 0.0
    regra = tabela["redutor"]
    rendimento = max(0.0, float(rendimento_tributavel or 0.0))
    if rendimento <= regra["piso"]:
        return regra["valor_maximo"]
    if rendimento >= regra["teto"]:
        return 0.0
    faixa = regra["teto"] - regra["piso"]
    return round(regra["valor_maximo"] * (regra["teto"] - rendimento) / faixa, 2)


def teto_pgbl(rendimento_bruto: float) -> float:
    """12% da renda bruta tributavel — o maximo dedutivel no ano.

    Aporte acima disto nao e proibido: ele so nao deduz. O dinheiro fica no
    plano, e no resgate sera tributado como PGBL — sobre o total — sem nunca
    ter dado o desconto que justifica esse tratamento. E o pior dos dois
    mundos, e por isso o teto aparece na tela como um limite, nao como uma
    sugestao.
    """
    return round(max(0.0, float(rendimento_bruto or 0.0)) * LIMITE_PGBL, 2)


def deducoes_legais(dados: dict, ano, aporte_pgbl: float | None = None) -> dict:
    """As deducoes da declaracao COMPLETA, uma a uma, ja com os tetos aplicados.

    Devolve um dicionario com cada parcela separada, e nao so o total, porque
    a tela precisa mostrar de onde veio cada real — e porque e assim que voce
    percebe que uma delas esta zerada por engano.

    OS TETOS QUE ESTA FUNCAO APLICA:

        instrucao    R$ ···· por pessoa/ano (voce + cada dependente).
                     Escola, faculdade, pos. **Curso livre e idioma nao
                     entram**, e material escolar tambem nao.
        dependente   R$ ···· por dependente/ano.
        medicas      sem teto — mas so despesa MEDICA: consulta, exame,
                     internacao, plano de saude, dentista, fisioterapia,
                     psicologo. **Farmacia nao entra.**
        pgbl         12% da renda bruta tributavel, e so para quem contribui
                     para o INSS ou RPPS (ou ja e aposentado).

    O aporte informado acima do teto e CORTADO no teto, nao recusado: a
    pergunta que a tela faz e "quanto disso deduz?", e a resposta e essa.
    """
    tabela = tabela_do_ano(ano)
    if tabela is None:
        return {}

    dependentes = int(dados.get("dependentes") or 0)
    bruto = float(dados.get("rendimento_bruto") or 0.0)
    aporte = (float(dados.get("aportes_pgbl") or 0.0)
              if aporte_pgbl is None else float(aporte_pgbl))

    pessoas = 1 + dependentes
    instrucao = min(float(dados.get("despesas_instrucao") or 0.0),
                    tabela["teto_instrucao"] * pessoas)

    if int(dados.get("contribui_inss") or 0):
        previdencia = min(aporte, teto_pgbl(bruto))
    else:
        previdencia = 0.0

    parcelas = {
        "inss": round(float(dados.get("inss") or 0.0), 2),
        "dependentes": round(dependentes * tabela["dependente"], 2),
        "medicas": round(float(dados.get("despesas_medicas") or 0.0), 2),
        "instrucao": round(instrucao, 2),
        "pensao": round(float(dados.get("pensao_alimenticia") or 0.0), 2),
        "outras": round(float(dados.get("outras_deducoes") or 0.0), 2),
        "previdencia_pgbl": round(previdencia, 2),
    }
    parcelas["total"] = round(sum(parcelas.values()), 2)
    parcelas["instrucao_teto"] = round(tabela["teto_instrucao"] * pessoas, 2)
    parcelas["instrucao_cortada"] = round(
        max(0.0, float(dados.get("despesas_instrucao") or 0.0)
            - parcelas["instrucao"]), 2)
    parcelas["pgbl_teto"] = teto_pgbl(bruto)
    parcelas["pgbl_cortado"] = round(max(0.0, aporte - previdencia), 2)
    return parcelas


def apurar(dados: dict, ano, aporte_pgbl: float | None = None) -> dict | None:
    """A apuracao completa do ano: os dois modelos, lado a lado.

    Devolve, entre outras chaves:

        completa_base / completa_imposto      declaracao por deducoes legais
        simplificada_base / simplificada_imposto
        modelo            'completa' | 'simplificada' — o que paga MENOS
        imposto_devido    o do modelo vencedor, ja com o redutor
        redutor           a reducao da Lei 15.270 aplicada (2026 em diante)
        saldo             positivo = a pagar; negativo = a restituir
        deducoes          o detalhamento de `deducoes_legais`

    O REDUTOR ENTRA DEPOIS, E LIMITADO AO IMPOSTO. Ele nao e deducao de base:
    e abatimento do imposto ja calculado, e nao pode virar credito. Por isso
    `min(redutor, imposto)`.

    A ESCOLHA DO MODELO E POR MENOR IMPOSTO, e nao por maior deducao. Sao
    coisas diferentes quando o redutor entra: ele pode zerar os dois lados, e
    ai tanto faz.
    """
    tabela = tabela_do_ano(ano)
    if tabela is None:
        return None

    bruto = float(dados.get("rendimento_bruto") or 0.0)
    deducoes = deducoes_legais(dados, ano, aporte_pgbl)

    completa_base = max(0.0, bruto - deducoes["total"])
    completa_imposto = imposto_pela_tabela(completa_base, ano)

    desconto = min(bruto * tabela["desconto_simplificado"],
                   tabela["teto_simplificado"])
    simplificada_base = max(0.0, bruto - desconto)
    simplificada_imposto = imposto_pela_tabela(simplificada_base, ano)

    bruto_redutor = redutor_do_ano(bruto, ano)
    completa_final = round(max(0.0, completa_imposto
                               - min(bruto_redutor, completa_imposto)), 2)
    simplificada_final = round(max(0.0, simplificada_imposto
                                   - min(bruto_redutor, simplificada_imposto)), 2)

    if completa_final <= simplificada_final:
        modelo, devido = "completa", completa_final
        antes_do_redutor = completa_imposto
    else:
        modelo, devido = "simplificada", simplificada_final
        antes_do_redutor = simplificada_imposto

    retido = float(dados.get("irrf_retido") or 0.0)
    return {
        "ano": str(ano),
        "lei": tabela["lei"],
        "rendimento_bruto": round(bruto, 2),
        "deducoes": deducoes,
        "completa_base": round(completa_base, 2),
        "completa_imposto": completa_final,
        "simplificada_desconto": round(desconto, 2),
        "simplificada_base": round(simplificada_base, 2),
        "simplificada_imposto": simplificada_final,
        "modelo": modelo,
        "imposto_devido": devido,
        "imposto_antes_do_redutor": round(antes_do_redutor, 2),
        "redutor": round(min(bruto_redutor, antes_do_redutor), 2),
        "redutor_disponivel": bruto_redutor,
        "irrf_retido": round(retido, 2),
        "saldo": round(devido - retido, 2),
    }


def beneficio_do_aporte(dados: dict, ano, aporte: float) -> dict | None:
    """Quanto de imposto um aporte em PGBL economiza — apurando duas vezes.

    A economia sai da DIFERENCA entre duas apuracoes completas (uma sem
    aporte, outra com), e nunca de `aporte x aliquota`. E a unica forma de
    acertar quando a deducao atravessa faixa da tabela, e a unica que devolve
    zero quando a simplificada ganha.

    Devolve:
        economia            imposto sem o aporte menos imposto com o aporte
        aliquota_efetiva    economia / aporte deduzido — o resultado da conta
        aporte_deduzido     a parte do aporte que coube no teto de 12%
        aporte_perdido      a parte que passou do teto e nao deduz nada
        modelo_sem / modelo_com   qual declaracao ganha em cada cenario
        vale_a_pena         False quando a economia e zero
        motivo              por que e zero, quando e
    """
    tabela = tabela_do_ano(ano)
    if tabela is None:
        return None

    sem = apurar(dados, ano, aporte_pgbl=0.0)
    com = apurar(dados, ano, aporte_pgbl=aporte)

    deduzido = com["deducoes"]["previdencia_pgbl"]
    economia = round(sem["imposto_devido"] - com["imposto_devido"], 2)

    motivo = ""
    if not int(dados.get("contribui_inss") or 0):
        motivo = ("A deducao do PGBL exige contribuicao ao INSS ou a regime "
                  "proprio (ou ser aposentado). Sem isso ela nao existe.")
    elif economia <= 0 and sem["imposto_devido"] <= 0:
        motivo = ("Nao ha imposto a economizar: pela tabela deste ano voce ja "
                  "nao deve nada.")
    elif economia <= 0 and com["modelo"] == "simplificada":
        motivo = ("Para voce a declaracao SIMPLIFICADA paga menos, e nela o "
                  "desconto de 20% substitui todas as deducoes — o PGBL nao "
                  "entra na conta.")
    elif deduzido <= 0:
        motivo = "O aporte informado e zero, ou passou inteiro do teto de 12%."

    return {
        "aporte": round(float(aporte or 0.0), 2),
        "aporte_deduzido": deduzido,
        "aporte_perdido": com["deducoes"]["pgbl_cortado"],
        "economia": max(0.0, economia),
        "aliquota_efetiva": (round(economia / deduzido, 4)
                             if deduzido > 0 and economia > 0 else 0.0),
        "imposto_sem": sem["imposto_devido"],
        "imposto_com": com["imposto_devido"],
        "modelo_sem": sem["modelo"],
        "modelo_com": com["modelo"],
        "vale_a_pena": economia > 0,
        "motivo": motivo,
    }


def quanto_aportar(dados: dict, ano) -> dict | None:
    """O teto do ano, o que ja foi aportado e o que falta ate 31/12.

    O PRAZO E PARTE DA RESPOSTA. O aporte so conta para o ano-calendario se
    for feito ate 31 de dezembro dele — feito em janeiro, deduz so na
    declaracao do ano seguinte. Por isso `dias_ate_o_prazo` vem junto.
    """
    tabela = tabela_do_ano(ano)
    if tabela is None:
        return None

    bruto = float(dados.get("rendimento_bruto") or 0.0)
    ja = float(dados.get("aportes_pgbl") or 0.0)
    teto = teto_pgbl(bruto)
    falta = round(max(0.0, teto - ja), 2)

    prazo = date(int(ano), 12, 31)
    hoje = date.today()
    beneficio = beneficio_do_aporte(dados, ano, teto)

    return {
        "ano": str(ano),
        "teto": teto,
        "ja_aportado": round(ja, 2),
        "falta": falta,
        "excedeu": round(max(0.0, ja - teto), 2),
        "prazo": prazo.isoformat(),
        "dias_ate_o_prazo": (prazo - hoje).days,
        "prazo_vencido": hoje > prazo,
        "por_mes_ate_o_prazo": (
            round(falta / max(1, (prazo.year - hoje.year) * 12
                              + prazo.month - hoje.month + 1), 2)
            if not (hoje > prazo) else 0.0),
        "economia_no_teto": beneficio["economia"] if beneficio else 0.0,
        "aliquota_efetiva": beneficio["aliquota_efetiva"] if beneficio else 0.0,
        "vale_a_pena": beneficio["vale_a_pena"] if beneficio else False,
        "motivo": beneficio["motivo"] if beneficio else "",
    }


def aliquota_regressiva(anos: float) -> float:
    """A aliquota da tabela regressiva da previdencia, pelo tempo do aporte.

    Comeca em 35% e cai 5 pontos a cada dois anos, ate 10% depois de dez anos.
    E por APORTE, nao pela idade do plano: dinheiro que entrou ano passado tem
    o relogio dele.
    """
    if anos < 2:
        return 0.35
    if anos < 4:
        return 0.30
    if anos < 6:
        return 0.25
    if anos < 8:
        return 0.20
    if anos < 10:
        return 0.15
    return 0.10


def comparar_com_alternativa(aporte: float, economia: float, anos: float,
                             retorno_aa: float,
                             taxa_adm_aa: float = 0.0,
                             aliquota_alternativa: float = 0.15,
                             reinveste_a_restituicao: bool = True) -> dict:
    """PGBL contra o mesmo dinheiro investido fora dele. A conta do outro lado.

    O QUE ESTA COMPARACAO EXISTE PARA MOSTRAR
    -----------------------------------------
    Os simuladores param na restituicao. Mas o PGBL e tributado no resgate
    sobre o **valor total** — aporte mais rendimento — enquanto o dinheiro
    investido por fora paga so sobre o **ganho**. A economia de hoje e um
    emprestimo, e esta funcao diz quanto dele fica com voce.

    OS TRES "SE" QUE DECIDEM
    ------------------------
      1. **SE voce ficar tempo suficiente.** Antes de dez anos a aliquota
         regressiva e maior que os 15% do investimento comum, e a conta pode
         inverter. Por isso `anos` e entrada, nao suposicao.
      2. **SE voce reinvestir a restituicao.** Ela e o beneficio inteiro. Se
         virar gasto, sobra o custo e nao sobra o ganho —
         `reinveste_a_restituicao=False` mostra esse cenario.
      3. **SE a taxa do plano nao comer a diferenca.** Meio ponto ao ano por
         dez anos nao e detalhe.

    Devolve o liquido dos dois caminhos e a diferenca entre eles. Nao devolve
    recomendacao: os numeros sao seus, a escolha tambem.
    """
    aporte = float(aporte or 0.0)
    economia = float(economia or 0.0)
    anos = float(anos or 0.0)
    liquido_aa = float(retorno_aa or 0.0) - float(taxa_adm_aa or 0.0)

    bruto_pgbl = aporte * (1 + liquido_aa) ** anos
    aliquota = aliquota_regressiva(anos)
    liquido_pgbl = bruto_pgbl * (1 - aliquota)

    if reinveste_a_restituicao:
        bruto_extra = economia * (1 + float(retorno_aa or 0.0)) ** anos
        liquido_pgbl += bruto_extra - max(0.0, bruto_extra - economia) * \
            aliquota_alternativa

    bruto_fora = aporte * (1 + float(retorno_aa or 0.0)) ** anos
    liquido_fora = bruto_fora - max(0.0, bruto_fora - aporte) * aliquota_alternativa

    return {
        "anos": anos,
        "aporte": round(aporte, 2),
        "economia_reinvestida": round(economia if reinveste_a_restituicao else 0.0, 2),
        "aliquota_pgbl": aliquota,
        "aliquota_alternativa": aliquota_alternativa,
        "bruto_pgbl": round(bruto_pgbl, 2),
        "liquido_pgbl": round(liquido_pgbl, 2),
        "bruto_fora": round(bruto_fora, 2),
        "liquido_fora": round(liquido_fora, 2),
        "diferenca": round(liquido_pgbl - liquido_fora, 2),
        "pgbl_ganha": liquido_pgbl > liquido_fora,
    }


def comparar_com_vgbl(aporte: float, economia: float, anos: float,
                      retorno_aa: float, taxa_adm_aa: float = 0.0,
                      aliquota_alternativa: float = 0.15,
                      reinveste_a_restituicao: bool = True) -> dict:
    """PGBL contra VGBL — a comparacao certa, e a que da a resposta mais limpa.

    Os dois planos sao a mesma aplicacao com o mesmo prazo e a mesma tabela
    regressiva. Muda uma coisa so:

        PGBL   deduz na entrada, e no resgate paga sobre o TOTAL
        VGBL   nao deduz nada,  e no resgate paga so sobre o GANHO

    Chame o montante final de X, o aporte de A e a aliquota de a. Entao:

        liquido PGBL = X - a*X       = X*(1-a)
        liquido VGBL = X - a*(X - A) = X*(1-a) + a*A

    A diferenca e **a*A** — o imposto sobre o proprio aporte, que so o PGBL
    paga. Ela nao depende do retorno nem do prazo.

    DAI SAI A REGRA INTEIRA, e ela cabe numa linha:

        **Sem a deducao, o VGBL ganha do PGBL por 10% do aporte. Sempre.**

    O PGBL so faz sentido para quem consegue deduzir de verdade — declaracao
    completa, contribuindo para o INSS, e reinvestindo a restituicao. Fora
    disso ele e um VGBL que paga imposto a mais.

    Repare que este resultado nao aparece na comparacao contra um investimento
    comum (`comparar_com_alternativa`): la o PGBL, mesmo sem deducao nenhuma,
    acaba ganhando depois de uns doze anos, porque 10% sobre tudo passa a
    valer menos que 15% sobre um ganho que ficou grande. Verdade, e comparacao
    errada — se voce nao pode deduzir, sua alternativa nao e um CDB, e o VGBL.
    """
    aporte = float(aporte or 0.0)
    economia = float(economia or 0.0)
    anos = float(anos or 0.0)
    liquido_aa = float(retorno_aa or 0.0) - float(taxa_adm_aa or 0.0)
    aliquota = aliquota_regressiva(anos)

    montante = aporte * (1 + liquido_aa) ** anos
    liquido_pgbl = montante * (1 - aliquota)
    liquido_vgbl = montante - max(0.0, montante - aporte) * aliquota

    if reinveste_a_restituicao and economia > 0:
        bruto_extra = economia * (1 + float(retorno_aa or 0.0)) ** anos
        liquido_pgbl += (bruto_extra
                         - max(0.0, bruto_extra - economia) * aliquota_alternativa)

    return {
        "anos": anos,
        "aliquota": aliquota,
        "liquido_pgbl": round(liquido_pgbl, 2),
        "liquido_vgbl": round(liquido_vgbl, 2),
        "diferenca": round(liquido_pgbl - liquido_vgbl, 2),
        "pgbl_ganha": liquido_pgbl > liquido_vgbl,
        "imposto_extra_do_pgbl": round(aliquota * aporte, 2),
    }


def curva_de_equilibrio(aporte: float, economia: float, retorno_aa: float,
                        taxa_adm_aa: float = 0.0,
                        aliquota_alternativa: float = 0.15,
                        reinveste_a_restituicao: bool = True,
                        ate: int = 30) -> pd.DataFrame:
    """A comparacao ano a ano, para achar em que ano o PGBL passa a ganhar.

    Colunas: anos, aliquota_pgbl, liquido_pgbl, liquido_fora, diferenca,
             pgbl_ganha
    """
    linhas = []
    for anos in range(1, int(ate) + 1):
        resultado = comparar_com_alternativa(
            aporte, economia, anos, retorno_aa, taxa_adm_aa,
            aliquota_alternativa, reinveste_a_restituicao)
        linhas.append({
            "anos": anos,
            "aliquota_pgbl": resultado["aliquota_pgbl"],
            "liquido_pgbl": resultado["liquido_pgbl"],
            "liquido_fora": resultado["liquido_fora"],
            "diferenca": resultado["diferenca"],
            "pgbl_ganha": resultado["pgbl_ganha"],
        })
    return pd.DataFrame(linhas)


def ano_de_virada(curva: pd.DataFrame) -> int | None:
    """O primeiro ano em que o PGBL passa a render mais liquido, ou None."""
    if curva.empty:
        return None
    ganhando = curva[curva["pgbl_ganha"]]
    if ganhando.empty:
        return None
    return int(ganhando.iloc[0]["anos"])


def gasto_por_grande_categoria(df_lancamentos: pd.DataFrame, ano: str,
                               grande_categoria: str) -> float:
    """Quanto voce gastou no ano numa grande categoria — SUGESTAO, nao resposta.

    POR QUE ISTO E SO UM PONTO DE PARTIDA
    -------------------------------------
    A Receita nao aceita "o que voce gastou com saude": aceita despesa MEDICA.
    Farmacia nao entra. Academia nao entra. Em `Educacao`, curso livre e
    idioma nao entram, e material escolar tambem nao.

    Entao este numero serve para voce nao comecar de zero e para lembrar de um
    gasto esquecido — e a tela o apresenta assim, com o aviso junto. Mandar
    ele direto para o campo da declaracao seria inventar dedutibilidade, que e
    exatamente o tipo de chute que o resto deste projeto recusa.
    """
    if df_lancamentos is None or df_lancamentos.empty:
        return 0.0
    df = df_lancamentos
    if "mes_competencia" not in df.columns or "grande_categoria" not in df.columns:
        return 0.0
    do_ano = df[df["mes_competencia"].astype(str).str.startswith(str(ano))]
    do_grupo = do_ano[do_ano["grande_categoria"] == grande_categoria]
    if do_grupo.empty:
        return 0.0
    return round(float(do_grupo["valor"].abs().sum()), 2)


def dados_do_ano(ano) -> dict:
    """Le da tabela `ir_ano` o que voce informou do informe de rendimentos.

    Ano ainda nao preenchido devolve o dicionario com zeros — e nao None —
    para a tela poder desenhar o formulario vazio sem tratar dois casos.
    """
    linha = banco.consultar_um("SELECT * FROM ir_ano WHERE ano = ?", (str(ano),))
    if linha is None:
        vazio = {campo: 0.0 for campo in CAMPOS_DO_ANO}
        vazio["ano"] = str(ano)
        vazio["dependentes"] = 0
        vazio["contribui_inss"] = 1
        vazio["preenchido"] = False
        return vazio
    dados = dict(linha)
    dados["preenchido"] = bool(dados.get("rendimento_bruto"))
    return dados


def salvar_dados_do_ano(ano, valores: dict) -> None:
    """Grava (ou atualiza) os numeros do informe de rendimentos daquele ano."""
    from datetime import datetime

    campos = ", ".join(CAMPOS_DO_ANO)
    marcas = ", ".join("?" for _ in CAMPOS_DO_ANO)
    atualiza = ", ".join(f"{c} = excluded.{c}" for c in CAMPOS_DO_ANO)
    parametros = [str(ano)] + [valores.get(c) or 0 for c in CAMPOS_DO_ANO]
    parametros.append(datetime.now().isoformat(timespec="seconds"))
    banco.executar(
        f"INSERT INTO ir_ano (ano, {campos}, atualizado_em) "
        f"VALUES (?, {marcas}, ?) "
        f"ON CONFLICT(ano) DO UPDATE SET {atualiza}, "
        f"atualizado_em = excluded.atualizado_em",
        tuple(parametros),
    )


def panorama() -> pd.DataFrame:
    """Um ano por linha: base, teto de 12%, aportado, falta e economia.

    E a resposta a "me recomende quanto aplicar por ano" — com a ressalva que
    a tela repete: ano sem informe preenchido aparece vazio, porque o teto sai
    do bruto e o bruto vem do informe.

    Colunas: ano, preenchido, rendimento_bruto, teto, ja_aportado, falta,
             economia_no_teto, aliquota_efetiva, modelo, vale_a_pena
    """
    linhas = []
    for ano in anos_com_tabela():
        dados = dados_do_ano(ano)
        apuracao = apurar(dados, ano)
        recomendacao = quanto_aportar(dados, ano)
        linhas.append({
            "ano": ano,
            "preenchido": dados.get("preenchido", False),
            "rendimento_bruto": float(dados.get("rendimento_bruto") or 0.0),
            "teto": recomendacao["teto"] if recomendacao else 0.0,
            "ja_aportado": recomendacao["ja_aportado"] if recomendacao else 0.0,
            "falta": recomendacao["falta"] if recomendacao else 0.0,
            "economia_no_teto": (recomendacao["economia_no_teto"]
                                 if recomendacao else 0.0),
            "aliquota_efetiva": (recomendacao["aliquota_efetiva"]
                                 if recomendacao else 0.0),
            "modelo": apuracao["modelo"] if apuracao else "",
            "vale_a_pena": recomendacao["vale_a_pena"] if recomendacao else False,
        })
    return pd.DataFrame(linhas)
