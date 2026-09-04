import os
import re
import requests
from flask import Flask, request, jsonify, render_template
from twilio.twiml.messaging_response import MessagingResponse
from database import salvar_transacao, buscar_transacoes_por_mes
import sqlite3
from datetime import datetime

app = Flask(__name__)

# ==========================================
# CONFIGURAÇÃO DO TWILIO - VIA VARIÁVEIS DE AMBIENTE
# ==========================================

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

# ==========================================
# CONFIGURAÇÃO DA GROQ - VIA VARIÁVEIS DE AMBIENTE
# ==========================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ==========================================
# FUNÇÃO PARA TRANSCREVER ÁUDIO
# ==========================================

def transcrever_audio(url_audio):
    """Baixa o áudio do WhatsApp e transcreve usando Groq"""
    try:
        from groq import Groq
        
        print(f"📥 Baixando áudio de: {url_audio}")
        
        # Faz a requisição com autenticação básica do Twilio
        auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        audio_response = requests.get(url_audio, auth=auth, headers=headers)
        
        if audio_response.status_code == 401:
            print("❌ Erro 401: Não autorizado. Verifique seu Auth Token.")
            return None
            
        if audio_response.status_code != 200:
            print(f"❌ Erro ao baixar áudio: {audio_response.status_code}")
            return None
        
        # Salva o arquivo
        with open('temp_audio.ogg', 'wb') as f:
            f.write(audio_response.content)
        
        print("✅ Áudio baixado com sucesso!")
        print("📤 Enviando para Groq para transcrição...")
        
        # Inicializa o cliente Groq
        client = Groq(api_key=GROQ_API_KEY)
        
        # Transcreve o áudio
        with open('temp_audio.ogg', 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-large-v3",
                language="pt",
                response_format="text"
            )
        
        # Remove o arquivo temporário
        os.remove('temp_audio.ogg')
        
        print(f"🎤 Texto transcrito: {transcription}")
        return transcription
        
    except Exception as e:
        print(f"❌ Erro ao transcrever áudio: {e}")
        return None

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def extrair_numero(texto):
    """Extrai o primeiro número (R$) encontrado no texto"""
    padrao = r'R?\$?\s*(\d+[.,]?\d*)'
    match = re.search(padrao, texto)
    if match:
        numero = match.group(1).replace(',', '.')
        return float(numero)
    return None

def extrair_descricao(texto):
    """Remove números e palavras-chave da descrição"""
    texto_sem_valor = re.sub(r'R?\$?\s*\d+[.,]?\d*', '', texto)
    palavras_remover = ['gastei', 'recebi', 'comprei', 'paguei', 'ganhei', 'de', 'no', 'na', 'em']
    for palavra in palavras_remover:
        texto_sem_valor = texto_sem_valor.replace(palavra, '')
    return texto_sem_valor.strip()

def classificar_categoria(descricao):
    """Classifica automaticamente a categoria baseado na descrição"""
    descricao_lower = descricao.lower()
    
    categorias = {
        'Alimentação': ['mercado', 'restaurante', 'ifood', 'comida', 'lanche', 'pizza', 'sushi', 'feira'],
        'Transporte': ['uber', 'taxi', 'gasolina', 'combustivel', 'estacionamento', 'onibus', 'metro', 'carro'],
        'Lazer': ['cinema', 'teatro', 'show', 'shopping', 'viagem', 'hotel', 'bar', 'balada'],
        'Saúde': ['farmácia', 'dentista', 'médico', 'exame', 'plano de saude', 'hospital'],
        'Educação': ['faculdade', 'curso', 'livro', 'material', 'inglês', 'escola'],
        'Casa': ['aluguel', 'condomínio', 'luz', 'agua', 'gas', 'internet', 'iptu', 'energia'],
        'Salário': ['salário', 'salario', 'empresa', 'cliente', 'freela', 'renda', 'pagamento']
    }
    
    for categoria, palavras in categorias.items():
        for palavra in palavras:
            if palavra in descricao_lower:
                return categoria
    
    return 'Outros'

# ==========================================
# ROTA PRINCIPAL DO WHATSAPP
# ==========================================

@app.route("/whatsapp", methods=['POST'])
def whatsapp_bot():
    """Recebe mensagens do WhatsApp e processa (texto e áudio)"""
    
    mensagem = request.form.get('Body', '').lower()
    remetente = request.form.get('From', '')
    
    # Verifica se tem mídia (áudio)
    tem_midia = request.form.get('NumMedia')
    
    if tem_midia and int(tem_midia) > 0:
        url_audio = request.form.get('MediaUrl0')
        
        if url_audio:
            print(f"🎵 Áudio recebido! URL: {url_audio}")
            texto_transcrito = transcrever_audio(url_audio)
            if texto_transcrito:
                mensagem = texto_transcrito.lower()
                print(f"🎤 Áudio transcrito: {mensagem}")
            else:
                print("❌ Falha na transcrição do áudio")
                resp = MessagingResponse()
                resp.message("❌ Não consegui entender o áudio. Tente falar mais claro ou enviar por texto.")
                return str(resp)
    
    # ===== PROCESSAMENTO DA MENSAGEM =====
    resposta = ""
    
    if "saldo" in mensagem or "resumo" in mensagem:
        transacoes = buscar_transacoes_por_mes()
        total_receitas = sum(t[3] for t in transacoes if t[0] == 'RECEITA')
        total_despesas = sum(t[3] for t in transacoes if t[0] == 'DESPESA')
        saldo = total_receitas - total_despesas
        
        resposta = f"📊 *RESUMO DO MÊS*\n"
        resposta += f"💰 Receitas: R$ {total_receitas:.2f}\n"
        resposta += f"💸 Despesas: R$ {total_despesas:.2f}\n"
        resposta += f"📈 Saldo: R$ {saldo:.2f}\n"
        resposta += f"\n📝 Total de transações: {len(transacoes)}"
    
    elif "listar" in mensagem or "extrato" in mensagem:
        transacoes = buscar_transacoes_por_mes()
        if not transacoes:
            resposta = "📭 Nenhuma transação encontrada este mês."
        else:
            resposta = "📋 *ÚLTIMAS TRANSAÇÕES:*\n\n"
            for t in transacoes[:5]:
                tipo_emoji = "✅" if t[0] == 'RECEITA' else "⚠️"
                resposta += f"{tipo_emoji} {t[0]}: R$ {t[3]:.2f} - {t[2]}\n"
    
    elif "excluir" in mensagem:
        conn = sqlite3.connect('financas.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, descricao, valor FROM transacoes 
            WHERE origem = ? 
            ORDER BY id DESC LIMIT 1
        ''', (remetente,))
        
        ultima = cursor.fetchone()
        if ultima:
            cursor.execute('DELETE FROM transacoes WHERE id = ?', (ultima[0],))
            conn.commit()
            resposta = f"🗑️ Transação excluída: {ultima[1]} - R$ {ultima[2]:.2f}"
        else:
            resposta = "❌ Nenhuma transação encontrada para excluir."
        conn.close()
    
    else:
        if any(p in mensagem for p in ['recebi', 'ganhei', 'salário', 'renda', 'freela']):
            tipo = 'RECEITA'
        elif any(p in mensagem for p in ['gastei', 'comprei', 'paguei', 'despesa']):
            tipo = 'DESPESA'
        else:
            resposta = """🤖 *Não entendi!* 
            
Envie assim:
• RECEITA: "Recebi 1500 de salário"
• DESPESA: "Gastei 50 no mercado"

Comandos:
📊 "saldo" - ver resumo
📋 "listar" - ver transações
🗑️ "excluir" - remove última

🎤 ÁUDIO: Fale "Gastei 30 no Uber" que eu entendo!"""
        
        if 'resposta' not in locals() or not resposta:
            valor = extrair_numero(mensagem)
            descricao = extrair_descricao(mensagem)
            categoria = classificar_categoria(descricao)
            
            if valor and descricao:
                salvar_transacao(tipo, categoria, descricao, valor, remetente)
                emoji = "✅" if tipo == 'RECEITA' else "⚠️"
                resposta = f"{emoji} *{tipo} registrada!*\n"
                resposta += f"📝 {descricao}\n"
                resposta += f"💰 R$ {valor:.2f}\n"
                resposta += f"📂 Categoria: {categoria}"
                if tem_midia:
                    resposta += "\n🎤 Reconhecido por áudio!"
            else:
                resposta = "❌ Não consegui identificar o valor. Envie como: 'Gastei 50 no mercado'"
    
    resp = MessagingResponse()
    resp.message(resposta)
    return str(resp)

# ==========================================
# ROTA DO DASHBOARD
# ==========================================

@app.route("/api/dashboard", methods=['GET'])
def dashboard():
    transacoes = buscar_transacoes_por_mes()
    
    total_receitas = sum(t[3] for t in transacoes if t[0] == 'RECEITA')
    total_despesas = sum(t[3] for t in transacoes if t[0] == 'DESPESA')
    saldo = total_receitas - total_despesas
    
    categorias = {}
    for t in transacoes:
        if t[0] == 'DESPESA':
            cat = t[1]
            categorias[cat] = categorias.get(cat, 0) + t[3]
    
    categorias_lista = [{'nome': k, 'valor': v} for k, v in categorias.items()]
    
    return jsonify({
        'saldo': saldo,
        'total_receitas': total_receitas,
        'total_despesas': total_despesas,
        'total_transacoes': len(transacoes),
        'categorias': categorias_lista,
        'transacoes': [
            {
                'tipo': t[0],
                'categoria': t[1],
                'descricao': t[2],
                'valor': t[3],
                'data': t[4]
            } for t in transacoes
        ]
    })

# ==========================================
# ROTA PRINCIPAL
# ==========================================

@app.route("/", methods=['GET'])
def home():
    return "🚀 Bot do WhatsApp está rodando! Envie uma mensagem para testar."

# ==========================================
# INICIALIZAÇÃO
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)