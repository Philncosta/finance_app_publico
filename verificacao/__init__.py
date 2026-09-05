"""
verificacao — scripts que conferem se as contas do app estao certas.
==============================================================================

Diferente de `migracao/`, que foi um trabalho de uma vez so (trazer a planilha
para o banco), estes scripts sao para rodar SEMPRE que voce mexer nos calculos.

Rode assim, da pasta do projeto:

    .venv\\Scripts\\python -m verificacao.conferir_rebalanceamento

Cada script imprime um relatorio e termina com codigo 0 (tudo certo) ou 1
(alguma conta nao fecha). Para a foto inteira, com um placar so:

    .venv\\Scripts\\python -m verificacao.conferir_tudo

O andaime que todos usam — o placar `Conferencia` e o banco descartavel — mora
em `base.py`. Conferencia nova comeca importando de la, e nao copiando de um
vizinho: foi a copia que gerou 15 versoes do placar e 10 do banco descartavel,
com divergencias reais entre elas.
"""
