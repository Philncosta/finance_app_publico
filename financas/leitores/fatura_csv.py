"""
fatura_csv.py — Le o CSV da fatura do cartao de credito.
==============================================================================

O ARQUIVO DE ENTRADA
--------------------
Nome:     Fatura2026-01-05.csv   (a data no nome e o VENCIMENTO da fatura)
Colunas:  Data;Estabelecimento;Portador;Valor;Parcela

    Data;Estabelecimento;Portador;Valor;Parcela
    01/12/2025;MP*LUXCRISTAIS;MARIA A DA SILVA;R$ ····;1 de 6
    02/12/2025;UBER * PENDING;CARLOS B DE ANDRADE;R$ ····;-
    03/12/2025;Pagamento de fatura;CARLOS B DE ANDRADE;R$ -R$ ····; de 1

AS QUATRO ARMADILHAS DESTE ARQUIVO
----------------------------------
1. BOM (Byte Order Mark). O arquivo comeca com tres bytes invisiveis que
   marcam "isto e UTF-8". Se voce abrir com encoding="utf-8", o nome da
   primeira coluna vira "﻿Data" em vez de "Data" e nenhuma busca por
   "Data" funciona. Abrindo com "utf-8-sig", o Python descarta o BOM sozinho.

2. Separador ponto e virgula, nao virgula. Porque no Brasil a virgula ja e
   usada como separador decimal.

3. O MES NAO VEM DE DENTRO DO ARQUIVO. Uma fatura que vence em 05/01/2026 tem
   compras de dezembro e parcelas de compras bem mais antigas. Lemos o mes do
   NOME do arquivo — que traz o VENCIMENTO — e RECUAMOS UM MES, porque a
   competencia e o mes em que se gastou: todas contam em 2025-12.
   Quem faz isso e `competencia_da_fatura()`, logo abaixo, e o porque completo
   esta na docstring dela.

4. Nem toda linha e uma compra. Tem pagamento de fatura, estorno e credito
   provisorio, todos com valor NEGATIVO no arquivo. Eles ficam, mas o sinal
   deles e tratado com cuidado (ver abaixo).

O SINAL DO VALOR
----------------
O arquivo e escrito do ponto de vista do CARTAO:
    positivo = voce passou a dever mais (comprou)
    negativo = sua divida diminuiu (pagou ou foi estornado)

Nos guardamos do ponto de vista do SEU DINHEIRO, entao invertemos tudo:

    compra      "R$ ····"    ->  -499.50
    estorno     "R$ -100,24"   ->  +100.24
    pagamento   "R$ -R$ ····" ->  +6220.95
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from financas import config
from financas.formato import parse_brl, parse_data, parse_parcela, vazio
from financas.leitores.base import ResultadoLeitura, linha_normalizada

APELIDOS = {
    "data": {"data", "datacompra", "datadacompra", "dataoperacao"},
    "descricao": {"estabelecimento", "descricao", "historico", "lancamento"},
    "portador": {"portador", "cartao", "titular", "nomeportador"},
    "valor": {"valor", "valorbrl", "valorrs", "montante"},
    "parcela": {"parcela", "parcelas", "parcelamento"},
}


def _chave_limpa(texto: str) -> str:
    """Deixa o nome da coluna comparavel: minusculo, sem acento, sem pontuacao."""
    from financas.formato import normalizar_texto
    return re.sub(r"[^a-z]", "", normalizar_texto(texto).lower())


def _mapear_colunas(cabecalho: list[str]) -> dict:
    """Descobre qual coluna do arquivo corresponde a cada campo que precisamos.

    Devolve algo como {"data": "Data", "valor": "Valor", ...} — a chave e o
    nome interno, o valor e o nome real que aquele arquivo usou.
    """
    mapa = {}
    for coluna in cabecalho:
        if coluna is None:
            continue
        limpo = _chave_limpa(coluna)
        for campo, aceitos in APELIDOS.items():
            if limpo in aceitos and campo not in mapa:
                mapa[campo] = coluna
    return mapa


def mes_do_nome_arquivo(nome: str) -> str | None:
    """Extrai o mes de competencia do NOME do arquivo.

        "Fatura2026-01-05.csv"  -> "2026-01"
        "Fatura_2026-03.csv"    -> "2026-03"
        "fatura 2026-07-05.CSV" -> "2026-07"

    Devolve None se nao achar, e ai a tela de importacao pergunta para voce.
    """
    if vazio(nome):
        return None
    achado = re.search(r"(\d{4})-(\d{2})", str(nome))
    if not achado:
        return None
    ano, mes = int(achado.group(1)), int(achado.group(2))
    if not (1 <= mes <= 12) or not (2000 <= ano <= 2100):
        return None
    return f"{ano:04d}-{mes:02d}"


def competencia_da_fatura(nome: str) -> str | None:
    """Em que mes a fatura do arquivo `nome` PESA — que nao e o mes do nome.

        "Fatura2026-09-05.csv"  -> "2026-08"

    POR QUE RECUA UM MES
    --------------------
    O nome do arquivo traz a data de **vencimento**, e a fatura que vence dia
    05 contem o que foi gasto no mes ANTERIOR. Conferido no historico dele:

        arquivo 2026-09-05  ->  compras de 30/07 a 21/08
        arquivo 2026-08-05  ->  compras de 29/06 a 26/07
        arquivo 2025-12-05  ->  compras de 27/10 a 26/11

    O cartao fecha por volta do dia 25 — o mesmo dia em que o salario dele
    cai. Gasto e salario da mesma quinzena tem de contar no mesmo mes, senao
    o saldo do mes vira ficcao: setembro/2026 aparecia com -R$ ····
    porque tinha a fatura e nenhuma receita.

    SEPARADA DE `mes_do_nome_arquivo` DE PROPOSITO. Aquela e um **parser** e
    responde "o que esta escrito no nome". Esta e a **regra** e responde "em
    que mes isso conta". Misturar as duas esconderia a decisao dentro de uma
    expressao regular.

    E o dinheiro sai da conta so no dia 05 do mes seguinte — quem projeta
    CAIXA desfaz este recuo. Ver `planejamento.projecao_caixa`.
    """
    from financas.formato import somar_meses

    do_nome = mes_do_nome_arquivo(nome)
    return somar_meses(do_nome, -1) if do_nome else None


def ler_texto(texto: str, nome_arquivo: str = "",
              mes_competencia: str | None = None) -> ResultadoLeitura:
    """Le o conteudo da fatura ja em texto e devolve o resultado normalizado.

    Separado de `ler_arquivo` de proposito: o Streamlit entrega o arquivo que
    voce sobe como bytes na memoria, nunca como caminho em disco. Assim os
    dois casos usam exatamente a mesma logica.
    """
    resultado = ResultadoLeitura()

    mes = mes_competencia or competencia_da_fatura(nome_arquivo)
    if not mes:
        resultado.erros.append(
            "Não consegui descobrir o mês da fatura pelo nome do arquivo "
            f"({nome_arquivo!r}). Informe o mês de vencimento na tela de importação."
        )
        return resultado

    leitor = csv.DictReader(io.StringIO(texto), delimiter=";")
    if not leitor.fieldnames:
        resultado.erros.append("O arquivo está vazio ou não tem cabeçalho.")
        return resultado

    mapa = _mapear_colunas(list(leitor.fieldnames))
    faltando = [c for c in ("data", "descricao", "valor") if c not in mapa]
    if faltando:
        resultado.erros.append(
            f"Faltam colunas obrigatórias no arquivo: {', '.join(faltando)}. "
            f"O cabeçalho encontrado foi: {leitor.fieldnames}"
        )
        return resultado

    for numero, registro in enumerate(leitor, start=2):
        bruto_data = registro.get(mapa["data"])
        bruto_valor = registro.get(mapa["valor"])
        descricao = (registro.get(mapa["descricao"]) or "").strip()

        if vazio(bruto_data) and vazio(bruto_valor) and not descricao:
            continue

        data = parse_data(bruto_data)
        valor_arquivo = parse_brl(bruto_valor)

        if data is None:
            resultado.avisos.append(f"linha {numero}: data ilegível ({bruto_data!r}), linha ignorada")
            continue
        if valor_arquivo is None:
            resultado.avisos.append(f"linha {numero}: valor ilegível ({bruto_valor!r}), linha ignorada")
            continue
        if not descricao:
            descricao = "(sem descrição)"

        parcela_texto = registro.get(mapa["parcela"]) if "parcela" in mapa else None
        parcela_atual, parcela_total = parse_parcela(parcela_texto)

        resultado.linhas.append(linha_normalizada(
            data=data.isoformat(),
            mes_competencia=mes,
            descricao=descricao,
            portador=(registro.get(mapa["portador"]) or "").strip() or None
            if "portador" in mapa else None,
            valor=-valor_arquivo,
            parcela_atual=parcela_atual,
            parcela_total=parcela_total,
            parcela_texto=(parcela_texto or "").strip() or None,
            origem=config.ORIGEM_FATURA,
            linha_arquivo=numero,
        ))

    if not resultado.linhas and not resultado.erros:
        resultado.erros.append("Nenhuma transação válida foi encontrada no arquivo.")

    if resultado.linhas:
        datas = sorted(linha["data"] for linha in resultado.linhas)
        gastos = sum(l["valor"] for l in resultado.linhas if l["valor"] < 0)
        creditos = sum(l["valor"] for l in resultado.linhas if l["valor"] > 0)
        resultado.meta = {
            "tipo": "Fatura",
            "mes_competencia": mes,
            "vencimento_do_nome": mes_do_nome_arquivo(nome_arquivo),
            "periodo": f"compras de {datas[0]} a {datas[-1]}",
            "total_gastos": gastos,
            "total_creditos": creditos,
            "parceladas": sum(1 for l in resultado.linhas if l["parcela_total"] > 1),
        }
    return resultado


def ler_arquivo(caminho, mes_competencia: str | None = None) -> ResultadoLeitura:
    """Le a fatura direto de um arquivo em disco.

    O encoding "utf-8-sig" e o detalhe que resolve o BOM. O `errors="replace"`
    e uma rede de seguranca: se aparecer um byte estranho, ele vira "?" em vez
    de derrubar a importacao inteira por causa de um caractere.
    """
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as erro:
        resultado = ResultadoLeitura()
        resultado.erros.append(f"Não consegui abrir o arquivo: {erro}")
        return resultado
    return ler_texto(texto, caminho.name, mes_competencia)
