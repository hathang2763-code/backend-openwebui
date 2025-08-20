"""
Semantic splitter for documents based on Ali IDP result or raw text.

Produces chunk dictionaries and can be adapted to LangChain Documents.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document

log = logging.getLogger(__name__)


class SemanticSplitter:
    def __init__(self, max_chunk_size: int = 1000, overlap: int = 100) -> None:
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    # ----- Public API -----
    def split_from_idp(self, idp_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        layouts = (idp_result or {}).get("layouts", [])
        for i, layout in enumerate(layouts):
            try:
                content = (layout.get("text") or "").strip()
                if not content:
                    continue
                chunk = {
                    "content": content,
                    "title": self._extract_title(layout),
                    "type": layout.get("type", "text"),
                    "subtype": layout.get("subType", ""),
                    "page_number": (layout.get("pageNum") or [0])[0]
                    if isinstance(layout.get("pageNum"), list)
                    else 0,
                    "unique_id": layout.get("uniqueId", f"chunk_{i}"),
                    "markdown_content": layout.get("markdownContent", ""),
                    "position": {
                        "x": layout.get("x", 0),
                        "y": layout.get("y", 0),
                        "width": layout.get("w", 0),
                        "height": layout.get("h", 0),
                    },
                }
                if len(chunk["content"]) > self.max_chunk_size:
                    chunks.extend(self._split_large_content(chunk))
                else:
                    chunks.append(chunk)
            except Exception as e:
                log.debug("layout split error: %s", e)
                continue

        # Fallback: markdown
        if not chunks and (idp_result or {}).get("markdown"):
            chunks = self._split_markdown_content(idp_result.get("markdown", ""))
        return chunks

    def split_text(self, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []
        # split by blank lines first, then sentence fallback
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: List[Dict[str, Any]] = []
        current = ""
        idx = 0
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
            if len(current) + len(p) + 2 <= self.max_chunk_size:
                current = (current + "\n\n" + p) if current else p
            else:
                if current:
                    chunks.append(self._mk_basic_chunk(current, idx))
                    idx += 1
                current = p
                if len(current) > self.max_chunk_size:
                    s_chunks = self._split_by_sentences(current, idx)
                    chunks.extend(s_chunks)
                    idx += len(s_chunks)
                    current = ""
        if current:
            chunks.append(self._mk_basic_chunk(current, idx))
        return chunks

    def to_documents(self, chunks: List[Dict[str, Any]], base_meta: Optional[Dict[str, Any]] = None) -> List[Document]:
        base_meta = base_meta or {}
        docs: List[Document] = []
        for ch in chunks:
            meta = {
                **base_meta,
                "page_number": ch.get("page_number", 0),
                "element_type": ch.get("type", "text"),
                "element_subtype": ch.get("subtype", ""),
                "unique_id": ch.get("unique_id", ""),
                "has_markdown": bool(ch.get("markdown_content")),
                "has_title": bool(ch.get("title")),
                "content_length": len(ch.get("content", "")),
            }
            docs.append(Document(page_content=ch.get("content", ""), metadata=meta))
        return docs

    # ----- Helpers -----
    def _extract_title(self, layout: Dict[str, Any]) -> str:
        lt = layout.get("type", "")
        st = layout.get("subType", "")
        if lt in ["title", "para_title"] or "title" in st.lower():
            return (layout.get("text") or "").strip()
        text = (layout.get("text") or "").strip()
        if text and len(text) < 100:
            pats = [
                r"^\d+\.\s*\S+",
                r"^第\d+章\s*\S+",
                r"^第\d+节\s*\S+",
                r"^[一二三四五六七八九十]+、\S+",
                r"^\w+\s*:\s*\S+",
                r"^#+\s*\S+",
            ]
            for pat in pats:
                if re.match(pat, text):
                    return text
        return ""

    def _split_large_content(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        content = chunk.get("content", "")
        subs: List[Dict[str, Any]] = []
        paras = re.split(r"\n\s*\n", content)
        cur = ""
        idx = 0
        for p in paras:
            p = p.strip()
            if not p:
                continue
            if len(cur) + len(p) + 2 <= self.max_chunk_size:
                cur = (cur + "\n\n" + p) if cur else p
            else:
                if cur:
                    sc = dict(chunk)
                    sc["content"] = cur
                    sc["unique_id"] = f"{chunk.get('unique_id','chunk')}_{idx}"
                    subs.append(sc)
                    idx += 1
                cur = p
                if len(cur) > self.max_chunk_size:
                    sentence_chunks = self._split_by_sentences(cur, idx, base_chunk=chunk)
                    subs.extend(sentence_chunks)
                    idx += len(sentence_chunks)
                    cur = ""
        if cur:
            sc = dict(chunk)
            sc["content"] = cur
            sc["unique_id"] = f"{chunk.get('unique_id','chunk')}_{idx}"
            subs.append(sc)
        return subs

    def _split_by_sentences(self, content: str, start_index: int, base_chunk: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        base_chunk = base_chunk or {
            "type": "text",
            "subtype": "content",
            "page_number": 0,
            "unique_id": "chunk",
            "markdown_content": "",
        }
        sentences = re.split(r"[。！？\.\!\?]\s*", content)
        out: List[Dict[str, Any]] = []
        cur = ""
        idx = start_index
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if len(cur) + len(s) + 1 <= self.max_chunk_size:
                cur = (cur + s) if cur else s
            else:
                if cur:
                    sc = dict(base_chunk)
                    sc["content"] = cur
                    sc["unique_id"] = f"{base_chunk.get('unique_id','chunk')}_{idx}"
                    out.append(sc)
                    idx += 1
                cur = s
                if len(cur) > self.max_chunk_size:
                    out.extend(self._force_split(cur, base_chunk, idx))
                    idx += len(out)
                    cur = ""
        if cur:
            sc = dict(base_chunk)
            sc["content"] = cur
            sc["unique_id"] = f"{base_chunk.get('unique_id','chunk')}_{idx}"
            out.append(sc)
        return out

    def _force_split(self, content: str, base_chunk: Dict[str, Any], start_index: int) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        idx = start_index
        step = max(1, self.max_chunk_size - self.overlap)
        for i in range(0, len(content), step):
            seg = content[i : i + self.max_chunk_size]
            if seg.strip():
                sc = dict(base_chunk)
                sc["content"] = seg
                sc["unique_id"] = f"{base_chunk.get('unique_id','chunk')}_{idx}"
                out.append(sc)
                idx += 1
        return out

    def _split_markdown_content(self, md: str) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        sections = re.split(r"\n(?=#+\s)", md)
        for i, sec in enumerate(sections):
            sec = sec.strip()
            if not sec:
                continue
            m = re.match(r"^(#+)\s*(.+?)(?:\n|$)", sec)
            title = m.group(2) if m else ""
            chunk = {
                "content": sec,
                "title": title,
                "type": "markdown_section",
                "subtype": f"level_{len(m.group(1))}" if m else "content",
                "page_number": 0,
                "unique_id": f"markdown_chunk_{i}",
                "markdown_content": sec,
                "position": {"x": 0, "y": 0, "width": 0, "height": 0},
            }
            if len(chunk["content"]) > self.max_chunk_size:
                chunks.extend(self._split_large_content(chunk))
            else:
                chunks.append(chunk)
        return chunks

    def _mk_basic_chunk(self, content: str, idx: int) -> Dict[str, Any]:
        return {
            "content": content,
            "title": "",
            "type": "text",
            "subtype": "content",
            "page_number": 0,
            "unique_id": f"text_chunk_{idx}",
            "markdown_content": "",
            "position": {"x": 0, "y": 0, "width": 0, "height": 0},
        }
