# 12 · Carteira e rebalanceamento por aporte

Arquivos do código:
[`financas/leitores/posicao_xp.py`](../financas/leitores/posicao_xp.py) ·
[`financas/leitores/extrato_xp_xlsx.py`](../financas/leitores/extrato_xp_xlsx.py) ·
[`financas/calculos/investimentos.py`](../financas/calculos/investimentos.py) ·
[`verificacao/conferir_rebalanceamento.py`](../verificacao/conferir_rebalanceamento.py)

Este documento continua o [11 · Investimentos](11_investimentos.md), que
explica a carteira cadastrada à mão. Aqui é a parte que veio depois: importar a
carteira da corretora e decidir para onde mandar o aporte do mês.

---

## O problema que isto resolveu

A tela de Investimentos existia, mas a carteira estava **vazia**. Ninguém ia
digitar 7 aplicações todo mês — e sem os saldos, metade da tela não servia
para nada.

Pior: o app achava que você tinha **R$ ····** aplicados, porque só conhecia o
que saiu da conta corrente em 2026. A carteira de verdade tinha
**R$ ····**. A diferença de R$ ···· era dinheiro aplicado antes de
janeiro, mais o rendimento acumulado — coisas que o extrato da conta corrente
não tem como saber.

A corretora exporta os dois arquivos que faltavam. Com eles, acompanhar a
carteira deixou de ser digitação e virou importação.

---

## Os dois arquivos novos

| Arquivo | O que traz | Vira o quê |
|---|---|---|
| `PosicaoDetalhada.xlsx` | quanto cada papel vale hoje | saldo da carteira |
| `Extrato 12345678 ….xlsx` | compras, juros, IRRF, aportes | movimentações |

Os dois entram pela tela **Importar**, a mesma de sempre. Não ganharam tela
própria de propósito: a máquina de prévia, deduplicação, histórico e backup
automático já existia e já estava testada. Duplicá-la seria criar um segundo
lugar para o mesmo defeito aparecer.

### As três armadilhas do arquivo de posição

**1. As colunas mudam de bloco para bloco.**

```
Fundos:   Posição | % Alocação | Rent. Líquida | Rent. Bruta | Valor aplicado | Valor líquido
Tesouro:  Posição | % Alocação | Total aplicado | Qtd.       | Disponível     | Vencimento
```

Ler por posição fixa daria "Rentabilidade Líquida = 15/08/2060" no bloco do
Tesouro. Por isso o leitor **remonta o mapa de colunas a cada subcabeçalho** e
usa esse mapa só até o próximo bloco.

**2. O rótulo do bloco não diz o indexador de verdade.**

No arquivo de 22/08, `NTN-B ago/2060` e `LFT mar/2031` aparecem no **mesmo**
bloco rotulado "Pós-Fixado". Mas a NTN-B é indexada à **inflação** e a LFT à
**Selic** — são classes diferentes, com riscos diferentes. No arquivo histórico
de 31/07, os mesmos papéis vêm em dois blocos separados e rotulados
corretamente.

Ou seja: o rótulo depende de como a corretora agrupou naquele dia. Por isso a
classe sai do **nome do papel**, que não muda.

**3. A linha de totais parece um ativo.**

```
r4   R$ ···· | R$ ···· | R$ ···· | ...
```

Lida sem cuidado, ela vira um "ativo" chamado `R$ ····` valendo
R$ ···· — e a carteira aparece com o dobro do tamanho. O leitor só aceita
linha de ativo **depois** de ter visto um subcabeçalho, o que descarta essa.

E repare na diferença entre os dois números do topo:

```
patrimônio (R$ ····) = total investido (R$ ····) + saldo em conta (22,74)
```

Quem tem de bater com a soma dos ativos é o **total investido**, não o
patrimônio.

### A armadilha do extrato

Depois das movimentações realizadas, o arquivo abre uma **segunda seção**
chamada *Lançamentos futuros*, com cabeçalho igualzinho ao primeiro. São
compras agendadas, que ainda não aconteceram. Nos seus arquivos ela veio vazia,
mas num mês com compra programada não viria — e sem parar ali, o leitor somaria
dinheiro que ainda não saiu.

---

## Classes de ativo: dois níveis

Espelha a estrutura das categorias de gasto, de propósito — é o padrão que você
já conhece:

```
grandes_categorias / categorias   <->   macros_ativo / classes_ativo
```

| Macro | Classes |
|---|---|
| **Renda Fixa** | NTN-B (inflação), Tesouro Selic, Prefixado, CDB/LCI/LCA, Debênture |
| **Renda Variável** | Ação BR, ETF, FII, Fundo multimercado |
| **Internacional** | Stock EUA |
| **Caixa** | Fundo DI |
| **Outros** | Cripto |

Cada classe tem uma lista de **palavras-chave** separadas por `|`. A primeira
classe cuja palavra apareça no nome do papel vence:

| Papel | Casa com | Classe |
|---|---|---|
| `NTN-B ago/2060` | `NTN-B` | NTN-B (inflação) |
| `NTNB PRINC ago/2032` | `NTNB` | NTN-B (inflação) |
| `LFT mar/2031` | `LFT` | Tesouro Selic |
| `Trend DI FIC RF Simples RL` | `DI FIC` | Fundo DI |
| `Trend Investback V` | `INVESTBACK` | Fundo DI |

**Stock EUA fica sem palavra-chave de propósito.** Não existe padrão no nome de
uma ação americana que a identifique — `AAPL` e `MSFT` não têm nada em comum
além de serem curtos. Essa classe é atribuída à mão, na tela de Cadastro.

**Ação BR tem uma regra**, e é uma regra de verdade, não um chute: o formato do
ticker da B3.

```
4 letras + 3, 4, 5 ou 6   ->  ação      (TASA3, PETR4, VALE3, ITUB4)
4 letras + 11             ->  AMBÍGUO
```

O `11` ficou de fora porque serve para três coisas diferentes ao mesmo tempo —
FII (`HGLG11`), ETF (`BOVA11`) e unit de ação (`TAEE11`). Errar aí estraga o
rebalanceamento sem avisar. Os ETFs mais comuns já são pegos pelas
palavras-chave; o resto você classifica na tela, uma vez só.

---

## A foto é completa: o que sumiu foi vendido

`posicao()` **repete o último saldo conhecido** quando um mês não tem dado.
Essa regra nasceu para o caminho manual e está certa lá: um CDB que você
esqueceu de anotar não virou pó.

Com o arquivo da corretora ela vira um erro. A posição é uma **foto completa** —
o "Total investido" bate com a soma dos ativos listados. Se um papel não está
nela, ele vale zero.

Quando as 8 posições de 2026 entraram, a carteira somou R$ ···· contra os
R$ ···· do arquivo. A diferença eram dois papéis vendidos que continuavam
sendo contados: `TASA3` (saiu em junho, R$ ····) e
`Trend Investback FIC FIRF Simples RL` (saiu em abril, R$ ····).

Hoje, ao importar uma posição, quem sumiu da foto recebe **saldo zero** naquele
mês, com o último saldo conhecido lançado como resgate. Não sabemos o preço
exato da venda, e usar o último saldo faz o rendimento daquele mês dar zero para
o papel — melhor que inventar um lucro ou um prejuízo que não houve.

**Só é zerado quem é acompanhado por importação** (tem algum saldo gravado por
esse caminho). O que você cadastra e atualiza à mão nunca é zerado por um
arquivo da corretora, que nem enxerga esse ativo. É o que protege o stock pick
dos EUA quando ele entrar.

---

## A conferência que os dois arquivos fazem um do outro

Posição e extrato são fontes **independentes**. Isso permite uma checagem forte:

```
variação da carteira no mês  −  fluxo externo (aporte/resgate)  =  rendimento
```

Se as duas fontes discordassem, essa conta daria um rendimento absurdo em algum
mês. Nos 8 meses de 2026 ela fecha, com R$ ···· de rendimento no período.

Os meses negativos (mai −R$ ···· jun −R$ ····) são marcação a mercado das NTN-B
longas — a `NTN-B ago/2060` sozinha está em −11,97% no ano. Normal para um
título de 34 anos de prazo, e irrelevante se você levar ao vencimento.

---

## O rebalanceamento, passo a passo

**A regra que decidiu o desenho: nunca sugerir venda.** Vender realiza imposto
sobre o ganho e, no caso da NTN-B, expõe você à marcação a mercado. Como existe
aporte mensal, dá para corrigir só comprando. Leva mais tempo e custa menos.

A conta:

```
1. total_novo = o que você tem hoje + o aporte deste mês
2. para cada classe:  ideal = meta% × total_novo
3. falta = ideal − saldo_atual, e o que for negativo vira zero
4. o aporte é dividido proporcionalmente ao que falta
```

Repare no passo 2: o ideal é calculado sobre o total **depois** do aporte. Sem
isso você persegue um alvo que se move, porque o próprio aporte muda o
denominador.

### Exemplo com a sua carteira

Carteira de R$ ···· aporte de R$ ···· metas de exemplo:

| Classe | Saldo | % hoje | Meta | Falta | **Aportar** | % depois |
|---|---|---|---|---|---|---|
| NTN-B | R$ ···· | 54,0% | 35% | — | R$ ···· | 52,6% |
| Fundo DI | R$ ···· | 26,2% | 10% | — | R$ ···· | 25,5% |
| Tesouro Selic | R$ ···· | 19,8% | 15% | — | R$ ···· | 19,3% |
| ETF | R$ ···· | 0,0% | 20% | R$ ···· | **R$ ····** | 1,3% |
| Ação BR | R$ ···· | 0,0% | 10% | R$ ···· | **R$ ····** | 0,6% |
| Stock EUA | R$ ···· | 0,0% | 10% | R$ ···· | **R$ ····** | 0,6% |

As três classes acima da meta não recebem nada; elas se corrigem sozinhas
porque o total cresce em volta delas.

---

## A coisa que parece erro e não é

Você vai ver, de vez em quando, uma classe que estava **quase na meta ficar
mais longe** depois do aporte:

| Classe | Saldo | Meta | Antes | Recebe | Depois |
|---|---|---|---|---|---|
| C1 | 44,00 | 45% | 44,0% | 1,02 | **40,9%** |
| C2 | 1,00 | 45% | 1,0% | 8,98 | 9,1% |
| C3 | 55,00 | 10% | 55,0% | 0,00 | 50,0% |

A C1 **recebeu dinheiro e caiu** de 44% para 40,9%. O motivo é que percentual é
uma divisão: o aporte aumenta o bolo inteiro (o denominador) ao mesmo tempo em
que enche cada fatia. Quem estava quase na meta e é enchido devagar perde para
a diluição; quem estava muito atrás é enchido rápido.

Não é defeito — é o preço de não vender nada. E olhe o conjunto: a soma das
distâncias até a meta caiu de **90 para 80 pontos**. A carteira inteira se
aproximou, que é o que importa. No mês seguinte a C1 é atendida.

### Por isso a garantia testada é sobre a carteira toda

O primeiro teste que escrevi dizia *"nenhuma classe termina mais longe da meta
do que estava"*. Ele **falhou**, e falhou com razão — pelo motivo acima.
Prometer isso deixaria o teste bonito e mentiroso.

As garantias verdadeiras, conferidas em
[`verificacao/conferir_rebalanceamento.py`](../verificacao/conferir_rebalanceamento.py):

| # | Garantia |
|---|---|
| 1 | a soma distribuída é **exatamente** o aporte informado |
| 2 | nenhuma classe recebe valor negativo (nunca sugere vender) |
| 3 | nenhuma classe passa do próprio ideal por causa do aporte |
| 4 | a soma das distâncias até a meta **nunca aumenta** |
| 5 | **sem meta nenhuma cadastrada, não distribui nada** |

Rode assim:

```bash
.venv\Scripts\python -m verificacao.conferir_rebalanceamento
```

Ele testa a sua carteira real **e** 400 carteiras sorteadas — saldos e metas
aleatórios, incluindo os casos esquisitos (carteira vazia, uma classe só, metas
que não somam 100%). Testar só com a sua carteira provaria pouco: os defeitos
de arredondamento aparecem justamente nas combinações que ninguém pensou em
testar à mão.

### A garantia 5 chegou tarde, e a história explica por quê (2026-08-23)

Sem nenhuma meta cadastrada, `rebalancear(1000)` mandava **os R$ ···· inteiros
para "NTN-B (inflação)"** — uma classe com alvo de 0%.

A função decidia certo e zerava a coluna. O estrago vinha no ajuste de
arredondamento: com tudo zero, o "resíduo" passava a ser o aporte inteiro, e
`idxmax()` numa coluna de zeros devolve a primeira linha.

**Por que 2.143 checagens não pegaram isso.** O caso "sem metas" só era testado
contra `_distribuir()` — a reimplementação independente que este projeto mantém
de propósito, para uma servir de conferência da outra. **Ela acertava.** A
função de produção só era exercitada na seção 3, onde as metas eram *sempre*
gravadas antes de testar.

> O arquivo já avisava que "um teste escrito sob a mesma suposição do código
> passa pelo motivo errado". Este caso é a volta a mais: **testar a cópia do
> código em vez do código não prova nada sobre o código.** A cópia estava
> certa; quem rodava na tela, não.

A tela protegia você — ela checa `soma_das_metas() <= 0` e mostra o aviso antes
de chamar a conta. Mas a guarda estava na camada errada: `financas/` precisa
estar certo sozinho, porque é justamente isso que permite testá-lo sozinho.

### E o teste não escreve mais no seu banco

Esta seção precisa de metas cadastradas para rodar, e ela as gravava **no banco
de produção**, desfazendo num `finally`. Enquanto `metas_alocacao` esteve
vazia, não havia o que perder. No dia em que você cadastrar as suas metas, um
Ctrl+C no meio apagaria o trabalho — e o culpado seria o script que existe para
provar que está tudo certo.

Agora ele copia o banco para a pasta temporária e aponta `config.CAMINHO_BANCO`
para a cópia. Funciona porque `banco.conectar()` lê essa variável **na hora da
chamada**, não no import.

> **Um teste nunca deve poder destruir o dado que ele verifica.**

---

## "Em quantos meses eu chego lá?"

A aba responde, para cada classe fora da faixa. A simulação **ignora o
rendimento de propósito**: ninguém sabe quanto a bolsa vai render, e supor um
número deixaria o prazo mais bonito e menos confiável. Sem rendimento, o prazo
é o pior caso realista — e é esse que serve para decidir.

---

## De onde sai o aporte de cada papel — três fontes

Esta é a parte mais delicada do módulo, e a que mais errou antes de acertar.

Para saber quanto um papel **rendeu**, é preciso saber quanto dele foi
**comprado** no mês:

```
rendimento = saldo − saldo anterior − aporte + resgate
```

Sem o aporte, uma compra nova vira "rendimento". Foi o que produziu um
rendimento de **−R$ ···· em agosto/2026** e um fundo DI com **+37,9% em 8
meses**.

### A coluna que parecia resolver e não resolvia

O arquivo tem uma coluna "Total aplicado". Ela **não é custo de aquisição**:

```
Histórico 31/01   NTN-B ago/2060   posição R$ ····   aplicado R$      0,00
Atual     22/08   NTN-B ago/2060   posição R$ ····   aplicado R$ ····
```

Zerada no histórico, cópia da posição no atual. E o "Valor aplicado" do bloco
de Fundos, que é real, mudou de forma inexplicável em maio: subiu R$ ···· no
mês em que houve um **resgate**.

### A ordem que vale hoje

| # | Fonte | Quando vale | Precisão |
|---|---|---|---|
| 0 | **primeiro mês do papel** | o saldo de abertura não é ganho | exata |
| 1 | **movimentos do extrato** | o extrato nomeia o fundo | exata |
| 2 | **quantidade de títulos** | Tesouro | estimativa |
| 3 | variação do custo | fundos sem movimento casado | frágil |

**Fonte 0** — no primeiro mês, o saldo inteiro conta como aporte e o rendimento
fica zero. O que o papel rendeu antes de entrar no app não tem como ser sabido.

**Fonte 1** — a melhor. O extrato diz `RESGATE Trend DI FIC RF Simples RL`, e
isso é dinheiro de verdade, não uma coluna calculada. O casamento usa as **duas
primeiras palavras** do nome, porque o extrato abrevia o resto — e duas palavras
já separam "Trend DI" de "Trend Investback".

**Fonte 2** — o Tesouro não entra na fonte 1, porque o extrato só diz "COMPRA
TESOURO DIRETO CLIENTES", sem dizer qual título. Mas a quantidade não mente:

```
NTN-B ago/2060   jan  7,84 títulos   →   mar  14,22 títulos
aporte ≈ 6,38 × preço unitário do mês = R$ ····
```

Não sabemos o preço do dia da compra, então erra por centavos. Ignorar a compra
errava por dezenas de milhares.

### No nível da carteira inteira, outra conta

O gráfico "o que fez a carteira crescer" **não soma papel a papel**. Ele usa o
fluxo externo, que é uma fonte independente:

```
variação da carteira  =  fluxo externo (conta corrente ⇄ corretora)  +  rendimento
```

Compra e venda dentro da corretora não entram — comprar um título converte
dinheiro parado em título, e o tamanho da carteira não muda.

O KPI "Rendimento apurado" usa **a mesma fonte**, de propósito: dois números
diferentes para a mesma coisa, na mesma tela, é pior que um número menos
detalhado.

---

## Por que o custo aplicado ainda é guardado

O arquivo de posição traz duas colunas de dinheiro por papel:

```
Posição         R$ ····   quanto vale hoje
Valor aplicado  R$ ····   quanto você colocou
```

A diferença (R$ ····) é o ganho acumulado. A migração 4 criou a coluna
`investimentos_saldos.custo_aplicado` para guardar a segunda.

Sem ela, a única forma de calcular rendimento seria comparar saldos de dois
meses — e aí uma **compra nova apareceria como se fosse rendimento**. Com o
custo guardado, o aporte do mês sai da conta certa:

```
aporte(mês) = custo(mês) − custo(mês anterior)
```

e a fórmula que já existia passa a dar o número verdadeiro. Na primeira
importação de um papel, `custo(mês anterior)` é zero, então o aporte é o custo
inteiro e o rendimento sai como `saldo − custo` — exatamente o ganho acumulado.

Foi assim que a tela passou a mostrar **R$ ····** de rendimento apurado,
que é a soma dos ganhos dos 7 papéis.

---

## O que ficou de fora, e por quê

**Moeda estrangeira.** O stock pick dos EUA entra por cadastro manual, com o
saldo em reais, até a exportação existir. A coluna `moeda` já foi criada, então
quando o arquivo aparecer não vai precisar de migração — mas decidir o
tratamento de câmbio agora, sem saber o que a corretora exporta, seria escrever
código para jogar fora.

**Venda no rebalanceamento.** Decisão sua: só aporte.

---

## Ver também

- [11 · Investimentos](11_investimentos.md) — a carteira cadastrada à mão
- [03 · Leitura de arquivos](03_leitura_de_arquivos.md) — o contrato dos leitores
- [02 · Banco de dados](02_banco_de_dados.md) — as tabelas e as migrações
