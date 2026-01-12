from flask import Flask, request, jsonify
from flask_cors import CORS
import imaplib
import email
from email.header import decode_header
import os

app = Flask(__name__)
CORS(app)  # Permite acesso de qualquer origem

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
            "GET /message?id=X": "Lê email específico",
            "GET /delete?id=X": "Deleta email"
        },
        "examples": {
            "inbox": f"{request.host_url}inbox",
            "message": f"{request.host_url}message?id=1",
            "delete": f"{request.host_url}delete?id=1"
        }
    }), 200

@app.route('/inbox', methods=['GET'])
def inbox():
    """Lista emails da inbox"""
    result = email_api.get_inbox()
    status = 200 if result.get("success") else 500
    return jsonify(result), status

@app.route('/message', methods=['GET'])
def message():
    """Lê uma mensagem específica"""
    message_id = request.args.get('id')
    if not message_id:
        return jsonify({"success": False, "error": "Parâmetro 'id' obrigatório"}), 400
    
    result = email_api.get_message(message_id)
    status = 200 if result.get("success") else 500
    return jsonify(result), status

@app.route('/delete', methods=['GET'])
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
