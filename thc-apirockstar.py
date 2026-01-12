from flask import Flask, request, jsonify
from flask_cors import CORS
import imaplib
import email
from email.header import decode_header
import os
import random
from functools import wraps

app = Flask(__name__)
CORS(app)

# --- CONFIGURAÇÕES ---
API_KEY = "80f0408f19msh84c47582323e83dp19f0e5jsn12964d13628d"
API_HOST = "api-8be0.onrender.com"

EMAIL_CONFIG = {
    "email": "samuelfdsafdsaf4safadsfsdafasd@gmail.com",
    "password": "wkbsannbvnyqhhmf",
    "imap_server": "imap.gmail.com",
    "imap_port": 993
}

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.headers.get('x-rapidapi-key') != API_KEY or \
           request.headers.get('x-rapidapi-host') != API_HOST:
            return jsonify({"success": False, "error": "Credenciais inválidas"}), 403
        return f(*args, **kwargs)
    return decorated_function

class EmailIMAPAPI:
    def __init__(self, email, password, imap_server, imap_port):
        self.email_addr = email
        self.password = password
        self.server = imap_server
        self.port = imap_port
    
    def connect(self):
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            mail.login(self.email_addr, self.password)
            return mail, None
        except Exception as e:
            return None, str(e)

    def _decode_text(self, text):
        if not text: return ""
        try:
            decoded = decode_header(text)
            parts = []
            for content, charset in decoded:
                if isinstance(content, bytes):
                    parts.append(content.decode(charset or "utf-8", errors="ignore"))
                else:
                    parts.append(str(content))
            return "".join(parts)
        except: return str(text)

    def generate_dotted_email(self):
        """Gera um email inserindo pontos aleatórios no nome de usuário"""
        user, domain = self.email_addr.split('@')
        user_list = list(user)
        
        # Define quantos pontos inserir (entre 1 e 5 para não ficar gigante)
        num_dots = random.randint(1, 5)
        # Escolhe posições aleatórias (não pode ser na primeira ou última posição)
        possible_positions = list(range(1, len(user_list)))
        dot_positions = random.sample(possible_positions, min(num_dots, len(possible_positions)))
        
        # Insere os pontos de trás para frente para não alterar os índices
        for pos in sorted(dot_positions, reverse=True):
            user_list.insert(pos, '.')
            
        dotted_user = "".join(user_list)
        return f"{dotted_user}@{domain}"

    def get_token_inbox(self, target_email):
        """Busca emails e filtra EXATAMENTE pelo padrão de pontos"""
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        
        try:
            mail.select('"inbox"')
            # O Gmail trata pontos como iguais no SEARCH, então buscamos todos do usuário base
            # e filtramos manualmente no Python o cabeçalho 'To'
            _, messages = mail.search(None, 'ALL')
            ids = [i.decode() for i in messages[0].split()]
            ids.reverse() # Mais recentes primeiro
            
            emails = []
            # Verifica os últimos 30 emails para encontrar os que batem com o padrão de pontos
            for e_id in ids[:30]:
                _, data = mail.fetch(e_id, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                
                # Pega o destinatário real do cabeçalho
                to_header = msg.get("To", "").lower()
                
                # Filtro rigoroso: só entra se o email com pontos bater exatamente
                if target_email.lower() in to_header:
                    emails.append({
                        "id": e_id,
                        "from": self._decode_text(msg["From"]),
                        "subject": self._decode_text(msg["Subject"]),
                        "date": msg["Date"]
                    })
            
            mail.close()
            mail.logout()
            return {"success": True, "target": target_email, "count": len(emails), "emails": emails}
        except Exception as e: return {"success": False, "error": str(e)}

# Inicialização
api = EmailIMAPAPI(**EMAIL_CONFIG)

# --- ROTAS ---

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Online", "mode": "Dot Aliasing"})

@app.route('/generate-email', methods=['POST'])
@require_api_key
def generate():
    """Gera um email com pontos aleatórios"""
    email_addr = api.generate_dotted_email()
    return jsonify({
        "success": True,
        "email": email_addr,
        "token": email_addr # No sistema de pontos, o próprio email é o token
    })

@app.route('/inbox', methods=['POST'])
@require_api_key
def get_inbox_route():
    """Busca emails que foram enviados para o endereço com pontos específicos"""
    data = request.get_json() or {}
    token = data.get('token') # Aqui o token é o email completo gerado
    if not token: return jsonify({"error": "Envie o 'token' (email gerado)"}), 400
    return jsonify(api.get_token_inbox(token))

@app.route('/message', methods=['GET'])
@require_api_key
def get_msg_route():
    m_id = request.args.get('id')
    if not m_id: return jsonify({"error": "ID obrigatorio"}), 400
    res = api.connect()
    if res[1]: return jsonify({"error": res[1]}), 500
    
    mail = res[0]
    mail.select('"inbox"')
    _, data = mail.fetch(m_id, "(RFC822)")
    msg = email.message_from_bytes(data[0][1])
    
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode(errors="ignore")
                break
    else:
        body = msg.get_payload(decode=True).decode(errors="ignore")
    
    mail.close()
    mail.logout()
    return jsonify({"success": True, "body": body})

@app.route('/ids/latest', methods=['GET'])
@require_api_key
def latest_route():
    mail, err = api.connect()
    if err: return jsonify({"error": err}), 500
    mail.select('"inbox"')
    _, messages = mail.search(None, "ALL")
    ids = messages[0].split()
    latest_id = ids[-1].decode() if ids else None
    mail.logout()
    return jsonify({"success": True, "latest_id": latest_id})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
