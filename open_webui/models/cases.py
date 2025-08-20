import time
import uuid
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, String, Text, BigInteger, JSON

from open_webui.internal.db import Base, get_db


class Case(Base):
    __tablename__ = "case"

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text)

    title = Column(Text)
    query = Column(Text)
    status = Column(Text)  # open | solved | closed
    vendor = Column(Text, nullable=True)
    category = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class CaseNode(Base):
    __tablename__ = "case_node"

    id = Column(Text, primary_key=True, unique=True)
    case_id = Column(Text)

    title = Column(Text)
    content = Column(Text)
    node_type = Column(Text)
    status = Column(Text, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(BigInteger)


class CaseEdge(Base):
    __tablename__ = "case_edge"

    id = Column(Text, primary_key=True, unique=True)
    case_id = Column(Text)

    source_node_id = Column(Text)
    target_node_id = Column(Text)
    edge_type = Column(Text)
    metadata_ = Column("metadata", JSON, nullable=True)


class CaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    title: str
    query: str
    status: str
    vendor: Optional[str] = None
    category: Optional[str] = None
    metadata: Optional[dict] = Field(default=None, validation_alias="metadata_")
    created_at: Optional[int] = None
    updated_at: Optional[int] = None


class CaseCreateForm(BaseModel):
    query: str
    attachments: Optional[list[dict]] = None
    useLanggraph: Optional[bool] = False
    vendor: Optional[str] = None


class CaseNodeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    title: str
    content: str
    node_type: str
    status: Optional[str] = None
    metadata: Optional[dict] = Field(default=None, validation_alias="metadata_")
    created_at: Optional[int] = None


class CaseEdgeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    source_node_id: str
    target_node_id: str
    edge_type: str
    metadata: Optional[dict] = Field(default=None, validation_alias="metadata_")


class CaseWithGraphModel(CaseModel):
    nodes: List[CaseNodeModel] = []
    edges: List[CaseEdgeModel] = []


class CaseListResponse(BaseModel):
    items: List[CaseModel]
    total: int
    page: int
    page_size: int


class CasesTable:
    def insert_new_case(self, user_id: str, form: CaseCreateForm) -> Optional[CaseModel]:
        now = int(time.time())
        title = form.query[:100] + "..." if len(form.query or "") > 100 else form.query
        c = Case(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            query=form.query,
            status="open",
            vendor=form.vendor,
            category=None,
            created_at=now,
            updated_at=now,
        )
        with get_db() as db:
            db.add(c)
            db.commit()
            db.refresh(c)
            return CaseModel.model_validate(c)

    def get_case_by_id(self, case_id: str) -> Optional[CaseModel]:
        with get_db() as db:
            c = db.query(Case).filter_by(id=case_id).first()
            return CaseModel.model_validate(c) if c else None

    def get_case_with_graph_by_id(self, case_id: str) -> Optional[CaseWithGraphModel]:
        with get_db() as db:
            c = db.query(Case).filter_by(id=case_id).first()
            if not c:
                return None
            nodes = db.query(CaseNode).filter_by(case_id=case_id).all()
            edges = db.query(CaseEdge).filter_by(case_id=case_id).all()
            return CaseWithGraphModel(
                **CaseModel.model_validate(c).model_dump(),
                nodes=[CaseNodeModel.model_validate(n) for n in nodes],
                edges=[CaseEdgeModel.model_validate(e) for e in edges],
            )

    def update_case(self, case_id: str, fields: dict) -> Optional[CaseModel]:
        with get_db() as db:
            c = db.query(Case).filter_by(id=case_id).first()
            if not c:
                return None
            for k, v in fields.items():
                if hasattr(c, k) and v is not None:
                    setattr(c, k, v)
            c.updated_at = int(time.time())
            db.commit()
            db.refresh(c)
            return CaseModel.model_validate(c)

    def delete_case(self, case_id: str) -> bool:
        with get_db() as db:
            c = db.query(Case).filter_by(id=case_id).first()
            if not c:
                return False
            # Delete nodes and edges first
            db.query(CaseEdge).filter_by(case_id=case_id).delete()
            db.query(CaseNode).filter_by(case_id=case_id).delete()
            db.delete(c)
            db.commit()
            return True

    def create_node(
        self,
        case_id: str,
        title: str,
        content: str,
        node_type: str,
        status: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> CaseNodeModel:
        now = int(time.time())
        n = CaseNode(
            id=str(uuid.uuid4()),
            case_id=case_id,
            title=title,
            content=content,
            node_type=node_type,
            status=status,
            metadata_=metadata or {},
            created_at=now,
        )
        with get_db() as db:
            db.add(n)
            db.commit()
            db.refresh(n)
            # update case updated_at
            db.query(Case).filter_by(id=case_id).update({"updated_at": now})
            db.commit()
            return CaseNodeModel.model_validate(n)

    def create_edge(
        self,
        case_id: str,
        source_node_id: str,
        target_node_id: str,
        edge_type: str,
        metadata: Optional[dict] = None,
    ) -> CaseEdgeModel:
        e = CaseEdge(
            id=str(uuid.uuid4()),
            case_id=case_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type=edge_type,
            metadata_=metadata or {},
        )
        with get_db() as db:
            db.add(e)
            db.commit()
            db.refresh(e)
            return CaseEdgeModel.model_validate(e)

    def delete_node(self, node_id: str) -> bool:
        with get_db() as db:
            n = db.query(CaseNode).filter_by(id=node_id).first()
            if not n:
                return False
            db.delete(n)
            db.commit()
            return True

    def delete_edge(self, edge_id: str) -> bool:
        with get_db() as db:
            e = db.query(CaseEdge).filter_by(id=edge_id).first()
            if not e:
                return False
            db.delete(e)
            db.commit()
            return True

    def update_node_metadata(self, node_id: str, patch: dict) -> Optional[CaseNodeModel]:
        with get_db() as db:
            n = db.query(CaseNode).filter_by(id=node_id).first()
            if not n:
                return None
            current = n.metadata_ or {}
            current.update(patch or {})
            n.metadata_ = current
            db.commit()
            db.refresh(n)
            return CaseNodeModel.model_validate(n)

    def list_cases_by_user(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
        vendor: Optional[str] = None,
        category: Optional[str] = None,
    ) -> CaseListResponse:
        with get_db() as db:
            query = db.query(Case).filter_by(user_id=user_id)
            if status:
                query = query.filter(Case.status == status)
            if vendor:
                query = query.filter(Case.vendor == vendor)
            if category:
                query = query.filter(Case.category == category)

            total = query.count()
            items = (
                query.order_by(Case.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            return CaseListResponse(
                items=[CaseModel.model_validate(i) for i in items],
                total=total,
                page=page,
                page_size=page_size,
            )
