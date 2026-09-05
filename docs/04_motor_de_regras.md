# 04 · O motor de regras

Arquivos do código: [`financas/regras.py`](../financas/regras.py) e
[`financas/importador.py`](../financas/importador.py)

---

## O problema

O banco manda `"DL*UBERRIDES"` ou `"Pix enviado para Raia Drogasil S/A"`. Você
quer ver **Transporte** e **Saúde**. Categorizar 500 linhas na mão todo mês
não é sustentável.

A solução (a mesma da planilha, que já tinha 148 regras) é uma **lista de
regras** lida de cima para baixo.

---

## A regra de ouro: a ordem importa

> As regras são lidas **de cima para baixo** e a **primeira que casar vence**.
> As de baixo nem chegam a ser testadas.

Isso não é detalhe técnico — é a lógica em si. Exemplo real do seu extrato:

| Ordem | Palavra-chave | Valor mín. | Sentido | Vira |
|---|---|---|---|---|
| 5 | XP EMPREGADORA | R$ ···· | Entrada | **PLR** (Receita Extraordinária) |
| 6 | XP EMPREGADORA | R$ ···· | Entrada | **Salário** (Receita) |

Um depósito de R$ ···· não atinge os R$ ···· então pula a regra 5 e cai na
6 → Salário. Um depósito de R$ ···· atinge, então para na regra 5 → PLR.

**Se você inverter a ordem, os dois viram Salário** — porque a regra genérica
casaria primeiro e a específica nunca seria testada. O painel perderia a
distinção entre receita normal e extraordinária, e fevereiro pareceria um mês
comum de R$ ···· de receita.

> **Regra prática:** específica em cima, genérica embaixo.

---

## Dois tipos de regra

### Regras da fatura — simples

Só a palavra-chave importa:

```
"DROGA"  →  categoria "Saúde", tipo "Variável"
```

A **natureza** não vem da regra: ela é deduzida da categoria escolhida, usando
a coluna `natureza_padrao` do cadastro de categorias. Assim você configura
"Pagamento de Fatura é natureza Pagamento" **uma vez**, em Configurações, e
todas as regras que apontam para essa categoria herdam isso.

### Regras do extrato — mais espertas

No extrato a mesma palavra pode significar coisas diferentes, então a regra
olha três coisas:

| Campo | Pergunta |
|---|---|
| `palavra_chave` | está na descrição? |
| `valor_min_abs` | o valor absoluto atinge o mínimo? |
| `sinal` | o sentido bate? (Entrada / Saída / Ambos) |

E define categoria, tipo **e natureza**.

Outro exemplo real, com o mesmo nome virando coisas opostas:

| Palavra | Sentido | Vira |
|---|---|---|
| Carla | Entrada | Família / **Receita** |
| Carla | Saída | Família / **Despesa** |
| Associação | Saída | Família / **Despesa** |
| Pedro Ribeiro | Entrada ≥ R$ ···· | Reembolso / **Transferência** |

#### O `valor_min_abs` em uso: o pote de terceiros

O caso que mostra para que serve o valor mínimo. Parte do dinheiro que passa
pela sua conta é **emprestado, e você faz a gestão** — ele não é renda sua nem
patrimônio seu. Mas o mesmo remetente também manda valores pequenos, do dia a
dia, que são receita normal.

| Ordem | Palavra-chave | Mínimo | Sinal | Vira |
|---|---|---|---|---|
| 5 | `OLIVIA LOPES SILVA` | — | Ambos | Investimentos Bruno / Transferência |
| 6 | `BRUNO DA SILVA SILVA` | — | **Saída** | Família / Despesa |
| 7 | `ANA DO NASCIMENTO SILVA` | — | Ambos | Transferência / Transferência |
| 40 | `TED recebida` | — | Entrada | Outras Receitas / Receita |

Repare nas **ordens baixas**. A regra genérica `TED recebida` está na ordem 40;
se as específicas viessem depois dela, nunca seriam alcançadas — a primeira que
casa vence.

E um detalhe que evitou um erro: a regra usa `BRUNO DA SILVA SILVA`, o nome
completo. Existe um `Bruno Moreira Lima Simas` nos seus extratos, que é outra
pessoa e seria capturado por uma regra escrita só como "BRUNO".

#### Por que a regra 6 mudou em 2026-08-23

Ela mandava **tudo acima de R$ ····** para o pote de terceiros, nos dois
sentidos. Parecia certo enquanto se acreditava que uma TED grande para o
Bruno fosse devolução do capital administrado.

Não era. As duas TED de R$ ···· de agosto/2026 eram **o repasse de um seguro
que o pai dele tinha a receber** — dinheiro que passou pela conta e saiu. E
delas, só uma chegou: a primeira foi para a conta errada e voltou
(`TED devolvida`).

O estrago de deixar como estava seria duplo: as saídas ao pai **esvaziavam o
pote** (o capital da Olivia aparecia R$ ···· menor do que é), e a reserva de
emergência ficava 2,8 meses mais otimista do que a realidade.

Hoje a regra:

- vale **só na saída** — o que entra do pai mantém o comportamento antigo;
- não tem mínimo — qualquer valor enviado é gasto com família;
- aponta para **`Família`**, o balde que existe justamente para isso. Foi ele
  quem escolheu esse nome em vez de `Carla`, para caber gasto futuro com o pai.

Quando a saída for repasse (dinheiro de terceiro passando), ele marca
`Transferência` na mão — o caso é raro e a regra não tem como adivinhar.

**A lição geral: uma regra que decide pelo VALOR está apostando que valor alto
significa sempre a mesma coisa.** Aqui não significava.

O que o pote alimenta está em
[05 · Cálculos](05_calculos.md#as-duas-leituras-de-patrimônio).

---

### A natureza não vem da regra — vem da categoria

Numa linha de **fatura**, a regra escolhe só a categoria e o tipo. A natureza é
deduzida depois, pela coluna `natureza_padrao` do cadastro de categorias:

```python
# classificar_fatura()
natureza=regras.natureza_por_categoria.get(categoria, config.NATUREZA_DESPESA)
```

Repare que `regras_fatura` nem **tem** coluna `natureza` — é proposital. Você
configura *"Pagamento de Fatura é natureza Pagamento"* uma vez, em
Configurações, e todas as regras que apontam para essa categoria herdam.

Foi isso que resolveu o Wellhub do Pedro em 23/08/2026 com uma linha em vez de
uma manutenção mensal: a categoria **`Reembolso`** passou a ter
`natureza_padrao = 'Transferência'`. Faz sentido pela própria palavra —
reembolso é dinheiro que voltou, nunca renda.

> **A pergunta que decide onde configurar algo:** isso vale para *esta regra*
> ou para *tudo que cair nesta categoria*? Se vale para a categoria, configure
> na categoria — senão você repete a mesma decisão em cada regra nova e uma
> hora esquece uma.

---

### A armadilha do acento: `UPPER()` do SQLite ≠ `.upper()` do Python

```sql
UPPER('Pedrao')  ->  'PEDRAO'     certo
UPPER('Pedrão')  ->  'PEDRãO'     o "ã" passa batido
```

**O `UPPER()` do SQLite só conhece ASCII.** Então esta linha, que existiu neste
projeto até 23/08/2026, nunca casava com nada acentuado:

```python
# ERRADO: o Python manda %SAÚDE%, o banco tem SAúDE guardado
banco.consultar("SELECT ... WHERE UPPER(descricao) LIKE ?", (f"%{p.upper()}%",))
```

A correção foi tirar a comparação do SQL e usar `normalizar_texto()` — a mesma
função que o motor de regras usa, que remove o acento **antes** de comparar. É
por isso que ela existe, e é por isso que as duas pontas têm de passar por ela.

> **A regra geral:** quando uma comparação atravessa a fronteira Python↔SQL,
> decida de que lado ela mora e deixe **só um lado** normalizando. Funções de
> mesmo nome em linguagens diferentes não fazem a mesma coisa.

---

### Quando quem USOU o cartão decide a categoria

As duas seções acima olham a **descrição**. Isso não resolve um caso real: o
cartão adicional que sua mãe usava.

Ela comprava de farmácia a restaurante — as 522 compras estavam espalhadas por
Saúde, Alimentação, Compras, Vestuário. **Nenhuma palavra-chave separa as
compras dela das suas**, porque as descrições são as mesmas. O que separa é a
coluna `portador`, que a fatura sempre trouxe e que nenhuma regra olhava.

```python
regras.definir_portador_categoria("CARLA", "Família")
```

Três decisões de desenho:

| Decisão | Por quê |
|---|---|
| O mapa fica em `parametros`, não no código | acrescentar outro portador sem mexer em Python |
| Roda **depois** da classificação normal | o portador sobrescreve o que a descrição disse |
| Guarda `regra = "portador: CARLA T N SILVA"` | você vê na importação por que foi parar ali |

**Por que o destino é `Família` e não um nome de pessoa.** A primeira versão
mandava para uma categoria `Carla`. Funcionava, e envelhecia mal: uma categoria
com nome de pessoa não recebe mais ninguém. `Família` recebe o pai dele, recebe
o que vier, e mantém o histórico junto em vez de deixá-lo isolado.

**O que se perde:** a categoria deixa de dizer *o que* foi comprado. O dado não
some — continua na descrição, e o `portador` continua gravado linha a linha.
Foi assim que um relatório de `analises/` reconstruiu uma conta-corrente
inteira mesmo depois de tudo virar `Família`: **o recorte dele era pelo
portador, não pela categoria**.

Essa é a vantagem de guardar o fato numa coluna em vez de embutir na
classificação. A categoria é uma *decisão*, e decisões mudam; o portador é um
*fato*, e fatos não.

---

## Como a comparação é feita

Os dois lados passam por `normalizar_texto()`:

- vira MAIÚSCULO
- perde os acentos
- espaço duplo vira simples

Assim `"Drogaria Tamoio"`, `"DROGARIA  TAMOIO"` e `"drogaria tamoio"` viram
todos `"DROGARIA TAMOIO"`, e a comparação casa.

Depois é um simples **"a palavra-chave está contida na descrição?"**.

> **Não usamos expressão regular de propósito.** Você vai cadastrar regras na
> tela, e "contém" é uma ideia que qualquer pessoa entende sem aprender
> sintaxe nova.

---

## Quando nenhuma regra casa

O sistema não desiste — ele dá o melhor palpite possível:

- **Na fatura:** categoria `Outros`, tipo Variável, natureza Despesa.
  Praticamente tudo que passa no cartão é gasto.
- **No extrato:** o sinal já diz muita coisa. Entrou dinheiro → `Outras
  Receitas`. Saiu → `Outros` / Despesa.

E a coluna `regra` fica vazia, o que faz a linha aparecer no filtro
**"Só sem regra"** da tela de importação — para você conferir.

---

## Como está hoje, nos seus dados

Medido em **2026-08-23**, rodando o próprio classificador sobre a base inteira:

| Origem | Regras ativas | Cobertura |
|---|---|---|
| Extrato | 82 | **99,7%** (699 de 701) |
| Fatura | 208 | **85,8%** (2.643 de 3.079) |

O número de regras dobrou desde a migração (eram 41 e 104), e não foi à mão: é
a tela de **Triagem** trabalhando. Cada decisão que você toma lá vira regra, e a
cobertura da fatura subiu de ~77% para 85,8%.

Os ~14% que caem em "Outros" são uma **cauda longa real**: lojas onde você
comprou uma ou duas vezes. Ao conferir, a maioria delas você mesmo tinha
marcado como "Outros" na planilha — não é falha do motor.

> **Como refazer esta medição** (os números acima envelhecem sozinhos):
> ```bash
> .venv\Scripts\python -c "from financas import banco, regras, config; cj=regras.carregar_regras(); [print(o, sum(1 for l in banco.consultar('SELECT descricao,valor FROM lancamentos WHERE origem=?',(o,)) if regras.classificar(dict(descricao=l['descricao'],valor=l['valor'],origem=o),cj).automatica)) for o in ('Extrato','Fatura')]"
> ```

### Regra morta: quando a de cima engole a de baixo

A ordem tem um efeito colateral que só aparece medindo. Hoje existe uma regra
`FERNANDOREIS → Família` na ordem **225** que **nunca dispara**, porque outra
`FERNANDOREIS → Serviços` está na ordem **64**. A primeira que casa vence.

Isso acontece quando você resolve algo na Triagem que já tinha regra antiga. É
inofensivo em volume, mas significa que a sua decisão mais recente não é a que
vale. `testar_contra_historico()` existe para achar exatamente isso: a regra
morta aparece com **0 acertos**.

---

## As ferramentas que a planilha não tinha

> **Triagem e Sugestões parecem a mesma coisa e resolvem problemas opostos.**
> `sugerir_regras()` **aprende com o que você já classificou** — não serve
> quando não há decisão passada (nos dados de 2024–2025 devolveu 139 sugestões
> dizendo "Outros → Outros"). A **triagem não aprende nada**: só organiza o
> trabalho e deixa a decisão com você, na ordem em que ela rende mais.

### 1. Testar contra o histórico

Roda todas as regras contra os lançamentos já gravados, **na ordem real**, e
mostra quantos cada uma pegaria. Serve para três coisas:

- achar **regra morta** — cadastrada, mas que nunca casa (talvez a loja mudou
  de nome no extrato);
- achar **regra canibal** — uma genérica lá em cima engolindo o que deveria
  cair numa específica mais abaixo;
- conferir antes de mexer — você vê o efeito de reordenar sem reimportar nada.

Na tela: **Regras → aba Testar**.

### 0. Triagem — resolver o que caiu em "Outros"

A ferramenta mais útil quando você acabou de importar um monte de arquivo
antigo. Ela **não adivinha nada**: junta as linhas soltas por estabelecimento e
ordena por quanto pesam, para você decidir uma vez e resolver muitas linhas.

O ganho está na ordem. Com 991 lançamentos em Outros:

- **29 decisões** cobrem 50% do valor
- **125 decisões** cobrem 80%

Atacar em ordem alfabética, ou linha a linha, gastaria o mesmo esforço nos
R$ ···· e nos R$ ····

#### Como as descrições viram estabelecimentos

O mesmo lugar aparece escrito de várias formas no arquivo do banco:

```
UBER   *UBER   *TRIP  |
UBER* PENDING         |->  UBER
UBER* TRIP            |
```

E há três casos com tratamento próprio:

| Caso | Vira | Por quê |
|---|---|---|
| `Pix enviado para Eduardo…` | `PIX/TED EDUARDO…` | o que importa é a pessoa |
| `MP*LILINHO`, `ZIG*ALDEIA` | `MP`, `ZIG` | o intermediário agrupa bem |
| `HABIBE CLINICA ODONTOL` | 22 primeiros caracteres | mesmo corte de `sugerir_regras` |

Sobre os intermediários, duas descobertas opostas nos seus dados: **`ZIG*` são
todos bares**, e uma regra acerta as 22 linhas. Já **`MP*` são 49 lojistas
diferentes** somando R$ ···· — média de R$ ···· Tratar cada um seria 49
decisões para 2,5% do problema; como grupo único, é uma.

#### Cada decisão faz duas coisas

1. **Retroativo** — os lançamentos daquele estabelecimento saem de Outros.
   Sem isso, os gráficos dos meses antigos continuariam errados.
2. **Regra** — a próxima importação classifica sozinha.

A natureza sai do **sinal** do grupo: um Pix que soma positivo vira Receita, um
que soma negativo vira Despesa. O mesmo nome pode ser as duas coisas.

#### A armadilha do trecho curto demais

A comparação é por **trecho contido**, então uma palavra-chave curta pega mais
do que você imagina. Dois casos reais:

| Palavra-chave | Pega o que você quer | Pega também |
|---|---|---|
| `BOTAFOGO` | `S.A.F BOTAFOGO` (o clube) | Outback, Verde Vício, KFC, Galeto — o **bairro** |
| `BRUNO` | `BRUNO DA SILVA SILVA` | `Bruno Moreira Lima Simas`, que é outra pessoa |
| `1001` | a viação | qualquer código de pedido que contenha 1001 |

O conserto é sempre o mesmo: **use o nome completo**. `S.A.F BOTAFOGO`,
`BRUNO DA SILVA SILVA`. Antes de criar uma regra curta, vale rodar a aba
**Testar** e ver o que ela pegaria.

**A triagem hoje faz isso sozinha.** `palavra_chave_segura()` pergunta se a
palavra pega algum lançamento de OUTRO grupo; se pega, tenta a variante com
asterisco (`PAG*`); se nem assim, não cria regra e avisa na tela. Melhor ficar
sem regra do que com uma que erra toda importação.

Isso nasceu de um erro real: o grupo `PAG` virou regra `PAG`, que capturou
"**PAG**AMENTO PARA MERCADO PAGO" e mandou R$ ···· para Viagem.

#### Não persiga 100%

416 estabelecimentos aparecem uma única vez. Decidir cada compra de R$ ···· custa
mais do que o número melhora. Resolver os que pesam e deixar a cauda em Outros
é a escolha certa, não preguiça.

### 2. Sugerir regras novas

Procura estabelecimentos que aparecem várias vezes e que **nenhuma regra
reconhece**. Para cada um, sugere a categoria — e a sugestão **não é um
palpite**: é a categoria que **você mesmo** escolheu à mão nas vezes
anteriores.

A coluna `concordância` diz quanto das vezes você usou aquela mesma categoria.
100% significa que você foi consistente; 60% significa que variou e vale olhar
com atenção.

Na tela: **Regras → aba Sugestões**.

Regras criadas por aí entram no **fim** da lista, com a menor prioridade —
assim nunca roubam transações de uma regra específica que você já tinha
ajustado.

---

## A deduplicação (parte do mesmo caminho)

Depois de ler e antes de classificar, o importador precisa responder: **esta
transação já está no banco?**

### A impressão digital de cada origem

| Origem | Chave |
|---|---|
| **OFX** | o `FITID` — código único que o próprio banco atribui |
| **Extrato CSV** | data + hora + descrição + valor |
| **Fatura CSV** | mês + data + estabelecimento + portador + valor + parcela + **contador de ocorrência** |

**Por que a hora salva o extrato CSV:** dois Pix de R$ ···· para a mesma pessoa
no mesmo dia são transações diferentes se saíram em minutos diferentes. Sem a
hora, o sistema acharia que são a mesma e descartaria a segunda.

**Por que a fatura precisa de contador:** duas corridas de Uber de R$ ···· no
mesmo dia acontecem de verdade nos seus arquivos. O contador dá sufixo 1 à
primeira e 2 à segunda, tornando-as distintas. Como o contador é reconstruído
da mesma forma toda vez que o arquivo é lido, reimportar continua funcionando.

### O problema que quase passou batido: duplicata entre formatos

Os seus extratos **se sobrepõem**. O CSV vai até 06/08 e o OFX começa em
24/07. Vinte e uma transações, somando **R$ ····**, estão nos dois
arquivos.

Mas o `id_unico` do OFX vem do FITID e o do CSV vem de data+hora+descrição.
**A mesma transação gera ids diferentes conforme o arquivo de origem.** A
deduplicação normal não veria problema nenhum, e importar os dois arquivos
contaria R$ ···· duas vezes.

**A solução** é uma segunda impressão digital, feita só com o que as duas
fontes têm em comum:

```
data + valor + começo da descrição (40 caracteres)
```

A hora fica de fora porque o OFX não a fornece. A descrição é cortada porque
os dois formatos às vezes truncam o texto em tamanhos diferentes.

E a contagem é feita com um `Counter`, não com um conjunto: se você mandou
dois Pix de R$ ···· para a mesma pessoa no mesmo dia, os dois são reais e os
dois devem entrar. Marcamos como duplicata **exatamente a quantidade que já
existe** e deixamos passar o excedente.

### Duas camadas de proteção

Além da checagem no código, a coluna `id_unico` da tabela é `UNIQUE` e o
`INSERT` usa `OR IGNORE`. Ou seja: mesmo que o código tenha uma falha, o
próprio banco recusa a duplicata.

> Nunca confie numa camada só para proteger seus dados.

---

## Onde ver isso funcionando

Classificar uma descrição qualquer:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import regras; R = regras.carregar_regras(); print(regras.classificar_extrato('TED recebida de XP EMPREGADORA', 54997.77, R)); print(regras.classificar_extrato('TED recebida de XP EMPREGADORA', 5299.34, R))"
```

Ver quais regras mais pegam:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import regras; r = regras.testar_contra_historico('Extrato'); print(sorted([x for x in r if x['ordem']], key=lambda x: -x['acertos'])[:6])"
```
