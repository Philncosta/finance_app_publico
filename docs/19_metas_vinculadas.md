# 19 · Meta vinculada ao patrimônio investido

> Uma meta como "chegar a R$ ···· investido" não pode depender de você
> lembrar de atualizar um número. Ela tem de se atualizar sozinha.

Arquivos: [`financas/calculos/metas.py`](../financas/calculos/metas.py),
[`paginas/metas_compras.py`](../paginas/metas_compras.py),
[`ui/graficos.py`](../ui/graficos.py) (`aporte_do_mes_vs_meta`).
Prova: [`verificacao/conferir_metas.py`](../verificacao/conferir_metas.py).

## O problema com "Já acumulado" digitado

Toda meta tem um campo `ja_acumulado`, digitado à mão. Funciona bem para uma
entrada de imóvel ou uma reserva — dinheiro parado numa conta, que só muda
quando você decide.

Mas uma meta de patrimônio investido muda **todo mês**, com aporte e com
oscilação de mercado. Depender de lembrar de atualizar o número é como o
`aporte_definido` fixo de uma planilha: funciona até você esquecer, e você vai
esquecer.

## `vinculo = "patrimonio_investido"`

Uma meta pode ter essa flag (migração 18, `ALTER TABLE metas ADD COLUMN
vinculo TEXT`). Quando tem, `metas.calcular()` **ignora** o `ja_acumulado`
digitado e usa o patrimônio investido de verdade —
`estado.carteira_conciliacao(mes)["carteira_cadastrada"]`, o mesmo número que
o Dashboard mostra em "Investido". Nenhum número novo: é a fonte que já existe
reaproveitada.

A substituição acontece dentro de `calcular()` e se propaga para tudo que
depende dela — `falta`, `pct_concluido`, `situacao`, e a soma em `resumo()`.
Isso importa: trocar só o `ja_acumulado` mostrado e esquecer de propagar para
o resto deixaria "Já tem" dizendo uma coisa e "Falta" dizendo outra que não
fecha com ele.

Na tela, a coluna **"Ligar ao patrimônio?"** no cadastro é um checkbox — ele
não edita a coluna `vinculo` diretamente (que é texto livre no banco), para
não abrir espaço para um valor digitado errado.

## Sem prazo é uma resposta válida

A meta de R$ ···· não tem uma data-alvo — é um hábito, não um projeto com
fim. `prazo = NULL` já era suportado (`situacao = "sem prazo"`), mas expôs um
bug real: **misturar uma meta sem prazo com uma meta com prazo na mesma
tabela fazia a tela quebrar** com `ValueError: cannot convert float NaN to
integer`.

A causa: `pd.DataFrame(linhas)` decide o tipo de cada coluna olhando **todas**
as linhas de uma vez. Uma meta sem prazo (`meses_restantes = None`) ao lado de
uma com prazo (um inteiro) promove a coluna inteira para `float64` — e o
`None` vira `NaN`, não continua `None`. A tela checava `is not None`, e
`float('nan') is not None` é `True`. Trocado por `vazio()` (de
`financas/formato.py`, que trata `None` e `NaN` como a mesma coisa — a própria
razão dela existir).

## Um segundo bug, mais sério: "nan" virando dado gravado

Ao salvar a meta sem prazo pelo editor, o `prazo` foi parar no banco como a
**string literal `"nan"`**, não `NULL`. A causa é irmã da primeira:

```python
str(linha.get("prazo") or "").strip() or None
```

Uma célula vazia chega como `NaN` do pandas. `NaN or ""` devolve `NaN` — não
`""` — porque `bool(NaN)` é `True`. `str(NaN)` é a string `"nan"`, que
sobrevive ao `.strip()` e ao `or None` seguinte, porque `"nan"` é uma string
não vazia.

`vazio()` já sabe detectar isso — ela reconhece a própria string `"nan"` como
vazia, e é por isso que a **leitura** nunca quebrou (o `metas.calcular()`
tratava "nan" como prazo ausente sem problema). O problema era só a
**escrita**: o padrão certo, usado agora em todo o arquivo, é

```python
def _texto_ou_none(valor) -> str | None:
    return None if vazio(valor) else str(valor).strip() or None
```

Auditei o banco real por esse padrão (`prazo LIKE 'nan'` e equivalentes) —
nenhum dado seu anterior foi afetado, só a meta de teste criada nesta sessão,
já corrigida.

**O mesmo padrão `str(x or "").strip()` aparece em outros 18 pontos, em 5
arquivos** (`configuracoes.py`, `gastos_fixos.py`, `investimentos.py`,
`regras.py`) que não foram tocados aqui — ficou como tarefa separada, sinalizada
para revisão futura, porque corrigir 5 páginas não relacionadas estava fora do
escopo desta mudança.

## Por que não há juros na projeção

`meses_no_ritmo = falta / aporte` é uma **soma**, nunca um valor futuro
composto. R$ ····/mês por 24 meses aqui dá exatamente R$ ···· — nunca mais.

Isso é deliberado: o objetivo desta conta é responder *"quanto da minha
própria receita/despesa eu vou guardar"*, não simular retorno de investimento
— isso já existe, separado, na comparação com índices da tela de
Investimentos ([docs/11](11_investimentos.md)). Somar as duas coisas aqui
inflaria a meta com uma expectativa de mercado que pode não se realizar.

## "Aportou o que prometeu?"

Um gráfico novo, que só aparece quando existe pelo menos uma meta vinculada:
barras do que **de fato** saiu para a carteira em cada mês
(`investimentos.movimentacoes()`, a mesma extração que a comparação com
índices usa), verdes quando bateu a meta mensal e cinzas quando não, com uma
linha tracejada na meta atual.

**A linha é única para todos os meses, de propósito.** O app não guarda
histórico de quando `aporte_definido` mudou de valor — só o valor atual.
Desenhar a linha atual sobre meses antigos é uma simplificação honesta: ela
mostra "como este mês se compara ao que você quer *agora*", não uma
reconstrução fictícia do que valia em cada mês passado.

Isso também é onde os aportes irregulares (a PLR, por exemplo) aparecem
automaticamente — eles entram nos mesmos lançamentos de categoria
`Investimentos` que alimentam esse gráfico e o `ja_acumulado` vinculado, sem
precisar de nenhuma lógica separada para "aporte extra".
