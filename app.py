from flask import Flask, request, jsonify
import uuid
import time
from functools import wraps

app = Flask(__name__)

orders = {}
SECRET_TOKEN = "super-gizli-api-token-123"

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"message": "Token eksik veya formatı hatalı (Bearer <token>).", "access": "denied"}), 401

        token = auth_header.split(' ')[1]
        
        if token != SECRET_TOKEN:
            return jsonify({"message": "Geçersiz Bearer Token.", "access": "denied"}), 403

        return f(*args, **kwargs)
    return decorated

@app.route('/order', methods=['POST'])
def create_order():
    data = request.json
    
    required_fields = ['user_id', 'restaurant_id', 'amount', 'items']
    if not all(field in data for field in required_fields):
        return jsonify({"message": "Eksik alanlar var."}), 400

    if data['amount'] > 1000:
        return jsonify({"message": "Ödeme başarısız.", "reason": "Limit aşıldı (Simülasyon Hatası)."}), 400

    order_id = f"ORD-{int(time.time())}-{str(uuid.uuid4())[:3]}"
    new_order = {
        "id": order_id, "user_id": data['user_id'], "restaurant_id": data['restaurant_id'],
        "amount": data['amount'], "items": data['items'],
        "status": "PAYMENT_SUCCESS", "created_at": time.time()
    }
    orders[order_id] = new_order
    
    return jsonify({
        "message": "Siparişiniz başarıyla alındı ve işleniyor.",
        "order_id": order_id, "status": new_order["status"],
        "next_step": "Restoran onayı bekleniyor (arka planda işleniyor)."
    }), 202

@app.route('/order/<string:order_id>', methods=['GET'])
def get_order_status(order_id):
    order = orders.get(order_id)
    if not order:
        return jsonify({"message": "Sipariş bulunamadı."}), 404
    
    if time.time() - order["created_at"] > 30 and order["status"] == "PAYMENT_SUCCESS":
         order["status"] = "CONFIRMED"
         orders[order_id] = order

    return jsonify({"id": order["id"], "status": order["status"], "amount": order["amount"]}), 200

@app.route('/admin/approve', methods=['POST'])
@token_required
def approve_order_admin():
    data = request.json
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({"message": "Onaylanacak sipariş ID'si eksik."}), 400
        
    if order_id in orders:
        orders[order_id]["status"] = "CONFIRMED_BY_ADMIN"
        return jsonify({
            "message": f"Sipariş {order_id} yönetici tarafından başarıyla onaylandı.",
            "status": orders[order_id]["status"]
        }), 200
    else:
        return jsonify({"message": f"Sipariş {order_id} bulunamadı."}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
