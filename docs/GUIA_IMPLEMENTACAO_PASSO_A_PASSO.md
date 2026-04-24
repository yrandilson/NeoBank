# Guia Passo a Passo - Como Eu Implementaria (NeoBank)

Este guia descreve como implementar cada funcionalidade de banco real no NeoBank, em ordem pratica.

## 1) Ledger de Dupla Entrada
Objetivo: tornar saldo auditavel e consistente.

Passos:
1. Criar tabela de ledger com: conta_id, tipo, direcao, valor, saldo_antes, saldo_depois, transacao_codigo.
2. Definir contas de compensacao internas (contas tecnicas).
3. Criar helper unico para registrar lancamentos.
4. Em cada operacao financeira, registrar debito e credito no mesmo bloco transacional.
5. Criar endpoint de consulta do ledger por conta.
6. Criar job de conciliacao diaria: soma ledger vs saldo da conta.

Checklist:
- idempotencia por codigo
- sem update/delete de lancamentos
- trilha temporal completa

## 2) PIX Realista
Passos:
1. Modelar tabela de cobranças PIX (txid, expiracao, payload).
2. Implementar QR dinamico e chave aleatoria automatica.
3. Criar fluxo de agendamento (status: pendente, executado, cancelado).
4. Implementar devolucao PIX total/parcial.
5. Adicionar validacoes de limite diario e horario.

## 3) Cartao com Fatura
Passos:
1. Criar tabelas de compras, faturas e parcelas.
2. Gerar fatura por ciclo (fechamento/vencimento).
3. Permitir pagamento total, minimo e parcial.
4. Em parcial, aplicar juros rotativo sobre saldo remanescente.
5. Adicionar historico de fatura e simulador de parcelamento.
6. Incluir bloqueio e desbloqueio de cartão com feedback ao usuário.

## 4) Boletos
Passos:
1. Criar tabela de boletos (linha_digitavel, vencimento, status, valor_atual, dias_atraso_aplicados).
2. Implementar emissao e pagamento.
3. Em atraso, aplicar multa (uma vez) e juros diario proporcional.
4. Baixar boleto, registrar em transacoes e ledger.
5. Integrar processamento de atraso no job diario.
6. Expor tela de emissao/listagem/pagamento no frontend.

## 5) Transferencias Agendadas e Recorrentes
Passos:
1. Criar tabela com periodicidade (unica, mensal, semanal).
2. Criar worker de execucao periodica.
3. Persistir tentativas/erros e proxima_execucao.
4. Permitir pausar, cancelar e editar recorrencia.

## 6) Seguranca (2FA + Sessao)
Passos:
1. Tabela de desafios OTP com expiracao e tentativas.
2. Exigir OTP em operacoes de risco (PIX, TED, pagamento alto).
3. Vincular dispositivos confiaveis.
4. Painel para encerrar sessoes ativas.

## 7) Antifraude Basico
Passos:
1. Regras: valor alto, horario incomum, dispositivo novo, destino novo.
2. Score de risco por operacao.
3. Bloqueio temporario quando score exceder limiar.
4. Workflow de desbloqueio via suporte.

## 8) KYC e Compliance (simulado)
Passos:
1. Status KYC (pendente, aprovado, rejeitado).
2. Bloquear operacoes acima do limite sem KYC aprovado.
3. Tabela de verificacoes e evidencias.
4. Trilha de auditoria para alteracoes de status.

## 9) Contestacao e Suporte
Passos:
1. Tabela de tickets (tipo, prioridade, SLA).
2. Fluxo de contestacao de transacoes.
3. Timeline de interacoes.
4. Resultado final com estorno quando aplicavel.

## 10) Relatorios e Operacao
Passos:
1. Exportar extrato PDF/CSV.
2. Relatorio mensal consolidado por categoria.
3. Painel operacional (falhas, pendencias, reconciliacao).
4. Backups e rotacao de logs.

## 11) Cron Diario (operacao realista)
Passos:
1. Criar endpoint de processamento diario com escopo por usuario e global.
2. No escopo global, proteger com token de job (`JOB_TOKEN`).
3. Incluir no processamento:
- PIX agendado vencido
- juros rotativo para faturas em atraso
4. Agendar no sistema operacional:
- Windows Task Scheduler ou cron no Linux.
5. Registrar resultado (processados/falhas) para auditoria operacional.

## 12) Fechamento Mensal por Competencia (Cartao)
Passos:
1. Ao lancar compra parcelada, criar as parcelas futuras com `mes_ref`.
2. Faturar apenas a parcela do mes corrente no momento da compra.
3. Deixar parcelas futuras como pendentes (sem `fatura_id`).
4. No job diario, mover parcelas pendentes cujo `mes_ref <= mes atual` para a fatura correspondente.
5. Recalcular total da fatura e valor minimo apos movimentar parcelas.
6. Aplicar juros rotativo apenas em faturas vencidas com saldo em aberto.

## 13) Historico de Faturas e Exportacao
Passos:
1. Criar endpoint para listar faturas por cartao (ultimos meses) com valor em aberto.
2. Criar endpoint de detalhe da fatura com parcelas da competencia.
3. No frontend, adicionar pagina dedicada de faturas com seletor de cartao.
4. Adicionar filtro de periodo (3, 6, 12, 24 meses) sem nova chamada ao backend.
5. Adicionar filtro de status (aberta, fechada, paga) combinado ao periodo.
6. Permitir pagamento da fatura aberta diretamente na tela de historico.
7. Implementar exportacao CSV da fatura detalhada (cabecalho + parcelas).
8. Implementar exportacao CSV consolidada das faturas conforme filtros aplicados.

## 14) Agentic AI (Agentes Autonomos)
Passos:
1. Definir tipos de tarefa (contestacao, investigacao de fatura, orquestracao de onboarding).
2. Criar tabela de tarefas com `entrada_json` e `resultado_json`.
3. Implementar executor com etapas por tipo e trilha de auditoria.
4. Expor endpoint de execucao e historico de tarefas.
5. Integrar notificacoes de status para o usuario.

## 15) Smart Sweep e Prevenção de Descoberto
Passos:
1. Criar configuracao por usuario (limites, percentual, reserva minima).
2. Calcular obrigacoes de curto prazo (boletos, dividas e faturas).
3. Implementar prevençao preditiva para transferir da reserva quando saldo projetado cair.
4. Implementar sweep de excesso para investimento automatico quando seguro.
5. Integrar execucao manual e execucao no job diario.

## 16) UX por Cenário e Tom Adaptativo
Passos:
1. Definir cenarios (padrao, pagamento_contas, acumular_investir).
2. Criar endpoint de recomendacao de cenario por contexto financeiro.
3. Permitir override manual (cenario_forcado) para testes e operacao.
4. Configurar tom de comunicacao para orientar mensagens e friccao.
5. Exibir no dashboard um banner de contexto e atalhos dinamicos por cenario.

## 19) Risco Comportamental e Fricção Adaptativa
Passos:
1. Calcular score de risco por comportamento recente (picos de saída, destinos novos, inadimplência e horário sensível).
2. Converter score em limiar OTP dinâmico por faixa de risco.
3. Aplicar limiar dinâmico nas operações sensíveis (TED, PIX, fatura, dívida, boleto, compra no crédito).
4. Expor painel de risco para transparência ao usuário.
5. Tratar HTTP 428 no frontend para solicitar OTP sob demanda, sem quebra de fluxo.

## 20) Dashboard Dinâmico por Cenário (UX real adaptativa)
Passos:
1. No backend, incluir no payload do dashboard: `cenario_ux`, `tom_comunicacao`, `risco_nivel` e `limiar_otp`.
2. No frontend, exibir banner contextual com mensagem adaptada ao tom configurado.
3. Reordenar os cards do dashboard por prioridade de cenário (ex: contas, investir, padrão).
4. Alterar atalhos rápidos conforme intenção prevista do usuário.
5. Exibir painel "Foco do dia" com orientação operacional e badge de risco.

## 21) Ordem Personalizada de Widgets (preferência do usuário)
Passos:
1. Persistir configuração de ordem no perfil de automação do usuário.
2. Permitir ativar/desativar override manual da ordem de cards.
3. Validar e normalizar lista de widgets permitidos no backend.
4. Aplicar ordem personalizada no dashboard quando ativa, mantendo fallback por cenário.
5. Permitir reordenação via drag-and-drop direto no dashboard.
6. Oferecer presets de layout (investidor, pagador, balanceado).

## 17) Identidade Financeira Multi-fonte (Open Finance)
Passos:
1. Criar tabela de fontes externas por instituicao e tipo.
2. Implementar CRUD basico das fontes.
3. Expor consolidado patrimonial (conta interna + reserva + fontes externas).
4. Mostrar resumo unificado no hub de automacao.

## 18) Liquidação Programável e Tokenização (simulação)
Passos:
1. Criar tabela de pagamentos condicionais com status e codigo de execução.
2. Modelar condições por data e por saldo mínimo.
3. Executar automaticamente no job diario quando condicao for atendida.
4. Expor cancelamento de pagamentos pendentes.
5. Integrar no frontend como base de uma esteira tipo Drex programável.

## Plano de execucao sugerido (pratico)
Semana 1-2:
- ledger completo
- reconciliacao basica

Semana 3-4:
- PIX avancado (agendamento + devolucao)

Semana 5-6:
- cartao/fatura

Semana 7:
- boletos

Semana 8:
- 2FA + antifraude

Semana 9:
- suporte/contestacao + relatorios

## Dica de implementacao no estilo senior
- comece por modelo de dados e invariantes
- escreva testes de contrato da API antes do frontend
- implemente primeiro caminho feliz e depois casos de erro
- trate idempotencia e concorrencia cedo
- so depois invista em refinamento visual
