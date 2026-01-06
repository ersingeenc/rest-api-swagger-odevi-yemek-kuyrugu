# Yemek Kuyruğu MCP Servisi

Bu klasör, Yemek Kuyruğu projesi ile **mantıksal olarak ilişkili** bir MCP (Model Context Protocol) servis örneği içerir.

## Dosya

- `yemek_kuyrugu_mcp.py`  
  - MCP server tanımı (`FastMCP("Yemek Kuyrugu MCP", ...)`)
  - İki adet tool fonksiyonu:
    - `tahmini_bekleme_suresi(aktif_siparis_sayisi, ort_hazirlama_suresi_dk=8, paralel_mutfak_sayisi=1)`
      - Kuyruktaki sipariş sayısına göre toplam ve ortalama bekleme süresi döner.
    - `onerilen_menu(ana_malzeme="chicken")`
      - `requests` kütüphanesi ile TheMealDB public API'sine istek atar ve örnek bir yemek önerisi döner.

## Çalıştırma

Örnek (lokalde):

```bash
pip install -r requirements.txt
python -m mcp.server.run python mcp/yemek_kuyrugu_mcp.py
```

veya doğrudan:

```bash
python mcp/yemek_kuyrugu_mcp.py
```

MCP uyumlu bir istemci (dersinizde kullanılan IDE / araç) bu scripti
`command: "python", args: ["mcp/yemek_kuyrugu_mcp.py"]` şeklinde çalıştıracak
şekilde yapılandırılabilir.
