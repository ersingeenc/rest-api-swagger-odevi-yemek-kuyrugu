"""
Yemek Kuyruğu MCP Servisi

Bu dosya, Model Context Protocol (MCP) ile çalışan bir servis örneğidir.
Servis, yemek kuyruğu projesi ile mantıksal olarak ilişkilidir ve
aşağıdaki iki tool fonksiyonunu sağlar:

- tahmini_bekleme_suresi_tool: Kuyruktaki sipariş sayısına göre tahmini bekleme süresi hesabı
- onerilen_menu_tool: Public bir yemek API'sinden (TheMealDB) örnek yemek önerisi çeker

Bu dosya, projeden bağımsız bir süreç olarak çalışır ve LLM istemcileri
tarafından MCP server olarak kullanılabilir.
"""

from mcp.server.fastmcp import FastMCP
from .tools import tahmini_bekleme_suresi, onerilen_menu

# MCP sunucusunu oluştur
mcp = FastMCP("Yemek Kuyrugu MCP", json_response=True)


@mcp.tool()
def tahmini_bekleme_suresi_tool(
    aktif_siparis_sayisi: int,
    ort_hazirlama_suresi_dk: int = 8,
    paralel_mutfak_sayisi: int = 1,
) -> dict:
    """
    MCP tool sarmalayıcısı:
    Asıl hesaplama mcp.tools.tahmini_bekleme_suresi fonksiyonunda yapılır.
    """
    return tahmini_bekleme_suresi(
        aktif_siparis_sayisi=aktif_siparis_sayisi,
        ort_hazirlama_suresi_dk=ort_hazirlama_suresi_dk,
        paralel_mutfak_sayisi=paralel_mutfak_sayisi,
    )


@mcp.tool()
def onerilen_menu_tool(ana_malzeme: str = "chicken") -> dict:
    """
    MCP tool sarmalayıcısı:
    Asıl iş mantığı mcp.tools.onerilen_menu fonksiyonunda.
    """
    return onerilen_menu(ana_malzeme)


if __name__ == "__main__":
    # Derste genelde stdio veya http kullanılıyor; burada stdio seçtik.
    # MCP client'lar bunu stdio üzerinden bağlayabilir.
    mcp.run(transport="stdio")
