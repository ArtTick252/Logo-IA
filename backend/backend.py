import os
from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import openai
import stripe
import jwt
import datetime
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import smtplib

app = Flask(__name__)
CORS(app)

# --- CONFIG ---
openai.api_key = os.getenv("OPENAI_API_KEY")
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///orders.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "supersecretjwtkey")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DOMAIN_URL = os.getenv("DOMAIN_URL", "http://localhost:3000")

db = SQLAlchemy(app)

# --- DB MODELS ---
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

# --- UTILITAIRES JWT ---
def encode_auth_token():
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=12),
        'iat': datetime.datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def decode_auth_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return True
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return False

# --- ROUTES ---

# Auth admin - retourne token JWT si bon mdp
@app.route("/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    if not data or "password" not in data:
        return jsonify({"message": "Password required"}), 400
    if data["password"] == ADMIN_PASSWORD:
        token = encode_auth_token()
        return jsonify({"token": token})
    else:
        return jsonify({"message": "Wrong password"}), 401

# Middleware simple pour protéger routes admin
def admin_required(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"message": "Token missing"}), 401
        token = auth_header.split(" ")[1]
        if not decode_auth_token(token):
            return jsonify({"message": "Invalid or expired token"}), 401
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Liste commandes admin protégée
@app.route("/admin/orders", methods=["GET"])
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.date.desc()).all()
    return jsonify([{
        "id": o.id,
        "name": o.name,
        "email": o.email,
        "image_url": o.image_url,
        "date": o.date.isoformat()
    } for o in orders])

# Création session Stripe
@app.route("/create-checkout-session", methods=["POST"])
def create_checkout_session():
    data = request.json
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                'price_data': {
                    'currency': 'eur',
                    'product_data': {
                        'name': f"Logo IA pour {data['name']}",
                    },
                    'unit_amount': 500,  # 5 euros en centimes
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=DOMAIN_URL + f"/success?email={data['email']}&name={data['name']}",
            cancel_url=DOMAIN_URL + "/cancel",
        )
        return jsonify({'url': session.url})
    except Exception as e:
        return jsonify(error=str(e)), 400

# Génération logo après paiement
@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    if not name or not email:
        return jsonify({"message": "Name and email required"}), 400

    # Générer image DALL·E
    try:
        response = openai.Image.create(
            prompt=f"Minimal vector-style logo for {name}",
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']
    except Exception as e:
        return jsonify({"message": "Error generating image", "error": str(e)}), 500

    # Enregistrer commande
    order = Order(name=name, email=email, image_url=image_url)
    db.session.add(order)
    db.session.commit()

    # Envoyer email
    try:
        msg = MIMEMultipart()
        msg['Subject'] = f"Votre logo IA pour {name}"
        msg['From'] = os.getenv("EMAIL_FROM")
        msg['To'] = email
        img_data = requests.get(image_url).content
        msg.attach(MIMEImage(img_data, name="logo.png"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(os.getenv("EMAIL_FROM"), os.getenv("EMAIL_PASS"))
            server.send_message(msg)
    except Exception as e:
        print("Error sending email:", e)

    return jsonify({"status": "ok", "image_url": image_url})


if __name__ == "__main__":
    app.run(debug=True)
