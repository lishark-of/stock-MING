import hashlib
import io

import requests
from PyPDF2 import PdfReader


MAX_PDF_BYTES = 20 * 1024 * 1024


def download_and_extract_pdf(pdf_url, max_pages=20, max_chars=30000):
    if not pdf_url:
        return {
            "ok": False,
            "parse_status": "failed",
            "text_excerpt": "",
            "content_hash": "",
            "error": "缺少 PDF URL",
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; StockMINGAnnouncementBot/1.0)",
        "Accept": "application/pdf,*/*",
        "Referer": "https://www.cninfo.com.cn/",
    }

    try:
        resp = requests.get(pdf_url, headers=headers, timeout=20)
        if resp.status_code != 200:
            return {
                "ok": False,
                "parse_status": "failed",
                "text_excerpt": "",
                "content_hash": "",
                "error": f"HTTP {resp.status_code}",
            }

        content = resp.content or b""
        if len(content) > MAX_PDF_BYTES:
            return {
                "ok": False,
                "parse_status": "failed",
                "text_excerpt": "",
                "content_hash": hashlib.sha256(content[:MAX_PDF_BYTES]).hexdigest(),
                "error": "PDF 文件超过 20MB 限制",
            }

        content_type = (resp.headers.get("Content-Type") or "").lower()
        if "pdf" not in content_type and not content.startswith(b"%PDF"):
            return {
                "ok": False,
                "parse_status": "failed",
                "text_excerpt": "",
                "content_hash": hashlib.sha256(content).hexdigest(),
                "error": f"响应不是 PDF：{content_type or 'unknown content-type'}",
            }

        content_hash = hashlib.sha256(content).hexdigest()
        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages[: int(max_pages or 20)]:
            pages.append(page.extract_text() or "")
            if sum(len(part) for part in pages) >= int(max_chars or 30000):
                break
        text = "\n".join(part.strip() for part in pages if part and part.strip())
        text = text[: int(max_chars or 30000)]
        if not text.strip():
            return {
                "ok": False,
                "parse_status": "empty",
                "text_excerpt": "",
                "content_hash": content_hash,
                "error": "PDF 可下载但文本解析为空，未做 OCR",
            }

        return {
            "ok": True,
            "parse_status": "ok",
            "text_excerpt": text,
            "content_hash": content_hash,
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "parse_status": "failed",
            "text_excerpt": "",
            "content_hash": "",
            "error": str(exc),
        }
