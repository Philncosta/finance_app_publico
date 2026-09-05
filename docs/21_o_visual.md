# 21 · O visual: o que é do Streamlit e o que é nosso

> A regra desta reforma foi uma só: **nenhum número entra, sai ou muda de
> lugar**. Só a pele.

Arquivos: [`.streamlit/config.toml`](../.streamlit/config.toml),
[`ui/tema.py`](../ui/tema.py), [`ui/componentes.py`](../ui/componentes.py)
(`painel`, `selo`), [`ui/graficos.py`](../ui/graficos.py) (`_estilo`).

---

## 1. O `tema.py` estava brigando com o Streamlit

Ele escrevia CSS para coisas que o Streamlit já configura sozinho: raio de
canto, cor de borda, tamanho do valor da métrica, cor da barra lateral. CSS que
repete a configuração é CSS que um dia diverge dela.

O que foi para o [`config.toml`](../.streamlit/config.toml):

| Antes, em CSS | Agora, em config |
|---|---|
| `border-radius: 10px` em botão, tabela, campo | `baseRadius = "0.75rem"` |
| `border: 1px solid #E2E8F0` repetido | `borderColor = "#EDF1F6"` |
| `font-family` nas regras | `font = "Inter:…"` |
| — | `metricValueFontSize`, `metricValueFontWeight` |
| `background` da barra lateral | `[theme.sidebar]` inteiro |

### A barra lateral é o caso que justifica tudo

Pintar o fundo da barra lateral pelo CSS é uma linha. O problema são as outras
trinta: o radio de período, o checkbox, o expander, o `st.code`, as captions —
cada um herdando um texto quase preto sobre indigo escuro, e cada um exigindo
um seletor próprio para consertar. É o tipo de coisa que fica 90% pronta e o
resto só aparece semanas depois, num widget que ninguém reabriu.

`[theme.sidebar]` resolve porque o Streamlit recolore os **próprios** widgets:

```toml
[theme.sidebar]
backgroundColor          = "#1E1B4B"
secondaryBackgroundColor = "#312E81"
textColor                = "#C7D2FE"
primaryColor             = "#818CF8"
```

Medido depois: marca, caption, radio, checkbox e expander todos em `#C7D2FE`
sobre `#1E1B4B`. Nenhum seletor de CSS envolvido.

### O que continua sendo nosso

`.cartao`, `.destaque`, `.estatistica`, `.secao`, `.barra`, `.tarja`, `.dica`,
`.selo`, `.painel-*`, `.marca-*` — componentes que o Streamlit não tem. E o
`clamp(…cqi…)` do valor da métrica ([docs/20](20_metas_e_compras.md)), porque
`metricValueFontSize` é um tamanho fixo e "caber na caixa" não é um tamanho
fixo.

---

## 2. `c.painel()`: o gráfico passou a morar em algum lugar

O padrão antigo era um título solto e, embaixo, o gráfico solto no fundo cinza:

```python
st.markdown("#### Da receita ao saldo")
priv.grafico(graficos.cascata_do_mes(...))
```

Funciona, e nada diz onde um assunto termina e o outro começa. Com oito
gráficos na tela, a página vira uma pilha de desenhos.

```python
with c.painel("Da receita ao saldo"):
    priv.grafico(graficos.cascata_do_mes(...))
```

O título é o **mesmo** — mudou de lugar, não de conteúdo. O cartão é o que o
faz pertencer ao gráfico.

### A regra de quando usar — e a versão errada dela

A primeira regra escrita aqui dizia: *"aba cujo conteúdo inteiro é um gráfico
fica sem cartão, porque a tira de abas já agrupa"*. **Estava errada**, e ele
viu na tela antes de mim: no meio de uma coluna de cartões, "Receita × despesa"
aparecia como um gráfico nu entre "Ano a ano" e "Saldo acumulado no ano". Um
buraco.

O erro foi confundir *agrupar logicamente* com *desenhar moldura*. A tira de
abas agrupa no sentido de que separa conteúdos — mas **não desenha nada**. Não
há moldura para o cartão duplicar.

A regra correta é mais simples, e por não ter exceção não produz buraco:

> **Todo gráfico fica dentro de uma superfície branca.** As superfícies são
> três, e todas desenham a mesma coisa: `c.painel()`, o
> `st.container(border=True)` com `key`, e o `st.expander`.

Duas formas, conforme o que o grupo de abas contém:

| O grupo de abas é… | O que se faz |
|---|---|
| um gráfico por aba (`Receita × despesa`) | o **grupo inteiro** entra num cartão, e o `####` de cima vira o título dele |
| uma seção com várias coisas (`Para onde o dinheiro foi`) | **cada gráfico** ganha seu cartão; a seção segue sendo seção |

O expander entrou nessa lista tarde: ele já tinha borda e canto do
`config.toml`, mas o fundo era **transparente** — um retângulo vazado ao lado
de cartões brancos. Uma regra de CSS resolveu para os 30 expanders do app.

E o título:

| O que estava acima do gráfico | O que acontece |
|---|---|
| `st.markdown("#### Rótulo")` | vira o título do painel |
| `st.markdown("**Rótulo**")` | vira o título do painel |
| `### Seção` ou `c.secao(...)` | **continua sendo título de seção**; o gráfico abaixo ganha painel sem título |

A distinção da última linha importa: transformar um cabeçalho de seção em
título de cartão mudaria a hierarquia da página — e a regra desta reforma era
não mexer em conteúdo.

### Onde foi aplicado

Todas as 13 telas, e **sem exceção**: varrendo o DOM de cada tela, todo
`stPlotlyChart` tem um painel, um cartão ou um expander como ancestral.

Essa varredura é a forma honesta de conferir isto, e vale mais que olhar a
página: ela responde "quantos gráficos NÃO estão emoldurados" em vez de
"a página parece ok".

```js
[...document.querySelectorAll('[data-testid="stPlotlyChart"]')]
  .filter(g => !g.closest('[class*="st-key-painel_"], [class*="st-key-cartao_"], [data-testid="stExpander"]'))
```

Se isso devolver algo, há um buraco. Foi assim que os sete gráficos nus do
Dashboard apareceram — todos dentro de abas, todos vítimas da regra errada.

### O detalhe chato: achar o container

`st.container(border=True)` não se identifica de nenhuma forma estável — só por
um hash de emotion (`st-emotion-cache-1woxk8z`) que muda de versão para versão.
A saída é o `key`, que o Streamlit transforma numa classe:

```python
st.container(border=True, key="painel_da_receita_ao_saldo")
```
```css
div[class*="st-key-painel_"] { background: #FFF; box-shadow: …; }
```

`painel()` deriva a chave do título sozinho; só painel **sem** título precisa
passar `chave=`.

---

## 3. Um nível de caixa só

O cartão de meta tinha três `st.metric` dentro — e `st.metric` desenha a
própria borda. Caixa dentro de caixa dentro de caixa.

A troca foi para [`c.estatisticas`](../ui/componentes.py), que já existia e é
exatamente isto: *"números de apoio, sem moldura… a ausência de borda é o que
os mantém no segundo plano"*. **Mesmos três números, mesma ordem, mesma
coluna** — só a moldura de cada um sumiu.

---

## 4. O selo

O status da meta era `✅ no ritmo` no fim de uma frase. Virou pastilha
(`c.selo`), no mesmo ponto da mesma frase, com a cor dizendo o que o emoji
dizia. `selo()` **devolve** HTML em vez de desenhar, porque ele quase nunca
aparece sozinho — entra no meio de uma linha que já existe.

Fundo claro com texto escuro da mesma família, nunca cor cheia: uma pastilha de
status não pode competir com o número que ela está qualificando.

---

## 5. Gráficos

Em `_estilo()`, num lugar só, valendo para os 40 gráficos: canto arredondado
nas barras (`marker_cornerradius=4`), fonte Inter igual à do resto, e o fim da
linha de eixo — a grade horizontal já dava a referência, e a linha era um
segundo traçado dizendo o mesmo.

O raio é pequeno de propósito: em barra empilhada cada segmento arredonda, e um
raio grande separaria visualmente pedaços que são a mesma coluna.

---

## 6. Como se prova que só a pele mudou

Capturando o texto da tela antes e depois e comparando linha a linha:

```
antes: 148 linhas · depois: 148 linhas
IDENTICO — nenhuma linha de conteudo mudou.
```

Rótulo de eixo sai dos dois lados antes de comparar: a densidade de rótulos que
o Plotly desenha depende da **largura**, e o gráfico ficou mais estreito ao
entrar no cartão. Isso é desenho, não conteúdo.

A única diferença aceita e declarada é em Metas: o `✅` sumiu da frase porque
virou a cor da pastilha.

### E quando a captura "antes" já não existe mais

No primeiro lote a baseline foi capturada antes de começar. No segundo (as onze
telas restantes) o código já estava alterado quando veio a aprovação — não havia
"antes" para comparar.

A saída é o git: uma **worktree** no commit anterior, com uma cópia do banco
dentro dela, rodando num servidor paralelo na porta 8578. As duas versões vivas
ao mesmo tempo, e as 13 telas percorridas nas duas.

```
git worktree add <temp> <commit-anterior>
cp dados/financas.db <temp>/dados/
```

A cópia do banco importa: a worktree tem o seu próprio `dados/`, e
`config.RAIZ` é derivado de `__file__`. Sem a cópia, a versão antiga subiria com
banco vazio e a comparação não diria nada.

**Resultado: as 13 telas, mesma contagem de linhas e mesmo hash.**

E um teste que só diz "igual" não prova nada, então o hash foi conferido contra
si mesmo: trocando um caractere do texto ou removendo uma linha, ele muda. É o
que separa "comparei e bateu" de "meu comparador está quebrado".

---

## 7. A fonte ficou a do sistema — e a história vale ser contada

A reforma chegou a apontar para a Inter, a fonte das referências, hospedada no
Google Fonts. Ela voltou atrás, e o caminho até essa decisão tem duas lições.

### A configuração estava silenciosamente quebrada

A primeira tentativa foi:

```toml
font = "Inter:https://fonts.googleapis.com/css2?family=Inter…&display=swap, sans-serif"
```

O formato `"<nome>:<url>"` é documentado pelo Streamlit. Mas a vírgula com o
fallback no fim confundia o parser: ele descartava a URL e ficava só com o
nome. Resultado — a página pedia uma fonte chamada "Inter" que ninguém tinha
baixado, e caía no padrão do navegador. **Nenhuma tela chegou a ser vista com
Inter, e ninguém percebeu.**

O que expôs isso não foi olhar a tela (as duas fontes são parecidas o
bastante), foi medir:

```js
largura('Inter')            // 400.83
largura('FonteQueNaoExiste') // 400.83  ← idênticas: a Inter não existe aqui
```

**Lição: `document.fonts.check('16px Inter')` devolve `true` para qualquer
nome** — inclusive para uma fonte inventada. Ele não serve para responder "a
fonte carregou?". Medir a largura do mesmo texto e comparar com uma fonte que
sabidamente não existe serve.

### E aí a decisão ficou fácil

Com a URL corrigida a Inter funcionou de verdade (1 pedido, 920 bytes, ~190 ms
na primeira carga; zero nas seguintes, porque o navegador cacheia). Mas duas
coisas pesaram contra:

1. **O app é local em todo o resto.** O banco está no seu disco e nada sai
   daqui. A fonte remota seria a única coisa da tela a depender de internet — e
   a única a contar para um servidor de fora que este painel foi aberto.
2. **As telas aprovadas foram vistas sem Inter.** O visual que agradou já é o
   da fonte do sistema. Ligar a Inter depois da aprovação mudaria justamente o
   que tinha sido aprovado.

Se um dia ela fizer falta, o caminho sem rede é baixar o `.woff2` para dentro
do projeto e declarar `[[theme.fontFaces]]` apontando para `app/static/`, com
`server.enableStaticServing = true`.
