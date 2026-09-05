# 20 · Metas e compras: o velocímetro, o preço com memória e o calendário

> Três perguntas que a tela não respondia: *estou no ritmo?*, *este preço é
> bom?* e *quando é que eu compro isso?*

Arquivos: [`paginas/metas_compras.py`](../paginas/metas_compras.py),
[`financas/precos.py`](../financas/precos.py),
[`financas/calculos/compras.py`](../financas/calculos/compras.py)
(`calendario`), [`financas/calculos/metas.py`](../financas/calculos/metas.py)
(`mover`), [`ui/graficos.py`](../ui/graficos.py) (`velocimetro`,
`historico_preco`, `calendario_compras`).
Prova: [`verificacao/conferir_compras.py`](../verificacao/conferir_compras.py).

---

## 1. O velocímetro, e o risquinho no 100%

A informação mais importante da aba de metas sempre foi *estou ou não no
ritmo?*. Ela existia — como a palavra "atrasada" dentro de um aviso, embaixo
de quatro `st.metric`. Ninguém lê isso de relance.

Agora cada meta tem um meio-círculo com uma **marca fina no 100%**. Essa marca
é o gráfico inteiro: "68%" sozinho não diz nada, porque nada na tela diz onde
ficaria o suficiente. Com a marca, você bate o olho e vê de que lado dela está.

O que o velocímetro mede muda conforme a meta, e o **título diz qual**:

| A meta tem prazo? | O velocímetro mede | Embaixo dele |
|---|---|---|
| Sim | **Ritmo do aporte** = definido ÷ necessário | Necessário / Definido, por mês |
| Não | **Progresso** = já tem ÷ alvo | Alvo / Já tem |
| Concluída | **Progresso**, 100% | Alvo / "meta cumprida" |

### Cor de juízo × cor neutra

`velocimetro(..., julgar=True)` (o padrão) pinta pela convenção da casa: verde
cumpriu, âmbar está perto, vermelho não cumpriu. Isso serve para *cumprimento*
— cobertura da capacidade, metas no ritmo, ritmo do aporte.

`julgar=False` usa o índigo neutro, e é o que os indicadores de **progresso**
usam. Uma meta 27% concluída não está reprovada, está no meio do caminho.
Pintar isso de vermelho seria o painel repreendendo você por ter começado.

### O olhinho e o velocímetro

A figura se marca com `meta={"valores": "percentual"}`, e por isso passa
inteira pelo olhinho: porcentagem não revela quanto você tem. Os valores em R$
que acompanham cada velocímetro ficam **fora** da figura, em `st.caption` com
`fmt_brl_md` — onde o olhinho os alcança. Ver [docs/15](15_o_olhinho.md).

O calendário de compras usa uma marca nova, `"sem_dinheiro"`: ali o eixo mede
**meses**, não reais. Chamar meses de "percentual" só para reaproveitar a
exceção esconderia, no próprio nome, a razão de ela existir.

---

## 2. O bug que o velocímetro revelou: meta sem prazo cobrava tudo

Assim que a "Cobertura da capacidade" foi para a tela, ela marcou **0,1%**.

A causa estava em `metas.calcular()`, e era anterior a esta reforma:

```python
aporte_necessario = falta / meses_restantes if meses_restantes else falta
```

`if meses_restantes` é falso para `None` **e** para `0` — dois casos
diferentes tratados como um. A meta "chegar a R$ ···· investido", que não
tem data, caía no `else` e aparecia exigindo os R$ ···· que faltavam
**dentro deste mês**.

O número contaminava tudo que soma: `resumo()["aporte_necessario_total"]`, o
"sua capacidade cobre tudo?" e o botão de distribuir — que entregava
praticamente toda a capacidade para a meta sem prazo, porque a exigência dela
era o valor inteiro.

A correção separa os dois casos:

```python
if meses_restantes is None:      # sem data: não há exigência mensal
    aporte_necessario = 0.0
elif meses_restantes == 0:       # o prazo é este mês: precisa de tudo agora
    aporte_necessario = falta
else:
    aporte_necessario = falta / meses_restantes
```

E o botão "Distribuir minha capacidade" passa a ratear **só entre as metas com
prazo**, dizendo quantas ficaram de fora. Sem isso ele zeraria o aporte que
você definiu à mão para a meta sem prazo — uma correção que criaria outro
problema.

`conferir_metas.py` passou a travar as três situações.

---

## 3. Editar no cartão, e a exclusão que agora pergunta

Antes, mudar o aporte de uma meta exigia rolar até o fim da página, achar a
linha na tabela e salvar tudo junto. Agora cada cartão tem lápis (`st.popover`
com o formulário), lixeira (`@st.dialog` com o nome da meta escrito por
extenso) e setas ▲▼.

Três detalhes que não são óbvios:

**O formulário lê o CADASTRO, não a linha calculada.** Numa meta vinculada ao
patrimônio, `metas.calcular()` substitui `ja_acumulado` pelo valor real da
carteira ([docs/19](19_metas_vinculadas.md)). Se o formulário lesse dali,
salvar gravaria o valor derivado por cima do número guardado — e no dia em que
você desmarcasse o vínculo encontraria a foto da carteira no lugar do seu
número.

**Com o olhinho ligado, os campos em R$ somem** (`_campo_de_dinheiro`), e não
apenas ficam desabilitados: um `number_input` desabilitado continua imprimindo
o número. Quando somem, devolvem o valor guardado — salvar com o olhinho ligado
regrava o mesmo número, nunca zero. É a mesma regra do
`privacidade.editor`: **um recurso de esconder valores nunca pode alterar
valores.**

**As setas usam a coluna `ordem`, que já existia e nenhuma tela alimentava.**
Como ela nasceu com `DEFAULT 0`, `metas.mover()` renumera 1..N antes de
trocar — trocar dois zeros não muda nada.

### O guarda-exclusão da tabela

A tabela do "modo avançado" continua, e com ela o comportamento que gerou a
pergunta: *"e se eu apagar uma linha?"*. Antes, a linha que sumisse da tabela
era `DELETE`-ada no Salvar, sem aviso. Agora a tela conta quantas sumiram, diz
**quais**, e só executa o `DELETE` se você marcar a caixa. Sem a marca, as
metas removidas simplesmente continuam no banco e voltam a aparecer.

Exclusão implícita é o tipo de comportamento que a pessoa só descobre no dia em
que perde alguma coisa.

Isso hoje é `componentes.guarda_de_exclusao()`, usado nas três tabelas que
editam cadastro (metas, compras e gastos fixos) — antes eram três cópias do
mesmo bloco de quinze linhas, e a terceira nunca chegou a ser escrita: Gastos
fixos ficou apagando em silêncio por mais uma semana.

A decisão de **o que** apagar mora separada, em `componentes.ids_removidos()`,
sem nenhuma chamada ao Streamlit. Isso é o que a torna testável — e ela é o
único ponto onde um erro custa dado:

    errar para MAIS   apaga o que você não mandou apagar
    errar para MENOS  finge que apagou, e a linha reaparece

`verificacao/conferir_exclusao.py` cobre os dois lados, incluindo a linha nova
sem `id` (que quebraria num `int(NaN)`), a tabela esvaziada, a tabela sem
coluna `id` (falha fechada: não apaga nada) e linhas reordenadas na tela.

---

## 3b. A mensagem que ninguém nunca viu

Este trecho existia na página desde sempre, e em mais oito telas do app:

```python
banco.executar(...)
st.success("Metas salvas.")   # nunca foi vista por ninguém
st.rerun()
```

`st.rerun()` interrompe a execução e redesenha a página do zero — jogando fora
tudo que foi escrito naquele run, **inclusive a mensagem escrita uma linha
antes**. Conferido na tela: depois de clicar em "Salvar metas", o texto
"Metas salvas." não aparecia em lugar nenhum.

Passava despercebido porque o efeito acontece: a meta É salva, a linha some, a
tabela atualiza. Só a confirmação se perdia. O que fez isso virar problema de
verdade foi o guarda-exclusão acima — o recado "as 2 metas que você removeu
continuam no banco" **não** é redundante com a tela, é a única forma de saber
que elas não foram apagadas.

A saída é o aviso atravessar o rerun pelo estado da sessão:
`componentes.recado()` guarda, `componentes.mostrar_recado()` mostra e consome,
no topo da página. O relatório da busca de preços usa a mesma ideia, com uma
diferença: ele **fica** até você dispensar, porque a lista de falhas ("a loja
bloqueou o acesso") é justamente o que você precisa ler com calma, e sumiria no
primeiro clique em qualquer outra coisa.

### As outras oito telas, depois

Elas foram junto — 25 mensagens, não as 23 que um `grep -A 3` tinha contado. O
grep erra dos dois lados: pega mensagem e `rerun` que estão em **ramos
diferentes** (falso positivo) e perde os que têm mais de três linhas entre um e
outro (falso negativo).

O `ast` sabe a diferença porque lê a mesma árvore que o Python executa. A
condição exata é: um `st.success/info/warning/error(...)` e um `st.rerun()` no
**mesmo bloco**, com a mensagem antes — tudo que roda entre os dois acontece
sem a tela ser entregue ao navegador.

```python
for campo in ("body", "orelse", "finalbody"):
    bloco = getattr(no, campo, None)     # cada ramo, separadamente
```

Foi esse detector que encontrou as 25, que fez a troca, e que depois voltou a
rodar para provar que sobrou zero.

---

## 3c. O número que não cabia na caixa

Nos cartões de meta, `R$ ····` aparecia como `R$ ····…`.

A causa é o padrão do `st.metric`: `font-size: 36px` com `white-space: nowrap`
e `text-overflow: ellipsis`. Medido na tela, o texto ocupava **234px numa caixa
de 157px**.

Num painel de dinheiro isso não é só feio, é **errado**: os dígitos sumidos não
deixam rastro, e `R$ ····…` se lê como mil reais e pouco. Cortar um valor é
o mesmo tipo de falha silenciosa que o olhinho evita — só que aqui o app se
enganava sozinho.

A saída em [`ui/tema.py`](../ui/tema.py) é fazer a fonte acompanhar a caixa:

```css
div[data-testid="stMetric"] { container-type: inline-size; }
div[data-testid="stMetricValue"] > div {
    font-size: clamp(0.95rem, 14cqi, 2.25rem) !important;
    white-space: normal !important;      /* quebra em vez de cortar */
    text-overflow: clip !important;
}
```

`cqi` é 1% da largura do **container** — o próprio cartão da métrica. A fonte
sai em 22px numa caixa de 157px, 16,7px numa de 119px, e o teto de `2.25rem`
devolve os 36px originais nas caixas largas. Sem `container-type`, `cqi` não
existe; por isso a primeira linha.

E o `white-space: normal` é a rede de segurança: se um número for longo demais
até para o piso de `0.95rem`, ele **quebra em duas linhas** em vez de perder
dígito. Ficar feio é aceitável; mentir não.

---

## 4. O preço com memória

`futuras_compras.preco_atual` é um número que se **sobrescreve**. Você anota
R$ ···· hoje, R$ ···· no mês que vem, e o 4.299 some. Sem os valores
anteriores não dá para responder a única pergunta que uma lista de desejos
precisa responder: **"R$ ···· é barato, ou já esteve mais barato?"**

A migração 21 cria `precos_compras` — uma linha por consulta:

```sql
CREATE TABLE precos_compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id INTEGER NOT NULL,
    data TEXT NOT NULL,          -- 'AAAA-MM-DD'
    preco REAL NOT NULL,
    fonte TEXT,                  -- 'manual' | 'jsonld' | 'og' | 'microdata'
    obtido_em TEXT
);
```

**Não há coluna `preco_minimo`.** O menor preço é `MIN(preco)` daqui. Guardar
o mínimo também seriam duas fontes para o mesmo número, e duas chances de
divergir — a mesma razão pela qual preço e câmbio moram na mesma tabela
`cotacoes` ([docs/13](13_moeda_e_cotacoes.md)).

### Só ponto de mudança, e o gráfico em degrau

`precos.registrar()` não grava um ponto por consulta. Preço igual ao último só
carimba `obtido_em` ("conferi hoje, não mudou"). Quinze consultas de um preço
parado deixam **um** ponto.

Isso obriga o gráfico a ser em **degrau** (`line_shape="hv"`). Não é estética:
dois pontos — 4.299 em 10/07 e 3.999 em 26/08 — ligados por uma reta desenham
uma queda gradual que nunca aconteceu. O preço ficou em 4.299 até o dia em que
virou 3.999.

Todo preço digitado à mão na tabela também entra no histórico. É isso que faz a
curva existir para quem nunca clicar em "Buscar preços".

---

## 5. A busca automática, e o tamanho dela

`precos.ler_preco_da_pagina()` baixa o HTML do link e procura o preço em três
lugares **padronizados**, nesta ordem:

| Ordem | Formato | Onde |
|---|---|---|
| 1 | JSON-LD | `<script type="application/ld+json">` com `@type: Product` → `offers.price` |
| 2 | Open Graph | `<meta property="og:price:amount">` |
| 3 | Microdata | `itemprop="price"` |

São os três formatos que as lojas publicam **de propósito**, para o Google
entender a página. Não há raspagem de HTML visual — nada de "pega a terceira
`<div>` da classe tal", que quebra na primeira mudança de layout. Entre
ofertas concorrentes na mesma página, fica com a menor.

Sem dependência nova: `urllib.request` + `json` + `re`, como já fazem
[`indices.py`](../financas/indices.py) e [`cambio.py`](../financas/cambio.py).

### O que isso NÃO faz

**Funciona em parte das lojas, não em todas.** Amazon e Mercado Livre bloqueiam
acesso automático e/ou montam o preço por JavaScript depois que a página abre.
Nesses, a busca falha — e falha **falando**: cada item aparece na tela com o
motivo ("a loja bloqueou o acesso automático (HTTP 403)", "não achei o preço no
HTML"). O campo manual continua valendo.

É o mesmo trato do `cotacoes.py` com o yfinance ([docs/13](13_moeda_e_cotacoes.md)):
quando funciona, poupa digitação; quando não funciona, o app não quebra e diz
por quê. **Nenhuma falha é silenciosa** — um rastreador que erra sem avisar é
pior que nenhum, porque você olha um preço de três meses atrás achando que é de
hoje.

A busca só roda **quando você clica no botão**, nunca ao abrir a página, com
uma pausa de um segundo entre lojas. Uma consulta que saísse sozinha a cada
`st.rerun()` viraria dezenas de requisições por minuto para a loja — abuso, e o
caminho mais curto para o bloqueio.

---

## 6. O calendário: em que mês cada compra cabe

`compras.calendario()` responde "quando eu compro isso" com a única fonte
honesta: a **sobra de caixa projetada** do Planejamento (`saldo_mes` de
`planejamento.projecao_caixa`), acumulando de um mês para o outro. Sem
projeção, cai para a sua capacidade mensal.

### A fila é rigorosa, de propósito

Os itens são atendidos em ordem de prioridade, e **um item caro segura a fila
até caber**. A alternativa — pular o caro e ir enfiando os baratos que cabem —
renderia uma lista mais cheia e uma prioridade que não significa nada: o item
"Alta" de R$ ···· nunca chegaria, porque os de R$ ···· comeriam a sobra todo
mês. Se você quer o barato antes, mude a prioridade dele; é exatamente o
controle que a coluna existe para dar.

O que não cabe em 12 meses aparece com a barra listrada e o rótulo dizendo
isso. Sumir da tela seria esconder justamente o item que você precisa
reavaliar.

Não há juros nem parcelamento na conta: é soma de sobras, tudo à vista.
Parcelar é outra pergunta, e já tem tela própria.
