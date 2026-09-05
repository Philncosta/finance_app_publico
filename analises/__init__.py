"""
analises — relatorios que respondem uma pergunta especifica.
==============================================================================

Diferente de `verificacao/`, que confere se as contas estao certas, aqui o
objetivo e ENTENDER alguma coisa. Um script por pergunta.

Rode da pasta do projeto:

    .venv\\Scripts\\python -m analises.nome_do_relatorio

Sao relatorios de terminal de proposito: nem toda pergunta merece uma tela no
painel, e uma tela a mais e uma tela a mais para manter.

A PASTA ESTA VAZIA, E ISSO E UM ESTADO NORMAL
---------------------------------------------
Um relatorio daqui nasce para responder uma pergunta e morre quando ela foi
respondida — nao ha divida tecnica em apagar. O ultimo morador saiu em
2026-08-29, depois de cumprir o que existia para fazer; ele continua no
historico do git, no commit `61e98e8`, se um dia a pergunta voltar.

O QUE FICA DELE, E VALE PARA O PROXIMO
--------------------------------------
**Calcular numa funcao, mostrar noutra.** Ele separava `levantar()`, que
devolvia os dados, de `imprimir()`, que so mostrava. E a mesma regra de
`financas/` x `ui/` aplicada dentro de um arquivo so — e e ela que permite um
relatorio de terminal virar pagina no dia em que a pergunta ficar recorrente,
sem reescrever a conta.

**E o recorte por FATO, nao por decisao.** Ele reconstruia uma conta inteira
recortando por `portador`, que e um dado gravado linha a linha, e nao por
`categoria`, que e uma classificacao e muda. Guardar o fato numa coluna e o que
deixa a classificacao livre para mudar depois.
"""
