# 13 · Moeda e cotações

Como o app lida com dinheiro que **não está em reais**, e de onde vem o câmbio.

Arquivo principal: [`financas/cambio.py`](../financas/cambio.py).
Prova automática: [`verificacao/conferir_cambio.py`](../verificacao/conferir_cambio.py).

---

## O problema

Até agosto/2026 o app inteiro pensava em reais, e isso bastava. Aí entrou a
conta internacional, com três papéis em dólar (IREN, DGXX, IRE).

Somar `R$ ····` (dólares) com `R$ ····` (reais) daria `R$ ····` de coisa
nenhuma.

**E o pior: não quebraria.** O programa não reclama, a tela não fica vermelha —
aparece um número maior, com cara de número certo. Erro que soma é o mais
perigoso que existe, porque some no meio de um total plausível.

---

## A coluna que existia e ninguém lia

`investimentos.moeda` existe desde a migração 3, de agosto/2026. Ela era
**escrita e nunca lida**: nenhum cálculo do app olhava para ela.

Era uma armadilha armada esperando o primeiro papel em dólar.

> **Lição:** guardar um dado "para quando precisar" não é preparação — é uma
> promessa que o código não cumpre. Ou o dado é usado, ou ele mente sobre estar
> pronto.

---

## A decisão central: converter UMA vez, na entrada

O app poderia converter em cada cálculo. São seis: `posicao`,
`evolucao_carteira`, `alocacao_atual`, `conciliar`, `patrimonio.evolucao` e o
rebalanceamento.

Seis lugares para lembrar são seis chances de esquecer — e o dia em que alguém
esquecesse, o app somaria dólar com real **sem quebrar**.

Então a conversão acontece num lugar só: **`salvar_saldo()`**, na hora de
gravar. O banco guarda os dois números:

```
saldo         em REAIS, é o que todo cálculo do app soma
saldo_moeda   o valor original em dólar, para a tela mostrar
cambio_usado  a taxa empregada naquele mês
```

Depois que o dado entra, **o resto do app volta a ser um app de reais.**

### Por que guardar o câmbio usado

Sem `cambio_usado`, o saldo de março só poderia ser conferido recalculando — e
a cotação de hoje não serve para conferir o passado. Com ele, dá para
reproduzir exatamente o número que estava na tela naquele mês.

---

## De onde vem a cotação

Do **PTAX do Banco Central** — a taxa oficial, publicada todo dia útil. API
pública, sem cadastro e sem chave:

```
https://olinda.bcb.gov.br/olinda/servico/PTAX/...
```

Usamos a **cotação de venda**, que é a referência de quem compra dólar e a que
a Receita usa.

### E por que não a taxa que você pagou de verdade

A taxa da corretora tem spread e IOF embutidos. No seu câmbio de 30/10/2025:

| | |
|---|---|
| PTAX venda do dia | 5,3850 |
| taxa que você pagou | 5,3928 |
| spread | **+0,15%** |
| IOF | **1,100%** exatos |
| **custo total** | **1,25% acima do PTAX** |

Essa taxa é o **custo da operação** — ela importa para saber se você fez um bom
negócio (fez: 1,25% é barato).

Mas para responder *"quanto vale hoje, em reais, o que está lá fora"*, a
referência tem de ser a taxa de mercado. Senão o seu patrimônio mudaria
conforme a corretora que você usou.

> **PTAX para avaliar quanto vale; taxa real para medir quanto custou.**

---

## Três cuidados que o código toma

### 1. Sábado não tem cotação

Nem feriado. A função anda para trás até achar um dia útil — e **devolve a data
que realmente usou**:

```python
cotacao_dolar("2026-08-22")   # sábado
# -> (5.1625, "2026-08-21")   usou sexta, e diz que usou
```

A tela pode então escrever "dólar de 21/08" em vez de fingir que tem o de hoje.

### 2. Cotação só olha para trás

Este foi um bug real, achado pela própria verificação em 23/08/2026. O "último
recurso" da busca pegava a cotação mais recente **de qualquer data**:

```python
cotacao_dolar("2019-06-15")   # a base começa em 2024-03
# -> devolvia 5,1625, a taxa de HOJE, para uma data de sete anos atrás
```

Uma cotação do futuro respondendo por uma data do passado — e `salvar_saldo`
converteria com ela, calado.

> **O que aconteceu com o dólar depois daquele dia não diz nada sobre quanto
> ele valia naquele dia.**

### 3. Sem cotação, o saldo NÃO é gravado

A escolha natural seria "sem cotação, grava o número como está". Isso faria um
saldo em dólar entrar no banco como se fosse real — e ninguém descobriria.

`salvar_saldo` levanta erro e não grava:

```
Nao consegui a cotacao de USD para 2026-08. O saldo NAO foi gravado —
gravar sem converter somaria USD com reais.
```

**Falhar alto é a única opção segura** quando a alternativa é mentir baixo.

---

## Sem internet, o app continua funcionando

Toda cotação buscada fica gravada na tabela `cotacoes`. Se a busca falhar, o
app usa a última guardada e **diz de que dia ela é**. O painel nunca deixa de
abrir por causa de rede.

A base hoje tem **625 dias** de PTAX, de março/2024 a agosto/2026 — carregada
de uma vez só, numa ida à rede.

---

## A tabela `cotacoes`

```sql
CREATE TABLE cotacoes (
    ticker      TEXT NOT NULL,      -- 'IREN', 'TASA3.SA', 'USDBRL'
    data        TEXT NOT NULL,
    fechamento  REAL NOT NULL,
    moeda       TEXT NOT NULL,
    fonte       TEXT,               -- 'yfinance' | 'ptax' | 'manual'
    obtida_em   TEXT,
    PRIMARY KEY (ticker, data)
);
```

**Preço de ação e câmbio moram na mesma tabela de propósito.** São a mesma
pergunta — *quanto vale uma unidade, neste dia* — e duas tabelas quase iguais
seriam duas chances de divergir. O dólar entra com o "ticker" `USDBRL`.

---

## O botão "Atualizar cotações"

Fica em *Investimentos → Atualizar saldos*, e só aparece quando existe algum
papel com ticker (para quem só tem Tesouro e fundo, seria ruído permanente).

Ele faz três coisas, nessa ordem:

1. busca o fechamento mais recente dos papéis com ticker;
2. atualiza o dólar (PTAX) dos últimos 15 dias;
3. **recalcula o saldo do mês** — `quantidade × cotação`.

O passo 3 é o que dá utilidade aos outros dois. Sem ele, atualizar cotações
guardaria dados que ninguém olha.

### Quem entra, e por que os outros ficam de fora

Exige as **duas** coisas:

| | |
|---|---|
| **ticker** | senão não há preço para buscar (Tesouro e fundo não têm) |
| **quantidade** | senão não há o que multiplicar |

Papel com ticker mas sem quantidade fica de fora **e é listado na tela**.
Chutar uma quantidade seria pior que não atualizar.

### O que ele não toca

`aporte` e `resgate` do mês são lidos e regravados como estavam. Eles contam
quanto dinheiro entrou e saiu **daquele papel**, e isso não se deduz de preço
nenhum — sobrescrever com zero apagaria justamente a informação que separa
rendimento de dinheiro novo.

### Sem internet

A tela avisa e não muda nada:

> Não consegui buscar cotação agora — sem internet, ou o provedor fora do ar.
> **O app continua funcionando** com as cotações já guardadas; nada foi perdido.

---

## Como conferir

```bash
.venv\Scripts\python -m verificacao.conferir_cambio
```

São **21 checagens em nove frentes**: as cotações batem com o Banco Central,
dia não útil cai para trás e informa a data, real passa direto, a gravação
converte, o saldo do passado não se mexe quando o dólar de hoje mexe, sem
cotação a gravação é recusada, `quantidade × cotação` reproduz a posição real
da corretora, preço anterior à base não vira o preço de hoje, e com a
biblioteca fora do ar nada quebra.

Ele trabalha numa **cópia descartável do banco** — nenhum teste deste projeto
pode destruir o dado que ele verifica.

---

## Cotações de papéis: `financas/cotacoes.py`

A mesma tabela guarda o preço de fechamento de ações, ETFs e FIIs. A fonte é o
**yfinance**, que lê o Yahoo Finance.

### O limite, dito sem rodeio

| Cobre | Não cobre |
|---|---|
| ações e ETFs dos EUA (`IREN`, `DGXX`, `IRE`) | **Tesouro Direto** (LFT, NTN-B) |
| B3 com sufixo `.SA` (`TASA3.SA`, `BBAS3.SA`) | **fundos** (Trend DI, Investback) |
| FIIs | qualquer coisa sem ticker público |

Tesouro e fundos continuam vindo do arquivo de posição da corretora, como
sempre. **Esta API resolve a parte internacional e a renda variável, não a
carteira inteira.**

### A ressalva da biblioteca

`yfinance` não é oficial: raspa o Yahoo e já quebrou quando o site mudou. Duas
defesas, e nenhuma é luxo:

1. tudo que é buscado fica **gravado** em `cotacoes`;
2. se a busca falhar, as funções usam o que já está guardado e **dizem de
   quando é**.

O import da biblioteca acontece **dentro da função**, não no topo do arquivo —
assim uma dependência opcional, que só serve para renda variável, não derruba o
app inteiro na hora de abrir.

---

## O que isso permitiu: reconstruir dez meses sem digitar nada

A conta internacional não exporta extrato. Mas as quantidades ficaram estáveis
desde 31/10/2025, então:

```
saldo do mês = quantidade × cotação de fechamento do último dia do mês
```

Dez meses de saldo, exatos. A prova é o mês que dá para conferir:

| | reconstruído | print do app da corretora |
|---|---|---|
| IREN | R$ ···· | R$ ···· |
| DGXX | R$ ···· | R$ ···· |
| IRE | R$ ···· | R$ ···· |
| **total** | **R$ ····** | **R$ ····** |

0,07% — um dia de pregão de diferença.

### Grupamento: por que a conta fecha mesmo assim

O IRE fez um **grupamento de 1 para 4 em 20/03/2026** (de 145 cotas para
36,25). Foram os dois "Ajuste + R$ ····" que apareceram no extrato dele.

As cotações vêm **ajustadas por split**, e é isso que salva:

> **preço ajustado × quantidade de hoje = valor correto em qualquer data
> passada** — porque o grupamento não muda o valor da posição, só em quantos
> pedaços ela está dividida.

---

## Onde mexer

| Quero… | Vá em |
|---|---|
| adicionar outra moeda (EUR) | `cambio.py` — hoje só USD tem busca; a estrutura já é genérica |
| trocar a fonte do câmbio | `buscar_ptax()` |
| ver o câmbio usado num mês | coluna `investimentos_saldos.cambio_usado` |
| cadastrar um papel em dólar | *Investimentos → Cadastro*, campo **Moeda** |
