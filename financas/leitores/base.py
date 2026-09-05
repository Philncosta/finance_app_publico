"""
base.py — O que todo leitor de arquivo tem em comum.
==============================================================================

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Sao tres formatos de arquivo diferentes (fatura CSV, extrato CSV, extrato OFX),
mas o resto do sistema nao pode se importar com isso. Se cada leitor devolvesse
um formato proprio, o importador precisaria de tres caminhos diferentes, e cada
grafico precisaria saber de onde o dado veio.

Entao combinamos um CONTRATO: nao importa o arquivo, todo leitor devolve um
`ResultadoLeitura` com uma lista de linhas no MESMO formato. Depois desse
ponto, o sistema inteiro trata fatura e extrato do mesmo jeito.

Esse padrao tem nome: "normalizacao". E uma das ideias mais uteis de
programacao — voce paga o preco de converter uma vez, na entrada, e o resto do
programa fica simples.

O FORMATO NORMALIZADO DE UMA LINHA
----------------------------------
    data             'AAAA-MM-DD'   quando a transacao aconteceu
    hora             'HH:MM:SS'     so o extrato CSV tem; senao None
    mes_competencia  'AAAA-MM'      em que mes isso conta (ver abaixo)
    descricao        texto          estabelecimento ou historico do banco
    portador         texto/None     so a fatura tem (quem usou o cartao)
    valor            numero         COM SINAL, do seu ponto de vista
    parcela_atual    inteiro        1 quando nao e parcelado
    parcela_total    inteiro        1 quando nao e parcelado
    parcela_texto    texto/None     o original ("3 de 3"), para conferencia
    saldo_apos       numero/None    saldo da conta depois (so extrato)
    fitid            texto/None     id unico do banco (so OFX)
    origem           'Fatura' ou 'Extrato'
    linha_arquivo    inteiro        em que linha do arquivo isso estava

SOBRE O "MES DE COMPETENCIA"
----------------------------
E a diferenca mais importante entre os dois tipos de arquivo:

- No EXTRATO, o mes e simplesmente o mes da data. Gastou dia 3 de agosto,
  conta em agosto.

- Na FATURA, o mes sai do NOME DO ARQUIVO **e recua um mes**.
  "Fatura2026-01-05.csv" e a fatura que VENCE em 05/01/2026, e ela contem o
  que foi gasto de ~26/11 a ~25/12. Todas as linhas contam em **2025-12** — o
  mes do GASTO, nao o do vencimento. Uma parcela "3 de 10" comprada em outubro
  tambem cai nessa fatura, e conta no mesmo 2025-12.

  O recuo existe porque o cartao fecha por volta do dia 25, a mesma semana em
  que o salario cai: gasto e receita do mesmo ciclo precisam contar no mesmo
  mes, ou o saldo do mes vira ficcao. Quem aplica a regra e
  `fatura_csv.competencia_da_fatura()`.

ATENCAO SE VOCE LEU ESTE ARQUIVO ANTES DE 25/08/2026: ate a migracao 13 a
fatura contava no mes do VENCIMENTO, e este mesmo paragrafo dizia o contrario
do que diz agora. A regra mudou; o texto acompanhou.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResultadoLeitura:
    """O que um leitor devolve depois de ler um arquivo.

    `@dataclass` e um atalho do Python: ele escreve sozinho o __init__, o
    __repr__ e a comparacao da classe a partir dos campos declarados. Sem ele,
    voce escreveria 20 linhas de codigo repetitivo para guardar 4 valores.

    Campos:
        linhas  — as transacoes ja normalizadas (o formato descrito no topo)
        avisos  — problemas que NAO impediram a leitura (linha estranha,
                  data ilegivel). Aparecem na tela para voce decidir.
        erros   — problemas que impediram a leitura. Se tiver erro, `linhas`
                  provavelmente esta vazia.
        meta    — informacao sobre o arquivo (banco, conta, periodo, saldo).
                  Serve para mostrar "voce esta importando o extrato de
                  22/07 a 21/08 do Banco XP" antes de confirmar.
    """

    linhas: list[dict] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


    @property
    def ok(self) -> bool:
        """True quando deu para ler alguma coisa e nao houve erro fatal."""
        return not self.erros and len(self.linhas) > 0

    @property
    def total(self) -> float:
        """Soma dos valores lidos. Util para conferir com o total do arquivo."""
        return sum(linha["valor"] for linha in self.linhas)

    def resumo(self) -> str:
        """Uma frase curta para mostrar na tela depois de ler o arquivo."""
        if self.erros:
            return f"Nao deu para ler: {self.erros[0]}"
        partes = [f"{len(self.linhas)} transações"]
        if self.meta.get("periodo"):
            partes.append(self.meta["periodo"])
        if self.avisos:
            partes.append(f"{len(self.avisos)} aviso(s)")
        return " · ".join(partes)


def linha_normalizada(
    *,
    data: str,
    mes_competencia: str,
    descricao: str,
    valor: float,
    origem: str,
    linha_arquivo: int,
    hora: str | None = None,
    portador: str | None = None,
    parcela_atual: int = 1,
    parcela_total: int = 1,
    parcela_texto: str | None = None,
    saldo_apos: float | None = None,
    fitid: str | None = None,
) -> dict:
    """Monta uma linha no formato normalizado.

    O `*` sozinho no comeco dos parametros obriga quem chama a usar o NOME de
    cada argumento (`descricao="UBER"` em vez de so `"UBER"`). Com 13 campos,
    isso evita o erro classico de trocar dois de lugar sem perceber.
    """
    return {
        "data": data,
        "hora": hora,
        "mes_competencia": mes_competencia,
        "descricao": descricao,
        "portador": portador,
        "valor": valor,
        "parcela_atual": parcela_atual,
        "parcela_total": parcela_total,
        "parcela_texto": parcela_texto,
        "saldo_apos": saldo_apos,
        "fitid": fitid,
        "origem": origem,
        "linha_arquivo": linha_arquivo,
    }
