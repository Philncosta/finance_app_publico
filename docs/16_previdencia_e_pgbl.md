# 16 · Previdência: PGBL, VGBL e a conta do outro lado

> **Aba `Previdência (PGBL)` na tela de Imposto de renda.**
> Motor em `financas/calculos/previdencia.py`, conferido por
> `verificacao/conferir_previdencia.py`.

---

## O que esta aba responde, e em que ordem

Três perguntas — e **a ordem importa**, porque a segunda só faz sentido se a
primeira der "completa":

1. Para você, a declaração **completa** ganha da **simplificada**?
2. Se ganha: qual o teto legal do aporte em PGBL, e quanto ele economiza?
3. Essa economia **sobrevive ao resgate**?

Ela não recomenda plano, corretora nem produto, e não substitui contador. Faz
a aritmética do imposto sobre os números que você informar, e mostra os dois
lados dela.

---

## A regra em uma frase

**PGBL** deduz na entrada e, no resgate, paga imposto sobre o **valor total** —
aporte mais rendimento.
**VGBL** não deduz nada e, no resgate, paga só sobre o **ganho**.

Tudo o mais é igual: mesma aplicação, mesmo prazo, mesma tabela regressiva.

---

## As quatro coisas que esta aba existe para dizer

### 1. Na declaração simplificada, o PGBL vale exatamente zero

O desconto simplificado — 20% da renda, limitado a **R$ ····** (AC 2025)
ou **R$ ····** (AC 2026) — **substitui todas as deduções**. Inclusive a
previdência complementar.

Por isso a aba calcula **os dois modelos, sempre**, e o simulador devolve
economia zero quando a simplificada ganha. Um simulador que pula essa pergunta
pode prometer uma economia que não existe para você.

### 2. O benefício não é 27,5%

A dedução derruba a base de cálculo e pode **atravessar faixa** da tabela:
parte abatida a 27,5%, parte a 22,5%.

Por isso a economia aqui é sempre a **diferença entre duas apurações de
verdade** — uma sem o aporte, outra com —, nunca `aporte × alíquota`. A
"alíquota efetiva" que a tela mostra é o *resultado* da conta, não a entrada
dela.

### 3. Não é desconto. É adiamento.

A restituição de hoje é um empréstimo que se paga no resgate. Você paga menos
**se** três coisas acontecerem, e nenhuma delas é sobre o plano:

| | |
|---|---|
| **se** você entrega a declaração completa | senão a dedução nem existe |
| **se** você fica até a alíquota de 10% | dez anos; antes disso a regressiva é 35%, 30%, 25%… |
| **se** você reinveste a restituição | ela é o benefício inteiro — gasta, sobra só o custo |

A tela tem uma caixa "Reinvisto a restituição". **Desmarque e veja o que
acontece.**

### 4. Em 2026, abaixo de R$ ···· de rendimento tributável não há o que economizar

O redutor da Lei 15.270/2025 já zera o imposto até ali. Não se economiza
imposto que não existe — e nenhum simulador comercial diz isso.

---

## A comparação certa é com o VGBL, não com um CDB

Chame o montante final de **X**, o aporte de **A** e a alíquota regressiva de
**a**:

```
líquido PGBL = X − a·X        = X·(1−a)
líquido VGBL = X − a·(X − A)  = X·(1−a) + a·A
```

A diferença é **a·A** — o imposto sobre o próprio aporte, que só o PGBL paga.
**Ela não depende do retorno nem do prazo.** Daí sai a regra inteira:

> **Sem a dedução, o VGBL ganha do PGBL por 10% do aporte. Sempre.**

O PGBL só faz sentido para quem consegue deduzir de verdade. Fora disso ele é
um VGBL que paga imposto a mais.

### Por que a comparação com "um investimento comum" engana

Contra um CDB (15% sobre o ganho), o PGBL **mesmo sem dedução nenhuma** acaba
ganhando depois de uns doze anos: 10% sobre tudo passa a custar menos que 15%
sobre um ganho que ficou grande.

É verdade, e é a comparação errada. Se você não pode deduzir, sua alternativa
não é um CDB — é o VGBL. O gráfico da aba mostra a curva contra o investimento
comum porque é ela que tem um *ano de virada* interessante; o número ao lado,
contra o VGBL, é o que decide.

*(Este foi um teste escrito errado que a conta corrigiu: a primeira versão
afirmava que, sem dedução, o PGBL nunca ganharia de um investimento comum.
Ganha, sim, lá na frente. O `conferir_previdencia` reprovou a afirmação, não o
código.)*

---

## De onde vem cada número

As tabelas mudam por lei. Por isso ficam numa constante **datada**, com o ano
a que cada uma pertence — nunca "a tabela atual".

| ano-calendário | lei | declaração |
|---|---|---|
| 2025 | Lei 15.191/2025 | entregue em 2026 |
| 2026 | Lei 15.270/2025 | entregue em 2027 |

**Ano sem tabela cadastrada devolve `None` e a tela avisa.** Não se usa a
tabela do ano passado no lugar: erraria em silêncio, que é o defeito que este
projeto mais persegue.

### Os limites, um a um

| | AC 2025 | AC 2026 |
|---|---|---|
| dedução PGBL | 12% da renda bruta tributável | 12% |
| desconto simplificado | R$ ···· | R$ ···· |
| dependente | R$ ····/ano | R$ ····/ano |
| instrução | R$ ···· por pessoa/ano | R$ ···· |
| despesas médicas | sem teto | sem teto |
| redutor | não existia | até R$ ···· |

### A conferência que vale por todas

Pela tabela de 2026, quem tem **R$ ····** de rendimento tributável e
entrega a **simplificada** paga exatamente **R$ ····** de imposto — e
R$ ···· é, ao centavo, o teto do redutor que a lei criou.

Não é coincidência: a lei escolheu o número para **zerar** o imposto de quem
ganha até R$ ···· por mês. Se a tabela ou o redutor estiverem digitados
errados, essa igualdade quebra — e é isso que o conferidor testa.

### Duas coisas sobre o redutor que mudam a conta do PGBL

1. Ele olha para o **rendimento tributável**, não para a base depois das
   deduções. Aportar em PGBL **não o aumenta**.
2. Ele é **limitado ao imposto devido**, então não vira restituição extra.

---

## A armadilha central: o bruto

O teto de 12% é sobre a **renda bruta tributável sujeita ao ajuste anual**, e
este app só enxerga o **líquido** que caiu na conta. É a mesma advertência que
abre a tela de Imposto — e aqui ela é mais cara, porque o erro vira um aporte
do tamanho errado.

Por isso **nada aqui adivinha o bruto**. Os números vêm do informe de
rendimentos, digitados uma vez por ano e guardados na tabela `ir_ano`
(migração 15).

**E atenção ao que NÃO entra na base dos 12%:** PLR e 13º salário têm
tributação exclusiva e ficam de fora. Somar a PLR ali inflaria o teto e faria
você aportar mais do que pode deduzir — e o excedente não volta: fica preso
num plano, para ser tributado como PGBL, sobre o total, sem nunca ter dado o
desconto que justifica esse tratamento.

---

## O que o app sugere, e o que ele se recusa a preencher

A aba mostra, como **ponto de partida a conferir**, quanto você gastou no ano
nas grandes categorias **Saúde** e **Educação**.

Isso não é a resposta, e a tela diz isso ao lado do número:

| a Receita aceita | não aceita |
|---|---|
| consulta, exame, internação, plano de saúde, dentista, fisioterapia, psicólogo | **farmácia**, medicamento, academia |
| escola, faculdade, pós-graduação, ensino técnico | **curso livre**, idioma, material escolar |

Mandar o total da categoria direto para o campo da declaração seria inventar
dedutibilidade. O número serve para você não começar do zero e para lembrar de
um gasto esquecido — a triagem é sua.

---

## Onde mexer

| quero… | vá em |
|---|---|
| atualizar a tabela de um ano novo | `TABELAS` em `financas/calculos/previdencia.py` |
| mudar o que a tela pergunta | migração da tabela `ir_ano` + `CAMPOS_DO_ANO` |
| conferir se a conta continua certa | `.venv\Scripts\python -m verificacao.conferir_previdencia` |

Ao acrescentar um ano em `TABELAS`, acrescente também as checagens dele no
conferidor. Uma tabela nova sem teste é uma tabela que ninguém sabe se está
certa.
