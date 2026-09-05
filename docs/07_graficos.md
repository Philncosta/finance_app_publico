# 07 · Os gráficos

Arquivo do código: [`ui/graficos.py`](../ui/graficos.py)

---

## Por que todos os gráficos ficam num arquivo só

**Consistência.** Todos passam pela mesma função de acabamento (`_estilo`), o
que garante a mesma fonte, a mesma altura, a mesma grade e as mesmas cores em
todas as telas. Gráfico feito "cada um do seu jeito" é o que faz um painel
parecer amador.

**Testabilidade.** Cada função recebe um DataFrame e devolve uma figura. Não lê
banco, não chama Streamlit. Dá para gerar qualquer gráfico num script e salvar
como imagem, sem abrir o app.

---

## A regra de cor

Cada grande categoria tem **uma cor**, definida no cadastro
(*Configurações → Grandes categorias*) e usada em **todos** os gráficos.
"Casa" é sempre índigo, "Comida" é sempre âmbar.

Isso permite bater o olho e reconhecer a categoria sem ler a legenda — e é uma
das coisas que mais diferencia um painel bom de um amontoado de cores.

Para valores, a convenção é fixa em todo o app:

| Cor | Significado |
|---|---|
| verde | entrou dinheiro / sobrou |
| vermelho | saiu dinheiro / estourou |
| âmbar | atenção, compromisso futuro |
| índigo | neutro, informativo |

---

## O catálogo

### Composição do mês

| Função | Tipo | Responde |
|---|---|---|
| `rosca_fixo_parcelado_variavel` | rosca | quanto do gasto eu conseguiria mudar no mês que vem? |
| `pizza_por_grande_categoria` | rosca | onde o dinheiro foi? |
| `barras_por_categoria` | barras horizontais | o detalhe por categoria |
| `barras_por_dia` | barras | em que dias do mês o dinheiro sai? |
| `cascata_do_mes` | cascata | o caminho da receita até o saldo |

### Histórico

| Função | Tipo | Responde |
|---|---|---|
| `historico_receita_despesa` | barras + linha | como os meses se comparam? |
| `linha_saldo_acumulado` | área | o dinheiro somou ou encolheu no ano? |
| `evolucao_por_grande_categoria` | barras empilhadas | qual categoria cresceu? |

### Parcelas e projeção

| Função | Tipo | Responde |
|---|---|---|
| `barras_parcelas_futuras` | barras | quanto já está comprometido em cada mês? |
| `barras_parcelamentos_ativos` | barras horizontais | quais compras ainda estou pagando? |
| `projecao_caixa` | empilhadas + linha | as despesas previstas passam a receita? |
| `linha_saldo_projetado` | área | quando o saldo fica negativo? |

### Orçamento, patrimônio, metas e financiamento

| Função | Tipo | Responde |
|---|---|---|
| `orcado_vs_real` | barras agrupadas | estou dentro do planejado? |
| `simulacao` | barras agrupadas | quanto sobraria se eu cortasse? |
| `patrimonio` | barras empilhadas | quanto em conta, quanto aplicado? |
| `progresso_metas` | barras empilhadas | quanto já tenho de cada meta? |
| `amortizacao_por_ano` | barras empilhadas | quanto do financiamento é juro? |
| `saldo_devedor` | área | como a dívida cai ao longo do contrato? |

### Os novos (não existiam na planilha)

| Função | Responde |
|---|---|
| `heatmap_dia_semana` | em que dia da semana eu gasto mais? |
| `top_estabelecimentos` | onde exatamente o dinheiro foi parar? |
| `cascata_do_mes` | qual parcela do gasto derrubou mais o saldo? |
| `alocacao_atual_vs_meta` | minha carteira está na alocação que eu quero? |
| `rebalanceamento_aporte` | para onde vai o aporte deste mês? |
| `variacoes_do_mes` | o que mudou contra o mês passado, e onde? |
| `taxa_de_poupanca` | estou guardando dinheiro, ao longo do tempo? |
| `comparativo_anual` | 2026 está melhor que 2025? |

#### `variacoes_do_mes`: o zero no meio é o desenho

Barras divergentes, com a linha do zero visível. Uma barra para a direita é
gasto que **subiu**, para a esquerda é gasto que **caiu** — o olho lê a
direção antes de ler o número, que é a ordem em que a pergunta se faz
("piorou ou melhorou?", depois "quanto?").

Vermelho para o que subiu e verde para o que caiu, e não o contrário: a
variável aqui é **despesa**, então subir é ruim. É a mesma inversão do
`delta_positivo` dos cartões.

Ele substituiu a seção "este mês foi normal?", que comparava com a média de
3 meses. Saber que você gastou 22% acima da média não permite fazer nada;
saber que **Saúde subiu R$ ····** permite.

#### `taxa_de_poupanca`: barras e linha juntas, e o eixo cortado

As barras são o mês, a linha é a média de 3 meses. As duas juntas porque uma
sozinha engana: só as barras é ruído puro (a receita oscila de R$ ···· a
R$ ····), só a linha esconde que houve mês no vermelho.

O eixo é cortado em **−100%**. Um mês magro pode dar −153%, e deixar a escala
livre espremeria todos os outros meses numa faixa ilegível por causa de um
ponto só.

#### `comparativo_anual`: médias mensais, nunca totais

Os anos têm tamanhos diferentes no banco — 2024 começa em abril, 2026 está
pela metade. Comparar totais faria 2026 parecer fraco por um motivo que não
tem nada a ver com dinheiro. A taxa de poupança de cada ano vai escrita em
cima do par de barras, porque é a leitura que importa e ela não aparece
sozinha na altura das barras.

#### `alocacao_atual_vs_meta`: por que sobreposto e não lado a lado

A barra clara é a **meta**, desenhada atrás; a colorida é o **atual**, na
frente e mais fina (`barmode="overlay"`). Lado a lado, você compararia dois
comprimentos; sobrepostas, você vê de relance se o atual **encheu** a meta ou
**passou** dela — que é a pergunta da tela.

A cor diz a situação: verde dentro da faixa, âmbar abaixo da meta, vermelho
acima. E o eixo é em **porcentagem**, então o `tickprefix="R$ "` que o
`_estilo` aplica precisa ser desfeito depois que ele roda.

---

## O futuro sombreado

Parcelas já contratadas criam lançamentos até dez/2026. Um gráfico que chega
lá, sem marcação, faz o futuro parecer passado — e um mês futuro **sempre**
parece péssimo, porque a despesa contratada já está lá e a receita ainda não.

`marcar_futuro(fig, meses)` sombreia a faixa e escreve *"ainda não
aconteceu"*. Uma faixa só, e não linha tracejada em cada série: com quatro
séries viraria poluição.

Detalhe que custa uma hora quando esquecido: os gráficos daqui usam eixo de
**categoria** (`jan/2026`, `fev/2026`), não de data. A faixa é posicionada por
índice, e começa em `indice - 0.5` porque a barra do índice N ocupa de N−0.5 a
N+0.5 — começar em N deixaria metade da barra de fora.

A `taxa_de_poupanca` não recebe a marcação **de propósito**: ela já exclui
meses em andamento por construção, então não há futuro ali.

---

## As decisões de desenho, e o porquê

### Por que a rosca tem buraco no meio

O buraco (`hole=0.62`) não é enfeite: ele deixa espaço para o **total**, que é
a informação que a pessoa procura primeiro. Sem ele, você teria que somar as
fatias de cabeça.

### Por que "por categoria" usa barras horizontais

Nome de categoria é texto, e texto se lê deitado. Em barra vertical,
"Serviços Domésticos" viraria um rótulo girado 45 graus que ninguém consegue
ler.

### Por que o gráfico por dia mostra os 31 dias

Todos os dias aparecem, mesmo os sem gasto. Sem isso, o eixo pularia de 3 para
7 e daria a impressão errada de que os dias foram seguidos.

O mesmo vale para a grade de parcelas futuras: meses com zero aparecem, senão
o gráfico "encurtaria" o tempo.

### Por que a projeção usa barras empilhadas com uma linha por cima

As barras mostram **de que é feita** a despesa de cada mês futuro; a linha
mostra a receita. Onde a pilha passa da linha, o mês fecha no vermelho — dá
para ver **sem ler número nenhum**.

### Por que o gráfico de amortização por ano, e não por parcela

360 linhas não cabem num gráfico legível; 30 barras sim. E cada barra conta a
história certa: nos primeiros anos a parte vermelha (juros) domina e a verde
(amortização) é um fiozinho. É a imagem que explica por que a dívida "não
anda" no começo — e por que adiantar parcela cedo economiza tanto.

### Por que a cascata

Ela mostra o **caminho** do dinheiro no mês, não só o começo e o fim. Cada
barra parte de onde a anterior terminou, então dá para ver qual parcela do
gasto derrubou mais o saldo.

---

## Detalhes técnicos que valem conhecer

### Fundo transparente

```python
paper_bgcolor="rgba(0,0,0,0)"
plot_bgcolor="rgba(0,0,0,0)"
```

Sem isso, o gráfico desenha um retângulo branco por cima do cartão. Com
transparência, ele assume a cor do cartão em que estiver.

### `hovermode="x unified"`

Mostra todos os valores daquele ponto numa caixinha só, em vez de uma por
série. Num gráfico de receita × despesa × saldo, isso é a diferença entre
comparar de olho e não conseguir comparar.

### Nunca passe `title=None`

> **Um bug que existiu aqui.** A primeira versão fazia:
>
> ```python
> fig.update_layout(title=dict(...) if titulo else None)
> ```
>
> O Plotly 6.x desenha literalmente a palavra **"undefined"** no topo do
> gráfico quando recebe `None` ali. Apareceram 6 "undefined" espalhados pelo
> Dashboard.
>
> A forma certa é **não incluir a chave**. Por isso o dicionário de layout é
> montado antes e o título só entra se existir.

### Toda chamada precisa de `key`

```python
st.plotly_chart(graficos.meu_grafico(dados), width="stretch",
                key="minha_pagina_meu_grafico")
```

> **Um bug que existiu aqui.** O Streamlit gera o ID de cada elemento a partir
> do **tipo e dos parâmetros**. Nos meses futuros, que quase não têm
> lançamento, vários gráficos devolvem a *mesma* figura de "Sem dados" — mesmo
> tipo, mesmos parâmetros, mesmo ID. Resultado:
> `StreamlitDuplicateElementId`, e a tela quebrava ao avançar o mês.
>
> Nos meses com dados isso nunca acontecia, porque cada gráfico é diferente —
> por isso o bug só aparecia à frente.
>
> A correção foi dar `key` explícita aos 28 gráficos do app, com o nome
> derivado da função (`dashboard_cascata_do_mes`). Nomes assim são estáveis:
> continuam válidos mesmo que alguém mova um gráfico de lugar.

A regra vale para qualquer elemento que possa se repetir com os mesmos
parâmetros: `plotly_chart`, `data_editor`, `button`, `selectbox`.

### Figura vazia em vez de `None`

Quando não há dado, as funções devolvem uma figura com um recado no meio
(`_sem_dados`), e não `None`. Isso mantém o layout inteiro: a página desenha o
gráfico do mesmo tamanho e não "pula" quando falta dado.

### O `reindex` nas barras empilhadas

```python
serie = recorte.set_index("mes")["valor"].reindex(meses, fill_value=0)
```

Garante uma barra por mês, mesmo nos meses sem gasto daquela categoria. Sem
isso, as pilhas ficariam desalinhadas — cada categoria começaria num mês
diferente.

---

## Como criar um gráfico novo

1. Escreva a função em `ui/graficos.py`, seguindo o padrão:

```python
def meu_grafico(df: pd.DataFrame) -> go.Figure:
    """Uma frase dizendo que PERGUNTA este gráfico responde."""
    if df.empty:
        return _sem_dados()

    fig = go.Figure(go.Bar(
        x=df["mes"], y=df["valor"],
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        hovertemplate="R$ %{y:,.2f}<extra></extra>",
    ))
    return _estilo(fig, altura=300, legenda=False)
```

2. Chame na página, **sempre com `key`**:

```python
st.plotly_chart(graficos.meu_grafico(dados_do_grafico), width="stretch",
                key="minha_pagina_meu_grafico")
```

**Não invente cores.** Use `CORES["primaria"]`, `CORES["sucesso"]`,
`CORES["perigo"]` ou `_cores_para(nomes, mapa)` para respeitar a cor de cada
categoria.

**Sempre termine com `_estilo(fig)`.** É ele que aplica fonte, margem, grade e
fundo transparente.

O `<extra></extra>` no `hovertemplate` remove a caixinha lateral que o Plotly
mostra por padrão com o nome da série — quase sempre redundante.

---

## Como ver um gráfico sem abrir o app

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import dados; from ui import graficos; df = dados.carregar_lancamentos(); fig = graficos.historico_receita_despesa(dados.por_mes(df)); fig.write_html('grafico.html'); print('salvo em grafico.html')"
```

Depois é só abrir `grafico.html` no navegador.

---

## A armadilha do eixo de categoria com nome numérico

Achada em 2026-08-23 no gráfico "Ano a ano", que aparecia com **um único rótulo
no eixo** e as barras invisíveis no canto.

Num eixo `type="category"`, as barras são posicionadas por **índice** — 0, 1, 2.
Mas uma anotação escrita assim:

```python
fig.add_annotation(x="2024", ...)     # o nome da categoria
```

é resolvida como o **número 2024**. As três anotações foram parar em
2024/2025/2026 na escala numérica, o autorange esticou o eixo de `[-0,5; 2,5]`
para `[-0,5; 2124]`, e com o eixo 850 vezes maior o `dtick` virou 40 — só o
índice 0 calhava de ser categoria de verdade.

**A correção é usar o índice:**

```python
for indice, (_, linha) in enumerate(df.iterrows()):
    fig.add_annotation(x=indice, ...)
```

> O ano tem **nome numérico**, e é por isso que a confusão acontece. Com uma
> categoria chamada "Renda Fixa" o Plotly não teria como se enganar. Num app
> financeiro, porém, anos e meses são categorias o tempo todo — vale conferir o
> `range` do eixo sempre que um gráfico de categoria sair estranho.

Como diagnosticar, no console do navegador:

```javascript
const d = document.querySelector('.js-plotly-plot');
d._fullLayout.xaxis.range        // deveria ser [-0.5, n-0.5]
d._fullLayout.xaxis._categories  // as categorias que ele reconheceu
```

---

## Rótulo de valor em gráfico de porcentagem

O gráfico "Quanto sobrou, mês a mês" tem o eixo em **%** — é o que permite
comparar meses de tamanhos diferentes. Mas o percentual sozinho não diz quanto
dinheiro é: "sobrou 48%" pode ser R$ ···· ou R$ ····

Por isso o valor em reais vai **na barra** (`text=[fmt_brl(v) ...]`), e o hover
traz receita e despesa junto.

Dois cuidados que o rótulo exigiu:

| Cuidado | Por quê |
|---|---|
| `textposition="auto"` | com `"outside"`, o rótulo de um mês muito negativo cai abaixo do piso do eixo e **some** |
| piso do eixo com folga | idem — jul/2026 (−118,8%) tinha a barra cortada num piso de −100% |

O piso continua existindo (hoje −150%): um mês magro pode dar **−236%**, e
escala livre espremeria todos os outros numa faixa ilegível por causa de um
ponto só.
