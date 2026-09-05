"""
formato.py — Traduzir "texto de banco" para numero, e numero para texto bonito.
==============================================================================

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Os arquivos que o banco exporta nao trazem numeros: trazem TEXTO que PARECE
numero. O extrato manda a string "-R$ ····" e a data "01/04/26". O Python
nao sabe somar "-R$ ····" — ele precisa do numero -287.99.

Este modulo faz essa ponte nas duas direcoes:

    LER     (texto do banco   -> numero/data do Python):  parse_brl, parse_data
    MOSTRAR (numero do Python -> texto bonito na tela ):  fmt_brl, fmt_pct

Toda funcao aqui e "pura": recebe um valor, devolve outro, e nao mexe em
arquivo nem em banco de dados. Isso quer dizer que voce pode testar qualquer
uma delas no terminal, sem abrir o app.

AS ARMADILHAS QUE ESTE ARQUIVO RESOLVE
--------------------------------------
Todas descobertas testando com os SEUS arquivos de verdade:

1. O arquivo de fatura comeca com um caractere invisivel (BOM) grudado no
   cabecalho. Sem tratar, a coluna vira "﻿Data" e o codigo nao a acha.
   (Quem resolve isso e o leitor, abrindo com encoding "utf-8-sig".)
2. "R$ ····" usa ponto de milhar e virgula decimal (padrao BR); o OFX usa
   "-500.00" (padrao internacional). Os dois chegam no mesmo sistema.
3. A fatura usa data "01/04/2026" (ano com 4 digitos) e o extrato usa
   "01/04/26" (ano com 2). O OFX usa "20260821".
4. NaN ("nao e um numero", o vazio do pandas) e VERDADEIRO em Python. Ou seja,
   "valor or 0" devolve NaN, nao 0. Por isso existe a funcao vazio().
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from datetime import date, datetime, timedelta


def vazio(valor) -> bool:
    """Diz se um valor deve ser tratado como "nao preenchido".

    Por que nao usar "if not valor:"? Porque em Python:

        >>> import math
        >>> bool(math.nan)
        True                  # <- NaN e VERDADEIRO!
        >>> math.nan or 0
        nan                   # <- e nao 0, como a gente esperava

    O pandas usa NaN para representar celula vazia. Entao linha["fim"] or 0
    numa data em branco devolve NaN e o calculo seguinte quebra. Esta funcao
    concentra a checagem certa num lugar so.

    Considera vazio: None, NaN, NaT, string em branco e os textos
    "nan" / "nat" / "none" / "-".
    """
    if valor is None:
        return True
    if isinstance(valor, float) and math.isnan(valor):
        return True
    if isinstance(valor, str):
        limpo = valor.strip()
        return limpo == "" or limpo.lower() in {"nan", "nat", "none", "-"}
    if type(valor).__name__ == "NaTType":
        return True
    return False


def ou(valor, padrao):
    """Devolve `valor`, ou `padrao` se `valor` estiver vazio.

    E o substituto seguro do "valor or padrao". Use SEMPRE que ler um campo
    opcional vindo do banco ou de um arquivo:

        dia = ou(linha["dia"], 1)          # em vez de linha["dia"] or 1
    """
    return padrao if vazio(valor) else valor


_SO_NUMERO = re.compile(r"[^\d,.\-]")


def parse_brl(texto) -> float | None:
    """Converte o dinheiro em texto para numero.

    Aceita as tres formas que aparecem nos seus arquivos:

        "R$ ····"  -> 1234.56     (fatura e extrato CSV)
        "-R$ ····"    -> -82.67      (saida no extrato CSV)
        "-500.00"      -> -500.0      (OFX, padrao internacional)

    COMO ELE DECIDE se o ponto e milhar ou decimal:
      - Tem virgula? E formato brasileiro -> o ponto e milhar (joga fora) e a
        virgula vira o ponto decimal.
      - Nao tem virgula mas tem "R$"? Tambem e brasileiro, sem centavos
        ("R$ ····" = mil e quinhentos) -> o ponto e milhar.
      - Nao tem nem virgula nem "R$"? E numero internacional -> o ponto ja e o
        separador decimal, nao mexe.

    Devolve None quando nao da para converter, em vez de quebrar o programa.
    """
    if vazio(texto):
        return None

    if isinstance(texto, (int, float)) and not isinstance(texto, bool):
        return float(texto)

    original = str(texto).strip()
    tem_virgula = "," in original
    tem_simbolo_real = "r$" in original.lower()

    limpo = _SO_NUMERO.sub("", original)
    if limpo in ("", "-", ".", ","):
        return None

    if tem_virgula:
        limpo = limpo.replace(".", "").replace(",", ".")
    elif tem_simbolo_real:
        limpo = limpo.replace(".", "")

    negativo = "-" in limpo
    limpo = limpo.replace("-", "")

    try:
        numero = float(limpo)
    except ValueError:
        return None
    return -numero if negativo else numero


def parse_data(valor) -> date | None:
    """Converte data em texto (ou numero de serie do Excel) para `date`.

    Formatos aceitos, na ordem em que sao testados:

        "2026-08-21"          ISO, o padrao que gravamos no banco
        "21/08/2026"          fatura CSV
        "21/08/26"            extrato CSV (ano com 2 digitos)
        "20260821"            OFX
        "20260821120000[-3]"  OFX com hora e fuso
        46175                 numero de serie do Excel (usado na migracao)

    Ano com 2 digitos: 00-68 vira 2000-2068; 69-99 vira 1969-1999 (regra do
    proprio Python no formato %y).
    """
    if vazio(valor):
        return None

    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor

    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return date(1899, 12, 30) + timedelta(days=int(valor))

    texto = str(valor).strip()
    if not texto:
        return None

    if "[" in texto:
        texto = texto.split("[")[0]

    if texto.isdigit() and len(texto) >= 8:
        texto = texto[:8]
        try:
            return date(int(texto[0:4]), int(texto[4:6]), int(texto[6:8]))
        except ValueError:
            return None

    if texto.isdigit() and len(texto) <= 6:
        return date(1899, 12, 30) + timedelta(days=int(texto))

    texto = texto.split(" ")[0].split("T")[0]

    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


_PARCELA = re.compile(r"(\d+)\s*de\s*(\d+)", re.IGNORECASE)


def parse_parcela(texto) -> tuple[int, int]:
    """Le a coluna "Parcela" da fatura e devolve (parcela_atual, total).

    A fatura escreve de tres jeitos diferentes:

        "3 de 3"   -> (3, 3)    compra parcelada, terceira de tres
        "-"        -> (1, 1)    compra a vista
        " de 1"    -> (1, 1)    a vista, com o texto meio quebrado
                                (aparece nas linhas de pagamento de fatura)

    Sempre devolve numeros, nunca None — assim quem chama calcula direto sem
    precisar checar vazio.
    """
    if vazio(texto):
        return (1, 1)
    achado = _PARCELA.search(str(texto))
    if not achado:
        return (1, 1)
    atual = int(achado.group(1))
    total = int(achado.group(2))
    if atual < 1:
        atual = 1
    if total < atual:
        total = atual
    return (atual, total)


def normalizar_texto(texto) -> str:
    """Deixa o texto "cru" para comparar: MAIUSCULO, sem acento, sem espaco duplo.

    Serve para o motor de regras. A palavra-chave cadastrada e "DROGARIA", mas
    a fatura pode escrever "Drogaria Tamoio" ou "DROGARIA  TAMOIO". Passando as
    duas pontas por aqui, as duas viram "DROGARIA TAMOIO" e a comparacao casa.

    O unicodedata.normalize("NFKD", ...) separa a letra do acento (o "a" com
    acento vira "a" + o acento sozinho); depois jogamos fora tudo que for
    acento (unicodedata.combining).
    """
    if vazio(texto):
        return ""
    bruto = str(texto)
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", bruto)
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def fmt_moeda(valor, simbolo: str = "R$", sinal: bool = False) -> str:
    """Formata numero como dinheiro, com separadores brasileiros.

    O Python formata no padrao americano (f"{1234.5:,.2f}" da "1,234.50").
    O truque abaixo troca os separadores: primeiro poe um marcador temporario
    ("X") no lugar da virgula, depois o ponto vira virgula, e por fim o
    marcador vira ponto.

    A pontuacao continua brasileira mesmo em dolar — "R$ ····" — porque
    quem le e brasileiro e o resto da tela usa essa convencao. Misturar
    "R$ ····" com "R$ ····" na mesma linha faria o olho tropecar.

    sinal=True forca o "+" na frente de valores positivos, util para mostrar
    variacao ("+R$ ····" fica mais claro que "R$ ····").
    """
    if vazio(valor):
        return "—"
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "—"

    corpo = f"{abs(numero):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    negativo = numero < 0 and float(corpo.replace(".", "").replace(",", ".")) != 0

    if negativo:
        return f"-{simbolo} {corpo}"
    if sinal:
        return f"+{simbolo} {corpo}"
    return f"{simbolo} {corpo}"


def fmt_brl(valor, sinal: bool = False) -> str:
    """Formata numero como dinheiro brasileiro: 1234.5 -> "R$ ····".

    O SINAL SAI DO CORPO JA ARREDONDADO, e nao do numero cru: `-0,001` e
    negativo, mas arredondado para centavos vira zero, e a funcao escrevia
    "-R$ ····" — que parece defeito de programa. Zero nao tem sinal.
    """
    return fmt_moeda(valor, "R$", sinal)


def fmt_usd(valor, sinal: bool = False) -> str:
    """Formata numero como dolar: 7410.55 -> "R$ ····".

    Existe porque a carteira tem uma metade internacional e porque a pergunta
    "quanto isso vale em dolar" e legitima — mas o app inteiro guarda valor em
    REAIS (ver `investimentos.salvar_saldo`). Entao esta funcao formata um
    numero que alguem ja converteu; ela nao converte nada.
    """
    return fmt_moeda(valor, "US$", sinal)


def fmt_brl_md(valor, sinal: bool = False) -> str:
    """Igual a fmt_brl, mas seguro para usar em texto markdown do Streamlit.

    POR QUE ISSO PRECISA EXISTIR: o Streamlit interpreta cifrao-texto-cifrao
    como formula matematica (LaTeX). Se voce escrever

        st.caption(f"Gastou {fmt_brl(a)} de {fmt_brl(b)}")

    a string tem DOIS cifroes, o Streamlit acha que e uma formula e engole o
    trecho do meio: "Gastou R R$ ···· de R R$ ····" — os valores somem.
    Escapando com barra invertida ele mostra o cifrao literal.

    ONDE USAR CADA UMA (tabela verificada na tela, nao e teoria):

        contexto                                use
        ------------------------------------    ---------------------------
        st.caption / st.markdown / st.info      fmt_brl_md  (com escape)
        st.markdown(unsafe_allow_html=True)     fmt_brl     (sem escape!)
        st.metric                               fmt_brl
        tabela / dataframe / grafico            fmt_brl

    O caso do HTML e o contraintuitivo: dentro de uma tag de bloco, o markdown
    nao processa o conteudo, entao a formula LaTeX nao e detectada — mas a
    contrabarra tambem nao e consumida, e apareceria "R\\$ R$ ····" na tela.
    """
    return fmt_brl(valor, sinal).replace("R$", "R\\$")


def fmt_pct(valor, casas: int = 1) -> str:
    """Formata fracao como porcentagem: 0.4567 -> "45,7%".

    Repare que a entrada e FRACAO (0.45), nao numero de porcento (45). E a
    convencao usada em todo o projeto, para nao restar duvida.

    PRECISA DO MESMO TRUQUE DO MARCADOR que fmt_brl e fmt_num usam, e por um
    bom tempo nao teve. A versao antiga fazia so `.replace(".", ",")`:

        f"{-1829.9:,.1f}"           ->  "-1,829.9"   (padrao americano)
        .replace(".", ",")          ->  "-1,829,9"   <- duas virgulas!

    Ficou invisivel por meses porque porcentagem quase nunca passa de 1000% —
    ate agosto/2026, quando a reclassificacao de R$ ···· que nao eram receita
    deixou o mes com receita de R$ ···· contra R$ ···· de despesa. A
    taxa de poupanca deu -1829,9% e o painel mostrou "-1,829,9%".

    A licao: uma funcao de formatacao so e testada de verdade nos extremos.
    As tres irmas daqui (fmt_brl, fmt_num, fmt_pct) agora fazem a MESMA coisa.
    """
    if vazio(valor):
        return "—"
    try:
        numero = float(valor) * 100
    except (TypeError, ValueError):
        return "—"
    corpo = f"{numero:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return corpo + "%"


def fmt_num(valor, casas: int = 0) -> str:
    """Formata numero comum no padrao BR: 1234.5 -> "1.234,5"."""
    if vazio(valor):
        return "—"
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "—"
    return f"{numero:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def mes_de(data_valor) -> str | None:
    """Extrai o mes de uma data: date(2026, 8, 21) -> "2026-08"."""
    d = parse_data(data_valor)
    if d is None:
        return None
    return f"{d.year:04d}-{d.month:02d}"


def mes_para_indice(mes: str) -> int | None:
    """Converte "2026-08" para o numero 24320 (= 2026*12 + 8)."""
    if vazio(mes):
        return None
    texto = str(mes).strip()
    if len(texto) < 7 or texto[4] != "-":
        return None
    try:
        ano, numero_mes = int(texto[:4]), int(texto[5:7])
    except ValueError:
        return None
    if not 1 <= numero_mes <= 12:
        return None
    return ano * 12 + numero_mes


def indice_para_mes(indice: int) -> str:
    """Faz o caminho de volta: 24320 -> "2026-08".

    O -1 e o +1 existem por causa de dezembro: 2026*12+12 = 24324 dividido por
    12 da exatamente 2027 com resto 0, o que jogaria dezembro para o ano
    seguinte. Subtraindo 1 antes da divisao e somando 1 depois, dezembro cai
    no lugar certo.
    """
    indice = int(indice)
    ano = (indice - 1) // 12
    mes = indice - ano * 12
    return f"{ano:04d}-{mes:02d}"


def somar_meses(mes: str, quantidade: int) -> str | None:
    """Anda `quantidade` meses a partir de `mes`. Aceita negativo para voltar.

        somar_meses("2026-11", 2)   -> "2027-01"
        somar_meses("2026-01", -1)  -> "2025-12"
    """
    indice = mes_para_indice(mes)
    if indice is None:
        return None
    return indice_para_mes(indice + int(quantidade))


def intervalo_meses(inicio: str, fim: str) -> list[str]:
    """Lista todos os meses entre dois, inclusive:

        intervalo_meses("2026-01", "2026-03") -> ["2026-01", "2026-02", "2026-03"]
    """
    a, b = mes_para_indice(inicio), mes_para_indice(fim)
    if a is None or b is None or b < a:
        return []
    return [indice_para_mes(i) for i in range(a, b + 1)]


def rotulo_mes(mes: str) -> str:
    """Deixa o mes legivel para humano: "2026-08" -> "ago/2026"."""
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]
    indice = mes_para_indice(mes)
    if indice is None:
        return "—" if vazio(mes) else str(mes)
    ano = (indice - 1) // 12
    numero_mes = indice - ano * 12
    return f"{nomes[numero_mes - 1]}/{ano}"


def chave_hash(*partes) -> str:
    """Gera uma "impressao digital" curta a partir de varios pedacos de texto.

    Serve para descobrir se um lancamento ja esta no banco. Juntamos data +
    descricao + valor, passamos pelo SHA-1, e ficamos com os 16 primeiros
    caracteres do resultado. Se dois lancamentos geram a mesma impressao, sao
    a mesma coisa.

    Por que hash e nao a string inteira? Porque a string ficaria enorme e cheia
    de caractere estranho; o hash tem sempre 16 caracteres e vira indice rapido
    no banco de dados.
    """
    texto = "|".join("" if vazio(p) else str(p).strip() for p in partes)
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def hash_arquivo(caminho) -> str:
    """Impressao digital do CONTEUDO de um arquivo inteiro (SHA-256).

    Usada para avisar "voce ja importou este arquivo". Le em blocos de 64 KB
    para nao carregar um arquivo gigante inteiro na memoria de uma vez.
    """
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()
