import logging
from typing import Optional, List, Union, Any, Dict

from open_webui.retrieval.vector.main import (
    VectorDBBase,
    VectorItem,
    SearchResult,
    GetResult,
)
from open_webui.env import SRC_LOG_LEVELS
from open_webui.config import WEAVIATE_URL, WEAVIATE_COLLECTION_PREFIX

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


class WeaviateClient(VectorDBBase):
    """
    Minimal Weaviate adapter for Open WebUI vector interface.

    Notes:
    - Lazy import the client to avoid hard dependency when not used.
    - This implementation targets Weaviate v4 client API; if unavailable,
      it will raise a clear error at runtime when selected.
    - Collections are created per `collection_name` with a configurable prefix.
    - Text stored under property `text`, metadata under property `metadata`.
    """

    def __init__(self) -> None:
        self.url = WEAVIATE_URL
        self.collection_prefix = WEAVIATE_COLLECTION_PREFIX
        self._client = None

        if not self.url:
            log.warning("WEAVIATE_URL is not configured; WeaviateClient disabled")
            return

        try:
            import weaviate
            from urllib.parse import urlparse

            parsed = urlparse(self.url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 8080
            secure = parsed.scheme == "https"

            # Prefer v4 connect API
            if hasattr(weaviate, "connect_to_local") or hasattr(
                weaviate, "connect_to_custom"
            ):
                try:
                    if hasattr(weaviate, "connect_to_custom"):
                        self._client = weaviate.connect_to_custom(
                            http_host=host, http_port=port, http_secure=secure
                        )
                    else:
                        self._client = weaviate.connect_to_local(
                            host=host, port=port, secure=secure
                        )
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to connect to Weaviate v4 at {self.url}: {e}"
                    )
            else:
                # v3 client fallback
                try:
                    self._client = weaviate.Client(self.url)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to connect to Weaviate v3 at {self.url}: {e}"
                    )

            log.info(f"Connected to Weaviate at {self.url}")
        except Exception as e:
            # Defer failure until methods are invoked
            log.error(f"Weaviate client initialization failed: {e}")
            self._client = None

    # ---------- Helpers ----------
    def _collection_name(self, name: str) -> str:
        return f"{self.collection_prefix}_{name}" if self.collection_prefix else name

    def _ensure_collection(self, collection_name: str, dim: int) -> None:
        client = self._require_client()
        name = self._collection_name(collection_name)

        # v4 API
        if hasattr(client, "collections"):
            if not client.collections.exists(name):
                from weaviate.classes.config import Property, DataType

                client.collections.create(
                    name=name,
                    properties=[
                        Property(name="text", data_type=DataType.TEXT),
                        Property(name="metadata", data_type=DataType.OBJECT),
                    ],
                    vectorizer_config={"vectorizer": "none"},
                )
        else:
            # v3 API
            schema = client.schema.get()
            classes = [c.get("class") for c in schema.get("classes", [])]
            if name not in classes:
                client.schema.create_class(
                    {
                        "class": name,
                        "vectorizer": "none",
                        "properties": [
                            {"name": "text", "dataType": ["text"]},
                            {"name": "metadata", "dataType": ["object"]},
                        ],
                    }
                )

    def _require_client(self):
        if self._client is None:
            raise RuntimeError(
                "Weaviate client is not initialized. Ensure weaviate client is installed and WEAVIATE_URL is set."
            )
        return self._client

    # ---------- VectorDBBase methods ----------
    def has_collection(self, collection_name: str) -> bool:
        client = self._require_client()
        name = self._collection_name(collection_name)
        if hasattr(client, "collections"):
            return client.collections.exists(name)
        else:
            schema = client.schema.get()
            classes = [c.get("class") for c in schema.get("classes", [])]
            return name in classes

    def delete_collection(self, collection_name: str) -> None:
        client = self._require_client()
        name = self._collection_name(collection_name)
        if hasattr(client, "collections"):
            if client.collections.exists(name):
                client.collections.delete(name)
        else:
            client.schema.delete_class(name)

    def insert(self, collection_name: str, items: List[VectorItem]) -> None:
        self.upsert(collection_name, items)

    def upsert(self, collection_name: str, items: List[VectorItem]) -> None:
        client = self._require_client()
        if not items:
            return
        dim = len(items[0]["vector"]) if isinstance(items[0]["vector"], list) else 0
        self._ensure_collection(collection_name, dim)
        name = self._collection_name(collection_name)

        if hasattr(client, "collections"):
            coll = client.collections.get(name)
            objects = []
            vectors = []
            for it in items:
                objects.append(
                    {
                        "uuid": it["id"],
                        "properties": {"text": it["text"], "metadata": it["metadata"]},
                    }
                )
                vectors.append(it["vector"])
            coll.data.insert_many(objects=objects, vectors=vectors)
        else:
            # v3 batch
            with client.batch as batch:
                for it in items:
                    batch.add_data_object(
                        data_object={
                            "text": it["text"],
                            "metadata": it["metadata"],
                        },
                        class_name=name,
                        uuid=it["id"],
                        vector=it["vector"],
                    )

    def search(
        self, collection_name: str, vectors: List[List[Union[float, int]]], limit: int
    ) -> Optional[SearchResult]:
        client = self._require_client()
        if not vectors:
            return None
        name = self._collection_name(collection_name)

        if hasattr(client, "collections"):
            coll = client.collections.get(name)
            res = coll.query.near_vector(near_vector=vectors[0], limit=limit)
            ids = []
            texts = []
            metas = []
            dists = []
            for obj in getattr(res, "objects", []) or []:
                ids.append(getattr(obj, "uuid", None))
                properties = getattr(obj, "properties", {}) or {}
                texts.append(properties.get("text"))
                metas.append(properties.get("metadata"))
                meta = getattr(obj, "metadata", None)
                dists.append(getattr(meta, "distance", 0.0) if meta else 0.0)

            return SearchResult(
                ids=[ids],
                documents=[texts],
                metadatas=[metas],
                distances=[dists],
            )
        else:
            # v3 GraphQL
            query = (
                client.query.get(name, ["text", "metadata"]).with_near_vector(
                    {"vector": vectors[0]}
                ).with_limit(limit)
            )
            result = query.do()
            data = (((result or {}).get("data") or {}).get("Get") or {}).get(name) or []

            ids = []
            texts = []
            metas = []
            for obj in data:
                texts.append(obj.get("text"))
                metas.append(obj.get("metadata"))
                ids.append(obj.get("_additional", {}).get("id"))

            return SearchResult(ids=[ids], documents=[texts], metadatas=[metas], distances=[[]])

    def query(self, collection_name: str, filter: Dict, limit: Optional[int] = None) -> Optional[GetResult]:
        # 简化实现：取回集合后在本地基于 metadata 做过滤
        all_items = self.get(collection_name)
        if not all_items or not all_items.metadatas:
            return all_items
        metadatas = all_items.metadatas[0]
        documents = all_items.documents[0]
        # v4 fetch_objects 不返回 id，已在 get() 中尝试填充 ids
        ids = (all_items.ids[0] if all_items.ids else [None] * len(metadatas))
        def match(md):
            if not isinstance(md, dict):
                return False
            for k, v in filter.items():
                if md.get(k) != v:
                    return False
            return True
        filtered = [(i, md, doc, _id) for i, (md, doc, _id) in enumerate(zip(metadatas, documents, ids)) if match(md)]
        if limit is not None:
            filtered = filtered[:limit]
        if not filtered:
            return GetResult(ids=[[]], documents=[[]], metadatas=[[]])
        f_ids = [it[3] for it in filtered]
        f_docs = [it[2] for it in filtered]
        f_mds = [it[1] for it in filtered]
        return GetResult(ids=[f_ids], documents=[f_docs], metadatas=[f_mds])

    def get(self, collection_name: str) -> Optional[GetResult]:
        client = self._require_client()
        name = self._collection_name(collection_name)

        if hasattr(client, "collections"):
            coll = client.collections.get(name)
            # No direct list-all API with vectors; fetch limited objects
            res = coll.query.fetch_objects(limit=1000)
            ids = []
            texts = []
            metas = []
            for obj in getattr(res, "objects", []) or []:
                ids.append(getattr(obj, "uuid", None))
                properties = getattr(obj, "properties", {}) or {}
                texts.append(properties.get("text"))
                metas.append(properties.get("metadata"))
            return GetResult(ids=[ids], documents=[texts], metadatas=[metas])
        else:
            result = (
                client.query.get(name, ["text", "metadata"]).with_additional(["id"]).do()
            )
            data = (((result or {}).get("data") or {}).get("Get") or {}).get(name) or []
            ids = []
            texts = []
            metas = []
            for obj in data:
                ids.append(obj.get("_additional", {}).get("id"))
                texts.append(obj.get("text"))
                metas.append(obj.get("metadata"))
            return GetResult(ids=[ids], documents=[texts], metadatas=[metas])

    def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict] = None,
    ) -> None:
        client = self._require_client()
        name = self._collection_name(collection_name)

        if hasattr(client, "collections"):
            # v4: 无直接精确 where 模式，退化为 get + 逐个删除
            coll = client.collections.get(name)
            to_delete = []
            if ids:
                to_delete = ids
            elif filter:
                qr = self.query(collection_name, filter)
                to_delete = (qr.ids[0] if qr and qr.ids else [])
            else:
                # 全量删除：直接删除集合
                try:
                    client.collections.delete(name)
                except Exception:
                    pass
                return
            for i in to_delete:
                try:
                    coll.data.delete_by_id(i)
                except Exception:
                    pass
        else:
            if ids or filter:
                to_delete = ids or []
                if filter and not to_delete:
                    qr = self.query(collection_name, filter)
                    to_delete = (qr.ids[0] if qr and qr.ids else [])
                for i in to_delete:
                    try:
                        client.data_object.delete(uuid=i, class_name=name)
                    except Exception:
                        pass
            else:
                # v3: 全量删除 => 重建类
                try:
                    client.schema.delete_class(name)
                except Exception:
                    pass
                self._ensure_collection(collection_name, 0)

    def reset(self) -> None:
        client = self._require_client()
        if hasattr(client, "collections"):
            # v4: list and delete prefixed collections only
            for c in client.collections.list_all():
                if not self.collection_prefix or str(c).startswith(self.collection_prefix):
                    try:
                        client.collections.delete(str(c))
                    except Exception:
                        pass
        else:
            schema = client.schema.get()
            for cls in schema.get("classes", []) or []:
                name = cls.get("class")
                if not self.collection_prefix or name.startswith(self.collection_prefix):
                    try:
                        client.schema.delete_class(name)
                    except Exception:
                        pass
