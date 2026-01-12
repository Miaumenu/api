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
API_KEY = "80f0408f19msh84c47582323e83dp19f0e5jsn12964d13628d"
API_HOST = "api-8be0.onrender.com"

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
        p_key = request.headers.get('x-rapidapi-key')
        p_host = request.headers.get('x-rapidapi-host')
        if p_key != API_KEY or p_host != API_HOST:
            return jsonify({"success": False, "error": "Credenciais inválidas"}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- CLASSE IMAP COMPLETA ---
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

    def get_ids(self, folder="inbox", order="desc"):
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        try:
            mail.select(f'"{folder}"')
            _, messages = mail.search(None, "ALL")
            ids = [i.decode() for i in messages[0].split()]
            if order == "desc": ids.reverse()
            mail.close()
            mail.logout()
            return {"success": True, "ids": ids}
        except Exception as e: return {"success": False, "error": str(e)}

    def get_token_inbox(self, token):
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        try:
            mail.select('"inbox"')
            user, domain = self.email_addr.split('@')
            target = f"{user}+{token}@{domain}"
            _, messages = mail.search(None, f'(TO "{target}")')
            ids = [i.decode() for i in messages[0].split()]
            ids.reverse()
            
            emails = []
            for e_id in ids[:10]:
                _, data = mail.fetch(e_id, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                emails.append({
                    "id": e_id,
                    "from": self._decode_text(msg["From"]),
                    "subject": self._decode_text(msg["Subject"]),
                    "date": msg["Date"]
                })
            mail.close()
            mail.logout()
            return {"success": True, "token": token, "emails": emails}
        except Exception as e: return {"success": False, "error": str(e)}

    def get_message_body(self, m_id):
        mail, error = self.connect()
        if error: return {"success": False, "error": error}
        try:
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
            return {"success": True, "body": body}
        except Exception as e: return {"success": False, "error": str(e)}

# Instância única
api = EmailIMAPAPI(**EMAIL_CONFIG)

# --- ENDPOINTS ---

@app.route('/generate-email', methods=['POST'])
@require_api_key
def generate():
    token = str(uuid.uuid4())[:8]
    user, domain = EMAIL_CONFIG["email"].split('@')
    return jsonify({
        "success": True,
        "email": f"{user}+{token}@{domain}",
        "token": token
    })

@app.route('/inbox', methods=['POST'])
@require_api_key
def get_inbox():
    data = request.get_json()
    token = data.get('token')
    if not token: return jsonify({"error": "Token obrigatorio"}), 400
    return jsonify(api.get_token_inbox(token))

@app.route('/message', methods=['GET'])
@require_api_key
def get_msg():
    m_id = request.args.get('id')
    if not m_id: return jsonify({"error": "ID obrigatorio"}), 400
    return jsonify(api.get_message_body(m_id))

@app.route('/ids/latest', methods=['GET'])
@require_api_key
def latest():
    res = api.get_ids()
    if res["success"] and res["ids"]:
        return jsonify({"success": True, "latest_id": res["ids"][0]})
    return jsonify({"success": False, "error": "Vazio"}), 404

@app.route('/folders', methods=['GET'])
@require_api_key
def folders():
    mail, err = api.connect()
    if err: return jsonify({"error": err}), 500
    _, folder_list = mail.list()
    mail.logout()
    return jsonify({"success": True, "folders": [f.decode() for f in folder_list]})

if __name__ == '__main__':
    # Porta padrão para o Render é 10000 ou definida pela env PORT
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
