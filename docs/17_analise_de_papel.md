# 17 · Análise de papel

> A tela que responde *"a empresa aguenta?"*, *"está cara?"* e *"quanto eu
> tenho de verdade nela?"* — e que diz alto quando a pergunta não se aplica.

Arquivos: [`financas/fundamentos.py`](../financas/fundamentos.py),
[`ui/analise.py`](../ui/analise.py),
`exposicao_economica()` em [`financas/calculos/investimentos.py`](../financas/calculos/investimentos.py).
Prova: [`verificacao/conferir_fundamentos.py`](../verificacao/conferir_fundamentos.py).

## A medição veio antes do desenho

O pedido era um componente de análise de ações, com o Simply Wall St como
referência. Antes de desenhar qualquer coisa, medimos o que a fonte de fato
entrega para os papéis da carteira:

| | IREN | DGXX | IRE |
|---|---|---|---|
| campos preenchidos | 18 de 22 | 17 de 22 | **2 de 22** |
| P/L | — | — | — |
| lucro por ação | **−2,22** | **−0,57** | — |
| margem | **−99%** | **−115%** | — |
| crescimento de receita | **−24%** | **−18%** | — |
| setor informado | *"Financial Services"* ❌ | Utilities | — |

A medição derrubou o desenho óbvio, e cada linha dela virou uma regra:

**1. O kit clássico não serve para carteira nenhuma dele.** P/L, PEG, dividend
yield e ROE positivo pressupõem lucro. Nenhum dos três papéis dá lucro. Um
painel de valuation sairia com traço em toda linha — e traço num cartão parece
falha de busca, não informação.

**2. O setor da fonte pode estar errado.** O IREN é mineradora de bitcoin
pivotando para datacenter de IA, e chega classificado como *Serviços
Financeiros / Mercado de Capitais*. Qualquer comparação "contra o setor" o
compararia com bancos. Por isso `SETOR_SUSPEITO` existe e a tela avisa por cima
dos números, não numa nota de rodapé.

**3. Múltiplo negativo é lixo, não dado.** O IREN vem com
`forwardPE = −172,9`. Impresso como está, vira "P/L de −172". Aqui múltiplo com
lucro negativo devolve `None`, **e a tela explica por quê** — porque a empresa
dá prejuízo, não porque a busca falhou.

## O que substitui o kit clássico

Para empresa que queima caixa a pergunta não é *"está cara?"*, é **"o dinheiro
dura quanto tempo?"**. E isso é computável:

    fôlego = caixa ÷ queima anual de caixa

| | caixa | queima/ano | fôlego | dívida |
|---|---|---|---|---|
| IREN | R$ ···· bi | −4,24 bi | **~17 meses** | R$ ···· bi (**maior que o caixa**) |
| DGXX | R$ ···· mi | −117 mi | **~13 meses** | **zero** |

Duas empresas no prejuízo com balanços opostos. É esse contraste que a tela
mostra, e ele decide mais que qualquer múltiplo.

**Quem gera caixa devolve `None`, nunca um número enorme.** A tentação é
escrever "fôlego de 9.999 meses" para a Apple. Isso é pior que vazio: o cartão
fica preenchido, com cara de medição, respondendo pergunta que não se aplica.

E o mesmo fato muda de significado conforme o caso. *Dívida maior que caixa*
numa empresa que queima dinheiro quer dizer dependência de dinheiro de fora
— emitir ação (que dilui) ou tomar mais dívida. Na Apple, que gera caixa, é
escolha de estrutura de capital e o que importa é o custo, não o tamanho. A
tela troca a frase conforme o caso, porque a mesma frase nos dois seria mentira
em um deles.

## O fundo alavancado, que é o achado sério

O IRE chega da fonte como `EQUITY` — ação comum. O nome dele diz
**"Defiance Daily Target 2X Long IREN ETF"**. O campo estruturado está errado e
o texto está certo, então `alavancagem()` lê o nome.

Isso importa por três motivos, e nenhum é cosmético.

**Ele não tem balanço para analisar.** Não é dado faltando: o conceito não se
aplica. A tela some com o bloco "A empresa aguenta?" e põe a frase no lugar.

**A exposição real é o dobro da posição.** Quem tem IREN e IRE tem uma aposta
só, e um pedaço dela dobrado:

    posição IREN               R$ ····
    posição IRE                R$  R$ ····
    exposição via IRE (×2)     R$  R$ ····
    ------------------------------------------
    EXPOSIÇÃO REAL A IREN      R$ ····   (10,7% da carteira)

Somar as duas linhas como a tela as mostra dá R$ ···· e **subestima o
risco em R$ ····**. A diferença parece pequena porque a posição em IRE é
pequena — ela deixa de ser pequena depressa, e é justamente quando ninguém está
olhando.

`exposicao_economica()` conta só o **mesmo papel-alvo**, que é fato. Papéis
diferentes que andam juntos — dois do mesmo setor — não entram, porque isso
seria estimativa de correlação, não medição.

**E 2x por dia não é 2x no período.** Esta é a que o nome do fundo esconde.
Medido em 215 pregões da carteira dele:

| | |
|---|---|
| IREN no período | **−35,8%** |
| 2× disso seria | −71,5% |
| IRE entregou | **−89,5%** |
| diferença | **−17,9 p.p.** |

A razão diária entre os dois deu mediana **1,99** — a alavancagem funciona
exatamente como anunciada, todo dia. O buraco vem de multiplicar dias, não de a
promessa ter sido quebrada. Cair 10% e subir 10% devolve o papel normal a 99%
do que era, e o alavancado 2x a **96%**. Repita por meses e o resultado é esse.
Quanto mais o alvo oscila, maior a diferença — e a volatilidade diária do IREN
é de 7,0%, contra 14,0% do IRE.

## Por que não tem snowflake preenchido à força

O floco do Simply Wall St pontua valor, futuro, saúde, passado e dividendos. As
notas saem de modelo proprietário — *fair value* por fluxo de caixa descontado,
com premissas que não são publicadas. Reproduzir a **aparência** sem o modelo
daria um desenho bonito com número inventado dentro, que é pior que não ter
desenho.

O que dá para desenhar com honestidade é o floco **do que a fonte de fato
entrega**: cada eixo um número medido, e o eixo sem dado encolhido, à vista.

## A tela aceita qualquer ticker

Não só os da carteira. É para **pesquisar antes de comprar**, que é quando a
pergunta importa. Papel de fora não tem histórico de preço gravado, então
`_preco()` busca uma vez e guarda — sem isso, *"alvo contra o preço de hoje"*
ficaria em branco justamente na tela feita para pesquisar.

Papel do Brasil leva o sufixo `.SA`: `PETR4.SA`, `BBAS3.SA`.

## O cache é de um dia, e diz de quando é

Balanço muda por trimestre, não por minuto. O json **cru** fica em
`fundamentos` com `obtido_em`, sem interpretação — quando a leitura estiver
errada, dá para corrigir sem buscar tudo de novo. Se a rede cair, o guardado
continua servindo e a tela diz a data.

## O limite, dito sem rodeio

A fonte é o Yahoo Finance pelo `yfinance`, que **não é oficial** e já quebrou
quando o Yahoo mexeu no site. Tesouro Direto e fundo brasileiro não têm
cobertura nenhuma. E nada aqui é recomendação: a tela mostra o que a fonte diz
e o que a aritmética conclui, com as ressalvas coladas. Quem decide é você.
