# 14 · Imposto de renda

> Esta tela **organiza e confere**. Ela não calcula imposto, não emite DARF,
> não apura ganho de capital e **não substitui um contador**.

Isso não é modéstia protocolar. Apurar imposto exige dados que este app não
tem — o salário **bruto**, o informe oficial da corretora — e regras que mudam
todo ano. Um número calculado aqui envelheceria em silêncio, que é exatamente
o tipo de erro que este projeto passa o tempo inteiro tentando evitar.

O que ela faz é mais útil e mais honesto: **deixar você chegar no contador com
tudo separado, conferido, e com os buracos apontados.**

---

## Por que uma tela, e não uma aba de Investimentos

O IR cruza duas metades que moram em lugares diferentes:

    RENDA          salário, PLR, outras receitas
    PATRIMÔNIO     a carteira em 31 de dezembro

Nenhuma tela existente cobre as duas. Por isso ela é uma tela própria.

---

## As três coisas que a tela existe para dizer

### 1. A PLR não se soma ao salário

A declaração separa o que você recebeu em duas famílias, e a diferença entre
elas é **quando o imposto foi calculado**:

| Ficha | O que entra | Quando o imposto foi calculado |
|---|---|---|
| Rendimentos Tributáveis | salário | recalculado no ajuste anual |
| Tributação exclusiva/definitiva | **PLR**, rendimento de aplicação | já foi, na fonte, e acabou |

A PLR tem tabela própria e imposto definitivo. Na declaração ela vai em
**«Rendimentos sujeitos à tributação exclusiva/definitiva», item 11 —
Participação nos lucros ou resultados**.

**Somar ao salário é um erro caro:** você jogaria um valor já tributado dentro
da tabela progressiva, subindo a alíquota sobre todo o resto. Em 2025 a PLR
dele foi **R$ ····**.

Por isso a regra não é uma coluna discreta na tabela — é um bloco em
destaque, e `conferir_imposto.py` tem uma prova só para ela.

### 2. O app vê o líquido; a declaração usa o bruto

"Salário R$ ····" é o que **caiu na conta**, já sem IRRF e sem INSS. O
número da declaração é maior e está no informe da empresa.

**O app não produz o número da declaração. Ele produz o número para conferir.**
O aviso aparece antes de qualquer tabela, de propósito: copiar o líquido para
a declaração é a armadilha mais fácil desta tela.

### 3. A conta Global não tem informe — ninguém vai mandar

Para a XP-Brasil existe informe de rendimentos, e a Receita **exige** que você
use o documento oficial da corretora.

Para a conta internacional não existe nada. Desde a **Lei 14.754/2023**,
aplicação financeira no exterior é tributada a **15%** na declaração anual —
e **sem a faixa de isenção** que ações brasileiras têm. Prejuízo também
precisa ser declarado: é ele que compensa ganho futuro.

A posição internacional deste app foi reconstruída de `quantidade × cotação`,
conferida contra o print da corretora. É a melhor fonte que existe, e ela vale
**enquanto ele não operar lá de novo**.

---

## O custo de aquisição é o problema central

A ficha **Bens e Direitos** é uma fotografia do que você tinha em 31/12,
avaliada pelo que você **pagou** — nunca pelo valor de mercado.

A razão: a Receita cobra imposto sobre **ganho realizado**. Enquanto você não
vende, a valorização não existe para ela. Declarar pelo mercado faria a
diferença entre um ano e outro aparecer como patrimônio surgido do nada.

Corretagem, liquidação e emolumentos **entram no custo**.

E o custo, neste banco, quase não existia:

    custo preenchido       64 de 185 linhas de saldo
    em 31/12/2025          1 papel de 9 — com custo da coluna que mente

A migração 11 criou `fonte_custo`, que diz de onde veio cada um:

| fonte | o que significa |
|---|---|
| `extrato` | linha de compra de verdade, com data |
| `manual` | você digitou, olhando a nota ou o informe |
| `valor_aplicado` | ⚠️ a coluna da corretora que muda sozinha |

Os 64 custos que já existiam foram todos marcados como `valor_aplicado` — que
é a verdade sobre eles.

**Custo desconhecido volta `None`, nunca `0,0`.** Zero se lê como "custou
nada", e um bem declarado com custo zero transforma a venda inteira em ganho
tributável. Vazio significa **não sei**.

### Por que o custo do extrato quase nunca serve

`custo_pelo_extrato()` soma as linhas de compra. Parece a fonte perfeita — e
quase produziu o pior número da tela.

Clicando o botão na verificação, o **Trend DI** recebeu custo de
**R$ ····**. É um fundo que vale R$ ···· e existe desde abr/2024. O
extrato da corretora só começa em **jan/2026**, então ele somou apenas as
compras recentes — e gravou com `fonte_custo = 'extrato'`, o rótulo mais
confiável que existe.

Hoje a função **só responde para papel que nasceu dentro da cobertura do
extrato**. Dos 18 papéis, sobra um.

> **Pior que não ter custo é ter um custo errado que parece certo.**

### E gravar custo pode falhar em silêncio

`salvar_custo()` é um `UPDATE`, e `UPDATE` numa linha que não existe casa com
**zero linhas, sem erro nenhum**. Como `investimentos_saldos` só tem linha nos
meses fotografados, gravar em `'2026-12'` durante agosto dizia "salvo" e não
salvava.

Por isso ela devolve `bool`, e por isso `bens_e_direitos()` devolve
`mes_do_dado` — o mês que **existe** e para onde a gravação deve ir.

---

## Prévia × posição fechada

Olhar o ano corrente é útil (você chega em abril com tudo pronto), mas
dezembro ainda não aconteceu. A tela mostra a foto mais recente que tem e
**diz que é prévia**, em vez de apresentar agosto com cara de 31/12.

---

## O que buscar fora do app

| Documento | Onde | Para quê |
|---|---|---|
| Informe da empresa | RH ou portal | salário **bruto**, INSS, IRRF |
| Informe da XP-Brasil | app da corretora | posição oficial em 31/12 e imposto retido |
| Notas de corretagem | corretora | custo, quando o informe não detalha |
| **XP Global** | **não existe** | você reconstrói — é para isto que a tela serve |

---

## Como testar no terminal

```bash
.venv\Scripts\python -m verificacao.conferir_imposto
```

107 checagens. As que mais importam:

| # | Prova |
|---|---|
| 2 | custo desconhecido é `None`, nunca 0,0 |
| 3 | a PLR nunca entra no rendimento tributável |
| 7 | a projeção **desligada** é idêntica à de antes |
| 8 | gravar custo em mês sem foto **recusa**, em vez de fingir |
| 9 | custo de extrato só vale para papel nascido dentro dele |
