"""
banco.py — O banco de dados SQLite: onde tudo fica guardado.
==============================================================================

O QUE E O SQLITE
----------------
E um banco de dados que cabe num ARQUIVO SO (dados/financas.db). Nao precisa
instalar servidor, nao precisa senha, nao precisa nada rodando em segundo
plano. Voce copia o arquivo e levou o banco inteiro junto. O Python ja vem com
ele de fabrica (modulo sqlite3), por isso nem aparece no requirements.txt.

E por isso que ele foi escolhido: voce queria algo facil de transportar e de
guardar na nuvem.

COMO ESTE ARQUIVO ESTA ORGANIZADO
---------------------------------
    1. CONEXAO      -> como abrir e fechar o arquivo com seguranca
    2. MIGRACOES    -> como o formato das tabelas evolui sem perder dados
    3. ATALHOS      -> funcoes curtas para ler e escrever sem repetir codigo
    4. PARAMETROS   -> guardar configuracoes (chave -> valor)
    5. SEMENTE      -> o conteudo inicial (categorias, contas) num banco novo

A DECISAO MAIS IMPORTANTE DESTE PROJETO: O SINAL DO VALOR
---------------------------------------------------------
Na planilha antiga, a coluna Valor era SEMPRE positiva, e uma outra coluna
(Natureza) dizia se aquilo era entrada ou saida. Para somar o mes voce
precisava de um SUMIFS diferente para cada natureza.

Aqui e diferente e mais simples:

        valor NEGATIVO  =  dinheiro SAIU  (despesa, aporte, pagamento)
        valor POSITIVO  =  dinheiro ENTROU (salario, reembolso, rendimento)

Com isso, "quanto sobrou no mes" e literalmente a soma da coluna. A coluna
Natureza continua existindo, mas para CLASSIFICAR (e despesa? e investimento?),
nao para descobrir o sinal.

Se voce se confundir depois, lembre: o extrato do banco ja funciona assim.
"-R$ ····" saiu, "R$ ····" entrou.
"""

from __future__ import annotations

import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

from financas import config


@contextmanager
def conectar(caminho=None):
    """Abre o banco, entrega a conexao, e fecha sozinho no final.

    O decorador @contextmanager permite usar assim:

        with banco.conectar() as conn:
            conn.execute("SELECT ...")
        # aqui a conexao ja foi fechada automaticamente, mesmo se deu erro

    Tres ajustes importantes sao feitos em toda conexao:

    - row_factory = sqlite3.Row
      Sem isso, cada linha vem como tupla e voce acessa por posicao
      (linha[3]) — ilegivel e quebra assim que alguem muda a ordem das
      colunas. Com isso, voce acessa por nome: linha["valor"].

    - PRAGMA foreign_keys = ON
      O SQLite so verifica as ligacoes entre tabelas se voce pedir. Isso
      impede, por exemplo, apagar uma conta que ainda tem lancamentos.

    - PRAGMA journal_mode = WAL
      Modo "write-ahead logging": deixa ler e escrever ao mesmo tempo sem
      travar. Como o Streamlit reexecuta o script a cada clique, isso evita
      o erro "database is locked".

    ABRIMOS E FECHAMOS A CADA OPERACAO de proposito. Uma conexao SQLite nao
    pode ser compartilhada entre threads, e o Streamlit usa varias. Abrir de
    novo custa quase nada para um banco deste tamanho, e elimina uma classe
    inteira de bug dificil de achar.
    """
    if caminho is None:
        config.garantir_pastas()
        caminho = config.CAMINHO_BANCO

    conn = sqlite3.connect(str(caminho), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


MIGRACOES: list[str] = []

MIGRACOES.append("""
-- Contas: de onde o dinheiro sai/entra. O cartao de credito e uma "conta"
-- tambem, o que permite ter mais de um cartao depois sem refazer nada.
CREATE TABLE IF NOT EXISTS contas (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    nome   TEXT    NOT NULL UNIQUE,
    tipo   TEXT    NOT NULL,               -- 'Conta Corrente' ou 'Cartão de Crédito'
    banco  TEXT,
    ativo  INTEGER NOT NULL DEFAULT 1      -- SQLite nao tem booleano: 1=sim, 0=nao
);

-- Grandes categorias: o agrupamento largo (Casa, Comida, Moto...). Serve para
-- o orcamento e para os graficos nao ficarem com 26 fatias ilegiveis.
CREATE TABLE IF NOT EXISTS grandes_categorias (
    nome   TEXT PRIMARY KEY,
    cor    TEXT,
    ordem  INTEGER NOT NULL DEFAULT 0
);

-- Categorias: o detalhe (Alimentação, Combustível...). Cada uma pertence a
-- uma grande categoria.
CREATE TABLE IF NOT EXISTS categorias (
    nome              TEXT PRIMARY KEY,
    grande_categoria  TEXT NOT NULL,
    natureza_padrao   TEXT NOT NULL DEFAULT 'Despesa',
    ativa             INTEGER NOT NULL DEFAULT 1,
    ordem             INTEGER NOT NULL DEFAULT 0
);

-- LANCAMENTOS: o coracao do sistema. Cada linha e um evento financeiro.
CREATE TABLE IF NOT EXISTS lancamentos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,

    -- A impressao digital que impede importar a mesma compra duas vezes.
    -- UNIQUE faz o proprio banco recusar a duplicata, mesmo se o codigo
    -- tentar por engano. E a nossa ultima linha de defesa.
    id_unico            TEXT NOT NULL UNIQUE,

    data                TEXT NOT NULL,     -- 'AAAA-MM-DD' (ordena certo como texto)
    hora                TEXT,              -- 'HH:MM:SS', so o extrato tem
    mes_competencia     TEXT NOT NULL,     -- 'AAAA-MM': em que mes isso "conta"
    descricao           TEXT NOT NULL,
    portador            TEXT,

    valor               REAL NOT NULL,     -- COM SINAL (ver topo do arquivo)

    categoria           TEXT,
    tipo                TEXT,              -- 'Fixo' ou 'Variável'
    natureza            TEXT,              -- 'Despesa', 'Receita', ...
    origem              TEXT,              -- 'Fatura', 'Extrato', 'Manual', 'Rateio'
    conta_id            INTEGER,

    parcela_atual       INTEGER NOT NULL DEFAULT 1,
    parcela_total       INTEGER NOT NULL DEFAULT 1,
    chave_parcelamento  TEXT,              -- junta as parcelas da MESMA compra

    fitid               TEXT,              -- id unico que o OFX do banco fornece
    saldo_apos          REAL,              -- saldo da conta depois do lancamento
    observacao          TEXT,
    regra_aplicada      TEXT,              -- qual regra classificou (para auditar)

    criado_em           TEXT,
    atualizado_em       TEXT,

    FOREIGN KEY (conta_id) REFERENCES contas(id)
);

-- INDICES: sao "atalhos de busca". Sem eles, filtrar por mes faz o banco ler
-- as 1050 linhas uma a uma. Com eles, ele pula direto. Em troca, ocupam um
-- pouco mais de espaco e deixam a escrita um tico mais lenta — vale muito a
-- pena para as colunas que a gente filtra o tempo todo.
CREATE INDEX IF NOT EXISTS ix_lanc_mes       ON lancamentos(mes_competencia);
CREATE INDEX IF NOT EXISTS ix_lanc_data      ON lancamentos(data);
CREATE INDEX IF NOT EXISTS ix_lanc_categoria ON lancamentos(categoria);
CREATE INDEX IF NOT EXISTS ix_lanc_natureza  ON lancamentos(natureza);
CREATE INDEX IF NOT EXISTS ix_lanc_parc      ON lancamentos(chave_parcelamento);
CREATE INDEX IF NOT EXISTS ix_lanc_fitid     ON lancamentos(fitid);

-- Regras da FATURA: palavra-chave -> categoria. Lidas em ordem crescente de
-- `ordem`; a primeira que casar vence (igual a planilha fazia).
CREATE TABLE IF NOT EXISTS regras_fatura (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem          INTEGER NOT NULL DEFAULT 0,
    palavra_chave  TEXT    NOT NULL,
    categoria      TEXT    NOT NULL,
    tipo           TEXT    NOT NULL DEFAULT 'Variável',
    ativa          INTEGER NOT NULL DEFAULT 1
);

-- Regras do EXTRATO: mais ricas que as da fatura, porque no extrato a mesma
-- palavra pode significar coisas diferentes conforme o valor e o sentido.
-- Ex.: "XP EMPREGADORA" acima de 50 mil e PLR; abaixo disso e Salario.
CREATE TABLE IF NOT EXISTS regras_extrato (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ordem          INTEGER NOT NULL DEFAULT 0,
    palavra_chave  TEXT    NOT NULL,
    valor_min_abs  REAL    NOT NULL DEFAULT 0,   -- compara com o valor ABSOLUTO
    sinal          TEXT    NOT NULL DEFAULT 'Ambos',  -- Entrada / Saída / Ambos
    categoria      TEXT    NOT NULL,
    tipo           TEXT    NOT NULL DEFAULT 'Variável',
    natureza       TEXT    NOT NULL DEFAULT 'Despesa',
    ativa          INTEGER NOT NULL DEFAULT 1
);

-- Gastos fixos cadastrados (aluguel, faculdade, assinaturas...).
CREATE TABLE IF NOT EXISTS gastos_fixos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item            TEXT    NOT NULL,
    categoria       TEXT,
    valor_mensal    REAL    NOT NULL DEFAULT 0,
    dia             INTEGER,                 -- dia do mes em que vence
    inicio          TEXT,                    -- 'AAAA-MM'
    fim             TEXT,                    -- 'AAAA-MM' vazio = sem fim previsto
    reajuste_aa     REAL    NOT NULL DEFAULT 0,   -- reajuste anual, fracao (0.05 = 5%)
    ativo           INTEGER NOT NULL DEFAULT 1,
    parcelado       INTEGER NOT NULL DEFAULT 0,  -- LEGADO: ninguem le. Superada na
                                             -- migracao 19 por forma_pagamento +
                                             -- a deteccao automatica de parcelas
    chave_historico TEXT,                    -- palavra p/ achar no historico real
    observacao      TEXT
);

-- Orcamento: quanto voce PRETENDE gastar em cada grande categoria, por mes.
-- A chave primaria composta garante uma linha por (mes, grande categoria).
CREATE TABLE IF NOT EXISTS orcamento (
    mes               TEXT NOT NULL,
    grande_categoria  TEXT NOT NULL,
    valor_orcado      REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (mes, grande_categoria)
);

-- Metas e objetivos (reserva de emergencia, entrada do imovel...).
CREATE TABLE IF NOT EXISTS metas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    meta           TEXT    NOT NULL,
    tipo           TEXT,
    valor_alvo     REAL    NOT NULL DEFAULT 0,
    ja_acumulado   REAL    NOT NULL DEFAULT 0,
    prazo          TEXT,                     -- 'AAAA-MM' desejado
    aporte_definido REAL   NOT NULL DEFAULT 0,
    prioridade     TEXT    NOT NULL DEFAULT 'Média',
    status         TEXT    NOT NULL DEFAULT 'Ativa',
    observacao     TEXT,
    ordem          INTEGER NOT NULL DEFAULT 0
);

-- Lista de desejos com preco alvo x preco atual.
CREATE TABLE IF NOT EXISTS futuras_compras (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    item          TEXT    NOT NULL,
    categoria     TEXT,
    prioridade    TEXT    NOT NULL DEFAULT 'Média',
    loja          TEXT,
    link          TEXT,
    preco_alvo    REAL,
    preco_atual   REAL,
    data_cotacao  TEXT,
    status        TEXT    NOT NULL DEFAULT 'Desejo',
    observacao    TEXT
);

-- Patrimonio mes a mes: o saldo que voce tinha em conta e aplicado.
CREATE TABLE IF NOT EXISTS patrimonio_mensal (
    mes                    TEXT PRIMARY KEY,
    saldo_conta            REAL,
    saldo_aplicado_manual  REAL,       -- se preenchido, manda no lugar do estimado
    observacao             TEXT
);

-- Cenarios de financiamento imobiliario (da aba Financiamento).
CREATE TABLE IF NOT EXISTS financiamento_cenarios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nome              TEXT NOT NULL,
    valor_imovel      REAL NOT NULL DEFAULT 0,
    valor_entrada     REAL NOT NULL DEFAULT 0,
    prazo_meses       INTEGER NOT NULL DEFAULT 360,
    sistema           TEXT NOT NULL DEFAULT 'PRICE',   -- PRICE ou SAC
    juros_aa          REAL NOT NULL DEFAULT 0.1,
    conversao_taxa    TEXT NOT NULL DEFAULT 'Equivalente (efetiva)',
    seguro_mip_am     REAL NOT NULL DEFAULT 0.00025,
    seguro_dfi_am     REAL NOT NULL DEFAULT 0.0001,
    taxa_adm_mes      REAL NOT NULL DEFAULT 25,
    aporte_extra_mes  REAL NOT NULL DEFAULT 0,
    aporte_inicio     INTEGER NOT NULL DEFAULT 1,
    aporte_pontual    REAL NOT NULL DEFAULT 0,
    aporte_pontual_parcela INTEGER NOT NULL DEFAULT 12,
    efeito_aporte     TEXT NOT NULL DEFAULT 'Reduzir prazo'
);

-- Configuracoes soltas do app, no formato chave -> valor.
CREATE TABLE IF NOT EXISTS parametros (
    chave  TEXT PRIMARY KEY,
    valor  TEXT
);

-- Historico de importacoes: impede reimportar o mesmo arquivo por engano.
CREATE TABLE IF NOT EXISTS arquivos_importados (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    sha256          TEXT NOT NULL,
    tipo            TEXT,
    mes_referencia  TEXT,
    linhas_lidas    INTEGER NOT NULL DEFAULT 0,
    linhas_novas    INTEGER NOT NULL DEFAULT 0,
    linhas_dup      INTEGER NOT NULL DEFAULT 0,
    importado_em    TEXT
);
""")

MIGRACOES.append("""
-- O cadastro: o que voce tem.
CREATE TABLE IF NOT EXISTS investimentos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    nome             TEXT    NOT NULL,
    tipo             TEXT    NOT NULL DEFAULT 'Renda Fixa',
    instituicao      TEXT,
    indexador        TEXT,              -- CDI, IPCA+, Prefixado, Variável...
    taxa_contratada  REAL,              -- 1.10 = 110% do CDI | 0.12 = 12% a.a.
    data_inicio      TEXT,              -- 'AAAA-MM-DD'
    data_vencimento  TEXT,              -- vazio = sem vencimento
    liquidez         TEXT,              -- 'Diária', 'No vencimento', 'D+30'...
    objetivo         TEXT,              -- para que esse dinheiro serve
    ativo            INTEGER NOT NULL DEFAULT 1,
    observacao       TEXT
);

-- O acompanhamento: quanto cada um valia no fim de cada mes.
CREATE TABLE IF NOT EXISTS investimentos_saldos (
    investimento_id  INTEGER NOT NULL,
    mes              TEXT    NOT NULL,          -- 'AAAA-MM'
    saldo            REAL    NOT NULL DEFAULT 0, -- quanto vale no fim do mes
    aporte           REAL    NOT NULL DEFAULT 0, -- quanto voce pos neste mes
    resgate          REAL    NOT NULL DEFAULT 0, -- quanto voce tirou
    observacao       TEXT,

    -- Chave composta: uma linha por investimento por mes. O banco impede
    -- registrar o mesmo mes duas vezes para o mesmo investimento.
    PRIMARY KEY (investimento_id, mes),
    FOREIGN KEY (investimento_id) REFERENCES investimentos(id)
);

CREATE INDEX IF NOT EXISTS ix_inv_saldos_mes ON investimentos_saldos(mes);
""")

MIGRACOES.append("""
-- O nivel de cima: Renda Fixa, Renda Variavel, Internacional, Caixa.
CREATE TABLE IF NOT EXISTS macros_ativo (
    nome   TEXT PRIMARY KEY,
    cor    TEXT,
    ordem  INTEGER NOT NULL DEFAULT 0
);

-- O nivel de baixo: NTN-B, Tesouro Selic, ETF, Ação BR...
--
-- `palavras_chave` e o que permite classificar um papel automaticamente pelo
-- NOME dele. Precisa existir porque a classificacao da corretora nao serve:
-- no arquivo da XP, NTN-B e LFT aparecem no mesmo bloco rotulado
-- "Pós-Fixado", embora a NTN-B seja indexada a inflacao. O nome do papel e
-- confiavel; o rotulo do bloco nao.
CREATE TABLE IF NOT EXISTS classes_ativo (
    nome            TEXT PRIMARY KEY,
    macro           TEXT NOT NULL,
    ordem           INTEGER NOT NULL DEFAULT 0,
    palavras_chave  TEXT              -- separadas por "|", vazio = so manual
);

-- A meta de alocacao. `nivel` diz se a meta e por macro ou por classe, o que
-- permite voce dizer "60% em Renda Fixa" E "dentro dela, 40% em NTN-B".
CREATE TABLE IF NOT EXISTS metas_alocacao (
    nivel            TEXT NOT NULL,        -- 'macro' ou 'classe'
    nome             TEXT NOT NULL,
    percentual_alvo  REAL NOT NULL DEFAULT 0,   -- fracao: 0.30 = 30%
    tolerancia       REAL NOT NULL DEFAULT 0.05, -- 0.05 = 5 pontos percentuais
    PRIMARY KEY (nivel, nome)
);

-- O extrato de DENTRO da conta de investimento: compras, juros, IRRF.
--
-- TABELA SEPARADA DE `lancamentos` DE PROPOSITO. Uma "COMPRA TESOURO DIRETO"
-- de R$ 25 mil nao e despesa — o dinheiro so mudou de forma. Se entrasse em
-- lancamentos, o Dashboard mostraria R$ 103 mil de gasto que nunca existiu, e
-- as transferencias apareceriam duas vezes (a conta corrente ja registra o
-- outro lado).
CREATE TABLE IF NOT EXISTS investimentos_movimentos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    id_unico         TEXT NOT NULL UNIQUE,
    data             TEXT NOT NULL,        -- 'AAAA-MM-DD'
    liquidacao       TEXT,
    mes_competencia  TEXT NOT NULL,        -- 'AAAA-MM'
    descricao        TEXT NOT NULL,
    valor            REAL NOT NULL,        -- COM SINAL, igual ao resto do app
    saldo_apos       REAL,
    tipo_movimento   TEXT,                 -- aporte, compra, juros, imposto...
    investimento_id  INTEGER,              -- quando da para ligar ao papel
    criado_em        TEXT,
    FOREIGN KEY (investimento_id) REFERENCES investimentos(id)
);

CREATE INDEX IF NOT EXISTS ix_inv_mov_data ON investimentos_movimentos(data);
CREATE INDEX IF NOT EXISTS ix_inv_mov_mes  ON investimentos_movimentos(mes_competencia);
CREATE INDEX IF NOT EXISTS ix_inv_mov_tipo ON investimentos_movimentos(tipo_movimento);

-- A classe (nivel micro) de cada investimento cadastrado.
ALTER TABLE investimentos ADD COLUMN classe TEXT;

-- A moeda fica registrada desde ja, mesmo com tudo em BRL hoje: quando o
-- stock pick dos EUA entrar, a coluna ja existe e nao precisa de migracao.
ALTER TABLE investimentos ADD COLUMN moeda TEXT DEFAULT 'BRL';
""")

MIGRACOES.append("""
ALTER TABLE investimentos_saldos ADD COLUMN custo_aplicado REAL;
""")

MIGRACOES.append("""
ALTER TABLE investimentos_saldos ADD COLUMN quantidade REAL;
""")

MIGRACOES.append("""
CREATE TRIGGER IF NOT EXISTS tg_lancamentos_atualizado_em
AFTER UPDATE ON lancamentos
FOR EACH ROW
WHEN NEW.atualizado_em IS OLD.atualizado_em
BEGIN
    UPDATE lancamentos
       SET atualizado_em = datetime('now', 'localtime')
     WHERE id = NEW.id;
END;
""")

MIGRACOES.append("""
INSERT OR IGNORE INTO classes_ativo (nome, macro, ordem, palavras_chave)
VALUES ('Saldo em conta', 'Caixa', 13, '');
""")

MIGRACOES.append("""
CREATE TABLE IF NOT EXISTS cotacoes (
    ticker      TEXT NOT NULL,       -- 'IREN', 'TASA3.SA', 'USDBRL'
    data        TEXT NOT NULL,       -- 'AAAA-MM-DD'
    fechamento  REAL NOT NULL,
    moeda       TEXT NOT NULL DEFAULT 'USD',   -- em que moeda o preco esta
    fonte       TEXT,                -- 'yfinance' | 'ptax' | 'manual'
    obtida_em   TEXT,
    PRIMARY KEY (ticker, data)
);

CREATE INDEX IF NOT EXISTS ix_cotacoes_data ON cotacoes(data);

-- O simbolo do papel no provedor de cotacoes. Vazio = acompanhado a mao.
-- B3 leva sufixo '.SA' (TASA3.SA); bolsa americana vai direto (IREN).
ALTER TABLE investimentos ADD COLUMN ticker TEXT;

-- O saldo na moeda ORIGINAL do papel. Fica NULL para tudo que e BRL, onde
-- seria so uma copia de `saldo`.
ALTER TABLE investimentos_saldos ADD COLUMN saldo_moeda REAL;

-- A cotacao usada na conversao daquele mes. Guardar o CAMBIO EMPREGADO, e nao
-- so recalcular depois, e o que permite reproduzir o numero que estava na tela
-- meses atras — a cotacao de hoje nao serve para conferir o passado.
ALTER TABLE investimentos_saldos ADD COLUMN cambio_usado REAL;
""")

MIGRACOES.append("""
INSERT OR IGNORE INTO classes_ativo (nome, macro, ordem, palavras_chave)
VALUES ('ETF EUA', 'Internacional', 14, '');
""")

MIGRACOES.append("""
CREATE TABLE IF NOT EXISTS indices (
    nome      TEXT NOT NULL,          -- 'CDI' | 'IPCA'
    mes       TEXT NOT NULL,          -- 'AAAA-MM'
    taxa      REAL NOT NULL,          -- variacao do mes, em fracao
    fonte     TEXT,                   -- 'sgs'
    obtida_em TEXT,
    PRIMARY KEY (nome, mes)
);
""")

MIGRACOES.append("""
ALTER TABLE investimentos_saldos ADD COLUMN fonte_custo TEXT;
UPDATE investimentos_saldos SET fonte_custo = 'valor_aplicado'
 WHERE custo_aplicado IS NOT NULL AND fonte_custo IS NULL;
""")

MIGRACOES.append("""
ALTER TABLE futuras_compras ADD COLUMN projeto  TEXT;
ALTER TABLE futuras_compras ADD COLUMN mes_alvo TEXT;
""")

def _migracao_13_competencia_da_fatura(conn) -> None:
    """Recua a competencia de toda linha de fatura em 1 mes, com a chave junto."""
    from financas.formato import mes_para_indice, normalizar_texto, somar_meses

    linhas = conn.execute(
        """SELECT id, mes_competencia, descricao, parcela_atual, parcela_total
             FROM lancamentos WHERE origem = 'Fatura'"""
    ).fetchall()

    for linha in linhas:
        mes_novo = somar_meses(linha["mes_competencia"], -1)
        if not mes_novo:
            continue

        chave = None
        total = linha["parcela_total"] or 0
        atual = linha["parcela_atual"] or 0
        if total > 1 and atual >= 1:
            indice = mes_para_indice(mes_novo)
            if indice is not None:
                chave = (f"{normalizar_texto(linha['descricao'])}|{total}|"
                         f"{indice - (atual - 1)}")

        conn.execute(
            "UPDATE lancamentos SET mes_competencia = ?, chave_parcelamento = ? "
            "WHERE id = ?",
            (mes_novo, chave, linha["id"]))


MIGRACOES.append(_migracao_13_competencia_da_fatura)

def _migracao_14_id_unico_da_fatura(conn) -> None:
    """Recalcula o id_unico de toda linha de fatura pela formula unica."""
    from collections import Counter

    from financas.formato import chave_hash
    from financas.importador import assinatura_fatura

    linhas = conn.execute(
        """SELECT id, id_unico, mes_competencia, data, descricao, portador,
                  valor, parcela_atual, parcela_total
             FROM lancamentos WHERE origem = 'Fatura' ORDER BY id"""
    ).fetchall()
    if not linhas:
        return

    ocorrencias: Counter = Counter()
    novos: list[tuple[str, int]] = []
    for linha in linhas:
        assinatura = assinatura_fatura(
            linha["mes_competencia"], linha["data"], linha["descricao"],
            linha["portador"], linha["valor"],
            linha["parcela_atual"], linha["parcela_total"])
        ocorrencias[assinatura] += 1
        novos.append((chave_hash(*assinatura, ocorrencias[assinatura]),
                      linha["id"]))

    ids_novos = {novo for novo, _ in novos}
    if len(ids_novos) != len(novos):
        raise RuntimeError(
            f"migracao 14 abortada: {len(novos) - len(ids_novos)} colisao(oes) "
            f"entre as linhas de fatura. Isso indica linhas duplicadas ja "
            f"gravadas — investigue antes de recalcular os ids.")

    de_fora = conn.execute(
        "SELECT COUNT(*) FROM lancamentos WHERE origem <> 'Fatura' "
        f"AND id_unico IN ({','.join('?' * len(ids_novos))})",
        tuple(ids_novos)).fetchone()[0]
    if de_fora:
        raise RuntimeError(
            f"migracao 14 abortada: {de_fora} id(s) novo(s) colidem com "
            f"lancamentos que nao sao de fatura.")

    conn.execute(
        "UPDATE lancamentos SET id_unico = 'mig14:' || id WHERE origem = 'Fatura'")
    conn.executemany(
        "UPDATE lancamentos SET id_unico = ? WHERE id = ?", novos)

    sobraram = conn.execute(
        "SELECT COUNT(*) FROM lancamentos WHERE id_unico LIKE 'mig14:%'"
    ).fetchone()[0]
    if sobraram:
        raise RuntimeError(
            f"migracao 14 abortada: {sobraram} linha(s) ficaram com o id "
            f"temporario — a segunda passada nao cobriu todas.")


MIGRACOES.append(_migracao_14_id_unico_da_fatura)

MIGRACOES.append("""
CREATE TABLE IF NOT EXISTS ir_ano (
    ano                TEXT PRIMARY KEY,   -- ano-calendario, 'AAAA'
    rendimento_bruto   REAL,               -- tributavel sujeito ao AJUSTE ANUAL:
                                           -- salario bruto + ferias. NAO entram
                                           -- PLR nem 13o (tributacao exclusiva)
    inss               REAL,               -- previdencia oficial descontada no ano
    irrf_retido        REAL,               -- imposto retido na fonte sobre o salario
    dependentes        INTEGER DEFAULT 0,
    despesas_medicas   REAL DEFAULT 0,     -- sem teto na lei
    despesas_instrucao REAL DEFAULT 0,     -- o gasto cheio; o teto entra no calculo
    pensao_alimenticia REAL DEFAULT 0,
    outras_deducoes    REAL DEFAULT 0,
    aportes_pgbl       REAL DEFAULT 0,     -- ja aportado no ano
    contribui_inss     INTEGER DEFAULT 1,  -- porta de entrada da deducao de 12%
    atualizado_em      TEXT
);
""")

MIGRACOES.append("""
CREATE TABLE IF NOT EXISTS investimentos_compras (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    investimento_id INTEGER NOT NULL,
    data            TEXT NOT NULL,     -- 'AAAA-MM-DD', o dia da ordem
    quantidade      REAL,              -- NULL para fundo, que nao tem cota unitaria
    valor_unitario  REAL,              -- na MOEDA DO PAPEL
    custos          REAL DEFAULT 0,    -- corretagem e emolumentos, na moeda do papel
    valor_total     REAL NOT NULL,     -- na moeda do papel
    moeda           TEXT NOT NULL,
    cambio_usado    REAL,              -- gravado na hora; NULL quando ja e BRL
    valor_total_brl REAL NOT NULL,     -- convertido UMA vez, na gravacao
    fator_ajuste    REAL DEFAULT 1.0,  -- grupamento/desdobramento posterior
    observacao      TEXT,
    criado_em       TEXT
);
CREATE INDEX IF NOT EXISTS ix_compras_papel
    ON investimentos_compras (investimento_id);
""")

MIGRACOES.append("""
CREATE TABLE IF NOT EXISTS fundamentos (
    ticker      TEXT PRIMARY KEY,
    dados       TEXT NOT NULL,      -- o json cru da fonte, sem interpretacao
    fonte       TEXT,
    obtido_em   TEXT
);
ALTER TABLE investimentos ADD COLUMN alavancagem REAL;
ALTER TABLE investimentos ADD COLUMN subjacente TEXT;
""")

MIGRACOES.append("""
ALTER TABLE metas ADD COLUMN vinculo TEXT;
""")


def _migracao_19_forma_de_pagamento_do_fixo(conn) -> None:
    """Quatro colunas em `gastos_fixos`, e adivinha a forma de pagamento.

    POR QUE. A previsao somava o gasto fixo CADASTRADO e a parcela do cartao
    PROJETADA como se fossem coisas diferentes. Quando o mesmo gasto e as duas
    (a nutricionista: cadastrada como fixo E chegando parcelada em 12x), ele
    contava duas vezes — R$ ···· por mes ate abr/2027.

    As colunas novas dao a cada item tres respostas que o codigo nao tinha como
    adivinhar sozinho: por onde ele e pago, se deve entrar na previsao, e se o
    valor e o que voce digitou ou a media do historico.

    O BACKFILL VOTA, NAO CHUTA. Para cada item, casa `chave_historico` contra
    os lancamentos dos ultimos 12 meses e ve de que origem vieram. Maioria
    Fatura -> 'Cartao'. Qualquer outra coisa, empate ou zero casamentos ->
    'Conta', que e o default conservador: errar para fora da fatura esconde
    menos do que errar para dentro.

    `parcelado` fica onde esta, de proposito. Dropar coluna quebraria a
    restauracao de todo backup .zip ja gerado, porque `backup.restaurar` monta
    o INSERT com as colunas que encontra no CSV.
    """
    from financas.formato import normalizar_texto, somar_meses

    conn.executescript("""
        ALTER TABLE gastos_fixos ADD COLUMN forma_pagamento     TEXT    NOT NULL DEFAULT 'Conta';
        ALTER TABLE gastos_fixos ADD COLUMN considerar_previsao INTEGER NOT NULL DEFAULT 1;
        ALTER TABLE gastos_fixos ADD COLUMN base_valor          TEXT    NOT NULL DEFAULT 'Cadastrado';
        ALTER TABLE gastos_fixos ADD COLUMN categoria_historico TEXT;
    """)

    itens = conn.execute(
        "SELECT id, item, chave_historico FROM gastos_fixos").fetchall()
    if not itens:
        return

    ultimo = conn.execute(
        "SELECT MAX(mes_competencia) AS m FROM lancamentos").fetchone()["m"]
    if not ultimo:
        return
    corte = somar_meses(ultimo, -11)

    lancamentos = conn.execute(
        """SELECT descricao, origem FROM lancamentos
            WHERE natureza = 'Despesa' AND mes_competencia >= ?""",
        (corte,)).fetchall()
    descricoes = [(normalizar_texto(l["descricao"]), l["origem"])
                  for l in lancamentos]

    decisoes: list[tuple[str, int]] = []
    for linha in itens:
        chave = normalizar_texto(linha["chave_historico"])
        forma = "Conta"
        if chave:
            votos_cartao = sum(1 for d, o in descricoes
                               if chave in d and o == "Fatura")
            votos_conta = sum(1 for d, o in descricoes
                              if chave in d and o != "Fatura")
            if votos_cartao > votos_conta:
                forma = "Cartão"
            print(f"  {linha['item'][:38]:<40} Fatura {votos_cartao:>3} | "
                  f"outras {votos_conta:>3}  -> {forma}")
        else:
            print(f"  {linha['item'][:38]:<40} sem chave"
                  f"{'':>18}  -> {forma}")
        decisoes.append((forma, linha["id"]))

    conn.executemany(
        "UPDATE gastos_fixos SET forma_pagamento = ? WHERE id = ?", decisoes)


MIGRACOES.append(_migracao_19_forma_de_pagamento_do_fixo)


def _migracao_20_rateio_nao_e_caixa(conn) -> None:
    """Dois itens cujo valor cadastrado nao e o que sai da conta.

    POR QUE. O cadastro de gastos fixos alimenta uma previsao de CAIXA — "o que
    o banco vai debitar". Dois itens estavam cadastrados pelo valor RATEADO,
    que e outra pergunta ("quanto disso e meu"). O rateio esta certo para saber
    de quem e a despesa; ele so nao e o numero que o banco debita.

    SEGURO DA MOTO. Cadastrado R$ ····/mes como "rateio mensal". As
    cobrancas reais foram tres de R$ ···· (mar, abr e mai/2026) e nada depois
    — apolice paga em parcelas, nao mensalidade. A previsao seguia somando
    R$ ···· em set, out e nov por uma cobranca que nao vem mais. Ele
    confirmou em 30/08/2026 que a apolice esta quitada, entao o item ganha
    `fim`, e nao `ativo = 0`: encerrar por data preserva os meses passados em
    que ele valeu, e desativar reescreveria a historia.

    YOUTUBE PREMIUM. Cadastrado R$ ···· — um quarto de R$ ···· Mas o debito
    e de R$ ···· todo mes, e o reembolso dos amigos chega em lotes irregulares
    (R$ ···· de oito pessoas em jun/2026), nao mensalmente. Previa-se um
    quarto de uma conta que sai inteira.

    O SENTIDO DO ERRO IMPORTA: previsao curta demais e a que faz alguem achar
    que tem folga que nao tem. Os dois acertos empurram a previsao para o lado
    pessimista, que e o lado seguro para quem esta tentando fazer sobrar
    salario.
    """
    conn.execute(
        "UPDATE gastos_fixos SET fim = '2026-05', observacao = ? "
        " WHERE item LIKE 'Seguro moto Suhai%' AND fim IS NULL",
        ("apólice quitada em 3 parcelas (mar-mai/2026); encerrado em "
         "30/08/2026",))

    conn.execute(
        "UPDATE gastos_fixos SET valor_mensal = 53.90, item = ?, "
        "       observacao = ? "
        " WHERE item LIKE 'YouTube Premium%' AND valor_mensal < 20",
        ("YouTube Premium (família)",
         "o débito é cheio (DL*GOOGLE YOUTUB); o reembolso dos amigos chega "
         "em lotes irregulares, não mês a mês"))


MIGRACOES.append(_migracao_20_rateio_nao_e_caixa)

# Historico de preco de cada item da lista de desejos.
#
# POR QUE UMA TABELA, E NAO MAIS UMA COLUNA. `futuras_compras.preco_atual` e um
# numero que se SOBRESCREVE: a cada consulta o valor anterior some. Sem os
# valores anteriores nao da para responder a unica pergunta que importa numa
# lista de desejos — "R$ ···· hoje e caro?". Uma linha por consulta responde,
# e de graca: menor preco ja visto, curva, e "esta no melhor preco de sempre".
#
# NAO HA COLUNA `preco_minimo`. O menor preco e `MIN(preco)` daqui. Guardar o
# minimo tambem seria duas fontes para o mesmo numero, e duas chances de
# divergir — a mesma razao pela qual preco e cambio moram na mesma tabela
# `cotacoes`.
MIGRACOES.append("""
CREATE TABLE IF NOT EXISTS precos_compras (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id  INTEGER NOT NULL,
    data       TEXT    NOT NULL,      -- 'AAAA-MM-DD' da consulta
    preco      REAL    NOT NULL,
    fonte      TEXT,                  -- 'manual' | 'jsonld' | 'og' | 'microdata'
    obtido_em  TEXT
);

CREATE INDEX IF NOT EXISTS ix_precos_compras
    ON precos_compras (compra_id, data);
""")


# O TEMA: a que o papel te expoe, e nao o que ele e.
#
# POR QUE UM EIXO SEPARADO, E NAO UMA SUBCLASSE. "Datacenters" pode ser uma
# acao americana, um REIT e um ETF ao mesmo tempo. Como filho da classe, o
# mesmo tema precisaria existir tres vezes, e somar exposicao viraria conta a
# mao. Como coluna solta, ele corta a carteira por outro eixo — ver
# docs/22_eixos_da_carteira.md.
#
# POR QUE MANUAL. O app ja guarda os fundamentos do yfinance, e para a IREN
# eles dizem sector "Financial Services", industry "Capital Markets". E a
# classificacao contabil da empresa, nao a exposicao economica dela: puxar
# isso automaticamente poria um datacenter de IA em "Servicos Financeiros",
# com toda a confianca de um dado que veio de fora. A sugestao do provedor
# aparece ao lado do campo, para voce decidir; nunca preenche sozinha.
#
# A TABELA E EDITAVEL de proposito. Uma lista fechada no codigo seria uma
# armadilha no dia em que a carteira ganhasse um tema que ninguem previu.
MIGRACOES.append("""
ALTER TABLE investimentos ADD COLUMN tema TEXT;

CREATE TABLE IF NOT EXISTS temas_ativo (
    nome   TEXT PRIMARY KEY,
    ordem  INTEGER NOT NULL DEFAULT 0
);

INSERT OR IGNORE INTO temas_ativo (nome, ordem) VALUES
    ('Amplo / Diversificado', 1),
    ('Bolsa ampla',           2),
    ('Datacenters e IA',      3),
    ('Tecnologia',            4),
    ('Metais e mineração',    5),
    ('Energia',               6),
    ('Imóveis',               7),
    ('Dividendos',            8),
    ('Financeiro',            9),
    ('Consumo',              10),
    ('Saúde',                11),
    ('Cripto',               12);
""")


# AS CONTAS QUE FALTAVAM, E A NATUREZA DE CADA MOVIMENTO DA CORRETORA.
#
# O DINHEIRO DELE ANDA POR TRES CONTAS, e o app so conhecia uma. A conta de
# investimentos existia como a tabela `investimentos_movimentos` mais um papel
# chamado "Saldo em conta (XP)"; a conta global existia so como tres papeis,
# sem o caixa em dolar. Com isso, "transferi da corrente para a de
# investimentos" era uma CATEGORIA, e nao o que de fato e: saldo saindo de uma
# conta e entrando em outra.
#
# `natureza` E O CAMPO QUE TAPA O BURACO. Ate aqui, todo movimento da corretora
# que nao casasse com uma regra virava `tipo_movimento = 'outro'`, e o calculo
# de fluxo externo so olhava `aporte` e `resgate`. Resultado real, no extrato
# dele de setembro:
#
#     2026-09-02  TED - RECEBIMENTO EXTERNO  +R$ ····  ->  "outro"
#
# Dinheiro entrando de fora direto na corretora, que virou
# RENDIMENTO DE INVESTIMENTO em silencio — porque `conciliar()` calcula
# `carteira − aportado − abertura` e chama a sobra de rendimento.
#
# `natureza` fica NULL ate voce triar na tela. Enquanto for NULL, o valor
# aparece na linha "nao explicado" do fechamento — visivel, com mes e valor.
# O app nao adivinha: "TED - RECEBIMENTO EXTERNO" tanto pode ser venda quanto
# heranca ou venda de carro, e um palpite errado aqui erra em silencio.
MIGRACOES.append("""
ALTER TABLE contas ADD COLUMN moeda TEXT NOT NULL DEFAULT 'BRL';

INSERT OR IGNORE INTO contas (nome, tipo, banco, moeda, ativo) VALUES
    ('Conta Investimentos XP', 'Conta de Investimento', 'Banco XP S.A.', 'BRL', 1),
    ('XP Investments US',      'Conta de Investimento', 'XP Investments US LLC', 'USD', 1);

-- 'entrada_externa' | 'saida_externa' | 'interna' | NULL (= ainda nao triado)
ALTER TABLE investimentos_movimentos ADD COLUMN natureza TEXT;

-- O que ja da para afirmar sem perguntar: aporte e resgate sao, por
-- definicao, dinheiro andando entre as SUAS contas. Compra, venda, juros e
-- imposto nao cruzam a fronteira do patrimonio — acontecem dentro dela.
UPDATE investimentos_movimentos SET natureza = 'interna'
 WHERE tipo_movimento IN ('aporte', 'resgate');
""")


# CORRIGE A 23: `natureza` guarda so o que NAO da para derivar.
#
# A migracao anterior gravou `natureza = 'interna'` em todo aporte e resgate.
# O valor esta certo — e justamente por isso nao devia estar gravado: ele e
# funcao direta do `tipo_movimento`, e uma copia gravada de algo derivavel e
# uma segunda verdade esperando para divergir no dia em que a regra mudar.
#
# A partir daqui:
#     tipo_movimento conhecido  -> o componente sai de COMPONENTE_DO_TIPO
#     tipo_movimento 'outro'    -> `natureza` guarda a SUA resposta, e ate
#                                  voce responder o valor aparece em
#                                  "nao explicado"
#
# E a mesma divisao de `balde_de` (deriva) contra `tema` (guarda): guarda-se o
# que so uma pessoa sabe.
MIGRACOES.append("""
UPDATE investimentos_movimentos SET natureza = NULL
 WHERE tipo_movimento IN ('aporte', 'resgate') AND natureza = 'interna';
""")


# A CATEGORIA QUE FALTAVA PARA DINHEIRO QUE ENTRA E NAO E RENDA.
#
# Uma entrada de R$ ···· caiu direto na corretora e por isso nunca virou
# lancamento: `lancamentos` so nasce de extrato da conta corrente ou de
# fatura. Ele perguntou o obvio — "como e receita extra, por que nao entra
# para os lancamentos?" — e nao havia resposta boa.
#
# `Indenizacao` e uma categoria, nao um rotulo solto, porque e a CATEGORIA que
# decide a ficha do imposto (`DESTINO_DA_RECEITA`). Escolher esse nome faz o
# mapeamento ser verdadeiro por construcao: indenizacao e isenta. Verba de
# origem que pague salario atrasado E tributavel e pertence a outra
# categoria — a nota da ficha diz isso, para o nome nao virar uma isencao
# automatica que ninguem conferiu.
MIGRACOES.append("""
INSERT OR IGNORE INTO categorias (nome, grande_categoria, natureza_padrao, ativa, ordem)
VALUES ('Indenização', 'Receita', 'Receita Extraordinária', 1, 90);
""")


def versao_atual(conn) -> int:
    """Le o numero da versao gravado dentro do proprio arquivo .db."""
    return conn.execute("PRAGMA user_version").fetchone()[0]


def aplicar_migracoes(caminho=None) -> int:
    """Roda as migracoes que ainda faltam. Devolve quantas foram aplicadas.

    E seguro chamar quantas vezes quiser: se ja estiver atualizado, nao faz
    nada. Por isso o app chama isso toda vez que sobe.
    """
    aplicadas = 0
    with conectar(caminho) as conn:
        versao = versao_atual(conn)
        for numero, sql in enumerate(MIGRACOES, start=1):
            if numero > versao:
                if callable(sql):
                    sql(conn)
                else:
                    conn.executescript(sql)
                conn.execute(f"PRAGMA user_version = {numero}")
                aplicadas += 1
    return aplicadas


def consultar(sql: str, params=()) -> list[sqlite3.Row]:
    """Roda um SELECT e devolve a lista de linhas."""
    with conectar() as conn:
        return conn.execute(sql, params).fetchall()


def consultar_um(sql: str, params=()):
    """Roda um SELECT e devolve so a primeira linha (ou None)."""
    with conectar() as conn:
        return conn.execute(sql, params).fetchone()


def df(sql: str, params=()) -> pd.DataFrame:
    """Roda um SELECT e devolve um DataFrame do pandas.

    DataFrame e a "tabela em memoria" do pandas: parece uma planilha, com
    colunas nomeadas, e sabe somar/agrupar/filtrar sozinho. E o formato que
    todo o resto do projeto usa para calcular e desenhar grafico.
    """
    with conectar() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def executar(sql: str, params=()) -> int:
    """Roda INSERT/UPDATE/DELETE. Devolve o id inserido, ou as linhas afetadas.

    ATENCAO A SEGURANCA: sempre passe valores em `params`, com ? no SQL:

        executar("DELETE FROM lancamentos WHERE id = ?", (5,))   # certo
        executar(f"DELETE FROM lancamentos WHERE id = {5}")      # errado

    O jeito errado permite "SQL injection" — alguem escrever comando dentro de
    um campo de texto. Com ? o banco trata o valor sempre como dado, nunca
    como comando.
    """
    with conectar() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid if cur.lastrowid else cur.rowcount


def executar_muitos(sql: str, lista_de_params) -> int:
    """Roda o mesmo comando para varias linhas de uma vez.

    Muito mais rapido que chamar `executar` num laco: o banco abre UMA
    transacao para as 1050 linhas em vez de 1050 transacoes.

    DEVOLVE QUANTAS LINHAS ENTRARAM DE FATO, e nao quantas foram tentadas.

    A diferenca so aparece com "INSERT OR IGNORE", que e justamente como toda
    importacao grava: mandar 19 linhas das quais 4 sao repetidas resulta em 15.
    Devolver 19 faria a tela anunciar "19 gravadas, 0 ignoradas" logo depois de
    a deduplicacao ter funcionado — o numero que existe para provar que ela
    funcionou seria o unico a esconder isso.
    """
    lista = list(lista_de_params)
    if not lista:
        return 0
    with conectar() as conn:
        return conn.executemany(sql, lista).rowcount


def agora() -> str:
    """Data e hora de agora em texto ISO, para as colunas criado_em."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def contar(tabela: str) -> int:
    """Quantas linhas tem a tabela. Util para checar se o banco esta vazio."""
    linha = consultar_um(f"SELECT COUNT(*) AS n FROM {tabela}")
    return int(linha["n"]) if linha else 0


def tabelas() -> list[str]:
    """Lista os nomes das tabelas existentes no banco."""
    linhas = consultar(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [linha["name"] for linha in linhas]


def obter_parametro(chave: str, padrao=None) -> str | None:
    """Le uma configuracao salva. Devolve `padrao` se nunca foi definida."""
    linha = consultar_um("SELECT valor FROM parametros WHERE chave = ?", (chave,))
    if linha is None or linha["valor"] is None:
        return padrao
    return linha["valor"]


def obter_parametro_num(chave: str, padrao: float = 0.0) -> float:
    """Igual ao anterior, mas ja converte para numero."""
    valor = obter_parametro(chave)
    if valor is None:
        return padrao
    try:
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def obter_parametro_pasta(chave: str, padrao) -> str:
    """Le um caminho de pasta salvo, voltando ao padrao quando ele nao existe mais.

    Caminho absoluto guardado em banco envelhece em silencio: mover a pasta do
    projeto deixa o valor apontando para um lugar que sumiu, e a tela nao
    acusa nada — ela so deixa de achar arquivo. Quando o caminho salvo nao e
    mais uma pasta, esta funcao volta ao padrao e regrava, para o proximo
    acesso ja nascer certo.

    Use so para pastas com um padrao seguro dentro do projeto. `pasta_backup`
    nao passa por aqui de proposito: um disco externo desconectado nao e
    motivo para reescrever a escolha do usuario.
    """
    salvo = obter_parametro(chave)
    if salvo and Path(salvo).is_dir():
        return salvo
    definir_parametro(chave, str(padrao))
    return str(padrao)


def definir_parametro(chave: str, valor) -> None:
    """Grava (ou sobrescreve) uma configuracao.

    O "ON CONFLICT ... DO UPDATE" e um upsert: se a chave ja existe, atualiza
    em vez de dar erro de chave duplicada.
    """
    executar(
        "INSERT INTO parametros (chave, valor) VALUES (?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
        (chave, None if valor is None else str(valor)),
    )


GRANDES_CATEGORIAS_PADRAO = [
    ("Casa",       "#4F46E5", 1),
    ("Comida",     "#F59E0B", 2),
    ("Compras",    "#EC4899", 3),
    ("Educação",   "#0EA5E9", 4),
    ("Lazer",      "#8B5CF6", 5),
    ("Veículo",    "#F97316", 6),
    ("Saúde",      "#10B981", 7),
    ("Transporte", "#14B8A6", 8),
    ("Receita",    "#22C55E", 9),
    ("Outros",     "#64748B", 10),
]

CATEGORIAS_PADRAO = [
    ("Alimentação",         "Comida",     "Despesa"),
    ("Assinaturas",         "Lazer",      "Despesa"),
    ("Casa",                "Casa",       "Despesa"),
    ("Combustível",         "Veículo",    "Despesa"),
    ("Compras",             "Compras",    "Despesa"),
    ("Contas",              "Casa",       "Despesa"),
    ("Cuidados Pessoais",   "Compras",    "Despesa"),
    ("Educação",            "Educação",   "Despesa"),
    ("Lazer",               "Lazer",      "Despesa"),
    ("Luz",                 "Casa",       "Despesa"),
    ("Pedágio",             "Veículo",    "Despesa"),
    ("Saúde",               "Saúde",      "Despesa"),
    ("Serviços",            "Casa",       "Despesa"),
    ("Serviços Domésticos", "Casa",       "Despesa"),
    ("Transporte",          "Transporte", "Despesa"),
    ("Manutenção",          "Veículo",    "Despesa"),
    ("Vestuário",           "Compras",    "Despesa"),
    ("Outros",              "Outros",     "Despesa"),
    ("Salário",             "Receita",    "Receita"),
    ("PLR",                 "Receita",    "Receita Extraordinária"),
    ("Freelance / Extra",   "Receita",    "Receita"),
    ("Reembolso",           "Receita",    "Receita"),
    ("Família",             "Outros",     "Receita"),
    ("Outras Receitas",     "Receita",    "Receita"),
    ("Investimentos",       "Outros",     "Investimento"),
    ("Desinvestimentos",    "Outros",     "Investimento"),
    ("Rendimentos",         "Receita",    "Investimento"),
    ("Transferência",       "Outros",     "Investimento"),
    ("Pagamento de Fatura", "Outros",     "Pagamento"),
]

CONTAS_PADRAO = [
    ("Conta Corrente XP", "Conta Corrente", "Banco XP S.A."),
    ("Cartão XP",         "Cartão de Crédito", "Banco XP S.A."),
]

MACROS_ATIVO_PADRAO = [
    ("Renda Fixa",      "#4F46E5", 1),
    ("Renda Variável",  "#EF4444", 2),
    ("Internacional",   "#8B5CF6", 3),
    ("Caixa",           "#10B981", 4),
    ("Outros",          "#64748B", 5),
]

CLASSES_ATIVO_PADRAO = [
    ("NTN-B (inflação)",  "Renda Fixa",      1, "NTN-B|NTNB"),
    ("Tesouro Selic",     "Renda Fixa",      2, "LFT|TESOURO SELIC"),
    ("Prefixado",         "Renda Fixa",      3, "LTN|NTN-F|PREFIXADO"),
    ("CDB / LCI / LCA",   "Renda Fixa",      4, "CDB|LCI|LCA|LC "),
    ("Debênture",         "Renda Fixa",      5, "DEBENTURE|DEB "),
    ("Fundo DI",          "Caixa",           6, "DI FIC|SIMPLES|INVESTBACK|REFERENCIADO"),
    ("Ação BR",           "Renda Variável",  7, ""),
    ("ETF",               "Renda Variável",  8, "ETF|BOVA|IVVB|SMAL|HASH"),
    ("FII",               "Renda Variável",  9, "FII|FUNDO IMOBILIARIO"),
    ("Fundo multimercado", "Renda Variável", 10, "MULTIMERCADO|MACRO"),
    ("Stock EUA",         "Internacional",  11, ""),
    ("ETF EUA",           "Internacional",  14, ""),
    ("Cripto",            "Outros",         12, "BITCOIN|ETHEREUM|CRIPTO"),
    ("Saldo em conta",    "Caixa",          13, ""),
]

NOME_CAIXA_CORRETORA = "Saldo em conta (XP)"


REFERENCIAS_CATEGORIA = [
    ("lancamentos", "categoria"),
    ("gastos_fixos", "categoria"),
    ("regras_fatura", "categoria"),
    ("regras_extrato", "categoria"),
    ("futuras_compras", "categoria"),
]

REFERENCIAS_GRANDE_CATEGORIA = [
    ("categorias", "grande_categoria"),
    ("orcamento", "grande_categoria"),
]


def _renomear_no_mapa_de_portadores(conn, antigo: str, novo: str) -> int:
    """Troca o nome da categoria dentro do JSON do mapa de portadores.

    Recebe `conn` em vez de abrir a sua propria conexao para entrar na MESMA
    transacao das outras trocas — ou o mapa poderia ficar atualizado com o
    resto revertido, que e o pior dos dois mundos.
    """
    import json

    linha = conn.execute(
        "SELECT valor FROM parametros WHERE chave = ?",
        ("portadores_categoria",)).fetchone()
    if not linha or not linha["valor"]:
        return 0
    try:
        mapa = json.loads(linha["valor"])
    except (ValueError, TypeError):
        return 0

    trocados = {k: (novo if v == antigo else v) for k, v in mapa.items()}
    quantos = sum(1 for k in mapa if mapa[k] != trocados[k])
    if quantos:
        conn.execute(
            "UPDATE parametros SET valor = ? WHERE chave = ?",
            (json.dumps(trocados, ensure_ascii=False), "portadores_categoria"))
    return quantos


def renomear_categoria(antigo: str, novo: str) -> dict:
    """Renomeia uma categoria e leva junto tudo que aponta para ela.

    Devolve quantas linhas mudaram em cada tabela, para a tela poder dizer o
    que aconteceu — "renomeei e movi 46 lancamentos" e uma frase bem melhor
    que "salvo com sucesso".

    Se o nome novo JA EXISTE, isto vira uma FUSAO: os lancamentos da antiga
    passam para a existente e a antiga e apagada. E o comportamento util
    quando voce percebe que criou duas categorias para a mesma coisa.
    """
    antigo, novo = (antigo or "").strip(), (novo or "").strip()
    if not antigo or not novo or antigo == novo:
        return {}

    mudancas: dict[str, int] = {}
    with conectar() as conn:
        destino = conn.execute(
            "SELECT nome FROM categorias WHERE nome = ?", (novo,)).fetchone()
        if destino is None:
            conn.execute(
                """INSERT INTO categorias
                   (nome, grande_categoria, natureza_padrao, ativa, ordem)
                   SELECT ?, grande_categoria, natureza_padrao, ativa, ordem
                   FROM categorias WHERE nome = ?""",
                (novo, antigo))

        for tabela, coluna in REFERENCIAS_CATEGORIA:
            cursor = conn.execute(
                f"UPDATE {tabela} SET {coluna} = ? WHERE {coluna} = ?",
                (novo, antigo))
            if cursor.rowcount:
                mudancas[tabela] = cursor.rowcount

        quantos = _renomear_no_mapa_de_portadores(conn, antigo, novo)
        if quantos:
            mudancas["mapa de portadores"] = quantos

        conn.execute("DELETE FROM categorias WHERE nome = ?", (antigo,))
    return mudancas


def _fundir_orcamento(conn, antigo: str, novo: str) -> int:
    """Soma os orcamentos que colidiriam antes de renomear. Devolve quantos somou.

    O BUG QUE ISTO EVITA — reproduzido em 2026-08-23.

    `orcamento` tem chave primaria composta `(mes, grande_categoria)`. Se as
    duas grandes categorias ja tem meta no MESMO mes, o UPDATE que renomeia
    tenta criar uma linha duplicada e o banco recusa:

        IntegrityError: UNIQUE constraint failed:
                        orcamento.mes, orcamento.grande_categoria

    Como `conectar()` faz rollback em erro, a renomeacao inteira era desfeita e
    a tela mostrava uma mensagem incompreensivel. Nao corrompia nada — mas a
    operacao ficava impossivel.

    E nao era hipotetico: ele tem 9 linhas de orcamento em 2026-09, cobrindo
    Casa, Comida, Compras, Educacao e outras. Fundir quaisquer duas falhava.

    A regra certa nao e "escolher uma das duas metas", e sim SOMAR: se voce
    fundiu duas grandes categorias, o orcamento da nova e o dos dois lados
    juntos. E o mesmo espirito da fusao de categorias, que junta os lancamentos
    em vez de escolher um.
    """
    somados = conn.execute(
        """UPDATE orcamento
              SET valor_orcado = valor_orcado + (
                  SELECT o2.valor_orcado FROM orcamento o2
                   WHERE o2.mes = orcamento.mes AND o2.grande_categoria = ?)
            WHERE grande_categoria = ?
              AND EXISTS (SELECT 1 FROM orcamento o3
                           WHERE o3.mes = orcamento.mes
                             AND o3.grande_categoria = ?)""",
        (antigo, novo, antigo)).rowcount

    conn.execute(
        """DELETE FROM orcamento
            WHERE grande_categoria = ?
              AND mes IN (SELECT mes FROM orcamento WHERE grande_categoria = ?)""",
        (antigo, novo))
    return somados


def renomear_grande_categoria(antigo: str, novo: str) -> dict:
    """Renomeia uma grande categoria e leva junto as categorias e o orcamento.

    Se o nome novo JA EXISTE, isto vira uma FUSAO — e os orcamentos dos dois
    lados sao SOMADOS mes a mes (ver `_fundir_orcamento`).
    """
    antigo, novo = (antigo or "").strip(), (novo or "").strip()
    if not antigo or not novo or antigo == novo:
        return {}

    mudancas: dict[str, int] = {}
    with conectar() as conn:
        destino = conn.execute(
            "SELECT nome FROM grandes_categorias WHERE nome = ?",
            (novo,)).fetchone()
        if destino is None:
            conn.execute(
                """INSERT INTO grandes_categorias (nome, cor, ordem)
                   SELECT ?, cor, ordem FROM grandes_categorias WHERE nome = ?""",
                (novo, antigo))
        else:
            somados = _fundir_orcamento(conn, antigo, novo)
            if somados:
                mudancas["orçamentos somados"] = somados

        for tabela, coluna in REFERENCIAS_GRANDE_CATEGORIA:
            cursor = conn.execute(
                f"UPDATE {tabela} SET {coluna} = ? WHERE {coluna} = ?",
                (novo, antigo))
            if cursor.rowcount:
                mudancas[tabela] = cursor.rowcount

        conn.execute("DELETE FROM grandes_categorias WHERE nome = ?", (antigo,))
    return mudancas


def semear_padroes() -> dict:
    """Preenche categorias/contas/parametros iniciais, se ainda nao existirem.

    Devolve um resumo do que foi inserido, para o script de setup mostrar.
    Chamar de novo depois nao duplica nada (usa INSERT OR IGNORE e so age em
    tabela vazia).
    """
    resumo = {"grandes_categorias": 0, "categorias": 0, "contas": 0,
              "macros_ativo": 0, "classes_ativo": 0}

    if contar("grandes_categorias") == 0:
        resumo["grandes_categorias"] = executar_muitos(
            "INSERT OR IGNORE INTO grandes_categorias (nome, cor, ordem) VALUES (?,?,?)",
            GRANDES_CATEGORIAS_PADRAO,
        )

    if contar("categorias") == 0:
        resumo["categorias"] = executar_muitos(
            "INSERT OR IGNORE INTO categorias "
            "(nome, grande_categoria, natureza_padrao, ordem) VALUES (?,?,?,?)",
            [(nome, gc, nat, i) for i, (nome, gc, nat) in enumerate(CATEGORIAS_PADRAO, 1)],
        )

    if contar("contas") == 0:
        resumo["contas"] = executar_muitos(
            "INSERT OR IGNORE INTO contas (nome, tipo, banco) VALUES (?,?,?)",
            CONTAS_PADRAO,
        )

    if contar("macros_ativo") == 0:
        resumo["macros_ativo"] = executar_muitos(
            "INSERT OR IGNORE INTO macros_ativo (nome, cor, ordem) VALUES (?,?,?)",
            MACROS_ATIVO_PADRAO,
        )

    if contar("classes_ativo") == 0:
        resumo["classes_ativo"] = executar_muitos(
            "INSERT OR IGNORE INTO classes_ativo "
            "(nome, macro, ordem, palavras_chave) VALUES (?,?,?,?)",
            CLASSES_ATIVO_PADRAO,
        )

    padroes = {
        "pasta_backup": str(config.PASTA_BACKUP_NUVEM_PADRAO),
        "meta_reserva_meses": "6",
        "salario_previsto": "0",
        "saldo_aplicado_inicial": "0",
        "corte_meta": "1000",
    }
    for chave, valor in padroes.items():
        if obter_parametro(chave) is None:
            definir_parametro(chave, valor)

    return resumo


def inicializar() -> dict:
    """Deixa o banco pronto para uso: cria/atualiza tabelas e semeia padroes.

    E esta a funcao que o app.py chama ao subir. Barata e idempotente
    ("idempotente" = rodar 10 vezes tem o mesmo efeito de rodar 1).
    """
    config.garantir_pastas()
    migracoes = aplicar_migracoes()
    resumo = semear_padroes()
    resumo["migracoes_aplicadas"] = migracoes
    return resumo


def id_conta(nome: str) -> int | None:
    """Descobre o id de uma conta pelo nome. Devolve None se nao existir."""
    linha = consultar_um("SELECT id FROM contas WHERE nome = ?", (nome,))
    return int(linha["id"]) if linha else None


def copia_de_seguranca_rapida() -> str:
    """Faz uma copia do arquivo .db ao lado, antes de uma operacao arriscada.

    Usada antes de restaurar backup ou apagar em massa. E o "cinto de
    seguranca": se algo der errado, o arquivo anterior esta ali.

    ELA LIMPA AS PROPRIAS COPIAS ANTIGAS, e isso nao e detalhe.

    Ate 2026-08-23 nada apagava esses arquivos: `backup.limpar_antigos()` so
    varre `financas_*.zip`. Cada copia pesa o banco inteiro (~1,9 MB), e em
    dois dias de trabalho acumularam-se **20 delas, 24 MB** — mais do que todo
    o resto do projeto somado.

    A regra geral que isso ensina: **quem cria arquivo tem de decidir quando
    ele morre.** Deixar a limpeza para "alguem depois" e como nao ter limpeza,
    porque esse alguem nunca aparece.
    """
    config.garantir_pastas()
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = config.PASTA_BACKUPS / f"antes_de_{carimbo}.db"
    if config.CAMINHO_BANCO.exists():
        shutil.copy2(config.CAMINHO_BANCO, destino)
    limpar_copias_rapidas()
    return str(destino)


def limpar_copias_rapidas(manter: int | None = None) -> int:
    """Apaga as copias `antes_de_*.db` mais antigas. Devolve quantas apagou.

    Mantem as `manter` mais recentes (padrao `config.MAX_COPIAS_RAPIDAS`).
    Elas servem para desfazer o que acabou de dar errado; passada uma semana,
    o `.zip` cobre melhor e ocupa 15 vezes menos.
    """
    manter = manter or config.MAX_COPIAS_RAPIDAS
    pasta = config.PASTA_BACKUPS
    if not pasta.is_dir():
        return 0

    copias = sorted(pasta.glob("antes_de_*.db"),
                    key=lambda caminho: caminho.stat().st_mtime, reverse=True)
    apagadas = 0
    for caminho in copias[manter:]:
        try:
            caminho.unlink()
            apagadas += 1
        except OSError:
            pass
    return apagadas
