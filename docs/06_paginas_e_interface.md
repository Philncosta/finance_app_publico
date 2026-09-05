# 06 · As páginas e a interface

Arquivos do código: [`paginas/`](../paginas/), [`ui/`](../ui/) e
[`app.py`](../app.py)

---

## Como uma página Streamlit funciona

Uma página é um **script comum**, lido de cima para baixo. Cada comando
`st.alguma_coisa()` desenha um pedaço na tela, **na ordem em que aparece no
código**.

```python
st.title("Dashboard")          # desenha o título
st.metric("Saldo", "R$ ····")   # desenha um cartão logo abaixo
```

Não existe "onde colocar este botão" — ele aparece onde a linha estiver. É a
coisa mais simples do Streamlit e a razão de ele ser tão fácil de começar.

---

## O modelo de reexecução (o conceito que mais confunde)

> **Toda vez que você mexe em qualquer coisa na tela, o Streamlit roda o
> script da página inteiro, de cima para baixo, de novo.**

Clicou num botão? Reexecuta. Trocou o mês no menu? Reexecuta. Digitou uma
letra numa caixa de texto? Reexecuta.

Isso parece desperdício, mas é o que permite o código ser linear e sem
"callbacks". A tela é sempre o resultado de rodar o script do zero com os
valores atuais dos controles.

### Consequência 1: variáveis normais somem

```python
contador = 0          # isto vira 0 DE NOVO a cada clique
if st.button("+1"):
    contador += 1     # nunca passa de 1
```

**A solução:** `st.session_state`, um dicionário que sobrevive às
reexecuções. No projeto isso está embrulhado em `ui/estado.py`:

```python
estado.guardar("importar_previa", previa)   # sobrevive
previa = estado.pegar("importar_previa")
estado.esquecer("importar_previa")
```

É assim que a tela de importação mantém a prévia enquanto você revisa e mexe
nas caixinhas.

### Consequência 2: ler o banco a cada clique seria lento

**A solução:** cache. A anotação `@st.cache_data` diz "guarde o resultado
desta função; nas próximas chamadas devolva o guardado sem executar nada".

```python
@st.cache_data(ttl=60)
def lancamentos():
    return dados.carregar_lancamentos()
```

O `ttl=60` é "guarde por 60 segundos". Escolhemos um tempo curto de propósito:
os dados mudam quando **você** importa ou edita, e nesses momentos chamamos
`estado.limpar_cache()` explicitamente. O `ttl` é só uma rede de segurança.

> **Regra que vale ouro:** todo código que **escreve** no banco (importar,
> editar, apagar, restaurar) precisa chamar `estado.limpar_cache()` logo
> depois. Se esquecer, a tela continua mostrando o dado velho e parece que a
> alteração não funcionou.

### `cache_data` × `cache_resource`

| Anotação | Guarda | Exemplo aqui |
|---|---|---|
| `@st.cache_data` | um **valor** (tabela, número, lista) | `estado.lancamentos()` |
| `@st.cache_resource` | um **recurso** ou efeito único | `estado.preparar_banco()` |

`preparar_banco()` usa `cache_resource` porque não está guardando um dado para
reusar: está garantindo que a criação das tabelas aconteça **uma vez só** por
sessão.

---

## A navegação

Montada em `app.py`, com `st.navigation`:

```python
paginas = {
    "Visão geral": [
        st.Page("paginas/dashboard.py", title="Dashboard",
                icon=":material/dashboard:", default=True),
        ...
    ],
    "Planejar": [...],
}
navegacao = st.navigation(paginas, position="sidebar")
navegacao.run()
```

**Por que `st.navigation` e não a pasta `pages/` automática:** a forma
automática tira os títulos do nome do arquivo (`1_Dashboard.py` viraria
"1 Dashboard") e não permite agrupar. Com `st.navigation` escolhemos o título,
o ícone e os grupos — que é o que dá o menu organizado em quatro seções.

Os ícones `:material/nome:` vêm do conjunto Material Icons, que o Streamlit já
traz embutido.

### A ordem obrigatória em `app.py`

```python
st.set_page_config(...)   # PRECISA ser o primeiro comando Streamlit
from ui import estado, tema   # imports vêm depois, de propósito
```

Se `set_page_config` vier depois de qualquer outro comando Streamlit, o app
para com erro. E como alguns módulos tocam no Streamlit ao serem carregados,
os imports deles ficam abaixo — por isso há um `# noqa: E402` naquela linha
(um aviso para o verificador de estilo não reclamar da ordem).

---

## O tema: como o CSS entra

`ui/tema.py` injeta o CSS com:

```python
st.markdown(CSS, unsafe_allow_html=True)
```

O nome `unsafe` assusta, mas só quer dizer "confie no HTML que estou
passando". Como esse HTML é escrito por nós no próprio arquivo — e nunca
montado com texto digitado por alguém — não há risco.

### A regra de segurança

> **Nunca coloque dado do usuário dentro de HTML cru sem escapar.**

Se a descrição de um lançamento fosse `<script>...`, jogar esse texto direto no
HTML seria um problema. Por isso `card_kpi()` e companhia passam todo texto por
`escapar_html()` antes de montar a marcação — ela troca `<` por `&lt;`, `&` por
`&amp;` e assim por diante.

### Por que os seletores CSS miram em `data-testid`

O Streamlit gera nomes de classe que mudam de versão para versão
(`.st-emotion-cache-1a2b3c`). Escrever regra em cima desses nomes quebra na
primeira atualização.

Por isso miramos em atributos **estáveis** — `data-testid`, que a equipe do
Streamlit mantém de propósito — e nas nossas próprias classes (`.cartao`,
`.kpi-valor`), que ninguém muda.

### O detalhe do `%` dobrado

O CSS usa `%(primaria)s` como marcador, e no fim fazemos
`CSS % config.CORES_TEMA` para substituir pelas cores. Como `%` é o caractere
de substituição, um `%` literal precisa aparecer dobrado:

```css
height: 100%%;    /* vira 100% depois da substituição */
```

---

## Os componentes

`ui/componentes.py` tem as peças reaproveitadas:

| Função | Desenha |
|---|---|
| `cabecalho(titulo, subtitulo)` | o título grande no topo |
| `secao(titulo, dica)` | divisória de seção (não é um título) |
| `destaque([...])` | 2 ou 3 números grandes, **sem moldura** |
| `estatisticas([...])` | números de apoio, sem borda nem sombra |
| `card_kpi(rotulo, valor, ...)` | um cartão com número grande |
| `linha_kpis([...])` | vários cartões lado a lado |
| `tarja(texto, tipo)` | faixa fina de contexto |
| `barra(percentual)` | barrinha de progresso colorida |
| `card_meta(titulo, atual, alvo)` | cartão com meta e barra |
| `etiqueta(texto, cor)` | devolve o HTML de uma etiqueta |
| `nota(texto_html)` | caixinha de observação com barra azul |
| `aviso_vazio(mensagem, dica)` | mensagem amigável quando não há dado |
| `config_moeda/percentual/data` | configuração de coluna para tabelas |

### O período dos gráficos

Fica na **barra lateral**, desenhado uma vez em `app.py`, e vale para o app
inteiro. Escolher "Tudo" no Dashboard e ir para o Patrimônio mantém a mesma
janela — os números continuam comparáveis entre telas.

```python
estado.seletor_de_periodo()          # desenha (uma vez, no app.py)
estado.recortar_serie(serie)         # corta uma série mensal
estado.recortar_lancamentos(df)      # corta lançamentos por mes_competencia
```

**Não confundir com o seletor de mês.** O mês diz *"qual mês estou
analisando"* — o Dashboard inteiro fala dele. O período diz *"quanto de
histórico quero ver nos gráficos de linha"*.

`estado.calcular_limites()` é a regra, separada como **função pura** para
poder ser testada no terminal. E há uma lição escrita nela: `meses()` devolve
do mais recente para o mais antigo, e a primeira versão assumia crescente — o
gráfico inteiro virava um ponto só. O teste não pegou porque eu havia montado
a lista ordenada de outro jeito. Hoje a função ordena o que recebe.

### A hierarquia: qual componente usar

Esta é a decisão que separa um painel legível de um amontoado. Foi aprendida
do jeito difícil: o Dashboard chegou a ter **dezesseis `card_kpi` idênticos**,
em quatro fileiras de quatro. Quando tudo se destaca, nada se destaca.

| Componente | Peso | Quantos por tela |
|---|---|---|
| `destaque` | 38px, sem moldura | 1 a 3 por seção |
| `estatisticas` | 20px, sem moldura | 3 a 5 por seção |
| `card_kpi` | 26px, com cartão | **a exceção** |

A regra prática: `destaque` responde a pergunta da seção; `estatisticas`
sustenta a resposta; `card_kpi` só quando algo precisa mesmo gritar.

**A ausência de moldura é o desenho.** Um número grande sozinho no branco pesa
mais que o mesmo número dentro de uma caixa igual a outras quinze — o cartão
só destaca enquanto for raro.

### O `?`: onde as explicações longas moram

`card_kpi`, `destaque`, `estatisticas` e `secao` aceitam `dica=`, que desenha
um círculo de 14px com o texto no `title` do HTML.

Antes, essas explicações eram `st.caption` soltos embaixo de cada gráfico.
Eram úteis na primeira leitura e viravam ruído na centésima — mas apagar seria
pior, porque o app também serve para aprender. O tooltip resolve os dois
lados, e o bloco *"Entenda esta tela"* no fim da página guarda as longas.

### O detalhe do `delta_positivo`

```python
card_kpi("Este mês vs média", "16,5%",
         delta="acima do normal", delta_positivo=False)
```

O texto do delta e o **significado** dele são parâmetros separados de
propósito: nem sempre "para cima" é bom. Gasto subindo é ruim; receita subindo
é boa. Quem chama decide o significado, e o componente só pinta.

### O detalhe da barra que passa de 100%

A largura desenhada é limitada a 100% — senão uma barra de 300% vazaria para
fora do cartão. Mas o **número** continua sendo mostrado por inteiro ao lado.

---

## Tabelas editáveis

`st.data_editor` é uma tabela onde você mexe nas células. Ela devolve o
DataFrame alterado quando o script roda de novo.

**Ela não salva sozinha no banco.** A gravação acontece quando você clica em
Salvar, e isso é proposital: evita gravar no meio de uma edição.

### A armadilha da coluna de data

O SQLite guarda data como **texto**. Se você entregar esse texto direto para
um `DateColumn`, o Streamlit quebra. O caminho é sempre:

```python
df["data"] = pd.to_datetime(df["data"])         # antes de mostrar
...
df["data"] = df["data"].dt.strftime("%Y-%m-%d") # antes de salvar
```

### A armadilha da célula vazia

Uma célula em branco no `st.data_editor` chega ao Python como `float('nan')`,
não como `None` ou `""`. Isso quebra o jeito óbvio de limpar um campo antes de
gravar:

```python
nome = str(linha.get("campo") or "").strip() or None   # ERRADO
```

`bool(float('nan'))` é `True`, então `NaN or ""` continua sendo `NaN` — e
`str(NaN)` é a string **"nan"**, gravada de verdade no banco em vez de `NULL`.
O mesmo vale para um campo com valor padrão: `linha.get("tipo") or "Renda
Fixa"` também devolve `NaN` (não o padrão) quando a célula está vazia, porque
o `or` nunca chega a testar o segundo lado.

O caminho seguro usa `formato.vazio()`, que trata `None`, `NaN` e a própria
string `"nan"` como a mesma coisa:

```python
def _texto_ou_none(valor) -> str | None:
    return None if vazio(valor) else str(valor).strip() or None

def _numero_ou(valor, padrao: float) -> float:
    return padrao if vazio(valor) else float(valor)
```

Achado em `metas_compras.py` (2026-08-30) e depois em mais 36 campos
espalhados por `configuracoes.py`, `gastos_fixos.py`, `investimentos.py` e
`regras.py` — todo lugar que limpa uma linha de `st.data_editor` antes de um
INSERT/UPDATE tem esse risco. Os dois ajudantes são pequenos o bastante para
copiar em cada arquivo (o projeto evita módulo compartilhado até 3+ usos reais
fora do mesmo arquivo), mas a lição — nunca `x or default` numa célula que
pode vir vazia do editor — vale em qualquer página nova.

### Salvar só o que mudou

Na tela de Lançamentos, ao salvar, o código compara a tabela editada com a
original e grava **só as linhas que mudaram**. Gravar tudo funcionaria, mas com
1.000 linhas seria lento e sujaria a coluna `atualizado_em` de registros
intocados.

### Colunas somente leitura

Na tela de Lançamentos, `data`, `descricao` e `valor` estão com
`disabled=True`. Não é capricho: essas colunas entram na impressão digital que
impede duplicata. Mudá-las quebraria a deduplicação e o mesmo lançamento
poderia entrar de novo na próxima importação.

---

## Formulários

```python
with st.form("form_lancamento_manual", clear_on_submit=True):
    descricao = st.text_input("Descrição")
    valor = st.number_input("Valor")
    enviado = st.form_submit_button("Adicionar")
```

O `st.form` junta vários campos e **só envia quando o botão é clicado**. Sem
ele, cada tecla digitada dispararia uma reexecução da página inteira.

---

## O padrão de uma página

Quase toda página deste projeto segue a mesma estrutura:

```python
# 1. Carregar (do cache)
df = estado.lancamentos()

# 2. Sair cedo se não há dado
if df.empty:
    c.aviso_vazio("Sem lançamentos ainda.")
    st.stop()

# 3. Seletor de mês, logo abaixo do título
mes = estado.seletor_de_mes_topo()

# 4. Calcular (chamando financas/calculos/)
painel = kpis.painel(df, mes)

# 5. Desenhar
c.cabecalho("Dashboard", ...)
c.linha_kpis([...])
st.plotly_chart(graficos.alguma_coisa(...), width="stretch")
```

`st.stop()` interrompe o script ali — nada abaixo é desenhado. É mais limpo
que embrulhar a página inteira num `else`.

O seletor de mês fica no `estado` (e não em cada página) para que trocar o mês
no Dashboard já deixe o Planejamento no mesmo mês.

---

## Quando duas telas mostram números diferentes de propósito

A tela de **Gastos fixos** diz R$ ···· A de **Planejamento** diz
R$ ···· As duas estão certas, e a diferença é a nutricionista, que já está
sendo projetada como parcela do cartão.

Duas telas discordando é um **bug** neste projeto — foi o que aconteceu com o
patrimônio, que lia R$ ···· a mais numa tela que na outra. A diferença aqui
é que estas duas respondem perguntas diferentes:

| Tela | Pergunta | Número |
|---|---|---|
| Gastos fixos | quanto eu cadastrei? | o piso bruto |
| Planejamento | quanto a previsão soma? | já sem o que vem por outro caminho |

**O que torna isso aceitável é a diferença ser explicável item a item.** Por
isso existe o painel *"O que entra na previsão de \<mês\>"*, com uma linha por
item e a coluna *Por quê*:

```
previsto                          ainda vai cair
lançado                           já saiu neste mês (R$ ····)
já está nas parcelas do cartão    parcela de R$ ····
desligado                         você tirou este item da previsão
fora                              não vale neste mês (início/fim)
```

Um número que difere de outro sem explicação é um defeito. Um número que difere
**com** a explicação ao lado é informação. A regra prática: se você vai mostrar
dois valores para a mesma coisa, mostre também a conta que leva de um ao outro,
na mesma tela.

### Mostrar a ambiguidade em vez de escolher por ele

O mesmo painel avisa quando uma chave de histórico casa com mais de uma
categoria — *"A chave «EDUARDO MOREIRA» casa com Casa, Lazer, Outros"*.

O app **poderia** ter escolhido sozinho (filtrar pela categoria do cadastro),
e teria acertado no aluguel e errado em dois outros itens, em silêncio. Quando
o dado não decide, quem decide é ele — o código só precisa de um lugar para
receber a resposta, e de um aviso para provocá-la.

---

## Um detalhe de versão

O parâmetro `use_container_width=True` foi **descontinuado** no Streamlit. O
substituto é:

```python
st.plotly_chart(figura, width="stretch")    # ocupa a largura toda
st.dataframe(tabela, width="content")       # ocupa só o necessário
```

Todo o projeto já usa a forma nova.

---

## O seletor de mês, e a lição de estado que ele ensina

O mês é o controle principal de quase toda tela, então ele fica **no topo da
página**, logo abaixo do título — não na barra lateral, onde ficava antes e
onde era fácil não ver. Tem também setas ◀ ▶, porque a comparação mais comum é
com o mês anterior e clicar é mais rápido que procurar na lista.

O código está em `ui/estado.py`, função `seletor_de_mes_topo()`. Ele resolve
**dois** problemas de estado do Streamlit que valem conhecer — os dois
apareceram na prática.

### Problema 0: a seta não passava do presente

Este apareceu depois, em 01/09/2026, e é o mais fácil de repetir num projeto
novo. A lista do seletor saía de `meses_disponiveis()`:

```sql
SELECT DISTINCT mes_competencia FROM lancamentos
```

Ou seja: **um mês só existia depois que alguma linha caía nele.** Com o mês
recém-virado, a ▶ nascia desabilitada — mesmo o app sabendo, pelos fixos e
parcelas, exatamente o que vai vencer nos meses seguintes.

A informação existia e era inalcançável, porque `previsao.do_mes()` monta um
mês futuro inteiro **sem precisar de lançamento nenhum**.

A saída foi `dados.meses_para_seletor(horizonte=12)`: o histórico, mais o mês
corrente, mais doze meses à frente.

**Repare no que NÃO foi feito:** `meses_disponiveis()` ficou intacta. Ela ainda
alimenta os seletores de Lançamentos, Patrimônio e Investimentos, onde um mês
futuro só produziria filtro vazio. A tentação era acrescentar um parâmetro
(`incluir_futuro=True`) — mas duas perguntas diferentes merecem **duas
funções**, com o nome dizendo qual é qual. Um parâmetro booleano na assinatura
obriga quem lê a ir ver o corpo para saber o que a chamada faz.

### Problema 0b: oferecer e validar com listas diferentes

Consequência direta do anterior, e o tipo de bug que se manifesta como
*"cliquei e não aconteceu nada"*.

`mes_selecionado()` confere se o mês guardado ainda é válido. Se ela olhasse
`meses()` (só o passado) enquanto o seletor oferece `meses_do_seletor()` (com
futuro), escolher novembro seria desfeito **na mesma execução**: o valor cairia
no `if atual not in disponiveis` e voltaria para o padrão.

> **A regra:** um valor tem de ser validado pela **mesma** lista que o ofereceu.
> Oferecer por uma e validar por outra é uma contradição silenciosa — nada dá
> erro, a escolha só não gruda.

### Problema 1: o título mostrava o mês antigo

O Dashboard desenha o título (*"ago/2026 · 102 lançamentos"*) **antes** do
menu. Se o menu guardasse a escolha só depois de desenhado, o título ficaria
um render atrasado.

A solução é ler o estado do próprio widget, que o Streamlit grava **antes** de
reexecutar o script:

```python
mes = estado.mes_selecionado()   # só lê — pode ser chamado antes do menu
...
c.cabecalho("Dashboard", f"{rotulo_mes(mes)} · ...")
estado.seletor_de_mes_topo()     # desenha o menu
```

### Problema 2: trocar de página perdia o mês

O Streamlit **descarta o estado de um widget quando ele some da tela** — e
mudar de página faz exatamente isso. Na primeira versão, escolher agosto no
Dashboard e ir para o Planejamento voltava para setembro.

Por isso o mês usa **duas** chaves:

| Chave | Papel |
|---|---|
| `mes_selecionado` | armazenamento durável — nunca é `key` de widget, então nunca é descartado |
| `widget_mes_topo` | a `key` do menu suspenso |

E `mes_selecionado()` consulta nesta ordem: primeiro o widget (que tem o valor
mais recente na execução atual), depois o armazenamento durável (que sobrevive
à troca de página).

> **A regra geral:** se um valor precisa sobreviver à navegação, ele **não**
> pode morar na `key` de um widget. Guarde numa chave própria e sincronize as
> duas.

### Problema 3: a ordem dos botões no código

Os botões ◀ ▶ são criados **antes** do menu, e não é capricho de layout
(`st.columns` deixa preencher as colunas em qualquer ordem).

É que, ao clicar numa seta, precisamos escrever em
`st.session_state["widget_mes_topo"]` — e o Streamlit **proíbe** escrever numa
chave depois que o widget dono dela já foi criado naquela execução. Criando os
botões primeiro e chamando `st.rerun()` logo em seguida, o menu nem chega a ser
desenhado naquela passada.

### O que continua reiniciando

Recarregar a página no navegador (F5, ou digitar o endereço de novo) começa uma
**sessão nova** do Streamlit, e aí o mês volta para o padrão. Isso é normal e
vale para qualquer coisa guardada em `session_state`. Navegar pelo menu do app
mantém tudo.
