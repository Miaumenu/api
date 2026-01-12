from flask import Flask, request, jsonify
from flask_cors import CORS
import imaplib
import email
from email.header import decode_header
import os
import uuid
from functools import wraps

app = Flask(__name__)
CORS(app)

# --- CONFIGURAÇÕES ---
# Mantenha suas chaves aqui
API_KEY = "80f0408f19msh84c47582323e83dp19f0e5jsn12964d13628d"
API_HOST = "api-8be0.onrender.com"

# Credenciais do Gmail
EMAIL_CONFIG = {
    "email": "samuelfdsafdsaf4safadsfsdafasd@gmail.com",
    "password": "wkbsannbvnyqhhmf",
    "imap_server": "imap.gmail.com",
    "imap_port": 993
}

# --- DECORATOR DE SEGURANÇA ---
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Para facilitar testes locais, se não tiver header, verifica se é localhost
        # Mas para produção, exige os headers
        provided_key = request.headers.get('x-rapidapi-key')
        provided_host = request.headers.get('x-rapidapi-host')
        
        if not provided_key or not provided_host:
            return jsonify({"success": False, "error": "Headers obrigatórios ausentes"}), 401
        
        if provided_key != API_KEY or provided_host != API_HOST:
            return jsonify({"success": False, "error": "Credenciais inválidas"}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# --- CLASSE IMAP ---
class EmailIMAPAPI:
    # CORREÇÃO DO ERRO DE DEPLOY AQUI:
    # Os nomes dos argumentos devem bater com as chaves do EMAIL_CONFIG
    def __init__(self, email, password, imap_server, imap_port):
        self.email_addr = email  # Armazena internamente
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
            decoded_list = decode_header(text)
            decoded_text = ""
            for content, encoding in decoded_list:
                if isinstance(content, bytes):
                    decoded_text += content.decode(encoding or "utf-8", errors="ignore")
                else:
                    decoded_text += str(content)
            return decoded_text
        except:
            return str(text)

    def generate_temp_email(self):
        """Gera um email com alias (+token)"""
        # Gera token curto de 8 caracteres
        token = str(uuid.uuid4())[:8]
        
        # Separa usuario e dominio
        if '@' in self.email_addr:
            user_part, domain_part = self.email_addr.split('@')
            # Cria: usuario+token@gmail.com
            generated_email = f"{user_part}+{token}@{domain_part}"
        else:
            return {"success": False, "error": "Email configurado inválido"}
        
        return {
            "success": True,
            "email": generated_email,
            "token": token  # O usuário precisa guardar esse token para ler a inbox
        }

    def get_token_inbox(self, token):
        """Busca emails enviados especificamente para o alias do token"""
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        
        try:
            mail.select('"inbox"')
            
            # Reconstrói o email alvo
            user_part, domain_part = self.email_addr.split('@')
            target_email = f"{user_part}+{token}@{domain_part}"
            
            # Busca no IMAP: TO "email+token@gmail.com"
            search_criterion = f'(TO "{target_email}")'
            status, messages = mail.search(None, search_criterion)
            
            if status != "OK":
                return {"success": False, "error": "Erro na busca"}

            email_ids = messages[0].split()
            email_ids.reverse() # Mais recentes primeiro
            
            results = []
            # Limite de 10 emails para não travar
            for e_id in email_ids[:10]:
                _, msg_data = mail.fetch(e_id, "(RFC822)")
                msg = email.message_from_bytes(msg_data[0][1])
                
                # Extrai corpo simples
                body = "Conteúdo complexo/HTML"
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(errors="ignore")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(errors="ignore")

                results.append({
                    "id": e_id.decode(),
                    "to": target_email,
                    "from": self._decode_text(msg.get("From")),
                    "subject": self._decode_text(msg.get("Subject")),
                    "date": msg.get("Date"),
                    "body_preview": body[:100] # Preview de 100 chars
                })
            
            mail.close()
            mail.logout()
            
            return {
                "success": True,
                "token": token,
                "email_used": target_email,
                "count": len(results),
                "emails": results
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}

    # Deletar tudo (Cuidado)
    def delete_all(self, folder="inbox"):
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        try:
            mail.select(folder)
            status, messages = mail.search(None, "ALL")
            email_ids = messages[0].split()
            for e_id in email_ids:
                mail.store(e_id, '+FLAGS', '\\Deleted')
            mail.expunge()
            mail.close()
            mail.logout()
            return {"success": True, "message": f"Limpou {len(email_ids)} emails"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Inicializa a API com a correção do **kwargs
api = EmailIMAPAPI(**EMAIL_CONFIG)

# --- ROTAS ---

@app.route('/', methods=['GET'])
def home():
    return jsonify({"status": "Online", "msg": "API Rockstar Email"})

# 1. Gerar Email Temporário
@app.route('/generate-email', methods=['POST'])
@require_api_key
def generate_email_route():
    """Retorna { email: 'user+token@gmail.com', token: 'token' }"""
    return jsonify(api.generate_temp_email())

# 2. Ler Inbox do Token
@app.route('/inbox', methods=['POST'])
@require_api_key
def inbox_token_route():
    """Recebe JSON { token: '...' } e retorna emails desse token"""
    data = request.get_json()
    
    # Suporte para receber tanto 'token' quanto 'email' (extraindo token)
    token = data.get('token')
    
    if not token:
        return jsonify({"success": False, "error": "Envie o 'token' gerado no /generate-email"}), 400
        
    return jsonify(api.get_token_inbox(token))

# 3. Deletar Tudo
@app.route('/delete-all', methods=['DELETE'])
@require_api_key
def delete_all_route():
    if request.args.get('confirm') != "true":
        return jsonify({"error": "Confirme com ?confirm=true"}), 400
    return jsonify(api.delete_all())

if __name__ == '__main__':
    # Render fornece a porta na variável de ambiente PORT
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
