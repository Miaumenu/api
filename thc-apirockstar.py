from flask import Flask, request, jsonify
from flask_cors import CORS
import imaplib
import email
from email.header import decode_header
import os

app = Flask(__name__)
CORS(app)  # Permite acesso de qualquer origem

# API KEY para autenticação
API_KEY = "80f0408f19msh84c47582323e83dp19f0e5jsn12964d13628d"
API_HOST = "api-8be0.onrender.com"

def require_api_key(f):
    """Decorator para verificar API Key (estilo RapidAPI)"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verifica headers estilo RapidAPI
        provided_key = request.headers.get('x-rapidapi-key')
        provided_host = request.headers.get('x-rapidapi-host')
        
        if not provided_key or not provided_host:
            return jsonify({
                "success": False,
                "error": "Headers obrigatórios: x-rapidapi-key e x-rapidapi-host"
            }), 401
        
        if provided_key != API_KEY or provided_host != API_HOST:
            return jsonify({
                "success": False,
                "error": "API Key ou Host inválido"
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

class EmailIMAPAPI:
    """API para acessar emails via IMAP"""
    
    def __init__(self, email_address, password, imap_server="imap.gmail.com", imap_port=993):
        self.email_address = email_address
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
    
    def connect(self):
        """Conecta ao servidor IMAP"""
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.email_address, self.password)
            return mail, None
        except Exception as e:
            return None, str(e)
    
    def get_inbox(self):
        """Lista mensagens da inbox"""
        mail, error = self.connect()
        if error:
            return {"success": False, "error": f"Falha na conexão: {error}"}
        
        try:
            mail.select("inbox")
            status, messages = mail.search(None, "ALL")
            
            if status != "OK":
                return {"success": False, "error": "Falha ao buscar mensagens"}
            
            email_ids = messages[0].split()
            emails_list = []
            
            # Pega últimas 10 mensagens
            for email_id in email_ids[-10:]:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                
                if status == "OK":
                    msg = email.message_from_bytes(msg_data[0][1])
                    
                    # Decodifica subject
                    subject = decode_header(msg["Subject"])[0][0]
                    if isinstance(subject, bytes):
                        subject = subject.decode()
                    
                    # Decodifica from
                    from_ = msg.get("From")
                    
                    emails_list.append({
                        "id": email_id.decode(),
                        "from": from_,
                        "subject": subject,
                        "date": msg.get("Date")
                    })
            
            mail.close()
            mail.logout()
            
            return {"success": True, "data": emails_list}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_message(self, message_id):
        """Lê uma mensagem específica"""
        mail, error = self.connect()
        if error:
            return {"success": False, "error": f"Falha na conexão: {error}"}
        
        try:
            mail.select("inbox")
            status, msg_data = mail.fetch(message_id, "(RFC822)")
            
            if status != "OK":
                return {"success": False, "error": "Mensagem não encontrada"}
            
            msg = email.message_from_bytes(msg_data[0][1])
            
            # Extrai corpo do email
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()
            
            # Decodifica subject
            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()
            
            mail.close()
            mail.logout()
            
            return {
                "success": True,
                "data": {
                    "from": msg.get("From"),
                    "subject": subject,
                    "date": msg.get("Date"),
                    "body": body
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_message(self, message_id):
        """Deleta uma mensagem"""
        mail, error = self.connect()
        if error:
            return {"success": False, "error": f"Falha na conexão: {error}"}
        
        try:
            mail.select("inbox")
            mail.store(message_id, '+FLAGS', '\\Deleted')
            mail.expunge()
            
            mail.close()
            mail.logout()
            
            return {"success": True, "message": "Email deletado"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# CONFIGURAÇÃO
EMAIL_CONFIG = {
    "email": "samuelfdsafdsaf4safadsfsdafasd@gmail.com",
    "password": "wkbsannbvnyqhhmf",
    "imap_server": "imap.gmail.com",
    "imap_port": 993
}

email_api = EmailIMAPAPI(
    EMAIL_CONFIG["email"],
    EMAIL_CONFIG["password"],
    EMAIL_CONFIG["imap_server"],
    EMAIL_CONFIG["imap_port"]
)

# ENDPOINTS
@app.route('/', methods=['GET'])
def home():
    """Página inicial com documentação"""
    return jsonify({
        "message": "API de Email via IMAP",
        "endpoints": {
            "GET /inbox": "Lista emails da inbox",
            "GET /all": "Lista todos os emails com conteúdo completo",
            "GET /message?id=X": "Lê email específico",
            "GET /delete?id=X": "Deleta email"
        },
        "examples": {
            "inbox": f"{request.host_url}inbox",
            "all": f"{request.host_url}all",
            "message": f"{request.host_url}message?id=1",
            "delete": f"{request.host_url}delete?id=1"
        }
    }), 200

@app.route('/all', methods=['GET'])
def get_all():
    """Retorna todos os emails com conteúdo completo"""
    # Primeiro pega a lista de emails
    inbox_result = email_api.get_inbox()
    
    if not inbox_result.get("success"):
        return jsonify(inbox_result), 500
    
    emails = inbox_result.get("data", [])
    full_emails = []
    
    # Para cada email, busca o conteúdo completo
    for email_info in emails:
        msg_id = email_info.get("id")
        if msg_id:
            message_result = email_api.get_message(msg_id)
            if message_result.get("success"):
                full_emails.append({
                    "id": msg_id,
                    "preview": email_info,
                    "full": message_result.get("data")
                })
            else:
                full_emails.append({
                    "id": msg_id,
                    "preview": email_info,
                    "full": None,
                    "error": message_result.get("error")
                })
    
    return jsonify({
        "success": True,
        "total": len(full_emails),
        "emails": full_emails
    }), 200

@app.route('/inbox', methods=['GET'])
def inbox():
    """Lista emails da inbox"""
    result = email_api.get_inbox()
    status = 200 if result.get("success") else 500
    return jsonify(result), status

@app.route('/message', methods=['GET'])
@require_api_key
def message():
    """Lê uma mensagem específica"""
    message_id = request.args.get('id')
    if not message_id:
        return jsonify({"success": False, "error": "Parâmetro 'id' obrigatório"}), 400
    
    result = email_api.get_message(message_id)
    status = 200 if result.get("success") else 500
    return jsonify(result), status

@app.route('/delete', methods=['GET'])
@require_api_key
def delete():
    """Deleta uma mensagem"""
    message_id = request.args.get('id')
    if not message_id:
        return jsonify({"success": False, "error": "Parâmetro 'id' obrigatório"}), 400
    
    result = email_api.delete_message(message_id)
    status = 200 if result.get("success") else 500
    return jsonify(result), status

if __name__ == '__main__':
    # Pega porta do ambiente (para deploy) ou usa 5000
    port = int(os.environ.get('PORT', 5000))
    
    print("="*70)
    print("📧 API DE EMAIL VIA IMAP")
    print("="*70)
    print(f"📡 Porta: {port}")
    print(f"📧 Email: {EMAIL_CONFIG['email']}")
    print("="*70)
    
    # Para produção, use um servidor WSGI como gunicorn
    app.run(host='0.0.0.0', port=port, debug=False)
