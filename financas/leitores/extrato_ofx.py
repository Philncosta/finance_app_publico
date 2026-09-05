"""
extrato_ofx.py — Le o extrato em OFX (o formato padrao de banco).
==============================================================================

O QUE E OFX
-----------
"Open Financial Exchange" e o formato padrao que bancos do mundo inteiro usam
para exportar extrato. Ele parece HTML, mas nao e: e SGML, um primo mais velho
e mais relaxado do XML.

    OFXHEADER:100
    DATA:OFXSGML
    VERSION:102
    CHARSET:1252

    <OFX>
      <BANKMSGSRSV1><STMTTRNRS><STMTRS>
        <CURDEF>BRL
        <BANKACCTFROM><BANKID>348<ACCTID>12345678<ACCTTYPE>CHECKING</BANKACCTFROM>
        <BANKTRANLIST>
          <DTSTART>20260722
          <DTEND>20260821
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>20260819
            <TRNAMT>-500.00
            <FITID>5ae06205-6d4b-45f3-b820-08b9efde382d
            <MEMO>Transferência enviada para a conta investimento
          </STMTTRN>
        </BANKTRANLIST>
        <LEDGERBAL><BALAMT>47.11<DTASOF>20260821</LEDGERBAL>
      </STMTRS></STMTTRNRS></BANKMSGSRSV1>
    </OFX>

POR QUE O OFX E MELHOR QUE O CSV
--------------------------------
Por causa do campo FITID: "Financial Institution Transaction ID". E um codigo
UNICO que o proprio banco atribui a cada transacao e nunca muda. No seu
arquivo sao 43 transacoes com 43 FITIDs distintos.

Isso resolve o problema mais chato da importacao. Com CSV, para saber se uma
transacao ja foi importada a gente precisa adivinhar comparando data +
descricao + valor — e dois Pix iguais no mesmo minuto confundem. Com FITID nao
tem adivinhacao: se o codigo ja esta no banco, ja foi importado. Ponto.

POR QUE ESCREVI UM PARSER EM VEZ DE INSTALAR UMA BIBLIOTECA
-----------------------------------------------------------
Existe a biblioteca `ofxparse`, mas ela puxa o BeautifulSoup junto, esta pouco
mantida, e o pedaco de OFX que a gente precisa cabe em ~60 linhas. Menos
dependencia = menos coisa para quebrar quando voce atualizar o Python daqui a
um ano. E, como voce esta aprendendo, um parser que da para ler inteiro vale
mais que uma caixa-preta.

POR QUE NAO DA PARA USAR UM PARSER DE XML PRONTO
------------------------------------------------
Repare que <TRNTYPE>DEBIT nao tem </TRNTYPE>. Em SGML o fechamento e opcional
para campos simples. Qualquer parser de XML de verdade recusa esse arquivo com
erro de "tag nao fechada". Por isso lemos com expressao regular, que nao se
importa com isso.

(Bancos mais novos as vezes mandam OFX 2.x, que e XML de verdade e bem
formado. O parser abaixo funciona nos dois casos, porque as tags fechadas
extras simplesmente nao atrapalham.)
"""

from __future__ import annotations

import re
from pathlib import Path

from financas import config
from financas.formato import mes_de, parse_brl, parse_data
from financas.leitores.base import ResultadoLeitura, linha_normalizada

_TAG = re.compile(r"<([A-Za-z0-9_.]+)>([^<\r\n]*)")

_TRANSACAO = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S | re.I)

_TRANSACAO_ABERTA = re.compile(
    r"<STMTTRN>(.*?)(?=<STMTTRN>|</BANKTRANLIST>|</CCSTMTRS>|</STMTRS>|\Z)", re.S | re.I
)


def _campos(bloco: str) -> dict:
    """Transforma um pedaco de OFX num dicionario {TAG: valor}.

    Tags de agrupamento (as que abrem outro nivel, como <BANKACCTFROM>) vem com
    valor vazio e sao descartadas — so interessam os campos com conteudo.
    """
    saida = {}
    for nome, valor in _TAG.findall(bloco):
        valor = valor.strip()
        if valor:
            saida.setdefault(nome.upper(), valor)
    return saida


def _decodificar(dados: bytes) -> str:
    """Converte os bytes do arquivo em texto, descobrindo o encoding de verdade.

    NAO CONFIE NO CABECALHO. O seu arquivo do Banco XP declara

        ENCODING:USASCII
        CHARSET:1252

    mas o conteudo esta gravado em UTF-8. A palavra "Transferência" aparece
    nos bytes como  \\xc3\\xaa  (que e "ê" em UTF-8) e nao como \\xea (que
    seria "ê" em Windows-1252). Obedecendo o cabecalho, sai "TransferÃªncia".
    Foi exatamente esse o bug que apareceu ao testar com o arquivo real.

    A SOLUCAO e usar uma propriedade do proprio UTF-8: ele e AUTOVALIDAVEL.
    As sequencias de bytes de varios caracteres seguem um padrao rigido, e
    texto acentuado em Windows-1252 quase nunca forma um UTF-8 valido por
    acidente. Entao:

        1. Tenta UTF-8 no modo estrito. Se passar, era UTF-8 mesmo.
        2. Se falhar, ai sim usa o charset declarado no cabecalho.
        3. Em ultimo caso, latin-1, que aceita qualquer byte sem dar erro.

    Essa ordem acerta tanto no arquivo que mente (o seu) quanto no que fala a
    verdade.
    """
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass

    cabecalho = dados[:400].decode("ascii", errors="ignore").upper()
    if "CHARSET:1252" in cabecalho or "WINDOWS-1252" in cabecalho:
        try:
            return dados.decode("cp1252")
        except UnicodeDecodeError:
            pass

    return dados.decode("latin-1", errors="replace")


def ler_texto(texto: str, nome_arquivo: str = "") -> ResultadoLeitura:
    """Le um OFX ja decodificado e devolve o resultado normalizado."""
    resultado = ResultadoLeitura()

    if "<OFX" not in texto.upper():
        resultado.erros.append(
            "Este arquivo nao parece ser um OFX (nao achei a marca <OFX>)."
        )
        return resultado

    cabecalho = _campos(texto[:4000])
    periodo_inicio = parse_data(cabecalho.get("DTSTART"))
    periodo_fim = parse_data(cabecalho.get("DTEND"))

    saldo_final = None
    data_saldo = None
    bloco_saldo = re.search(
        r"<LEDGERBAL>(.*?)(?:</LEDGERBAL>|</STMTRS>|</CCSTMTRS>|\Z)", texto, re.S | re.I
    )
    if bloco_saldo:
        campos_saldo = _campos(bloco_saldo.group(1))
        saldo_final = parse_brl(campos_saldo.get("BALAMT"))
        data_saldo = parse_data(campos_saldo.get("DTASOF"))

    blocos = _TRANSACAO.findall(texto)
    if not blocos:
        blocos = _TRANSACAO_ABERTA.findall(texto)
    if not blocos:
        resultado.erros.append("Não encontrei nenhuma transação (<STMTTRN>) no arquivo.")
        return resultado

    vistos = set()
    for numero, bloco in enumerate(blocos, start=1):
        campos = _campos(bloco)

        data = parse_data(campos.get("DTPOSTED") or campos.get("DTUSER"))
        valor = parse_brl(campos.get("TRNAMT"))

        descricao = (campos.get("MEMO") or campos.get("NAME") or "").strip()
        fitid = (campos.get("FITID") or "").strip() or None

        if data is None:
            resultado.avisos.append(f"transação {numero}: sem data válida, ignorada")
            continue
        if valor is None:
            resultado.avisos.append(f"transação {numero}: sem valor válido, ignorada")
            continue
        if not descricao:
            descricao = campos.get("TRNTYPE", "(sem descrição)").strip()

        if fitid:
            if fitid in vistos:
                resultado.avisos.append(
                    f"transacao {numero}: FITID repetido dentro do proprio arquivo "
                    f"({fitid}). A deduplicacao vai tratar como a mesma transacao."
                )
            vistos.add(fitid)

        resultado.linhas.append(linha_normalizada(
            data=data.isoformat(),
            mes_competencia=mes_de(data),
            descricao=descricao,
            valor=valor,
            fitid=fitid,
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
            "tipo": "Extrato OFX",
            "banco": cabecalho.get("ORG"),
            "conta": cabecalho.get("ACCTID"),
            "moeda": cabecalho.get("CURDEF"),
            "saldo_final": saldo_final,
            "data_saldo": data_saldo.isoformat() if data_saldo else None,
            "periodo": (
                f"{periodo_inicio.isoformat()} a {periodo_fim.isoformat()}"
                if periodo_inicio and periodo_fim
                else f"{datas[0]} a {datas[-1]}"
            ),
            "total_entradas": entradas,
            "total_saidas": saidas,
            "com_fitid": sum(1 for l in resultado.linhas if l["fitid"]),
            "meses": sorted({l["mes_competencia"] for l in resultado.linhas}),
        }
    return resultado


def ler_arquivo(caminho) -> ResultadoLeitura:
    """Le o OFX direto de um arquivo em disco.

    Abrimos em modo BINARIO ("rb") porque so depois de ler o cabecalho e que
    sabemos qual encoding usar.
    """
    caminho = Path(caminho)
    try:
        dados = caminho.read_bytes()
    except OSError as erro:
        resultado = ResultadoLeitura()
        resultado.erros.append(f"Não consegui abrir o arquivo: {erro}")
        return resultado
    return ler_texto(_decodificar(dados), caminho.name)


def ler_bytes(dados: bytes, nome_arquivo: str = "") -> ResultadoLeitura:
    """Le o OFX a partir dos bytes (e o que o upload do Streamlit entrega)."""
    return ler_texto(_decodificar(dados), nome_arquivo)
