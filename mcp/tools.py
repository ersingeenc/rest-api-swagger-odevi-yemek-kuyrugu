"""
Ortak MCP tool fonksiyonlarının saf Python implementasyonu.

Bu modül, herhangi bir MCP kütüphanesine bağımlı değildir.
Hem Flask uygulaması içinde, hem de MCP server içinde import edilerek kullanılabilir.
"""

import requests


def tahmini_bekleme_suresi(
    aktif_siparis_sayisi: int,
    ort_hazirlama_suresi_dk: int = 8,
    paralel_mutfak_sayisi: int = 1,
) -> dict:
    """
    Yemek kuyruğu projesi için:
    Restorandaki aktif sipariş sayısına göre tahmini bekleme süresini hesaplar.

    Parametreler:
      - aktif_siparis_sayisi: Şu an kuyruktaki sipariş sayısı
      - ort_hazirlama_suresi_dk: Bir siparişin ortalama hazırlanma süresi (dakika)
      - paralel_mutfak_sayisi: Aynı anda çalışan mutfak/hat sayısı (ör: 2 ocak, 2 ayrı usta)

    Dönen:
      - toplam_bekleme_dk: Tahmini toplam bekleme süresi
      - tahmini_sira_suresi_dk: Bir sipariş için ortalama bekleme
    """
    if aktif_siparis_sayisi < 0:
        raise ValueError("aktif_siparis_sayisi negatif olamaz")

    if paralel_mutfak_sayisi <= 0:
        raise ValueError("paralel_mutfak_sayisi en az 1 olmalı")

    toplam_is_yuku = aktif_siparis_sayisi * ort_hazirlama_suresi_dk
    toplam_bekleme_dk = toplam_is_yuku / paralel_mutfak_sayisi

    tahmini_sira_suresi_dk = (
        toplam_bekleme_dk / aktif_siparis_sayisi if aktif_siparis_sayisi > 0 else 0
    )

    return {
        "aktif_siparis_sayisi": aktif_siparis_sayisi,
        "ort_hazirlama_suresi_dk": ort_hazirlama_suresi_dk,
        "paralel_mutfak_sayisi": paralel_mutfak_sayisi,
        "toplam_bekleme_dk": round(toplam_bekleme_dk, 2),
        "tahmini_sira_suresi_dk": round(tahmini_sira_suresi_dk, 2),
    }


def onerilen_menu(ana_malzeme: str = "chicken") -> dict:
    """
    Public bir API'ye (TheMealDB) 'requests' ile istek atarak
    proje için 'günün menüsü' gibi kullanılabilecek bir yemek önerisi döner.

    - https://www.themealdb.com/api/json/v1/1/filter.php?i={ana_malzeme}

    Parametre:
      - ana_malzeme: chicken, beef, pasta vb.

    Dönen:
      - ana_malzeme
      - onerilen_yemek
      - yemek_id
      - gorsel_url
    """
    url = f"https://www.themealdb.com/api/json/v1/1/filter.php?i={ana_malzeme}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        return {
            "ana_malzeme": ana_malzeme,
            "hata": f"Public API isteği başarısız oldu: {e}",
        }

    data = response.json()
    meals = data.get("meals") or []

    if not meals:
        return {
            "ana_malzeme": ana_malzeme,
            "onerilen_yemek": None,
            "mesaj": "Bu malzemeyle ilgili yemek bulunamadı.",
        }

    secilen = meals[0]

    return {
        "ana_malzeme": ana_malzeme,
        "onerilen_yemek": secilen.get("strMeal"),
        "yemek_id": secilen.get("idMeal"),
        "gorsel_url": secilen.get("strMealThumb"),
    }
