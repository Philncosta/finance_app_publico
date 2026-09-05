"""
backup.py — Copia de seguranca em .zip de CSVs, pronta para a nuvem.
==============================================================================

POR QUE NAO SIMPLESMENTE COPIAR O ARQUIVO .db PARA O ONEDRIVE
--------------------------------------------------------------
Porque banco de dados aberto e arquivo de sincronizacao nao combinam. Enquanto
o app roda, o SQLite mantem arquivos auxiliares (-wal e -shm) com escritas que
ainda nao entraram no .db principal. Se o OneDrive sincronizar o .db "no meio
do caminho", a copia na nuvem pode ficar inconsistente — e voce so descobre no
dia em que precisar dela.

A ESTRATEGIA DAQUI
------------------
    o banco .db     fica LOCAL, na pasta do projeto (rapido e seguro)
    o backup .zip   vai para a NUVEM (OneDrive), com um CSV por tabela

O .zip tem tres vantagens sobre copiar o .db:

    1. E um arquivo FECHADO. Depois de gravado nao muda mais, entao o
       OneDrive nunca o pega no meio de uma escrita.
    2. E LEGIVEL. Se um dia este programa nao existir mais, os seus dados
       continuam abriveis no Excel — sao CSVs comuns dentro de um zip.
    3. E VERSIONADO. Cada backup tem data e hora no nome, entao voce pode
       voltar para o estado de tres semanas atras, e nao so para o ultimo.

QUANDO O BACKUP ACONTECE
------------------------
    - automaticamente, ao final de toda importacao;
    - quando voce clica em "Fazer backup agora" em Configuracoes.
"""

from __future__ import annotations

import csv
import io
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from financas import banco, config

TABELAS_BACKUP = [
    "grandes_categorias", "categorias", "contas", "parametros",
    "macros_ativo", "classes_ativo", "metas_alocacao",
    "regras_fatura", "regras_extrato", "gastos_fixos", "orcamento",
    "metas", "futuras_compras", "patrimonio_mensal",
    "financiamento_cenarios", "arquivos_importados",
    "investimentos", "investimentos_saldos", "investimentos_movimentos",
    "cotacoes", "indices",
    "lancamentos",
]


def tabelas_em_ordem() -> list[str]:
    """As tabelas a copiar: as conhecidas na ordem certa, mais as que surgirem.

    POR QUE NAO USAR `TABELAS_BACKUP` DIRETO
    ----------------------------------------
    Porque uma lista escrita a mao envelhece em silencio. Ela ja envelheceu
    uma vez: oito tabelas de investimento ficaram oito meses fora do backup
    sem ninguem perceber, porque nada nunca falha por causa de uma tabela que
    voce nao pediu.

    Aqui a lista decide a ORDEM (que importa, por causa das chaves
    estrangeiras) e o BANCO decide o CONJUNTO (que e o que nao pode faltar).
    Tabela nova entra no fim, que e o lugar seguro: quem chega depois costuma
    depender de quem ja estava.

    Se o banco nao puder ser lido, devolve a lista fixa — um backup parcial e
    melhor que nenhum.
    """
    try:
        existentes = [
            linha["name"] for linha in banco.consultar(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")
        ]
    except Exception:
        return list(TABELAS_BACKUP)

    conhecidas = [t for t in TABELAS_BACKUP if t in existentes]
    novas = [t for t in existentes if t not in TABELAS_BACKUP]
    return conhecidas + novas

LEIA_ME = """BACKUP DO PAINEL FINANCEIRO
===========================

Gerado em: {quando}
Origem:    {origem}

O QUE TEM AQUI DENTRO
---------------------
Um arquivo .csv para cada tabela do banco de dados. Todos usam:

    separador   ponto e virgula (;)
    codificacao UTF-8
    numeros     com PONTO decimal (1234.56), formato internacional
    datas       AAAA-MM-DD

{tabelas}

COMO RESTAURAR
--------------
Pelo app: Configuracoes -> Restaurar backup -> escolha este arquivo .zip.
O app faz uma copia do banco atual antes de sobrescrever qualquer coisa.

SEM O APP
---------
Os CSVs abrem direto no Excel (Dados -> De Texto/CSV, separador ";",
codificacao UTF-8). Seus dados nao dependem deste programa para existir.

O ARQUIVO MAIS IMPORTANTE E O lancamentos.csv — e o historico completo.
"""


def _tabela_para_csv(tabela: str) -> str:
    """Le uma tabela inteira e devolve o conteudo em CSV (como texto).

    Usa io.StringIO, que e um "arquivo de mentira" que mora na memoria. Assim
    escrevemos o CSV sem criar arquivo temporario em disco — o texto vai
    direto para dentro do zip.
    """
    linhas = banco.consultar(f"SELECT * FROM {tabela}")
    buffer = io.StringIO()

    if not linhas:
        colunas = [
            info["name"] for info in banco.consultar(f"PRAGMA table_info({tabela})")
        ]
        csv.writer(buffer, delimiter=";").writerow(colunas)
        return buffer.getvalue()

    escritor = csv.DictWriter(buffer, fieldnames=linhas[0].keys(), delimiter=";")
    escritor.writeheader()
    for linha in linhas:
        escritor.writerow(dict(linha))
    return buffer.getvalue()


def criar(pasta_destino=None, sufixo: str = "") -> dict:
    """Gera o .zip de backup e devolve um resumo do que foi gravado.

    Devolve {caminho_local, caminho_nuvem, tabelas, linhas, tamanho_kb, quando}.
    `caminho_nuvem` vem None quando a pasta da nuvem nao existe ou nao foi
    configurada — o backup local acontece de qualquer jeito.
    """
    config.garantir_pastas()
    quando = datetime.now()
    carimbo = quando.strftime("%Y-%m-%d_%H%M")
    nome = f"financas_{carimbo}{('_' + sufixo) if sufixo else ''}.zip"
    destino_local = config.PASTA_BACKUPS / nome

    contagens = {}
    with zipfile.ZipFile(destino_local, "w", zipfile.ZIP_DEFLATED) as zip_arquivo:
        for tabela in tabelas_em_ordem():
            try:
                conteudo = _tabela_para_csv(tabela)
            except Exception:
                continue
            zip_arquivo.writestr(f"{tabela}.csv", conteudo)
            contagens[tabela] = banco.contar(tabela)

        resumo_tabelas = "\n".join(
            f"    {tabela:24} {quantidade:>6} linhas"
            for tabela, quantidade in contagens.items()
        )
        zip_arquivo.writestr("LEIA-ME.txt", LEIA_ME.format(
            quando=quando.strftime("%d/%m/%Y às %H:%M"),
            origem=str(config.CAMINHO_BANCO),
            tabelas=resumo_tabelas,
        ))

    caminho_nuvem = None
    pasta_nuvem = Path(pasta_destino or banco.obter_parametro(
        "pasta_backup", str(config.PASTA_BACKUP_NUVEM_PADRAO)))
    try:
        pasta_nuvem.mkdir(parents=True, exist_ok=True)
        destino_nuvem = pasta_nuvem / nome
        shutil.copy2(destino_local, destino_nuvem)
        caminho_nuvem = str(destino_nuvem)
    except OSError:
        caminho_nuvem = None

    limpar_antigos()
    if caminho_nuvem:
        limpar_antigos(pasta_nuvem)

    return {
        "caminho_local": str(destino_local),
        "caminho_nuvem": caminho_nuvem,
        "tabelas": len(contagens),
        "linhas": sum(contagens.values()),
        "tamanho_kb": destino_local.stat().st_size / 1024,
        "quando": quando.strftime("%d/%m/%Y %H:%M"),
    }


def limpar_antigos(pasta=None, manter: int | None = None) -> int:
    """Apaga os backups mais antigos, mantendo os N mais recentes.

    Sem isso, um backup por importacao vira centenas de arquivos em alguns
    meses. Devolve quantos foram apagados.
    """
    pasta = Path(pasta or config.PASTA_BACKUPS)
    manter = manter or config.MAX_BACKUPS
    if not pasta.is_dir():
        return 0

    arquivos = sorted(
        pasta.glob("financas_*.zip"),
        key=lambda caminho: caminho.stat().st_mtime,
        reverse=True,
    )
    apagados = 0
    for caminho in arquivos[manter:]:
        try:
            caminho.unlink()
            apagados += 1
        except OSError:
            pass
    return apagados


def listar(pasta=None) -> list[dict]:
    """Lista os backups disponiveis, do mais novo para o mais antigo."""
    pastas = [Path(pasta)] if pasta else [
        config.PASTA_BACKUPS,
        Path(banco.obter_parametro("pasta_backup",
                                   str(config.PASTA_BACKUP_NUVEM_PADRAO))),
    ]

    encontrados = {}
    for diretorio in pastas:
        if not diretorio.is_dir():
            continue
        for caminho in diretorio.glob("financas_*.zip"):
            info = caminho.stat()
            encontrados[caminho.name] = {
                "nome": caminho.name,
                "caminho": str(caminho),
                "quando": datetime.fromtimestamp(info.st_mtime),
                "tamanho_kb": info.st_size / 1024,
                "local": str(diretorio),
            }

    return sorted(encontrados.values(), key=lambda b: b["quando"], reverse=True)


def restaurar(caminho_zip, apagar_antes: bool = True) -> dict:
    """Restaura o banco a partir de um .zip de backup.

    SEGURANCA: antes de mexer em qualquer coisa, copia o banco atual para
    dados/backups/antes_de_AAAAMMDD_HHMMSS.db. Se a restauracao trouxer um
    resultado inesperado, o estado anterior esta guardado.

    `apagar_antes=True` substitui o conteudo (o normal ao restaurar).
    `apagar_antes=False` acrescenta ao que ja existe, ignorando duplicatas —
    util para juntar dados de duas maquinas.
    """
    caminho_zip = Path(caminho_zip)
    if not caminho_zip.exists():
        raise FileNotFoundError(f"Backup nao encontrado: {caminho_zip}")

    copia = banco.copia_de_seguranca_rapida()
    banco.inicializar()

    ordem = tabelas_em_ordem()
    restauradas = {}
    with zipfile.ZipFile(caminho_zip) as zip_arquivo:
        nomes = set(zip_arquivo.namelist())

        if apagar_antes:
            for tabela in reversed(ordem):
                if f"{tabela}.csv" in nomes:
                    banco.executar(f"DELETE FROM {tabela}")

        for tabela in ordem:
            arquivo = f"{tabela}.csv"
            if arquivo not in nomes:
                continue

            texto = zip_arquivo.read(arquivo).decode("utf-8-sig")
            linhas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
            if not linhas:
                restauradas[tabela] = 0
                continue

            colunas = list(linhas[0].keys())
            marcadores = ",".join("?" * len(colunas))
            valores = [
                tuple(linha[coluna] if linha[coluna] != "" else None
                      for coluna in colunas)
                for linha in linhas
            ]
            banco.executar_muitos(
                f"INSERT OR IGNORE INTO {tabela} ({','.join(colunas)}) "
                f"VALUES ({marcadores})",
                valores,
            )
            restauradas[tabela] = banco.contar(tabela)

    return {
        "copia_de_seguranca": copia,
        "tabelas": restauradas,
        "total": sum(restauradas.values()),
    }


def conteudo(caminho_zip) -> dict:
    """Espia o que tem dentro de um backup, sem restaurar.

    Serve para a tela mostrar "este backup tem 1.050 lancamentos de
    21/08/2026" antes de voce confirmar a restauracao.
    """
    caminho_zip = Path(caminho_zip)
    if not caminho_zip.exists():
        return {}

    resumo = {}
    with zipfile.ZipFile(caminho_zip) as zip_arquivo:
        for nome in zip_arquivo.namelist():
            if not nome.endswith(".csv"):
                continue
            texto = zip_arquivo.read(nome).decode("utf-8-sig")
            linhas = max(0, len(texto.strip().splitlines()) - 1)
            resumo[nome[:-4]] = linhas
    return resumo
