"""
文档解析服务 - PDF / Word / TXT / MD / CSV
"""
from __future__ import annotations

import io


class DocumentParser:
    @staticmethod
    def parse_pdf(file_bytes: bytes) -> str:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(file_bytes))
            chunks = []
            for page in reader.pages:
                text = page.extract_text() or ""
                if text:
                    chunks.append(text)
            return "\n".join(chunks)
        except Exception as e:
            return f"PDF 解析失败: {e}"

    @staticmethod
    def parse_docx(file_bytes: bytes) -> str:
        try:
            from docx import Document

            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except Exception as e:
            return f"Word 解析失败: {e}"

    @staticmethod
    def parse_txt(file_bytes: bytes) -> str:
        return file_bytes.decode("utf-8", errors="ignore")

    def parse(self, file_bytes: bytes, file_ext: str) -> str:
        ext = file_ext.lower().lstrip(".")
        if ext == "pdf":
            return self.parse_pdf(file_bytes)
        if ext in ("doc", "docx"):
            return self.parse_docx(file_bytes)
        if ext in ("txt", "md", "csv"):
            return self.parse_txt(file_bytes)
        return f"不支持的文件类型: {ext}"


document_parser = DocumentParser()
