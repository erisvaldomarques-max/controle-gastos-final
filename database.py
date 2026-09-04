import sqlite3
from datetime import datetime

def criar_banco():
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    
    # Cria a tabela de transações
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL CHECK (tipo IN ('RECEITA', 'DESPESA')),
            categoria TEXT,
            descricao TEXT,
            valor REAL NOT NULL,
            data_ocorrencia TEXT,
            origem TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados criado com sucesso!")

def salvar_transacao(tipo, categoria, descricao, valor, origem='WHATSAPP'):
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    
    data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        INSERT INTO transacoes (tipo, categoria, descricao, valor, data_ocorrencia, origem)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tipo, categoria, descricao, valor, data_atual, origem))
    
    conn.commit()
    conn.close()

def buscar_transacoes_por_mes():
    conn = sqlite3.connect('financas.db')
    cursor = conn.cursor()
    
    # Busca todas as transações do mês atual
    cursor.execute('''
        SELECT tipo, categoria, descricao, valor, data_ocorrencia 
        FROM transacoes 
        WHERE strftime('%m', data_ocorrencia) = strftime('%m', 'now')
        ORDER BY data_ocorrencia DESC
    ''')
    
    transacoes = cursor.fetchall()
    conn.close()
    return transacoes

# Executa uma vez para criar o banco
if __name__ == '__main__':
    criar_banco()