"""
extrato_csv.py — Le o CSV do extrato da conta corrente.
==============================================================================

O ARQUIVO DE ENTRADA
--------------------
Nome:     extrato_de_01-01-2026_ate_01-04-2026.csv
Colunas:  Data;Hora;Descricao;Valor;Saldo

    Data;Hora;Descricao;Valor;Saldo
    01/04/26;20:20:46;Pix recebido de Débora de Nunes Prado;R$ ····;R$ ····
    01/04/26;14:51:37;Pix enviado para Magalupay;-R$ ····;R$ ····

O QUE MUDA EM RELACAO A FATURA
------------------------------
1. NAO tem BOM (mas abrimos com utf-8-sig do mesmo jeito — se um dia aparecer,
   ja esta tratado, e se nao tiver, nao faz diferenca nenhuma).

2. A data tem ANO COM DOIS DIGITOS: "01/04/26", nao "01/04/2026". O
   parse_data ja sabe lidar com os dois.

3. O VALOR JA VEM COM O SINAL CERTO. "-R$ ····" saiu, "R$ ····" entrou.
   Diferente da fatura, aqui NAO invertemos nada.

4. Tem coluna HORA. Isso e mais util do que parece: e o que permite
   diferenciar dois Pix do mesmo valor para a mesma pessoa no mesmo dia. Sem a
   hora, o sistema acharia que sao a mesma transacao e descartaria a segunda.

5. Tem coluna SALDO (quanto sobrou na conta depois). Guardamos porque a
   pagina de Patrimonio usa o ultimo saldo do mes.

6. O mes de competencia e simplesmente o mes da data — nao vem do nome do
   arquivo como na fatura.

CUIDADO COM O PERIODO DOS ARQUIVOS
----------------------------------
Os seus extratos se sobrepoem: um vai de 08/05 a 06/08 e o OFX vai de 22/07 a
21/08. Os dias entre 22/07 e 06/08 aparecem NOS DOIS. Quem resolve isso e a
deduplicacao no importador — este leitor so le o que esta escrito.
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from financas import config
from financas.formato import mes_de, normalizar_texto, parse_brl, parse_data, vazio
from financas.leitores.base import ResultadoLeitura, linha_normalizada

APELIDOS = {
    "data": {"data", "datalancamento", "datamovimento"},
    "hora": {"hora", "horario"},
    "descricao": {"descricao", "historico", "lancamento", "detalhe", "movimentacao"},
    "valor": {"valor", "valorbrl", "montante"},
    "saldo": {"saldo", "saldoapos", "saldofinal"},
}


def _chave_limpa(texto: str) -> str:
    return re.sub(r"[^a-z]", "", normalizar_texto(texto).lower())


def _mapear_colunas(cabecalho: list[str]) -> dict:
    mapa = {}
    for coluna in cabecalho:
        if coluna is None:
            continue
        limpo = _chave_limpa(coluna)
        for campo, aceitos in APELIDOS.items():
            if limpo in aceitos and campo not in mapa:
                mapa[campo] = coluna
    return mapa


def ler_texto(texto: str, nome_arquivo: str = "") -> ResultadoLeitura:
    """Le o conteudo do extrato ja em texto e devolve o resultado normalizado."""
    resultado = ResultadoLeitura()

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
        valor = parse_brl(bruto_valor)

        if data is None:
            resultado.avisos.append(f"linha {numero}: data ilegível ({bruto_data!r}), linha ignorada")
            continue
        if valor is None:
            resultado.avisos.append(f"linha {numero}: valor ilegível ({bruto_valor!r}), linha ignorada")
            continue
        if not descricao:
            descricao = "(sem descrição)"

        hora = (registro.get(mapa["hora"]) or "").strip() if "hora" in mapa else None
        saldo = parse_brl(registro.get(mapa["saldo"])) if "saldo" in mapa else None

        resultado.linhas.append(linha_normalizada(
            data=data.isoformat(),
            hora=hora or None,
            mes_competencia=mes_de(data),
            descricao=descricao,
            valor=valor,
            saldo_apos=saldo,
            origem=config.ORIGEM_EXTRATO,
            linha_arquivo=numero,
        ))

    if not resultado.linhas and not resultado.erros:
        resultado.erros.append("Nenhuma transação válida foi encontrada no arquivo.")

    if resultado.linhas:
        datas = sorted(linha["data"] for linha in resultado.linhas)
        entradas = sum(l["valor"] for l in resultado.linhas if l["valor"] > 0)
        saidas = sum(l["valor"] for l in resultado.linhas if l["valor"] < 0)
        resultado.meta = {
            "tipo": "Extrato CSV",
            "periodo": f"{datas[0]} a {datas[-1]}",
            "total_entradas": entradas,
            "total_saidas": saidas,
            "meses": sorted({l["mes_competencia"] for l in resultado.linhas}),
        }
    return resultado


def ler_arquivo(caminho) -> ResultadoLeitura:
    """Le o extrato direto de um arquivo em disco."""
    caminho = Path(caminho)
    try:
        texto = caminho.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as erro:
        resultado = ResultadoLeitura()
        resultado.erros.append(f"Não consegui abrir o arquivo: {erro}")
        return resultado
    return ler_texto(texto, caminho.name)
