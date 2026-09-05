# 18 · Publicar sem publicar sua vida

> Como compartilhar o app com outra pessoa sem que ela veja um centavo do que
> é seu — e por que isso **não** passa por reescrever o histórico do git.

Arquivo: [`publicar.py`](../publicar.py). Rode assim:

```
.venv\Scripts\python publicar.py
```

## O problema, medido

O repositório é privado e sempre foi. Ele guarda, de propósito, coisas que
num repositório público seriam um desastre:

| o que | quanto |
|---|---|
| extratos e faturas em `arquivos_originais/` e `migracao/semente/` | **81 arquivos, 1,9 MB** |
| valores em reais na documentação | **387**, sendo **294 só no CHANGELOG** |
| nomes de pessoas em código e docs | 63 ocorrências |
| caminhos com o seu nome de usuário | 14 arquivos |

Nada disso é acidente: num repositório privado esses arquivos são o histórico
do projeto, e é onde eles devem estar.

## A decisão que evita a parte perigosa

O caminho "óbvio" seria reescrever o histórico com `git filter-repo`, apagando
os arquivos pessoais de todos os commits passados. Funciona, e cobra caro:

- **muda o hash de todo commit** — o repositório vira outro;
- exige `push --force`;
- qualquer clone antigo passa a divergir sem avisar;
- se algo der errado no meio, o que se perde é o histórico inteiro.

`publicar.py` não faz nada disso. Ele escreve uma pasta **nova**, que nasce
limpa porque nunca teve nada dentro:

    repositório privado    tudo, para sempre, como está hoje
    pasta publicada        só o código, sem passado nenhum

Você dá `git init` na pasta gerada e publica **ela**. As duas vidas seguem
separadas, e nenhuma operação irreversível acontece no que já existe.

**O que isso não resolve, dito sem rodeio:** se o repositório privado já foi
público em algum momento, ou se alguém já o clonou, os arquivos continuam onde
estiveram. Nada aqui alcança uma cópia que já saiu da sua máquina. Este script
cuida do que vai para frente.

## As cinco camadas

**1. Exclusão por extensão, não por nome.** `.csv`, `.xlsx`, `.ofx`, `.db`,
`.pdf`, `.zip` nunca entram. Nome muda; extensão de planilha continua sendo
planilha. Um arquivo novo que aparecer amanhã já nasce fora, sem ninguém
lembrar de atualizar nada.

**2. Caminhos da máquina reescritos.** `CAMINHO\PARA\Phil\finance_app`
vira `CAMINHO\PARA\finance_app` — na cópia. Os seus arquivos continuam com o
caminho que de fato funciona aí, que é o motivo de ele estar escrito assim. A
troca preserva o fim do caminho, que é a parte útil:
`.../OneDrive/Backup/x.zip` vira `CAMINHO/PARA/Backup/x.zip`.

**3. Nomes trocados por um arquivo de fora.** `nomes.txt`, uma linha `de=para`
por nome, ignorado pelo git:

```
Fulano=Ana
Beltrano=Bruno
```

Ele fica **fora do código** de propósito: uma lista de "nomes que não podem
aparecer" é, ela própria, uma lista de nomes. Sem o arquivo o script avisa e
segue — ele não tem como adivinhar quais nomes são seus.

A troca cobre as três formas em que um nome aparece: `FULANO` copiado de um
extrato para dentro de uma docstring, `Fulano` no texto corrido e `fulano` em
nome de coisa. Trocar só a forma exata deixaria as outras duas passarem, que é
o jeito mais comum de um scrub falhar.

**4. O CHANGELOG fica de fora.** Ele concentra **294 dos 387 valores em reais**
— 76% da exposição numérica em um arquivo só. É um diário de decisões suas
sobre dinheiro seu, e é justamente o que menos serve a quem clona: ninguém
precisa saber por que você rateou a PLR de agosto para entender como o app
funciona. `--com-changelog` inclui, se você quiser.

Os outros 93 valores estão na documentação técnica, e ali eles **pagam o que
custam**: *"o Trend DI recebeu R$ ···· e devolveu R$ ···· em 29 meses"*
é o que prova que dividir saldo por aporte não mede rentabilidade. Sem o
número, vira opinião. Se preferir abrir mão disso, `--sem-numeros` troca todos
por `R$ ····` — é uma troca, não uma melhoria.

**5. Uma conferência depois, não confiança na lista.** `conferir()` varre a
cópia pronta procurando arquivo de dado, pasta excluída, caminho de máquina e
nome da lista. A lista de exclusão é uma **intenção**; a varredura é uma
**medição**. Se as duas discordam, a cópia é reprovada em vez de publicada.

> Ela chegou a acusar a si mesma: o prefixo de caminho de usuário do Windows
> que ela procurava estava escrito, por extenso, no próprio código-fonte dela.
> O padrão agora é montado em tempo de execução, e `publicar.py` continua
> sendo verificado como qualquer outro arquivo. Esta mesma frase, se citasse o
> prefixo literalmente, cairia na mesma armadilha — por isso ele não aparece
> aqui.

## O banco de demonstração

Gerado do zero, com dois anos de lançamentos inventados: salário fixo, moradia
estável, alimentação e lazer oscilando, décimo terceiro em dezembro, aporte
mensal, quatro papéis de renda fixa e variável.

**Ele não é aleatório puro de propósito.** Dado de demonstração sem forma
nenhuma deixa todos os gráficos parecendo ruído, e quem abrir não entende o que
a tela quer mostrar. A semente é fixa, então a demonstração é sempre a mesma.

**Ele usa as migrações de verdade**, não um schema escrito à parte. Se as duas
coisas fossem separadas, a demonstração envelheceria em silêncio: uma tabela
nova entraria no app e o banco de exemplo continuaria sem ela — e o erro só
apareceria para quem clonasse o projeto.

O que ele **não** traz é série de CDI nem cotação. A tela então diz *"sem série
do CDI"* e *"sem cotação guardada"*, que é o comportamento certo: um clique em
**Atualizar dados de fora**, na barra lateral, busca o dado real. Semear CDI
inventado seria mostrar taxa falsa com cara de medição.

## Dinheiro de terceiros deixou de ter nome no código

`config.CATEGORIA_TERCEIROS` era uma constante com o nome de uma pessoa. Virou
`config.categoria_terceiros()`, que lê o parâmetro `categoria_terceiros` do
banco, editável em **Configurações → Dinheiro que não é seu**.

Dois motivos: nome de pessoa em constante vaza para todo mundo que ler o
repositório, e não é algo que quem clonar vai querer herdar — o terceiro dele é
outro, ou não existe. O que a categoria faz continua em [docs/14](14_imposto_de_renda.md).

## Manter a cópia atualizada

Rode de novo. Ele reescreve a pasta de destino do zero e você faz um commit
novo no repositório público. A pasta é descartável de propósito: nada nela é
editado à mão, então nada nela se perde ao ser regerado.
