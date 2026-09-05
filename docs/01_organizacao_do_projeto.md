# 01 · Como o projeto está organizado

Este arquivo explica **por que** cada pasta existe. A ideia central é simples:
cada pasta tem um trabalho só, e ninguém invade o trabalho do vizinho.

---

## O mapa

```
finance_app/
├── app.py            ← a porta de entrada
├── financas/         ← O MOTOR   (as contas)
├── ui/               ← A CARA    (a aparência)
├── paginas/          ← AS TELAS  (o que você vê)
├── migracao/         ← scripts usados uma vez, para trazer o Excel
├── verificacao/      ← testes que provam que uma conta está certa
├── analises/         ← relatórios de terminal, fora do painel
├── dados/            ← o banco e os backups
└── docs/             ← esta explicação
```

---

## A regra mais importante do projeto

> **Nenhum arquivo dentro de `financas/` importa `streamlit`.**

Se você abrir qualquer arquivo dessa pasta, vai ver imports de `pandas`, de
`sqlite3`, do próprio projeto — mas nunca `import streamlit as st`.

### Por que isso importa

Porque separa **calcular** de **mostrar**. E isso traz três benefícios
concretos:

**1. Dá para testar no terminal.** Um cálculo que não depende de Streamlit
pode ser rodado com um comando de uma linha, sem subir servidor nenhum. Foi
assim que todos os números deste projeto foram conferidos contra a planilha:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m migracao.conferir
```

**2. Dá para achar o erro.** Quando um número aparece errado na tela, a
primeira pergunta é: *o cálculo está errado, ou é a tela que está mostrando
errado?* Com as camadas separadas, você testa o cálculo isoladamente e a
resposta aparece em segundos.

**3. Se um dia você trocar o Streamlit por outra coisa**, todo o motor
continua valendo. Só a camada de cima seria refeita.

---

## Onde o *porquê* mora (e por que não é dentro do código)

> **O código não tem comentários `#`. A explicação vive em três lugares, e
> cada um responde a uma pergunta diferente.**

| Onde | Responde | Exemplo |
|---|---|---|
| **docstring** | *como se usa isto, e que armadilha tem?* | `rebalancear()` lista as quatro garantias que a função promete |
| **`docs/`** | *que conceito é esse, e por que o sistema pensa assim?* | por que a reserva sai do patrimônio próprio |
| **`CHANGELOG.md`** | *o que mudou naquele dia, e o que estava errado antes* | por que a competência da fatura recuou um mês |

### Por que essa escolha

Até 2026-08-28 havia **2.988 linhas de comentário** espalhadas pelos arquivos
`.py` — mais de um décimo do projeto. Elas eram boas, e ainda assim eram o
lugar errado:

**1. Comentário envelhece ensilvado no código e ninguém percebe.** A docstring
viaja junto com a assinatura da função: mudou o que ela devolve, você está
olhando para a explicação. Um bloco de vinte linhas trinta linhas acima, não.

**2. A mesma coisa estava escrita duas vezes.** Quase todo bloco de decisão
tinha um parágrafo equivalente em `docs/` ou no CHANGELOG. Duas cópias da
mesma verdade viram, com o tempo, duas versões diferentes dela.

**3. O código ficava difícil de ler *como código*.** `investimentos.py` tinha
421 linhas de comentário em 2.200. Para ver o que a função fazia era preciso
rolar por cima da explicação de por que ela existe.

### O que continua no código

- **Docstring de módulo, de classe e de função** — obrigatória, e
  `verificacao/conferir_documentacao.py` reprova a build se faltar uma.
- **Diretivas de ferramenta** (`# noqa`, `# type:`) — são instrução para o
  interpretador e para o linter, não texto para humano.

### E se eu apagar um porquê sem querer?

Ele está no git. `git log -p -- caminho/do/arquivo.py` mostra todo comentário
que já existiu ali. O commit anterior a esta limpeza guarda os 2.988 originais.

---

## `financas/` — o motor

Aqui mora tudo que **sabe fazer contas** e **sabe falar com o banco**.

| Arquivo | Trabalho |
|---|---|
| `config.py` | Constantes: caminhos de pasta, listas de opções válidas, cores. Um lugar só para tudo que é fixo. |
| `formato.py` | Traduz texto ↔ número ↔ data. É quem entende `"R$ ····"` e `"01/04/26"`. |
| `banco.py` | Abre o SQLite, cria as tabelas, faz as migrações. |
| `dados.py` | Lê o banco e devolve tabelas já enriquecidas, prontas para calcular. |
| `regras.py` | O motor de categorização automática. |
| `importador.py` | O caminho completo de um arquivo até o banco, com deduplicação. |
| `backup.py` | Gera o `.zip` de backup e restaura. |
| `cambio.py` | Dólar ↔ real, pelo PTAX do Banco Central. |
| `cotacoes.py` | Preço de ativo por ticker, guardado localmente. |
| `indices.py` | CDI e IPCA, das séries SGS do Banco Central. |
| `leitores/` | Um arquivo por formato — **cinco**: `fatura_csv`, `extrato_csv`, `extrato_ofx`, `posicao_xp`, `extrato_xp_xlsx`. |
| `calculos/` | Um arquivo por área — **onze**: `kpis`, `parcelas`, `fixos`, `planejamento`, `previsao`, `patrimonio`, `investimentos`, `imposto`, `metas`, `compras`, `financiamento`. |

### Por que `leitores/` tem um arquivo por formato

Porque os três formatos não têm nada em comum além do resultado. A fatura tem
BOM e coluna de parcela; o extrato CSV tem hora e saldo; o OFX é SGML com
FITID. Misturar os três num arquivo só criaria uma sopa de `if`.

Cada leitor faz o seu trabalho e devolve o **mesmo formato padronizado**
(descrito em `leitores/base.py`). Depois desse ponto, o resto do sistema não
sabe nem se importa de onde o dado veio. Esse padrão tem nome:
**normalização** — você paga o preço de converter uma vez, na entrada, e o
resto do programa fica simples.

### Por que `calculos/` tem um arquivo por área

Porque cada um responde uma pergunta diferente, e assim você sabe onde
procurar. "Quanto sobrou no mês?" está em `kpis.py`. "Quanto ainda vou pagar
de parcela?" está em `parcelas.py`.

### Pura, ou só sem Streamlit? São duas coisas

Este guia já disse que *"todas as funções aí são puras: não mexem em arquivo
nem em banco"*. **Isso não é verdade**, e a diferença importa na hora de
testar.

Uma função **pura** recebe dados e devolve dados. `kpis.resultado_do_mes(df,
mes)` é assim: dê o mesmo DataFrame e ela devolve o mesmo número, sempre.

Mas `calculos/investimentos.py` **lê e escreve no banco** — `salvar()`,
`salvar_saldo()`, `gravar_posicao()`, `apagar()`. E `planejamento.py`,
`metas.py`, `compras.py` e `fixos.py` leem o banco para buscar cadastro. O
próprio topo de `investimentos.py` diz a verdade: *"todas as funções aqui são
puras **ou leem o banco**"*.

A regra que vale para a pasta inteira é a outra, e essa é cumprida sem
exceção:

> **Nada em `financas/` importa `streamlit`.**

É ela que permite testar no terminal. Pureza é um bônus onde existe — e onde
não existe (qualquer coisa que grave), o teste precisa cuidar de devolver o
banco ao estado em que o encontrou. Ver `verificacao/conferir_previsao.py`,
que aprendeu isso do jeito difícil.

---

## `ui/` — a cara

Aqui mora tudo que **desenha** e tudo que **conversa com o Streamlit**.

| Arquivo | Trabalho |
|---|---|
| `tema.py` | O CSS. Cores, cartões arredondados, sombras. |
| `componentes.py` | Peças reaproveitadas: cartão de indicador, barra de progresso, etiqueta. |
| `graficos.py` | Todos os gráficos, em Plotly. |
| `estado.py` | O cache e a memória entre cliques. É a única "cola" com o Streamlit. |

### Por que `componentes.py` existe

O cartão de indicador aparece umas 40 vezes no app. Se cada página montasse o
seu, seriam 40 cópias do mesmo HTML — e mudar a aparência significaria editar
40 lugares (e esquecer alguns).

Com o componente, a página escreve uma linha:

```python
componentes.card_kpi("Saldo do mês", fmt_brl(4467.61), cor="verde")
```

e não precisa saber nada de HTML.

### Por que `graficos.py` junta todos os gráficos

Dois motivos:

- **Consistência.** Todos passam pela mesma função de acabamento (`_estilo`),
  que garante a mesma fonte, a mesma altura e as mesmas cores em todas as
  telas. Gráfico feito "cada um do seu jeito" é o que faz um painel parecer
  amador.
- **Testabilidade.** Cada função recebe um DataFrame e devolve uma figura.
  Não lê banco, não chama Streamlit.

---

## `paginas/` — as telas

Um arquivo por tela. Cada um é um script comum, lido de cima para baixo: cada
comando `st.alguma_coisa()` desenha um pedaço, na ordem em que aparece no
código.

Uma página **não faz conta**. Ela chama uma função de `financas/calculos/`,
recebe o número pronto e manda desenhar. Se você abrir `paginas/dashboard.py`
vai ver quase só chamadas — é assim de propósito.

O menu da esquerda é montado em `app.py`, com `st.navigation`.

---

## `migracao/` — os scripts de mudança

Foram usados uma vez, para trazer os dados da planilha. Ficam guardados porque
documentam **exatamente** o que foi trazido e como foi convertido.

| Arquivo | Trabalho |
|---|---|
| `extrair_xlsm.py` | lê o `.xlsm` e gera CSVs legíveis em `migracao/semente/` |
| `carregar.py` | lê esses CSVs e grava no banco, aplicando a conversão de sinal |
| `conferir.py` | compara o banco novo com a planilha, mês a mês |

### Por que em duas etapas em vez de uma

1. Os CSVs intermediários são **legíveis**. Se um número sair errado no app,
   você abre o CSV e vê na hora se o erro veio da planilha ou do
   carregamento.
2. Dá para refazer a carga sem reabrir a planilha, que é a parte lenta.
3. Os CSVs viram um **registro histórico** do que a planilha tinha no dia da
   migração.

---

## `verificacao/` — o que prova que a conta está certa

Aqui moram os scripts que **conferem** o projeto sozinhos:

| Arquivo | O que prova |
|---|---|
| `conferir_rebalanceamento.py` | a divisão do aporte está matematicamente certa |
| `conferir_competencia.py` | a fatura conta no mês do gasto, e a chave de parcelamento acompanha |
| `conferir_previsao.py` | o previsto é sempre *o que falta*, e nada conta duas vezes |
| `conferir_imposto.py` | o bem vai pelo custo de aquisição, não pelo valor de mercado |
| `conferir_indices.py` | CDI e IPCA batem com a série do Banco Central |
| `conferir_cambio.py` | a conversão usa o PTAX do fim do mês, e é reproduzível |
| `conferir_documentacao.py` | nenhuma função pública ficou sem explicação |
| `conferir_fechamento.py` | o dinheiro não some entre a corretora e a conta |

Dois arquivos ali não conferem nada — são a infraestrutura dos que conferem:

| Arquivo | O que é |
|---|---|
| `base.py` | o placar (`Conferencia`) e o **banco descartável**, um só para todos |
| `conferir_tudo.py` | roda a suíte inteira e devolve um placar único |

```bash
.venv\Scripts\python -m verificacao.conferir_tudo
```

`base.py` nasceu de uma varredura em 2026-09-04: o placar existia em **15
cópias** (sob dois nomes) e o banco descartável em **10**. Não era estilo, era
divergência — e a peça duplicada era justamente a que impede um teste de
escrever no banco de verdade. Dez implementações de uma proteção são dez
chances de uma estar errada, e a errada só aparece no dia em que apagar dado
que não volta.


### Por que uma pasta separada de `migracao/conferir.py`

As duas conferem coisas, mas são conferências de naturezas diferentes:

| | `migracao/conferir.py` | `verificacao/` |
|---|---|---|
| Compara com | a planilha antiga | a própria definição do cálculo |
| Vale até quando | o Excel for esquecido | sempre |
| Se falhar, o erro está | na importação | na fórmula |

`migracao/conferir.py` é uma ponte com o passado. `verificacao/` é uma rede de
segurança para o futuro: ele continua fazendo sentido daqui a cinco anos,
quando ninguém mais lembrar que existiu um `.xlsm`.

### A ideia por trás do teste

O script **reescreve a fórmula de outro jeito** e compara os dois resultados.
Isso parece bobo — por que escrever a mesma conta duas vezes? — mas é o ponto:
se ele chamasse a função de produção para descobrir o resultado esperado,
concordaria com qualquer erro que ela tivesse.

E ele não testa só a sua carteira. Sorteia centenas de carteiras aleatórias,
incluindo os casos esquisitos (carteira vazia, uma classe só, meta zerada). Um
teste que só usa o seu caso real prova pouco, porque os bugs de arredondamento
aparecem justamente nas combinações que ninguém pensaria em testar à mão.

```bash
.venv\Scripts\python -m verificacao.conferir_rebalanceamento
```

### O segundo: conferir a própria documentação

`conferir_documentacao.py` usa o módulo `ast` — **o próprio Python lendo
Python**. Ele devolve a mesma árvore que o interpretador usa para executar o
arquivo, então dá para perguntar "quais são as funções aqui?" sem chutar:

```python
arvore = ast.parse(codigo)
for no in arvore.body:
    if isinstance(no, ast.FunctionDef):
        no.name                  # o nome
        ast.get_docstring(no)    # a explicação, ou None
```

Um `grep "def "` faria quase a mesma coisa e erraria em três lugares: a palavra
`def` dentro de um comentário, dentro de uma string, e a função aninhada dentro
de outra. Usar `arvore.body` (em vez de `ast.walk`) pega **só** as funções de
topo — as que outro arquivo pode chamar. Função aninhada é detalhe interno.

Ele mede duas coisas com pesos bem diferentes:

- **funções sem docstring** — meta é zero, e o script sai com erro se não for;
- **funções não citadas em `docs/`** — informativo, e alto de propósito. Os
  guias explicam conceitos, não são manual de referência.

### O que ele NÃO mede — e é o buraco que importa

Ele confere se a docstring **existe**. Nunca se ela é **verdadeira**.

Isso não é um detalhe teórico. Em 25/08/2026, uma revisão linha a linha achou
**treze** lugares em que o texto dizia o oposto do código — entre eles
`docs/03` afirmando o contrário de `docs/02` sobre a mesma regra, e
`leitores/fatura_csv.py` se contradizendo dentro do próprio arquivo, com 90
linhas de distância. Todos passavam neste script com nota máxima, porque todos
tinham docstring.

A causa foi sempre a mesma: **uma regra de negócio mudou e o texto ficou.**

Nenhum script resolve isso sozinho — julgar se uma frase em português descreve
um cálculo é trabalho de quem lê. O que dá para fazer é reduzir a chance:
quando mudar uma regra, procure onde mais ela está escrita antes de fechar a
alteração. A receita está em
[09_receitas_de_alteracao.md](09_receitas_de_alteracao.md).

> Uma métrica que dá sensação de segurança sem cobrir o risco de verdade é
> pior que nenhuma métrica, porque desliga a desconfiança.

```bash
.venv\Scripts\python -m verificacao.conferir_documentacao
```

---

## `analises/` — perguntas que não merecem uma tela

Relatório de terminal: roda, imprime, acabou. **A pasta está vazia hoje, e
isso é um estado normal** — um relatório daqui nasce para responder uma
pergunta e sai quando ela foi respondida. O primeiro morador saiu em
2026-08-29, e continua no histórico do git se a pergunta voltar.

### Por que não virou uma página

Nem toda pergunta merece uma tela. Uma tela custa: entra no menu, precisa de
layout, precisa continuar funcionando quando o resto mudar. Vale a pena quando
a pergunta é **recorrente**.

Uma pergunta pontual — algo que você quer saber de vez em quando, não todo
dia — se responde com um script de terminal: custa dez minutos para escrever e
nenhuma manutenção. E se um dia virar rotina, ele já nasce pronto para virar
página, **desde que separe `levantar()`, que devolve os dados, de
`imprimir()`, que só mostra**. Aí basta chamar a primeira de dentro de uma
página e ignorar a segunda.

Essa separação — **calcular numa função, mostrar noutra** — é a mesma regra de
`financas/` × `ui/`, aplicada num arquivo só.

```bash
.venv\Scripts\python -m analises.nome_do_relatorio
```

---

## A ordem em que os arquivos se chamam

Para não ficar dúvida de quem depende de quem:

```
app.py
  └─ ui/estado.py ─── financas/banco.py ─── financas/config.py
  └─ ui/tema.py
  └─ paginas/qualquer_uma.py
       ├─ ui/componentes.py ─── ui/tema.py
       ├─ ui/graficos.py ────── financas/config.py
       ├─ ui/estado.py
       └─ financas/calculos/… ─ financas/dados.py ─ financas/banco.py
                              └ financas/formato.py
```

Repare que as setas **nunca sobem**: `financas/` nunca chama `ui/`, e `ui/`
nunca chama `paginas/`. Essa direção única é o que impede o projeto de virar
um nó.

---

## Uma pergunta útil quando for mexer

> "Isto é uma **conta** ou é uma **aparência**?"

- Conta → vai em `financas/`
- Aparência → vai em `ui/` ou na página

Se a resposta for "os dois", provavelmente são duas coisas que deveriam estar
separadas.
