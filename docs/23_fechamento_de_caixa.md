# 23 · Fechamento de caixa — o dinheiro não some no meio do caminho

> **O pedido que originou isto**
>
> "Tenho 2 contas, uma corrente e outra de investimentos dentro do banco XP.
> (…) Além disso, tenho também a conta global, que tem os investimentos e a
> conta corrente em dólar. Essas 3 contas + o que tenho investido precisam
> conversar, **não pode haver dinheiro sumindo no meio do caminho**."

Este documento cobre o que foi feito: fazer o app ser capaz de *dizer* quando
não sabe, em vez de empurrar a sobra para "rendimento". A parte da conta global
em dólar foi deixada de lado a pedido dele — o porquê está no fim.

---

## O buraco, com nome, data e valor

No extrato da conta de investimentos:

```
2026-09-02   TED - RECEBIMENTO EXTERNO   +R$ ····
```

Dinheiro entrando **de fora, direto na corretora**. Não passou
pela conta corrente. O leitor do extrato não tinha regra para essa descrição e
o classificou como `outro` — que era o balde silencioso.

O problema não estava no leitor. Estava em `conciliar()`:

```python
diferenca = carteira − aportado − abertura      # e chamava isso de rendimento
```

`aportado` vinha de `fluxo_externo_mensal()`, que só soma `aporte` e `resgate`.
Os R$ ···· não contavam como dinheiro que entrou — então apareciam
inteiros na `diferenca`, ou seja, **como lucro de investimento**.

Não é um erro de cálculo. É o modelo assumindo que só existem dois caminhos
para o dinheiro cruzar a fronteira: conta corrente → corretora e a volta.
Enquanto isso foi verdade, a conta fechava. No dia em que surgiu um terceiro
caminho, a sobra foi para a única gaveta que existia.

---

## A equação

```
saldo_inicial + entradas − saidas + rendimento + cambio − custos
+ nao_explicado = saldo_final
```

**`nao_explicado` é calculado por diferença e sempre exibido, nunca
absorvido.** É a mudança de fundo. Uma sobra empurrada para "rendimento" é uma
sobra que não existe — e um número que ninguém pode conferir.

### Em que componente cada movimento entra

Sai do `tipo_movimento`, por tabela (`COMPONENTE_DO_TIPO`):

| Tipo | Componente | Por quê |
|---|---|---|
| `aporte`, `resgate` | **interna** | anda entre as suas contas; soma zero no total |
| `juros`, `dividendo`, `rendimento` | **rendimento** | a carteira produziu |
| `imposto`, `taxa` | **custo** | saiu para fora e não volta |
| `compra`, `venda` | **nenhum** | só troca a *forma* do dinheiro dentro da mesma conta |
| `outro` | *depende* | é o que a triagem resolve |

Comprar um papel não é dinheiro entrando nem saindo: R$ ···· de caixa viram
R$ ···· de NTN-B. Se compra contasse como saída, todo mês com aporte grande
apareceria como um mês de perda.

---

## A triagem: o app pergunta em vez de chutar

`TED - RECEBIMENTO EXTERNO` pode ser uma venda, uma herança ou um reembolso
grande. O texto não decide. Adivinhar erraria em silêncio — que é exatamente o
defeito que estamos consertando, só que com outra roupa.

Então o app **pergunta**, em *Investimentos → Manutenção → Movimentações*.
Cada pendência recebe uma natureza:

| Resposta | Efeito |
|---|---|
| dinheiro que entrou de fora (receita) | soma em `entradas` |
| dinheiro que saiu para fora (despesa) | soma em `saidas` |
| transferência entre contas minhas | soma em `interna`, e o total não muda |

Enquanto a pendência existir, o valor aparece em `nao_explicado`, a situação da
carteira vira **"há dinheiro sem explicação"** e uma tarja avisa no topo da aba
Carteira — antes de qualquer número bonito.

### Deriva o que dá, guarda o que não dá

`natureza` só é gravada para o que o `tipo_movimento` **não** explica, e só é
lida depois dele:

```python
componente = COMPONENTE_DO_TIPO.get(tipo)
if componente:
    return componente          # o tipo manda
return NATUREZAS.get(natureza) # a triagem só responde pelo resto
```

A ordem não é detalhe. Se `natureza` fosse consultada primeiro, uma resposta
antiga de triagem passaria por cima de uma regra nova — o mesmo erro de
guardar aquilo que se deriva, agora com efeito retroativo.

Foi por isso que a migração 23, que gravava `natureza = 'interna'` para todo
`aporte`/`resgate`, foi desfeita pela migração 24. Aquilo era uma segunda fonte
de verdade para um fato que o tipo já dizia.

---

## O segundo erro, que só apareceu porque fomos olhar

Consertado o primeiro, os dois medidores de rendimento **discordaram mais**, e
não menos. Isso é sinal de que havia outra coisa.

O app mede rendimento por dois caminhos independentes:

- **de cima:** `carteira − aportado − abertura`
- **de baixo:** a soma do rendimento apurado papel a papel, mês a mês

Eles discordavam em **R$ ····** — que é, ao centavo, o fluxo líquido de
setembro (+269,00 de aporte, −R$ ···· de resgate).

A causa: **os dois lados da balança eram de meses diferentes.** `posicao()`
devolve a carteira até o último saldo *cadastrado* (2026-08); o fluxo somava
até onde houvesse *extrato* (2026-09). Um patrimônio de agosto comparado com
transferências de setembro.

Isso passou despercebido por anos porque o número errado era plausível. Só uma
checagem automática pega esse tipo de defeito — e a do app (`conferir_indices`,
checagem 8) **já estava falhando**; ninguém tinha rodado.

A correção: `mes_referencia` nunca passa do último mês da carteira.

```python
mes_referencia = mes
if ultimo_da_carteira and (not mes_referencia
                           or mes_referencia > ultimo_da_carteira):
    mes_referencia = ultimo_da_carteira
```

O teto importa porque **hoje é setembro**: o Dashboard pede o mês corrente, e
sem ele o caminho mais usado do app seria justamente o quebrado.

Alinhados, os dois medidores passam a bater **ao centavo** em todos os meses.

---

## O que `conciliar()` devolve agora

Continua devolvendo tudo o que devolvia — as telas não quebram — e ganha:

| Chave | O que é |
|---|---|
| `entrou_de_fora` | entradas − saídas externas já triadas, até o mês de referência |
| `nao_explicado` | o que ainda não tem explicação **dentro** do mês de referência |
| `n_a_triar` | quantas pendências existem, **de qualquer mês** |
| `valor_a_triar` | quanto somam, em módulo |
| `mes_referencia` | de que mês é a foto que a conta usou |

`nao_explicado` e `valor_a_triar` são separados de propósito. O primeiro entra
na equação e por isso respeita o mês; o segundo é a lista de trabalho e não
respeita. Os R$ ···· caem num mês que a carteira ainda não alcança — somar
os dois num número só esconderia justamente o caso que motivou tudo isto.

---

## A prova

`verificacao/conferir_fechamento.py`, 74 checagens:

```
.venv\Scripts\python -m verificacao.conferir_fechamento
```

1. **O tipo manda** — inclusive o caso travado: `aporte` com
   `natureza = "entrada_externa"` continua sendo interna.
2. **Sem resposta, aparece** — não classificado vai *inteiro* para a sobra, e
   não pode virar rendimento nem ser adivinhado como entrada.
3. **Triado, sai da sobra** — nas três naturezas.
4. **Interna soma zero** — e uma ponta sozinha **tem** de deixar resto; sem
   esse contraste, um `somar()` que devolvesse zero para tudo passaria na
   checagem anterior sem fazer nada.
5. **Comprar só troca a forma** — R$ ···· operados, zero de efeito.
6. **Os dois medidores batem** — em seis meses, incluindo dois posteriores ao
   último saldo, e pedir 2027-12 não inventa uma carteira mais nova.
7. **O caso real** — os R$ ···· estão na fila, não no rendimento. Escrita
   sobre o banco de verdade: se alguém "arrumar" o app de um jeito que engula
   essa quantia de novo, é aqui que aparece.
8. **Resposta inválida não grava.**
9. **O espelho** — entrada externa vira lançamento com a natureza vinda da
   categoria; triar duas vezes não duplica; retriar como interna **apaga** o
   espelho; e uma categoria inválida não deixa meia gravação.
10. **A categoria combina com o sentido** — entrada só recebe receita, saída só
    despesa, e nenhuma categoria serve aos dois.
11. **Indenização é isenta** — e a nota avisa que verba salarial da mesma
    origem não é.
12. **A tabela lida como a tela lê** — os casos de borda do botão, incluindo
    o `NaN` de célula vazia.
13. **O sinal do extrato manda** — resposta que contradiz a direção é recusada,
    sem deixar meia gravação; e a saída legítima (valor negativo) passa.
14. **Lançamento apagado devolve o movimento para a fila** — com o motivo, o
    dinheiro voltando a `não explicado`, e a interna não sendo cobrada por um
    espelho que ela nunca deveria ter.

A separação entre `somar()` (pura) e `por_componente()` (lê o banco) existe
para isto: um teste que só consegue olhar os dados de verdade só descobre os
erros que já aconteceram. Com `somar()`, dá para provar a regra da saída
externa mesmo sem nunca ter tido uma.

---

## A conta global ficou de fora, de propósito

O plano previa ler o extrato da XP Investments US e trazer o caixa em dólar.
**Ele pediu para pular** (03/09/2026):

> "Essa etapa 3 pode pular, não tenho saldo lá ainda, só na conta de
> investimento mesmo."

A decisão é coerente com o extrato: o `Cash Balance` de lá é **R$ ····**. Ler
um PDF por mês para acompanhar dezesseis dólares seria trabalho sem retorno, e
código que não se usa é código que apodrece sem ninguém notar.

O que **fica sabendo-se que fica**: as três posições em dólar (IREN, DGXX, IRE)
continuam na carteira e valem 13,4% dela. O rendimento delas ainda mistura
variação de preço com variação de câmbio num número só — quando isso passar a
incomodar, a decomposição é

    efeito_preco  = (valor_fim_usd − valor_ini_usd) × ptax_ini
    efeito_cambio = valor_fim_usd × (ptax_fim − ptax_ini)

com o termo cruzado indo para o câmbio, explicitamente. Toda a infraestrutura
de PTAX já existe em [`cambio.py`](../financas/cambio.py).

A conta `XP Investments US` (id 4, moeda USD) **foi criada e ficou**, sem uso
por enquanto. Ela é verdade sobre as contas dele; apagá-la seria uma migração
para desfazer outra migração, e ela não custa nada parada.

## O dinheiro que entrou de fora também vira lançamento

Ele perguntou o óbvio, e não havia resposta boa:

> "Como os 5k que entraram foi receita extra, por que não entra para os
> lançamentos?"

Porque são **dois mundos que não se falavam**. `lancamentos` só nascia do
extrato da conta corrente e da fatura; `investimentos_movimentos` vem do
extrato da corretora. Os R$ ···· nunca tocaram a conta corrente — nenhum
leitor jamais os viu.

O estrago era visível em setembro/2026:

| | |
|---|---|
| Receitas nos lançamentos | R$ ···· |
| A despesa paga com esse dinheiro, R$ ···· | contava como **despesa** |
| A receita de R$ ···· que os pagou | **não existia** |

O mês parecia cinco mil pior do que foi.

Agora, triar como entrada ou saída externa **cria um lançamento-espelho**, e a
tela pede a categoria — porque é ela que decide a ficha do imposto, e essa
escolha é sua.

### As três regras que sustentam isso

**Transferência interna não vira lançamento.** É o que impede contar o mesmo
dinheiro duas vezes: quando ele anda entre as suas contas, a outra ponta já
está no extrato da conta corrente — os R$ ···· que ele sacou da corretora
já estão lá como `Transferência`. E se você mudar de ideia e retriar como
interna, o espelho **some**; não fica órfão.

**A origem é `Corretora`, não `Manual`.** `Manual` quer dizer "você digitou".
O campo `origem` existe justamente para você saber de onde o número veio;
mentir nele é barato de fazer e caro de descobrir.

**O `id_unico` é `corretora:` + o do movimento.** Estável: reimportar o extrato
não duplica, e triar duas vezes atualiza a mesma linha em vez de criar outra.

### Indenização é isenta, e a nota diz o resto

Ele confirmou que, no caso dele, era receita **não tributável**.

A categoria `Indenização` (migração 25) cai na ficha **Rendimentos Isentos e
Não Tributáveis**. O nome foi escolhido para o mapeamento ser verdadeiro por
construção — indenização repõe uma perda, não acrescenta patrimônio.

Mas a nota da ficha avisa do que costuma vir junto: se a mesma origem pagou
salário atrasado, férias ou 13º, **essa parte é tributável** e pertence a outra
categoria. Sem esse aviso, o nome viraria uma isenção automática que ninguém
conferiu — e erro de declaração só aparece depois de entregue.

### O bug que apareceu ao escrever a prova

A primeira versão de `triar()` gravava a natureza e **só depois** olhava a
categoria. Com uma categoria inválida o erro subia, mas o movimento já tinha
saído da fila de triagem: sumia da tela como se estivesse resolvido, e sem
lançamento nenhum do outro lado. **Meia triagem gravada é pior que nenhuma,
porque parece que deu certo.**

Agora valida tudo antes de gravar qualquer coisa, e a checagem 9 olha o
**estado depois do erro**, não só o erro.

### Três defeitos que só apareceram porque fomos procurar

Depois de tudo pronto, valia perguntar o que ainda podia dar errado. Deu três.

**O sinal podia contradizer o extrato.** Marcar a entrada de +R$ ···· como
"saiu para fora" produzia uma **despesa de valor positivo** — linha incoerente,
que soma no mês em vez de subtrair. Dava para "consertar" invertendo o sinal
sozinho, mas aí o app inventaria uma despesa de cinco mil que nunca existiu.
Quem sabe a direção do dinheiro é o extrato; a sua resposta diz de *onde* ele
veio, não para que lado foi. Quando os dois se contradizem, o app **recusa** e
explica:

```
o extrato diz que esse dinheiro entrou (R$ ····),
e a resposta diz o contrário — «dinheiro que saiu para fora (despesa)»
```

E a saída legítima, com valor negativo, continua funcionando — senão a trava
teria virado uma proibição geral.

**Apagar o lançamento fazia o dinheiro sumir em silêncio.** A tela de
Lançamentos deixa apagar qualquer linha, e Configurações deixa apagar todas.
Apagando o espelho, o movimento continuava marcado como triado: sumia da fila,
sumia da receita do mês, e nada avisava. Era o mesmo "dinheiro sumindo no meio
do caminho" que este módulo existe para impedir — só que criado por nós.

Agora um movimento externo sem o seu lançamento **volta para a fila**, o
dinheiro volta a ser `não explicado`, e a coluna **Por quê** distingue os dois
casos:

| Motivo | O que houve |
|---|---|
| nunca classificado | o app não teve regra e você ainda não respondeu |
| o lançamento foi apagado | você já respondeu, mas o lançamento que provava isso não existe mais |

**Lançamento órfão.** Se o movimento da corretora for apagado, o espelho
sobrevive apontando para o nada. Nenhuma tela apaga `investimentos_movimentos`
— só dá para chegar nisso por SQL direto — então fica registrado aqui em vez de
virar código que nunca roda.

### E um quarto defeito, que só apareceu quando ele usou

Ele classificou os R$ ···· de verdade. No mesmo instante, **uma checagem
falhou e outra parou de provar qualquer coisa**:

```
x antes de triar nao pode existir lancamento espelho
  "a fila esta vazia — tudo ja triado"
```

As checagens que usavam o caso real liam o banco **supondo** que o movimento
ainda estava na fila. Isso vale enquanto o recurso não é usado — ou seja, um
teste que se desliga sozinho no minuto em que o app começa a funcionar.

Agora cada checagem **monta o estado de que precisa** (`repor_na_fila`) dentro
da cópia descartável, em vez de torcer para encontrá-lo. E a 7 ganhou a outra
metade: classificado, a situação **tem** de deixar de acusar — senão o aviso
ficaria aceso para sempre e viraria ruído.

### E o que já estava certo

Conferido medindo **todas as telas antes e depois** da triagem, numa cópia do
banco. Mudaram exatamente quatro coisas, todas as pretendidas:

```
receita do mês         320,00 -> R$ ····    +R$ ····
receita recorrente     320,00 ->   320,00         0,00   (extraordinária não infla a previsão)
patrimônio total   R$ ···· -> R$ ····       0,00   (SEM dupla contagem)
saldo aplicado     R$ ···· -> R$ ····       0,00
rendimento apurado   R$ ···· -> R$ ····         0,00   (não vaza para o investimento)
IR tributável      R$ ···· -> R$ ····       0,00
IR isento                0,00 -> R$ ····    +R$ ····
```

A dupla contagem no patrimônio era o risco mais sério, porque o dinheiro está
ao mesmo tempo no lançamento e na carteira. Não acontece: `saldo em conta` vem
de `saldo_apos` do extrato da conta corrente (`origem = 'Extrato'`, e o espelho
é `origem = 'Corretora'`), e `saldo aplicado` acumula só lançamentos de
natureza `Investimento`.

E reimportar o extrato da corretora **não apaga a triagem** — o `INSERT OR
IGNORE` preserva a linha que já existe, com a sua resposta.

### E a leitura da tabela saiu da tela

A lógica do botão "Classificar" morava dentro do `if st.button(...)`, onde
script nenhum alcança. Virou `fechamento.ler_triagem()`, e os casos de borda
passaram a ser conferidos: categoria em branco, categoria do sentido errado,
interna com categoria preenchida, e a célula vazia que o pandas devolve como
`NaN` — que sem tratamento viraria a categoria literal `"nan"`.

## O que ainda não está feito

- **A equação por conta.** `fechar(mes, conta)` — uma linha por conta e uma do
  total, com as transferências internas somando zero entre elas. Hoje a
  equação existe e é conferida para a carteira inteira, não conta a conta.
- **`moeda` não aparece na tela de contas.** A coluna existe no banco e o
  editor em *Configurações → Contas* não a mostra. Não quebra nada (o `INSERT`
  cai no `DEFAULT 'BRL'` e o `UPDATE` não a toca), mas duas das quatro contas
  agora têm moeda que importa.

Ver também: [11_investimentos.md](11_investimentos.md),
[13_moeda_e_cotacoes.md](13_moeda_e_cotacoes.md),
[10_glossario.md](10_glossario.md).
