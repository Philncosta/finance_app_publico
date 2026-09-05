# 00 · Comece aqui

Este é o primeiro arquivo para ler. Ele explica o que você precisa saber antes
de abrir qualquer código.

---

## 1. Como rodar o app

**Duplo clique em `iniciar.bat`.**

Vai abrir uma janela preta (o terminal) e, alguns segundos depois, o navegador
com o painel. A janela preta precisa **continuar aberta** enquanto você usa o
app — é ela que está rodando o programa. Fechar a janela fecha o app.

Se o navegador não abrir sozinho, digite `http://localhost:8501`.

---

## 2. As três peças que você precisa entender

O projeto usa três tecnologias. Nenhuma delas é complicada, mas vale saber o
que cada uma faz.

### Python

A linguagem de programação. É o que está escrito em todo arquivo `.py`.

Python foi escolhido porque é a linguagem mais legível que existe para
iniciante — muitas linhas parecem inglês comum:

```python
if valor < 0:
    print("saiu dinheiro")
```

### Streamlit

Uma biblioteca que transforma um script Python numa **página de internet**.

Sem Streamlit, um programa Python só fala com você pelo terminal (texto
preto e branco). Com Streamlit, você escreve:

```python
st.title("Dashboard")
st.metric("Saldo", "R$ ····")
```

e ele desenha um título e um cartão bonito no navegador. Você nunca escreve
HTML, CSS ou JavaScript — só Python.

### SQLite

O banco de dados. É onde os lançamentos ficam guardados.

O que faz o SQLite especial é que **ele cabe num arquivo só**:
`dados/financas.db`. Não precisa instalar servidor, não tem senha, não tem
nada rodando em segundo plano. Você copia esse arquivo e levou o banco
inteiro junto. É por isso que ele foi escolhido — você queria algo fácil de
transportar.

O Python já vem com o SQLite de fábrica, por isso ele nem aparece na lista de
bibliotecas instaladas.

---

## 3. O que é a pasta `.venv`

`venv` quer dizer *virtual environment* — **ambiente virtual**.

**O problema que ele resolve:** o Python instalado no seu Windows é um só. Se
o projeto A precisa da versão 1 de uma biblioteca e o projeto B precisa da
versão 2, eles brigam. Um deles vai quebrar.

**A solução:** cada projeto ganha a sua própria cópia isolada do Python, com
as suas próprias bibliotecas. Essa cópia vive na pasta `.venv`. Ela pertence
só a este projeto e não afeta mais nada no computador.

Por isso, sempre que você rodar algo deste projeto, use o Python de dentro
do `.venv`:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m migracao.conferir
```

E não simplesmente `python -m migracao.conferir` — esse usaria o Python do
sistema, que não tem as bibliotecas instaladas.

> A pasta `.venv` pode ser apagada e recriada a qualquer momento. Ela não
> contém nenhum dado seu — só bibliotecas baixadas da internet. O comando
> para recriar está no fim do [README](../README.md).

---

## 4. As bibliotecas instaladas

Estão listadas em `requirements.txt`:

| Biblioteca | Para quê |
|---|---|
| **streamlit** | transforma o script em site |
| **pandas** | tabelas em memória (o `DataFrame`) |
| **plotly** | os gráficos interativos |
| **openpyxl** | ler o `.xlsm` na migração e exportar `.xlsx` |
| **numpy** | contas numéricas (usado por baixo pelo pandas) |

---

## 5. O caminho que um dado percorre

Vale guardar esta sequência — ela explica a organização inteira do projeto:

```
   arquivo do banco (CSV/OFX)
            ↓
   financas/leitores/        transforma em linhas padronizadas
            ↓
   financas/regras.py        sugere a categoria
            ↓
   financas/importador.py    remove duplicata e grava
            ↓
   dados/financas.db         o banco
            ↓
   financas/dados.py         lê e enriquece
            ↓
   financas/calculos/        faz as contas
            ↓
   paginas/                  desenha a tela
```

Cada seta é uma etapa isolada. Quando um número aparece errado, dá para
descobrir **em qual etapa** o erro entrou, testando uma de cada vez.

---

## 6. O primeiro conceito difícil: o app roda inteiro a cada clique

Esta é a coisa mais estranha do Streamlit, e vale entender agora para não
sofrer depois.

**Toda vez que você mexe em qualquer coisa na tela** — clica num botão, troca
o mês no menu, digita numa caixa — **o Streamlit roda o script da página
inteiro, de cima para baixo, de novo.**

Isso é ótimo, porque o código fica simples e linear: você escreve os comandos
na ordem em que quer que apareçam na tela, e pronto. Não existe "quando
clicar, faça isso".

Mas tem duas consequências:

1. **Variáveis normais somem a cada clique.** Se você guardar algo numa
   variável comum, ela é criada de novo do zero no próximo clique.
   → Solução: `st.session_state`, um dicionário que sobrevive. No projeto,
   isso está embrulhado em `ui/estado.py` (`estado.guardar`, `estado.pegar`).

2. **Ler o banco a cada clique seria lento.**
   → Solução: **cache**. A anotação `@st.cache_data` diz "guarde o resultado
   desta função". Também está em `ui/estado.py`.

> **Regra prática:** sempre que o código escrever no banco (importar, editar,
> apagar), ele precisa chamar `estado.limpar_cache()` logo depois. Se
> esquecer, a tela continua mostrando o dado velho e parece que a alteração
> não funcionou.

---

## 7. Como testar um cálculo sem abrir o app

Esta é a vantagem prática de a pasta `financas/` não importar Streamlit.

Abra o Prompt de Comando na pasta do projeto e rode:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import dados; from financas.calculos import kpis; df = dados.carregar_lancamentos(); print(kpis.resultado_do_mes(df, '2026-08'))"
```

Vai imprimir o dicionário com receita, despesa e saldo daquele mês, direto no
terminal. Sem navegador, sem esperar o app subir.

É assim que todo número deste projeto foi conferido contra a planilha.

---

## 8. Por onde seguir

- Quer entender a **organização das pastas** → [01_organizacao_do_projeto.md](01_organizacao_do_projeto.md)
- Quer **mexer em alguma coisa agora** → [09_receitas_de_alteracao.md](09_receitas_de_alteracao.md)
- Bateu numa **palavra que não conhece** → [10_glossario.md](10_glossario.md)
