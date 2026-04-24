# API - Modulos Realistas Implementados

Este documento descreve os novos modulos implementados para aproximar o NeoBank de um banco real.

## 1) OTP Transacional

### Solicitar OTP
POST `/api/otp/solicitar`

Body:
```json
{
  "acao": "transferencia"
}
```

Resposta (simulador):
```json
{
  "mensagem": "OTP gerado com sucesso",
  "acao": "transferencia",
  "expira_em": "2026-04-06 15:00:00",
  "codigo_simulado": "123456"
}
```

Acoes usadas:
- `transferencia`
- `pix`
- `pagar_divida`
- `cartao_compra`
- `pagar_fatura`
- `pagar_boleto`

Observacao:
- Operacoes com valor >= R$500 exigem OTP.
- Sem OTP, backend retorna HTTP `428` com `requires_otp=true`.
- Em operações sensíveis, o limiar de OTP pode ser reduzido dinamicamente conforme score de risco.

## 2) PIX Avancado

### Agendar PIX
POST `/api/pix/agendar`
```json
{
  "chave": "destino@email.com",
  "valor": 150.0,
  "descricao": "Pagamento agendado",
  "data_execucao": "2026-05-01 10:30:00"
}
```

### Listar agendamentos
GET `/api/pix/agendar`

### Cancelar agendamento
POST `/api/pix/agendamentos/{id}/cancelar`

### Processar agendamentos vencidos
POST `/api/pix/agendamentos/processar`

### Devolver PIX
POST `/api/pix/devolver`
```json
{
  "codigo": "CODIGO_TRANSACAO_PIX_ORIGINAL",
  "valor": 50.0
}
```

Regras:
- So devolve PIX recebido pela propria conta.
- Permite devolucao parcial e total.

## 3) Cartao de Credito com Fatura

### Lancar compra
POST `/api/cartoes/{cartao_id}/compras`
```json
{
  "descricao": "Compra marketplace",
  "valor": 320.0,
  "parcelas": 3
}
```

### Consultar fatura atual
GET `/api/cartoes/{cartao_id}/fatura`

### Pagar fatura
POST `/api/cartoes/{cartao_id}/fatura/pagar`
```json
{
  "valor": 200.0
}
```

Regras:
- Compra aumenta `limite_usado`.
- Pagamento da fatura reduz `limite_usado`.
- Pagamento parcial permitido.
- Compras parceladas sao distribuídas por competência mensal.

## 4) Ledger Contabil

### Consultar lancamentos
GET `/api/ledger?limit=100`

Retorna trilha financeira por conta:
- tipo
- direcao (debito/credito)
- saldo_antes
- saldo_depois
- codigo de transacao

## 5) Boletos

### Emitir boleto
POST `/api/boletos`
```json
{
  "descricao": "Mensalidade academia",
  "beneficiario": "Academia XPTO",
  "valor": 199.90,
  "vencimento_em": "2026-05-10",
  "multa_percentual": 2.0,
  "juros_mensal": 1.0
}
```

### Listar boletos
GET `/api/boletos`

### Pagar boleto
POST `/api/boletos/{boleto_id}/pagar`

Regra:
- Pagamento usa o `valor_atual` do boleto (com encargos se houver atraso).
- Para valores >= R$500, exige OTP (`acao_otp: pagar_boleto`).

### Processar atraso dos boletos
POST `/api/boletos/processar-atraso`

Aplica:
- multa única (quando entra em atraso)
- juros proporcional diário com base no `juros_mensal`

## 6) Como implementar eu no seu lugar (resumo pratico)

1. Definir invariantes de negocio por modulo
- nunca saldo abaixo do permitido
- toda transacao financeira gera lancamento contábil
- operacao sensivel exige OTP por limiar

2. Fazer backend antes do frontend
- modelagem SQL
- regras de validacao
- endpoint + smoke tests

3. Integrar frontend em cima de contrato estavel
- tratar HTTP 428 para OTP
- tratar erros com mensagens amigaveis

4. Instrumentar e validar
- py_compile
- test_client para fluxos felizes e erros
- revisar logging e notificacoes

## 7) Job Diario (cron-like)

### Processamento diário por usuário
POST `/api/jobs/processar-diario`
```json
{
  "scope": "me"
}
```

Processa:
- PIX agendados vencidos do usuário
- fechamento de competência de parcelas para fatura do mês
- juros rotativo de faturas vencidas do usuário
- atualização de boletos em atraso (multa/juros)
- execução de pagamentos programáveis
- prevenção de descoberto e smart sweep

## 8) IA Autônoma (Agentic AI)

### Executar tarefa de agente
POST `/api/ai/agentes/tarefas`
```json
{
  "tipo": "contestar_cobranca",
  "entrada": {"descricao": "cobrança duplicada"}
}
```

Tipos suportados:
- `contestar_cobranca`
- `investigar_fatura`
- `orquestrar_abertura_conta`

### Listar tarefas executadas
GET `/api/ai/agentes/tarefas`

## 9) Automação Inteligente

### Configuração de automação
GET/POST `/api/automacao/config`

Campos principais:
- `sweep_ativo`
- `sweep_min_reserva`
- `sweep_percentual_excesso`
- `prevencao_descoberto_ativa`
- `limite_alerta`
- `tom_comunicacao`
- `cenario_forcado`

### Reserva de liquidez
GET/POST `/api/automacao/reserva`
```json
{
  "acao": "depositar",
  "valor": 300.0
}
```

### Executar automação sob demanda
POST `/api/automacao/executar`

### Cenário UX contextual
GET `/api/ux/cenario`

### Painel de risco comportamental
GET `/api/risco/painel`

Retorna:
- `score` (0-100)
- `nivel` (baixo/medio/alto)
- `fatores`
- `limiar_otp` dinâmico

## 10) Open Finance Multi-fonte

### Cadastrar fonte externa
POST `/api/openfinance/fontes`
```json
{
  "instituicao": "Banco Externo",
  "tipo": "investimento",
  "saldo": 12000.0
}
```

### Listar fontes
GET `/api/openfinance/fontes`

### Remover fonte
DELETE `/api/openfinance/fontes/{fonte_id}`

### Consolidado patrimonial
GET `/api/openfinance/consolidado`

## 11) Liquidação Programável (tokenização simulada)

### Criar pagamento programável
POST `/api/pagamentos-programaveis`
```json
{
  "descricao": "Pagamento fornecedor",
  "destinatario": "Fornecedor ABC",
  "valor": 850.0,
  "condicao_tipo": "data",
  "condicao_valor": "2026-12-20"
}
```

`condicao_tipo` aceitos:
- `data`
- `saldo_minimo`

### Listar pagamentos programáveis
GET `/api/pagamentos-programaveis`

### Cancelar pagamento pendente
POST `/api/pagamentos-programaveis/{id}/cancelar`

### Processamento diário global (todos usuários)
POST `/api/jobs/processar-diario`

Headers:
- `Authorization: Bearer <token_usuario_autenticado>`
- `X-Job-Token: <JOB_TOKEN>`

Body:
```json
{
  "scope": "all"
}
```

Observações:
- `JOB_TOKEN` deve estar configurado no backend.
- Sem token válido, retorno `403`.
