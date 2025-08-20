from __future__ import annotations

import logging
from typing import List

from langchain_core.documents import Document

from open_webui.services.ali_idp import AliIDPClient
from open_webui.services.semantic_splitter import SemanticSplitter

log = logging.getLogger(__name__)


class AlibabaIDPLoader:
    def __init__(self, file_path: str, mime_type: str | None = None, **kwargs):
        self.file_path = file_path
        self.mime_type = mime_type
        self.enable_llm = kwargs.get("ALIBABA_IDP_ENABLE_LLM", True)
        self.enable_formula = kwargs.get("ALIBABA_IDP_ENABLE_FORMULA", True)
        self.max_chunk_size = int(kwargs.get("ALIBABA_IDP_MAX_CHUNK_SIZE", 1000))
        self.overlap = int(kwargs.get("ALIBABA_IDP_CHUNK_OVERLAP", 100))

    def load(self) -> List[Document]:
        client = AliIDPClient()
        result = client.parse_document(
            self.file_path, enable_llm=self.enable_llm, enable_formula=self.enable_formula
        )
        splitter = SemanticSplitter(max_chunk_size=self.max_chunk_size, overlap=self.overlap)
        chunks = splitter.split_from_idp(result)
        base_meta = {"Content-Type": self.mime_type} if self.mime_type else {}
        docs = splitter.to_documents(chunks, base_meta=base_meta)
        return docs
