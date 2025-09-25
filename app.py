import os
import re
import sqlite3
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# carregar variáveis do arquivo .env
load_dotenv()

BITLY_TOKEN = os.getenv("BITLY_TOKEN")      # token do Bitly (opcional)
AMAZON_TAG = os.getenv("AMAZON_TAG")        # ex: meutag-20
MLM_CAMPAIGN = os.getenv("MLM_CAMPAIGN")    # ex: campanhaxpto (se tiver)

app = Flask(__name__)

# ---------------- FUNÇÕES AUXILIARES ----------------

def get_db():
    """Cria ou abre o banco de cache."""
    conn = sqlite3.connect("db.sqlite")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            original_url TEXT PRIMARY KEY,
            affiliate_url TEXT
        )
    """)
    return conn

def extract_asin(url):
    """Extrai o ASIN (código do produto) do link da Amazon."""
    m = re.search(r"/dp/([A-Z0-9]{10})", url) or re.search(r"/gp/product/([A-Z0-9]{10})", url)
    return m.group(1) if m else None

def build_amazon_affiliate(url):
    """Gera link de afiliado da Amazon."""
    asin = extract_asin(url)
    if asin and AMAZON_TAG:
        return f"https://www.amazon.com/dp/{asin}/?tag={AMAZON_TAG}"
    return url

def build_mercadolivre_affiliate(url):
    """Gera link de afiliado do Mercado Livre (simples)."""
    if MLM_CAMPAIGN:
        return f"{url}?campaign={MLM_CAMPAIGN}"
    return url

def shorten_url(long_url):
    """Encurta o link usando Bitly (opcional)."""
    if not BITLY_TOKEN:
        return long_url
    headers = {"Authorization": f"Bearer {BITLY_TOKEN}"}
    r = requests.post("https://api-ssl.bitly.com/v4/shorten",
                      json={"long_url": long_url}, headers=headers)
    if r.status_code == 200:
        return r.json().get("link", long_url)
    return long_url

# ---------------- ROTAS ----------------

@app.route("/")
def home():
    return "✅ API rodando! Use /convert?url=SEULINK"

@app.route("/convert", methods=["GET"])
def convert():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "Parâmetro 'url' é obrigatório"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT affiliate_url FROM links WHERE original_url=?", (url,))
    row = cur.fetchone()

    if row:
        return jsonify({"affiliate_url": row[0]})

    # Gerar link de afiliado
    if "amazon." in url:
        aff_url = build_amazon_affiliate(url)
    elif "mercadolivre.com" in url:
        aff_url = build_mercadolivre_affiliate(url)
    else:
        aff_url = url

    # Encurtar (opcional)
    aff_url = shorten_url(aff_url)

    # Salvar no banco
    cur.execute("INSERT OR REPLACE INTO links (original_url, affiliate_url) VALUES (?, ?)", (url, aff_url))
    conn.commit()
    conn.close()

    return jsonify({"affiliate_url": aff_url})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
