from flask import Flask, request, jsonify, g
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Numeric
import uuid
import time
from functools import wraps
import os
from datetime import datetime

from mcp.tools import tahmini_bekleme_suresi, onerilen_menu

app = Flask(__name__)
CORS(app)

# ============================
#  DATABASE CONFIG
# ============================
# Burada varsayılan olarak LOCAL PostgreSQL'e bağlanıyoruz.
# Eğer Docker içinden bağlanacaksan:
#   host.docker.internal kullan (docker-compose.yml'de gösterdim).
#
# Örneğin:
#   postgresql+psycopg2://postgres:SENIN_SIFREN@localhost:5432/ordersdb
#
db_url = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:SENIN_SIFREN@localhost:5432/ordersdb"
)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

ROLE_USER = "USER"
ROLE_RESTAURANT = "RESTAURANT"


# ============================
#  MODELLER (yemek_kuyrugu şeması)
# ============================

class Restaurant(db.Model):
    __tablename__ = "restaurants"
    __table_args__ = {"schema": "yemek_kuyrugu"}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = {"schema": "yemek_kuyrugu"}

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    restaurant_id = db.Column(
        db.Integer,
        db.ForeignKey("yemek_kuyrugu.restaurants.id"),
        nullable=True
    )
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    restaurant = db.relationship("Restaurant", backref="owners", lazy=True)
    orders = db.relationship("Order", backref="user", lazy=True)


class Order(db.Model):
    __tablename__ = "orders"
    __table_args__ = {"schema": "yemek_kuyrugu"}

    id = db.Column(db.String(64), primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("yemek_kuyrugu.users.id"),
        nullable=False
    )
    restaurant_id = db.Column(
        db.Integer,
        db.ForeignKey("yemek_kuyrugu.restaurants.id"),
        nullable=False
    )

    amount = db.Column(Numeric(10, 2), nullable=False)
    items = db.Column(JSONB, nullable=False)

    status = db.Column(db.String(32), nullable=False)
    transaction_id = db.Column(db.String(64))

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    last_updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now()
    )

    status_history = db.Column(JSONB, nullable=False, default=list)


# Session'lar RAM'de tutuluyor (sadece /me/orders için)
sessions = {}  # token -> user_id


# ============================
#  YARDIMCI FUNCTIONS
# ============================

def auth_required(role: str | None = None):
    """
    Login zorunlu endpoint'ler için decorator.
    Sadece /me/orders için kullanıyoruz, restoran uçlarında yok.
    """
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get('Authorization')

            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({
                    "message": "Token eksik veya formatı hatalı (Bearer <token>).",
                    "access": "denied"
                }), 401

            token = auth_header.split(' ')[1]
            user_id = sessions.get(token)

            if not user_id:
                return jsonify({
                    "message": "Geçersiz veya süresi geçmiş oturum token'ı.",
                    "access": "denied"
                }), 401

            user = User.query.get(user_id)
            if not user:
                return jsonify({
                    "message": "Kullanıcı bulunamadı.",
                    "access": "denied"
                }), 401

            if role is not None and user.role != role:
                return jsonify({
                    "message": f"Bu işlem için gerekli rol: {role}",
                    "access": "denied"
                }), 403

            g.current_user = user
            return f(*args, **kwargs)
        return decorated
    return wrapper


def add_status_history(order: Order, new_status: str, reason: str | None = None):
    """Siparişin status + history bilgisini günceller."""
    now = datetime.now().astimezone()
    history = order.status_history or []
    entry = {
        "status": new_status,
        "timestamp": now.isoformat()
    }
    if reason:
        entry["reason"] = reason
    history.append(entry)
    order.status_history = history
    order.status = new_status
    order.last_updated_at = now
    return order


def order_to_dict(order: Order):
    return {
        "id": order.id,
        "status": order.status,
        "amount": float(order.amount) if order.amount is not None else None,
        "items": order.items,
        "user_id": order.user_id,
        "restaurant_id": order.restaurant_id,
        "transaction_id": order.transaction_id,
        "created_at": order.created_at.timestamp() if order.created_at else None,
        "last_updated_at": order.last_updated_at.timestamp() if order.last_updated_at else None,
        "status_history": order.status_history,
    }


# ============================
#  HEALTHCHECK
# ============================

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "service": "order-api",
        "timestamp": time.time()
    }), 200


# ============================
#  AUTH: REGISTER / LOGIN
# ============================

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")
    role = data.get("role")
    restaurant_id = data.get("restaurant_id")

    if not username or not password or not role:
        return jsonify({"message": "username, password ve role zorunludur."}), 400

    if role not in [ROLE_USER, ROLE_RESTAURANT]:
        return jsonify({"message": f"role sadece {ROLE_USER} veya {ROLE_RESTAURANT} olabilir."}), 400

    if role == ROLE_RESTAURANT and restaurant_id is None:
        return jsonify({"message": "Restoran sahipleri için restaurant_id zorunludur."}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Bu kullanıcı adı zaten alınmış."}), 400

    if restaurant_id is not None:
        rest = Restaurant.query.get(restaurant_id)
        if not rest:
            return jsonify({"message": "Verilen restaurant_id mevcut değil."}), 400

    user = User(
        username=username,
        password=password,
        role=role,
        restaurant_id=restaurant_id if role == ROLE_RESTAURANT else None
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({
        "message": "Kayıt başarılı.",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "restaurant_id": user.restaurant_id
        }
    }), 201


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}

    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"message": "username ve password zorunludur."}), 400

    user = User.query.filter_by(username=username, password=password).first()
    if not user:
        return jsonify({"message": "Kullanıcı adı veya şifre hatalı."}), 401

    token = str(uuid.uuid4())
    sessions[token] = user.id

    return jsonify({
        "message": "Giriş başarılı.",
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "restaurant_id": user.restaurant_id
        }
    }), 200


# ============================
#  SİPARİŞ OLUŞTUR / GÖSTER
# ============================

@app.route('/order', methods=['POST'])
def create_order():
    data = request.get_json(silent=True) or {}

    required_fields = ['user_id', 'restaurant_id', 'amount', 'items']
    missing = [f for f in required_fields if f not in data]
    if missing:
        return jsonify({
            "message": "Eksik alanlar var.",
            "reason": f"Eksik alanlar: {', '.join(missing)}"
        }), 400

    try:
        amount = float(data['amount'])
    except (ValueError, TypeError):
        return jsonify({
            "message": "Ödeme başarısız.",
            "reason": "Geçersiz tutar formatı."
        }), 400

    if amount > 1000:
        return jsonify({
            "message": "Ödeme başarısız.",
            "reason": "Limit aşıldı (Simülasyon Hatası)."
        }), 400

    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({"message": "Verilen user_id için kullanıcı bulunamadı."}), 400

    restaurant = Restaurant.query.get(data['restaurant_id'])
    if not restaurant:
        return jsonify({"message": "Verilen restaurant_id için restoran bulunamadı."}), 400

    ts = int(time.time())
    order_id = f"ORD-{ts}-{str(uuid.uuid4())[:3]}"
    transaction_id = f"TX-{ts}-{str(uuid.uuid4())[:4]}"

    now = datetime.now().astimezone()
    initial_history = [{
        "status": "PAYMENT_SUCCESS",
        "timestamp": now.isoformat(),
        "reason": "Ödeme başarıyla alındı, restoran onayı bekleniyor."
    }]

    order = Order(
        id=order_id,
        user_id=user.id,
        restaurant_id=restaurant.id,
        amount=amount,
        items=data['items'],
        status="PAYMENT_SUCCESS",
        transaction_id=transaction_id,
        created_at=now,
        last_updated_at=now,
        status_history=initial_history
    )
    db.session.add(order)
    db.session.commit()

    return jsonify({
        "message": "Siparişiniz başarıyla alındı ve restoran onayı bekliyor.",
        "order_id": order.id,
        "status": order.status,
        "transaction_id": order.transaction_id,
        "next_step": "Restoran sahibinin siparişi onaylaması veya reddetmesi bekleniyor."
    }), 202


@app.route('/order/<string:order_id>', methods=['GET'])
def get_order_status(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"message": "Sipariş bulunamadı."}), 404
    return jsonify(order_to_dict(order)), 200


@app.route('/orders', methods=['GET'])
def list_orders():
    user_id = request.args.get('user_id')
    status = request.args.get('status')

    q = Order.query
    if user_id is not None:
        q = q.filter(Order.user_id == int(user_id))
    if status is not None:
        q = q.filter(Order.status == status)

    orders = q.order_by(Order.created_at.desc()).all()
    return jsonify([order_to_dict(o) for o in orders]), 200


@app.route('/me/orders', methods=['GET'])
@auth_required()
def list_my_orders():
    user: User = g.current_user
    if user.role == ROLE_USER:
        q = Order.query.filter_by(user_id=user.id)
    else:  # RESTAURANT
        if user.restaurant_id is None:
            return jsonify({"message": "Bu restoran kullanıcısının restaurant_id bilgisi yok."}), 400
        q = Order.query.filter_by(restaurant_id=user.restaurant_id)

    orders = q.order_by(Order.created_at.desc()).all()
    return jsonify([order_to_dict(o) for o in orders]), 200


@app.route('/order/<string:order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    order = Order.query.get(order_id)
    if not order:
        return jsonify({"message": "Sipariş bulunamadı."}), 404

    if order.status in ["CANCELLED", "REJECTED", "CONFIRMED"]:
        return jsonify({
            "message": "Bu sipariş sonlandırılmış veya onaylanmış, iptal edilemez.",
            "status": order.status
        }), 400

    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "Kullanıcı tarafından iptal edildi.")

    add_status_history(order, "CANCELLED", reason)
    db.session.commit()

    return jsonify({
        "message": f"Sipariş {order.id} başarıyla iptal edildi.",
        "status": order.status
    }), 200


# ============================
#  RESTORAN SAHİBİ ENDPOINTLERİ
# ============================

@app.route('/restaurant/orders', methods=['GET'])
def list_restaurant_orders():
    restaurant_user_id = request.args.get('restaurant_user_id')
    status = request.args.get('status')

    if restaurant_user_id is None:
        return jsonify({"message": "restaurant_user_id query param zorunludur."}), 400

    try:
        restaurant_user_id_int = int(restaurant_user_id)
    except ValueError:
        return jsonify({"message": "restaurant_user_id sayısal olmalıdır."}), 400

    user = User.query.get(restaurant_user_id_int)
    if not user:
        return jsonify({"message": "Belirtilen restaurant_user_id için kullanıcı bulunamadı."}), 404

    if user.role != ROLE_RESTAURANT:
        return jsonify({"message": "Bu kullanıcı restoran sahibi değil (role=RESTAURANT olmalı)."}), 403

    if user.restaurant_id is None:
        return jsonify({"message": "Bu restoran kullanıcısının restaurant_id bilgisi yok."}), 400

    q = Order.query.filter_by(restaurant_id=user.restaurant_id)
    if status is not None:
        q = q.filter(Order.status == status)

    orders = q.order_by(Order.created_at.desc()).all()
    return jsonify([order_to_dict(o) for o in orders]), 200


@app.route('/restaurant/approve', methods=['POST'])
def approve_order_restaurant():
    data = request.get_json(silent=True) or {}
    restaurant_user_id = data.get('restaurant_user_id')
    order_id = data.get('order_id')

    if not restaurant_user_id or not order_id:
        return jsonify({"message": "restaurant_user_id ve order_id zorunludur."}), 400

    try:
        restaurant_user_id_int = int(restaurant_user_id)
    except ValueError:
        return jsonify({"message": "restaurant_user_id sayısal olmalıdır."}), 400

    user = User.query.get(restaurant_user_id_int)
    if not user:
        return jsonify({"message": "Belirtilen restaurant_user_id için kullanıcı bulunamadı."}), 404

    if user.role != ROLE_RESTAURANT:
        return jsonify({"message": "Bu kullanıcı restoran sahibi değil (role=RESTAURANT olmalı)."}), 403

    if user.restaurant_id is None:
        return jsonify({"message": "Bu restoran kullanıcısının restaurant_id bilgisi yok."}), 400

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"message": f"Sipariş {order_id} bulunamadı."}), 404

    if order.restaurant_id != user.restaurant_id:
        return jsonify({
            "message": "Bu sipariş başka bir restorana ait. Yetkiniz yok.",
            "status": order.status
        }), 403

    if order.status in ["CANCELLED", "REJECTED", "CONFIRMED"]:
        return jsonify({
            "message": "Bu sipariş sonlandırılmış veya zaten onaylanmış, tekrar onaylanamaz.",
            "status": order.status
        }), 400

    add_status_history(order, "CONFIRMED", "Restoran sahibi tarafından onaylandı.")
    db.session.commit()

    return jsonify({
        "message": f"Sipariş {order.id} restoran sahibi tarafından başarıyla onaylandı.",
        "status": order.status
    }), 200


@app.route('/restaurant/reject', methods=['POST'])
def reject_order_restaurant():
    data = request.get_json(silent=True) or {}
    restaurant_user_id = data.get('restaurant_user_id')
    order_id = data.get('order_id')
    reason = data.get('reason', "Restoran sahibi tarafından reddedildi.")

    if not restaurant_user_id or not order_id:
        return jsonify({"message": "restaurant_user_id ve order_id zorunludur."}), 400

    try:
        restaurant_user_id_int = int(restaurant_user_id)
    except ValueError:
        return jsonify({"message": "restaurant_user_id sayısal olmalıdır."}), 400

    user = User.query.get(restaurant_user_id_int)
    if not user:
        return jsonify({"message": "Belirtilen restaurant_user_id için kullanıcı bulunamadı."}), 404

    if user.role != ROLE_RESTAURANT:
        return jsonify({"message": "Bu kullanıcı restoran sahibi değil (role=RESTAURANT olmalı)."}), 403

    if user.restaurant_id is None:
        return jsonify({"message": "Bu restoran kullanıcısının restaurant_id bilgisi yok."}), 400

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"message": f"Sipariş {order_id} bulunamadı."}), 404

    if order.restaurant_id != user.restaurant_id:
        return jsonify({
            "message": "Bu sipariş başka bir restorana ait. Yetkiniz yok.",
            "status": order.status
        }), 403

    if order.status in ["CANCELLED", "REJECTED", "CONFIRMED"]:
        return jsonify({
            "message": "Bu sipariş zaten sonlandırılmış veya onaylanmış.",
            "status": order.status
        }), 400

    add_status_history(order, "REJECTED", reason)
    db.session.commit()

    return jsonify({
        "message": f"Sipariş {order.id} restoran sahibi tarafından reddedildi.",
        "status": order.status,
        "reason": reason
    }), 200


# =========================================
#  MCP TOOL FONKSİYONLARINI KULLANAN UÇLAR
# =========================================

@app.route('/restaurant/queue/estimate', methods=['GET'])
def estimate_queue_wait_time():
    """
    Belirli bir restoran için aktif sipariş sayısını veritabanından sayar
    ve MCP içindeki tahmini_bekleme_suresi fonksiyonunu kullanarak
    tahmini bekleme süresini döner.

    Query parametreleri:
      - restaurant_user_id: Restoran sahibi kullanıcının ID'si (zorunlu)
      - ort_hazirlama_suresi_dk: Opsiyonel, varsayılan 8
      - paralel_mutfak_sayisi: Opsiyonel, varsayılan 1
    """
    restaurant_user_id = request.args.get('restaurant_user_id')
    if restaurant_user_id is None:
        return jsonify({"message": "restaurant_user_id query param zorunludur."}), 400

    try:
        restaurant_user_id_int = int(restaurant_user_id)
    except ValueError:
        return jsonify({"message": "restaurant_user_id sayısal olmalıdır."}), 400

    user = User.query.get(restaurant_user_id_int)
    if not user:
        return jsonify({"message": "Belirtilen restaurant_user_id için kullanıcı bulunamadı."}), 404

    if user.role != ROLE_RESTAURANT:
        return jsonify({"message": "Bu kullanıcı restoran sahibi değil (role=RESTAURANT olmalı)."}), 403

    if user.restaurant_id is None:
        return jsonify({"message": "Bu restoran kullanıcısının restaurant_id bilgisi yok."}), 400

    # Aktif siparişleri say: sonlandırılmış olmayanlar
    aktif_siparis_sayisi = Order.query.filter(
        Order.restaurant_id == user.restaurant_id,
        Order.status.notin_(["CANCELLED", "REJECTED", "CONFIRMED"])
    ).count()

    # Opsiyonel parametreleri oku
    ort_sure_raw = request.args.get('ort_hazirlama_suresi_dk', '8')
    paralel_raw = request.args.get('paralel_mutfak_sayisi', '1')

    try:
        ort_hazirlama_suresi_dk = int(ort_sure_raw)
        paralel_mutfak_sayisi = int(paralel_raw)
    except ValueError:
        return jsonify({"message": "ort_hazirlama_suresi_dk ve paralel_mutfak_sayisi tamsayı olmalıdır."}), 400

    # MCP tool fonksiyonunu doğrudan Python fonksiyonu gibi kullanıyoruz
    sonuc = tahmini_bekleme_suresi(
        aktif_siparis_sayisi=aktif_siparis_sayisi,
        ort_hazirlama_suresi_dk=ort_hazirlama_suresi_dk,
        paralel_mutfak_sayisi=paralel_mutfak_sayisi
    )

    return jsonify({
        "restaurant_id": user.restaurant_id,
        "restaurant_user_id": user.id,
        "aktif_siparis_sayisi": aktif_siparis_sayisi,
        "hesaplama": sonuc
    }), 200


@app.route('/menu/suggestion', methods=['GET'])
def menu_suggestion():
    """
    MCP içindeki onerilen_menu tool fonksiyonunu kullanarak
    TheMealDB public API'sinden günün menüsü / önerilen yemek bilgisi döner.

    Query parametreleri:
      - ana_malzeme: Örn. chicken, beef, pasta (varsayılan: chicken)
    """
    ana_malzeme = request.args.get('ana_malzeme', 'chicken')
    sonuc = onerilen_menu(ana_malzeme)

    # MCP fonksiyonu zaten JSON uyumlu dict döndürüyor,
    # burada sadece HTTP cevabına sarıyoruz.
    return jsonify(sonuc), 200



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
