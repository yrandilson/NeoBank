# Roadmap Banco Realista (NeoBank)

Este documento organiza a evolucao do NeoBank para um simulador de banco real em fases, com prioridade tecnica e de negocio.

## Objetivo
Transformar o projeto atual em uma plataforma bancaria simulada com:
- trilha contabil auditavel
- jornadas realistas de pagamentos/cartao/PIX
- seguranca transacional
- conformidade e operacao

## Fase 1 - Nucleo Confiavel (Alta prioridade)
Status atual no projeto:
- Gestao de dividas implementada
- Ledger contabil basico implementado

Itens:
1. Ledger de dupla entrada
- Cada evento financeiro deve gerar ao menos 2 lancamentos (debito e credito).
- Adicionar contas de compensacao (ex.: caixa_banco, carteira_cliente, receita_juros).
- Garantir idempotencia por codigo transacional.

2. Auditoria e rastreabilidade
- Persistir metadados: usuario, IP, user-agent, origem da operacao.
- Criar trilha imutavel para operacoes sensiveis.

3. Resiliencia transacional
- Padronizar transacoes SQL com rollback em erro.
- Garantir fechamento de conexao em todos os fluxos.

## Fase 2 - Produtos Core de Banco
1. PIX realista
- chave aleatoria automatica
- QR estatico e dinamico
- agendamento
- devolucao total/parcial

2. Cartao com fatura
- ciclo de fechamento
- valor minimo
- juros rotativo
- parcelamento de compras

3. Boletos e cobrancas
- emissao de boleto
- juros/multa por atraso
- baixa automatica

## Fase 3 - Seguranca e Compliance
1. 2FA transacional
- OTP por acao sensivel
- validade curta e tentativa maxima

2. Controle de risco
- limites por canal, horario e valor
- score de fraude simplificado

3. KYC e compliance
- onboarding com status de verificacao
- flags PEP/sancoes simuladas

## Fase 4 - Operacao e Suporte
1. Contestacao e chargeback
2. Central de atendimento com SLA
3. Reconciliacao diaria e relatorios
4. Exportacao de extrato (PDF/CSV)

## Criterios de pronto por funcionalidade
- API documentada
- validacoes de entrada
- testes de sucesso e falha
- logs estruturados
- observabilidade minima (latencia/erros)

## Sequencia recomendada de entrega (sprints)
1. Sprint A: ledger completo + reconciliacao
2. Sprint B: PIX avancado + agendamentos
3. Sprint C: cartao/fatura
4. Sprint D: boletos
5. Sprint E: 2FA e antifraude
6. Sprint F: suporte, contestacao e relatorios
