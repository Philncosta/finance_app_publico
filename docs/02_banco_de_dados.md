# 02 · O banco de dados

Arquivo do código: [`financas/banco.py`](../financas/banco.py)

---

## O que é o SQLite

Um banco de dados que cabe num **arquivo só**: `dados/financas.db`.

Não precisa instalar servidor, não tem senha, não tem nada rodando em segundo
plano. Você copia esse arquivo e levou o banco inteiro. Foi por isso que ele
foi escolhido: você queria algo fácil de transportar e de guardar na nuvem.

O Python já vem com ele de fábrica (módulo `sqlite3`), por isso ele nem aparece
no `requirements.txt`.

---

## A decisão mais importante do projeto: o sinal do valor

**Leia esta seção com atenção.** É a diferença mais importante entre a
planilha antiga e o sistema novo, e entender isso explica metade do código.

### Como era na planilha

A coluna `Valor` era **sempre positiva**. Uma outra coluna, `Natureza`, dizia
se aquilo entrava ou saía:

| Estabelecimento | Valor | Natureza |
|---|---|---|
| OFC RJ RIO SUL | 499,50 | Despesa |
| TED da XP | R$ ···· | Receita |

Para somar o mês, você precisava de um `SUMIFS` diferente para cada natureza.

### Como é aqui

O valor **tem sinal**:

> **negativo = saiu dinheiro** &nbsp;&nbsp;·&nbsp;&nbsp; **positivo = entrou dinheiro**

| Descrição | Valor |
|---|---|
| OFC RJ RIO SUL | −499,50 |
| TED da XP | +R$ ···· |

Com isso, **"quanto sobrou no mês" é literalmente a soma da coluna**. Os
gráficos ficam diretos, os filtros ficam simples.

A coluna `natureza` continua existindo, mas agora serve para **classificar**
(isto é despesa? é investimento?), não para descobrir o sinal.

> **Se você se confundir depois, lembre:** o extrato do seu banco já funciona
> assim. `-R$ ····` saiu, `R$ ····` entrou. Nós só adotamos a mesma
> convenção em todo lugar.

### Como a conversão foi feita na migração

O código está em [`migracao/carregar.py`](../migracao/carregar.py), função
`aplicar_sinal`. A regra depende primeiro da **origem**:

**Origem = Fatura** → `-valor`

O arquivo do cartão já vem com sinal próprio, escrito do ponto de vista do
cartão. Só invertemos para o seu ponto de vista:

| No arquivo | Vira | Por quê |
|---|---|---|
| +499,50 | −499,50 | compra: saiu dinheiro seu |
| −100,24 | +100,24 | estorno: voltou dinheiro seu |
| −R$ ···· | +R$ ···· | pagamento: a dívida do cartão diminuiu |

**Outras origens** → aí sim olhamos a natureza:

| Natureza | Sinal | Por quê |
|---|---|---|
| Despesa | `-valor` | gasto tira dinheiro |
| Receita | `+abs(valor)` | salário, Pix recebido |
| Receita Extraordinária | `+abs(valor)` | PLR, indenização |
| Pagamento | `-abs(valor)` | pagar a fatura sai da conta |
| Investimento | depende do texto | ver abaixo |
| Transferência | mantém o sinal do extrato | dinheiro que só mudou de lugar |

### As três naturezas que ficam fora dos totais

`Pagamento`, `Investimento` e `Transferência` **não entram** em receita nem em
despesa. Não é esquecimento: elas não são ganho nem gasto, só movimentação. Se
contassem, o mesmo dinheiro apareceria duas vezes.

A diferença entre as duas últimas importa:

- **Investimento** alimenta a tela de Patrimônio (aportes, resgates e
  rendimentos da conta investimento).
- **Transferência** não alimenta nada. É para TED que você manda para si mesmo
  em outro banco, dinheiro enviado e devolvido, repasse que só passa pela sua
  conta.

> Essa distinção surgiu de um caso real (22/08/2026): cinco TEDs de R$ ····
> entre contas e uma devolução estavam contadas como receita e despesa,
> inflando agosto em R$ ···· de um lado e R$ ···· do outro. Marcá-las como
> `Investimento` resolveria os totais, mas estragaria o patrimônio — daí a
> natureza própria.

### Dois detalhes que valem explicação

**1. Por que Despesa usa `-valor` e não `-abs(valor)`**

Porque existem 3 linhas negativas com natureza Despesa que são **estornos**
(uma compra devolvida). Com `-valor`, o estorno vira positivo — dinheiro
voltando — que é exatamente o comportamento certo. Com `-abs()`, o estorno
viraria mais um gasto.

**2. O caso do Investimento**

A planilha guardava mal: tanto `"Transferência enviada para a conta
investimento"` quanto `"recebida da conta investimento"` ficavam **positivas**,
e só o texto da descrição distinguia. Aqui lemos o texto e damos o sinal
correto — é o que faz a tela de Patrimônio funcionar sem gambiarra.

**3. Por que o pagamento da fatura fica positivo de um lado e negativo do outro**

O mesmo evento aparece nos dois arquivos:

- na **fatura**, como crédito (`+R$ ····`) — a dívida do cartão diminuiu;
- no **extrato**, como débito (`−R$ ····`) — o dinheiro saiu da conta.

Se você importar os dois arquivos, as duas pontas **se anulam** — que é o
comportamento certo para uma transferência entre duas contas suas. E, de
qualquer forma, tudo que tem natureza `Pagamento` fica de fora dos totais de
receita e despesa, para o gasto não ser contado duas vezes.

---

## As tabelas

São 14. A principal é `lancamentos`; as outras são cadastros e configurações.

### `lancamentos` — o coração

Uma linha por evento financeiro.

| Coluna | O que guarda |
|---|---|
| `id` | número sequencial automático |
| `id_unico` | a "impressão digital" que impede importar duas vezes |
| `data` | `AAAA-MM-DD`, quando aconteceu |
| `hora` | `HH:MM:SS` — só o extrato CSV tem |
| `mes_competencia` | `AAAA-MM`, em que mês isso *conta* |
| `descricao` | estabelecimento ou histórico do banco |
| `portador` | quem usou o cartão (só fatura) |
| `valor` | **com sinal** |
| `categoria`, `tipo`, `natureza`, `origem` | a classificação |
| `conta_id` | de qual conta/cartão veio |
| `parcela_atual`, `parcela_total` | 3 de 10 |
| `chave_parcelamento` | junta as parcelas da mesma compra |
| `fitid` | o id único que o OFX traz |
| `saldo_apos` | saldo da conta depois (só extrato) |
| `regra_aplicada` | qual regra classificou — para auditar depois |
| `criado_em`, `atualizado_em` | carimbos de tempo |

#### `data` × `mes_competencia`

São diferentes de propósito, e é a distinção mais sutil da tabela:

- **`data`** é quando a compra aconteceu.
- **`mes_competencia`** é em que mês ela *pesa no seu bolso*.

Numa compra à vista no débito, os dois são iguais. Numa compra parcelada no
cartão, não: uma parcela `3 de 10` de uma compra feita em outubro cai numa
fatura posterior. A `data` é outubro; o `mes_competencia` é o mês daquela
parcela.

Todos os totais do painel usam `mes_competencia`.

##### E para a fatura, competência é o mês em que se GASTOU

Não o mês em que ela vence. Esta é a decisão mais consequente da tabela, e ela
mudou em 25/08/2026 (migração 13).

O nome do arquivo da fatura traz a data de **vencimento** — `Fatura2026-09-05`.
Mas essa fatura contém o que foi gasto de **30/07 a 21/08**: o cartão fecha por
volta do dia 25. Contar no vencimento jogava o gasto de agosto dentro de
setembro.

**Por que isso importa mais do que parece:** o salário dele cai entre os dias
22 e 25, todo mês. O dinheiro que entra 25/08 é o mesmo que paga a fatura de
05/09. Separar os dois em meses diferentes fazia setembro/2026 aparecer com
**−R$ ····** — a fatura inteira, e nenhuma receita.

    arquivo Fatura2026-09-05  ->  competência 2026-08

A tradução mora em `leitores/fatura_csv.competencia_da_fatura()`, separada de
`mes_do_nome_arquivo()` de propósito: aquela é um **parser** ("o que está
escrito no nome"), esta é a **regra** ("em que mês isso conta").

**A tentação seguinte, e por que ela é errada.** Parece natural que a projeção
de caixa desloque a parcela +1 mês, "porque a fatura vence dia 05". Não. O
salário de setembro (25/09) e o gasto de setembro (26/08 a 25/09) já estão no
mesmo balde; o pagamento acontece dias depois, com dinheiro que já entrou.
Deslocar separaria a fatura do salário que a paga. O dia do pagamento aparece
na tela **Cartão e parcelas**, como informação — não como mudança de balde.

#### `chave_parcelamento`

O problema: uma compra parcelada aparece uma vez por mês, em meses diferentes,
com o mesmo estabelecimento. Como saber que a "3 de 10" de março e a "4 de 10"
de abril são **a mesma compra**?

A solução (a mesma que a planilha usava) é calcular de volta o **mês da
primeira parcela** e usar ele na chave:

```
indice_origem = indice_do_mes_atual - (parcela_atual - 1)
chave = ESTABELECIMENTO | total_de_parcelas | indice_origem
```

A "3 de 10" de 2026-03 e a "4 de 10" de 2026-04 dão o mesmo `indice_origem`
(2026-01), então caem na mesma chave. Compras à vista não ganham chave, porque
não há o que agrupar.

### As outras tabelas

| Tabela | Guarda |
|---|---|
| `contas` | conta corrente, cartão de crédito |
| `grandes_categorias` | Casa, Comida, Moto… com a cor de cada uma |
| `categorias` | Alimentação, Combustível… ligadas a uma grande categoria |
| `regras_fatura` | palavra-chave → categoria |
| `regras_extrato` | palavra-chave + valor mínimo + sentido → categoria |
| `gastos_fixos` | o cadastro de aluguel, assinatura, mensalidade (ver abaixo) |
| `orcamento` | a meta de gasto por mês e grande categoria |
| `metas` | objetivos de poupança |
| `futuras_compras` | lista de desejos |
| `patrimonio_mensal` | saldo em conta e aplicado que você informou |
| `investimentos` | o cadastro da carteira (CDB, Tesouro, fundo…) |
| `investimentos_saldos` | quanto cada aplicação valia no fim de cada mês |
| `financiamento_cenarios` | as premissas do simulador |
| `parametros` | configurações soltas (chave → valor) |
| `arquivos_importados` | histórico de importações |
| `macros_ativo` | Renda Fixa, Renda Variável, Internacional, Caixa |
| `classes_ativo` | NTN-B, Tesouro Selic, ETF… com as palavras-chave |
| `metas_alocacao` | quanto você quer ter em cada macro/classe |
| `investimentos_movimentos` | o extrato da conta da corretora |

---

## As quatro colunas que dizem como um gasto fixo entra na previsão

Migração 19. Cadastrar um gasto fixo não basta: o app precisa saber **por onde
ele chega**, senão soma a mesma despesa duas vezes.

| Coluna | Valores | Para que serve |
|---|---|---|
| `forma_pagamento` | `Cartão` \| `Conta` | `Conta` = boleto, Pix, débito. Separa o que cai na fatura do que sai direto da conta |
| `considerar_previsao` | 0 \| 1 | o interruptor: tira um item da projeção sem apagá-lo |
| `base_valor` | `Cadastrado` \| `Média 6m` | de onde sai o valor esperado — o que você digitou, ou a média das últimas cobranças |
| `categoria_historico` | texto \| `NULL` | restringe o casamento com o histórico a uma categoria. `NULL` = qualquer uma |

Os defaults são todos conservadores, e o motivo de cada um está em
`_migracao_19_forma_de_pagamento_do_fixo`. O de `forma_pagamento` foi
**adivinhado a partir do histórico**, não chutado: para cada item, a migração
casou a `chave_historico` contra os lançamentos dos últimos 12 meses e votou
pela origem majoritária. Resultado: 12 Cartão, 3 Conta.

> **`parcelado` é legado.** Ela existe no schema, ninguém lê, e metade dos
> valores estava errada — valia 1 no curso de inglês, que é pago por Pix e não é
> parcelamento nenhum. A pergunta que ela tentava responder ("esta despesa vem
> parcelada?") agora é respondida pela máquina, mês a mês, em vez de por um
> campo que alguém precisa lembrar de manter. Ela **não foi apagada** de
> propósito: `backup.restaurar` monta o INSERT com as colunas que encontra no
> CSV, então dropar a coluna quebraria a restauração de todo `.zip` já gerado.

---

## Renomear categoria é uma operação em cascata

O **nome é a chave primária** de `categorias` e `grandes_categorias`, e sete
tabelas guardam esse nome como texto. Não há id por trás — foi uma escolha de
simplicidade, e tem este preço: trocar o nome sem mexer no resto **não
renomeia nada**, cria uma categoria nova e deixa a antiga com o histórico.

```python
banco.renomear_categoria("Manutenção", "Moto")
# -> {'lancamentos': 46, 'gastos_fixos': 2, 'regras_fatura': 8, 'regras_extrato': 8}
```

Onde o nome aparece:

| Categoria | Grande categoria |
|---|---|
| `lancamentos`, `gastos_fixos` | `categorias` |
| `regras_fatura`, `regras_extrato` | `orcamento` |
| `futuras_compras` | |

**Se o destino já existe, vira fusão**: os registros da antiga passam para a
existente e a antiga é apagada. É o que resolve o caso de ter criado duas
categorias para a mesma coisa — e foi assim que `Carla` e `Família` viraram uma
só em 23/08/2026, levando 598 lançamentos e 2 regras junto.

### O ponto cego que essa lista tinha

A cascata varre uma lista de **(tabela, coluna)**. Isso deixou um lugar de
fora, e o erro só apareceu quando a fusão acima aconteceu:

```json
"portadores_categoria" -> {"CARLA": "Carla"}
```

O mapa de portador não é uma coluna. É um **JSON de uma linha só** dentro de
`parametros`, e continuou apontando para uma categoria já apagada. Nada
reclamou; a próxima fatura importada é que teria recriado `Carla` do nada.

> **A regra a levar daqui:** uma cascata que varre colunas não enxerga um nome
> escondido dentro de um valor. Sempre que você guardar dado estruturado como
> texto — JSON, CSV numa célula, lista separada por vírgula — ele fica de fora
> de tudo que o banco faria sozinho: índice, chave estrangeira, `UPDATE` em
> massa. É um preço justo pela simplicidade, desde que você saiba onde ele
> aparece.

A correção é `_renomear_no_mapa_de_portadores()`, que recebe a conexão **já
aberta** para entrar na mesma transação. Se abrisse a sua própria, o mapa
poderia ficar atualizado com o resto revertido — pior que os dois erros
isolados.

---

## Índices: por que existem

No fim do bloco `CREATE TABLE` você vai ver linhas assim:

```sql
CREATE INDEX IF NOT EXISTS ix_lanc_mes ON lancamentos(mes_competencia);
```

Um índice é um **atalho de busca**. Sem ele, filtrar por mês faz o banco ler
as 1.073 linhas uma a uma. Com ele, o banco pula direto para as certas.

Em troca, o índice ocupa um pouco mais de espaço e deixa a escrita um tico
mais lenta. Vale muito a pena para as colunas que a gente filtra o tempo todo
— e não vale para as outras. Por isso só seis colunas têm índice.

---

## Triggers: a regra que não dá para esquecer

Um **trigger** é um pedaço de SQL que o banco executa sozinho quando algo
acontece. Existe um só neste projeto, e a história dele explica quando vale a
pena.

### O problema que ele resolve

A tabela `lancamentos` tem `criado_em` e `atualizado_em`. O segundo serve para
`migracao/conferir.py` distinguir duas coisas bem diferentes:

```sql
atualizado_em > criado_em   -- você reclassificou de propósito  (~~)
atualizado_em = criado_em   -- a linha está como veio           (!!  se diferir)
```

A tela de Lançamentos escrevia essa coluna corretamente em todo `UPDATE`. Mas
**escrever a coluna era uma convenção, não uma garantia** — dependia de cada
lugar que altera um lançamento lembrar. Em 23/08/2026, uma reclassificação
feita por script direto deixou o carimbo intacto, e a conferência acusou erro
onde não havia.

### A correção

```sql
CREATE TRIGGER tg_lancamentos_atualizado_em
AFTER UPDATE ON lancamentos FOR EACH ROW
WHEN NEW.atualizado_em IS OLD.atualizado_em
BEGIN
    UPDATE lancamentos SET atualizado_em = datetime('now','localtime')
     WHERE id = NEW.id;
END;
```

Agora **não há como esquecer**: qualquer `UPDATE`, venha de onde vier — da
tela, de um script, do terminal —, carimba a linha.

O `WHEN` existe para o trigger não se disparar em cima de si mesmo. (No SQLite
a recursão de triggers vem desligada por padrão, então seria seguro de qualquer
forma — mas explicitar a condição deixa a intenção clara para quem lê.)

### Quando usar trigger, e quando não

| Use quando | Evite quando |
|---|---|
| a regra vale para **toda** escrita, sem exceção | a regra depende de contexto (quem, por quê) |
| esquecer é silencioso e passa despercebido | você precisa ver a lógica ao ler o código Python |
| é mecânico: carimbo, contador, log | envolve decisão de negócio |

O risco do trigger é ser **invisível**: ele age sem aparecer em nenhum arquivo
`.py`, e alguém depurando pode levar um tempo até desconfiar. Por isso vale só
quando o ganho é grande — e por isso este projeto tem exatamente um.

> **O padrão maior:** quando a corretude depende de todo mundo lembrar de fazer
> a mesma coisa, ela vai falhar. Empurre a regra para onde não possa ser
> esquecida — um trigger, uma constraint, um valor padrão, ou uma função única
> por onde tudo passa. É a mesma ideia do `natureza_padrao` da categoria em
> [04 · Motor de regras](04_motor_de_regras.md): configurar **uma vez, no lugar
> certo**.

---

## Migrações: como o banco muda sem perder dados

**O problema:** daqui a um mês você vai querer uma coluna nova. Mas o banco já
vai ter dados dentro. Apagar e recriar perde tudo.

**A solução:** o SQLite guarda um número dentro do próprio arquivo, chamado
`user_version`. No `banco.py` existe uma lista `MIGRACOES`, com um bloco de SQL
por versão. Ao abrir o app, comparamos a versão gravada no arquivo com o
tamanho da lista e rodamos **só o que falta**.

### Como adicionar uma coluna nova no futuro

1. **Não mexa** nos blocos que já existem — bancos antigos já rodaram eles.
2. Acrescente um bloco **novo no fim** da lista:

```python
MIGRACOES.append("ALTER TABLE lancamentos ADD COLUMN tags TEXT;")
```

3. Pronto. Quem já tem banco recebe só a alteração; quem está começando recebe
   tudo em ordem.

### As migrações que já rodaram

| Versão | Quando | O que trouxe |
|---|---|---|
| **1** | criação | as 15 tabelas originais |
| **2** | 2026-08-22 | macro e micro categorias de gasto |
| **3** | 2026-08-22 | classes de ativo, metas de alocação e o extrato da corretora |
| **4** | 2026-08-22 | `investimentos_saldos.custo_aplicado` |

A **4** merece explicação, porque uma coluna só resolve um problema sutil. O
arquivo de posição diz quanto cada papel *vale* e quanto você *aplicou*. Sem
guardar a segunda, calcular rendimento exigiria comparar saldos de dois meses —
e aí uma **compra nova viraria "rendimento"**. Com o custo guardado:

```
aporte(mês) = custo(mês) − custo(mês anterior)
```

e a fórmula de rendimento que já existia passa a dar o número verdadeiro.
Detalhes em [12 · Carteira e rebalanceamento](12_carteira_e_rebalanceamento.md).

---

## Como o código fala com o banco

### Abrir e fechar

```python
with banco.conectar() as conn:
    conn.execute("SELECT ...")
# aqui a conexão já foi fechada automaticamente, mesmo se deu erro
```

Abrimos e fechamos **a cada operação**, de propósito. Uma conexão SQLite não
pode ser compartilhada entre threads, e o Streamlit usa várias. Abrir de novo
custa quase nada para um banco deste tamanho, e elimina uma classe inteira de
bug difícil de achar.

Três ajustes são feitos em toda conexão:

- `row_factory = sqlite3.Row` — permite acessar por nome (`linha["valor"]`) em
  vez de por posição (`linha[3]`), que é ilegível e quebra se alguém mudar a
  ordem das colunas.
- `PRAGMA foreign_keys = ON` — o SQLite só verifica as ligações entre tabelas
  se você pedir.
- `PRAGMA journal_mode = WAL` — deixa ler e escrever ao mesmo tempo sem
  travar. Evita o erro "database is locked" quando o Streamlit reexecuta.

### Os atalhos

| Função | Para quê |
|---|---|
| `banco.df(sql)` | roda um SELECT e devolve um DataFrame |
| `banco.consultar(sql)` | roda um SELECT e devolve lista de linhas |
| `banco.consultar_um(sql)` | idem, mas só a primeira linha |
| `banco.executar(sql, params)` | INSERT / UPDATE / DELETE |
| `banco.executar_muitos(sql, lista)` | o mesmo comando para várias linhas |
| `banco.contar("tabela")` | quantas linhas tem |

### A regra de segurança do SQL

Sempre passe valores em `params`, com `?` no SQL:

```python
banco.executar("DELETE FROM lancamentos WHERE id = ?", (5,))   # certo
banco.executar(f"DELETE FROM lancamentos WHERE id = {5}")      # errado
```

O jeito errado permite **SQL injection** — alguém escrever comando dentro de
um campo de texto. Com `?`, o banco trata o valor sempre como dado, nunca como
comando. Todo o projeto usa `?`.

---

## Onde ver isso funcionando

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -c "from financas import banco; print(banco.tabelas()); print(banco.contar('lancamentos'), 'lançamentos')"
```
