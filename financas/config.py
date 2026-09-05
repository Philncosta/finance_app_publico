"""
config.py — Onde ficam as coisas e como elas se chamam.
==============================================================================

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Todo projeto tem "constantes": caminhos de pasta, listas de opcoes validas,
cores. Se cada arquivo do projeto escrever o seu proprio caminho, o dia em que
voce mudar a pasta vai ter que caçar em 20 lugares. Aqui tudo isso fica em UM
lugar so. Os outros modulos fazem `from financas import config` e usam
`config.CAMINHO_BANCO`, por exemplo.

COMO LER ESTE ARQUIVO
---------------------
Ele nao "faz" nada — nao tem funcao que calcula. Ele so DECLARA valores.
Quando o Python importa este arquivo, ele executa de cima para baixo e deixa
essas variaveis prontas na memoria.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PASTA_DADOS = RAIZ / "dados"
PASTA_BACKUPS = PASTA_DADOS / "backups"
PASTA_SEMENTE = RAIZ / "migracao" / "semente"
PASTA_ARQUIVOS_ORIGINAIS = RAIZ / "arquivos_originais"

CAMINHO_BANCO = PASTA_DADOS / "financas.db"

CAMINHO_XLSM = PASTA_ARQUIVOS_ORIGINAIS / "Dasbhardo excel.xlsm"

PASTA_BACKUP_NUVEM_PADRAO = Path.home() / "OneDrive" / "Financas_Backup"

MAX_BACKUPS = 30

MAX_COPIAS_RAPIDAS = 5


def garantir_pastas() -> None:
    """Cria as pastas de dados se ainda nao existirem.

    `mkdir(parents=True, exist_ok=True)` significa:
      - parents=True  -> cria tambem as pastas-mae que faltarem
      - exist_ok=True -> se ja existir, nao reclama (nao levanta erro)
    """
    for pasta in (PASTA_DADOS, PASTA_BACKUPS, PASTA_ARQUIVOS_ORIGINAIS):
        pasta.mkdir(parents=True, exist_ok=True)


NATUREZA_DESPESA = "Despesa"
NATUREZA_RECEITA = "Receita"
NATUREZA_RECEITA_EXTRA = "Receita Extraordinária"
NATUREZA_PAGAMENTO = "Pagamento"
NATUREZA_INVESTIMENTO = "Investimento"

NATUREZA_TRANSFERENCIA = "Transferência"

CATEGORIA_TERCEIROS_PADRAO = "Investimentos de terceiros"


def categoria_terceiros() -> str:
    """A categoria que marca dinheiro que esta na conta mas NAO e seu.

    POR QUE ISTO E FUNCAO E NAO CONSTANTE. O valor certo aqui e o nome de uma
    pessoa — quem confiou o dinheiro a voce. Nome de pessoa em constante de
    codigo vaza para todo mundo que ler o repositorio, e nao e algo que quem
    clonar o projeto vai querer herdar: o terceiro dele e outro.

    Entao o nome mora no BANCO, em `parametros`, editavel em Configuracoes. O
    codigo so sabe que existe uma categoria com esse papel.

    O que ela faz esta em `docs/14`: dinheiro de terceiro fica fora de receita,
    fora de despesa E fora do patrimonio. Ele passa pela conta sem ser seu.
    """
    from financas import banco

    return banco.obter_parametro("categoria_terceiros",
                                 CATEGORIA_TERCEIROS_PADRAO)

CATEGORIA_PLR = "PLR"

NATUREZAS = [
    NATUREZA_DESPESA,
    NATUREZA_RECEITA,
    NATUREZA_RECEITA_EXTRA,
    NATUREZA_PAGAMENTO,
    NATUREZA_INVESTIMENTO,
    NATUREZA_TRANSFERENCIA,
]

NATUREZAS_DESPESA = [NATUREZA_DESPESA]

NATUREZAS_RECEITA = [NATUREZA_RECEITA, NATUREZA_RECEITA_EXTRA]

TIPO_FIXO = "Fixo"
TIPO_VARIAVEL = "Variável"
TIPOS = [TIPO_FIXO, TIPO_VARIAVEL]

ORIGEM_FATURA = "Fatura"
ORIGEM_EXTRATO = "Extrato"
ORIGEM_MANUAL = "Manual"
ORIGEM_RATEIO = "Rateio"
ORIGENS = [ORIGEM_FATURA, ORIGEM_EXTRATO, ORIGEM_MANUAL, ORIGEM_RATEIO]

FORMA_CARTAO = "Cartão"
FORMA_CONTA = "Conta"
FORMAS_PAGAMENTO = [FORMA_CARTAO, FORMA_CONTA]

BASE_CADASTRADO = "Cadastrado"
BASE_MEDIA = "Média 6m"
BASES_VALOR = [BASE_CADASTRADO, BASE_MEDIA]

SITUACAO_DESLIGADO = "desligado"
SITUACAO_FORA = "fora"
SITUACAO_PARCELA = "parcela"
SITUACAO_LANCADO = "lançado"
SITUACAO_PREVISTO = "previsto"

SINAL_ENTRADA = "Entrada"
SINAL_SAIDA = "Saída"
SINAL_AMBOS = "Ambos"
SINAIS = [SINAL_ENTRADA, SINAL_SAIDA, SINAL_AMBOS]

CORES_TEMA = {
    "primaria": "#4F46E5",
    "secundaria": "#0EA5E9",
    "sucesso": "#10B981",
    "alerta": "#F59E0B",
    "alerta_clara": "#FCD34D",
    "perigo": "#EF4444",
    "neutra": "#64748B",
    "fundo": "#F1F5F9",
    "cartao": "#FFFFFF",
    "texto": "#0F172A",
    "texto_fraco": "#64748B",
    "borda": "#EDF1F6",
    # A barra lateral tem paleta propria porque tem FUNDO proprio: escura, para
    # separar navegacao de conteudo sem desenhar borda. Os tons vivem aqui
    # junto dos outros para o CSS e o `[theme.sidebar]` do config.toml lerem a
    # mesma fonte — dois lugares guardando o mesmo indigo divergiriam no dia em
    # que um deles mudasse.
    "sidebar_fundo": "#1E1B4B",
    "sidebar_texto": "#C7D2FE",
    "sidebar_texto_fraco": "#818CF8",
    "sidebar_ativo": "#4F46E5",
}

PALETA = [
    "#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444",
    "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1",
    "#84CC16", "#06B6D4", "#A855F7", "#F43F5E", "#22C55E",
]

NOME_APP = "Painel Financeiro"
