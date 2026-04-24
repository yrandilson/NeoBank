# 🏦 NeoBank — Sistema Bancário Digital com IA

Sistema bancário completo construído com **Python + Flask + SQLite + IA (Claude)**

---

## ✅ Funcionalidades

### 🔐 Autenticação
- Cadastro com CPF, nome, e-mail e senha
- Login com JWT simulado (token seguro com PBKDF2 + salt)
- Sessões com expiração automática (8h)
- Conta demo pré-criada

### 💰 Conta Corrente
- Criação automática de conta ao cadastrar
- Número de conta gerado automaticamente
- Limite de cheque especial (R$500)
- **Bônus de R$100** para novos usuários
- Extrato completo com filtros por tipo

### 💸 Movimentações
- **Depósito** com valores rápidos
- **Transferência TED** entre contas NeoBank
- **PIX** com chaves CPF, e-mail, telefone e aleatória
- **Despesas & Receitas** com cadastro de entrada/saída por categoria
- Edição e exclusão de lançamentos com estorno automático de saldo
- Gráfico mensal de saídas por categoria
- Orçamento mensal por categoria com alertas de limite (80%/100%)
- Histórico completo de todas as transações

### 💳 Cartões
- Cartão de débito criado automaticamente
- Criação de novos cartões (débito/crédito/virtual)
- Bloqueio de cartões
- Desbloqueio de cartões
- Visualização com número mascarado

### 📈 Investimentos
- **CDB** — 12,5% a.a.
- **LCI** — 10,8% a.a. (isento IR)
- **LCA** — 10,5% a.a. (isento IR)
- **Tesouro Direto** — 13,2% a.a.
- **Fundos Multimercado** — 9,8% a.a.
- Resgate com cálculo automático de IR (15%)

### 🏦 Empréstimos
- Simulação em tempo real (tabela Price)
- Taxas progressivas por prazo
- Limite de R$50.000
- Crédito instantâneo na conta

### 📌 Gestão de Dívidas
- Cadastro de dívidas por categoria e credor
- Controle de valor total, valor pago e saldo pendente
- Acompanhamento de parcelas pagas x total
- Pagamento de dívida com débito direto da conta
- Marcação automática de dívida quitada

### 📄 Boletos
- Emissão de boletos com linha digitável simulada
- Pagamento de boleto com débito em conta
- Cálculo automático de multa e juros para boletos vencidos
- Processamento manual de atraso e também via job diário

### 📚 Núcleo Contábil (Ledger)
- Lançamentos contábeis por operação financeira
- Histórico de débito/crédito por conta
- Endpoint de consulta: `/api/ledger`

### 🔐 OTP Transacional
- Geração de OTP por ação sensível
- Exigência automática para operações acima de R$500
- Fluxo com expiração e limite de tentativas

### ⚡ PIX Avançado
- PIX agendado com execução posterior
- Cancelamento de agendamento pendente
- Processamento de agendamentos vencidos
- Devolução PIX parcial ou total

### 🗓️ Processamento Diário (Simulação de Cron)
- Processa PIX agendados vencidos
- Aplica juros rotativo em faturas vencidas
- Atualiza boletos vencidos com multa/juros
- Execução por usuário na interface
- Execução global via endpoint protegido por token

### 🧾 Fatura de Cartão
- Lançamento de compras no cartão de crédito
- Parcelamento com distribuição por competência mensal
- Consulta de fatura do mês corrente
- Histórico de faturas dos últimos meses
- Detalhe de parcelas por fatura selecionada
- Pagamento total/parcial da fatura
- Atualização automática do limite utilizado

### 🧮 Fechamento Mensal de Fatura
- Job diário move parcelas pendentes para a fatura do mês correspondente
- Recalcula total da fatura e valor mínimo automaticamente
- Base para ciclo realista de fechamento/competência

### 🤖 Assistente IA (Claude)
- Chat integrado na interface
- Contexto completo da conta do usuário
- Dicas de investimento personalizadas
- Análise financeira inteligente

### 🧠 IA Autônoma e Automação Inteligente
- Agentes autônomos para contestação, investigação de fatura e orquestração de fluxos
- Smart Sweep para investimento automático de excesso de caixa com reserva de segurança
- Prevenção preditiva de descoberto com transferência automática da reserva de liquidez
- Configuração de tom e cenário UX orientado ao contexto financeiro
- Score de risco comportamental com limiar OTP dinâmico por usuário
- Dashboard adaptado por cenário (pagamento de contas, investir, padrão)

### 🔗 Open Finance Multi-fonte
- Cadastro de fontes externas por instituição/tipo/saldo
- Consolidação patrimonial em visão única (NeoBank + fontes externas)

### 🧩 Liquidação Programável (simulação Drex/tokenização)
- Pagamentos programáveis condicionais por data ou por saldo mínimo
- Execução automática via job diário e também por execução manual da automação

---

## 🚀 Como Executar

### Pré-requisitos
```bash
Python 3.8+
pip install -r requirements.txt
```

### Executar
```bash
python app.py
```

Acesse: **http://127.0.0.1:5000**

### Variáveis de ambiente (opcional)
- `FLASK_DEBUG=1` ativa modo debug (padrão: `0`)
- `HOST=0.0.0.0` altera host (padrão: `127.0.0.1`)
- `PORT=5000` altera porta (padrão: `5000`)
- `JOB_TOKEN=seu_token_seguro` habilita execução global do job diário

Exemplo (PowerShell):
```powershell
$env:FLASK_DEBUG="1"
$env:HOST="127.0.0.1"
$env:PORT="5000"
python app.py
```

### Conta Demo
- E-mail: `demo@neobank.com`
- Senha: `demo123`

Ou clique em **"usar conta demo"** na tela de login.

Observação: ao iniciar, o sistema garante/reconcilia automaticamente a conta demo (usuário ativo, senha válida e dados mínimos necessários).

---

## 🗄️ Banco de Dados

SQLite com as seguintes tabelas:

| Tabela | Descrição |
|--------|-----------|
| `usuarios` | Dados dos clientes |
| `contas` | Contas bancárias |
| `transacoes` | Histórico de movimentações |
| `ledger_lancamentos` | Lançamentos contábeis detalhados |
| `cartoes` | Cartões de débito/crédito |
| `pix_chaves` | Chaves PIX cadastradas |
| `emprestimos` | Empréstimos ativos |
| `investimentos` | Carteira de investimentos |
| `dividas` | Dívidas cadastradas e pagamentos |
| `gastos_categorias` | Entradas/saídas categorizadas para controle financeiro |
| `orcamentos_categorias` | Limites mensais por categoria para alertas de orçamento |
| `desafios_otp` | Desafios OTP transacionais |
| `pix_agendamentos` | PIX agendados e status de execução |
| `pix_devolucoes` | Histórico de devoluções PIX |
| `faturas_cartao` | Controle de faturas de crédito |
| `compras_cartao` | Compras lançadas no crédito |
| `parcelas_compra_cartao` | Parcelas distribuídas por mês de competência |
| `boletos` | Emissão, status e atualização de boletos |
| `automacao_config` | Configurações de automação inteligente por usuário |
| `reserva_liquidez` | Reserva para proteção de fluxo de caixa |
| `open_finance_fontes` | Fontes externas de Open Finance |
| `pagamentos_programaveis` | Liquidação condicional programável |
| `ai_agentes_tarefas` | Histórico de tarefas de agentes autônomos |
| `sessoes` | Tokens de autenticação |
| `notificacoes` | Notificações do sistema |

---

## 🔒 Segurança
- Senhas com **PBKDF2-SHA256 + salt** (100.000 iterações)
- Comparação de hashes resistente a timing attacks
- Tokens de sessão com 32 bytes de entropia
- Foreign keys habilitadas no SQLite
- Validação de saldo antes de cada transação

---

## 📁 Estrutura

```
NeoBank/
├── app.py          # Backend Flask com todas as rotas
├── index.html      # Frontend completo (single-file)
├── banco.db        # Banco SQLite (criado automaticamente)
├── docs/
│   ├── ROADMAP_BANCO_REAL.md
│   ├── GUIA_IMPLEMENTACAO_PASSO_A_PASSO.md
│   └── API_MODULOS_REALISTAS.md
├── requirements.txt
└── README.md
```

## 🧭 Documentação de Evolução
- Roadmap por fases: `docs/ROADMAP_BANCO_REAL.md`
- Guia técnico passo a passo: `docs/GUIA_IMPLEMENTACAO_PASSO_A_PASSO.md`
- Referência das APIs avançadas: `docs/API_MODULOS_REALISTAS.md`
