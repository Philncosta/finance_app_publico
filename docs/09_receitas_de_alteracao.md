# 09 · Receitas de alteração

Este é o arquivo para consultar quando você quiser **mudar alguma coisa**. Cada
receita diz onde mexer e o que não esquecer.

> **Antes de qualquer alteração maior:** gere um backup em
> *Configurações → Backup*. Leva dois segundos e evita dor de cabeça.

---

## Índice

1. [Adicionar uma categoria](#1-adicionar-uma-categoria)
2. [Criar uma regra de categorização](#2-criar-uma-regra-de-categorização)
3. [Corrigir a categoria de vários lançamentos de uma vez](#3-corrigir-a-categoria-de-vários-lançamentos-de-uma-vez)
4. [Adicionar um gráfico novo](#4-adicionar-um-gráfico-novo)
5. [Mudar um indicador do Dashboard](#5-mudar-um-indicador-do-dashboard)
6. [Mudar as cores do app](#6-mudar-as-cores-do-app)
7. [Adicionar uma coluna no banco](#7-adicionar-uma-coluna-no-banco)
8. [Criar uma página nova](#8-criar-uma-página-nova)
9. [Suportar um banco novo (outro formato de arquivo)](#9-suportar-um-banco-novo)
10. [Quando algo dá errado](#10-quando-algo-dá-errado)
11. [Mudar uma regra de negócio — onde mais ela está escrita?](#11-mudar-uma-regra-de-negócio)

---

## 1. Adicionar uma categoria

**Pela tela (o jeito normal):**

*Configurações → aba Categorias →* use a última linha vazia da tabela →
*Salvar categorias*.

Preencha:

| Campo | O que é |
|---|---|
| Categoria | o nome que vai aparecer nos menus |
| Grande categoria | o grupo largo (usado no orçamento e nos gráficos) |
| Natureza padrão | o que o sistema assume quando uma regra da fatura aponta para ela |
| Ativa | desmarcada, some dos menus mas o histórico continua |

**Se você quiser que ela venha de fábrica** num banco novo, acrescente também
em `financas/banco.py`, na lista `CATEGORIAS_PADRAO`:

```python
("Pets", "Casa", "Despesa"),
```

> **Não apague uma categoria que já tem lançamentos.** Desative em vez disso.
> Apagar deixaria os lançamentos apontando para o nada.

---

## 2. Criar uma regra de categorização

**O jeito rápido:** *Regras → aba Sugestões → Buscar sugestões*. O app procura
estabelecimentos recorrentes que nenhuma regra reconhece e sugere a categoria
que **você mesmo** usou à mão antes. Marque as que quiser e clique em criar.

**O jeito manual:** *Regras → aba Regras da fatura* (ou do extrato) → última
linha vazia → *Salvar*.

### O que não esquecer

**A ordem importa.** Regras são lidas de cima para baixo e a primeira que casar
vence. Coloque a específica em cima:

| Ordem | Palavra | Vira |
|---|---|---|
| 5 | XP EMPREGADORA (≥ 50.000, Entrada) | PLR |
| 6 | XP EMPREGADORA (Entrada) | Salário |

Invertido, os dois viram Salário.

**Regra nova só vale para as PRÓXIMAS importações.** Os lançamentos que já
estão no banco continuam como estão. Para corrigir o passado, use a receita 3.

**Depois de mexer, teste:** *Regras → aba Testar → Rodar teste*. Mostra quantos
lançamentos cada regra pegaria e revela regra morta ou canibal.

---

## 3. Corrigir a categoria de vários lançamentos de uma vez

*Lançamentos →* use os filtros (por exemplo, buscar "SHOPEE") *→ expanda
"Trocar a categoria de todos os lançamentos filtrados"* → escolha a nova →
*Aplicar*.

Isso altera **todos os lançamentos que estão passando pelos filtros**. Confira
o número que aparece antes de confirmar.

Depois, crie a regra correspondente (receita 2) para que os próximos venham
certos sozinhos.

---

## 4. Adicionar um gráfico novo

**Passo 1** — escreva a função em `ui/graficos.py`:

```python
def gastos_por_portador(df: pd.DataFrame) -> go.Figure:
    """Quanto cada portador do cartão gastou no mês."""
    if df.empty:
        return _sem_dados()

    agrupado = (df[df["e_despesa"]]
                .groupby("portador")["valor"].sum().mul(-1)
                .sort_values())

    fig = go.Figure(go.Bar(
        y=agrupado.index.tolist(), x=agrupado.values, orientation="h",
        marker=dict(color=CORES["primaria"], line=dict(width=0)),
        text=[fmt_brl(v) for v in agrupado.values],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>R$ %{x:,.2f}<extra></extra>",
    ))
    fig.update_yaxes(tickprefix="", gridcolor="rgba(0,0,0,0)")
    return _estilo(fig, altura=280, legenda=False)
```

**Passo 2** — chame na página, **sempre com `key`**:

```python
st.plotly_chart(graficos.gastos_por_portador(do_mes), width="stretch",
                key="dashboard_gastos_por_portador")
```

Sem a `key`, dois gráficos que devolvam a mesma figura vazia colidem e o
Streamlit quebra a tela com `StreamlitDuplicateElementId` — foi o que
acontecia nos meses futuros antes da correção.

### Regras da casa

- **Sempre termine com `_estilo(fig)`** — é ele que aplica fonte, margem,
  grade e fundo transparente.
- **Não invente cores.** Use `CORES["primaria"]`, `CORES["sucesso"]`,
  `CORES["perigo"]`, ou `_cores_para(nomes, mapa)` para respeitar a cor de
  cada categoria.
- **Devolva `_sem_dados()` quando não houver dado**, nunca `None` — isso
  mantém o layout estável.
- **Sempre passe `key=`** na chamada de `st.plotly_chart`.
- **Nunca passe `title=None`** ao Plotly: ele desenha "undefined" na tela.

---

## 5. Mudar um indicador do Dashboard

Os indicadores vivem em `financas/calculos/kpis.py`. Cada função devolve um
dicionário.

**Para acrescentar um indicador**, adicione a chave no dicionário:

```python
def resultado_do_mes(df, mes) -> dict:
    ...
    return {
        ...
        "gasto_por_dia": despesa / 30,      # novo
    }
```

E mostre na página, em `paginas/dashboard.py`:

```python
c.linha_kpis([
    ...
    {"rotulo": "Gasto médio por dia", "valor": fmt_brl(resultado["gasto_por_dia"])},
])
```

**Confira no terminal antes de abrir o app:**

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import dados; from financas.calculos import kpis; print(kpis.resultado_do_mes(dados.carregar_lancamentos(), '2026-08'))"
```

### Cuidado com o cifrão

Se o número for aparecer em `st.caption`, `st.info`, `st.warning` ou
`st.markdown` comum, use **`fmt_brl_md`**. Se for em `st.metric`, tabela,
gráfico ou dentro de `c.nota()`, use **`fmt_brl`**. A tabela completa está em
[03_leitura_de_arquivos.md](03_leitura_de_arquivos.md#7-o-cifrão-sumindo-na-tela).

---

## 6. Mudar as cores do app

**As cores das categorias** (as que aparecem nos gráficos):
*Configurações → Grandes categorias →* coluna Cor → código hexadecimal
(`#4F46E5`) → *Salvar*.

**As cores da interface** (fundo, botões, cartões): edite
`financas/config.py`, no dicionário `CORES_TEMA`:

```python
CORES_TEMA = {
    "primaria": "#4F46E5",    # botões e destaques
    "sucesso": "#10B981",     # verde: sobrou / receita
    "perigo": "#EF4444",      # vermelho: despesa / estourou
    ...
}
```

Esse mesmo dicionário alimenta o CSS **e** os gráficos, então mudar ali muda
tudo de uma vez.

Se mudar o fundo ou o texto, atualize também `.streamlit/config.toml`, que
define o tema base do Streamlit.

---

## 7. Adicionar uma coluna no banco

**Não mexa nos blocos de migração que já existem** — bancos antigos já rodaram
eles. Acrescente um bloco **novo no fim** da lista, em `financas/banco.py`:

```python
# ---------------------------------------------------------------- versao 2 --
MIGRACOES.append("""
ALTER TABLE lancamentos ADD COLUMN tags TEXT;
CREATE INDEX IF NOT EXISTS ix_lanc_tags ON lancamentos(tags);
""")
```

Ao abrir o app, a migração roda sozinha. Quem já tem banco recebe só a
alteração; quem está começando recebe tudo em ordem.

**Depois:**
1. Inclua a coluna no `SELECT` de `financas/dados.py`, função
   `carregar_lancamentos()`.
2. Se ela deve entrar no backup, ela já entra — o backup exporta a tabela
   inteira automaticamente.

**Se um dia você quiser REMOVER uma coluna, confira o backup antes.**
`backup.restaurar` monta o INSERT com as colunas que encontra dentro do CSV do
`.zip`. Some a coluna do banco e todo backup já gerado passa a falhar na
restauração com `no column named <coluna>` — e você descobre isso no pior dia
possível, que é justamente o dia em que precisou do backup.

O caminho seguro é em duas etapas: primeiro fazer `restaurar` ignorar coluna que
não existe mais, depois dropar. Enquanto isso não for feito, uma coluna morta
não incomoda ninguém — `gastos_fixos.parcelado` está lá por essa razão.

**Se a coluna nova tem um valor certo para os dados que já existem, preencha na
própria migração.** Um default estático deixa todo item antigo com o mesmo
valor, e alguém vai ter que corrigir na mão. A migração 19 é o exemplo: em vez
de deixar `forma_pagamento` inteiro como `'Conta'`, ela olhou o histórico de
cada item e votou pela origem majoritária. Migração pode ser uma função Python
quando o SQL não dá conta — veja `_migracao_19_forma_de_pagamento_do_fixo`.

---

## 8. Criar uma página nova

**Passo 1** — crie `paginas/minha_tela.py`:

```python
"""minha_tela.py — o que esta tela responde."""
from __future__ import annotations

import streamlit as st

from financas import dados
from financas.formato import fmt_brl
from ui import componentes as c
from ui import estado

df = estado.lancamentos()

c.cabecalho("Minha tela", "subtítulo explicando o que ela mostra")

if df.empty:
    c.aviso_vazio("Sem lançamentos ainda.")
    st.stop()

with st.sidebar:
    mes = estado.seletor_de_mes("Mês")

# ... o resto
```

**Passo 2** — registre no menu, em `app.py`:

```python
"Planejar": [
    ...
    st.Page("paginas/minha_tela.py", title="Minha tela",
            icon=":material/star:"),
],
```

Os ícones vêm do Material Icons: `:material/nome_do_icone:`.

---

## 9. Suportar um banco novo

Se você abrir conta em outro banco e o arquivo tiver formato diferente:

**Se for OFX** — provavelmente já funciona. O OFX é padrão. Teste:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas.leitores import extrato_ofx; r = extrato_ofx.ler_arquivo('caminho/do/arquivo.ofx'); print(r.resumo()); print(r.erros); print(r.linhas[:2])"
```

**Se for CSV com outros nomes de coluna** — acrescente os apelidos em
`financas/leitores/extrato_csv.py`:

```python
APELIDOS = {
    "descricao": {"descricao", "historico", "lancamento", "detalhe",
                  "movimentacao", "titulo"},     # ← novo apelido
    ...
}
```

O leitor já ignora acentos e maiúsculas ao comparar.

**Se for um formato realmente diferente** — crie
`financas/leitores/meu_banco.py` seguindo o contrato de
`leitores/base.py`, e registre a detecção em `importador.detectar_tipo()`.

**Não esqueça de criar a conta** em *Configurações → Contas*.

---

## 10. Quando algo dá errado

### A tela não atualizou depois de eu salvar

O cache. Todo código que escreve no banco precisa chamar
`estado.limpar_cache()` logo depois. Procure se está faltando.

### Aparece "R R$ ····" sem o cifrão

Você usou `fmt_brl` num contexto markdown. Troque por `fmt_brl_md`. Ver
[a tabela completa](03_leitura_de_arquivos.md#7-o-cifrão-sumindo-na-tela).

### Aparece "R\$ R$ ····" com uma barra

O contrário: você usou `fmt_brl_md` dentro de HTML cru (`c.nota` ou
`st.markdown(..., unsafe_allow_html=True)`). Troque por `fmt_brl`.

### Aparece "undefined" num gráfico

Alguém passou `title=None` ao Plotly. Não inclua a chave em vez de passar
`None`.

### O app não sobe / erro de import

Confira se está usando o Python da `.venv`:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "import streamlit, pandas, plotly; print('bibliotecas OK')"
```

Se der erro, recrie o ambiente (comando no fim do [README](../README.md)).

### Um número está diferente da planilha

Rode a conferência:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m migracao.conferir
```

Ela compara mês a mês e explica as três diferenças conhecidas (que são
esperadas, não erros).

### Importei duas vezes e desconfio de duplicata

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import banco; d = banco.consultar(\"SELECT data, valor, substr(descricao,1,40) AS d, COUNT(*) n FROM lancamentos GROUP BY data, valor, substr(descricao,1,40) HAVING COUNT(*)>1\"); print(f'{len(d)} possíveis duplicatas'); [print(dict(x)) for x in d[:10]]"
```

Se aparecer alguma, apague pelo `id` na tela de Lançamentos.

### Quero voltar ao estado de ontem

*Configurações → Backup e restauração →* escolha o backup pela data →
digite `RESTAURAR`.

---

## 11. Mudar uma regra de negócio

*(onde mais ela está escrita?)*

As receitas acima são para acrescentar coisas. Esta é para o caso mais
perigoso: **mudar uma regra que já está valendo.** Trocar uma cor não tem
consequência; trocar o significado de um campo tem — e a consequência aparece
longe do lugar que você editou.

### O caso real que gerou esta receita

Em 25/08/2026 a competência da fatura mudou do mês do **vencimento** para o mês
do **gasto** (migração 13). A mudança estava certa e foi bem feita: recalculou
os dados, recalculou a `chave_parcelamento`, atualizou o leitor e `docs/02`.

Mesmo assim deixou **quatro** pontas soltas, achadas só numa revisão linha a
linha:

| O que ficou para trás | Consequência |
|---|---|
| `id_unico` das 3.080 linhas de fatura | reimportar uma fatura duplicaria tudo — a deduplicação não reconhecia mais nada |
| `docs/03` e `leitores/base.py` | passaram a ensinar o contrário do que o código faz |
| o cabeçalho do próprio `fatura_csv.py` | contradizia uma função 90 linhas abaixo, no mesmo arquivo |
| `migracao/carregar.py` | (este foi lembrado, e é o motivo de os outros doerem menos) |

Nenhuma delas quebrava nada na hora. É esse o ponto.

### A checagem, antes de fechar a alteração

**1. O dado derivado precisa ser recalculado?**

Se a regra alimenta alguma coisa *calculada e guardada* — um hash, uma chave,
um total, um carimbo — essa coisa está velha agora. Procure assim:

```bash
grep -rn "nome_do_campo" financas/ paginas/ migracao/ verificacao/
```

Nesse caso `mes_competencia` alimentava `id_unico` e `chave_parcelamento`. A
segunda foi lembrada; a primeira, não.

**2. A regra está escrita em português em algum lugar?**

Quase sempre está, em três ou quatro:

```bash
grep -rn "palavra-chave da regra" docs/ README.md financas/ --include=*.md --include=*.py
```

Docstring do módulo, docstring da função, o guia em `docs/`, e às vezes o texto
de ajuda de uma tela. **`conferir_documentacao.py` não pega isso** — ele checa
se a docstring existe, nunca se ela é verdadeira.

**3. Existe uma segunda porta para a mesma função?**

Foi assim que o hash do arquivo ficou faltando: a importação por *upload* e a
por *pasta* faziam coisas diferentes, e só uma calculava o SHA-256. Se há dois
caminhos, os dois precisam da mudança — ou, melhor, precisam passar a chamar o
mesmo lugar.

**4. Escreva o porquê onde a decisão mora.**

Não só no CHANGELOG: um comentário na própria função, dizendo o que estava
errado antes. É o que este projeto já faz em toda parte, e é o que faz a regra
sobreviver a você.

---

## Uma última coisa

**Sempre que alterar o código, atualize:**

1. o comentário/docstring da função que você mexeu;
2. o arquivo de `docs/` correspondente;
3. o [CHANGELOG.md](../CHANGELOG.md), com a data e o motivo.

Isso não é burocracia — é o que faz você entender a própria decisão daqui a
seis meses, quando não lembrar mais por que fez daquele jeito.
