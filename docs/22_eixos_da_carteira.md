# 22 · Os eixos da carteira: a mesma carteira, cortada de outro jeito

> "Seleciono renda fixa, como está a divisão IPCA+ curto, médio, longo,
> liquidez diária?"

Arquivos: [`financas/calculos/investimentos.py`](../financas/calculos/investimentos.py)
(`DIMENSOES`, `balde_de`, `balde_de_prazo`, `alocacao_atual`),
[`ui/graficos.py`](../ui/graficos.py) (`rosca_alocacao`),
[`paginas/investimentos.py`](../paginas/investimentos.py).
Prova: [`verificacao/conferir_dimensoes.py`](../verificacao/conferir_dimensoes.py).

---

## 1. Eixo, não nível

O app já tinha dois níveis: **macro** (Renda Fixa, Renda Variável) e **classe**
(NTN-B, ETF, Ação BR), um dentro do outro. O que faltava não era um terceiro
nível — era outro **eixo**.

Um NTN-B ago/2045 é, ao mesmo tempo:

| Eixo | Onde ele cai |
|---|---|
| macro | Renda Fixa |
| classe | NTN-B (inflação) |
| tema | *(vazio — renda fixa não tem exposição temática)* |
| prazo | IPCA+ Longo |
| indexador | IPCA+ |
| liquidez | No vencimento |

Nenhum contém o outro. São perguntas diferentes sobre a mesma carteira.

Isso é o que faz o **tema** funcionar: "Datacenters" pode conter uma ação
americana, um REIT e um ETF ao mesmo tempo. Como filho da classe, "Datacenters"
precisaria existir três vezes, e somar exposição viraria conta à mão; como eixo,
existe uma vez.

### O que não precisou ser construído

`alocacao_atual(nivel=…)` já era parametrizada. Toda a máquina em volta —
metas, desvio, `dentro_faixa`, classe com meta e sem dinheiro — continuou
valendo de graça; a mudança foi trocar o `if nivel == "macro"` por uma chamada
a `balde_de(papel, eixo)`.

Metas de alocação só existem para macro e classe. Nos eixos derivados a tabela
vem com `tem_meta = False`, e a tela esconde as colunas de meta. "Quanto quero
ter em IPCA+ Longo" é uma pergunta legítima — só não é a que este cadastro
responde hoje, e inventar um alvo vazio seria pior que não ter.

---

## 2. As faixas de prazo, e a ordem que decide tudo

Nada disso pede um campo novo: sai de `indexador`, `data_vencimento` e
`liquidez`, que o cadastro já guarda.

```
1. renda variável não tem prazo  -> "Sem prazo (renda variável)"
2. liquidez diária vence tudo    -> "Liquidez diária"
3. tem vencimento                -> faixa pelo tempo que falta
4. resto                         -> "Sem vencimento definido"
```

**A ordem é o desenho, e as duas primeiras regras são as que erram.**

A regra 2 vem antes da 3 porque um CDB com liquidez diária e vencimento em 2027
é dinheiro disponível **hoje** — o vencimento só diz até quando ele rende, não
quando você alcança o dinheiro.

A regra 1 vem antes da 2 porque **ação tem `liquidez = "Diária"` no cadastro**.
Sem essa precedência, a carteira inteira de ações apareceria como "Liquidez
diária", ou seja, como reserva de emergência. Ação é líquida e não é reserva: o
preço no dia do resgate é que decide.

As faixas, em anos até o vencimento: **Curto** até 3, **Médio** 3 a 8,
**Longo** 8 a 20, **Ultra longo** acima de 20. O corte em 20 existe porque um
NTN-B 2060 tem mais que o dobro da duration de um 2035 — juntá-los num balde
"longo" esconderia a diferença que mais importa.

### A régua é o mês olhado, não `hoje`

```python
referencia = cambio.ultimo_dia_do_mes(mes) if mes else date.today()
```

O mesmo NTN-B ago/2032 é **Longo** visto de 2020, **Médio** visto de 2026 e
**Curto** visto de 2031. Usar `hoje` faria a tela de um mês passado classificar
os papéis com a régua de agora — e o gráfico de evolução mentiria.

`conferir_dimensoes.py` trava exatamente isso: se o mesmo papel não mudar de
faixa entre 2020, 2026 e 2031, a checagem falha.

### O rótulo leva o indexador junto

"Longo" sozinho não diz o que o papel faz. `IPCA+ Longo` e `Prefixado Longo`
são apostas opostas sobre inflação, com o mesmo prazo.

---

## 3. Nada some — a checagem que vale mais que olhar

Um papel que caia fora de todo balde não quebra nada: o gráfico continua
bonito, e o total fica menor que a carteira. Ninguém repara que faltam R$ ····
numa pizza.

Por isso a checagem principal não é "está bonito", é **a soma bate**:

```
macro         4 baldes, somam R$ ····
classe        8 baldes, somam R$ ····
tema          3 baldes, somam R$ ····
prazo         6 baldes, somam R$ ····
indexador     5 baldes, somam R$ ····
liquidez      2 baldes, somam R$ ····
```

É também por isso que `balde_de` **nunca devolve vazio**: papel sem informação
vira `(sem indexador)` e continua somando. Sumir da conta seria pior que
aparecer mal classificado.

---

## 4. A posição vem antes da meta

A aba de Rebalanceamento mostrava, para quem não tinha meta cadastrada, apenas
o aviso "cadastre suas metas de alocação". Nada mais — nem a carteira que a
pessoa tem.

Mas "como estou hoje" é a metade da pergunta que **não depende de nada**. Agora
as duas roscas aparecem sempre: a **ideal** (que fica em branco convidando a
cadastrar) e a **minha carteira** (que sempre funciona). O cálculo do aporte
continua exigindo metas, porque esse sim precisa delas.

`rosca_alocacao(nomes, valores)` é genérica de propósito: serve às duas roscas
do rebalanceamento e à do drill-down. `carteira_por_tipo` já desenhava uma
rosca, mas amarrada às colunas `tipo`/`saldo` — duas funções quase iguais
divergiriam no dia em que uma ganhasse um acabamento.

### O olhinho

A rosca mostra **percentual** nas fatias e o total em R$ no buraco. Com o
olhinho ligado, o percentual fica (não revela quanto você tem) e o total do
meio é mascarado, porque é anotação de layout e passa por `texto()`. Ver
[docs/15](15_o_olhinho.md).

---

## 5. O tema, e por que ele é digitado à mão

O eixo **tema** é o que responde "IREN é o quê, datacenter?". Ele é uma coluna
em `investimentos` (migração 22) mais a tabela `temas_ativo`, editável na aba
**Manutenção → Cadastro**.

Entrar em `DIMENSOES` foi literalmente acrescentar `"tema"` à tupla: o
drill-down, as roscas e o `balde_de` genérico passaram a funcionar com ele sem
nenhuma linha a mais. É o que o desenho de eixo prometia.

### A razão de ser manual está na tela, ao lado do campo

O app já guarda os fundamentos do yfinance. Para os três tickers dele:

| Ticker | O que o provedor diz |
|---|---|
| IREN | `Financial Services · Capital Markets` |
| DGXX | `Utilities · Utilities - Independent Power Producers` |
| IRE | *(sem fundamento guardado)* |

A IREN é uma mineradora de bitcoin que virou datacenter de IA. O provedor a
classifica pela **natureza contábil** da empresa, e acerta nesse critério — só
que esse não é o critério de exposição. Preencher o tema com isso classificaria
a carteira com confiança e errado.

Então `sugestao_de_tema()` devolve **texto**, e a tela o mostra numa coluna
travada chamada "O provedor diz", ao lado do campo "Tema". Você compara e
decide. A função nunca vai à rede — ela roda a cada desenho da tabela.

`conferir_dimensoes.py` tem uma checagem só para essa tentação: um papel **com**
ticker e **sem** tema digitado tem de cair em `(sem tema)`, nunca herdar o setor
do provedor.

### Remover um tema em uso não é permitido

O editor de temas recusa salvar se algum tema removido da lista ainda estiver
apontado por um papel. Sem isso, aquele papel ficaria com um valor fora da lista
e a caixa de seleção apareceria vazia, sem explicar por quê.
