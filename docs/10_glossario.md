# 10 · Glossário

As palavras que aparecem no código e na documentação, explicadas com exemplos
deste projeto.

---

## Conceitos de Python

### Função

Um pedaço de código com nome, que recebe valores e devolve um resultado.

```python
def fmt_brl(valor):
    return f"R$ {valor:,.2f}"

fmt_brl(1234.5)      # devolve "R$ ····"
```

O que entra entre parênteses são os **parâmetros**. O `return` diz o que sai.

### Função pura

Uma função que só depende do que recebe e não mexe em nada por fora — não lê
arquivo, não escreve em banco, não imprime na tela.

Todas as funções de `financas/calculos/` são puras. É por isso que dá para
testá-las no terminal com valores inventados: elas sempre devolvem o mesmo
resultado para a mesma entrada.

### Docstring

O texto entre três aspas logo abaixo do `def`. É a documentação da função, e o
Python a guarda para você poder consultar:

```python
def parse_brl(texto):
    """Converte o dinheiro em texto para número."""
```

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas.formato import parse_brl; help(parse_brl)"
```

### Dicionário (`dict`)

Uma coleção de pares **chave → valor**. É como uma agenda: você procura pelo
nome e acha o telefone.

```python
resultado = {"receita": 19943.58, "despesa": 15475.97}
resultado["receita"]        # 19943.58
resultado.get("saldo", 0)   # 0, porque a chave não existe
```

Quase todas as funções de cálculo deste projeto devolvem um dicionário — assim
a página escolhe o que mostrar sem precisar decorar a ordem dos valores.

### Lista

Uma sequência ordenada.

```python
NATUREZAS = ["Despesa", "Receita", "Pagamento"]
NATUREZAS[0]     # "Despesa"
len(NATUREZAS)   # 3
```

### Tupla

Como uma lista, mas **não pode ser alterada** depois de criada. Escrita com
parênteses:

```python
(3, 10)     # parcela 3 de 10
```

`parse_parcela("3 de 10")` devolve uma tupla.

### `dataclass`

Um atalho para criar uma classe que só guarda valores. Sem ele você escreveria
20 linhas repetitivas; com ele:

```python
@dataclass
class Classificacao:
    categoria: str
    tipo: str
    natureza: str
```

O Python escreve sozinho o construtor, a representação em texto e a
comparação.

> **A pegadinha do `field(default_factory=list)`:** se você escrevesse
> `linhas: list = []`, TODAS as instâncias compartilhariam a MESMA lista. É um
> erro clássico. `field(default_factory=list)` cria uma lista nova para cada
> objeto.

### Decorador (`@alguma_coisa`)

Uma linha com `@` logo acima de um `def`. Ela **modifica** o comportamento da
função.

```python
@st.cache_data(ttl=60)
def lancamentos():
    return dados.carregar_lancamentos()
```

Aqui o decorador faz a função guardar o resultado, em vez de recalcular toda
vez.

### `with` (gerenciador de contexto)

Garante que algo seja "fechado" no fim, mesmo se der erro no meio.

```python
with banco.conectar() as conn:
    conn.execute("SELECT ...")
# aqui a conexão já foi fechada, aconteça o que acontecer
```

### `f-string`

Uma string com `f` na frente, onde você pode colocar valores entre chaves:

```python
nome = "agosto"
f"O mês é {nome}"          # "O mês é agosto"
f"{1234.5:,.2f}"           # "1,234.50"
```

### `None`

O "nada" do Python. Diferente de `0` e de `""` — significa "não existe valor".

### `NaN`

*Not a Number*, "não é um número". É o "vazio" do pandas.

> **A armadilha mais importante deste projeto:** `NaN` é **verdadeiro** em
> Python. Então `valor or 0` devolve `NaN`, e não `0`. Por isso existem as
> funções `vazio()` e `ou()` em `formato.py`.

### `try` / `except`

Tenta fazer algo e, se der erro, faz outra coisa em vez de o programa parar.

```python
try:
    numero = float(texto)
except ValueError:
    return None       # não deu para converter; devolve None
```

### `import`

Traz código de outro arquivo.

```python
from financas import banco              # traz o módulo inteiro
from financas.formato import fmt_brl    # traz só uma função
```

### `if __name__ == "__main__":`

"Só faça isto se este arquivo for executado diretamente, não se ele for
importado por outro." É o que impede o script de migração de rodar sozinho
quando alguém importa uma função dele.

---

## Conceitos de dados

### DataFrame

A "tabela em memória" do pandas. Parece uma planilha: colunas com nome, linhas
numeradas. A diferença é que ele sabe fazer sozinho coisas como "somar a coluna
valor agrupando por categoria" numa linha:

```python
df.groupby("categoria")["valor"].sum()
```

É o formato que todo o projeto usa para calcular e desenhar gráfico.

### Series

Uma coluna sozinha de um DataFrame.

```python
df["valor"]          # uma Series
df["valor"].sum()    # a soma dela
```

### `groupby`

"Agrupe por esta coluna e, para cada grupo, faça esta conta."

```python
gastos.groupby("categoria")["valor"].sum()
# devolve uma linha por categoria, com a soma de cada uma
```

### Máscara booleana

Uma Series de verdadeiro/falso usada para filtrar:

```python
df["valor"] < 0                 # uma máscara: True onde saiu dinheiro
df[df["valor"] < 0]             # só as linhas onde a máscara é True
```

O projeto guarda algumas máscaras prontas em `dados.enriquecer()`
(`e_despesa`, `e_parcelado`), porque as mesmas condições apareceriam em
dezenas de lugares.

### `fillna`

Troca `NaN` por um valor padrão.

```python
df["categoria"] = df["categoria"].fillna("Outros")
```

### `pivot`

Vira uma tabela "longa" numa tabela "larga": transforma valores de uma coluna
em colunas. Usado no mapa de calor.

### Média × mediana

| | O que é | Sensível a extremo? |
|---|---|---|
| **Média** | soma ÷ quantidade | sim, muito |
| **Mediana** | o valor do meio | não |

Com os seus dados: a média de despesa mensal é R$ ···· e a mediana é
R$ ···· A diferença vem da moto de R$ ···· comprada em fevereiro.

Por isso a **projeção** usa mediana (quer o mês típico) e o **Dashboard** usa
média (quer o que realmente aconteceu).

---

## Conceitos de banco de dados

### SQL

A linguagem para conversar com o banco.

```sql
SELECT descricao, valor FROM lancamentos WHERE mes_competencia = '2026-08'
```

### `SELECT` / `INSERT` / `UPDATE` / `DELETE`

Ler / inserir / alterar / apagar.

### `WHERE`

O filtro. "Só as linhas onde…"

### `JOIN` e `LEFT JOIN`

Juntar duas tabelas. `LEFT JOIN` traz **todas** as linhas da primeira, mesmo
as que não têm par na segunda:

```sql
SELECT l.*, c.grande_categoria
FROM lancamentos l
LEFT JOIN categorias c ON c.nome = l.categoria
```

Um `JOIN` normal sumiria com lançamentos cuja categoria não está cadastrada —
exatamente o tipo de perda de dado que não se percebe.

### Índice

Um "atalho de busca" que o banco cria para uma coluna. Sem ele, filtrar por mês
faz o banco ler as 1.073 linhas uma a uma. Com ele, pula direto.

### Chave primária

A coluna que identifica cada linha unicamente. Em `lancamentos` é o `id`.

### `UNIQUE`

Impede que dois registros tenham o mesmo valor naquela coluna. `id_unico` é
`UNIQUE` — é a última linha de defesa contra duplicata.

### Transação

Um conjunto de operações que acontecem **todas** ou **nenhuma**. Se der erro no
meio, tudo é desfeito (`rollback`). É o que impede o banco de ficar pela
metade.

### SQL injection

Um ataque em que alguém escreve comando SQL dentro de um campo de texto.
Evita-se passando valores como parâmetros:

```python
banco.executar("DELETE FROM lancamentos WHERE id = ?", (5,))   # certo
banco.executar(f"DELETE FROM lancamentos WHERE id = {5}")      # errado
```

### `PRAGMA`

Comando de configuração do SQLite. Ex.: `PRAGMA foreign_keys = ON`.

### Migração

Uma alteração na **estrutura** do banco (coluna nova, tabela nova) feita de um
jeito que preserva os dados existentes.

### Idempotente

Uma operação que pode ser repetida sem mudar o resultado. `banco.inicializar()`
é idempotente: rodar 10 vezes tem o mesmo efeito de rodar 1.

---

## Conceitos de Streamlit

### Reexecução (*rerun*)

Toda interação faz o Streamlit rodar o script da página inteiro de novo, de
cima para baixo. É o conceito mais importante e o mais estranho no começo.

### `session_state`

Um dicionário que **sobrevive** às reexecuções. É onde se guarda "qual mês está
selecionado" ou "qual arquivo está em revisão".

### Cache

Guardar o resultado de uma função para não recalcular. `@st.cache_data` para
valores; `@st.cache_resource` para recursos e efeitos únicos.

### `st.stop()`

Interrompe o script ali. Nada abaixo é desenhado. Usado para sair cedo quando
não há dado.

### Widget

Qualquer controle da tela: botão, caixa de texto, menu suspenso, caixinha de
marcar.

### `key`

Um nome único dado a um widget. Necessário quando há dois widgets iguais na
mesma página, senão o Streamlit os confunde.

---

## Conceitos do domínio financeiro

### Competência

O mês em que uma despesa **pesa no seu bolso** — que pode não ser o mês em que
ela aconteceu. Uma compra de outubro parcelada em 10x tem competência
espalhada por 10 meses.

### Parcela herdada

Uma parcela (2ª, 3ª, 4ª…) de uma compra feita num mês anterior. Você não
decidiu gastá-la neste mês — ela chegou sozinha.

### Novo comprometimento

Quanto de dívida **futura** você criou num mês. Uma compra de R$ ···· em 12x
gera R$ ···· de novo comprometimento (os outros 11 meses).

### Natureza

Que tipo de evento financeiro é. São seis:

| Natureza | O que é | Entra em receita/despesa? |
|---|---|---|
| Despesa | gasto de verdade | sim (despesa) |
| Receita | salário, Pix recebido | sim (receita) |
| Receita Extraordinária | PLR, indenização | sim (receita, destacada) |
| Pagamento | pagar a fatura do cartão | **não** |
| Investimento | aporte, resgate, rendimento | **não** (mas conta no Patrimônio) |
| Transferência | dinheiro que só mudou de lugar | **não** |

As três últimas ficam de fora dos totais de propósito: elas não são ganho nem
gasto, só movimentação. Se contassem, o mesmo dinheiro apareceria duas vezes.

A diferença entre **Investimento** e **Transferência** é sutil e importa: o
Investimento alimenta o cálculo do patrimônio (aportes e resgates da conta
investimento); a Transferência não alimenta nada — é para TED que você manda
para si mesmo em outro banco, dinheiro enviado e devolvido, repasse que só
passa pela sua conta.

### Receita extraordinária

Entrada que não se repete: PLR, indenização, restituição. Separada da receita
normal porque planejar em cima dela é enganoso.

### Tipo (Fixo × Variável)

**Fixo** é o que você não decide de novo a cada mês (aluguel, assinatura). Corta-se
mudando de contrato. **Variável** corta-se mudando de hábito.

### Grande categoria

O agrupamento largo (Casa, Comida, Moto). Existe porque um gráfico com 26
fatias é ilegível, e porque o orçamento fica mais fácil de manter com 10 metas
do que com 26.

### Reserva de emergência

Dinheiro guardado, medido em **meses de despesa** — não em reais. R$ ···· são
12 meses para quem gasta R$ ···· e 2,5 meses para quem gasta R$ ····.

### PRICE × SAC

Dois jeitos de amortizar um financiamento. **PRICE**: prestação fixa, paga mais
juros. **SAC**: prestação começa maior e vai caindo, paga menos juros no total.

### Amortização

A parte da prestação que realmente **abate a dívida** (o resto é juro e
seguro).

### LTV

*Loan to Value* — quanto do imóvel está financiado. Financiar R$ ···· de um
imóvel de R$ ···· dá LTV de 20%.

### MIP e DFI

Seguros obrigatórios do financiamento imobiliário. **MIP**: morte e invalidez,
incide sobre o saldo devedor. **DFI**: danos ao imóvel, incide sobre o valor do
imóvel.

---

## Formatos de arquivo

### CSV

*Comma-Separated Values* — texto simples com um separador entre as colunas. No
Brasil o separador costuma ser `;`, porque a vírgula já é o separador decimal.

### OFX

*Open Financial Exchange* — o formato padrão que bancos do mundo inteiro usam
para exportar extrato. Parece HTML, mas é SGML (um primo mais velho e mais
relaxado do XML: as tags simples não precisam ser fechadas).

### FITID

*Financial Institution Transaction ID* — um código único que o banco atribui a
cada transação no OFX. É o que torna a detecção de duplicata perfeita.

### BOM

*Byte Order Mark* — três bytes invisíveis no começo de um arquivo, marcando
"isto é UTF-8". Se não for tratado, gruda no nome da primeira coluna e quebra
a leitura. Resolve-se abrindo com `encoding="utf-8-sig"`.

### Encoding

Como as letras viram bytes no arquivo. UTF-8 é o padrão moderno; Windows-1252
é o antigo do Windows. Ler com o encoding errado transforma "Transferência" em
"TransferÃªncia".

### Hash (SHA-1, SHA-256)

Uma "impressão digital" de um texto ou arquivo: um código de tamanho fixo que
muda completamente se qualquer coisa na entrada mudar. Usado aqui para
identificar lançamentos repetidos e arquivos já importados.
