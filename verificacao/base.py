"""
base.py — o placar e o banco descartavel, um so, para todas as conferencias.
==============================================================================

POR QUE ISTO PRECISOU EXISTIR (2026-09-04)
------------------------------------------
Cada script de conferencia trazia a sua propria copia destas duas pecas. Uma
varredura por AST encontrou:

    Conferencia         13 copias, em 5 versoes diferentes
    Placar               2 copias  (o MESMO trabalho, com outro nome)
    banco_descartavel   10 copias

Nao era estilo: as copias tinham DIVERGIDO. Tres imprimiam todas as falhas e
uma cortava em 20; uma renomeara os atributos por conta propria; e o
`banco_descartavel` — a peca que impede um teste de escrever no banco DE
VERDADE — existia em dez implementacoes. Dez implementacoes de uma protecao
sao dez chances de uma estar errada, e a errada so aparece no dia em que
apagar dado que nao volta.

Agora e uma peca so, e cada divergencia foi resolvida ficando com a MELHOR
versao, nao com a mais comum:

    do `conferir_rebalanceamento`  o corte em 20 falhas que ainda diz quantas
                                   sobraram — com 2.159 checagens, e a unica
                                   que nao alaga o terminal
    do `Placar`                    `exigir_igual`, que mostra obtido x esperado
                                   em vez de so dizer que falhou
    do `conferir_compras`          `banco_vazio`, que e outra coisa e continua
                                   sendo outra coisa (ver abaixo)

DUAS FORMAS DE NAO ENSILVAR NO BANCO DELE, E ELAS NAO SE MISTURAM
-----------------------------------------------------------------
    banco_descartavel()  trabalha numa COPIA do banco real — para conferir o
                         que os dados dele de fato dizem
    banco_vazio()        comeca do ZERO e roda as migracoes — para montar um
                         caso de teste sem heranca nenhuma

Achatar as duas numa funcao so esconderia a diferenca que importa: quem usa a
segunda espera um banco sem historico, e receber uma copia do banco real faria
o teste passar por motivo errado.

POR QUE UM TESTE NUNCA PODE ESCREVER NO BANCO REAL
--------------------------------------------------
Esta explicacao vem do `conferir_rebalanceamento`, e e a melhor razao escrita
no projeto para esta pasta existir. Aquela secao precisa de metas cadastradas
para testar, e a versao antiga gravava as metas NO BANCO DELE, desfazendo num
`finally`:

    DELETE FROM metas_alocacao        <- apaga as metas dele
    ...testa...
    DELETE + reinsere as originais    <- devolve

Funcionava, e era uma bomba-relogio. Enquanto `metas_alocacao` esteve vazia,
nao havia o que perder. No dia em que ele cadastrasse as metas de verdade, um
Ctrl+C no meio, uma queda de energia ou um erro nao previsto entre o DELETE e a
restauracao apagaria o trabalho dele — e o culpado seria justamente o script
que existe para provar que esta tudo certo.

**Um teste nunca deve poder destruir o dado que ele verifica.**

Como `banco.conectar()` le `config.CAMINHO_BANCO` na HORA da chamada (e nao no
import), trocar a variavel redireciona o app inteiro para a copia. O arquivo
original nao chega a ser aberto para escrita.
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from financas import banco, config

# Quantas falhas cabem no relatorio antes de virar parede de texto.
LIMITE_DE_FALHAS = 20


class Conferencia:
    """Conta as checagens e guarda as que falharam."""

    def __init__(self) -> None:
        self.falhas: list[str] = []
        self.checagens = 0

    def exigir(self, condicao: bool, mensagem: str) -> None:
        """Registra uma condicao que precisa ser verdadeira."""
        self.checagens += 1
        if not condicao:
            self.falhas.append(mensagem)

    def exigir_igual(self, obtido, esperado, descricao: str,
                     tolerancia: float = 0.0) -> None:
        """O mesmo, mostrando os DOIS valores quando nao bate.

        Veio do `Placar` de `conferir_previdencia`. "X != Y" manda voce ir
        atras dos numeros; "obtido R$ ···· / esperado R$ ····" ja diz de
        quanto foi o erro, que quase sempre e a pista.

        `tolerancia` existe porque dinheiro em float nao fecha no bit: duas
        contas certas podem diferir num centavo de arredondamento.
        """
        self.checagens += 1
        if isinstance(obtido, (int, float)) and isinstance(esperado, (int, float)):
            bateu = abs(float(obtido) - float(esperado)) <= tolerancia
        else:
            bateu = obtido == esperado
        if not bateu:
            self.falhas.append(f"{descricao}\n        obtido:   {obtido!r}"
                               f"\n        esperado: {esperado!r}")

    def relatorio(self) -> int:
        """Imprime o resultado. Devolve 0 se passou, 1 se algo falhou."""
        print()
        print("=" * 78)
        if self.falhas:
            print(f"FALHOU — {len(self.falhas)} problema(s) em "
                  f"{self.checagens} checagens")
            print("=" * 78)
            for falha in self.falhas[:LIMITE_DE_FALHAS]:
                print(f"  x {falha}")
            if len(self.falhas) > LIMITE_DE_FALHAS:
                print(f"  ... e mais {len(self.falhas) - LIMITE_DE_FALHAS}")
            return 1
        print(f"TUDO CERTO — {self.checagens} checagens, nenhuma falha")
        print("=" * 78)
        return 0


def _apagar(copia: Path) -> None:
    """Apaga o arquivo e os companheiros que o SQLite deixa (-wal, -shm)."""
    for sufixo in ("", "-wal", "-shm"):
        alvo = Path(str(copia) + sufixo)
        if alvo.exists():
            alvo.unlink()


@contextmanager
def banco_descartavel(nome: str):
    """Trabalha numa COPIA do banco real. `nome` batiza o arquivo temporario.

    Ver a explicacao no topo do modulo: e isto que separa uma conferencia de
    um acidente.
    """
    original = config.CAMINHO_BANCO
    copia = Path(tempfile.gettempdir()) / f"{nome}_temp.db"
    _apagar(copia)
    shutil.copy2(original, copia)
    config.CAMINHO_BANCO = copia
    try:
        yield
    finally:
        config.CAMINHO_BANCO = original
        _apagar(copia)


@contextmanager
def banco_vazio(nome: str):
    """Comeca do ZERO, so com as migracoes aplicadas.

    Para quem monta o proprio caso de teste e precisa que nao haja heranca
    nenhuma. `conferir_compras` depende disto: as contagens dele mudam se
    receber uma copia do banco real por engano.
    """
    original = config.CAMINHO_BANCO
    copia = Path(tempfile.gettempdir()) / f"{nome}_temp.db"
    _apagar(copia)
    config.CAMINHO_BANCO = copia
    try:
        banco.aplicar_migracoes()
        yield
    finally:
        config.CAMINHO_BANCO = original
        _apagar(copia)
