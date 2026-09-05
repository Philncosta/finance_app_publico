# 11 · Investimentos

Arquivos do código: [`financas/calculos/investimentos.py`](../financas/calculos/investimentos.py)
e [`paginas/investimentos.py`](../paginas/investimentos.py)

> **A partir de 2026-08-22 a carteira não precisa mais ser digitada.**
> A corretora exporta a posição em Excel, e o app importa. Veja
> [12 · Carteira e rebalanceamento](12_carteira_e_rebalanceamento.md) —
> este documento continua valendo para o que você cadastra à mão
> (ações, stock picks) e para a conta do rendimento.

---

## Por que esta tela tem duas metades

O extrato da conta corrente sabe dizer **quanto dinheiro saiu** para a conta de
investimento. Ele não sabe dizer:

- em **que** você aplicou (CDB? Tesouro? fundo?)
- quanto aquilo **vale** hoje
- quanto **rendeu**

Nenhum desses três dados aparece no extrato — eles vivem na corretora. Daí a
divisão:

| Metade | De onde vem | Trabalho seu |
|---|---|---|
| **Automática** | dos lançamentos importados | nenhum |
| **Manual** | de você, olhando a corretora | ~2 min por mês |

A aba **Carteira** cruza as duas e diz se batem.

---

## A metade automática

Sai das categorias que as regras do extrato aplicam sozinhas na importação:

| Categoria | O que é | Sinal |
|---|---|---|
| **Investimentos** | dinheiro saindo da conta para aplicar | negativo |
| **Desinvestimentos** | dinheiro voltando da aplicação | positivo |
| **Rendimentos** | juro que a própria conta corrente paga | positivo |

As duas primeiras vêm com a **mesma descrição** no extrato
(`"Transferência enviada/recebida da conta investimento"`) — o que as separa é
o sentido do dinheiro. Por isso existem duas regras, distinguidas pelo campo
*Sentido*:

| Ordem | Palavra-chave | Sentido | Vira |
|---|---|---|---|
| 3 | conta investimento | **Saída** | Investimentos |
| 4 | conta investimento | **Entrada** | Desinvestimentos |

Os **Rendimentos** ficam à parte de propósito: é o juro que o banco paga por
dinheiro parado na conta corrente, não rendimento da sua carteira. Misturar os
dois inflaria a rentabilidade.

> Nos seus dados: R$ ···· enviados, R$ ···· resgatados —
> **R$ ···· líquidos** aplicados, e R$ ···· de juro da conta corrente.

---

## A metade manual

Duas tabelas no banco, e a separação entre elas importa:

**`investimentos`** — o cadastro. Uma linha por aplicação: nome, tipo,
instituição, indexador, taxa, liquidez, objetivo.

**`investimentos_saldos`** — o acompanhamento. Uma linha por aplicação **por
mês**: saldo, aporte, resgate.

### Por que duas tabelas e não uma

Um investimento existe uma vez só; o saldo dele muda todo mês. Guardar os dois
juntos obrigaria a repetir nome, instituição e taxa em cada linha mensal — e,
no dia em que você corrigisse o nome, teria que corrigir em 12 lugares.

Essa separação tem nome: **normalização**. Cada informação mora num lugar só.

---

## A conta do rendimento

Não dá para simplesmente comparar dois saldos, porque entre um mês e outro
você pode ter aportado ou resgatado:

```
rendimento(mês) = saldo(mês) − saldo(mês anterior) − aporte(mês) + resgate(mês)
```

**Exemplo:** o saldo saiu de R$ ···· para R$ ···· mas você aportou
R$ ···· no meio. O rendimento foi **R$ ····**, não R$ ····

E o percentual usa como base o dinheiro que **esteve aplicado** durante o mês:

```
rendimento_% = rendimento ÷ (saldo anterior + aporte)
```

Sem somar o aporte, um mês em que você dobrou a aplicação mostraria um
percentual sem sentido.

### Rendimento é o nome do que sobrou sem explicação — e isso é perigoso

Repare na fórmula: rendimento é **o resto**. Tudo que a conta não conseguir
atribuir a um aporte ou a um resgate vira "rendimento", com esse nome
respeitável, mesmo quando não rendeu nada.

Em 2026-08-23 três fontes de dado que faltavam produziram, juntas, estes
números — todos rotulados como rendimento:

| mês | mostrava | era, na verdade |
|---|---|---|
| jun/2024 | −R$ ···· | um CDB vencendo e virando caixa parado |
| jul/2024 | +R$ ···· | o mesmo caixa voltando para um fundo |
| mar/2025 | −R$ ···· | R$ ···· aportados que ficaram parados |
| jan/2026 | −R$ ···· | nove meses sem foto, espremidos num mês |

Depois de corrigir as fontes, os doze meses de 2024-2025 passaram a render
**entre R$ ···· e R$ ····** — a faixa de ~1% ao mês, que é o CDI do período.

> **Quando o rendimento parecer grande demais, a primeira suspeita não é o
> mercado: é uma entrada ou saída que a conta não viu.**

### Por papel, isso tem uma consequência: a coluna `confiavel`

O aporte de um papel vem de três fontes, e elas não valem o mesmo:

| fonte | qualidade |
|---|---|
| extrato da corretora | dinheiro de verdade, com o papel nomeado |
| **quantidade** de títulos | o arquivo informa e não mente |
| coluna "Valor aplicado" | **mente** — muda sem você ter movimentado nada |

Um fundo não tem quantidade. Fora da cobertura do extrato da corretora, só
resta a terceira — e ela produziu isto no Trend DI:

```
out/2025  −13,81%      nov/2025  +27,52%      dez/2025  −20,28%
```

Um fundo DI não faz isso. O "Valor aplicado" pulou de R$ ···· para R$ ····
e voltou para R$ ···· em três meses.

`evolucao()` marca cada mês com **`confiavel`**, por uma regra de
**procedência, não de limiar**: o mês vale quando a fonte era boa — dentro do
extrato, ou o papel tem quantidade. `rentabilidade_periodo()` ignora os demais
e devolve `meses_ignorados`, para a tela avisar em vez de esconder.

O Trend DI passou de **−4,46% em 12 meses** para **+7,74% em 8 meses (0,94% ao
mês)** — a faixa do CDI.

E set/2025 ficou de fora mesmo parecendo bom (+1,22%). **A regra olha a fonte,
não o resultado** — escolher a dedo os meses de fonte ruim que parecem bonitos
seria pior que não filtrar.

### E a mesma regra vale na tabela da Carteira

`rentabilidade_periodo()` já ignorava os meses de fonte ruim. A **tabela** não —
a coluna "Rendeu no total" somava todos. Resultado: o `CDB BANCO XP ABR/2027`
aparecia com **−R$ ···· de prejuízo** que nunca existiu.

`posicao()` devolve as duas leituras, e elas servem para coisas diferentes:

| coluna | soma | serve para |
|---|---|---|
| `rendimento_total` | todos os meses | fechar com o saldo (é a identidade contábil) |
| `rendimento_confiavel` | só os meses de fonte boa | responder "quanto rendeu?" |
| `meses_sem_fonte` | — | dizer de quanta coisa você não sabe |

**`rendimento_confiavel` é `None`, nunca 0, quando não há mês mensurável.**
Zero se lê como "não rendeu"; a verdade é "não dá para saber". A tela mostra
vazio.

E o **primeiro mês não conta como medição**: ele é aporte puro, rendimento zero
por construção. Um papel cujo único mês confiável é o primeiro nunca foi medido
— por isso o CDB ABR/2027 e a BBAS3 aparecem vazios em vez de com 0,00.

### Posição aberta e posição encerrada

`posicao()` devolve **todo** papel já cadastrado, inclusive os zerados. Isso é
de propósito: quem soma a carteira precisa da lista completa (zerados somam
zero) e o histórico do que já se operou tem valor.

A separação é da **tela**, não do cálculo:

```python
abertas    = posicao[posicao["saldo"] > 0]     # a tabela do dia a dia
encerradas = posicao[posicao["saldo"] <= 0]    # o bloco recolhido
```

Eram 7 linhas zeradas em 18. Uma tabela em que 40% das linhas dizem R$ ····
esconde as que importam.

Cuidado ao agrupar: `por_tipo()` conta linhas com `("id", "size")`, então os
zerados inflavam a **contagem** de papéis por tipo — o saldo estava certo e a
contagem não. Passe `abertas`, não `posicao`.

### Duas garantias que moram no cálculo, não na gravação

**Saldo de abertura não é ganho.** O que você tinha no dia em que começou a
acompanhar não foi ganho naquele mês. A importação já respeitava isso; agora o
cálculo garante, venha o dado de onde vier. A assinatura desse erro é fácil de
reconhecer: o *rendimento acumulado* bate com o *saldo atual*.

**Caixa não rende.** A variação do saldo parado na corretora é sempre fluxo —
dinheiro entrando ou saindo — nunca rendimento. Sem isso ele aparecia com
−100% ao mês, quando só tinha sido aplicado.

---

## O dinheiro parado também é carteira

O arquivo da corretora traz **dois** números no cabeçalho, e por muito tempo o
app usou só um:

```
Total investido    R$ ····    aplicado em papéis
Saldo Disponível   R$  R$ ····    parado em conta na corretora
-------------------------------------
patrimônio         R$ ····    o que você tem lá
```

Aquele março/2025 é real: **41% do dinheiro dele estava parado**, esperando
decisão.

Ignorar isso fazia duas coisas ruins. A carteira aparecia menor do que era; e,
pior, quando o dinheiro parado era aplicado no mês seguinte, a diferença virava
"rendimento" (ver o quadro acima).

Hoje o saldo parado entra como um papel chamado **`Saldo em conta (XP)`**, na
classe `Saldo em conta` (macro `Caixa`). Ser um papel normal é o ponto: nenhuma
tela precisou de tratamento especial — a posição, a evolução, a alocação e o
rebalanceamento passaram a enxergá-lo sozinhos.

**E aparecer no rebalanceamento é desejável.** Dinheiro parado não é a ausência
de uma alocação; é uma alocação com custo de oportunidade, e o painel deve
cobrar por ela como cobra pelas outras.

---

## Duas fontes para o mesmo fato, e a regra de precedência

O dinheiro que cruza a fronteira entre a conta corrente e a corretora aparece
dos dois lados:

| Fonte | Onde | Cobertura | Confiança |
|---|---|---|---|
| Extrato da corretora | `investimentos_movimentos` | jan/2026 → | a própria corretora dizendo o que recebeu |
| Conta corrente | `lancamentos`, categorias `Investimentos` / `Desinvestimentos` | abr/2024 → | depende da classificação estar certa |

A regra, em `fluxo_externo_mensal()`: **onde o extrato da corretora alcança,
ele manda; fora dali, vale a conta corrente.**

O que dá confiança nessa ordem é que nos 8 meses em que **as duas existem**
elas batem ao centavo em 7. A única diferença — R$ ···· em ago/2026 — é
justamente onde a conta corrente erra: duas TED que saíram da corretora e
entraram como "TED recebida de ANA", classificadas `Transferência` em vez
de `Desinvestimentos`.

> A fonte preferida ganha exatamente no caso em que a outra erra. É o melhor
> argumento que uma regra de precedência pode ter — e ele só existe porque
> houve um período com as duas fontes para comparar.

### Foto faltando não é "nada aconteceu"

As fotos da carteira não são mensais sem falha: faltam abr/2025 a dez/2025.
Atribuir o fluxo só aos meses que **têm** foto joga fora tudo que se moveu no
vão, e a variação do período inteiro vira rendimento do primeiro mês que
reaparece.

Por isso **cada foto responde por tudo que aconteceu desde a foto anterior** —
que é a definição de rendimento, independente de quantos meses o intervalo
tenha.

---

## Rentabilidade acumulada: por que não é soma

Juros compostos **multiplicam, não somam**:

```
acumulado = (1 + r₁) × (1 + r₂) × … − 1
```

Um mês de 1,82% seguido de um de 1,34% não dá 3,16%, e sim **3,18%** — o
segundo mês rende também sobre o que o primeiro rendeu.

Pelo mesmo motivo, a média mensal é **geométrica**:

```
média = acumulado^(1/n) − 1
```

---

## A referência: contra o que comparar

"A NTN-B mai/2035 rendeu 6,05%" não é informação. É só um número até você saber
contra o que. No mesmo período o CDI fez 14,22% e o IPCA 4,44% — e, conforme a
régua, o mesmo papel "perdeu feio" ou "protegeu o poder de compra com folga".

**A régua errada é pior que nenhuma.** Este é o erro mais comum em planilha de
investimento pessoal: comparar tudo com o CDI.

| papel | contra CDI | por quê |
|---|---|---|
| LFT mar/2031 | 103% | ✅ pós-fixado, o CDI é a régua |
| Trend DI | 88% | ✅ e o desvio é taxa + come-cotas |
| NTN-B mai/2045 | 19% | ❌ o CDI **mente** aqui |
| IRE | −765% | ❌ aritmética sem significado — hoje vai contra o S&P |

Uma NTN-B perde do CDI em ciclo de juro alto **por construção**: a marcação a
mercado cai justamente porque a Selic subiu. A pergunta certa para um IPCA+ é
*protegeu o poder de compra?* — e a resposta está no IPCA.

E "% do CDI" para um papel que perdeu dinheiro não quer dizer nada: o resultado
troca de sinal e a razão vira ruído.

Por isso `indices.referencia_para()` decide pelo **macro**, e devolve `None`
quando nenhum índice serve:

    Caixa, Renda Fixa pós-fixada   -> CDI
    Renda Fixa indexada ao IPCA    -> IPCA
    Renda Variável                 -> IBOV
    Internacional                  -> S&P 500 (em reais, via IVVB11)
    Imóvel, Previdência, o resto   -> nenhuma

**Ação e papel no exterior passaram a ter régua** — antes não tinham. Não era
por não existir régua: era por o app só conhecer CDI e IPCA, e nenhum dos dois
dizer nada sobre uma ação. Com IBOV e S&P na base, o IREN sai de **−765%
contra o CDI** para **−37,8% contra +14,3% do S&P** — a mesma posição, agora
medida contra o que ela de fato disputa.

O S&P entra **em reais**, pelo ETF IVVB11, e isso é deliberado: a
carteira-sombra é em reais, então aplicar uma variação em dólar sobre ela
somaria moedas sem quebrar nada — o erro mais silencioso que este app tem.
Em compensação a comparação passa a incluir o câmbio, que é justamente o que
ele sente no bolso.

SMLL e IFIX entram por ETF (SMAL11, XFIX11) porque o índice em si não tem
ticker público. O ETF rende um pouco menos que o índice — taxa de
administração — e a tela diz que é aproximação em vez de fingir precisão.

`None` continua existindo, e continua sendo a resposta certa para imóvel e
previdência. O que mudou foi a lista de quem cai nele.

### A referência tem de usar os MESMOS meses

Se o rendimento de um papel ignora 4 meses de fonte ruim, o CDI tem de ignorar
os mesmos 4. Comparar 8 meses de fundo contra 12 meses de CDI é uma mentira que
passa despercebida — os dois números têm exatamente a mesma cara.

Por isso `rentabilidade_periodo()` devolve a **lista** `meses`, e
`indices.acumulado()` recebe uma lista, não um intervalo.

E `indices.cobertura()` existe por um motivo concreto: **o IPCA sai com um mês
de atraso.** A tela avisa quando a comparação cobre menos meses que o papel.

### A carteira-sombra

O gráfico da carteira mostra **reais**; o CDI é uma **taxa**. Desenhar uma taxa
junto de um valor não compara nada — as escalas não se falam.

O que responde a pergunta de verdade (*"e se eu tivesse deixado tudo no fundo
DI?"*) é simular a mesma carteira, com os mesmos aportes e resgates, rendendo o
índice:

    sombra_do_mês = (sombra_anterior + aporte − resgate) × (1 + taxa)

A sombra parte do mesmo ponto que a carteira real. Elas só se separam a partir
do segundo mês — que é o único jeito de a comparação ser justa.

Hoje: carteira **R$ ····** contra **R$ ····** no CDI.

## O cupom semestral não é prejuízo

Uma NTN-B com juros semestrais paga cupom **e passa a valer menos** no mesmo
dia: o preço cai pelo valor do cupom, que vira caixa na corretora.

Se o cupom não for registrado como saída daquele título, a conta central

    rendimento = saldo − anterior − aporte + resgate

vê só o saldo caindo e joga a diferença no rendimento. **O cupom aparece como
prejuízo do tamanho exato dele mesmo.** As três NTN-B dele estavam assim; a
mai/2045 mostrava −R$ ···· quando tinha ganho R$ ····

### Como o app descobre de quem é o cupom

O extrato registra o cupom mas **não diz de qual título**:

```
REPASSE DE JUROS TESOURO DIRETO 17/08/2026     706,67
REPASSE DE JUROS TESOURO DIRETO 17/08/2026     362,88
REPASSE DE JUROS TESOURO DIRETO 17/08/2026     870,38
```

São três linhas porque são três **lotes de compra do mesmo título**, não três
títulos. Duas regras resolvem, e as duas vêm de como a NTN-B funciona:

1. **O mês do cupom sai do vencimento.** `mai/2035` paga em maio e novembro;
   `ago/2060` em fevereiro e agosto. E **`PRINC` não paga nunca** — Tesouro
   IPCA+ e Tesouro IPCA+ *com Juros Semestrais* são produtos diferentes.
2. **Toda NTN-B paga o mesmo cupom por unidade**, porque todas usam o mesmo
   VNA. O rateio entre títulos que pagam no mesmo mês é proporcional à
   quantidade.

A regra 2 é verificável, e foi verificada:

    18/02/2026   R$ ···· /  7,84 un = R$ ···· por unidade
    15/05/2026   R$ ···· / 10,62 un = R$ ···· por unidade
    17/08/2026   R$ ···· / 14,22 un = R$ ···· por unidade

Três datas, dois títulos diferentes, mesmo valor por unidade — e a diferença
entre fevereiro e agosto é o próprio IPCA do período.

O valor atribuído é o cupom **bruto**, de propósito: é o bruto que sai do
título. O IRRF que a corretora retém é imposto dele, um custo da carteira — não
desempenho do papel.

## A conciliação

**Saldo de abertura não é rendimento.** A conta XP foi aberta em 17/04/2024 com
R$ ···· vindos de outro banco. `conciliar()` fazia `carteira − aportado` e
chamava o resto de rendimento — mas aquele dinheiro também não foi aportado, e
caía no resto.

O sintoma eram dois números discordando na mesma tela: *DIFERENÇA* R$ ····
ao lado de *RENDIMENTO APURADO* R$ ···· distantes exatamente o saldo de
abertura.

Com `saldo_de_abertura()` descontado, os **dois caminhos independentes** fecham
no mesmo valor:

    ponta a ponta   carteira − aportado − abertura   = R$ ····
    mês a mês       soma dos rendimentos mensais     = R$ ····

Que eles batam é uma checagem permanente: se um dia divergirem, algum fluxo
deixou de ser enxergado.


A função `conciliar()` compara as duas metades:

```
carteira cadastrada  −  aportado líquido  =  diferença
```

Como ler o resultado:

| Situação | O que significa |
|---|---|
| **rendendo** | a carteira vale mais do que você aportou — a diferença é o rendimento |
| **confere** | os dois batem (raro, só se você nunca teve rendimento) |
| **abaixo do aportado** | ou houve perda, ou — bem mais provável — falta cadastrar aplicação / atualizar saldo |
| **saldos desatualizados** | alguma aplicação tem saldo de um mês anterior |

O campo `desatualizado` de cada aplicação é o aviso prático de "vai na
corretora e anota".

---

## Por que o total da carteira não é a soma dos saldos menos a soma anterior

Em `evolucao_carteira()` somamos o **rendimento já calculado de cada
aplicação**, um por um — e não a diferença dos totais.

O motivo: uma aplicação cadastrada no meio do caminho faria o total "saltar", e
esse salto viraria **rendimento fantasma**. Calculando por aplicação e somando
depois, um cadastro novo entra com rendimento zero no primeiro mês, que é o
correto.

---

## A tela não tem seletor de mês — e o motivo é a pergunta

Todas as outras telas deste app giram em torno de **um mês**: quanto entrou em
agosto, quanto saiu, quanto sobrou. A carteira não. Ninguém pergunta *"quanto
eu tinha em maio"* — pergunta **"quanto eu tenho, e como cada papel está
indo"**.

Por isso a tela mostra sempre a **foto mais recente de cada papel**, e o
cabeçalho declara de quando ela é (*"Posição de ago/2026 · 11 papéis"*). A
coluna **Foto de**, na tabela de papéis, avisa quando a de algum papel é mais
velha que a dos outros.

**Sobrou um lugar com escolha de mês: *Manutenção → Atualizar saldos*.** E ali
ele não é leitura, é **registro** — você está gravando a foto de um mês
específico. A tela diz isso ao lado do controle, para a exceção não parecer
inconsistência.

---

## O número mais fácil de errar: "quanto esse papel valorizou"

Há duas contas, as duas parecem certas, e **uma delas mente**.

| papel | encadeada | saldo ÷ aportado |
|---|---|---|
| NTN-B ago/2060 | 10,3% | 6,9% |
| **Trend DI** | **7,7%** | **+213,4%** |
| LFT mar/2031 | 9,7% | 5,2% |
| IREN | −37,8% | −37,8% |

Repare que nos papéis comprados e guardados as duas quase coincidem. Elas se
separam onde há **rotatividade**: o Trend DI recebeu R$ ···· e devolveu
R$ ···· em 29 meses, porque é usado como caixa. Dividir o saldo pelo aporte
líquido de um papel assim não significa nada — e o resultado tem exatamente a
cara de um número certo.

A tela usa a **encadeada**, que já existia em `rentabilidade_periodo()`:

```
acumulado = (1 + r₁) × (1 + r₂) × … − 1
```

Ela é imune ao momento em que o dinheiro entrou, e é a mesma conta que permite
comparar com um índice.

### E ela avisa de quanto não sabe

`rentabilidade_periodo()` só usa os meses de **fonte confiável** e devolve
`meses_ignorados`. O Trend DI mede **9 dos seus 29 meses**; mostrar 7,7% sem
dizer isso seria esconder de onde o número saiu. A tela escreve, embaixo da
tabela, um recado por papel nessa situação.

### Papel sem mês medido sai vazio, nunca zero

O `NTNB PRINC ago/2032` tem um mês só de dado — e o primeiro mês de um papel é
**aporte por construção**, não medição. A rentabilidade dele fica em branco.
Zero se leria como "não rendeu", e a verdade é "não dá para saber".

---

## O preço médio vem de você: `investimentos_compras`

O saldo mensal diz quanto o papel **vale**. Ele nunca diz quanto você
**pagou** — e sem isso não existe preço médio, não existe "valorizou quanto
sobre o custo", e a ficha de Bens e Direitos do IR fica sem o único número que
ela pede. Em ago/2026, **1 de 11 papéis** tinha custo registrado.

A coluna "Valor aplicado" da corretora não resolve: [ela muda
sozinha](#a-metade-manual), sem você ter movimentado nada. A compra lançada por
você é a única fonte que não mente.

Por isso a migração 16 criou `investimentos_compras`, e *Manutenção → Lançar
compras* alimenta ela.

### Três decisões dentro dessa tabela

**A moeda é convertida na gravação**, como em `salvar_saldo()` — mas pela
cotação **do dia da ordem**, não do fim do mês, porque foi nesse dia que o
dinheiro saiu. `cambio_usado` fica gravado para o número ser reproduzível.

**`fator_ajuste` guarda grupamento e desdobramento.** O IRE fez 1:4 em
20/03/2026. As cotações vêm ajustadas por split, então uma compra lançada com a
quantidade antiga compararia peras com maçãs — o preço médio ficaria 4× menor
que o atual e a tela diria que o papel quadruplicou. O campo nasce 1,0 e só
muda se você disser: o app não tem como conhecer um evento societário.

**Fundo não tem quantidade**, e por isso não tem preço médio unitário. Para ele
a compra registra só o valor, e a tela mostra custo total.

### Preço médio e preço atual estão os dois em reais

Mesmo para papel americano. A cotação do IREN chega em **dólar**; mostrá-la ao
lado de um preço médio em real faria o papel parecer 80% mais barato só pela
troca de moeda. A conversão do preço atual usa a cotação de **hoje**, porque é
um preço de hoje; a do preço médio ficou gravada no dia da compra.

---

## O gráfico diário, e por que ele é o único

O banco guarda **756 fechamentos diários** de IREN e DGXX e 215 do IRE — três
anos de preço — e nenhuma tela mostrava nada disso, porque as duas leituras que
existiam (`preco_em`, `preco_do_mes`) devolvem **um ponto**, não uma série.
`cotacoes.serie()` resolveu isso.

O gráfico aparece só para papel com ticker, e a tela diz por quê: Tesouro
Direto e fundo **não têm cotação pública**. Misturar granularidades sem avisar
faria parecer que o resto da carteira tem menos dado do que tem — ela tem
dado mensal, que é o que existe.

---

## A grade ano × mês

`rentabilidade_por_mes_e_ano()` devolve uma linha por ano, doze colunas de mês,
mais **No ano** e **Acumulado**.

Ela responde uma pergunta que a linha do tempo responde mal: *como foi cada
mês?*. Numa curva de saldo, um mês ruim no meio de uma subida desaparece; na
grade ele fica vermelho no meio da fileira.

Os dois totais **compõem**, não somam. E célula vazia é mês sem dado — não mês
de rentabilidade zero.

---

## A rotina de dois minutos por mês

1. Abra a corretora e veja quanto cada aplicação vale.
2. No app: **Investimentos → Atualizar saldos**, escolha o mês na barra
   lateral.
3. Digite o saldo de cada uma. O app já mostra:
   - o **saldo anterior** (de onde partiu),
   - quanto o **extrato diz** que saiu para investimento naquele mês,
   - o **rendimento** recalculado a cada edição.
4. Distribua o aporte entre as aplicações e salve.

O app avisa se a soma dos aportes não bate com o que o extrato registrou — não
é erro (pode haver aporte por outro caminho), mas vale conferir.

---

## Como testar no terminal

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import dados; from financas.calculos import investimentos as inv; df = dados.carregar_lancamentos(); print(inv.movimentacoes(df)); print(inv.conciliar(df, '2026-08'))"
```

---

## Como mudar

**Adicionar um tipo de investimento** — edite a lista `TIPOS` em
`financas/calculos/investimentos.py`. O mesmo vale para `INDEXADORES` e
`LIQUIDEZ`.

**Mudar a conta de rendimento** — está em `evolucao()`, numa linha só. Se
mexer, atualize a explicação aqui e no docstring.

**Rastrear aporte por aplicação automaticamente** — hoje o extrato só sabe o
total que foi para a "conta investimento"; a divisão entre aplicações é você
quem faz. Para automatizar seria preciso importar o extrato **da corretora**,
o que exigiria um leitor novo em `financas/leitores/`.
