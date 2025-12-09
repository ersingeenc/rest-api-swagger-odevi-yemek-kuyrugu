# app.py
from flask import Flask, request, jsonify
import uuid
import time

app = Flask(__name__)

# Basit bir veritabanı simülasyonu
orders = {}

@app.route('/order', methods=['POST'])
def create_order():
    """Yeni bir sipariş oluşturur ve ödeme akışını simüle eder."""
    data = request.json
    
    # 1. Zorunlu Alan Kontrolü (Swagger'a göre)
    required_fields = ['user_id', 'restaurant_id', 'amount', 'items']
    if not all(field in data for field in required_fields):
        return jsonify({"message": "Eksik alanlar var."}), 400

    # 2. Ödeme Simülasyonu
    # amount 1000'den büyükse ödeme başarısız olsun.
    if data['amount'] > 1000:
        return jsonify({
            "message": "Ödeme başarısız.",
            "reason": "Limit aşıldı (Simülasyon Hatası)."
        }), 400

    # 3. Sipariş Oluşturma ve Kuyruğa Alma (Asenkron Simülasyon)
    order_id = f"ORD-{int(time.time())}-{str(uuid.uuid4())[:3]}"
    
    new_order = {
        "id": order_id,
        "user_id": data['user_id'],
        "restaurant_id": data['restaurant_id'],
        "amount": data['amount'],
        "items": data['items'],
        "status": "PAYMENT_SUCCESS", # Ödeme başarılı, şimdi restorana gönderildi.
        "created_at": time.time()
    }
    
    orders[order_id] = new_order
    
    # Restoran onayını simüle etmek için, 5 saniye sonra durumu CONFIRMED yapalım.
    # (Gerçekte bu, bir Kuyruk İşçisi (Worker) tarafından yapılır)
    # Bu kısmı basitleştiriyoruz, gerçek asenkron işlem yapmıyoruz.

    return jsonify({
        "message": "Siparişiniz başarıyla alındı ve işleniyor.",
        "order_id": order_id,
        "status": new_order["status"],
        "transaction_id": f"TX-{int(time.time())}",
        "next_step": "Restoran onayı bekleniyor (arka planda işleniyor)."
    }), 202

@app.route('/order/<string:order_id>', methods=['GET'])
def get_order_status(order_id):
    """Belirli bir siparişin durumunu sorgular."""
    
    order = orders.get(order_id)

    if not order:
        return jsonify({"message": "Sipariş bulunamadı."}), 404
    
    # Basit bir durum ilerlemesi simülasyonu ekleyelim:
    # 30 saniyeden eskiyse 'CONFIRMED' yapalım.
    if time.time() - order["created_at"] > 30 and order["status"] == "PAYMENT_SUCCESS":
         order["status"] = "CONFIRMED"
         orders[order_id] = order # Güncelleme

    return jsonify({
        "id": order["id"],
        "status": order["status"],
        "amount": order["amount"],
        "user_id": order["user_id"]
    }), 200

if __name__ == '__main__':
    # Flask'ı varsayılan portta çalıştır
    app.run(debug=True, port=5000)
