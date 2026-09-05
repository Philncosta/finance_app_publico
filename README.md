# Painel Financeiro

> ## Esta é a cópia pública, sem dados pessoais
>
> Gerada automaticamente por `publicar.py` a partir de um repositório privado.
> Não contém arquivos de extrato, banco de dados real, nem nome de pessoa
> nenhum — só código, documentação e um banco de **demonstração**, com dados
> inventados, para você ver o app funcionando antes de usar com os seus.
>
> Quer usar com os seus dados? Clone, rode, e importe os seus arquivos —
> tudo fica no seu computador, dentro do seu próprio banco local.

Dashboard financeiro pessoal em Streamlit, feito para substituir a planilha
`Dasbhardo excel.xlsm`. Roda no seu computador, guarda os dados num arquivo
só e não manda nada para lugar nenhum.

---

## Como abrir

**Duplo clique em `iniciar.bat`.** Só isso.

Se preferir o terminal:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\streamlit run app.py
```

O app abre em `http://localhost:8501`. Para fechar, feche a janela preta.

### Abrir do celular ou do tablet

O app aceita conexões da sua rede. Quando ele sobe, a janela preta mostra uma
linha **Network URL** com um endereço tipo `http://192.168.0.3:8501`. Digite
esse endereço no navegador do outro aparelho, estando no mesmo Wi-Fi.

### Esconder os valores

**O app abre com os valores escondidos.** No topo da barra lateral, logo
abaixo do menu, há um botão **👁 Mostrar valores** — um clique revela tudo,
outro esconde de novo. Escondido, todo valor em R$ vira `R$ ••••`: cartões,
tabelas, gráficos e tooltips.

Abrir escondido é de propósito: o primeiro desenho da tela é o único que você
não controla, e é justamente o momento em que alguém pode estar olhando.

Vale **por aparelho**: dá para deixar o celular escondido e o computador
mostrando. E **não é senha** — o banco continua sendo um arquivo local que
qualquer um abre. Serve para quem está do seu lado, não para proteger o
arquivo. Ver [docs/15](docs/15_o_olhinho.md).

---

## As telas

| Tela | Para quê |
|---|---|
| **Dashboard** | Como o mês está indo: sobrou ou faltou, o que foi decisão sua e o que foi herança de parcela |
| **Lançamentos** | A tabela de tudo — filtrar, corrigir categoria, lançar à mão, exportar |
| **Importar arquivos** | Trazer fatura CSV, extrato CSV e extrato OFX para dentro |
| **Planejamento** | Orçamento do mês, simulador de cortes e projeção de caixa de 18 meses |
| **Cartão e parcelas** | Tudo que já está contratado nos próximos meses |
| **Gastos fixos** | O piso do orçamento, e a comparação entre o que você cadastrou e o que paga de verdade |
| **Patrimônio** | Quanto você tem e por quantos meses isso te sustenta |
| **Investimentos** | A carteira sem escolher mês: posição de cada papel, quanto valorizou, rentabilidade mês a mês contra o CDI, e o rebalanceamento do aporte |
| **Metas e compras** | Objetivos de poupança e lista de desejos |
| **Financiamento** | Simulador PRICE/SAC com seguros e amortização extraordinária |
| **Regras** | As 289 regras que categorizam tudo sozinhas (207 de fatura, 82 de extrato) |
| **Imposto de renda** | O que declarar e onde, o que falta — e a aba de PGBL: quanto dá para deduzir e o que isso custa depois |
| **Configurações** | Categorias, contas, backup e manutenção |

---

## Onde ficam os seus dados

```
dados/financas.db          o banco (um arquivo só, fácil de copiar)
dados/backups/             backups .zip locais
```

E, na nuvem:

```
CAMINHO\PARA\OneDrive\Financas_Backup\financas_AAAA-MM-DD_HHMM.zip
```

**Por que o banco fica local e só o backup vai para a nuvem:** banco de dados
aberto e sincronização automática não combinam. Enquanto o app roda, o SQLite
mantém arquivos auxiliares com escritas ainda não gravadas, e o OneDrive pode
copiar o arquivo no meio do caminho. O `.zip` é um arquivo fechado — depois de
gravado não muda mais — e ainda por cima abre no Excel se um dia este programa
não existir.

Um backup é gerado **automaticamente ao final de toda importação**, e você
pode gerar um a qualquer momento em *Configurações → Backup*.

---

## Onde começar a ler o código

A pasta [`docs/`](docs/) tem a explicação completa, escrita para quem está
aprendendo a programar:

| Arquivo | Assunto |
|---|---|
| [00_COMECE_AQUI.md](docs/00_COMECE_AQUI.md) | O que é `.venv`, Streamlit, SQLite — e como rodar |
| [01_organizacao_do_projeto.md](docs/01_organizacao_do_projeto.md) | Que pasta faz o quê, e por quê |
| [02_banco_de_dados.md](docs/02_banco_de_dados.md) | As tabelas e a convenção de sinal |
| [03_leitura_de_arquivos.md](docs/03_leitura_de_arquivos.md) | CSV, OFX e as armadilhas de cada um |
| [04_motor_de_regras.md](docs/04_motor_de_regras.md) | Como a categorização automática funciona |
| [05_calculos.md](docs/05_calculos.md) | Cada indicador e de onde ele saía no Excel |
| [06_paginas_e_interface.md](docs/06_paginas_e_interface.md) | Como uma tela Streamlit funciona |
| [07_graficos.md](docs/07_graficos.md) | Os gráficos, e quando usar cada tipo |
| [08_backup_e_nuvem.md](docs/08_backup_e_nuvem.md) | A estratégia de backup |
| [09_receitas_de_alteracao.md](docs/09_receitas_de_alteracao.md) | "Quero adicionar uma categoria", "quero um gráfico novo"… |
| [10_glossario.md](docs/10_glossario.md) | Função, DataFrame, cache, dataclass… |
| [11_investimentos.md](docs/11_investimentos.md) | A carteira: as duas metades e a conta do rendimento |
| [12_carteira_e_rebalanceamento.md](docs/12_carteira_e_rebalanceamento.md) | Importar a posição da corretora e dividir o aporte do mês |
| [13_moeda_e_cotacoes.md](docs/13_moeda_e_cotacoes.md) | Dinheiro que não está em reais, e de onde vem o câmbio |
| [14_imposto_de_renda.md](docs/14_imposto_de_renda.md) | O que declarar e onde; por que a PLR é separada e o custo é o problema |
| [15_o_olhinho.md](docs/15_o_olhinho.md) | Esconder os valores com um clique — e por que não é senha |
| [16_previdencia_e_pgbl.md](docs/16_previdencia_e_pgbl.md) | PGBL: quanto dá para deduzir, quando não vale nada, e o imposto que fica para depois |
| [17_analise_de_papel.md](docs/17_analise_de_papel.md) | Analisar uma ação sem lucro, e por que 2x por dia não é 2x no período |
| [18_publicar.md](docs/18_publicar.md) | Compartilhar o app sem publicar sua vida — e sem reescrever o histórico |
| [19_metas_vinculadas.md](docs/19_metas_vinculadas.md) | Meta que se atualiza sozinha a partir do patrimônio real, e o bug do "nan" gravado no banco |
| [20_metas_e_compras.md](docs/20_metas_e_compras.md) | O velocímetro do ritmo, o preço que guarda histórico e o mês em que cada compra cabe |
| [21_o_visual.md](docs/21_o_visual.md) | O que é tema do Streamlit e o que é CSS nosso; o gráfico que passou a morar num cartão |
| [22_eixos_da_carteira.md](docs/22_eixos_da_carteira.md) | A mesma carteira por prazo, indexador ou liquidez — e por que o setor automático mentiria |
| [23_fechamento_de_caixa.md](docs/23_fechamento_de_caixa.md) | A equação que não deixa dinheiro sumir, a linha "não explicado" e os dois lados da balança que eram de meses diferentes |

O [CHANGELOG.md](CHANGELOG.md) registra o que mudou e por quê.

---

## Estrutura das pastas

```
finance_app/
├── iniciar.bat              duplo clique para abrir
├── app.py                   entrada: tema, menu, roteamento
├── requirements.txt         as bibliotecas usadas
├── .gitignore               o que não copiar / não versionar
│
├── financas/                O MOTOR — não importa streamlit
│   ├── config.py            caminhos, constantes, cores
│   ├── formato.py           texto ↔ número ↔ data
│   ├── cambio.py            dólar ↔ real, pelo PTAX do Banco Central
│   ├── banco.py             SQLite: tabelas e migrações
│   ├── dados.py             lê o banco e enriquece
│   ├── regras.py            categorização automática
│   ├── importador.py        arquivo → banco (com deduplicação)
│   ├── backup.py            .zip de CSVs para a nuvem
│   ├── cotacoes.py          preço de ativo por ticker
│   ├── indices.py           CDI e IPCA, das séries do Banco Central
│   ├── leitores/            um por formato de arquivo (5)
│   └── calculos/            um por área (12: kpis, parcelas, investimentos…)
│
├── ui/                      A APARÊNCIA
│   ├── tema.py              o CSS
│   ├── componentes.py       cartões, barras, cabeçalhos
│   ├── graficos.py          todos os gráficos Plotly
│   ├── privacidade.py       o olhinho: esconder os valores
│   └── estado.py            cache e memória entre cliques
│
├── paginas/                 uma tela por arquivo (13)
├── migracao/                scripts que trouxeram os dados do Excel
│   └── semente/             o retrato da planilha no dia da migração
├── verificacao/            10 scripts que provam que uma conta está certa
├── analises/                relatórios de terminal, fora do painel
│
├── arquivos_originais/      suas faturas, extratos e a planilha antiga
├── dados/                   o banco e os backups  ← não versionado
├── docs/                    a explicação de tudo
└── .venv/                   as bibliotecas  ← não copie, é recriável
```

**Por que os arquivos do banco ficam em `arquivos_originais/`:** eles estavam
soltos na raiz, misturados com o código. Separados, a raiz fica legível (só
código e configuração) e você sabe onde salvar a próxima fatura sem pensar.

**A separação entre `financas/` e `ui/` é proposital:** nenhum arquivo de
`financas/` importa Streamlit. Isso significa que dá para testar qualquer
cálculo rodando Python puro no terminal, sem subir o app — e foi assim que
todos os números foram conferidos contra a planilha.

---

## Como foi conferido

Os números não foram aceitos de olho. Cada etapa foi comparada com a planilha
original:

- **Migração** — receita, despesa e contagem de linhas conferidas mês a mês
  contra a aba `Base_Dados`. Diferença: **zero em todos os 15 meses**, nas
  1.050 linhas.
- **Parcelas futuras** — a grade projetada bate exatamente com a linha
  `TOTAL PREVISTO` da aba `Parcelas Futuras` (R$ ···· / R$ ···· / 117 × 5 / 0).
- **Financiamento** — a soma das amortizações fecha com o valor financiado e o
  saldo da última parcela é zero.
- **Leitores** — os 9 arquivos reais da pasta, 730 valores convertidos sem uma
  única falha.
- **Deduplicação** — importar o mesmo arquivo duas vezes grava 0 linhas na
  segunda; e as 20 transações que aparecem tanto no extrato CSV quanto no OFX
  são bloqueadas.

- **Rebalanceamento** — 2.159 checagens, incluindo centenas de carteiras
  sorteadas, provando que o aporte sugerido soma exato, nunca é negativo e
  aproxima a carteira da meta.
- **Competência da fatura** — 655 checagens de que o gasto do cartão conta no
  mês em que foi feito, com a chave de parcelamento acompanhando.
- **Previsão** — 378 checagens de que o previsto é sempre *o que falta*, e de
  que nada é contado duas vezes quando o dinheiro real chega: nem entre gasto
  fixo e parcela do cartão, nem entre o previsto e o realizado.
- **Investimentos** — 73 checagens de que a rentabilidade é composta e não
  somada, de que papel sem mês medido sai vazio, e de que compra em dólar
  é convertida uma vez só.
- **Olhinho** — 83 checagens de que os valores somem de tudo que a tela
  mostra, e de que a máscara **nunca** chega ao banco.
- **Previdência (PGBL)** — 69 checagens da tabela do IR, do redutor da Lei
  15.270/2025 e das três situações em que o PGBL não economiza nada.
- **Documentação** — 487 funções públicas, **nenhuma sem docstring**, e os 17
  guias todos no índice. (Este número diz que a explicação *existe*, não que
  ela está *correta* — ver [docs/01](docs/01_organizacao_do_projeto.md).)

Para refazer as conferências a qualquer momento:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m migracao.conferir
```

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m verificacao.conferir_rebalanceamento
```

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m verificacao.conferir_cambio
```

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m verificacao.conferir_documentacao
```

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m verificacao.conferir_privacidade
```

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m verificacao.conferir_previdencia
```

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m verificacao.conferir_investimentos
```

---

## Se precisar recriar o ambiente

```bash
cd CAMINHO\PARA\Phil\finance_app && python -m venv .venv && .venv\Scripts\python -m pip install -r requirements.txt
```

E, se quiser refazer a carga inicial a partir da planilha:

```bash
cd CAMINHO\PARA\Phil\finance_app && .venv\Scripts\python -m migracao.extrair_xlsm && .venv\Scripts\python -m migracao.carregar --recarregar
```
