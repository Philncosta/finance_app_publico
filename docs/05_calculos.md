# 05 · Os cálculos

Arquivos do código: [`financas/calculos/`](../financas/calculos/)

Cada indicador do painel está aqui, com a explicação de **o que ele responde**
e **de onde saía na planilha**.

Todas as funções desta pasta são **puras**: recebem um DataFrame, devolvem
números. Não leem banco, não importam Streamlit. Por isso dá para conferir
qualquer uma no terminal.

---

## `kpis.py` — os números grandes do Dashboard

### Resultado do mês

| Indicador | Conta | Vinha de |
|---|---|---|
| Receita total | soma de `Receita` + `Receita Extraordinária` | Dashboard A6 |
| Receita recorrente | só natureza `Receita` | — |
| Receita extraordinária | só `Receita Extraordinária` | — |
| Despesa | −(soma de natureza `Despesa`) | Dashboard E6 |
| Saldo | receita total − despesa | Dashboard I6 |
| Comprometimento | despesa ÷ receita total | Dashboard M6 |

#### Por que a receita vem separada em duas partes

Em fevereiro você recebeu **R$ ····** de PLR; em agosto, **R$ ····** de
indenização. Somar isso ao salário faz o mês parecer confortável quando na
verdade foi excepcional — e não se planeja o ano seguinte em cima de exceção.

A planilha resolvia isso mostrando **só a receita recorrente** no resumo anual.
Foi exatamente isso que explicou as diferenças encontradas na conferência da
migração: os oito meses batiam ao centavo depois de tirar a extraordinária.

Aqui mostramos as duas, com a extraordinária destacada num aviso próprio. O
Dashboard mostra: *"Sem ela, o saldo do mês seria X"* — que é o número honesto
para planejar.

---

### Composição da despesa — a análise mais útil do painel

| Indicador | Conta |
|---|---|
| Gasto novo do mês | despesa total − parcelas herdadas |
| Parcelas herdadas | parcelas 2, 3, 4… de compras de meses anteriores |
| Já contratado p/ o mês seguinte | parcelas herdadas **já lançadas** no mês que vem + as ainda não faturadas |
| Novo comprometimento criado | Σ (valor da parcela × (total − 1)) das **primeiras** parcelas do mês |

**Por que isso importa mais que o total:** duas pessoas podem gastar os mesmos
R$ ···· num mês. Uma decidiu tudo naquele mês e pode cortar no mês que vem;
a outra só está pagando parcela de compra antiga e não tem o que cortar. O
total não distingue as duas — esta conta sim.

**O "novo comprometimento"** é o indicador mais honesto do painel: quanto do
seu futuro você hipotecou neste mês. Uma compra de R$ ···· em 12x feita agora
aparece como R$ ···· — os outros 11 meses.

> Vinha do Dashboard, linhas 8–9 da planilha.

---

### Cartão de crédito

| Indicador | Conta |
|---|---|
| Fatura do mês | soma dos gastos com origem `Fatura` |
| Ainda a vencer | soma de tudo que falta de todos os parcelamentos |
| Parcelamentos ativos | quantos ainda têm parcela por vir |
| Variável no cartão | a parte com tipo `Variável` (a que dá para cortar) |

---

### Médias e tendência

**Cuidado importante:** as janelas de média **não incluem o mês escolhido**. Se
incluíssem, o mês estaria sendo comparado com ele mesmo — um mês caro puxaria
a própria média para cima e pareceria menos fora da curva do que foi.

Também descartamos os meses "de futuro". Um mês futuro pode já ter 3 ou 4
lançamentos (as mensalidades dos cursos agendadas até dezembro) e uma despesa
de R$ ···· Se ele entrasse na média, a média de 3 meses despencaria e a
comparação ficaria sem sentido. **Exigimos pelo menos 5 lançamentos** para
considerar um mês "vivido".

A **previsão do próximo mês** é a média de 3 meses mais as parcelas já
contratadas que caem lá. Não é adivinhação sofisticada — é a conta honesta com
o que se sabe hoje.

---

### O que mudou contra o mês passado — `variacao_por_categoria`

A média de 3 meses responde *"este mês foi caro?"*. Esta conta responde
*"caro **onde**?"* — e só a segunda dá para agir em cima.

> "Você gastou 22% acima da média" é uma informação morta.
> "Saúde subiu R$ ···· e Viagem R$ ····" você lembra o que foi, e decide se
> repete no mês que vem.

A conta é uma subtração simples por grande categoria: `atual − anterior`. Mas
duas decisões de ordenação e de borda fazem toda a diferença:

**Ordena pelo tamanho da MUDANÇA, não do gasto.** Se ordenasse pelo gasto, a
lista seria sempre a mesma — Moradia, Alimentação, Moradia, Alimentação — e não
diria nada. Uma categoria grande e estável não interessa aqui; uma pequena que
triplicou, sim.

**Categoria que existe num mês só entra com zero do outro lado.** Sem isso, a
maior novidade do mês ficaria justamente de fora — por ser nova.

**Percentual sem base vira `None`, não 100%.** Se o mês anterior foi zero, a
variação percentual não existe. Inventar um número ali (∞, 100%, 999%) é pior
que admitir que não dá para calcular: o gráfico mostra o valor em R$ e omite o
percentual.

---

### Taxa de poupança — `taxa_de_poupanca`

    taxa = (receita − despesa) ÷ receita

O painel dizia quanto entrou e quanto saiu, mas não respondia a pergunta do
longo prazo: **estou guardando dinheiro?** R$ ···· de receita com R$ ····
de despesa parece confortável em valor absoluto e é péssimo em taxa (5%).

#### Dois filtros, e os dois são necessários

| Filtro | O que aconteceria sem ele |
|---|---|
| menos de 5 lançamentos | um mês só com parcela agendada dá taxa de −300% e afunda a escala |
| mês em andamento | em 22/08/2026 setembro aparecia com **−143,5%** |

O segundo é o mais traiçoeiro. As despesas contratadas chegam antes da receita,
então o mês corrente **sempre** parece péssimo. Aquele setembro puxava a média
do período inteiro de +11% para −15%. Não era um mês ruim; era um mês que não
tinha acabado.

#### Agregada × média das mensais — uma diferença de 40 pontos

Existe `taxa_de_poupanca_agregada()` justamente para você **não** usar a média
das taxas mensais. São números diferentes:

| | |
|---|---|
| média das taxas mensais | −32,0% |
| mediana | −38,3% |
| **agregada** (Σ saldos ÷ Σ receitas) | **+28,3%** |

*(medido em 2026-08-23, sobre 28 meses fechados)*

A receita oscila muito — **R$ ····** no mês mais magro contra **R$ ····** no
mais gordo, catorze vezes. Um mês magro produz uma taxa de −236% (set/2025), e
uma média de percentuais trata esse mês como se pesasse igual a um mês de PLR.
A agregada pesa cada mês pelo tamanho dele, que é o que a pergunta *"de tudo
que entrou, quanto sobrou"* pede.

Repare que a distância entre as duas leituras **cresceu** desde a primeira vez
que esta tabela foi escrita (eram −12,1% e +29,6%). Não é o método que piorou:
é a renda que ficou mais irregular. Mais um motivo para não usar a média de
percentuais.

> **A regra geral:** ao juntar percentuais, quase nunca é a média deles. É a
> divisão das somas. Vale para taxa de poupança, para comprometimento e para
> qualquer razão entre dois totais.

---

### Ano a ano — `comparativo_anual`

Só passou a fazer sentido quando 2024 e 2025 entraram no banco: com um ano só
não há comparação nenhuma.

**A coluna `meses` é a que faz o resto ser legível.** 2024 tem 9 meses de
dados e 2026 está pela metade — comparar os **totais** diria que 2026 foi o
melhor ano, quando o que houve foi menos meses. Por isso vão junto as médias
mensais, que são o número comparável.

O mês em andamento fica de fora pelo mesmo motivo da taxa de poupança, e pela
mesma função: `dados.meses_fechados()`.

---

### Resumo anual

Tabela mês a mês com receita, despesa, saldo e acumulado, mais uma linha de
fechamento a cada trimestre.

> **Um bug que existiu aqui e vale conhecer.** A primeira versão pegava os três
> meses do trimestre com `linhas[numero_mes-3 : numero_mes]`. Isso dá certo no
> primeiro trimestre e erra em todos os outros — porque as próprias linhas de
> trimestre já inseridas empurram as posições para a frente. No 2º trimestre,
> `linhas[3:6]` pegava `[1º trimestre, abr, mai]` em vez de `[abr, mai, jun]`,
> e somava o trimestre anterior de novo.
>
> A correção foi usar `linhas[-3:]` — os três últimos itens adicionados, que
> são sempre os três meses daquele trimestre. Depois disso, a soma dos 4
> trimestres passou a fechar exatamente com a soma dos 12 meses.

---

## O que a reconciliação competência × caixa realmente prova

Existe uma conferência muito citada neste projeto:

```
competência − caixa − (fatura do mês − pagamento da fatura) = 0
```

Ela fecha ao centavo em todos os meses, e é fácil tratar isso como atestado
geral de integridade. **Não é** — e vale desenvolver a fórmula para ver por quê:

```
competência = [extrato R,RE,D] + [fatura R,RE,D]
caixa       = [extrato R,RE,D] + [extrato Pagamento]
fatura      = [fatura D]
pagamento   = [extrato Pagamento]

resíduo = competência − caixa − fatura + pagamento
        = [fatura R,RE]
```

O pagamento entra dos dois lados e **se cancela**. O resíduo mede uma coisa só:
*alguma linha de fatura está classificada como receita?*

Testado num banco de cópia em 2026-08-23:

| experimento | resultado |
|---|---|
| apagar os pagamentos de fatura de fev/2026 | **0/30 falham** — não percebe |
| marcar 1 linha de fatura como Receita | **1/30 falha** — percebe na hora |

Para o erro que ele existe para pegar (os sete "Crédito em confiança"
classificados como receita, R$ ····), é excelente. Para "faltam
lançamentos", é cego — e de fato não detectou os oito pagamentos de fatura que
faltavam na base até aquele dia.

> **Um teste que passa não prova o que você quer que ele prove; prova o que ele
> mede.** Vale derivar a fórmula pelo menos uma vez, para saber a diferença.

---

## `parcelas.py` — o que já está contratado

### Como a projeção funciona

Cada compra parcelada tem uma `chave_parcelamento` que junta todas as suas
parcelas. Para cada chave, olhamos:

```
parcela_total       quantas parcelas a compra tem       (ex: 10)
ultima_faturada     a maior parcela que já apareceu     (ex:  9)
mes_da_ultima       em que mês ela apareceu             (2026-08)
valor_da_parcela    quanto custa cada uma               (R$ ····)
```

Daí:

```
parcelas_restantes = 10 − 9 = 1
total_a_vencer     = 1 × R$ ····
e ela cai em         2026-08 + 1 = 2026-09
```

Repetindo para todos os parcelamentos e somando por mês, sai a grade de
"quanto já está comprometido em cada mês à frente".

### Só o cartão é projetado

Compromissos futuros que você lançou à mão (como as mensalidades dos cursos,
já registradas até dezembro) são lançamentos de verdade e já estão no banco.
Se projetássemos esses também, o mês contaria duas vezes.

### A conferência

A grade projetada bate **exatamente** com a linha `TOTAL PREVISTO` da aba
`Parcelas Futuras` da planilha:

| Mês | Projetado | Planilha |
|---|---|---|
| 2026-11 | R$ ···· | R$ ···· |
| 2026-12 | R$ ···· | R$ ···· |
| 2027-01 a 05 | 117,00 | 117,00 |
| 2027-06 | 0 | 0 |

> Vinha da aba `Parcelas Futuras` inteira.

---

## `fixos.py` — o piso do orçamento

### O recurso que justifica o módulo: cadastrado × realidade

Você anota "conta de luz: R$ ····". Mas quanto pagou **de verdade** nos
últimos 6 meses? Se a média real for outra, o seu planejamento inteiro está
apoiado num número errado.

A ligação entre o item cadastrado e os lançamentos reais é a coluna
`chave_historico`: um pedaço de texto que aparece na descrição
(`"ESTACIO"` para a faculdade, `"EDUARDO MOREIRA"` para o aluguel).

A média divide pela **janela inteira**, não pelos meses em que apareceu. Um
gasto que aconteceu em 3 dos 6 meses tem média mensal de metade do valor — e é
assim que ele pesa no seu orçamento.

A tolerância é de **10%**: diferença menor que isso aparece como "confere",
para não marcar como problema uma conta de luz que varia naturalmente.

#### Estorno abate, não soma

A comparação somava com `.abs()`. Um estorno é uma linha de natureza Despesa
com valor **positivo** — dinheiro que voltou. Com `.abs()`, uma devolução de
R$ ···· entrava como mais R$ ···· gastos, e o item aparecia custando R$ ····
quando custou zero.

A base tem **110 estornos, R$ ····** — não é caso de canto.

---

### Reajuste

```
valor_final = valor × (1 + reajuste_anual) ^ anos_completos
```

Usamos **anos completos** (divisão inteira por 12) porque reajuste de contrato
acontece de uma vez no aniversário, não um pouquinho por mês.

> Vinha da aba `Gastos Fixos`, colunas N e O.

---

### Quanto de cada item entra na previsão — `situacao_no_mes`

Um gasto fixo pode chegar à previsão por **três caminhos**, e só um pode valer.
Se dois valerem, a mesma despesa conta duas vezes:

1. **já foi lançado no mês** — a fatura chegou, o Pix saiu
2. **já é parcela projetada** — `parcelas.grade_futura` já cuida dele
3. **o cadastro** — a estimativa, para quando 1 e 2 não cobrem

A tabela de precedência:

| Condição | `situacao` | `entra_na_previsao` | `falta_no_mes` |
|---|---|---|---|
| `considerar_previsao = 0` | `desligado` | 0 | 0 |
| não vale no mês (início/fim) | `fora` | 0 | 0 |
| casa uma parcela prevista | `parcela` | **0** | 0 |
| já tem lançamento no mês | `lançado` | **o lançado** | 0 |
| nenhuma das anteriores | `previsto` | o esperado | o esperado |

#### Por que a parcela vence o cadastro

A parcela é **fato contratado**; o cadastro é **estimativa**. Quando os dois
descrevem a mesma despesa, o fato manda.

E há uma segunda razão, mais forte: `conferir_competencia` exige que
`projecao_caixa()["parcelas_cartao"]` seja idêntico a `parcelas.grade_futura()`,
mês a mês. Tirar a parcela da grade quebraria essa prova. Suprimir o lado do
cadastro é a **única** ordem que resolve a dupla contagem sem quebrá-la.

> O caso real: a nutricionista estava cadastrada como gasto fixo de R$ ···· **e**
> chegava como parcela 5/12 do cartão. A previsão somava os dois — R$ ···· por
> mês de despesa que não existia, até abr/2027.

#### Por que existem DUAS colunas de valor

Repare que um item **já lançado** devolve o valor lançado em
`entra_na_previsao`, e não zero. Isso não é descuido.

`projecao_caixa` **nunca conta despesa já lançada de um mês futuro** — ela só
lê receitas lançadas. Se o item lançado virasse zero no bruto, a mensalidade de
curso que você já lançou até dezembro sumiria da projeção, e o mês ficaria
**subestimado**.

Então: no **bruto** (`entra_na_previsao`) o lançamento substitui a estimativa,
porque é um número melhor. No **líquido** (`falta_no_mes`) ele vira zero,
porque já saiu. Uma função, uma precedência, duas leituras.

---

### Média por cobrança × média por janela

As duas médias existem e respondem perguntas diferentes. Confundi-las custa
caro, e é a decisão mais fácil de errar de novo daqui a seis meses.

| | Divide por | Responde |
|---|---|---|
| `media_real` | a **janela inteira** (6) | "quanto este item custa por mês" |
| `media_por_cobranca` | os **meses com cobrança** | "quanto vem na próxima vez" |

A conta de luz, medida em fev–jul/2026: R$ ···· em **4** dos 6 meses.

```
media_real          = R$ ···· / 6 = R$ ····
media_por_cobranca  = R$ ···· / 4 = R$ ····
cadastrado                          = R$ ····
```

Só a segunda serve como previsão. Usar a primeira **cortaria a conta de luz
pela metade**, porque a fórmula leria "buraco na base" como "mês sem conta" — e
um item só está em `gastos_fixos` porque ele se repete. Mês sem cobrança quase
sempre é dado faltando, não custo zero.

Dois guarda-corpos protegem a opção `Média 6m`:

- item com **menos de 2 meses** de cobrança volta para o valor cadastrado.
  Nunca zero, nunca a partir de um mês só.
- a janela é a dos **meses fechados**, a mesma de `projecao_caixa`. O mês em
  andamento está pela metade; incluí-lo puxaria a média para baixo só porque o
  mês ainda não acabou.

---

### O casamento com o histórico — `casar_no_historico`

Um matcher só, usado por `comparar_com_real`, por `situacao_no_mes` e pela base
da mediana de variáveis. Duas regras de casamento discordando na mesma tela é o
defeito que este projeto passa o tempo consertando.

A chave normalizada tem que estar contida na descrição normalizada. O filtro
opcional `categoria_historico` restringe também pela categoria.

**Por que o filtro de categoria é opt-in, e não o padrão.** A chave do aluguel é
`EDUARDO MOREIRA`, e existem Pix de **Lazer** para a mesma pessoa: sem
filtro, R$ ···· de lazer entram na conta do aluguel. Mas ligar o filtro por
padrão quebraria os itens cuja categoria cadastrada **não é** a categoria em que
os lançamentos caem — o ANTHROPIC está em `Educação` e chega em `Outros`; o
estacionamento está em `Moto` e chega em `Vestuário`. Um item que deixa de casar
volta a ser contado duas vezes.

Então o filtro é escolha por item, e a tela **avisa** quando uma chave casa com
mais de uma categoria. Pergunta visível em vez de mentira silenciosa.

---

## `planejamento.py` — orçamento, simulação e projeção

### Orçado × real

Compara o gasto por grande categoria com a meta do mês. As faixas de cor:

| Situação | Quando |
|---|---|
| ok | até 80% da meta |
| atenção | 80% a 100% |
| estourou | acima de 100% |

Se o mês não tem orçamento próprio, herda o do mês mais recente que tiver — e,
se só houver orçamento em meses futuros, usa o mais antigo. Parece estranho
olhar para a frente, mas é o comportamento certo: o orçamento migrado da
planilha está em 2026-09, e sem essa regra todo mês anterior apareceria como
"sem meta".

### Projeção de caixa

Monta o mês futuro somando quatro coisas **já conhecidas hoje**:

```
+ salário previsto        (você informa, ou a média da receita recorrente)
− gastos fixos na conta   (boleto, Pix, débito)
− gastos fixos no cartão  (caem na fatura)
− parcelas do cartão      (as já contratadas)
− outras variáveis        (a MEDIANA do gasto variável recente)
```

#### Fixos separados por forma de pagamento

`fixos_conta` e `fixos_cartao` são **decomposição** de `fixos`, não
substituição: `fixos` continua sendo a soma dos dois, e `total_despesas`
continua sendo `fixos + parcelas_cartao + outras_variaveis`. Isso não é
detalhe de implementação — é o que mantém `conferir_imposto` passando sem
edição, porque ele refaz a projeção inteira pela fórmula antiga.

O que a separação responde: **`fixos_cartao + parcelas_cartao` é o quanto da
sua fatura já está vendida antes de você comprar qualquer coisa.** Para
set/2026, R$ ···· + R$ ···· = **R$ ····**. É o número de quem
quer fazer sobrar salário.

E o que a projeção soma de fixos **não é mais** `total_mensal` (o piso
cadastrado bruto), e sim a soma de `entra_na_previsao` de
`fixos.situacao_no_mes` — já sem o que a grade de parcelas projeta por outro
caminho. Por isso a tela de Gastos fixos e a de Planejamento mostram números
diferentes **de propósito**, e a diferença é sempre explicável item a item:

```
Gastos fixos ... R$ ····   (piso cadastrado)
Planejamento ... R$ ····   (entra na previsão)
diferença ...... R$   117,00   (a nutricionista, já nas parcelas)
```

#### A base da mediana não conta o que já é fixo

A base de "outras variáveis" excluía quem tem `tipo = 'Fixo'` no lançamento. Mas
`tipo` vem da regra de importação, e um item pode estar cadastrado como gasto
fixo enquanto seus lançamentos continuam chegando marcados `Variável` — foi o
caso do estacionamento, do ANTHROPIC e dos suplementos. Nesses casos o mesmo
gasto entrava nos **dois** lados: no cadastro de fixos e na média de variáveis.

A base agora exclui também tudo que casa com a `chave_historico` de um item
fixo **ativo**. `tipo` continua sendo um dos filtros; ele só deixou de ser o
único. **O cadastro é a fonte de verdade sobre o que é fixo; `tipo` é uma
pista.**

> Medido no dia da mudança: R$ ···· saíram da janela e a mediana **não se
> moveu** (R$ ···· antes e depois), porque os itens caíam nos meses
> extremos. A mudança é neutra hoje — e é isso que a torna segura. O valor dela
> é impedir que ela deixe de ser neutra quando esses itens aparecerem em três
> meses seguidos, o que somaria ~R$ ····/mês de despesa fantasma.

#### Por que mediana e não média

Em fevereiro você comprou uma **moto de R$ ····** num único Pix.

| Medida | Valor |
|---|---|
| Média de despesa mensal | R$ ···· |
| **Mediana** | **R$ ····** |

A média sobe R$ ···· por causa de um evento único, e a projeção passa a supor
que você compra uma moto todo mês — jogando o saldo de 12 meses cerca de
R$ ···· para baixo sem nenhum motivo real.

A mediana é o valor do meio: metade dos meses gastou mais, metade gastou
menos. Uma compra única gigante desloca a média, mas não move a mediana. Para
projetar o **mês típico**, é a medida certa.

> A média continua aparecendo no Dashboard, em "Médias e Tendência" — lá ela é
> útil justamente por incluir tudo o que aconteceu.

### A janela tem de ser a mesma dos dois lados (2026-08-23)

A receita usa `dados.meses_fechados()`, que descarta o mês em andamento — ele
tem a despesa contratada mas ainda não a receita inteira.

A despesa **não descartava**, e a assimetria puxava a projeção para o lado
otimista: um mês pela metade tem gasto pela metade, e entrava na mediana como
se fosse um mês inteiro barato.

> Quando duas metades da mesma conta filtram o período de jeitos diferentes, o
> resultado não é "mais ou menos certo" — é enviesado numa direção previsível.

---

### Os alertas

A projeção também escreve avisos em português: *"Em set/2026 as despesas
previstas passam a receita em R$ ····"*. Um número numa tabela é fácil de
não ver; uma frase é difícil de ignorar.

> Vinha das seções 1, 2 e 3 da aba `Planejamento`.

---

## `previsao.py` — o que falta acontecer no mês

A regra que manda aqui, pedida por ele em palavras: *"assim que as receitas ou
despesas vierem, que elas se abatam na previsão para não serem consideradas
2x"*. Então a previsão nunca é "o esperado do mês" — é sempre **o que falta**.

### O abatimento no total estava errado, e errava para o lado otimista

A conta era `max(0, esperado − já_realizado)` sobre o total. Isso funciona
enquanto os dois lados crescem juntos, e quebra quando **um balde estoura e o
outro não**:

> Você gastou R$ ···· em variáveis (a mediana era R$ ····) e ainda **não**
> pagou o aluguel.
>
> Fórmula global: `max(0, 10.158 − 8.000) = 2.158` → o mês fecharia em
> R$ ····
> Verdade: os R$ ···· de fixos ainda vão sair. O mês fecha perto de R$ ····

O estouro do variável "comeu" os fixos que ainda vão cair. E note a direção do
erro: ele sempre **subestima** a despesa. Num painel de finanças, errar para o
lado otimista é o pior lado.

### O abatimento por balde

```
fixos_a_pagar     = o que falta dos fixos (só situação 'previsto')
parcelas_a_vencer = parcelas.previsto_no_mes(...)   ← só o NÃO faturado

despesa_prevista  = fixos_a_pagar + parcelas_a_vencer
```

Desde 30/08/2026 a mediana do variável **não entra aqui** — ver *Só compromisso*
mais abaixo. O abatimento por balde continua valendo para o que restou, e
`baldes_do_mes` continua sendo a prova de que nada conta duas vezes.

`previsto_no_mes` e **não** `ja_contratado_para`: as parcelas herdadas já estão
dentro de `despesa_realizada`, e somá-las aqui as contaria duas vezes.

### O que garante que nada abate duas vezes

Uma coisa só: **os três baldes particionam a despesa realizada.** Todo
lançamento cai em exatamente um, pela mesma precedência que
`fixos.situacao_no_mes` usa do outro lado:

```
parcela  >  fixo  >  avulsa
```

A nutricionista é o caso que exige essa ordem — ela casa com chave de fixo
**e** é parcela. Com `parcela > fixo` nos dois lados, ela é contada uma vez, no
mesmo balde, nas duas contas.

`previsao.baldes_do_mes()` devolve os três totais e os três conjuntos de `id`, e
a checagem 12 de `conferir_previsao` exige, mês a mês:

```
parcela + fixo + avulsa  ==  total_despesa   (ao centavo)
nenhum id em dois baldes
```

Se essa prova passa, é **aritmeticamente impossível** abater o mesmo real duas
vezes. Repare que ela não pode exigir "igual a ontem": a fórmula mudou de
propósito, e o número sobe nos meses em que o variável estourou. Uma prova de
regressão exigiria o número; esta exige a **propriedade**.

### `composicao_do_mes` — cada real com nome e situação

Em 30/08/2026 o dashboard de setembro mostrava, na mesma tela, R$ ···· de
despesa e R$ ···· na quebra por categoria. Os dois números estavam certos e
respondiam perguntas diferentes — e **R$ ···· 82% da previsão, não
apareciam em lugar nenhum**: quatorze gastos fixos com nome e categoria, mais a
mediana das variáveis. A tela injetava só as parcelas.

A correção não foi somar mais um gráfico. Foi fazer o KPI ser a soma da lista:

```
composicao_do_mes(df, mes)["valor"].sum() == do_mes(df, mes)["despesa_total"]
```

Três blocos, que são exatamente as três parcelas que `do_mes` soma, montados com
as mesmas chamadas e os mesmos argumentos — a igualdade vale por construção, não
por coincidência (checagem 17):

| `situacao` | O que é | Vem de |
|---|---|---|
| `lançado` | já aconteceu | os lançamentos do mês |
| `parcela` | parcela contratada que vai cair | `parcelas.detalhe_futuro` |
| `previsto` | fixo cadastrado ainda não pago | `fixos.situacao_no_mes` |

### Só compromisso — a mediana saiu (30/08/2026)

A primeira versão trazia uma quarta linha, "Gasto variável estimado", com a
mediana dos últimos 6 meses. Ele pediu para tirar: *"Quero só o que de concreto
vai entrar na previsão, que são as parcelas + gastos fixos."*

É uma escolha de **significado**, não um conserto — as duas versões estavam
certas para perguntas diferentes:

| | Responde |
|---|---|
| com mediana | "quanto o mês provavelmente vai custar" |
| só compromisso | "quanto já está vendido antes de eu decidir nada" |

A segunda é a que se confere linha a linha: todo número tem um contrato ou um
cadastro atrás.

**O preço:** o saldo previsto ficou otimista. Setembro/2026 foi de −R$ ····
para +R$ ···· ao deixar de contar R$ ···· de gasto variável que a história
dele diz que vai acontecer. Um número que omite o variável **mente por omissão**
se a tela não avisar — por isso a tarja da seção diz, com todas as letras, que
gasto variável não está na conta e que o saldo é o melhor caso. **Essa tarja é
parte do cálculo, não enfeite.**

A mediana continua viva em `projecao_caixa`, na coluna `outras_variaveis`, e a
tabela item a item do Planejamento **nomeia a diferença** entre os dois totais
em vez de deixá-los discordar em silêncio.

**Linha negativa é permitida — mas só de um lado.** Os 111 lançamentos com
`natureza='Despesa'` e valor positivo (estornos de fatura, e dinheiro de
terceiros que caiu na mesma vala) viram linha negativa aqui, e têm de virar:
`despesa_total` já os abate, e recusá-los quebraria a soma. O que não pode
existir é **previsão** negativa — não existe conta fixa que devolve dinheiro.

### `mes_base` — por que a função precisa saber de onde se olha

A janela da mediana anda com a base: `outras_variaveis` vale R$ ···· olhando
de agosto e R$ ···· olhando de outubro. Uma tela que mostra setembro,
outubro e novembro lado a lado precisa dos três olhando do **mesmo ponto** —
senão novembro aparece como R$ ···· no dashboard e R$ ···· na aba de
projeção, que é a mesma doença recriada entre duas telas.

Omitido, `mes_base` vale `mes − 1`, reproduzindo `do_mes` exatamente. Quem
mostra vários meses passa o mesmo valor para todos (checagem 18).

### A coluna `fixo` — seguir o mesmo gasto entre os meses

O pedido era: *"quando efetivamente houver o pagamento, ele vai continuar sendo
considerado no saldo do mês, mas em vez de ser previsão será algo já pago"*.

A situação já mudava sozinha. Mas o **nome mudava junto**: em setembro a linha
se chama "Aluguel"; em agosto, depois de paga, virava "Pix enviado para Eduardo
Moreira de Lima". O total fechava e ainda assim era impossível seguir o
mesmo gasto de um mês para o outro.

Então `item` continua sendo a verdade crua do extrato — trocar isso esconderia o
que o banco escreveu — e `fixo` diz a que item do cadastro aquele lançamento
pertence. Usa `casar_no_historico`, a **mesma** regra que decide se um fixo já
foi lançado: se as duas divergissem, um item poderia aparecer como `previsto` e
ao mesmo tempo ter lançamento apontando para ele (checagem 19).

---

## `patrimonio.py` — quanto você tem e por quanto tempo dura

### A pergunta certa

Não é "quanto eu tenho?" — é **"por quantos meses eu aguento sem renda?"**.

R$ ···· parados não significam nada isolados. Para quem gasta R$ ···· por
mês são 12 meses de tranquilidade; para quem gasta R$ ····, menos de três.
Por isso a reserva é medida em **meses de despesa**.

E a despesa usada é a **mediana**, pelo mesmo motivo da projeção.

### De onde vem cada número

**Saldo em conta** — duas fontes, nesta ordem de preferência:
1. o que você digitou (tabela `patrimonio_mensal`);
2. o **último saldo do extrato** daquele mês (coluna `saldo_apos`), que o
   próprio banco informou na importação.

A segunda fonte é o que faz isso funcionar sem trabalho manual: se você
importa o extrato, o saldo se atualiza sozinho.

**Saldo aplicado** — estimado, acumulando:

```
aplicado(mês) = aplicado(mês anterior) + aportes − resgates + rendimentos
```

Os aportes e resgates são os lançamentos de natureza `Investimento`, que agora
têm sinal correto (a correção feita na migração). Você pode sobrescrever
qualquer mês digitando o saldo real da corretora.

### As duas leituras de patrimônio

Parte do dinheiro que passa pela sua conta **não é seu**: é emprestado, e você
faz a gestão. Ele entra como natureza `Transferência` (categoria
`Investimentos Bruno`), então nunca contou como receita nem como despesa.

Mas isso sozinho não bastava. O dinheiro **fica na carteira**, investido junto
com o seu — e o patrimônio aparecia maior do que é. Daí as duas colunas:

```
patrimonio_total    saldo em conta + aplicado          (inclui terceiros)
capital_terceiros   soma ACUMULADA da categoria do pote
patrimonio_proprio  patrimonio_total − capital_terceiros
```

O acumulado importa: uma entrada de 2024 continua sob sua gestão em 2026, até
ser devolvida. Uma devolução entra negativa e reduz o saldo do pote.

| Leitura | Responde |
|---|---|
| `patrimonio_total` | quanto eu administro |
| `patrimonio_proprio` | quanto é meu |

**A reserva de emergência sai do `patrimonio_proprio`.** Esse é o ponto em que
a distinção deixa de ser estética: contando o dinheiro dos outros, a tela dizia
que a reserva cobria 14,7 meses; o número verdadeiro é bem menor. Numa
emergência esse dinheiro pode precisar voltar — e é justamente aí que a
diferença apareceria.

#### O pote é tão bom quanto a classificação que o alimenta (2026-08-23)

Em agosto/2026 duas TED de R$ ···· para `Bruno da Silva Silva` estavam
dentro do pote, tratadas como devolução do capital administrado. Não eram: eram
**o repasse de um seguro que o pai dele tinha a receber** — e uma delas nem
chegou (foi para a conta errada e voltou).

O efeito de duas linhas classificadas errado:

| | Errado | Certo |
|---|---|---|
| capital de terceiros | R$ ···· | **R$ ····** |
| patrimônio próprio | R$ ···· | **R$ ····** |
| reserva cobre | 11,1 meses | **8,3 meses** |

**Duas linhas moveram a reserva em 2,8 meses.** É o preço de um número que
depende de um saldo acumulado: erro não se dilui com o tempo, ele fica.

Na mesma leva, os R$ ···· que a seguradora pagou estavam como
`Receita Extraordinária` — receita dele. Agosto ia de **+R$ ····** para
**−R$ ····** quando isso saiu. A regra que decide é sempre a mesma:
*renda é só o que ficou na conta*, e aqui a saída era separável (uma TED
identificável), logo é `Transferência`.

> Ver `CHANGELOG.md`, 2026-08-23 — "A conta internacional que o app não
> enxergava".

Quando não há dinheiro de terceiros, a tela mostra "Patrimônio total" como
sempre, sem a distinção. Mostrar as duas leituras iguais seria só ruído.

> Vinha da aba `Patrimônio`.

---

## Parcelas: o que conta como "a vencer"

Duas condições, e as duas custaram um bug para aparecer:

1. **ainda faltam parcelas** (`parcela_total − parcela_atual > 0`);
2. **a última cai no futuro** (`mes_termino >= mês corrente`).

A segunda parece redundante e não é. Um parcelamento cujas parcelas restantes
estavam todas no passado continuava listado como "em aberto" — porque "faltam
parcelas" era a única checagem.

### Compra estornada não tem parcela a vencer

Quando uma compra parcelada é cancelada, o banco lança o estorno como uma
linha positiva de mesmo valor, sem parcela:

```
17/10/2025  VIA LASER SERVICO  R$  65,74  "1 de 5"   <- a compra
17/10/2025  VIA LASER SERVICO  R$ -65,74  "-"        <- o estorno
```

As parcelas 2/5 a 5/5 nunca chegam. Sem essa checagem, o app projetava
R$ ···· de parcelas a vencer para uma compra que não existe mais.

O par é reconhecido por **descrição + mês + valor absoluto**, comparado em
centavos inteiros — comparar floats daria `65.74 != 65.740000000000002` e a
regra nunca dispararia.

---

## Dinheiro que voltou: estorno × transferência

Quando alguém te devolve dinheiro, há **duas** situações diferentes, e usar o
tratamento errado deixa um dos lados inflado.

### A pergunta que decide: a saída é separável?

| | A despesa inteira era de outro | Parte da SUA despesa voltou |
|---|---|---|
| Exemplo | cartão adicional, assinatura que você só administra | racha de conta, compra contestada, reembolso do plano de saúde |
| A saída é | uma linha própria, identificável | uma transação só, que não dá para partir |
| Tratamento | `Transferência` nos dois lados | **estorno**: `Despesa` com valor POSITIVO |
| Efeito | sai da receita e da despesa | **abate** a despesa no mês |

**Por que o racha não pode ser `Transferência`.** Você pagou R$ ···· de um
jantar e três amigos devolveram R$ ···· Se a devolução virar transferência, a
receita cai (certo) mas a despesa continua marcando R$ ···· (errado) — seu gasto
real foi R$ ···· Como a saída é uma transação só, a única forma de corrigir é
o retorno **abater** a despesa.

### Como o abatimento funciona

Graças à convenção de sinal — negativo sai, positivo entra — não é preciso
mecanismo nenhum:

```
despesa do mês = −(soma de natureza 'Despesa')
```

Uma linha de `Despesa` com valor **positivo** entra nessa soma com o sinal
trocado e reduz o total. É a mesma coisa que a fatura já fazia com estornos de
compra: o cartão lança o crédito na própria fatura, e ele nasce natureza
`Despesa`.

> Esta é a segunda vez que a convenção de sinal paga por si mesma. A primeira
> foi "quanto sobrou é literalmente a soma da coluna"
> ([02 · Banco de dados](02_banco_de_dados.md)). Escolhas de representação
> simples continuam rendendo muito depois de tomadas.

### O caso que provou a regra

Sete lançamentos de **"Crédito em confiança/provisório"** — o crédito que o
banco lança dentro da fatura quando você contesta uma cobrança — estavam como
`Receita`. Somavam R$ ····

Esse número já era conhecido: era exatamente o resíduo dos três meses que não
fechavam na reconciliação competência × caixa.

| Mês | Os créditos | O resíduo |
|---|---|---|
| nov/2025 | R$ ···· | R$ ···· |
| dez/2025 | R$ ···· | R$ ···· |
| jan/2026 | R$ ···· | R$ ···· |

Reclassificados como estorno, a reconciliação passou a fechar ao centavo em
**30 dos 30 meses**.

---

## As duas leituras do PLR

Ele recebe PLR **duas vezes por ano**, em fevereiro e agosto. Isso distorce
qualquer leitura mensal: o mês do bônus parece extraordinário e os outros
parecem magros, quando aquele dinheiro é remuneração do ano inteiro.

```
COMO ENTROU   fev/2026 com R$ ···· e jul/2026 com R$ ····
RATEADO       os mesmos meses com R$ ···· e R$ ····
```

Nenhuma das duas é "a certa" — são perguntas diferentes. A primeira responde
*"quanto caiu na conta?"*, a segunda *"quanto eu ganho?"*. Por isso o painel
mostra as duas em abas.

### Uma visão não pode ser um fato

Até 2026-08-23 o rateio existia como **12 lançamentos gravados**, herdados da
planilha. Como o PLR original também estava lá, os mesmos R$ ····
contavam duas vezes na receita — 12% de receita fantasma, e a taxa de poupança
de 2026 aparecia como 41,4% quando era 29,2%.

O fato é o dinheiro que entrou. O rateio é uma forma de olhar para ele, e
agora é calculado em `kpis.serie_rateando_plr()`.

### Só a categoria `PLR` é rateada — e quem marca é você

Não toda receita extraordinária. Há R$ ···· da Caixa Previdência e
R$ ···· da Porto Seguro marcados como extraordinários, e esses são **eventos
únicos**: continuam aparecendo no mês em que caíram, nas duas leituras.

E não existe regra de valor adivinhando o que é PLR. Um limiar de "acima de X"
erraria nos dois sentidos, e classificar R$ ···· errado estraga o ano
inteiro em silêncio. A marcação é manual, na tela de Lançamentos.

A conta fecha: rateado + o que cai depois do fim dos dados = o total como
entrou, no centavo.

---

## O mês em andamento não entra em média nenhuma

Um mês que ainda não acabou tem a despesa contratada mas **não a receita
inteira**. Em 23/08/2026 agosto mostrava R$ ···· de receita recorrente,
porque o salário cai dia 24 e o extrato ia até dia 19.

Esse mês contaminava quatro cálculos diferentes, cada um com o seu próprio
filtro (ou sem filtro nenhum):

| Onde | Estragava |
|---|---|
| mês padrão do painel | abria em setembro, com 243,5% de comprometimento |
| taxa de poupança | −143,5% num mês, média do período de +11% para −15% |
| comparativo anual | rebaixava o ano corrente |
| projeção de caixa | receita prevista R$ ···· em vez de R$ ···· |

Agora existe **um só** filtro, `dados.meses_fechados()`, com dois testes:
tem movimento de verdade (≥ 5 lançamentos) **e** já terminou. Use-o sempre
que uma conta olhar para o histórico.

---

## `metas.py` — objetivos e o aporte que exigem

A conta central é simples:

```
aporte_necessario = (valor_alvo − já_acumulado) ÷ meses_restantes
```

O valor do módulo não está na fórmula, e sim em cruzar isso com a sua
**capacidade real** de poupar (que vem da projeção de caixa) e dizer, sem
rodeio, quais prazos são possíveis e quais não são.

### O número mais honesto: a data prevista real

Existem duas datas para cada meta:

- **prazo desejado** — a data que você escolheu;
- **data prevista** — quando você chega lá **no ritmo atual**.

Se você define R$ ····/mês para uma meta de R$ ····, a data prevista fica a
14 anos de distância, mesmo que o prazo desejado diga 2. Mostrar as duas lado
a lado é o que transforma uma lista de desejos num plano.

> Vinha da aba `Metas`.

---

## `compras.py` — a lista de desejos

Item caro não é compra, é projeto. Acima do valor de corte (R$ ···· por
padrão), um item deixa de ser "compro quando der" e passa a exigir um plano de
poupança — ou seja, vira meta. A função `promover_para_meta()` faz essa
passagem com um clique.

> Vinha da aba `Futuras Compras`.

---

## `financiamento.py` — PRICE e SAC

### Os dois sistemas, em uma frase cada

**PRICE** — a prestação é sempre a mesma. No início quase tudo é juro e quase
nada abate a dívida; isso vai se invertendo. Previsível, mas paga mais juros.

```
prestacao = saldo × [ i ÷ (1 − (1+i)^−n) ]
```

**SAC** — a amortização é sempre a mesma. A prestação começa alta e vai
caindo, porque o juro incide sobre um saldo cada vez menor. Paga menos juros
no total, mas exige mais folga no começo.

```
amortizacao = saldo_inicial ÷ n
prestacao   = amortizacao + juro_do_mes
```

No seu cenário (R$ ···· financiados, 360 meses, 10,5% a.a.):

| Sistema | 1ª prestação | Última | Total de juros |
|---|---|---|---|
| PRICE | R$ ···· | R$ ···· | R$ ···· |
| SAC | R$ ···· | R$ ···· | R$ ···· |

O SAC economiza R$ ···· em juros, mas exige R$ ···· a mais na primeira
prestação. A pergunta prática é: você aguenta a prestação inicial sem apertar?

### A conversão da taxa muda muito dinheiro

O contrato diz "10,5% ao ano". Isso vira quanto ao mês?

| Método | Conta | Resultado |
|---|---|---|
| Equivalente (efetiva) | (1 + 0,105)^(1/12) − 1 | **0,8355% a.m.** |
| Linear (nominal/12) | 0,105 ÷ 12 | 0,8750% a.m. |

Parece pouca diferença, mas em 360 meses dá dezenas de milhares de reais. Os
bancos brasileiros costumam usar a **equivalente** em contratos de imóvel.

### Os custos que quase todo simulador esconde

| Custo | Incide sobre |
|---|---|
| MIP (morte e invalidez) | o **saldo devedor** — cai com o tempo |
| DFI (danos ao imóvel) | o **valor do imóvel** — fixo |
| Taxa de administração | valor fixo por mês |

Por isso a tela separa:

- **prestação** = juros + amortização (o que o contrato cobra de dívida)
- **desembolso** = prestação + seguros + taxa + aporte extra (o que sai da sua
  conta de verdade)

No seu cenário a diferença é de R$ ····/mês — 11% a mais do que a prestação
sozinha sugere.

### A conferência matemática

```
soma das amortizações = R$ ····  =  valor financiado  ✓
saldo final da última parcela = R$ ····  ✓
```

> Vinha da aba `Financiamento`.

---

## Como conferir qualquer cálculo

O padrão é sempre o mesmo — importe, carregue os dados, chame a função:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import dados; from financas.calculos import kpis; df = dados.carregar_lancamentos(); p = kpis.painel(df, '2026-08'); [print(k, v) for k, v in p['resultado'].items()]"
```

E, para conferir tudo de uma vez contra a planilha:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m migracao.conferir
```
