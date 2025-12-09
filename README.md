# Yemek Siparişi Akışı API'si

Bu depo, bir yemek siparişi uygulamasının temel sipariş oluşturma ve durum sorgulama akışını (Ödeme -> Asenkron Kuyruk Simülasyonu) içeren basit bir REST API simülasyonunu içerir.

##  Gereksinimler

- Docker ve Docker Compose

##  Docker Kullanımı

API'yi Docker konteyneri içinde çalıştırmak ve 5000 portunda yayınlamak için aşağıdaki komutu kullanabilirsiniz.


docker build -t yemek-siparis-api-image .
