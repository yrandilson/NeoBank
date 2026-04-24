"""
NeoBank - Sistema Bancário Completo com IA
Backend: Flask + SQLite
"""

import sqlite3
import hashlib
import hmac
import secrets
import json
from functools import wraps
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
import os
import re

app = Flask(__name__, static_folder='static')
DB_PATH = os.path.join(os.path.dirname(__file__), 'banco.db')

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        cpf         TEXT UNIQUE NOT NULL,
        nome        TEXT NOT NULL,
        email       TEXT UNIQUE NOT NULL,
        telefone    TEXT,
        senha_hash  TEXT NOT NULL,
        salt        TEXT NOT NULL,
        criado_em   TEXT DEFAULT (datetime('now')),
        ativo       INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS contas (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
        numero          TEXT UNIQUE NOT NULL,
        agencia         TEXT NOT NULL DEFAULT '0001',
        tipo            TEXT NOT NULL DEFAULT 'corrente',
        saldo           REAL NOT NULL DEFAULT 0.0,
        limite_cheque   REAL NOT NULL DEFAULT 0.0,
        status          TEXT NOT NULL DEFAULT 'ativa',
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS transacoes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_origem    INTEGER REFERENCES contas(id),
        conta_destino   INTEGER REFERENCES contas(id),
        tipo            TEXT NOT NULL,
        valor           REAL NOT NULL,
        descricao       TEXT,
        status          TEXT NOT NULL DEFAULT 'concluida',
        saldo_anterior  REAL,
        saldo_posterior REAL,
        criado_em       TEXT DEFAULT (datetime('now')),
        codigo          TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS ledger_lancamentos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id        INTEGER NOT NULL REFERENCES contas(id),
        transacao_codigo TEXT,
        tipo            TEXT NOT NULL,
        direcao         TEXT NOT NULL,
        valor           REAL NOT NULL,
        saldo_antes     REAL NOT NULL,
        saldo_depois    REAL NOT NULL,
        descricao       TEXT,
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS cartoes (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id        INTEGER NOT NULL REFERENCES contas(id),
        numero          TEXT UNIQUE NOT NULL,
        cvv             TEXT NOT NULL,
        validade        TEXT NOT NULL,
        tipo            TEXT NOT NULL DEFAULT 'debito',
        limite          REAL DEFAULT 0.0,
        limite_usado    REAL DEFAULT 0.0,
        status          TEXT NOT NULL DEFAULT 'ativo',
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS pix_chaves (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id    INTEGER NOT NULL REFERENCES contas(id),
        tipo        TEXT NOT NULL,
        chave       TEXT UNIQUE NOT NULL,
        ativa       INTEGER DEFAULT 1,
        criado_em   TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS emprestimos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id        INTEGER NOT NULL REFERENCES contas(id),
        valor           REAL NOT NULL,
        juros_mensal    REAL NOT NULL,
        parcelas        INTEGER NOT NULL,
        parcelas_pagas  INTEGER DEFAULT 0,
        valor_parcela   REAL NOT NULL,
        status          TEXT DEFAULT 'ativo',
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS investimentos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id        INTEGER NOT NULL REFERENCES contas(id),
        tipo            TEXT NOT NULL,
        valor_inicial   REAL NOT NULL,
        valor_atual     REAL NOT NULL,
        taxa_anual      REAL NOT NULL,
        data_vencimento TEXT,
        status          TEXT DEFAULT 'ativo',
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS dividas (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id        INTEGER NOT NULL REFERENCES contas(id),
        descricao       TEXT NOT NULL,
        categoria       TEXT DEFAULT 'geral',
        credor          TEXT,
        valor_total     REAL NOT NULL,
        valor_pago      REAL NOT NULL DEFAULT 0.0,
        parcelas_total  INTEGER NOT NULL DEFAULT 1,
        parcelas_pagas  INTEGER NOT NULL DEFAULT 0,
        valor_parcela   REAL NOT NULL,
        juros_mensal    REAL NOT NULL DEFAULT 0.0,
        vencimento      TEXT,
        status          TEXT DEFAULT 'ativa',
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS gastos_categorias (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id            INTEGER NOT NULL REFERENCES contas(id),
        tipo_movimento      TEXT NOT NULL,
        categoria           TEXT NOT NULL DEFAULT 'geral',
        descricao           TEXT NOT NULL,
        valor               REAL NOT NULL,
        transacao_codigo    TEXT,
        criado_em           TEXT DEFAULT (datetime('now')),
        atualizado_em       TEXT
    );

    CREATE TABLE IF NOT EXISTS orcamentos_categorias (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id            INTEGER NOT NULL REFERENCES contas(id),
        categoria           TEXT NOT NULL,
        limite_mensal       REAL NOT NULL,
        mes_ref             TEXT NOT NULL,
        criado_em           TEXT DEFAULT (datetime('now')),
        UNIQUE(conta_id, categoria, mes_ref)
    );

    CREATE TABLE IF NOT EXISTS desafios_otp (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id       INTEGER NOT NULL REFERENCES usuarios(id),
        acao            TEXT NOT NULL,
        codigo_hash     TEXT NOT NULL,
        salt            TEXT NOT NULL,
        expira_em       TEXT NOT NULL,
        tentativas      INTEGER DEFAULT 0,
        max_tentativas  INTEGER DEFAULT 5,
        usado           INTEGER DEFAULT 0,
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS pix_agendamentos (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id      INTEGER NOT NULL REFERENCES usuarios(id),
        conta_id        INTEGER NOT NULL REFERENCES contas(id),
        chave           TEXT NOT NULL,
        valor           REAL NOT NULL,
        descricao       TEXT,
        data_execucao   TEXT NOT NULL,
        status          TEXT DEFAULT 'pendente',
        codigo_transacao TEXT,
        erro            TEXT,
        criado_em       TEXT DEFAULT (datetime('now')),
        processado_em   TEXT
    );

    CREATE TABLE IF NOT EXISTS pix_devolucoes (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        transacao_original  TEXT NOT NULL,
        transacao_devolucao TEXT NOT NULL,
        conta_origem        INTEGER NOT NULL REFERENCES contas(id),
        conta_destino       INTEGER NOT NULL REFERENCES contas(id),
        valor               REAL NOT NULL,
        criado_em           TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS faturas_cartao (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        cartao_id       INTEGER NOT NULL REFERENCES cartoes(id),
        mes_ref         TEXT NOT NULL,
        total_fatura    REAL NOT NULL DEFAULT 0.0,
        valor_pago      REAL NOT NULL DEFAULT 0.0,
        valor_minimo    REAL NOT NULL DEFAULT 0.0,
        status          TEXT DEFAULT 'aberta',
        fechamento_em   TEXT,
        vencimento_em   TEXT,
        criado_em       TEXT DEFAULT (datetime('now')),
        UNIQUE(cartao_id, mes_ref)
    );

    CREATE TABLE IF NOT EXISTS compras_cartao (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        cartao_id       INTEGER NOT NULL REFERENCES cartoes(id),
        fatura_id       INTEGER NOT NULL REFERENCES faturas_cartao(id),
        descricao       TEXT NOT NULL,
        valor           REAL NOT NULL,
        parcelas        INTEGER NOT NULL DEFAULT 1,
        parcela_atual   INTEGER NOT NULL DEFAULT 1,
        status          TEXT DEFAULT 'ativa',
        criado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS parcelas_compra_cartao (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        compra_id            INTEGER NOT NULL REFERENCES compras_cartao(id),
        cartao_id            INTEGER NOT NULL REFERENCES cartoes(id),
        mes_ref              TEXT NOT NULL,
        numero_parcela       INTEGER NOT NULL,
        total_parcelas       INTEGER NOT NULL,
        valor_parcela        REAL NOT NULL,
        fatura_id            INTEGER REFERENCES faturas_cartao(id),
        status               TEXT DEFAULT 'pendente',
        criado_em            TEXT DEFAULT (datetime('now')),
        UNIQUE(compra_id, numero_parcela)
    );

    CREATE TABLE IF NOT EXISTS boletos (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        conta_id            INTEGER NOT NULL REFERENCES contas(id),
        linha_digitavel     TEXT UNIQUE NOT NULL,
        descricao           TEXT NOT NULL,
        beneficiario        TEXT NOT NULL,
        valor_original      REAL NOT NULL,
        valor_atual         REAL NOT NULL,
        multa_percentual    REAL NOT NULL DEFAULT 2.0,
        juros_mensal        REAL NOT NULL DEFAULT 1.0,
        dias_atraso_aplicados INTEGER NOT NULL DEFAULT 0,
        vencimento_em       TEXT NOT NULL,
        status              TEXT NOT NULL DEFAULT 'pendente',
        pago_em             TEXT,
        criado_em           TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS automacao_config (
        id                          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id                  INTEGER NOT NULL UNIQUE REFERENCES usuarios(id),
        sweep_ativo                 INTEGER NOT NULL DEFAULT 0,
        sweep_min_reserva           REAL NOT NULL DEFAULT 500.0,
        sweep_percentual_excesso    REAL NOT NULL DEFAULT 0.3,
        prevencao_descoberto_ativa  INTEGER NOT NULL DEFAULT 1,
        limite_alerta               REAL NOT NULL DEFAULT 100.0,
        tom_comunicacao             TEXT NOT NULL DEFAULT 'neutro',
        cenario_forcado             TEXT,
        dashboard_ordem_ativa       INTEGER NOT NULL DEFAULT 0,
        dashboard_ordem_widgets     TEXT,
        atualizado_em               TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS reserva_liquidez (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id          INTEGER NOT NULL UNIQUE REFERENCES usuarios(id),
        saldo_reserva       REAL NOT NULL DEFAULT 0.0,
        atualizado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS open_finance_fontes (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id          INTEGER NOT NULL REFERENCES usuarios(id),
        instituicao         TEXT NOT NULL,
        tipo                TEXT NOT NULL,
        saldo               REAL NOT NULL,
        atualizado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS pagamentos_programaveis (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id          INTEGER NOT NULL REFERENCES usuarios(id),
        descricao           TEXT NOT NULL,
        destinatario        TEXT NOT NULL,
        valor               REAL NOT NULL,
        condicao_tipo       TEXT NOT NULL,
        condicao_valor      TEXT NOT NULL,
        status              TEXT NOT NULL DEFAULT 'pendente',
        criado_em           TEXT DEFAULT (datetime('now')),
        executado_em        TEXT,
        codigo_transacao    TEXT
    );

    CREATE TABLE IF NOT EXISTS ai_agentes_tarefas (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id          INTEGER NOT NULL REFERENCES usuarios(id),
        tipo                TEXT NOT NULL,
        entrada_json        TEXT,
        resultado_json      TEXT,
        status              TEXT NOT NULL DEFAULT 'concluida',
        criado_em           TEXT DEFAULT (datetime('now')),
        finalizado_em       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS sessoes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
        token       TEXT UNIQUE NOT NULL,
        expira_em   TEXT NOT NULL,
        criado_em   TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS notificacoes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
        titulo      TEXT NOT NULL,
        mensagem    TEXT NOT NULL,
        tipo        TEXT DEFAULT 'info',
        lida        INTEGER DEFAULT 0,
        criado_em   TEXT DEFAULT (datetime('now'))
    );
    """)
    # Migração leve para bases já existentes.
    auto_cols = {r['name'] for r in conn.execute("PRAGMA table_info(automacao_config)").fetchall()}
    if 'dashboard_ordem_ativa' not in auto_cols:
        conn.execute("ALTER TABLE automacao_config ADD COLUMN dashboard_ordem_ativa INTEGER NOT NULL DEFAULT 0")
    if 'dashboard_ordem_widgets' not in auto_cols:
        conn.execute("ALTER TABLE automacao_config ADD COLUMN dashboard_ordem_widgets TEXT")

    gastos_cols = {r['name'] for r in conn.execute("PRAGMA table_info(gastos_categorias)").fetchall()}
    if 'transacao_codigo' not in gastos_cols:
        conn.execute("ALTER TABLE gastos_categorias ADD COLUMN transacao_codigo TEXT")
    if 'atualizado_em' not in gastos_cols:
        conn.execute("ALTER TABLE gastos_categorias ADD COLUMN atualizado_em TEXT")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS orcamentos_categorias (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               conta_id INTEGER NOT NULL REFERENCES contas(id),
               categoria TEXT NOT NULL,
               limite_mensal REAL NOT NULL,
               mes_ref TEXT NOT NULL,
               criado_em TEXT DEFAULT (datetime('now')),
               UNIQUE(conta_id, categoria, mes_ref)
           )"""
    )

    conn.commit()
    conn.close()
    garantir_conta_demo()

# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def hash_senha(senha, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', senha.encode(), salt.encode(), 100000)
    return h.hex(), salt

def verificar_senha(senha, hash_stored, salt):
    h, _ = hash_senha(senha, salt)
    return hmac.compare_digest(h, hash_stored)

def criar_token(usuario_id):
    token = secrets.token_urlsafe(32)
    expira = (datetime.now() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    conn.execute("INSERT INTO sessoes (usuario_id, token, expira_em) VALUES (?,?,?)",
                 (usuario_id, token, expira))
    conn.commit()
    conn.close()
    return token

def verificar_token(token):
    if not token:
        return None
    conn = get_db()
    row = conn.execute("""
        SELECT s.usuario_id, u.nome, u.email, u.cpf
        FROM sessoes s JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.token=? AND s.expira_em > datetime('now') AND u.ativo=1
    """, (token,)).fetchone()
    conn.close()
    return dict(row) if row else None

def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        user = verificar_token(token)
        if not user:
            return jsonify({'erro': 'Não autorizado'}), 401
        request.user = user
        return f(*args, **kwargs)
    return wrapper

def gerar_numero_conta():
    return ''.join([str(secrets.randbelow(10)) for _ in range(8)])

def gerar_numero_cartao():
    return ' '.join([''.join([str(secrets.randbelow(10)) for _ in range(4)]) for _ in range(4)])

def gerar_codigo_transacao():
    return secrets.token_hex(16).upper()

def gerar_linha_digitavel():
    blocos = [
        ''.join([str(secrets.randbelow(10)) for _ in range(5)]),
        ''.join([str(secrets.randbelow(10)) for _ in range(5)]),
        ''.join([str(secrets.randbelow(10)) for _ in range(5)]),
        ''.join([str(secrets.randbelow(10)) for _ in range(6)]),
    ]
    return '.'.join(blocos)

def adicionar_notificacao(conn, usuario_id, titulo, mensagem, tipo='info'):
    conn.execute(
        "INSERT INTO notificacoes (usuario_id, titulo, mensagem, tipo) VALUES (?,?,?,?)",
        (usuario_id, titulo, mensagem, tipo)
    )

def registrar_lancamento(conn, conta_id, tipo, direcao, valor, saldo_antes, saldo_depois, descricao='', transacao_codigo=None):
    conn.execute(
        """INSERT INTO ledger_lancamentos
           (conta_id, transacao_codigo, tipo, direcao, valor, saldo_antes, saldo_depois, descricao)
           VALUES (?,?,?,?,?,?,?,?)""",
        (conta_id, transacao_codigo, tipo, direcao, valor, saldo_antes, saldo_depois, descricao)
    )

def requer_otp(valor, limiar=500.0):
    return float(valor or 0) >= float(limiar)

def calcular_score_risco(conn, usuario_id):
    conta = conn.execute("SELECT id FROM contas WHERE usuario_id=?", (usuario_id,)).fetchone()
    if not conta:
        return {'score': 0, 'nivel': 'baixo', 'fatores': []}

    cid = conta['id']
    fatores = []
    score = 0

    saidas = conn.execute(
        """SELECT COALESCE(AVG(valor),0) FROM transacoes
           WHERE conta_origem=? AND criado_em > datetime('now', '-30 days')""",
        (cid,)
    ).fetchone()[0] or 0

    maior_saida = conn.execute(
        """SELECT COALESCE(MAX(valor),0) FROM transacoes
           WHERE conta_origem=? AND criado_em > datetime('now', '-7 days')""",
        (cid,)
    ).fetchone()[0] or 0

    destinos_novos = conn.execute(
        """SELECT COUNT(*) FROM (
             SELECT conta_destino, MIN(criado_em) as primeiro
             FROM transacoes
             WHERE conta_origem=? AND conta_destino IS NOT NULL
             GROUP BY conta_destino
           ) x
           WHERE primeiro > datetime('now', '-7 days')""",
        (cid,)
    ).fetchone()[0] or 0

    boletos_atrasados = conn.execute(
        "SELECT COUNT(*) FROM boletos WHERE conta_id=? AND status='atrasado'",
        (cid,)
    ).fetchone()[0] or 0

    if maior_saida > max(1000.0, float(saidas) * 4):
        score += 35
        fatores.append('pico_de_saida')
    if destinos_novos >= 2:
        score += 25
        fatores.append('destinos_novos_recentes')
    if boletos_atrasados >= 2:
        score += 20
        fatores.append('inadimplencia_curto_prazo')
    hora = datetime.now().hour
    if hora < 6 or hora >= 23:
        score += 10
        fatores.append('janela_horaria_sensivel')

    score = min(100, int(score))
    nivel = 'baixo' if score < 40 else ('medio' if score < 70 else 'alto')
    return {'score': score, 'nivel': nivel, 'fatores': fatores}

def limiar_otp_dinamico(conn, usuario_id):
    risco = calcular_score_risco(conn, usuario_id)
    score = int(risco['score'])
    if score >= 70:
        return 100.0
    if score >= 40:
        return 300.0
    return 500.0

def criar_desafio_otp(conn, usuario_id, acao, ttl_min=5):
    codigo = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    codigo_hash, salt = hash_senha(codigo)
    expira = (datetime.utcnow() + timedelta(minutes=ttl_min)).strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        """INSERT INTO desafios_otp (usuario_id, acao, codigo_hash, salt, expira_em)
           VALUES (?,?,?,?,?)""",
        (usuario_id, acao, codigo_hash, salt, expira)
    )
    return codigo, expira

def validar_desafio_otp(conn, usuario_id, acao, codigo):
    row = conn.execute(
        """SELECT * FROM desafios_otp
           WHERE usuario_id=? AND acao=? AND usado=0 AND expira_em > datetime('now')
           ORDER BY id DESC LIMIT 1""",
        (usuario_id, acao)
    ).fetchone()
    if not row:
        return False, 'Nenhum OTP válido encontrado. Solicite um novo código.'

    if int(row['tentativas']) >= int(row['max_tentativas']):
        return False, 'OTP bloqueado por excesso de tentativas.'

    if not verificar_senha(codigo, row['codigo_hash'], row['salt']):
        conn.execute("UPDATE desafios_otp SET tentativas=tentativas+1 WHERE id=?", (row['id'],))
        return False, 'Código OTP inválido.'

    conn.execute("UPDATE desafios_otp SET usado=1 WHERE id=?", (row['id'],))
    return True, None

def obter_ou_criar_fatura(conn, cartao_id):
    hoje = datetime.now()
    mes_ref = hoje.strftime('%Y-%m')
    fatura = conn.execute(
        "SELECT * FROM faturas_cartao WHERE cartao_id=? AND mes_ref=?",
        (cartao_id, mes_ref)
    ).fetchone()
    if fatura:
        return fatura

    fechamento = hoje.replace(day=25).strftime('%Y-%m-%d')
    vencimento = (hoje.replace(day=25) + timedelta(days=10)).strftime('%Y-%m-%d')
    conn.execute(
        """INSERT INTO faturas_cartao (cartao_id, mes_ref, fechamento_em, vencimento_em)
           VALUES (?,?,?,?)""",
        (cartao_id, mes_ref, fechamento, vencimento)
    )
    return conn.execute(
        "SELECT * FROM faturas_cartao WHERE cartao_id=? AND mes_ref=?",
        (cartao_id, mes_ref)
    ).fetchone()

def obter_ou_criar_fatura_mes(conn, cartao_id, mes_ref):
    fatura = conn.execute(
        "SELECT * FROM faturas_cartao WHERE cartao_id=? AND mes_ref=?",
        (cartao_id, mes_ref)
    ).fetchone()
    if fatura:
        return fatura

    ano, mes = [int(x) for x in mes_ref.split('-')]
    fechamento_em = f"{ano:04d}-{mes:02d}-25"
    if mes == 12:
        venc_ano, venc_mes = ano + 1, 1
    else:
        venc_ano, venc_mes = ano, mes + 1
    vencimento_em = f"{venc_ano:04d}-{venc_mes:02d}-10"

    conn.execute(
        """INSERT INTO faturas_cartao (cartao_id, mes_ref, fechamento_em, vencimento_em)
           VALUES (?,?,?,?)""",
        (cartao_id, mes_ref, fechamento_em, vencimento_em)
    )
    return conn.execute(
        "SELECT * FROM faturas_cartao WHERE cartao_id=? AND mes_ref=?",
        (cartao_id, mes_ref)
    ).fetchone()

def mes_ref_add(mes_ref, offset):
    ano, mes = [int(x) for x in mes_ref.split('-')]
    total = (ano * 12 + (mes - 1)) + int(offset)
    novo_ano = total // 12
    novo_mes = (total % 12) + 1
    return f"{novo_ano:04d}-{novo_mes:02d}"

def recalcular_fatura(conn, fatura_id):
    total = conn.execute(
        "SELECT COALESCE(SUM(valor_parcela),0) FROM parcelas_compra_cartao WHERE fatura_id=?",
        (fatura_id,)
    ).fetchone()[0] or 0
    fatura = conn.execute("SELECT valor_pago FROM faturas_cartao WHERE id=?", (fatura_id,)).fetchone()
    valor_pago = float(fatura['valor_pago']) if fatura else 0.0
    aberto = max(0.0, float(total) - valor_pago)
    valor_minimo = round(aberto * 0.15, 2)
    status = 'paga' if aberto <= 0.001 else 'aberta'
    conn.execute(
        "UPDATE faturas_cartao SET total_fatura=?, valor_minimo=?, status=? WHERE id=?",
        (float(total), valor_minimo, status, fatura_id)
    )

def processar_pix_agendamentos(conn, usuario_id=None):
    processados = 0
    falhas = 0
    params = []
    query = """SELECT * FROM pix_agendamentos
               WHERE status='pendente' AND data_execucao <= datetime('now')"""
    if usuario_id is not None:
        query += " AND usuario_id=?"
        params.append(usuario_id)
    query += " ORDER BY data_execucao ASC"

    rows = conn.execute(query, params).fetchall()
    for ag in rows:
        try:
            conta_orig = conn.execute("SELECT * FROM contas WHERE id=? AND status='ativa'", (ag['conta_id'],)).fetchone()
            if not conta_orig:
                raise ValueError('Conta de origem não encontrada')

            valor = float(ag['valor'])
            chave = ag['chave']
            if valor > conta_orig['saldo'] + conta_orig['limite_cheque']:
                raise ValueError('Saldo insuficiente no momento da execução')

            pix = conn.execute(
                """SELECT p.*, c.id as cid, c.saldo, c.usuario_id as uid_dest, u.nome
                   FROM pix_chaves p
                   JOIN contas c ON p.conta_id = c.id
                   JOIN usuarios u ON c.usuario_id = u.id
                   WHERE p.chave=? AND p.ativa=1""",
                (chave,)
            ).fetchone()
            if not pix:
                raise ValueError('Chave PIX não encontrada')
            if pix['cid'] == conta_orig['id']:
                raise ValueError('Não é possível enviar PIX para si mesmo')

            codigo = gerar_codigo_transacao()
            conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta_orig['id']))
            conn.execute("UPDATE contas SET saldo = saldo + ? WHERE id=?", (valor, pix['cid']))
            conn.execute(
                """INSERT INTO transacoes (conta_origem, conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                   VALUES (?,?,'pix',?,?,?,?,?)""",
                (conta_orig['id'], pix['cid'], valor,
                 ag['descricao'] or f'PIX agendado para {chave}',
                 conta_orig['saldo'], conta_orig['saldo'] - valor, codigo)
            )
            registrar_lancamento(
                conn, conta_orig['id'], 'pix_agendado', 'debito', valor,
                conta_orig['saldo'], conta_orig['saldo'] - valor, ag['descricao'] or f'PIX agendado para {chave}', codigo
            )
            registrar_lancamento(
                conn, pix['cid'], 'pix_agendado', 'credito', valor,
                pix['saldo'], pix['saldo'] + valor, 'Recebimento de PIX agendado', codigo
            )

            conn.execute(
                """UPDATE pix_agendamentos
                   SET status='executado', codigo_transacao=?, processado_em=datetime('now')
                   WHERE id=?""",
                (codigo, ag['id'])
            )
            adicionar_notificacao(conn, ag['usuario_id'], '✅ PIX agendado executado', f'PIX de R${valor:.2f} foi executado com sucesso.', 'sucesso')
            processados += 1
        except Exception as e:
            conn.execute(
                """UPDATE pix_agendamentos
                   SET status='erro', erro=?, processado_em=datetime('now')
                   WHERE id=?""",
                (str(e), ag['id'])
            )
            falhas += 1

    return {'processados': processados, 'falhas': falhas}

def processar_faturas_rotativo(conn, usuario_id=None, taxa_rotativo=0.099):
    atualizadas = 0
    params = []
    query = """SELECT f.*, co.usuario_id
               FROM faturas_cartao f
               JOIN cartoes ca ON f.cartao_id = ca.id
               JOIN contas co ON ca.conta_id = co.id
               WHERE f.status IN ('aberta','parcial')
                 AND f.vencimento_em IS NOT NULL
                 AND date(f.vencimento_em) < date('now')"""
    if usuario_id is not None:
        query += " AND co.usuario_id=?"
        params.append(usuario_id)

    rows = conn.execute(query, params).fetchall()
    for f in rows:
        aberto = max(0.0, float(f['total_fatura']) - float(f['valor_pago']))
        if aberto <= 0:
            continue
        juros = round(aberto * taxa_rotativo, 2)
        novo_total = float(f['total_fatura']) + juros
        novo_minimo = round(max(0.0, novo_total - float(f['valor_pago'])) * 0.15, 2)

        conn.execute(
            """UPDATE faturas_cartao
               SET total_fatura=?, valor_minimo=?, status='atrasada'
               WHERE id=?""",
            (novo_total, novo_minimo, f['id'])
        )
        adicionar_notificacao(
            conn,
            f['usuario_id'],
            '⚠️ Juros rotativo aplicado',
            f'Foi aplicado R${juros:.2f} de juros rotativo na sua fatura em atraso.',
            'alerta'
        )
        atualizadas += 1

    return {'faturas_atualizadas': atualizadas}

def processar_fechamento_faturas(conn, usuario_id=None):
    hoje_mes = datetime.now().strftime('%Y-%m')
    faturadas = 0

    params = []
    query = """SELECT ca.id as cartao_id, co.usuario_id
               FROM cartoes ca
               JOIN contas co ON ca.conta_id = co.id
               WHERE ca.tipo='credito' AND ca.status='ativo'"""
    if usuario_id is not None:
        query += " AND co.usuario_id=?"
        params.append(usuario_id)

    cartoes = conn.execute(query, params).fetchall()
    for c in cartoes:
        cartao_id = c['cartao_id']
        obter_ou_criar_fatura_mes(conn, cartao_id, hoje_mes)
        rows = conn.execute(
            """SELECT * FROM parcelas_compra_cartao
               WHERE cartao_id=? AND fatura_id IS NULL AND mes_ref <= ?
               ORDER BY mes_ref ASC, numero_parcela ASC""",
            (cartao_id, hoje_mes)
        ).fetchall()

        faturas_tocadas = set()
        for p in rows:
            fatura_mes = obter_ou_criar_fatura_mes(conn, cartao_id, p['mes_ref'])
            conn.execute(
                "UPDATE parcelas_compra_cartao SET fatura_id=?, status='faturada' WHERE id=?",
                (fatura_mes['id'], p['id'])
            )
            faturas_tocadas.add(fatura_mes['id'])
            faturadas += 1

        for fid in faturas_tocadas:
            recalcular_fatura(conn, fid)

    return {'parcelas_faturadas': faturadas}

def processar_boletos_atrasados(conn, usuario_id=None):
    atualizados = 0
    params = []
    query = """SELECT b.*, co.usuario_id
               FROM boletos b
               JOIN contas co ON b.conta_id = co.id
               WHERE b.status IN ('pendente', 'atrasado')
                 AND date(b.vencimento_em) < date('now')"""
    if usuario_id is not None:
        query += " AND co.usuario_id=?"
        params.append(usuario_id)

    rows = conn.execute(query, params).fetchall()
    hoje = datetime.now().date()
    for b in rows:
        try:
            venc = datetime.strptime((b['vencimento_em'] or '')[:10], '%Y-%m-%d').date()
        except ValueError:
            continue

        dias_atraso = (hoje - venc).days
        if dias_atraso <= 0:
            continue

        dias_aplicados = int(b['dias_atraso_aplicados'] or 0)
        dias_novos = max(0, dias_atraso - dias_aplicados)
        if dias_novos == 0 and b['status'] == 'atrasado':
            continue

        valor_original = float(b['valor_original'])
        valor_atual = float(b['valor_atual'])

        if dias_aplicados == 0:
            valor_atual += valor_original * (float(b['multa_percentual']) / 100.0)

        juros_dia = (float(b['juros_mensal']) / 100.0) / 30.0
        if dias_novos > 0 and juros_dia > 0:
            valor_atual += valor_original * juros_dia * dias_novos

        valor_atual = round(valor_atual, 2)
        conn.execute(
            """UPDATE boletos
               SET valor_atual=?, dias_atraso_aplicados=?, status='atrasado'
               WHERE id=?""",
            (valor_atual, dias_atraso, b['id'])
        )
        atualizados += 1

    return {'boletos_atualizados': atualizados}

def obter_ou_criar_automacao_config(conn, usuario_id):
    row = conn.execute("SELECT * FROM automacao_config WHERE usuario_id=?", (usuario_id,)).fetchone()
    if row:
        return row
    conn.execute(
        """INSERT INTO automacao_config
           (usuario_id, sweep_ativo, sweep_min_reserva, sweep_percentual_excesso, prevencao_descoberto_ativa, limite_alerta, tom_comunicacao, dashboard_ordem_ativa, dashboard_ordem_widgets)
           VALUES (?,0,500,0.3,1,100,'neutro',0,NULL)""",
        (usuario_id,)
    )
    return conn.execute("SELECT * FROM automacao_config WHERE usuario_id=?", (usuario_id,)).fetchone()

def obter_ou_criar_reserva(conn, usuario_id):
    row = conn.execute("SELECT * FROM reserva_liquidez WHERE usuario_id=?", (usuario_id,)).fetchone()
    if row:
        return row
    conn.execute("INSERT INTO reserva_liquidez (usuario_id, saldo_reserva) VALUES (?,0)", (usuario_id,))
    return conn.execute("SELECT * FROM reserva_liquidez WHERE usuario_id=?", (usuario_id,)).fetchone()

def calcular_obrigacoes_curto_prazo(conn, conta_id, dias=7):
    boletos = conn.execute(
        """SELECT COALESCE(SUM(valor_atual),0)
           FROM boletos
           WHERE conta_id=? AND status IN ('pendente','atrasado')
             AND date(vencimento_em) <= date('now', ?)""",
        (conta_id, f'+{int(dias)} days')
    ).fetchone()[0] or 0

    dividas = conn.execute(
        """SELECT COALESCE(SUM(valor_parcela),0)
           FROM dividas
           WHERE conta_id=? AND status='ativa'
             AND (vencimento IS NULL OR date(vencimento) <= date('now', ?))""",
        (conta_id, f'+{int(dias)} days')
    ).fetchone()[0] or 0

    faturas = conn.execute(
        """SELECT COALESCE(SUM(MAX(0,total_fatura - valor_pago)),0)
           FROM faturas_cartao f
           JOIN cartoes c ON f.cartao_id = c.id
           WHERE c.conta_id=? AND f.status IN ('aberta','parcial','atrasada')
             AND f.vencimento_em IS NOT NULL
             AND date(f.vencimento_em) <= date('now', ?)""",
        (conta_id, f'+{int(dias)} days')
    ).fetchone()[0] or 0

    return float(boletos) + float(dividas) + float(faturas)

def executar_prevencao_descoberto(conn, usuario_id):
    cfg = obter_ou_criar_automacao_config(conn, usuario_id)
    if not int(cfg['prevencao_descoberto_ativa'] or 0):
        return {'acionado': False, 'valor_transferido': 0.0, 'motivo': 'prevencao_desativada'}

    conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (usuario_id,)).fetchone()
    if not conta:
        return {'acionado': False, 'valor_transferido': 0.0, 'motivo': 'conta_nao_encontrada'}

    reserva = obter_ou_criar_reserva(conn, usuario_id)
    obrigacoes = calcular_obrigacoes_curto_prazo(conn, conta['id'], dias=7)
    limite_alerta = float(cfg['limite_alerta'])
    saldo_previsto = float(conta['saldo']) - obrigacoes

    if saldo_previsto >= limite_alerta:
        return {'acionado': False, 'valor_transferido': 0.0, 'motivo': 'saldo_previsto_ok', 'saldo_previsto': round(saldo_previsto, 2)}

    necessidade = min(float(reserva['saldo_reserva']), max(0.0, limite_alerta - saldo_previsto))
    if necessidade <= 0:
        return {'acionado': False, 'valor_transferido': 0.0, 'motivo': 'sem_reserva_disponivel', 'saldo_previsto': round(saldo_previsto, 2)}

    novo_saldo = float(conta['saldo']) + necessidade
    novo_reserva = float(reserva['saldo_reserva']) - necessidade
    codigo = gerar_codigo_transacao()
    conn.execute("UPDATE contas SET saldo=? WHERE id=?", (novo_saldo, conta['id']))
    conn.execute("UPDATE reserva_liquidez SET saldo_reserva=?, atualizado_em=datetime('now') WHERE usuario_id=?", (novo_reserva, usuario_id))
    conn.execute(
        """INSERT INTO transacoes (conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
           VALUES (?,?,?,?,?,?,?)""",
        (conta['id'], 'prevencao_descoberto', necessidade, 'Transferência automática da reserva de liquidez', conta['saldo'], novo_saldo, codigo)
    )
    registrar_lancamento(
        conn, conta['id'], 'prevencao_descoberto', 'credito', necessidade,
        conta['saldo'], novo_saldo, 'Transferência automática da reserva de liquidez', codigo
    )
    adicionar_notificacao(conn, usuario_id, '🛡️ Prevenção de descoberto acionada', f'Reserva transferiu R${necessidade:.2f} para evitar saldo baixo projetado.', 'info')
    return {'acionado': True, 'valor_transferido': round(necessidade, 2), 'saldo_previsto': round(saldo_previsto, 2)}

def executar_smart_sweep(conn, usuario_id):
    cfg = obter_ou_criar_automacao_config(conn, usuario_id)
    if not int(cfg['sweep_ativo'] or 0):
        return {'executado': False, 'valor_investido': 0.0, 'motivo': 'sweep_desativado'}

    conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (usuario_id,)).fetchone()
    if not conta:
        return {'executado': False, 'valor_investido': 0.0, 'motivo': 'conta_nao_encontrada'}

    obrigacoes = calcular_obrigacoes_curto_prazo(conn, conta['id'], dias=15)
    min_reserva = float(cfg['sweep_min_reserva'])
    percentual = min(1.0, max(0.05, float(cfg['sweep_percentual_excesso'] or 0.3)))
    excesso = float(conta['saldo']) - (obrigacoes + min_reserva)
    valor = round(max(0.0, excesso * percentual), 2)

    if valor < 10:
        return {'executado': False, 'valor_investido': 0.0, 'motivo': 'sem_excesso_seguro'}

    saldo_novo = float(conta['saldo']) - valor
    vencimento = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    codigo = gerar_codigo_transacao()

    conn.execute("UPDATE contas SET saldo=? WHERE id=?", (saldo_novo, conta['id']))
    conn.execute(
        """INSERT INTO investimentos (conta_id, tipo, valor_inicial, valor_atual, taxa_anual, data_vencimento)
           VALUES (?,?,?,?,?,?)""",
        (conta['id'], 'SWEEP_CDB', valor, valor, 11.0, vencimento)
    )
    conn.execute(
        """INSERT INTO transacoes (conta_origem, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
           VALUES (?,?,?,?,?,?,?)""",
        (conta['id'], 'sweep_investimento', valor, 'Aplicação automática Smart Sweep', conta['saldo'], saldo_novo, codigo)
    )
    registrar_lancamento(
        conn, conta['id'], 'sweep_investimento', 'debito', valor,
        conta['saldo'], saldo_novo, 'Aplicação automática Smart Sweep', codigo
    )
    adicionar_notificacao(conn, usuario_id, '🤖 Smart Sweep executado', f'R${valor:.2f} investidos automaticamente com reserva de segurança mantida.', 'sucesso')
    return {'executado': True, 'valor_investido': round(valor, 2), 'obrigacoes_15d': round(obrigacoes, 2)}

def processar_pagamentos_programaveis(conn, usuario_id=None):
    params = []
    q = "SELECT * FROM pagamentos_programaveis WHERE status='pendente'"
    if usuario_id is not None:
        q += " AND usuario_id=?"
        params.append(usuario_id)
    rows = conn.execute(q, params).fetchall()

    executados = 0
    falhas = 0
    for row in rows:
        uid = row['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta:
            falhas += 1
            continue

        cond_ok = False
        if row['condicao_tipo'] == 'data':
            try:
                data_alvo = datetime.strptime((row['condicao_valor'] or '')[:10], '%Y-%m-%d').date()
                cond_ok = datetime.now().date() >= data_alvo
            except ValueError:
                cond_ok = False
        elif row['condicao_tipo'] == 'saldo_minimo':
            try:
                minimo = float(row['condicao_valor'])
                cond_ok = float(conta['saldo']) >= minimo
            except (TypeError, ValueError):
                cond_ok = False

        if not cond_ok:
            continue

        valor = float(row['valor'])
        if valor <= 0 or valor > float(conta['saldo']) + float(conta['limite_cheque']):
            falhas += 1
            continue

        saldo_novo = float(conta['saldo']) - valor
        codigo = gerar_codigo_transacao()
        conn.execute("UPDATE contas SET saldo=? WHERE id=?", (saldo_novo, conta['id']))
        conn.execute(
            """INSERT INTO transacoes (conta_origem, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
               VALUES (?,?,?,?,?,?,?)""",
            (conta['id'], 'pagamento_programavel', valor, row['descricao'], conta['saldo'], saldo_novo, codigo)
        )
        conn.execute(
            "UPDATE pagamentos_programaveis SET status='executado', executado_em=datetime('now'), codigo_transacao=? WHERE id=?",
            (codigo, row['id'])
        )
        registrar_lancamento(
            conn, conta['id'], 'pagamento_programavel', 'debito', valor,
            conta['saldo'], saldo_novo, row['descricao'], codigo
        )
        adicionar_notificacao(conn, uid, '🧩 Pagamento programável executado', f'{row["descricao"]} no valor de R${valor:.2f} foi liquidado automaticamente.', 'sucesso')
        executados += 1

    return {'programaveis_executados': executados, 'programaveis_falhas': falhas}

def decidir_cenario_ux(conn, usuario_id):
    cfg = obter_ou_criar_automacao_config(conn, usuario_id)
    if cfg['cenario_forcado']:
        return cfg['cenario_forcado']

    conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (usuario_id,)).fetchone()
    if not conta:
        return 'padrao'

    hoje = datetime.now().day
    conta_id = conta['id']
    vencendo = conn.execute(
        """SELECT COUNT(*) FROM boletos
           WHERE conta_id=? AND status IN ('pendente','atrasado')
             AND date(vencimento_em) <= date('now', '+5 days')""",
        (conta_id,)
    ).fetchone()[0]

    if vencendo > 0 or (1 <= hoje <= 10):
        return 'pagamento_contas'
    if float(conta['saldo']) > 5000:
        return 'acumular_investir'
    return 'padrao'

def executar_agente_autonomo(conn, usuario_id, tipo, entrada):
    resultado = {}
    if tipo == 'contestar_cobranca':
        codigo = gerar_codigo_transacao()[:10]
        resultado = {
            'protocolo': f'CTX-{codigo}',
            'status': 'aberta',
            'etapas': ['coleta_evidencias', 'analise_transacao', 'abertura_contestacao'],
            'mensagem': 'Contestação aberta automaticamente e enviada para análise.'
        }
        adicionar_notificacao(conn, usuario_id, '🧾 Contestação iniciada por IA', 'A contestação foi aberta automaticamente com protocolo gerado.', 'info')
    elif tipo == 'investigar_fatura':
        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=?", (usuario_id,)).fetchone()
        analise = {'achados': [], 'risco': 'baixo'}
        if conta:
            parcela = conn.execute(
                """SELECT p.valor_parcela, c.descricao, p.mes_ref
                   FROM parcelas_compra_cartao p
                   JOIN compras_cartao c ON p.compra_id=c.id
                   JOIN cartoes ca ON p.cartao_id=ca.id
                   WHERE ca.conta_id=?
                   ORDER BY p.valor_parcela DESC LIMIT 1""",
                (conta['id'],)
            ).fetchone()
            if parcela:
                analise['achados'].append(f"Maior parcela encontrada: {parcela['descricao']} em {parcela['mes_ref']} (R${float(parcela['valor_parcela']):.2f})")
                analise['risco'] = 'medio' if float(parcela['valor_parcela']) > 800 else 'baixo'
        resultado = {
            'status': 'concluida',
            'analise': analise,
            'mensagem': 'Investigação concluída com recomendações de monitoramento.'
        }
    else:
        resultado = {
            'status': 'concluida',
            'mensagem': 'Fluxo orquestrado de abertura concluído com validações simuladas.',
            'checklist': ['captura_documentos', 'validacao_identidade', 'abertura_conta', 'boas_vindas']
        }

    conn.execute(
        """INSERT INTO ai_agentes_tarefas (usuario_id, tipo, entrada_json, resultado_json, status)
           VALUES (?,?,?,?,?)""",
        (usuario_id, tipo, json.dumps(entrada or {}, ensure_ascii=False), json.dumps(resultado, ensure_ascii=False), 'concluida')
    )
    return resultado

def parse_json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None

def garantir_conta_demo():
    conn = get_db()
    try:
        senha_hash, salt = hash_senha('demo123')
        conn.execute("""INSERT OR IGNORE INTO usuarios (cpf, nome, email, telefone, senha_hash, salt, ativo)
                        VALUES (?,?,?,?,?,?,1)""",
                     ('12345678901', 'Usuário Demo', 'demo@neobank.com', '11999999999', senha_hash, salt))

        user = conn.execute("SELECT id FROM usuarios WHERE email=?", ('demo@neobank.com',)).fetchone()
        uid = user['id']
        conn.execute("""UPDATE usuarios SET nome=?, telefone=?, senha_hash=?, salt=?, ativo=1
                        WHERE id=?""",
                     ('Usuário Demo', '11999999999', senha_hash, salt, uid))

        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=? LIMIT 1", (uid,)).fetchone()
        if conta:
            conta_id = conta['id']
        else:
            numero = gerar_numero_conta()
            while conn.execute("SELECT id FROM contas WHERE numero=?", (numero,)).fetchone():
                numero = gerar_numero_conta()
            c = conn.cursor()
            c.execute("""INSERT INTO contas (usuario_id, numero, tipo, saldo, limite_cheque)
                         VALUES (?,?,'corrente', 1000.0, 500.0)""", (uid, numero))
            conta_id = c.lastrowid
            c.execute("""INSERT INTO transacoes (conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                         VALUES (?,?,?,?,?,?,?)""",
                      (conta_id, 'deposito', 1000.0, 'Saldo inicial da conta demo', 0.0, 1000.0, gerar_codigo_transacao()))
            registrar_lancamento(
                conn, conta_id, 'deposito', 'credito', 1000.0, 0.0, 1000.0,
                'Saldo inicial da conta demo'
            )

        cartao = conn.execute("SELECT id FROM cartoes WHERE conta_id=? LIMIT 1", (conta_id,)).fetchone()
        if not cartao:
            num_cartao = gerar_numero_cartao()
            cvv = ''.join([str(secrets.randbelow(10)) for _ in range(3)])
            validade = (datetime.now() + timedelta(days=365*4)).strftime('%m/%Y')
            conn.execute("""INSERT INTO cartoes (conta_id, numero, cvv, validade, tipo)
                            VALUES (?,?,?,?,'debito')""", (conta_id, num_cartao, cvv, validade))

        for tipo, chave in [('cpf', '12345678901'), ('email', 'demo@neobank.com')]:
            existe = conn.execute("SELECT id FROM pix_chaves WHERE chave=? AND ativa=1", (chave,)).fetchone()
            if not existe:
                conn.execute("""INSERT INTO pix_chaves (conta_id, tipo, chave)
                                VALUES (?,?,?)""", (conta_id, tipo, chave))

        adicionar_notificacao(conn, uid, 'Conta demo pronta',
            'Use demo@neobank.com / demo123 para testar o NeoBank.', 'info')

        conn.commit()
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: AUTENTICAÇÃO
# ─────────────────────────────────────────────

@app.route('/api/cadastro', methods=['POST'])
def cadastro():
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    campos = ['cpf', 'nome', 'email', 'senha']
    if not all(d.get(c) for c in campos):
        return jsonify({'erro': 'Campos obrigatórios: cpf, nome, email, senha'}), 400

    cpf = re.sub(r'\D', '', d['cpf'])
    if len(cpf) != 11:
        return jsonify({'erro': 'CPF inválido'}), 400

    senha_hash, salt = hash_senha(d['senha'])
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute("""INSERT INTO usuarios (cpf, nome, email, telefone, senha_hash, salt)
                     VALUES (?,?,?,?,?,?)""",
                  (cpf, d['nome'], d['email'], d.get('telefone', ''), senha_hash, salt))
        uid = c.lastrowid

        # Criar conta corrente
        numero = gerar_numero_conta()
        while conn.execute("SELECT id FROM contas WHERE numero=?", (numero,)).fetchone():
            numero = gerar_numero_conta()

        c.execute("""INSERT INTO contas (usuario_id, numero, tipo, saldo, limite_cheque)
                     VALUES (?,?,'corrente', 0.0, 500.0)""", (uid, numero))
        conta_id = c.lastrowid

        # Criar cartão de débito
        num_cartao = gerar_numero_cartao()
        cvv = ''.join([str(secrets.randbelow(10)) for _ in range(3)])
        validade = (datetime.now() + timedelta(days=365*4)).strftime('%m/%Y')
        c.execute("""INSERT INTO cartoes (conta_id, numero, cvv, validade, tipo)
                     VALUES (?,?,?,?,'debito')""", (conta_id, num_cartao, cvv, validade))

        # Criar chave PIX (CPF)
        c.execute("""INSERT INTO pix_chaves (conta_id, tipo, chave)
                     VALUES (?,?,?)""", (conta_id, 'cpf', cpf))

        # Bônus de boas-vindas
        c.execute("""INSERT INTO transacoes (conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                     VALUES (?,?,?,?,?,?,?)""",
                  (conta_id, 'bonus', 100.0, 'Bônus de boas-vindas NeoBank!', 0.0, 100.0, gerar_codigo_transacao()))
        c.execute("UPDATE contas SET saldo = saldo + 100 WHERE id=?", (conta_id,))
        registrar_lancamento(
            conn, conta_id, 'bonus', 'credito', 100.0, 0.0, 100.0,
            'Bônus de boas-vindas'
        )

        adicionar_notificacao(conn, uid, '🎉 Bem-vindo ao NeoBank!',
            f'Sua conta foi criada. Número: {numero}. Você ganhou R$100 de bônus!', 'sucesso')

        conn.commit()
        token = criar_token(uid)
        return jsonify({
            'token': token,
            'usuario': {'id': uid, 'nome': d['nome'], 'email': d['email']},
            'conta': {'numero': numero, 'agencia': '0001'},
            'mensagem': 'Conta criada com R$100 de bônus!'
        }), 201
    except sqlite3.IntegrityError as e:
        return jsonify({'erro': 'CPF ou e-mail já cadastrado'}), 409
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    email = d.get('email', '')
    senha = d.get('senha', '')
    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE email=? AND ativo=1", (email,)).fetchone()
    conn.close()
    if not user or not verificar_senha(senha, user['senha_hash'], user['salt']):
        return jsonify({'erro': 'E-mail ou senha incorretos'}), 401
    token = criar_token(user['id'])
    return jsonify({'token': token, 'usuario': {'id': user['id'], 'nome': user['nome'], 'email': user['email']}})

@app.route('/api/logout', methods=['POST'])
@auth_required
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    conn = get_db()
    conn.execute("DELETE FROM sessoes WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return jsonify({'mensagem': 'Logout realizado'})

@app.route('/api/otp/solicitar', methods=['POST'])
@auth_required
def solicitar_otp():
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    acao = (d.get('acao') or '').strip()
    if not acao:
        return jsonify({'erro': 'Ação OTP é obrigatória'}), 400

    conn = get_db()
    try:
        uid = request.user['usuario_id']
        codigo, expira = criar_desafio_otp(conn, uid, acao)
        adicionar_notificacao(
            conn,
            uid,
            '🔐 Código OTP gerado',
            f'Seu código para {acao} é {codigo}. Expira em 5 minutos.',
            'info'
        )
        conn.commit()
        # Em simulador retornamos o código no payload para facilitar testes.
        return jsonify({'mensagem': 'OTP gerado com sucesso', 'acao': acao, 'expira_em': expira, 'codigo_simulado': codigo})
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: CONTA
# ─────────────────────────────────────────────

@app.route('/api/perfil', methods=['GET'])
@auth_required
def perfil():
    conn = get_db()
    uid = request.user['usuario_id']
    user = conn.execute("SELECT id, cpf, nome, email, telefone, criado_em FROM usuarios WHERE id=?", (uid,)).fetchone()
    contas = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchall()
    conn.close()
    return jsonify({
        'usuario': dict(user),
        'contas': [dict(c) for c in contas]
    })

@app.route('/api/saldo', methods=['GET'])
@auth_required
def saldo():
    conn = get_db()
    uid = request.user['usuario_id']
    contas = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchall()
    conn.close()
    return jsonify({'contas': [dict(c) for c in contas]})

@app.route('/api/extrato', methods=['GET'])
@auth_required
def extrato():
    conn = get_db()
    uid = request.user['usuario_id']
    conta = conn.execute("SELECT id FROM contas WHERE usuario_id=? LIMIT 1", (uid,)).fetchone()
    if not conta:
        conn.close()
        return jsonify({'transacoes': []})

    try:
        limit = int(request.args.get('limit', 30))
        offset = int(request.args.get('offset', 0))
    except (TypeError, ValueError):
        conn.close()
        return jsonify({'erro': 'Parâmetros de paginação inválidos'}), 400

    if limit < 1 or limit > 100 or offset < 0:
        conn.close()
        return jsonify({'erro': 'Use limit entre 1 e 100 e offset >= 0'}), 400

    tipo_filter = request.args.get('tipo', '')

    query = """
        SELECT t.*, 
               co.numero as num_origem,
               cd.numero as num_destino
        FROM transacoes t
        LEFT JOIN contas co ON t.conta_origem = co.id
        LEFT JOIN contas cd ON t.conta_destino = cd.id
        WHERE (t.conta_origem=? OR t.conta_destino=?)
    """
    params = [conta['id'], conta['id']]
    if tipo_filter:
        query += " AND t.tipo=?"
        params.append(tipo_filter)
    query += " ORDER BY t.criado_em DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    txs = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify({'transacoes': [dict(t) for t in txs]})

# ─────────────────────────────────────────────
# ROTAS: TRANSFERÊNCIAS
# ─────────────────────────────────────────────

@app.route('/api/transferencia', methods=['POST'])
@auth_required
def transferencia():
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    try:
        valor = float(d.get('valor', 0))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Valor inválido'}), 400

    if valor <= 0:
        return jsonify({'erro': 'Valor inválido'}), 400

    conn = get_db()
    try:
        uid = request.user['usuario_id']
        limiar = limiar_otp_dinamico(conn, uid)
        if requer_otp(valor, limiar=limiar):
            otp_codigo = (d.get('otp_codigo') or '').strip()
            if not otp_codigo:
                return jsonify({'erro': f'OTP obrigatório para transferências >= R${limiar:.0f}', 'requires_otp': True, 'acao_otp': 'transferencia', 'limiar_otp': limiar}), 428
            ok, msg = validar_desafio_otp(conn, uid, 'transferencia', otp_codigo)
            if not ok:
                conn.commit()
                return jsonify({'erro': msg}), 401

        conta_orig = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta_orig:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        saldo_disp = conta_orig['saldo'] + conta_orig['limite_cheque']
        if valor > saldo_disp:
            return jsonify({'erro': f'Saldo insuficiente. Disponível: R${saldo_disp:.2f}'}), 400

        destino_num = d.get('conta_destino', '').strip()
        conta_dest = conn.execute("SELECT c.*, u.nome FROM contas c JOIN usuarios u ON c.usuario_id=u.id WHERE c.numero=? AND c.status='ativa'", (destino_num,)).fetchone()
        if not conta_dest:
            return jsonify({'erro': 'Conta destino não encontrada'}), 404
        if conta_dest['id'] == conta_orig['id']:
            return jsonify({'erro': 'Não é possível transferir para a mesma conta'}), 400

        saldo_ant_orig = conta_orig['saldo']
        saldo_ant_dest = conta_dest['saldo']
        codigo = gerar_codigo_transacao()

        conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta_orig['id']))
        conn.execute("UPDATE contas SET saldo = saldo + ? WHERE id=?", (valor, conta_dest['id']))
        conn.execute("""INSERT INTO transacoes (conta_origem, conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                        VALUES (?,?,?,?,?,?,?,?)""",
                     (conta_orig['id'], conta_dest['id'], d.get('tipo', 'ted'),
                      valor, d.get('descricao', 'Transferência'),
                      saldo_ant_orig, saldo_ant_orig - valor, codigo))
        registrar_lancamento(
            conn, conta_orig['id'], d.get('tipo', 'ted'), 'debito', valor,
            saldo_ant_orig, saldo_ant_orig - valor, d.get('descricao', 'Transferência enviada'), codigo
        )
        registrar_lancamento(
            conn, conta_dest['id'], d.get('tipo', 'ted'), 'credito', valor,
            saldo_ant_dest, saldo_ant_dest + valor, d.get('descricao', 'Transferência recebida'), codigo
        )

        adicionar_notificacao(conn, uid, '💸 Transferência enviada',
            f'R${valor:.2f} enviado para {conta_dest["nome"]}', 'info')
        adicionar_notificacao(conn, conta_dest['usuario_id'], '💰 Transferência recebida',
            f'Você recebeu R${valor:.2f}', 'sucesso')

        conn.commit()
        return jsonify({
            'mensagem': 'Transferência realizada com sucesso',
            'codigo': codigo,
            'valor': valor,
            'destinatario': conta_dest['nome']
        })
    finally:
        conn.close()

@app.route('/api/pix/enviar', methods=['POST'])
@auth_required
def pix_enviar():
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    try:
        valor = float(d.get('valor', 0))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Valor inválido'}), 400

    chave = d.get('chave', '').strip()
    if valor <= 0 or not chave:
        return jsonify({'erro': 'Valor e chave PIX são obrigatórios'}), 400

    conn = get_db()
    try:
        uid = request.user['usuario_id']
        limiar = limiar_otp_dinamico(conn, uid)
        if requer_otp(valor, limiar=limiar):
            otp_codigo = (d.get('otp_codigo') or '').strip()
            if not otp_codigo:
                return jsonify({'erro': f'OTP obrigatório para PIX >= R${limiar:.0f}', 'requires_otp': True, 'acao_otp': 'pix', 'limiar_otp': limiar}), 428
            ok, msg = validar_desafio_otp(conn, uid, 'pix', otp_codigo)
            if not ok:
                conn.commit()
                return jsonify({'erro': msg}), 401

        conta_orig = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta_orig:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if valor > conta_orig['saldo'] + conta_orig['limite_cheque']:
            return jsonify({'erro': 'Saldo insuficiente'}), 400

        pix = conn.execute("""
            SELECT p.*, c.id as cid, c.saldo, c.usuario_id as uid_dest, u.nome
            FROM pix_chaves p
            JOIN contas c ON p.conta_id = c.id
            JOIN usuarios u ON c.usuario_id = u.id
            WHERE p.chave=? AND p.ativa=1
        """, (chave,)).fetchone()

        if not pix:
            return jsonify({'erro': 'Chave PIX não encontrada'}), 404
        if pix['cid'] == conta_orig['id']:
            return jsonify({'erro': 'Não é possível enviar PIX para si mesmo'}), 400

        codigo = gerar_codigo_transacao()
        conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta_orig['id']))
        conn.execute("UPDATE contas SET saldo = saldo + ? WHERE id=?", (valor, pix['cid']))
        conn.execute("""INSERT INTO transacoes (conta_origem, conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                        VALUES (?,?,'pix',?,?,?,?,?)""",
                     (conta_orig['id'], pix['cid'], valor,
                      d.get('descricao', f'PIX para {chave}'),
                      conta_orig['saldo'], conta_orig['saldo'] - valor, codigo))
        registrar_lancamento(
            conn, conta_orig['id'], 'pix', 'debito', valor,
            conta_orig['saldo'], conta_orig['saldo'] - valor, d.get('descricao', f'PIX para {chave}'), codigo
        )
        registrar_lancamento(
            conn, pix['cid'], 'pix', 'credito', valor,
            pix['saldo'], pix['saldo'] + valor, f'PIX recebido de {request.user.get("nome", "conta NeoBank")}', codigo
        )

        adicionar_notificacao(conn, uid, '⚡ PIX enviado', f'PIX de R${valor:.2f} enviado!', 'info')
        adicionar_notificacao(conn, pix['uid_dest'], '⚡ PIX recebido', f'Você recebeu R${valor:.2f} via PIX!', 'sucesso')

        conn.commit()
        return jsonify({'mensagem': 'PIX enviado!', 'codigo': codigo, 'destinatario': pix['nome']})
    finally:
        conn.close()

@app.route('/api/pix/agendar', methods=['GET', 'POST'])
@auth_required
def pix_agendar():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if request.method == 'GET':
            rows = conn.execute(
                """SELECT * FROM pix_agendamentos
                   WHERE usuario_id=?
                   ORDER BY criado_em DESC LIMIT 100""",
                (uid,)
            ).fetchall()
            return jsonify({'agendamentos': [dict(r) for r in rows]})

        d = parse_json_body()
        if not d:
            return jsonify({'erro': 'JSON inválido'}), 400

        chave = (d.get('chave') or '').strip()
        descricao = (d.get('descricao') or '').strip()
        data_execucao = (d.get('data_execucao') or '').strip()

        try:
            valor = float(d.get('valor', 0))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400

        if not chave or valor <= 0 or not data_execucao:
            return jsonify({'erro': 'Campos obrigatórios: chave, valor e data_execucao'}), 400

        try:
            dt_exec = datetime.strptime(data_execucao, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return jsonify({'erro': 'data_execucao deve estar no formato YYYY-MM-DD HH:MM:SS'}), 400

        if dt_exec <= datetime.now():
            return jsonify({'erro': 'Data de execução deve ser futura'}), 400

        conn.execute(
            """INSERT INTO pix_agendamentos (usuario_id, conta_id, chave, valor, descricao, data_execucao)
               VALUES (?,?,?,?,?,?)""",
            (uid, conta['id'], chave, valor, descricao, dt_exec.strftime('%Y-%m-%d %H:%M:%S'))
        )
        adicionar_notificacao(conn, uid, '📅 PIX agendado', f'PIX de R${valor:.2f} agendado para {dt_exec.strftime("%d/%m/%Y %H:%M")}.', 'info')
        conn.commit()
        return jsonify({'mensagem': 'PIX agendado com sucesso'})
    finally:
        conn.close()

@app.route('/api/pix/agendamentos/<int:agendamento_id>/cancelar', methods=['POST'])
@auth_required
def pix_agendamento_cancelar(agendamento_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        row = conn.execute(
            "SELECT * FROM pix_agendamentos WHERE id=? AND usuario_id=?",
            (agendamento_id, uid)
        ).fetchone()
        if not row:
            return jsonify({'erro': 'Agendamento não encontrado'}), 404
        if row['status'] != 'pendente':
            return jsonify({'erro': 'Apenas agendamentos pendentes podem ser cancelados'}), 400

        conn.execute("UPDATE pix_agendamentos SET status='cancelado', processado_em=datetime('now') WHERE id=?", (agendamento_id,))
        conn.commit()
        return jsonify({'mensagem': 'Agendamento cancelado'})
    finally:
        conn.close()

@app.route('/api/pix/agendamentos/processar', methods=['POST'])
@auth_required
def pix_agendamentos_processar():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        stats = processar_pix_agendamentos(conn, usuario_id=uid)
        conn.commit()
        return jsonify({'mensagem': 'Processamento concluído', **stats})
    finally:
        conn.close()

@app.route('/api/jobs/processar-diario', methods=['POST'])
@auth_required
def job_processar_diario():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        d = parse_json_body() or {}
        scope = d.get('scope', 'me')

        usuario_scope = uid
        if scope == 'all':
            job_token = os.getenv('JOB_TOKEN', '')
            header_token = request.headers.get('X-Job-Token', '')
            if not job_token or header_token != job_token:
                return jsonify({'erro': 'Token de job inválido para execução global'}), 403
            usuario_scope = None

        pix_stats = processar_pix_agendamentos(conn, usuario_id=usuario_scope)
        fechamento_stats = processar_fechamento_faturas(conn, usuario_id=usuario_scope)
        fatura_stats = processar_faturas_rotativo(conn, usuario_id=usuario_scope)
        boleto_stats = processar_boletos_atrasados(conn, usuario_id=usuario_scope)
        programaveis_stats = processar_pagamentos_programaveis(conn, usuario_id=usuario_scope)

        auto_prev = 0
        auto_sweep = 0
        if usuario_scope is None:
            usuarios = conn.execute("SELECT id FROM usuarios WHERE ativo=1").fetchall()
            for u in usuarios:
                prev = executar_prevencao_descoberto(conn, u['id'])
                swp = executar_smart_sweep(conn, u['id'])
                if prev.get('acionado'):
                    auto_prev += 1
                if swp.get('executado'):
                    auto_sweep += 1
        else:
            prev = executar_prevencao_descoberto(conn, usuario_scope)
            swp = executar_smart_sweep(conn, usuario_scope)
            auto_prev = 1 if prev.get('acionado') else 0
            auto_sweep = 1 if swp.get('executado') else 0
        conn.commit()

        return jsonify({
            'mensagem': 'Processamento diário concluído',
            'scope': scope,
            **pix_stats,
            **fechamento_stats,
            **fatura_stats,
            **boleto_stats,
            **programaveis_stats,
            'prevencao_descoberto_acionada': auto_prev,
            'smart_sweeps_executados': auto_sweep
        })
    finally:
        conn.close()

@app.route('/api/automacao/config', methods=['GET', 'POST'])
@auth_required
def automacao_config():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        if request.method == 'GET':
            cfg = obter_ou_criar_automacao_config(conn, uid)
            reserva = obter_ou_criar_reserva(conn, uid)
            conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchone()
            obrig = calcular_obrigacoes_curto_prazo(conn, conta['id'], dias=7) if conta else 0
            cenario = decidir_cenario_ux(conn, uid)
            risco = calcular_score_risco(conn, uid)
            cfg_dict = dict(cfg)
            try:
                cfg_dict['dashboard_ordem_widgets'] = json.loads(cfg_dict.get('dashboard_ordem_widgets') or '[]')
            except Exception:
                cfg_dict['dashboard_ordem_widgets'] = []
            return jsonify({
                'config': cfg_dict,
                'reserva': dict(reserva),
                'projecao_7d': round((conta['saldo'] if conta else 0) - obrig, 2),
                'obrigacoes_7d': round(obrig, 2),
                'cenario_ux': cenario,
                'risco': risco,
                'limiar_otp': limiar_otp_dinamico(conn, uid)
            })

        d = parse_json_body() or {}
        sweep_ativo = 1 if d.get('sweep_ativo') else 0
        prev_ativo = 1 if d.get('prevencao_descoberto_ativa', True) else 0
        sweep_min = max(0.0, float(d.get('sweep_min_reserva', 500.0)))
        sweep_pct = min(1.0, max(0.05, float(d.get('sweep_percentual_excesso', 0.3))))
        limite_alerta = max(0.0, float(d.get('limite_alerta', 100.0)))
        tom = (d.get('tom_comunicacao') or 'neutro').strip().lower()
        cenario_forcado = (d.get('cenario_forcado') or '').strip() or None
        ordem_ativa = 1 if d.get('dashboard_ordem_ativa') else 0
        ordem_raw = d.get('dashboard_ordem_widgets') or []
        if isinstance(ordem_raw, str):
            ordem_raw = [x.strip() for x in ordem_raw.split(',') if x.strip()]
        ordem_permitida = ['entradas', 'saidas', 'investimentos', 'credito']
        ordem = [x for x in ordem_raw if x in ordem_permitida]
        ordem = list(dict.fromkeys(ordem))
        for item in ordem_permitida:
            if item not in ordem:
                ordem.append(item)
        ordem_json = json.dumps(ordem, ensure_ascii=False)

        obter_ou_criar_automacao_config(conn, uid)
        conn.execute(
            """UPDATE automacao_config
               SET sweep_ativo=?, sweep_min_reserva=?, sweep_percentual_excesso=?,
                   prevencao_descoberto_ativa=?, limite_alerta=?, tom_comunicacao=?, cenario_forcado=?,
                   dashboard_ordem_ativa=?, dashboard_ordem_widgets=?, atualizado_em=datetime('now')
               WHERE usuario_id=?""",
            (sweep_ativo, sweep_min, sweep_pct, prev_ativo, limite_alerta, tom, cenario_forcado, ordem_ativa, ordem_json, uid)
        )
        conn.commit()
        return jsonify({'mensagem': 'Configuração de automação atualizada'})
    finally:
        conn.close()

@app.route('/api/automacao/reserva', methods=['GET', 'POST'])
@auth_required
def automacao_reserva():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404
        reserva = obter_ou_criar_reserva(conn, uid)

        if request.method == 'GET':
            return jsonify({'reserva': dict(reserva)})

        d = parse_json_body() or {}
        acao = (d.get('acao') or '').strip().lower()
        try:
            valor = float(d.get('valor', 0))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400
        if valor <= 0:
            return jsonify({'erro': 'Valor inválido'}), 400

        saldo = float(conta['saldo'])
        saldo_reserva = float(reserva['saldo_reserva'])

        if acao == 'depositar':
            if valor > saldo:
                return jsonify({'erro': 'Saldo insuficiente para reservar'}), 400
            saldo -= valor
            saldo_reserva += valor
        elif acao == 'resgatar':
            if valor > saldo_reserva:
                return jsonify({'erro': 'Saldo de reserva insuficiente'}), 400
            saldo += valor
            saldo_reserva -= valor
        else:
            return jsonify({'erro': 'Ação inválida. Use depositar ou resgatar'}), 400

        conn.execute("UPDATE contas SET saldo=? WHERE id=?", (saldo, conta['id']))
        conn.execute("UPDATE reserva_liquidez SET saldo_reserva=?, atualizado_em=datetime('now') WHERE usuario_id=?", (saldo_reserva, uid))
        conn.commit()
        return jsonify({'mensagem': 'Reserva atualizada', 'saldo_conta': round(saldo, 2), 'saldo_reserva': round(saldo_reserva, 2)})
    finally:
        conn.close()

@app.route('/api/automacao/executar', methods=['POST'])
@auth_required
def automacao_executar():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        prev = executar_prevencao_descoberto(conn, uid)
        sweep = executar_smart_sweep(conn, uid)
        programaveis = processar_pagamentos_programaveis(conn, usuario_id=uid)
        conn.commit()
        return jsonify({'mensagem': 'Automação executada', 'prevencao_descoberto': prev, 'smart_sweep': sweep, **programaveis})
    finally:
        conn.close()

@app.route('/api/ux/cenario', methods=['GET'])
@auth_required
def ux_cenario():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        cfg = obter_ou_criar_automacao_config(conn, uid)
        cenario = decidir_cenario_ux(conn, uid)
        tom = (cfg['tom_comunicacao'] or 'neutro')
        return jsonify({'cenario': cenario, 'tom': tom})
    finally:
        conn.close()

@app.route('/api/risco/painel', methods=['GET'])
@auth_required
def risco_painel():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        risco = calcular_score_risco(conn, uid)
        limiar = limiar_otp_dinamico(conn, uid)
        return jsonify({
            **risco,
            'limiar_otp': limiar
        })
    finally:
        conn.close()

@app.route('/api/openfinance/fontes', methods=['GET', 'POST'])
@auth_required
def openfinance_fontes():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        if request.method == 'GET':
            rows = conn.execute("SELECT * FROM open_finance_fontes WHERE usuario_id=? ORDER BY atualizado_em DESC", (uid,)).fetchall()
            return jsonify({'fontes': [dict(r) for r in rows]})

        d = parse_json_body() or {}
        instituicao = (d.get('instituicao') or '').strip()
        tipo = (d.get('tipo') or '').strip().lower()
        try:
            saldo = float(d.get('saldo', 0))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Saldo inválido'}), 400

        if not instituicao or not tipo:
            return jsonify({'erro': 'instituicao e tipo são obrigatórios'}), 400

        conn.execute(
            "INSERT INTO open_finance_fontes (usuario_id, instituicao, tipo, saldo, atualizado_em) VALUES (?,?,?,?,datetime('now'))",
            (uid, instituicao, tipo, saldo)
        )
        conn.commit()
        return jsonify({'mensagem': 'Fonte Open Finance adicionada'})
    finally:
        conn.close()

@app.route('/api/openfinance/fontes/<int:fonte_id>', methods=['DELETE'])
@auth_required
def openfinance_remover_fonte(fonte_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conn.execute("DELETE FROM open_finance_fontes WHERE id=? AND usuario_id=?", (fonte_id, uid))
        conn.commit()
        return jsonify({'mensagem': 'Fonte removida'})
    finally:
        conn.close()

@app.route('/api/openfinance/consolidado', methods=['GET'])
@auth_required
def openfinance_consolidado():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT saldo FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        reserva = obter_ou_criar_reserva(conn, uid)
        fontes = conn.execute("SELECT tipo, COALESCE(SUM(saldo),0) as total FROM open_finance_fontes WHERE usuario_id=? GROUP BY tipo", (uid,)).fetchall()
        por_tipo = {r['tipo']: float(r['total']) for r in fontes}
        saldo_neobank = float(conta['saldo']) if conta else 0.0
        patrimonio = saldo_neobank + float(reserva['saldo_reserva']) + sum(por_tipo.values())
        return jsonify({
            'neobank': {'saldo_conta': round(saldo_neobank, 2), 'reserva_liquidez': round(float(reserva['saldo_reserva']), 2)},
            'externo_por_tipo': {k: round(v, 2) for k, v in por_tipo.items()},
            'patrimonio_total': round(patrimonio, 2)
        })
    finally:
        conn.close()

@app.route('/api/pagamentos-programaveis', methods=['GET', 'POST'])
@auth_required
def pagamentos_programaveis():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        if request.method == 'GET':
            rows = conn.execute("SELECT * FROM pagamentos_programaveis WHERE usuario_id=? ORDER BY criado_em DESC", (uid,)).fetchall()
            return jsonify({'pagamentos': [dict(r) for r in rows]})

        d = parse_json_body() or {}
        descricao = (d.get('descricao') or '').strip()
        destinatario = (d.get('destinatario') or '').strip()
        condicao_tipo = (d.get('condicao_tipo') or '').strip().lower()
        condicao_valor = (d.get('condicao_valor') or '').strip()
        try:
            valor = float(d.get('valor', 0))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400

        if not descricao or not destinatario or valor <= 0:
            return jsonify({'erro': 'Descrição, destinatário e valor são obrigatórios'}), 400
        if condicao_tipo not in ('data', 'saldo_minimo'):
            return jsonify({'erro': 'condicao_tipo deve ser data ou saldo_minimo'}), 400
        if condicao_tipo == 'data':
            try:
                datetime.strptime(condicao_valor[:10], '%Y-%m-%d')
            except ValueError:
                return jsonify({'erro': 'condicao_valor deve ser data YYYY-MM-DD'}), 400
        if condicao_tipo == 'saldo_minimo':
            try:
                float(condicao_valor)
            except (TypeError, ValueError):
                return jsonify({'erro': 'condicao_valor deve ser número para saldo_minimo'}), 400

        conn.execute(
            """INSERT INTO pagamentos_programaveis
               (usuario_id, descricao, destinatario, valor, condicao_tipo, condicao_valor)
               VALUES (?,?,?,?,?,?)""",
            (uid, descricao, destinatario, valor, condicao_tipo, condicao_valor)
        )
        conn.commit()
        return jsonify({'mensagem': 'Pagamento programável criado'})
    finally:
        conn.close()

@app.route('/api/pagamentos-programaveis/<int:pagamento_id>/cancelar', methods=['POST'])
@auth_required
def cancelar_pagamento_programavel(pagamento_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conn.execute(
            "UPDATE pagamentos_programaveis SET status='cancelado' WHERE id=? AND usuario_id=? AND status='pendente'",
            (pagamento_id, uid)
        )
        conn.commit()
        return jsonify({'mensagem': 'Pagamento programável cancelado'})
    finally:
        conn.close()

@app.route('/api/ai/agentes/tarefas', methods=['GET', 'POST'])
@auth_required
def ai_agentes_tarefas():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        if request.method == 'GET':
            rows = conn.execute(
                "SELECT * FROM ai_agentes_tarefas WHERE usuario_id=? ORDER BY criado_em DESC LIMIT 20",
                (uid,)
            ).fetchall()
            tarefas = []
            for r in rows:
                d = dict(r)
                d['entrada'] = json.loads(d['entrada_json']) if d.get('entrada_json') else {}
                d['resultado'] = json.loads(d['resultado_json']) if d.get('resultado_json') else {}
                tarefas.append(d)
            return jsonify({'tarefas': tarefas})

        d = parse_json_body() or {}
        tipo = (d.get('tipo') or '').strip().lower()
        entrada = d.get('entrada') or {}
        if tipo not in ('contestar_cobranca', 'investigar_fatura', 'orquestrar_abertura_conta'):
            return jsonify({'erro': 'Tipo inválido de agente'}), 400

        resultado = executar_agente_autonomo(conn, uid, tipo, entrada)
        conn.commit()
        return jsonify({'mensagem': 'Agente executado com sucesso', 'tipo': tipo, 'resultado': resultado})
    finally:
        conn.close()

@app.route('/api/boletos', methods=['GET', 'POST'])
@auth_required
def boletos():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if request.method == 'GET':
            rows = conn.execute(
                """SELECT * FROM boletos
                   WHERE conta_id=?
                   ORDER BY CASE WHEN status IN ('pendente','atrasado') THEN 0 ELSE 1 END,
                            date(vencimento_em) ASC,
                            criado_em DESC""",
                (conta['id'],)
            ).fetchall()

            hoje = datetime.now().date()
            boletos_out = []
            for r in rows:
                d = dict(r)
                try:
                    venc = datetime.strptime((d['vencimento_em'] or '')[:10], '%Y-%m-%d').date()
                    d['dias_atraso'] = max(0, (hoje - venc).days)
                except ValueError:
                    d['dias_atraso'] = 0
                boletos_out.append(d)

            return jsonify({'boletos': boletos_out})

        d = parse_json_body()
        if not d:
            return jsonify({'erro': 'JSON inválido'}), 400

        descricao = (d.get('descricao') or '').strip()
        beneficiario = (d.get('beneficiario') or '').strip()
        vencimento_em = (d.get('vencimento_em') or '').strip()

        try:
            valor = float(d.get('valor', 0))
            multa_percentual = float(d.get('multa_percentual', 2.0) or 2.0)
            juros_mensal = float(d.get('juros_mensal', 1.0) or 1.0)
        except (TypeError, ValueError):
            return jsonify({'erro': 'Parâmetros inválidos'}), 400

        if not descricao or not beneficiario:
            return jsonify({'erro': 'Descrição e beneficiário são obrigatórios'}), 400
        if valor <= 0:
            return jsonify({'erro': 'Valor inválido'}), 400
        if multa_percentual < 0 or juros_mensal < 0:
            return jsonify({'erro': 'Multa e juros não podem ser negativos'}), 400
        try:
            datetime.strptime(vencimento_em, '%Y-%m-%d')
        except ValueError:
            return jsonify({'erro': 'vencimento_em deve estar no formato YYYY-MM-DD'}), 400

        linha = gerar_linha_digitavel()
        while conn.execute("SELECT 1 FROM boletos WHERE linha_digitavel=?", (linha,)).fetchone():
            linha = gerar_linha_digitavel()

        conn.execute(
            """INSERT INTO boletos
               (conta_id, linha_digitavel, descricao, beneficiario, valor_original, valor_atual, multa_percentual, juros_mensal, vencimento_em)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (conta['id'], linha, descricao, beneficiario, valor, valor, multa_percentual, juros_mensal, vencimento_em)
        )
        adicionar_notificacao(conn, uid, '📄 Boleto emitido', f'Boleto de R${valor:.2f} emitido para {beneficiario}.', 'info')
        conn.commit()
        return jsonify({'mensagem': 'Boleto emitido com sucesso', 'linha_digitavel': linha})
    finally:
        conn.close()

@app.route('/api/boletos/processar-atraso', methods=['POST'])
@auth_required
def boletos_processar_atraso():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        stats = processar_boletos_atrasados(conn, usuario_id=uid)
        conn.commit()
        return jsonify({'mensagem': 'Boletos atrasados processados', **stats})
    finally:
        conn.close()

@app.route('/api/boletos/<int:boleto_id>/pagar', methods=['POST'])
@auth_required
def pagar_boleto(boleto_id):
    d = parse_json_body() or {}
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        boleto = conn.execute(
            "SELECT * FROM boletos WHERE id=? AND conta_id=?",
            (boleto_id, conta['id'])
        ).fetchone()
        if not boleto:
            return jsonify({'erro': 'Boleto não encontrado'}), 404
        if boleto['status'] == 'pago':
            return jsonify({'erro': 'Boleto já está pago'}), 400
        if boleto['status'] == 'cancelado':
            return jsonify({'erro': 'Boleto cancelado'}), 400

        valor = float(boleto['valor_atual'])
        if valor > conta['saldo'] + conta['limite_cheque']:
            return jsonify({'erro': 'Saldo insuficiente para pagar boleto'}), 400

        limiar = limiar_otp_dinamico(conn, uid)
        if requer_otp(valor, limiar=limiar):
            otp_codigo = (d.get('otp_codigo') or '').strip()
            if not otp_codigo:
                return jsonify({'erro': f'OTP obrigatório para pagamentos >= R${limiar:.0f}', 'requires_otp': True, 'acao_otp': 'pagar_boleto', 'limiar_otp': limiar}), 428
            ok, msg = validar_desafio_otp(conn, uid, 'pagar_boleto', otp_codigo)
            if not ok:
                conn.commit()
                return jsonify({'erro': msg}), 401

        codigo = gerar_codigo_transacao()
        conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta['id']))
        conn.execute("UPDATE boletos SET status='pago', pago_em=datetime('now') WHERE id=?", (boleto_id,))
        conn.execute(
            """INSERT INTO transacoes (conta_origem, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
               VALUES (?,?,?,?,?,?,?)""",
            (conta['id'], 'pagamento_boleto', valor, f'Pagamento de boleto {boleto["linha_digitavel"]}',
             conta['saldo'], conta['saldo'] - valor, codigo)
        )
        registrar_lancamento(
            conn, conta['id'], 'pagamento_boleto', 'debito', valor,
            conta['saldo'], conta['saldo'] - valor, f'Pagamento de boleto {boleto["linha_digitavel"]}', codigo
        )
        adicionar_notificacao(conn, uid, '✅ Boleto pago', f'Pagamento de R${valor:.2f} confirmado.', 'sucesso')
        conn.commit()
        return jsonify({'mensagem': 'Boleto pago com sucesso', 'valor': round(valor, 2), 'codigo': codigo})
    finally:
        conn.close()

@app.route('/api/pix/devolver', methods=['POST'])
@auth_required
def pix_devolver():
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    codigo_original = (d.get('codigo') or '').strip()
    if not codigo_original:
        return jsonify({'erro': 'Código da transação PIX é obrigatório'}), 400

    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        tx = conn.execute(
            """SELECT * FROM transacoes
               WHERE codigo=? AND tipo='pix' AND conta_destino=?""",
            (codigo_original, conta['id'])
        ).fetchone()
        if not tx:
            return jsonify({'erro': 'PIX original não encontrado para devolução'}), 404

        devolvido = conn.execute(
            "SELECT COALESCE(SUM(valor),0) FROM pix_devolucoes WHERE transacao_original=?",
            (codigo_original,)
        ).fetchone()[0] or 0
        restante = float(tx['valor']) - float(devolvido)
        if restante <= 0:
            return jsonify({'erro': 'PIX já devolvido integralmente'}), 400

        try:
            valor = float(d.get('valor', restante))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400

        if valor <= 0 or valor > restante + 0.001:
            return jsonify({'erro': f'Valor de devolução inválido. Restante: R${restante:.2f}'}), 400
        if valor > conta['saldo'] + conta['limite_cheque']:
            return jsonify({'erro': 'Saldo insuficiente para devolução'}), 400

        conta_dest = conn.execute("SELECT * FROM contas WHERE id=?", (tx['conta_origem'],)).fetchone()
        if not conta_dest:
            return jsonify({'erro': 'Conta de destino da devolução não encontrada'}), 404

        codigo_dev = gerar_codigo_transacao()
        conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta['id']))
        conn.execute("UPDATE contas SET saldo = saldo + ? WHERE id=?", (valor, conta_dest['id']))
        conn.execute(
            """INSERT INTO transacoes (conta_origem, conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
               VALUES (?,?,'pix_devolucao',?,?,?,?,?)""",
            (conta['id'], conta_dest['id'], valor,
             f'Devolução PIX {codigo_original}', conta['saldo'], conta['saldo'] - valor, codigo_dev)
        )
        conn.execute(
            """INSERT INTO pix_devolucoes (transacao_original, transacao_devolucao, conta_origem, conta_destino, valor)
               VALUES (?,?,?,?,?)""",
            (codigo_original, codigo_dev, conta['id'], conta_dest['id'], valor)
        )
        registrar_lancamento(
            conn, conta['id'], 'pix_devolucao', 'debito', valor,
            conta['saldo'], conta['saldo'] - valor, f'Devolução PIX {codigo_original}', codigo_dev
        )
        registrar_lancamento(
            conn, conta_dest['id'], 'pix_devolucao', 'credito', valor,
            conta_dest['saldo'], conta_dest['saldo'] + valor, f'Recebimento de devolução PIX {codigo_original}', codigo_dev
        )

        conn.commit()
        return jsonify({'mensagem': 'Devolução PIX realizada', 'codigo': codigo_dev, 'valor': valor, 'restante_original': round(restante - valor, 2)})
    finally:
        conn.close()

@app.route('/api/pix/chaves', methods=['GET', 'POST', 'DELETE'])
@auth_required
def pix_chaves():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if request.method == 'GET':
            chaves = conn.execute("SELECT * FROM pix_chaves WHERE conta_id=? AND ativa=1", (conta['id'],)).fetchall()
            return jsonify({'chaves': [dict(c) for c in chaves]})

        if request.method == 'POST':
            d = parse_json_body()
            if not d:
                return jsonify({'erro': 'JSON inválido'}), 400
            if not d.get('tipo') or not d.get('chave'):
                return jsonify({'erro': 'Campos obrigatórios: tipo e chave'}), 400

            try:
                conn.execute("INSERT INTO pix_chaves (conta_id, tipo, chave) VALUES (?,?,?)",
                             (conta['id'], d['tipo'], d['chave']))
                conn.commit()
                return jsonify({'mensagem': 'Chave PIX cadastrada'})
            except sqlite3.IntegrityError:
                return jsonify({'erro': 'Chave já cadastrada'}), 409

        if request.method == 'DELETE':
            d = parse_json_body()
            if not d or not d.get('chave_id'):
                return jsonify({'erro': 'chave_id é obrigatório'}), 400

            conn.execute("UPDATE pix_chaves SET ativa=0 WHERE id=? AND conta_id=?", (d['chave_id'], conta['id']))
            conn.commit()
            return jsonify({'mensagem': 'Chave removida'})
    finally:
        conn.close()

@app.route('/api/deposito', methods=['POST'])
@auth_required
def deposito():
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    try:
        valor = float(d.get('valor', 0))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Valor inválido'}), 400

    if valor <= 0:
        return jsonify({'erro': 'Valor inválido'}), 400

    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        codigo = gerar_codigo_transacao()
        conn.execute("UPDATE contas SET saldo = saldo + ? WHERE id=?", (valor, conta['id']))
        conn.execute("""INSERT INTO transacoes (conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                        VALUES (?,'deposito',?,?,?,?,?)""",
                     (conta['id'], valor, d.get('descricao', 'Depósito'),
                      conta['saldo'], conta['saldo'] + valor, codigo))
        registrar_lancamento(
            conn, conta['id'], 'deposito', 'credito', valor,
            conta['saldo'], conta['saldo'] + valor, d.get('descricao', 'Depósito'), codigo
        )

        adicionar_notificacao(conn, uid, '💵 Depósito realizado',
            f'R${valor:.2f} depositado em sua conta', 'sucesso')
        conn.commit()
        return jsonify({'mensagem': 'Depósito realizado', 'codigo': codigo})
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: CARTÕES
# ─────────────────────────────────────────────

@app.route('/api/cartoes', methods=['GET'])
@auth_required
def listar_cartoes():
    conn = get_db()
    uid = request.user['usuario_id']
    conta = conn.execute("SELECT id FROM contas WHERE usuario_id=?", (uid,)).fetchone()
    cartoes = conn.execute("SELECT * FROM cartoes WHERE conta_id=?", (conta['id'],)).fetchall()
    conn.close()
    result = []
    for c in cartoes:
        cd = dict(c)
        num = cd['numero'].replace(' ', '')
        cd['numero_mascarado'] = f"**** **** **** {num[-4:]}"
        result.append(cd)
    return jsonify({'cartoes': result})

@app.route('/api/cartoes/novo', methods=['POST'])
@auth_required
def novo_cartao():
    d = parse_json_body()
    if d is None:
        return jsonify({'erro': 'JSON inválido'}), 400

    tipo = d.get('tipo', 'credito')
    conn = get_db()
    uid = request.user['usuario_id']
    conta = conn.execute("SELECT id FROM contas WHERE usuario_id=?", (uid,)).fetchone()

    num_cartao = gerar_numero_cartao()
    cvv = ''.join([str(secrets.randbelow(10)) for _ in range(3)])
    validade = (datetime.now() + timedelta(days=365*4)).strftime('%m/%Y')
    limite = float(d.get('limite', 1000.0)) if tipo == 'credito' else 0

    conn.execute("""INSERT INTO cartoes (conta_id, numero, cvv, validade, tipo, limite)
                    VALUES (?,?,?,?,?,?)""",
                 (conta['id'], num_cartao, cvv, validade, tipo, limite))
    adicionar_notificacao(conn, uid, '💳 Novo cartão criado',
        f'Cartão {tipo} criado com sucesso!', 'info')
    conn.commit()
    conn.close()
    return jsonify({'mensagem': f'Cartão {tipo} criado', 'numero': num_cartao, 'validade': validade})

@app.route('/api/cartoes/<int:cartao_id>/bloquear', methods=['POST'])
@auth_required
def bloquear_cartao(cartao_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        cartao = conn.execute("SELECT * FROM cartoes WHERE id=? AND conta_id=?", (cartao_id, conta['id'])).fetchone()
        if not cartao:
            return jsonify({'erro': 'Cartão não encontrado'}), 404
        if cartao['status'] == 'bloqueado':
            return jsonify({'erro': 'Cartão já está bloqueado'}), 400

        conn.execute("UPDATE cartoes SET status='bloqueado' WHERE id=? AND conta_id=?", (cartao_id, conta['id']))
        adicionar_notificacao(conn, uid, '🔒 Cartão bloqueado', 'Seu cartão foi bloqueado com sucesso.', 'alerta')
        conn.commit()
        return jsonify({'mensagem': 'Cartão bloqueado'})
    finally:
        conn.close()

@app.route('/api/cartoes/<int:cartao_id>/desbloquear', methods=['POST'])
@auth_required
def desbloquear_cartao(cartao_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        cartao = conn.execute("SELECT * FROM cartoes WHERE id=? AND conta_id=?", (cartao_id, conta['id'])).fetchone()
        if not cartao:
            return jsonify({'erro': 'Cartão não encontrado'}), 404
        if cartao['status'] not in ('ativo', 'bloqueado'):
            return jsonify({'erro': f'Cartão em status não suportado para desbloqueio: {cartao["status"]}'}), 400
        if cartao['status'] == 'ativo':
            return jsonify({'erro': 'Cartão já está ativo'}), 400

        conn.execute("UPDATE cartoes SET status='ativo' WHERE id=? AND conta_id=?", (cartao_id, conta['id']))
        adicionar_notificacao(conn, uid, '🔓 Cartão desbloqueado', 'Seu cartão voltou a ficar disponível para uso.', 'sucesso')
        conn.commit()
        return jsonify({'mensagem': 'Cartão desbloqueado'})
    finally:
        conn.close()

@app.route('/api/cartoes/<int:cartao_id>/compras', methods=['POST'])
@auth_required
def compra_cartao(cartao_id):
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    try:
        valor = float(d.get('valor', 0))
        parcelas = int(d.get('parcelas', 1))
    except (TypeError, ValueError):
        return jsonify({'erro': 'Parâmetros inválidos'}), 400

    descricao = (d.get('descricao') or 'Compra no cartão').strip()
    if valor <= 0 or parcelas <= 0:
        return jsonify({'erro': 'Valor e parcelas inválidos'}), 400

    conn = get_db()
    try:
        uid = request.user['usuario_id']
        cartao = conn.execute(
            """SELECT ca.* FROM cartoes ca
               JOIN contas co ON ca.conta_id = co.id
               WHERE ca.id=? AND co.usuario_id=?""",
            (cartao_id, uid)
        ).fetchone()
        if not cartao:
            return jsonify({'erro': 'Cartão não encontrado'}), 404
        if cartao['status'] != 'ativo':
            return jsonify({'erro': 'Cartão bloqueado/inativo'}), 400
        if cartao['tipo'] != 'credito':
            return jsonify({'erro': 'Compras lançadas só são permitidas no cartão de crédito'}), 400

        if valor > (float(cartao['limite']) - float(cartao['limite_usado'])):
            return jsonify({'erro': 'Limite insuficiente no cartão'}), 400

        limiar = limiar_otp_dinamico(conn, uid)
        if requer_otp(valor, limiar=limiar):
            otp_codigo = (d.get('otp_codigo') or '').strip()
            if not otp_codigo:
                return jsonify({'erro': f'OTP obrigatório para compras >= R${limiar:.0f}', 'requires_otp': True, 'acao_otp': 'cartao_compra', 'limiar_otp': limiar}), 428
            ok, msg = validar_desafio_otp(conn, uid, 'cartao_compra', otp_codigo)
            if not ok:
                conn.commit()
                return jsonify({'erro': msg}), 401

        fatura = obter_ou_criar_fatura(conn, cartao_id)
        mes_base = fatura['mes_ref']
        valor_parcela = round(valor / parcelas, 2)
        valor_primeira = round(valor - (valor_parcela * (parcelas - 1)), 2)

        conn.execute(
            """INSERT INTO compras_cartao (cartao_id, fatura_id, descricao, valor, parcelas)
               VALUES (?,?,?,?,?)""",
            (cartao_id, fatura['id'], descricao, valor, parcelas)
        )
        compra_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for n in range(1, parcelas + 1):
            mes_ref = mes_ref_add(mes_base, n - 1)
            valor_n = valor_primeira if n == 1 else valor_parcela
            fatura_id = fatura['id'] if n == 1 else None
            status = 'faturada' if n == 1 else 'pendente'
            conn.execute(
                """INSERT INTO parcelas_compra_cartao
                   (compra_id, cartao_id, mes_ref, numero_parcela, total_parcelas, valor_parcela, fatura_id, status)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (compra_id, cartao_id, mes_ref, n, parcelas, valor_n, fatura_id, status)
            )

        recalcular_fatura(conn, fatura['id'])
        conn.execute("UPDATE cartoes SET limite_usado = limite_usado + ? WHERE id=?", (valor, cartao_id))

        adicionar_notificacao(conn, uid, '🧾 Compra no crédito', f'Compra de R${valor:.2f} lançada na fatura.', 'info')
        conn.commit()
        return jsonify({'mensagem': 'Compra lançada na fatura', 'valor': valor})
    finally:
        conn.close()

@app.route('/api/cartoes/<int:cartao_id>/fatura', methods=['GET'])
@auth_required
def fatura_cartao(cartao_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        cartao = conn.execute(
            """SELECT ca.* FROM cartoes ca
               JOIN contas co ON ca.conta_id = co.id
               WHERE ca.id=? AND co.usuario_id=?""",
            (cartao_id, uid)
        ).fetchone()
        if not cartao:
            return jsonify({'erro': 'Cartão não encontrado'}), 404

        fatura = obter_ou_criar_fatura(conn, cartao_id)
        compras = conn.execute(
            """SELECT p.id as parcela_id, p.numero_parcela, p.total_parcelas, p.valor_parcela,
                      p.mes_ref, c.descricao, c.id as compra_id, p.status
               FROM parcelas_compra_cartao p
               JOIN compras_cartao c ON p.compra_id = c.id
               WHERE p.fatura_id=?
               ORDER BY p.criado_em DESC""",
            (fatura['id'],)
        ).fetchall()
        aberto = max(0.0, float(fatura['total_fatura']) - float(fatura['valor_pago']))
        return jsonify({
            'fatura': {
                **dict(fatura),
                'valor_aberto': round(aberto, 2)
            },
            'compras': [dict(c) for c in compras]
        })
    finally:
        conn.close()

@app.route('/api/cartoes/<int:cartao_id>/faturas', methods=['GET'])
@auth_required
def listar_faturas_cartao(cartao_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        cartao = conn.execute(
            """SELECT ca.* FROM cartoes ca
               JOIN contas co ON ca.conta_id = co.id
               WHERE ca.id=? AND co.usuario_id=?""",
            (cartao_id, uid)
        ).fetchone()
        if not cartao:
            return jsonify({'erro': 'Cartão não encontrado'}), 404

        rows = conn.execute(
            """SELECT * FROM faturas_cartao
               WHERE cartao_id=?
               ORDER BY mes_ref DESC
               LIMIT 24""",
            (cartao_id,)
        ).fetchall()

        faturas = []
        for r in rows:
            d = dict(r)
            aberto = max(0.0, float(d['total_fatura']) - float(d['valor_pago']))
            d['valor_aberto'] = round(aberto, 2)
            faturas.append(d)

        return jsonify({'faturas': faturas})
    finally:
        conn.close()

@app.route('/api/cartoes/<int:cartao_id>/faturas/<int:fatura_id>', methods=['GET'])
@auth_required
def detalhe_fatura_cartao(cartao_id, fatura_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        cartao = conn.execute(
            """SELECT ca.* FROM cartoes ca
               JOIN contas co ON ca.conta_id = co.id
               WHERE ca.id=? AND co.usuario_id=?""",
            (cartao_id, uid)
        ).fetchone()
        if not cartao:
            return jsonify({'erro': 'Cartão não encontrado'}), 404

        fatura = conn.execute(
            "SELECT * FROM faturas_cartao WHERE id=? AND cartao_id=?",
            (fatura_id, cartao_id)
        ).fetchone()
        if not fatura:
            return jsonify({'erro': 'Fatura não encontrada'}), 404

        parcelas = conn.execute(
            """SELECT p.id as parcela_id, p.numero_parcela, p.total_parcelas,
                      p.valor_parcela, p.mes_ref, p.status,
                      c.descricao, c.id as compra_id
               FROM parcelas_compra_cartao p
               JOIN compras_cartao c ON p.compra_id = c.id
               WHERE p.fatura_id=?
               ORDER BY p.criado_em DESC""",
            (fatura_id,)
        ).fetchall()

        f = dict(fatura)
        aberto = max(0.0, float(f['total_fatura']) - float(f['valor_pago']))
        f['valor_aberto'] = round(aberto, 2)

        return jsonify({'fatura': f, 'parcelas': [dict(p) for p in parcelas]})
    finally:
        conn.close()

@app.route('/api/cartoes/<int:cartao_id>/fatura/pagar', methods=['POST'])
@auth_required
def pagar_fatura_cartao(cartao_id):
    d = parse_json_body()
    if not d:
        return jsonify({'erro': 'JSON inválido'}), 400

    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? AND status='ativa'", (uid,)).fetchone()
        cartao = conn.execute(
            """SELECT ca.* FROM cartoes ca
               JOIN contas co ON ca.conta_id = co.id
               WHERE ca.id=? AND co.usuario_id=?""",
            (cartao_id, uid)
        ).fetchone()
        if not conta or not cartao:
            return jsonify({'erro': 'Conta/cartão não encontrados'}), 404

        fatura = obter_ou_criar_fatura(conn, cartao_id)
        aberto = max(0.0, float(fatura['total_fatura']) - float(fatura['valor_pago']))
        if aberto <= 0:
            return jsonify({'erro': 'Não há saldo de fatura em aberto'}), 400

        try:
            valor = float(d.get('valor', aberto))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400

        if valor <= 0 or valor > aberto + 0.001:
            return jsonify({'erro': f'Valor inválido para pagamento. Em aberto: R${aberto:.2f}'}), 400
        if valor > conta['saldo'] + conta['limite_cheque']:
            return jsonify({'erro': 'Saldo insuficiente para pagar fatura'}), 400

        limiar = limiar_otp_dinamico(conn, uid)
        if requer_otp(valor, limiar=limiar):
            otp_codigo = (d.get('otp_codigo') or '').strip()
            if not otp_codigo:
                return jsonify({'erro': f'OTP obrigatório para pagamentos >= R${limiar:.0f}', 'requires_otp': True, 'acao_otp': 'pagar_fatura', 'limiar_otp': limiar}), 428
            ok, msg = validar_desafio_otp(conn, uid, 'pagar_fatura', otp_codigo)
            if not ok:
                conn.commit()
                return jsonify({'erro': msg}), 401

        novo_pago = float(fatura['valor_pago']) + valor
        novo_aberto = max(0.0, float(fatura['total_fatura']) - novo_pago)
        novo_status = 'paga' if novo_aberto <= 0.001 else 'parcial'

        conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta['id']))
        conn.execute(
            "UPDATE faturas_cartao SET valor_pago=?, status=? WHERE id=?",
            (novo_pago, novo_status, fatura['id'])
        )
        conn.execute(
            "UPDATE cartoes SET limite_usado = MAX(0, limite_usado - ?) WHERE id=?",
            (valor, cartao_id)
        )
        codigo = gerar_codigo_transacao()
        conn.execute(
            """INSERT INTO transacoes (conta_origem, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
               VALUES (?,?,?,?,?,?,?)""",
            (conta['id'], 'pagamento_fatura', valor, f'Pagamento de fatura cartão {cartao_id}',
             conta['saldo'], conta['saldo'] - valor, codigo)
        )
        registrar_lancamento(
            conn, conta['id'], 'pagamento_fatura', 'debito', valor,
            conta['saldo'], conta['saldo'] - valor, f'Pagamento de fatura cartão {cartao_id}', codigo
        )

        if valor < float(fatura['valor_minimo']) and novo_status != 'paga':
            adicionar_notificacao(conn, uid, '⚠️ Pagamento abaixo do mínimo', 'Pagamento abaixo do mínimo da fatura pode gerar juros rotativo no próximo ciclo.', 'alerta')
        else:
            adicionar_notificacao(conn, uid, '✅ Fatura paga', f'Pagamento de R${valor:.2f} registrado na sua fatura.', 'sucesso')

        conn.commit()
        return jsonify({'mensagem': 'Pagamento de fatura realizado', 'status_fatura': novo_status, 'valor_aberto': round(novo_aberto, 2)})
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: INVESTIMENTOS
# ─────────────────────────────────────────────

@app.route('/api/investimentos', methods=['GET', 'POST'])
@auth_required
def investimentos():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if request.method == 'GET':
            invs = conn.execute("SELECT * FROM investimentos WHERE conta_id=? AND status='ativo'", (conta['id'],)).fetchall()
            return jsonify({'investimentos': [dict(i) for i in invs]})

        d = parse_json_body()
        if not d:
            return jsonify({'erro': 'JSON inválido'}), 400

        try:
            valor = float(d.get('valor', 0))
            prazo = int(d.get('prazo_dias', 365))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Parâmetros inválidos'}), 400

        tipo = d.get('tipo', 'cdb')
        taxas = {'cdb': 12.5, 'lci': 10.8, 'lca': 10.5, 'tesouro': 13.2, 'fundos': 9.8}
        taxa = taxas.get(tipo, 10.0)

        if valor <= 0:
            return jsonify({'erro': 'Valor inválido'}), 400
        if prazo <= 0:
            return jsonify({'erro': 'Prazo inválido'}), 400
        if valor > conta['saldo']:
            return jsonify({'erro': 'Saldo insuficiente'}), 400

        vencimento = (datetime.now() + timedelta(days=prazo)).strftime('%Y-%m-%d')

        conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta['id']))
        conn.execute("""INSERT INTO investimentos (conta_id, tipo, valor_inicial, valor_atual, taxa_anual, data_vencimento)
                        VALUES (?,?,?,?,?,?)""",
                     (conta['id'], tipo.upper(), valor, valor, taxa, vencimento))
        conn.execute("""INSERT INTO transacoes (conta_origem, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                        VALUES (?,?,?,?,?,?,?)""",
                     (conta['id'], 'investimento', valor, f'Aplicação {tipo.upper()}',
                      conta['saldo'], conta['saldo'] - valor, gerar_codigo_transacao()))
        registrar_lancamento(
            conn, conta['id'], 'investimento', 'debito', valor,
            conta['saldo'], conta['saldo'] - valor, f'Aplicação {tipo.upper()}'
        )

        adicionar_notificacao(conn, uid, '📈 Investimento realizado',
            f'R${valor:.2f} aplicado em {tipo.upper()} a {taxa}% a.a.', 'sucesso')
        conn.commit()
        return jsonify({'mensagem': f'Investimento em {tipo.upper()} realizado!', 'taxa': taxa, 'vencimento': vencimento})
    finally:
        conn.close()

@app.route('/api/investimentos/<int:inv_id>/resgatar', methods=['POST'])
@auth_required
def resgatar_investimento(inv_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        inv = conn.execute("SELECT * FROM investimentos WHERE id=? AND conta_id=? AND status='ativo'",
                           (inv_id, conta['id'])).fetchone()
        if not inv:
            return jsonify({'erro': 'Investimento não encontrado'}), 404

        dias = (datetime.now() - datetime.strptime(inv['criado_em'][:10], '%Y-%m-%d')).days
        rendimento = inv['valor_inicial'] * (inv['taxa_anual'] / 100) * (dias / 365)
        valor_resgate = inv['valor_inicial'] + rendimento
        ir = rendimento * 0.15
        valor_liquido = valor_resgate - ir

        conn.execute("UPDATE investimentos SET status='resgatado', valor_atual=? WHERE id=?",
                     (valor_liquido, inv_id))
        conn.execute("UPDATE contas SET saldo = saldo + ? WHERE id=?", (valor_liquido, conta['id']))
        conn.execute("""INSERT INTO transacoes (conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                        VALUES (?,?,?,?,?,?,?)""",
                     (conta['id'], 'resgate', valor_liquido, f'Resgate {inv["tipo"]}',
                      conta['saldo'], conta['saldo'] + valor_liquido, gerar_codigo_transacao()))
        registrar_lancamento(
            conn, conta['id'], 'resgate', 'credito', valor_liquido,
            conta['saldo'], conta['saldo'] + valor_liquido, f'Resgate {inv["tipo"]}'
        )

        conn.commit()
        return jsonify({
            'mensagem': 'Resgate realizado',
            'valor_bruto': round(valor_resgate, 2),
            'ir_retido': round(ir, 2),
            'valor_liquido': round(valor_liquido, 2),
            'rendimento': round(rendimento, 2)
        })
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: EMPRÉSTIMOS
# ─────────────────────────────────────────────

@app.route('/api/emprestimos', methods=['GET', 'POST'])
@auth_required
def emprestimos():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if request.method == 'GET':
            emps = conn.execute("SELECT * FROM emprestimos WHERE conta_id=? AND status='ativo'", (conta['id'],)).fetchall()
            return jsonify({'emprestimos': [dict(e) for e in emps]})

        d = parse_json_body()
        if not d:
            return jsonify({'erro': 'JSON inválido'}), 400

        try:
            valor = float(d.get('valor', 0))
            parcelas = int(d.get('parcelas', 12))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Parâmetros inválidos'}), 400

        if valor <= 0 or parcelas <= 0:
            return jsonify({'erro': 'Parâmetros inválidos'}), 400
        if valor > 50000:
            return jsonify({'erro': 'Limite máximo R$50.000'}), 400

        taxa = 1.99 if parcelas <= 6 else (2.49 if parcelas <= 12 else 2.99)
        i = taxa / 100
        parcela = valor * (i * (1+i)**parcelas) / ((1+i)**parcelas - 1)

        conn.execute("""INSERT INTO emprestimos (conta_id, valor, juros_mensal, parcelas, valor_parcela)
                        VALUES (?,?,?,?,?)""",
                     (conta['id'], valor, taxa, parcelas, parcela))
        conn.execute("UPDATE contas SET saldo = saldo + ? WHERE id=?", (valor, conta['id']))
        conn.execute("""INSERT INTO transacoes (conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                        VALUES (?,?,?,?,?,?,?)""",
                     (conta['id'], 'emprestimo', valor, f'Empréstimo {parcelas}x',
                      conta['saldo'], conta['saldo'] + valor, gerar_codigo_transacao()))
        registrar_lancamento(
            conn, conta['id'], 'emprestimo', 'credito', valor,
            conta['saldo'], conta['saldo'] + valor, f'Crédito de empréstimo {parcelas}x'
        )

        adicionar_notificacao(conn, uid, '🏦 Empréstimo aprovado',
            f'R${valor:.2f} creditado em {parcelas}x de R${parcela:.2f}', 'sucesso')
        conn.commit()
        return jsonify({
            'mensagem': 'Empréstimo aprovado!',
            'valor': valor,
            'parcelas': parcelas,
            'valor_parcela': round(parcela, 2),
            'taxa': taxa
        })
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: DÍVIDAS
# ─────────────────────────────────────────────

@app.route('/api/dividas', methods=['GET', 'POST'])
@auth_required
def dividas():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if request.method == 'GET':
            rows = conn.execute(
                """SELECT * FROM dividas WHERE conta_id=? ORDER BY
                   CASE WHEN status='ativa' THEN 0 ELSE 1 END,
                   COALESCE(vencimento, '9999-12-31') ASC,
                   criado_em DESC""",
                (conta['id'],)
            ).fetchall()
            return jsonify({'dividas': [dict(r) for r in rows]})

        d = parse_json_body()
        if not d:
            return jsonify({'erro': 'JSON inválido'}), 400

        descricao = (d.get('descricao') or '').strip()
        categoria = (d.get('categoria') or 'geral').strip().lower()
        credor = (d.get('credor') or '').strip()
        vencimento = (d.get('vencimento') or '').strip()

        try:
            valor_total = float(d.get('valor_total', 0))
            parcelas_total = int(d.get('parcelas_total', 1))
            juros_mensal = float(d.get('juros_mensal', 0) or 0)
        except (TypeError, ValueError):
            return jsonify({'erro': 'Parâmetros inválidos'}), 400

        if not descricao:
            return jsonify({'erro': 'Descrição é obrigatória'}), 400
        if valor_total <= 0:
            return jsonify({'erro': 'Valor total inválido'}), 400
        if parcelas_total <= 0:
            return jsonify({'erro': 'Parcelas devem ser maiores que zero'}), 400
        if juros_mensal < 0:
            return jsonify({'erro': 'Juros mensal não pode ser negativo'}), 400

        if vencimento:
            try:
                datetime.strptime(vencimento, '%Y-%m-%d')
            except ValueError:
                return jsonify({'erro': 'Vencimento deve estar no formato YYYY-MM-DD'}), 400
        else:
            vencimento = None

        valor_parcela = round(valor_total / parcelas_total, 2)
        conn.execute(
            """INSERT INTO dividas
               (conta_id, descricao, categoria, credor, valor_total, valor_parcela, parcelas_total, juros_mensal, vencimento)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (conta['id'], descricao, categoria, credor, valor_total, valor_parcela, parcelas_total, juros_mensal, vencimento)
        )

        adicionar_notificacao(conn, uid, '📌 Dívida cadastrada',
            f'Dívida "{descricao}" registrada no valor de R${valor_total:.2f}.', 'info')
        conn.commit()
        return jsonify({'mensagem': 'Dívida cadastrada com sucesso'})
    finally:
        conn.close()

@app.route('/api/dividas/<int:divida_id>/pagar', methods=['POST'])
@auth_required
def pagar_divida(divida_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        divida = conn.execute("SELECT * FROM dividas WHERE id=? AND conta_id=?", (divida_id, conta['id'])).fetchone()
        if not divida:
            return jsonify({'erro': 'Dívida não encontrada'}), 404
        if divida['status'] != 'ativa':
            return jsonify({'erro': 'Essa dívida já está quitada'}), 400

        d = parse_json_body() or {}
        restante = max(0.0, float(divida['valor_total']) - float(divida['valor_pago']))
        valor_sugerido = min(float(divida['valor_parcela']), restante)

        try:
            valor = float(d.get('valor', valor_sugerido))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400

        limiar = limiar_otp_dinamico(conn, uid)
        if requer_otp(valor, limiar=limiar):
            otp_codigo = (d.get('otp_codigo') or '').strip()
            if not otp_codigo:
                return jsonify({'erro': f'OTP obrigatório para pagamentos >= R${limiar:.0f}', 'requires_otp': True, 'acao_otp': 'pagar_divida', 'limiar_otp': limiar}), 428
            ok, msg = validar_desafio_otp(conn, uid, 'pagar_divida', otp_codigo)
            if not ok:
                conn.commit()
                return jsonify({'erro': msg}), 401

        if valor <= 0:
            return jsonify({'erro': 'Valor inválido'}), 400
        if valor > restante + 0.001:
            return jsonify({'erro': f'Valor acima do restante da dívida (R${restante:.2f})'}), 400

        saldo_disp = conta['saldo'] + conta['limite_cheque']
        if valor > saldo_disp:
            return jsonify({'erro': f'Saldo insuficiente. Disponível: R${saldo_disp:.2f}'}), 400

        novo_pago = round(float(divida['valor_pago']) + valor, 2)
        valor_total = float(divida['valor_total'])
        valor_parcela = max(0.01, float(divida['valor_parcela']))
        parcelas_pagas = min(int(divida['parcelas_total']), int(novo_pago // valor_parcela))
        status = 'quitada' if novo_pago >= (valor_total - 0.001) else 'ativa'
        if status == 'quitada':
            parcelas_pagas = int(divida['parcelas_total'])

        conn.execute("UPDATE contas SET saldo = saldo - ? WHERE id=?", (valor, conta['id']))
        conn.execute(
            """UPDATE dividas
               SET valor_pago=?, parcelas_pagas=?, status=?
               WHERE id=? AND conta_id=?""",
            (novo_pago, parcelas_pagas, status, divida_id, conta['id'])
        )
        conn.execute(
            """INSERT INTO transacoes (conta_origem, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
               VALUES (?,?,?,?,?,?,?)""",
            (conta['id'], 'pagamento_divida', valor, f'Pagamento de dívida: {divida["descricao"]}',
             conta['saldo'], conta['saldo'] - valor, gerar_codigo_transacao())
        )
        registrar_lancamento(
            conn, conta['id'], 'pagamento_divida', 'debito', valor,
            conta['saldo'], conta['saldo'] - valor, f'Pagamento de dívida: {divida["descricao"]}'
        )

        if status == 'quitada':
            msg = f'Sua dívida "{divida["descricao"]}" foi quitada. Parabéns!'
            titulo = '✅ Dívida quitada'
            tipo = 'sucesso'
        else:
            restante_novo = max(0.0, valor_total - novo_pago)
            msg = f'Pagamento registrado. Restante: R${restante_novo:.2f}.'
            titulo = '💸 Pagamento de dívida'
            tipo = 'info'
        adicionar_notificacao(conn, uid, titulo, msg, tipo)

        conn.commit()
        return jsonify({
            'mensagem': 'Pagamento realizado com sucesso',
            'status_divida': status,
            'valor_pago': valor,
            'restante': round(max(0.0, valor_total - novo_pago), 2),
            'saldo_atual': round(conta['saldo'] - valor, 2)
        })
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: GASTOS E RECEITAS CATEGORIZADOS
# ─────────────────────────────────────────────

@app.route('/api/gastos', methods=['GET', 'POST'])
@auth_required
def gastos_categorizados():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? LIMIT 1", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        if request.method == 'GET':
            try:
                limit = int(request.args.get('limit', 80))
            except (TypeError, ValueError):
                return jsonify({'erro': 'Parâmetro limit inválido'}), 400

            if limit < 1 or limit > 300:
                return jsonify({'erro': 'Use limit entre 1 e 300'}), 400

            rows = conn.execute(
                """SELECT * FROM gastos_categorias
                   WHERE conta_id=?
                   ORDER BY criado_em DESC
                   LIMIT ?""",
                (conta['id'], limit)
            ).fetchall()

            resumo = conn.execute(
                """SELECT tipo_movimento, categoria,
                          COUNT(*) AS quantidade,
                          COALESCE(SUM(valor), 0) AS total
                   FROM gastos_categorias
                   WHERE conta_id=?
                   GROUP BY tipo_movimento, categoria
                   ORDER BY tipo_movimento ASC, total DESC""",
                (conta['id'],)
            ).fetchall()

            inicio_mes = datetime.now().strftime('%Y-%m-01 00:00:00')
            mes_ref = datetime.now().strftime('%Y-%m')
            entradas_mes = conn.execute(
                """SELECT COALESCE(SUM(valor), 0) FROM gastos_categorias
                   WHERE conta_id=? AND tipo_movimento='entrada' AND criado_em >= ?""",
                (conta['id'], inicio_mes)
            ).fetchone()[0] or 0
            saidas_mes = conn.execute(
                """SELECT COALESCE(SUM(valor), 0) FROM gastos_categorias
                   WHERE conta_id=? AND tipo_movimento='saida' AND criado_em >= ?""",
                (conta['id'], inicio_mes)
            ).fetchone()[0] or 0

            saidas_mes_categoria = conn.execute(
                """SELECT categoria, COALESCE(SUM(valor), 0) AS total
                   FROM gastos_categorias
                   WHERE conta_id=? AND tipo_movimento='saida' AND criado_em >= ?
                   GROUP BY categoria
                   ORDER BY total DESC""",
                (conta['id'], inicio_mes)
            ).fetchall()

            orc_rows = conn.execute(
                """SELECT * FROM orcamentos_categorias
                   WHERE conta_id=? AND mes_ref=?
                   ORDER BY categoria ASC""",
                (conta['id'], mes_ref)
            ).fetchall()
            gasto_por_cat = {r['categoria']: float(r['total'] or 0) for r in saidas_mes_categoria}
            orcamentos = []
            alertas = []
            for r in orc_rows:
                limite = float(r['limite_mensal'] or 0)
                executado = float(gasto_por_cat.get(r['categoria'], 0))
                percentual = (executado / limite * 100.0) if limite > 0 else 0.0
                status = 'ok'
                if percentual >= 100:
                    status = 'estourado'
                elif percentual >= 80:
                    status = 'alerta'

                item = {
                    'id': r['id'],
                    'categoria': r['categoria'],
                    'mes_ref': r['mes_ref'],
                    'limite_mensal': round(limite, 2),
                    'executado': round(executado, 2),
                    'percentual': round(percentual, 1),
                    'status': status
                }
                orcamentos.append(item)
                if status != 'ok':
                    alertas.append(item)

            return jsonify({
                'gastos': [dict(r) for r in rows],
                'resumo_categoria': [dict(r) for r in resumo],
                'saidas_mes_categoria': [dict(r) for r in saidas_mes_categoria],
                'orcamentos': orcamentos,
                'alertas_orcamento': alertas,
                'totais_mes': {
                    'entradas': round(float(entradas_mes), 2),
                    'saidas': round(float(saidas_mes), 2)
                }
            })

        d = parse_json_body()
        if not d:
            return jsonify({'erro': 'JSON inválido'}), 400

        tipo_movimento = (d.get('tipo_movimento') or '').strip().lower()
        categoria = (d.get('categoria') or 'geral').strip().lower()
        descricao = (d.get('descricao') or '').strip()

        try:
            valor = float(d.get('valor', 0))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400

        if tipo_movimento not in ('entrada', 'saida'):
            return jsonify({'erro': 'Tipo deve ser "entrada" ou "saida"'}), 400
        if not descricao:
            return jsonify({'erro': 'Descrição é obrigatória'}), 400
        if valor <= 0:
            return jsonify({'erro': 'Valor deve ser maior que zero'}), 400

        saldo_antes = float(conta['saldo'])
        codigo = gerar_codigo_transacao()

        if tipo_movimento == 'saida':
            saldo_disp = saldo_antes + float(conta['limite_cheque'])
            if valor > saldo_disp:
                return jsonify({'erro': f'Saldo insuficiente. Disponível: R${saldo_disp:.2f}'}), 400
            saldo_depois = round(saldo_antes - valor, 2)
            transacao_tipo = 'gasto_saida'
            conn.execute("UPDATE contas SET saldo=? WHERE id=?", (saldo_depois, conta['id']))
            conn.execute(
                """INSERT INTO transacoes (conta_origem, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                   VALUES (?,?,?,?,?,?,?)""",
                (conta['id'], transacao_tipo, valor, f'{descricao} ({categoria})', saldo_antes, saldo_depois, codigo)
            )
            registrar_lancamento(
                conn, conta['id'], transacao_tipo, 'debito', valor,
                saldo_antes, saldo_depois, f'Saída categorizada: {descricao} [{categoria}]', codigo
            )
            adicionar_notificacao(
                conn, uid, '📤 Saída registrada',
                f'Saída de R${valor:.2f} em "{categoria}" foi cadastrada.', 'info'
            )
        else:
            saldo_depois = round(saldo_antes + valor, 2)
            transacao_tipo = 'gasto_entrada'
            conn.execute("UPDATE contas SET saldo=? WHERE id=?", (saldo_depois, conta['id']))
            conn.execute(
                """INSERT INTO transacoes (conta_destino, tipo, valor, descricao, saldo_anterior, saldo_posterior, codigo)
                   VALUES (?,?,?,?,?,?,?)""",
                (conta['id'], transacao_tipo, valor, f'{descricao} ({categoria})', saldo_antes, saldo_depois, codigo)
            )
            registrar_lancamento(
                conn, conta['id'], transacao_tipo, 'credito', valor,
                saldo_antes, saldo_depois, f'Entrada categorizada: {descricao} [{categoria}]', codigo
            )
            adicionar_notificacao(
                conn, uid, '📥 Entrada registrada',
                f'Entrada de R${valor:.2f} em "{categoria}" foi cadastrada.', 'sucesso'
            )

        conn.execute(
                """INSERT INTO gastos_categorias
                    (conta_id, tipo_movimento, categoria, descricao, valor, transacao_codigo, atualizado_em)
                    VALUES (?,?,?,?,?,?,datetime('now'))""",
                (conta['id'], tipo_movimento, categoria, descricao, valor, codigo)
        )

        conn.commit()
        return jsonify({
            'mensagem': 'Lançamento registrado com sucesso',
            'tipo_movimento': tipo_movimento,
            'saldo_atual': saldo_depois
        })
    finally:
        conn.close()

@app.route('/api/gastos/<int:gasto_id>', methods=['PUT', 'DELETE'])
@auth_required
def gastos_categorizados_item(gasto_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT * FROM contas WHERE usuario_id=? LIMIT 1", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        gasto = conn.execute(
            "SELECT * FROM gastos_categorias WHERE id=? AND conta_id=?",
            (gasto_id, conta['id'])
        ).fetchone()
        if not gasto:
            return jsonify({'erro': 'Lançamento não encontrado'}), 404

        if not gasto['transacao_codigo']:
            return jsonify({'erro': 'Lançamento antigo sem vínculo de transação. Exclua manualmente e recadastre.'}), 409

        saldo_atual = float(conta['saldo'])
        valor_original = float(gasto['valor'])
        tipo_original = gasto['tipo_movimento']
        saldo_revertido = saldo_atual + valor_original if tipo_original == 'saida' else saldo_atual - valor_original

        if request.method == 'DELETE':
            conn.execute("UPDATE contas SET saldo=? WHERE id=?", (round(saldo_revertido, 2), conta['id']))
            conn.execute("DELETE FROM gastos_categorias WHERE id=? AND conta_id=?", (gasto_id, conta['id']))
            conn.execute(
                """UPDATE transacoes
                   SET status='cancelada', descricao=?, saldo_posterior=?
                   WHERE codigo=?""",
                (f"[ESTORNADO] {gasto['descricao']} ({gasto['categoria']})", round(saldo_revertido, 2), gasto['transacao_codigo'])
            )
            registrar_lancamento(
                conn, conta['id'], 'estorno_gasto', 'credito' if tipo_original == 'saida' else 'debito', valor_original,
                saldo_atual, round(saldo_revertido, 2), f'Estorno de lançamento categorizado #{gasto_id}', gasto['transacao_codigo']
            )
            adicionar_notificacao(conn, uid, '🗑️ Lançamento removido', f'Lançamento "{gasto['descricao']}" foi removido com estorno automático.', 'info')
            conn.commit()
            return jsonify({'mensagem': 'Lançamento removido com estorno', 'saldo_atual': round(saldo_revertido, 2)})

        d = parse_json_body() or {}
        tipo_novo = (d.get('tipo_movimento') or gasto['tipo_movimento']).strip().lower()
        categoria_nova = (d.get('categoria') or gasto['categoria']).strip().lower()
        descricao_nova = (d.get('descricao') or gasto['descricao']).strip()
        try:
            valor_novo = float(d.get('valor', valor_original))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Valor inválido'}), 400

        if tipo_novo not in ('entrada', 'saida'):
            return jsonify({'erro': 'Tipo deve ser "entrada" ou "saida"'}), 400
        if not descricao_nova:
            return jsonify({'erro': 'Descrição é obrigatória'}), 400
        if valor_novo <= 0:
            return jsonify({'erro': 'Valor deve ser maior que zero'}), 400

        if tipo_novo == 'saida':
            saldo_disp = saldo_revertido + float(conta['limite_cheque'])
            if valor_novo > saldo_disp:
                return jsonify({'erro': f'Saldo insuficiente. Disponível: R${saldo_disp:.2f}'}), 400
            saldo_final = round(saldo_revertido - valor_novo, 2)
            tipo_tx = 'gasto_saida'
            direcao = 'debito'
        else:
            saldo_final = round(saldo_revertido + valor_novo, 2)
            tipo_tx = 'gasto_entrada'
            direcao = 'credito'

        conn.execute("UPDATE contas SET saldo=? WHERE id=?", (saldo_final, conta['id']))
        conn.execute(
            """UPDATE gastos_categorias
               SET tipo_movimento=?, categoria=?, descricao=?, valor=?, atualizado_em=datetime('now')
               WHERE id=? AND conta_id=?""",
            (tipo_novo, categoria_nova, descricao_nova, valor_novo, gasto_id, conta['id'])
        )
        conn.execute(
            """UPDATE transacoes
               SET tipo=?, valor=?, descricao=?, saldo_anterior=?, saldo_posterior=?
               WHERE codigo=?""",
            (tipo_tx, valor_novo, f'{descricao_nova} ({categoria_nova})', round(saldo_revertido, 2), saldo_final, gasto['transacao_codigo'])
        )
        conn.execute(
            """UPDATE ledger_lancamentos
               SET tipo=?, direcao=?, valor=?, saldo_antes=?, saldo_depois=?, descricao=?
               WHERE transacao_codigo=?""",
            (tipo_tx, direcao, valor_novo, round(saldo_revertido, 2), saldo_final, f'Atualizado: {descricao_nova} [{categoria_nova}]', gasto['transacao_codigo'])
        )
        adicionar_notificacao(conn, uid, '✏️ Lançamento atualizado', f'Lançamento "{descricao_nova}" foi atualizado.', 'info')

        conn.commit()
        return jsonify({'mensagem': 'Lançamento atualizado com sucesso', 'saldo_atual': saldo_final})
    finally:
        conn.close()

@app.route('/api/orcamentos-categorias', methods=['GET', 'POST'])
@auth_required
def orcamentos_categorias():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=? LIMIT 1", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        mes_ref = datetime.now().strftime('%Y-%m')
        inicio_mes = datetime.now().strftime('%Y-%m-01 00:00:00')

        if request.method == 'GET':
            rows = conn.execute(
                """SELECT * FROM orcamentos_categorias
                   WHERE conta_id=? AND mes_ref=?
                   ORDER BY categoria ASC""",
                (conta['id'], mes_ref)
            ).fetchall()
            gastos = conn.execute(
                """SELECT categoria, COALESCE(SUM(valor),0) AS total
                   FROM gastos_categorias
                   WHERE conta_id=? AND tipo_movimento='saida' AND criado_em >= ?
                   GROUP BY categoria""",
                (conta['id'], inicio_mes)
            ).fetchall()
            mapa = {r['categoria']: float(r['total'] or 0) for r in gastos}

            lista = []
            for r in rows:
                limite = float(r['limite_mensal'] or 0)
                executado = float(mapa.get(r['categoria'], 0))
                percentual = (executado / limite * 100.0) if limite > 0 else 0.0
                status = 'ok'
                if percentual >= 100:
                    status = 'estourado'
                elif percentual >= 80:
                    status = 'alerta'
                lista.append({
                    'id': r['id'],
                    'categoria': r['categoria'],
                    'mes_ref': r['mes_ref'],
                    'limite_mensal': round(limite, 2),
                    'executado': round(executado, 2),
                    'percentual': round(percentual, 1),
                    'status': status
                })

            return jsonify({'orcamentos': lista})

        d = parse_json_body()
        if not d:
            return jsonify({'erro': 'JSON inválido'}), 400

        categoria = (d.get('categoria') or '').strip().lower()
        try:
            limite_mensal = float(d.get('limite_mensal', 0))
        except (TypeError, ValueError):
            return jsonify({'erro': 'Limite mensal inválido'}), 400

        if not categoria:
            return jsonify({'erro': 'Categoria é obrigatória'}), 400
        if limite_mensal <= 0:
            return jsonify({'erro': 'Limite mensal deve ser maior que zero'}), 400

        conn.execute(
            """INSERT INTO orcamentos_categorias (conta_id, categoria, limite_mensal, mes_ref)
               VALUES (?,?,?,?)
               ON CONFLICT(conta_id, categoria, mes_ref)
               DO UPDATE SET limite_mensal=excluded.limite_mensal""",
            (conta['id'], categoria, limite_mensal, mes_ref)
        )
        conn.commit()
        return jsonify({'mensagem': 'Orçamento salvo com sucesso'})
    finally:
        conn.close()

@app.route('/api/orcamentos-categorias/<int:orcamento_id>', methods=['DELETE'])
@auth_required
def excluir_orcamento_categoria(orcamento_id):
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=? LIMIT 1", (uid,)).fetchone()
        if not conta:
            return jsonify({'erro': 'Conta não encontrada'}), 404

        conn.execute("DELETE FROM orcamentos_categorias WHERE id=? AND conta_id=?", (orcamento_id, conta['id']))
        conn.commit()
        return jsonify({'mensagem': 'Orçamento removido'})
    finally:
        conn.close()

# ─────────────────────────────────────────────
# ROTAS: NOTIFICAÇÕES
# ─────────────────────────────────────────────

@app.route('/api/ledger', methods=['GET'])
@auth_required
def ledger_extrato():
    conn = get_db()
    try:
        uid = request.user['usuario_id']
        conta = conn.execute("SELECT id FROM contas WHERE usuario_id=? LIMIT 1", (uid,)).fetchone()
        if not conta:
            return jsonify({'lancamentos': []})

        limit = int(request.args.get('limit', 100))
        if limit < 1 or limit > 500:
            return jsonify({'erro': 'Use limit entre 1 e 500'}), 400

        rows = conn.execute(
            """SELECT * FROM ledger_lancamentos
               WHERE conta_id=?
               ORDER BY criado_em DESC
               LIMIT ?""",
            (conta['id'], limit)
        ).fetchall()
        return jsonify({'lancamentos': [dict(r) for r in rows]})
    finally:
        conn.close()

@app.route('/api/notificacoes', methods=['GET'])
@auth_required
def notificacoes():
    conn = get_db()
    uid = request.user['usuario_id']
    notifs = conn.execute(
        "SELECT * FROM notificacoes WHERE usuario_id=? ORDER BY criado_em DESC LIMIT 20", (uid,)
    ).fetchall()
    conn.close()
    return jsonify({'notificacoes': [dict(n) for n in notifs]})

@app.route('/api/notificacoes/ler', methods=['POST'])
@auth_required
def marcar_lidas():
    conn = get_db()
    uid = request.user['usuario_id']
    conn.execute("UPDATE notificacoes SET lida=1 WHERE usuario_id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({'mensagem': 'Notificações marcadas como lidas'})

# ─────────────────────────────────────────────
# ROTAS: DASHBOARD / ANALYTICS
# ─────────────────────────────────────────────

@app.route('/api/dashboard', methods=['GET'])
@auth_required
def dashboard():
    conn = get_db()
    uid = request.user['usuario_id']
    conta = conn.execute("SELECT * FROM contas WHERE usuario_id=?", (uid,)).fetchone()
    if not conta:
        conn.close()
        return jsonify({'erro': 'Conta não encontrada'}), 404

    cid = conta['id']

    # Últimas transações
    txs = conn.execute("""
        SELECT * FROM transacoes
        WHERE conta_origem=? OR conta_destino=?
        ORDER BY criado_em DESC LIMIT 5
    """, (cid, cid)).fetchall()

    # Gastos por tipo (últimos 30 dias)
    gastos = conn.execute("""
        SELECT tipo, SUM(valor) as total FROM transacoes
        WHERE conta_origem=? AND criado_em > datetime('now', '-30 days')
        GROUP BY tipo
    """, (cid,)).fetchall()

    # Entradas/Saídas mensais
    entradas = conn.execute("""
        SELECT SUM(valor) FROM transacoes
        WHERE conta_destino=? AND criado_em > datetime('now', '-30 days')
        AND tipo NOT IN ('emprestimo')
    """, (cid,)).fetchone()[0] or 0

    saidas = conn.execute("""
        SELECT SUM(valor) FROM transacoes
        WHERE conta_origem=? AND criado_em > datetime('now', '-30 days')
    """, (cid,)).fetchone()[0] or 0

    # Investimentos
    invs = conn.execute("SELECT COUNT(*), COALESCE(SUM(valor_atual),0) FROM investimentos WHERE conta_id=? AND status='ativo'", (cid,)).fetchone()

    # Empréstimos ativos
    emps = conn.execute("SELECT COUNT(*) FROM emprestimos WHERE conta_id=? AND status='ativo'", (cid,)).fetchone()

    # Dívidas ativas
    dividas = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(valor_total - valor_pago),0) FROM dividas WHERE conta_id=? AND status='ativa'",
        (cid,)
    ).fetchone()

    boletos = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(valor_atual),0) FROM boletos WHERE conta_id=? AND status IN ('pendente','atrasado')",
        (cid,)
    ).fetchone()

    # Notificações não lidas
    nao_lidas = conn.execute("SELECT COUNT(*) FROM notificacoes WHERE usuario_id=? AND lida=0", (uid,)).fetchone()[0]

    risco = calcular_score_risco(conn, uid)
    limiar_otp = limiar_otp_dinamico(conn, uid)
    cenario_ux = decidir_cenario_ux(conn, uid)
    cfg = conn.execute("SELECT tom_comunicacao, dashboard_ordem_ativa, dashboard_ordem_widgets FROM automacao_config WHERE usuario_id=?", (uid,)).fetchone()
    tom_comunicacao = cfg['tom_comunicacao'] if cfg and cfg['tom_comunicacao'] else 'neutro'
    ordem_ativa = int(cfg['dashboard_ordem_ativa']) if cfg and cfg['dashboard_ordem_ativa'] is not None else 0
    try:
        ordem_widgets = json.loads(cfg['dashboard_ordem_widgets']) if cfg and cfg['dashboard_ordem_widgets'] else []
    except Exception:
        ordem_widgets = []

    conn.close()
    return jsonify({
        'saldo': conta['saldo'],
        'limite_disponivel': conta['limite_cheque'],
        'numero_conta': conta['numero'],
        'agencia': conta['agencia'],
        'ultimas_transacoes': [dict(t) for t in txs],
        'gastos_por_tipo': [dict(g) for g in gastos],
        'entradas_mes': round(entradas, 2),
        'saidas_mes': round(saidas, 2),
        'total_investido': round(invs[1], 2),
        'num_investimentos': invs[0],
        'num_emprestimos': emps[0],
        'num_dividas_ativas': dividas[0],
        'total_dividas_pendentes': round(dividas[1], 2),
        'num_boletos_pendentes': boletos[0],
        'total_boletos_pendentes': round(boletos[1], 2),
        'notificacoes_nao_lidas': nao_lidas,
        'risco_score': risco['score'],
        'risco_nivel': risco['nivel'],
        'risco_fatores': risco['fatores'],
        'limiar_otp': limiar_otp,
        'cenario_ux': cenario_ux,
        'tom_comunicacao': tom_comunicacao,
        'dashboard_ordem_ativa': ordem_ativa,
        'dashboard_ordem_widgets': ordem_widgets
    })

# ─────────────────────────────────────────────
# FRONTEND
# ─────────────────────────────────────────────

@app.route('/')
def index():
    return send_file(os.path.join(os.path.dirname(__file__), 'index.html'))

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'banco': 'NeoBank', 'versao': '1.0'})

if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("  🏦 NeoBank - Sistema Bancário com IA")
    print("="*50)
    print("  ✅ Banco de dados inicializado")
    print("  🚀 Servidor: http://localhost:5000")
    print("  📱 Abra no navegador para usar o sistema")
    print("="*50 + "\n")
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', '5000'))
    app.run(debug=debug_mode, host=host, port=port)
