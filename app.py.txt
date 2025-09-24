import os
import re
import sqlite3
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# carregar variáveis do .env
load_dotenv()

BITLY_TOKEN = os.getenv("BITLY_TOKEN")
AMAZON_TAG = os.getenv("AMAZON_TAG")  # ex: meutag-20

app = Flask(__name__)

# ------------------- FUNÇÕES AUXILIARES -------------------

def get_db():
    conn = sqlite3.connect("db.sqlite")
    conn.execute("""CREATE TABLE IF NOT EXISTS mercadolivre (
                        original_url TEXT PRIMARY KEY,
                        affiliate_url TEXT
                    )""")
    return conn

def extract_asin(url):
    # procura ASIN no link da Amazon
    m = re.search(r"/dp/([A-Z0-9]{10})", url) or re.search(r"/gp/product/([A-Z0-9]{10})", url)
    return m.group(1) if m else None

def build_amazon_aff(url):
    asin = extract_asin(url)
    if not asin:
        return None
    return f"https://www.amazon.com.br/dp/{asin}/?tag={AMAZON_TAG}"

def check_ml_db(url):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT affiliate_url FROM mercadolivre WHERE original_url=?", (url,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def save_ml_link(original, affiliate):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO mercadolivre (original_url, affiliate_url) VALUES (?,?)",
                (original, affiliate))
    conn.commit()
    conn.close()

def shorten_with_bitly(long_url):
    headers = {"Authorization": f"Bearer {BITLY_TOKEN}", "Content-Type": "application/json"}
    data = {"long_url": long_url}
    r = requests.post("https://api-ssl.bitly.com/v4/shorten", json=data, headers=headers)
    if r.status_code == 200:
        return r.json()["link"]
    else:
        return long_url  # fallback

# ------------------- ENDPOINTS -------------------

@app.route("/convert", methods=["POST"])
def convert():
    url = request.json.get("url")
    if not url:
        return jsonify({"error": "URL não fornecida"}), 400

    affiliate = None
    origem = ""

    if "amazon" in url:
        affiliate = build_amazon_aff(url)
        origem = "amazon"
    elif "mercadolivre" in url or "mercado" in url:
        origem = "mercadolivre"
        affiliate = check_ml_db(url)

    if not affiliate and origem == "mercadolivre":
        return jsonify({
            "error": "Link Mercado Livre não cadastrado",
            "msg": "Cadastre manualmente via /add_ml"
        }), 400

    if not affiliate:
        return jsonify({"error": "Não consegui processar esse link"}), 400

    short = shorten_with_bitly(affiliate)

    return jsonify({
        "short": short,
        "affiliate": affiliate,
        "origem": origem
    })

@app.route("/add_ml", methods=["POST"])
def add_ml():
    data = request.json
    original = data.get("original")
    affiliate = data.get("affiliate")
    if not original or not affiliate:
        return jsonify({"error": "Campos 'original' e 'affiliate' obrigatórios"}), 400

    save_ml_link(original, affiliate)
    return jsonify({"msg": "Link ML salvo com sucesso!"})

# ------------------- MAIN -------------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
