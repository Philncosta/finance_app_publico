# 08 · Backup e nuvem

Arquivo do código: [`financas/backup.py`](../financas/backup.py)

---

## A estratégia, em uma frase

> **O banco fica local. O backup vai para a nuvem.**

```
dados/financas.db                                        ← local, rápido
dados/backups/financas_AAAA-MM-DD_HHMM.zip               ← local
CAMINHO\PARA\OneDrive\Financas_Backup\...zip        ← nuvem
```

---

## Por que não mandar o `.db` direto para o OneDrive

Porque **banco de dados aberto e sincronização automática não combinam**.

Enquanto o app roda, o SQLite mantém arquivos auxiliares (`-wal` e `-shm`) com
escritas que ainda não entraram no `.db` principal. Se o OneDrive sincronizar
o `.db` "no meio do caminho", a cópia na nuvem pode ficar inconsistente — e
você só descobre no dia em que precisar dela.

Pior: se você abrir o app em duas máquinas, o OneDrive pode gerar um arquivo
de conflito e você fica com dois bancos diferentes sem saber qual é o bom.

---

## Por que o `.zip` de CSVs é melhor

**1. É um arquivo fechado.** Depois de gravado não muda mais, então o OneDrive
nunca o pega no meio de uma escrita.

**2. É legível.** Se um dia este programa não existir mais, os seus dados
continuam abríveis no Excel — são CSVs comuns dentro de um zip. Isso importa
mais do que parece: seus dados não ficam reféns do programa.

**3. É versionado.** Cada backup tem data e hora no nome, então você pode
voltar para o estado de três semanas atrás, e não só para o último.

---

## O que tem dentro do zip

Um `.csv` por tabela, mais um `LEIA-ME.txt`:

```
grandes_categorias.csv   categorias.csv          contas.csv
parametros.csv           macros_ativo.csv        classes_ativo.csv
metas_alocacao.csv       regras_fatura.csv       regras_extrato.csv
gastos_fixos.csv         orcamento.csv           metas.csv
futuras_compras.csv      patrimonio_mensal.csv   financiamento_cenarios.csv
arquivos_importados.csv  cotacoes.csv            indices.csv

investimentos.csv               ← os papéis da carteira
investimentos_saldos.csv        ← o histórico de saldos, mês a mês
investimentos_movimentos.csv    ← o extrato da corretora
lancamentos.csv                 ← o mais importante: o histórico completo
LEIA-ME.txt
```

> **As quatro últimas entraram em 25/08/2026, e a falta delas era grave.** O
> backup levava 14 tabelas enquanto o banco tinha 22 — as oito de fora vieram
> das migrações 2, 3, 8 e 10, e ninguém voltou na lista para acrescentá-las.
> Restaurar num computador novo devolveria os lançamentos e uma tela de
> Investimentos **vazia**: 2.707 linhas, R$ ···· de carteira, que o
> backup nunca tinha visto. Nada avisava — um backup "com sucesso" continuava
> dizendo sucesso, porque uma lista-filtro só falha para o que está **fora**
> dela.

Todos usam:

| | |
|---|---|
| separador | ponto e vírgula (`;`) |
| codificação | UTF-8 |
| números | com **ponto** decimal (`1234.56`), formato internacional |
| datas | `AAAA-MM-DD` |

> Repare que os números no backup usam ponto decimal, não vírgula. É proposital:
> o backup existe para ser **restaurado por máquina**, e o formato
> internacional é o que o `float()` do Python lê sem ambiguidade. Para abrir no
> Excel, indique "ponto" como separador decimal na importação — ou use o botão
> *Baixar Excel* da tela de Lançamentos, que já sai no formato brasileiro.

O tamanho fica em torno de **37 KB** com os seus 1.073 lançamentos. CSV é texto
e comprime muito bem.

---

## A ordem das tabelas importa

Na lista `TABELAS_BACKUP` a ordem não é alfabética — é a **ordem de
dependência**:

```python
TABELAS_BACKUP = [
    "grandes_categorias", "categorias", "contas", ...,
    "investimentos", "investimentos_saldos", ...,
    "lancamentos",        # por último
]
```

`categorias` precisa existir antes de `lancamentos`, porque `lancamentos`
aponta para ela; `investimentos` antes de `investimentos_saldos`, pelo mesmo
motivo. Restaurar fora de ordem quebraria as ligações.

Na hora de **apagar** (no modo "Substituir tudo"), a ordem é **invertida** —
primeiro quem depende dos outros.

### Mas a lista decide a ORDEM, não o CONJUNTO

Esta é a parte que mudou em 25/08/2026, e ela vale como regra geral de
programação.

Uma lista escrita à mão que decide **o que entra** envelhece em silêncio: no
dia em que uma migração cria uma tabela, ela simplesmente não é copiada, e
nada falha — porque nada nunca reclama de uma tabela que você não pediu. Foi
exatamente o que aconteceu com as oito tabelas de investimento.

Por isso quem manda agora é `tabelas_em_ordem()`:

```python
conhecidas = [t for t in TABELAS_BACKUP if t in existentes]   # a ordem certa
novas      = [t for t in existentes if t not in TABELAS_BACKUP]  # o que surgiu
return conhecidas + novas
```

**A lista dá a ordem; o banco dá o conjunto.** Uma migração futura pode
esquecer de vir aqui — e o backup continua completo, com a tabela nova entrando
no fim, que é o lugar seguro (quem chega depois costuma depender de quem já
estava).

> A lição, fora deste arquivo: **quando uma lista enumera o que deve ser
> processado, pergunte o que acontece com o que ficou de fora.** Se a resposta
> for "nada, em silêncio", a lista está no lugar errado da decisão.

---

## Quando o backup acontece

- **Automaticamente**, ao final de toda importação (a caixinha "Gerar backup
  depois de importar" vem marcada).
- **Manualmente**, em *Configurações → Backup → Fazer backup*.

Os **30 mais recentes** são mantidos; os mais antigos são apagados sozinhos.
Sem isso, um backup por importação viraria centenas de arquivos em alguns
meses.

---

## Restaurar

Em *Configurações → Backup e restauração*.

**Antes de mexer em qualquer coisa**, o app copia o banco atual para
`dados/backups/antes_de_AAAAMMDD_HHMMSS.db`. Se a restauração trouxer um
resultado inesperado, o estado anterior está guardado.

Há dois modos:

| Modo | O que faz |
|---|---|
| **Substituir tudo** | apaga o conteúdo atual e põe o do backup (o normal) |
| **Juntar com o atual** | acrescenta o que faltar, ignorando duplicatas |

O "juntar" é útil para consolidar dados de duas máquinas: você importou
faturas no computador e o extrato no notebook, e quer os dois no mesmo lugar.

Para confirmar, é preciso digitar `RESTAURAR` — uma trava contra clique
acidental.

---

## Trocar a pasta da nuvem

Em *Configurações → Backup*, no campo "Pasta na nuvem". Serve qualquer pasta
que o seu computador sincronize: OneDrive, Google Drive, Dropbox.

Se a pasta não existir, ela é criada no primeiro backup. Se o caminho estiver
errado ou o drive desconectado, **o backup local acontece do mesmo jeito** — só
a cópia na nuvem é pulada, e a tela avisa.

---

## "Posso copiar a pasta toda para a nuvem?"

**Pode — mas exclua a `.venv`.** Ela sozinha é 427 MB dos 433 MB da pasta.

| | Tamanho |
|---|---|
| Pasta inteira | 433 MB |
| **Sem a `.venv`** | **6,4 MB** |
| Só a `.venv` | 427 MB (98,5%) |

### Por que a `.venv` não deve ir junto

**Ela é recriável em um comando.** São bibliotecas baixadas da internet, não
dados seus:

```bash
python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt
```

**E, pior, ela guarda caminhos absolutos.** Copiada para outra pasta ou outro
computador, simplesmente não funciona — os atalhos dentro dela ainda apontam
para o caminho antigo. Copiar é gastar 427 MB por algo que não serve.

### Um cuidado: feche o app antes de copiar

Enquanto o app está rodando, o SQLite mantém arquivos auxiliares (`.db-wal`,
`.db-shm`) com escritas que ainda não entraram no `.db` principal. Copiar
nesse momento pode levar uma cópia incompleta.

**Feche o app** (a janela preta) antes de copiar a pasta. Ou, melhor, use o
`.zip` de backup, que já é um arquivo fechado e imune a isso.

### As três formas, comparadas

| Forma | Tamanho | Quando usar |
|---|---|---|
| **O `.zip` de backup** | ~40 KB | o dia a dia — automático a cada importação |
| A pasta sem a `.venv` | 6,4 MB | levar o projeto para outro computador |
| A pasta inteira | 433 MB | nunca — a `.venv` não funciona fora do lugar |

> **A regra por trás disso:** não copie o que é **recriável** nem o que é
> **grande**. Copie o que você não consegue refazer. O arquivo `.gitignore` na
> raiz do projeto é exatamente essa lista, com o porquê de cada item.

---

## Levar o app para outro computador

1. Copie a pasta `finance_app` inteira (ou só o `financas.db` e os arquivos de
   código — a `.venv` é recriável).
2. No computador novo, recrie o ambiente:

```bash
cd caminho\para\finance_app && python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt
```

3. Duplo clique em `iniciar.bat`.

Se você só tem o `.zip` de backup, comece um banco vazio e restaure por
*Configurações → Restaurar*.

---

## Testar a restauração (vale fazer uma vez)

Backup que nunca foi testado não é backup — é esperança. Um teste seguro:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import backup; info = backup.criar(sufixo='teste'); print(info); print(backup.conteudo(info['caminho_local']))"
```

Isso gera um backup e mostra quantas linhas de cada tabela ele contém. Se o
número de `lancamentos` bater com o que o app mostra, o backup está íntegro.

---

## Uma coisa que o backup **não** faz

Ele não guarda os arquivos originais (`Fatura2026-01-05.csv` e companhia). Se
você quiser mantê-los, a pasta `arquivos_originais/` foi criada para isso —
mas eles não são necessários: tudo que estava dentro deles já está no banco e,
portanto, no backup.

---

## Dois tipos de backup, e por que os limites são diferentes

O app cria **duas** coisas, e confundi-las custa disco:

| | serve para | tamanho | quantos ficam |
|---|---|---|---|
| `financas_*.zip` | o backup de verdade — vai para a nuvem, abre no Excel | ~125 KB | 30 |
| `antes_de_*.db` | desfazer o que **acabou** de dar errado | ~1,9 MB | **5** |

O `.zip` é um retrato em CSV: pequeno, legível, e funciona mesmo se um dia este
programa não existir. O `.db` é uma cópia crua, feita por
`banco.copia_de_seguranca_rapida()` antes de restaurar um backup, apagar em
massa ou recarregar a migração — o cinto de segurança da operação seguinte.

### O que deu errado, e a regra que ficou

Até 2026-08-23, **nada apagava os `.db`**. `backup.limpar_antigos()` só varre
`financas_*.zip`, e as cópias cruas se acumulavam para sempre. Em dois dias de
trabalho: **20 arquivos, 24 MB** — mais do que o código, os documentos, os
extratos e as faturas somados.

A correção não foi apagar os arquivos (isso é o sintoma). Foi fazer a função
que os **cria** ser a que os **limita**.

> **Quem cria arquivo tem de decidir quando ele morre.** Deixar a limpeza para
> "alguém depois" é o mesmo que não ter limpeza — esse alguém nunca aparece.

Para limpar à mão a qualquer momento:

```bash
.venv\Scripts\python -c "from financas import banco; print(banco.limpar_copias_rapidas(), 'apagadas')"
```
