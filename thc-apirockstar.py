from flask import Flask, request, jsonify
from flask_cors import CORS
import imaplib
import email
from email.header import decode_header
import os
from functools import wraps

app = Flask(__name__)
CORS(app)  # Permite acesso cross-origin

# --- CONFIGURAÇÕES E CONSTANTES ---
API_KEY = "80f0408f19msh84c47582323e83dp19f0e5jsn12964d13628d"
API_HOST = "api-8be0.onrender.com"

# Credenciais do Email (Hardcoded conforme solicitado)
EMAIL_CONFIG = {
    "email": "samuelfdsafdsaf4safadsfsdafasd@gmail.com",
    "password": "wkbsannbvnyqhhmf",
    "imap_server": "imap.gmail.com",
    "imap_port": 993
}

# --- DECORATOR DE AUTENTICAÇÃO ---
def require_api_key(f):
    """Verifica se os headers x-rapidapi-key e host estão corretos."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('x-rapidapi-key')
        provided_host = request.headers.get('x-rapidapi-host')
        
        if not provided_key or not provided_host:
            return jsonify({"success": False, "error": "Headers obrigatórios ausentes"}), 401
        
        if provided_key != API_KEY or provided_host != API_HOST:
            return jsonify({"success": False, "error": "Credenciais de API inválidas"}), 403
        
        return f(*args, **kwargs)
    return decorated_function

# --- CLASSE DE GERENCIAMENTO IMAP ---
class EmailIMAPAPI:
    def __init__(self, email_addr, password, server, port):
        self.email_addr = email_addr
        self.password = password
        self.server = server
        self.port = port
    
    def connect(self):
        """Estabelece conexão SSL com o servidor IMAP."""
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            mail.login(self.email_addr, self.password)
            return mail, None
        except Exception as e:
            return None, str(e)

    def _decode_text(self, text):
        """Helper para decodificar assuntos e remetentes."""
        if not text: return ""
        decoded_list = decode_header(text)
        decoded_text = ""
        for content, encoding in decoded_list:
            if isinstance(content, bytes):
                decoded_text += content.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded_text += str(content)
        return decoded_text

    def get_folders(self):
        """Lista todas as pastas disponíveis na conta."""
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        
        try:
            status, folders = mail.list()
            folder_names = []
            for f in folders:
                # Parse simples para extrair o nome da pasta
                name = f.decode().split(' "/" ')[-1].replace('"', '')
                folder_names.append(name)
            
            mail.logout()
            return {"success": True, "folders": folder_names}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_ids(self, folder="inbox", order="desc"):
        """Retorna lista de IDs de emails."""
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        
        try:
            status, _ = mail.select(f'"{folder}"')
            if status != "OK": return {"success": False, "error": f"Pasta '{folder}' não encontrada"}
            
            status, messages = mail.search(None, "ALL")
            ids = messages[0].split()
            
            if order == "desc":
                ids.reverse() # Mais recentes primeiro
                
            ids_str = [i.decode() for i in ids]
            
            mail.close()
            mail.logout()
            return {"success": True, "count": len(ids_str), "ids": ids_str}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_message_content(self, message_id, folder="inbox"):
        """Lê o conteúdo completo de um email específico."""
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        
        try:
            # Tenta selecionar inbox primeiro, ou a pasta especificada se implementado
            mail.select(f'"{folder}"') 
            status, msg_data = mail.fetch(message_id, "(RFC822)")
            
            if status != "OK" or not msg_data or msg_data[0] is None:
                return {"success": False, "error": "Email não encontrado ou ID inválido"}

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Extrair corpo
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    if content_type == "text/plain" and "attachment" not in content_disposition:
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break # Prioriza text/plain
                    elif content_type == "text/html" and not body:
                        body = part.get_payload(decode=True).decode(errors="ignore")
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            return {
                "success": True,
                "data": {
                    "id": message_id,
                    "subject": self._decode_text(msg["Subject"]),
                    "from": self._decode_text(msg["From"]),
                    "date": msg.get("Date"),
                    "body": body
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_message(self, message_id, folder="inbox"):
        """Deleta um único email."""
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        try:
            mail.select(f'"{folder}"')
            mail.store(message_id, '+FLAGS', '\\Deleted')
            mail.expunge()
            mail.close()
            mail.logout()
            return {"success": True, "message": "Email deletado"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_all(self, folder="inbox"):
        """Deleta TODOS os emails de uma pasta."""
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        
        try:
            mail.select(f'"{folder}"')
            status, messages = mail.search(None, "ALL")
            email_ids = messages[0].split()
            
            if not email_ids:
                return {"success": True, "message": "Pasta já está vazia"}
            
            # Marcação em lote
            for e_id in email_ids:
                mail.store(e_id, '+FLAGS', '\\Deleted')
            
            mail.expunge()
            mail.close()
            mail.logout()
            return {"success": True, "message": f"Deletados {len(email_ids)} emails da pasta {folder}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Inicializa a API
api = EmailIMAPAPI(**EMAIL_CONFIG)

# --- ROTAS DA API ---

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "status": "online",
        "service": "IMAP Email API",
        "version": "2.0"
    })

@app.route('/folders', methods=['GET'])
@require_api_key
def list_folders():
    return jsonify(api.get_folders())

@app.route('/ids', methods=['GET'])
@require_api_key
def get_ids():
    folder = request.args.get('folder', 'inbox')
    order = request.args.get('order', 'desc')
    return jsonify(api.get_ids(folder, order))

@app.route('/ids/latest', methods=['GET'])
@require_api_key
def get_latest():
    res = api.get_ids(order="desc")
    if res.get("success") and res.get("ids"):
        return jsonify({"success": True, "latest_id": res["ids"][0]})
    return jsonify({"success": False, "error": "Nenhum email encontrado"}), 404

@app.route('/message', methods=['GET'])
@require_api_key
def get_message():
    msg_id = request.args.get('id')
    folder = request.args.get('folder', 'inbox')
    if not msg_id: return jsonify({"error": "ID necessário"}), 400
    return jsonify(api.get_message_content(msg_id, folder))

@app.route('/delete', methods=['DELETE'])
@require_api_key
def delete_one():
    msg_id = request.args.get('id')
    folder = request.args.get('folder', 'inbox')
    if not msg_id: return jsonify({"error": "ID necessário"}), 400
    return jsonify(api.delete_message(msg_id, folder))

@app.route('/delete-all', methods=['DELETE'])
@require_api_key
def delete_all_route():
    folder = request.args.get('folder', 'inbox')
    confirm = request.args.get('confirm')
    if confirm != "true":
        return jsonify({"error": "Confirmação necessária (?confirm=true)"}), 400
    return jsonify(api.delete_all(folder))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
