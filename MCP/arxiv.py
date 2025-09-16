# main.py
import os
import re
import urllib.request
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Optional, List, Dict

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Arxiv Helper")

ARXIV_API = "https://export.arxiv.org/api/query"
UA = "arxiv-mcp/1.0 (+example@domain.com)"
SAVE_DIR = r"C:\Users\Sots\Desktop\UBMK2025\Mcp-3\Arxiv"

# ------------------ Helpers ------------------

def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/atom+xml"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

def _parse_entries(raw_xml: bytes) -> List[Dict[str, Any]]:
    root = ET.fromstring(raw_xml)
    papers: List[Dict[str, Any]] = []
    for entry in root.findall(".//{*}entry"):
        full_id = entry.findtext("{*}id") or ""
        arxiv_id = full_id.split("/")[-1] if "/" in full_id else full_id
        title = (entry.findtext("{*}title") or "").strip()
        published = entry.findtext("{*}published") or ""
        authors = [a.findtext("{*}name") or "" for a in entry.findall("{*}author")]

        pdf_link = None
        for l in entry.findall("{*}link"):
            if l.get("type") == "application/pdf":
                pdf_link = l.get("href"); break
        if not pdf_link and arxiv_id:
            pdf_link = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        papers.append({
            "arxiv_id": arxiv_id,
            "title": " ".join(title.split()),
            "authors": authors,
            "published": published,
            "pdf_link": pdf_link
        })
    return papers

def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "-", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name.lower().endswith(".md"):
        name += ".md"
    return name

def _markdown_report(topic: str, items: List[Dict[str, Any]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# arXiv raporu — {topic}", f"_Oluşturulma: {now}_\n"]
    if not items:
        lines.append("> Sonuç bulunamadı.")
        return "\n".join(lines)

    lines.append("## Liste")
    for i, p in enumerate(items, 1):
        lines.append(f"{i}. [{p['title']}]({p['pdf_link']}) — `{p['arxiv_id']}`")

    lines.append("\n## Ayrıntılar ve Özetler")
    for p in items:
        authors = ", ".join(p.get("authors", [])) or "-"
        lines.extend([
            f"\n### {p['title']}\n",
            f"- arXiv ID: `{p['arxiv_id']}`",
            f"- Yazar(lar): {authors}",
            f"- Yayın: {p.get('published') or '-'}",
            f"- PDF: {p.get('pdf_link') or '-'}\n",
        ])
        abstract = p.get("abstract") or "(özet bulunamadı)"
        for ln in abstract.splitlines():
            lines.append(f"> {ln}")
    return "\n".join(lines)

def _build_search_query(topic: str) -> str:

    t = topic.strip()
    tokens = [tok for tok in re.split(r"\s+", t) if tok]
    if len(tokens) >= 2:
        phrase = t.replace('"', '')
        and_query = " AND ".join(tokens)
        return f'(ti:"{phrase}" OR abs:"{phrase}" OR ti:({and_query}) OR abs:({and_query}))'
    else:
        tok = tokens[0]
        return f'(ti:{tok} OR abs:{tok})'

# ------------------ MCP Tools ------------------

@mcp.tool()
def fetch_arxiv_papers(topic: str, number_of_papers: int = 3) -> dict:
    """Verilen konu için en yeni makaleleri getirir (ID, başlık, yazar, tarih, PDF linki)."""
    try:
        if not topic or not isinstance(topic, str):
            return {"status": "error", "data": [], "message": "Geçersiz konu."}
        if not isinstance(number_of_papers, int) or number_of_papers <= 0:
            return {"status": "error", "data": [], "message": "Geçersiz adet."}

        search_query = _build_search_query(topic)
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": number_of_papers,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API}?{urlencode(params)}"
        papers = _parse_entries(_http_get(url))
        return {"status": "success", "data": papers, "message": f"{len(papers)} kayıt."}
    except Exception as e:
        return {"status": "error", "data": [], "message": f"Hata: {e}"}

@mcp.tool()
def get_arxiv_abstract(arxiv_id: str) -> dict:
    """Tek bir arXiv makalesinin özetini (summary) döndürür."""
    try:
        if not arxiv_id or not isinstance(arxiv_id, str):
            return {"status": "error", "data": None, "message": "Geçersiz arXiv ID."}
        url = f"{ARXIV_API}?{urlencode({'id_list': arxiv_id})}"
        raw = _http_get(url)
        entry = ET.fromstring(raw).find(".//{*}entry")
        if entry is None:
            return {"status": "error", "data": None, "message": "Kayıt bulunamadı."}
        abstract = (entry.findtext("{*}summary") or "").strip()
        return {"status": "success", "data": abstract, "message": "Özet alındı."}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Hata: {e}"}

@mcp.tool()
def save_md_to_file(text: str, filename: str) -> dict:
    """Verilen Markdown metnini SAVE_DIR içine kaydeder."""
    try:
        if not text or not isinstance(text, str):
            return {"status": "error", "data": None, "message": "Geçersiz metin."}
        if not filename or not isinstance(filename, str):
            return {"status": "error", "data": None, "message": "Geçersiz dosya adı."}
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = os.path.join(SAVE_DIR, _sanitize_filename(filename))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return {"status": "success", "data": path, "message": "Kaydedildi."}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Hata: {e}"}

@mcp.tool()
def build_and_save_topic_report(topic: str, number_of_papers: int = 3, filename: Optional[str] = None) -> dict:
    """En yeni makaleleri getir, özetlerini çek, tek Markdown rapor oluştur ve kaydet."""
    try:
        lst = fetch_arxiv_papers(topic, number_of_papers)
        if lst.get("status") != "success" or not lst.get("data"):
            return {"status": "error", "data": None, "message": f"Liste alınamadı: {lst.get('message')}"}
        items = lst["data"]

        for p in items:
            aid = p.get("arxiv_id")
            abs_res = get_arxiv_abstract(aid) if aid else {"status": "error", "data": ""}
            p["abstract"] = abs_res["data"] if abs_res.get("status") == "success" else ""

        md = _markdown_report(topic, items)
        if not filename:
            filename = f"arxiv-{topic}-{datetime.now().strftime('%Y%m%d')}.md"
        saved = save_md_to_file(md, filename)
        if saved.get("status") != "success":
            return {"status": "error", "data": None, "message": f"Kaydetme hatası: {saved.get('message')}"}
        return {"status": "success", "data": {"path": saved["data"], "count": len(items)}, "message": "Rapor oluşturuldu."}
    except Exception as e:
        return {"status": "error", "data": None, "message": f"Hata: {e}"}

# ------------------ Run ------------------

if __name__ == "__main__":
    mcp.run()
