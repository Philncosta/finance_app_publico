# 03 · A leitura dos arquivos

Arquivos do código: [`financas/leitores/`](../financas/leitores/) e
[`financas/formato.py`](../financas/formato.py)

Este é o assunto mais "sujo" do projeto, e por um motivo justo: arquivo de
banco é cheio de detalhe estranho. Cada armadilha listada aqui foi descoberta
testando com os **seus arquivos de verdade** — nenhuma apareceria com dados
inventados.

---

## Os formatos

### Os três da conta corrente

| Arquivo | Colunas | Onde está o mês |
|---|---|---|
| `Fatura2026-01-05.csv` | `Data;Estabelecimento;Portador;Valor;Parcela` | **do nome do arquivo, menos um mês** |
| `extrato_de_..._.csv` | `Data;Hora;Descricao;Valor;Saldo` | na data de cada linha |
| `extrato_de_..._.ofx` | formato OFX (SGML) | na data de cada linha |

### Os dois da corretora

Chegaram depois, e são de natureza diferente: **não viram lançamento**.
Comprar um título não é despesa — é dinheiro mudando de lugar dentro do
seu patrimônio. Se entrassem em `lancamentos`, o Dashboard diria que você
gastou R$ ····.

| Arquivo | O que traz | Vira |
|---|---|---|
| `PosicaoDetalhada.xlsx` | quanto cada papel vale | saldo da carteira |
| `Extrato 12345678 ….xlsx` | compras, juros, IRRF | `investimentos_movimentos` |

As armadilhas desses dois (colunas que mudam de bloco, o rótulo de
indexador que mente, a linha de totais que parece ativo, a seção de
lançamentos futuros) estão em
[12 · Carteira e rebalanceamento](12_carteira_e_rebalanceamento.md).

---

## As armadilhas, uma por uma

### 1. O BOM invisível na fatura

O arquivo de fatura começa com **três bytes invisíveis** chamados BOM (*Byte
Order Mark*), que marcam "isto é UTF-8".

Se você abrir com `encoding="utf-8"`, o nome da primeira coluna vira
`"\ufeffData"` em vez de `"Data"` — e nenhuma busca por `"Data"` funciona. O
erro é traiçoeiro porque, ao imprimir na tela, os dois parecem idênticos.

**A solução:** abrir com `encoding="utf-8-sig"`. O `-sig` faz o Python
descartar o BOM sozinho.

```python
texto = caminho.read_text(encoding="utf-8-sig", errors="replace")
```

Usamos `utf-8-sig` também no extrato, que **não** tem BOM. Não faz diferença
nenhuma quando não há BOM, e protege caso um dia apareça.

### 2. Dinheiro em texto, em dois padrões diferentes

Os arquivos não trazem números — trazem texto que *parece* número:

```
"R$ ····"    fatura e extrato CSV  →  1234.56
"-R$ ····"      saída no extrato CSV  →  -82.67
"-500.00"        OFX, padrão internacional  →  -500.0
```

Repare o conflito: no padrão brasileiro o ponto é separador de **milhar**; no
internacional é o separador **decimal**. `"1.500"` pode ser mil e quinhentos ou
um e meio.

**Como `parse_brl` decide** (em `formato.py`):

- Tem vírgula? É brasileiro → o ponto é milhar (joga fora), a vírgula vira o
  ponto decimal.
- Não tem vírgula mas tem `R$`? Também é brasileiro, sem centavos
  (`"R$ ····"` = mil e quinhentos) → o ponto é milhar.
- Não tem nem vírgula nem `R$`? É internacional → o ponto já é decimal, não
  mexe.

O símbolo `R$` funciona como a pista que resolve a ambiguidade.

### 3. Três formatos de data no mesmo sistema

```
"01/04/2026"    fatura        (ano com 4 dígitos)
"01/04/26"      extrato CSV   (ano com 2 dígitos)
"20260821"      OFX
```

`parse_data` testa os formatos em ordem e devolve o primeiro que der certo.
Ela também aceita o número de série do Excel (`46175` = 02/06/2026), que foi
necessário na migração.

### 4. O OFX que **mente** sobre o próprio encoding

Esta foi a mais interessante de todas.

O cabeçalho do seu arquivo do Banco XP declara:

```
ENCODING:USASCII
CHARSET:1252
```

Mas o conteúdo está gravado em **UTF-8**. A palavra "Transferência" aparece
nos bytes como `\xc3\xaa` (que é "ê" em UTF-8) e não como `\xea` (que seria
"ê" em Windows-1252).

Obedecendo o cabeçalho, sai `"TransferÃªncia"` na tela. Foi exatamente esse o
bug que apareceu no primeiro teste.

**A solução** usa uma propriedade do próprio UTF-8: ele é **autovalidável**.
As sequências de vários bytes seguem um padrão rígido, e texto acentuado em
Windows-1252 quase nunca forma um UTF-8 válido por acidente. Então:

1. Tenta UTF-8 no modo estrito. Passou? Era UTF-8 mesmo.
2. Falhou? Aí sim usa o charset declarado no cabeçalho.
3. Em último caso, `latin-1`, que aceita qualquer byte sem dar erro.

Essa ordem acerta tanto no arquivo que mente quanto no que fala a verdade.

### 5. O saldo final do OFX fica no fim do arquivo

O `<LEDGERBAL><BALAMT>` está no **byte 15.664** de um arquivo de 15.822. A
primeira versão do parser só lia os primeiros 4.000 caracteres para pegar o
cabeçalho, e o saldo vinha vazio.

Agora o saldo tem uma busca própria, no texto inteiro.

### 6. `NaN` é verdadeiro em Python

Esta não é dos arquivos, é da linguagem — mas atinge tudo que lê arquivo.

O pandas usa `NaN` ("não é um número") para célula vazia. E:

```python
>>> import math
>>> bool(math.nan)
True                  # NaN é VERDADEIRO!
>>> math.nan or 0
nan                   # e não 0, como a gente esperava
```

Então `linha["fim"] or 0` numa data em branco devolve `NaN`, e o cálculo
seguinte quebra — geralmente longe dali, o que torna o bug difícil de achar.

**A solução:** as funções `vazio()` e `ou()` em `formato.py`.

```python
dia = ou(linha["dia"], 1)          # em vez de  linha["dia"] or 1
```

`vazio()` considera vazio: `None`, `NaN`, `NaT`, string em branco e os textos
`"nan"` / `"nat"` / `"none"` / `"-"`.

### 7. O cifrão sumindo na tela

O Streamlit interpreta `$...$` como fórmula matemática (LaTeX). Se um texto
tem **dois** cifrões, ele acha que é fórmula e engole o trecho do meio:

```python
st.caption(f"Gastou {fmt_brl(a)} de {fmt_brl(b)}")
# aparece: "Gastou R R$ ···· de R R$ ····"  ← os valores sumiram
```

A tabela abaixo foi **verificada na tela**, não é teoria:

| Onde | Sem escape | Com escape |
|---|---|---|
| `st.caption` / `st.markdown` / `st.info` / `st.warning` | ❌ come o valor | ✅ correto |
| `st.markdown(..., unsafe_allow_html=True)` | ✅ correto | ❌ mostra `R\$` |
| `st.metric`, tabela, gráfico | ✅ correto | ❌ mostra `R\$` |

Por isso existem duas funções:

- **`fmt_brl()`** — o normal. Use em `st.metric`, tabelas, gráficos e dentro
  de HTML cru (o componente `c.nota`).
- **`fmt_brl_md()`** — escapado. Use em `st.caption`, `st.info`, `st.warning`,
  `st.markdown` comum.

O caso do HTML é o contraintuitivo: dentro de uma tag de bloco, o markdown não
processa o conteúdo, então a fórmula LaTeX não é detectada — mas a contrabarra
do escape também não é consumida, e apareceria `R\$` na tela.

---

## O contrato: o que todo leitor devolve

Não importa o formato de entrada, todo leitor devolve um `ResultadoLeitura`
(definido em `leitores/base.py`) com linhas no **mesmo formato**:

| Campo | Conteúdo |
|---|---|
| `data` | `AAAA-MM-DD` |
| `hora` | `HH:MM:SS` ou `None` |
| `mes_competencia` | `AAAA-MM` |
| `descricao` | estabelecimento ou histórico |
| `portador` | só a fatura tem |
| `valor` | **com sinal**, do seu ponto de vista |
| `parcela_atual`, `parcela_total` | 1 e 1 quando não é parcelado |
| `saldo_apos` | só extrato |
| `fitid` | só OFX |
| `origem` | `Fatura` ou `Extrato` |

Depois desse ponto, o sistema inteiro trata fatura e extrato do mesmo jeito.
Isso se chama **normalização**: você paga o preço de converter uma vez, na
entrada, e o resto do programa fica simples.

O resultado traz também:

- `avisos` — problemas que **não** impediram a leitura (uma linha estranha).
- `erros` — problemas que impediram.
- `meta` — informação sobre o arquivo (banco, conta, período, saldo), usada
  para mostrar "você está importando o extrato de 22/07 a 21/08 do Banco XP"
  antes de confirmar.

---

## O mês da fatura sai do nome do arquivo — e depois recua um mês

Esta é a regra que mais surpreende, então vale insistir. E ela **mudou em
25/08/2026** (migração 13); se você leu este guia antes disso, leia de novo.

`Fatura2026-01-05.csv` é a fatura que **vence em 05/01/2026**. Dentro dela há:

- compras de dezembro,
- parcelas de compras de outubro,
- parcelas de compras do ano passado.

**Todas contam em 2025-12** — o mês em que o dinheiro foi *gasto*, não o mês em
que a fatura vence.

### Por que não no mês do vencimento

Porque o cartão fecha por volta do dia 25, que é a mesma semana em que o
salário cai. Contar a fatura no vencimento separava o gasto do salário que o
paga:

```
salário de dezembro     cai ~25/12   →  competência 2025-12
gasto no cartão      26/11 a 25/12   →  competência 2025-12   ← o mesmo balde
essa fatura é paga        05/01/2026   com o dinheiro que já entrou
```

O caso extremo apareceu em setembro/2026: receita R$ ···· (o mês nem havia
começado) contra R$ ···· de fatura importada com antecedência. Saldo
−R$ ···· num mês que não existia ainda.

### Como isso está escrito no código

São **duas funções separadas de propósito**, em `leitores/fatura_csv.py`:

| Função | Responde | `Fatura2026-01-05.csv` |
|---|---|---|
| `mes_do_nome_arquivo()` | "o que está escrito no nome?" | `2026-01` |
| `competencia_da_fatura()` | "em que mês isso conta?" | `2025-12` |

A primeira é um **parser**; a segunda é a **regra**. Misturar as duas
esconderia uma decisão de negócio dentro de uma expressão regular.

Se o nome não tiver data, a tela de importação pergunta o **vencimento** para
você — e aplica o recuo sozinha, para você não ter que fazer essa conta de
cabeça.

> **A tentação seguinte, e por que ela é errada.** Parece natural que a
> projeção de caixa desloque a parcela +1 mês, "porque a fatura vence dia 05".
> Não: o salário e o gasto do mesmo ciclo já estão no mesmo balde, e o
> pagamento sai poucos dias depois com dinheiro que já entrou. Ver
> `calculos/planejamento.py`.

---

## Onde ver isso funcionando

Ler um arquivo real e imprimir o resumo:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas.leitores import extrato_ofx; r = extrato_ofx.ler_arquivo('extrato_de_22-07-2026_ate_21-08-2026.ofx'); print(r.resumo()); print(r.meta); print(r.linhas[0])"
```

Testar as conversões de formato:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas.formato import parse_brl, parse_data; print(parse_brl('R$ ····'), parse_brl('-500.00'), parse_data('01/04/26'), parse_data('20260821'))"
```
