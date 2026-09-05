# 15 · O olhinho: esconder os valores

> **Um clique esconde todos os valores em R$. Outro traz de volta.**
> O botão fica na barra lateral, embaixo do período dos gráficos.

---

## O que isto é — e o que isto não é

**Não é segurança.** Não há senha, não há login, e não deve haver.

O banco é o arquivo `dados/financas.db`, e qualquer pessoa com acesso a este
computador o abre com um programa gratuito, em trinta segundos. Uma senha na
tela do Streamlit não protegeria nada disso — protegeria *a tela*, enquanto o
dado fica ali do lado, aberto. Uma proteção que parece existir e não existe é
pior que nenhuma, porque muda o seu comportamento sem mudar o seu risco.

**É uma cortina contra o ombro.** Alguém sentou ao seu lado. Você vai
compartilhar a tela numa reunião. O tablet ficou aberto na mesa da cozinha.
Esse é o problema — e é exatamente esse que o olhinho resolve.

### Por que não senha

| | senha | olhinho |
|---|---|---|
| protege o arquivo? | **não** | não |
| protege contra quem está do seu lado? | sim | sim |
| custa alguma coisa? | digitar a cada recarga da página | um clique |
| promete o que não cumpre? | **sim** | não |

Se um dia o objetivo passar a ser proteger o *arquivo*, a resposta não é
senha na tela: é criptografia de disco (BitLocker) ou um SQLite cifrado. São
outras conversas, e nenhuma delas começa por um campo de senha no Streamlit.

---

## Por aparelho, e não por conta

A escolha mora em `st.session_state`, que no Streamlit vale **por sessão** —
na prática, por aba de navegador.

Como o app aceita conexões da sua rede local, o celular e o computador são
sessões diferentes. Dá para deixar **o celular escondido e o computador
mostrando**, ao mesmo tempo. Guardar a escolha no banco faria o contrário, e
seria pior: esconder no celular apagaria os números da sua própria tela.

Pelo mesmo motivo, **a escolha se perde quando você recarrega a página ou
reinicia o app**.

---

## O app abre escondido — e a primeira versão abria mostrando

O padrão é **oculto**. Você clica em **👁 Mostrar valores** quando quiser ver.

A primeira versão fazia o contrário, com um argumento que parecia bom: *um
painel que abre escondido faz você clicar toda vez*. É verdade, e não importa.

O primeiro desenho da tela é **justamente o único que você não controla**. Se
ele mostrar os valores, o painel já vazou antes de você poder reagir — e o
momento em que isso acontece é exatamente o que o recurso existe para cobrir:
você abrindo o app na frente de alguém. **Um recurso de privacidade falha
fechado.**

O custo é honesto e está aí: um clique por abertura. Foi por isso que o botão
subiu para o topo da barra lateral, logo abaixo do menu, e ganha destaque
(botão primário) enquanto os valores estão ocultos — botão que se usa sempre
não mora no rodapé.

A constante é `privacidade.COMECA_OCULTO`, e ela tem teste próprio em
`conferir_privacidade.py`. Não por capricho: trocá-la para `False` numa
refatoração distraída **não quebra nada visível** — o app só volta a abrir
mostrando tudo, e ninguém percebe até acontecer na frente de alguém.

---

## O que fica escondido

| | |
|---|---|
| valores em R$ | cartões, textos, avisos, tabelas |
| gráficos | rótulo do eixo de valor, texto sobre as barras, tooltip do mouse, e o total escrito no meio da rosca |

## O que continua visível, e por quê

| | por quê |
|---|---|
| percentuais | "38% em renda fixa" não revela quanto você tem — e sem eles o gráfico de alocação vira enfeite |
| quantidades | "18 papéis", "3.811 lançamentos" — contagem não é valor |
| datas, categorias, nomes | é o que permite continuar navegando com o olhinho ligado |
| a **tabela de exemplo da tela de Regras** | ali o número *é* a lição: mascarar "um depósito de R$ ···· atinge o limite de R$ ····" tornaria a explicação ilegível |

A máscara é **`R$ ••••`**, e não um espaço em branco. Célula vazia parece
defeito; a máscara diz "tem um valor aqui, e você escolheu não ver".

---

## A regra que não pode ser quebrada

> **Um recurso de VER nunca pode mudar o que está gravado.**

O ponto delicado são as tabelas editáveis. O `st.data_editor` do Streamlit
devolve **o que está na tela** — e o que está na tela é `R$ ••••`. Se esse
texto seguisse para o código que salva, a próxima gravação escreveria a
máscara onde havia dinheiro.

Por isso `privacidade.editor()` faz três coisas:

1. mascara as colunas em R$ e **trava só elas** — as outras continuam
   editáveis, então dá para corrigir a categoria de um lançamento sem que o
   valor apareça;
2. antes de devolver, **repõe os números de origem**, casados pelo índice;
3. linha nova (nos editores que aceitam) fica sem valor — o mesmo que
   aconteceria se você criasse a linha com o campo em branco.

`verificacao/conferir_privacidade.py` confere isso explicitamente.

---

## Como usar numa tela nova

```python
from ui import privacidade as priv

priv.fmt_brl(1234.5)              # no lugar de formato.fmt_brl
priv.fmt_brl_md(1234.5)           # dentro de st.caption / st.markdown
priv.tabela(df, ...)              # no lugar de st.dataframe
priv.editor(df, ...)              # no lugar de st.data_editor
priv.grafico(fig, ...)            # no lugar de st.plotly_chart
priv.texto(frase_com_dinheiro)    # frase já formatada por financas/
```

**Nenhuma tela chama `st.dataframe`, `st.data_editor` ou `st.plotly_chart`
direto.** Isso é conferido — o teste 7 de `conferir_privacidade.py` varre
`paginas/` e falha se alguém voltar a chamar.

### A convenção virou contrato

`priv.tabela` e `priv.editor` **descobrem sozinhos** quais colunas mostram
dinheiro: eles leem o `column_config` e procuram `format="R$ %.2f"`.

Foi assim, e não com uma lista de nomes por tela, porque são mais de 50
tabelas no app — uma lista envelheceria na primeira coluna nova, em silêncio,
mostrando um valor que devia estar escondido.

O preço é um contrato: **coluna de dinheiro se declara com
`componentes.config_moeda()` ou com `format="R$ %.2f"`.** Declarada de outro
jeito, ela não será escondida.

---

## O que o `financas/` não pode fazer

Nada em `financas/` importa Streamlit — [a regra mais importante do
projeto](01_organizacao_do_projeto.md). Então nenhum cálculo consegue
consultar o olhinho, e não deve.

Duas funções de lá devolvem **frase**, e não número: `previsao.rotulo()` e
`planejamento.alertas_da_projecao()`. Elas formatam o dinheiro por dentro. A
máscara nesses dois casos é aplicada na saída, pela tela, com `priv.texto()`.

---

## Um defeito que o conferidor pegou

A primeira versão descobria o eixo de valor de um gráfico perguntando ao
`tickprefix` do eixo Y: `graficos._estilo()` põe `"R$ "` ali, e os gráficos
deitados (barra horizontal) zeram esse prefixo — logo, Y sem prefixo
significaria valor no X.

**Estava errado, e do jeito pior.** Os gráficos deitados zeram o prefixo
*antes* de chamar `_estilo()`, que roda depois e o repõe. Todos chegavam com
`"R$ "`. Nos gráficos deitados o código escondia o eixo das **categorias** —
deixando os valores na tela e o gráfico ilegível, os dois defeitos de uma vez.

A versão certa pergunta aos **dados**: quem tem `orientation="h"` é barra
deitada, e ali o valor está no X.
