import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.auth import get_verified_user
from open_webui.models.knowledge import Knowledges
from open_webui.retrieval.utils import get_embedding_function
from open_webui.routers.retrieval import get_ef
from open_webui.retrieval.vector.factory import VECTOR_DB_CLIENT
from open_webui.config import (
    RAG_EMBEDDING_ENGINE,
    RAG_EMBEDDING_MODEL,
    RAG_EMBEDDING_BATCH_SIZE,
    RAG_OPENAI_API_BASE_URL,
    RAG_OPENAI_API_KEY,
    RAG_AZURE_OPENAI_BASE_URL,
    VECTOR_DB,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


class LogParsingRequest(BaseModel):
    logType: str
    vendor: str
    logContent: str
    contextInfo: dict | None = None


class LogParsingResponse(BaseModel):
    parsed_data: dict | None = None
    analysis_result: dict | None = None
    severity: str | None = None
    recommendations: list[str] | None = None
    related_knowledge: list[dict] | None = None


@router.post("/log-parsing", response_model=LogParsingResponse)
async def parse_log(req: LogParsingRequest, request: Request, user=Depends(get_verified_user)):
    # 1) 基础校验
    if not req.logType:
        raise HTTPException(status_code=400, detail="logType is required")
    if not req.vendor:
        raise HTTPException(status_code=400, detail="vendor is required")
    if not req.logContent or not req.logContent.strip():
        raise HTTPException(status_code=400, detail="logContent is required")

    # 2) 解析日志（参考 backend 的规则，做轻量实现）
    parsed = _parse_log_simple(req.logType, req.vendor, req.logContent, req.contextInfo or {})

    # 3) 生成相关知识（基于可访问的知识库做向量检索）
    try:
        related = _search_related_knowledge(
            query=_build_query_from_parsed(parsed, req),
            user_id=user.id,
            request=request,
        )
    except Exception as e:
        log.warning(f"related_knowledge search failed: {e}")
        related = []

    # 4) 汇总结果
    return LogParsingResponse(
        parsed_data=parsed,
        analysis_result={
            "summary": parsed.get("summary"),
            "anomalies": parsed.get("anomalies", []),
            "keyEvents": parsed.get("keyEvents", []),
        },
        severity=parsed.get("severity"),
        recommendations=[r.get("action") for r in parsed.get("suggestedActions", [])],
        related_knowledge=related,
    )


# ============ 内部实现（轻量版） ============
_RULES = {
    "ospf_debug": {
        "patterns": {
            "mtu_mismatch": r"MTU mismatch|packet too big|DD packet size exceeds|MTU不匹配",
            "neighbor_stuck": r"ExStart|neighbor stuck|邻居状态|neighbor state",
            "authentication_fail": r"authentication|认证失败|auth fail",
            "area_mismatch": r"area mismatch|区域不匹配|different area",
            "hello_timer": r"hello timer|hello interval|hello间隔",
        },
        "severities": {
            "mtu_mismatch": "high",
            "neighbor_stuck": "high",
            "authentication_fail": "high",
            "area_mismatch": "medium",
            "hello_timer": "medium",
        },
    },
    "system_log": {
        "patterns": {
            "interface_down": r"interface.*down|接口.*down|link down",
            "memory_high": r"memory.*high|内存.*高|out of memory",
            "cpu_high": r"cpu.*high|CPU.*高|cpu utilization",
        },
        "severities": {
            "interface_down": "high",
            "memory_high": "high",
            "cpu_high": "medium",
        },
    },
}


def _parse_log_simple(log_type: str, vendor: str, content: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    import re

    rules = _RULES.get(log_type, {})
    patterns = rules.get("patterns", {})
    severities = rules.get("severities", {})

    anomalies: List[Dict[str, Any]] = []
    for name, pat in patterns.items():
        m = re.search(pat, content, flags=re.IGNORECASE | re.MULTILINE)
        if not m:
            continue
        line_start = max(0, content.rfind("\n", 0, m.start()) + 1)
        line_end = content.find("\n", m.end())
        if line_end == -1:
            line_end = len(content)
        evidence = content[line_start:line_end].strip()
        anomalies.append(
            {
                "type": name.upper(),
                "severity": severities.get(name, "medium"),
                "evidence": [evidence],
                "lineNumber": content[: m.start()].count("\n") + 1,
            }
        )

    severity = "low"
    if any(a["severity"] == "high" for a in anomalies):
        severity = "high"
    elif any(a["severity"] == "medium" for a in anomalies):
        severity = "medium"

    suggested = _suggest_actions(anomalies, vendor)
    summary = _build_summary(anomalies, log_type, vendor)

    return {
        "summary": summary,
        "anomalies": anomalies,
        "suggestedActions": suggested,
        "keyEvents": [a.get("evidence", [""])[0] for a in anomalies][:5],
        "severity": severity,
    }


def _suggest_actions(anomalies: List[Dict[str, Any]], vendor: str) -> List[Dict[str, Any]]:
    template = {
        "mtu_mismatch": {
            "action": "检查并统一接口MTU配置",
            "commands": {
                "Huawei": ["display interface GE0/0/1", "interface GE0/0/1", "mtu 1500", "commit"],
                "Cisco": ["show interface Gi0/0", "conf t", "int Gi0/0", "mtu 1500", "end"],
            },
        },
        "neighbor_stuck": {
            "action": "重置OSPF进程并检查配置",
            "commands": {
                "Huawei": ["reset ospf process", "display ospf peer"],
                "Cisco": ["clear ip ospf process", "show ip ospf neighbor"],
            },
        },
        "interface_down": {
            "action": "检查接口物理状态和配置",
            "commands": {
                "Huawei": ["display interface GE0/0/1", "undo shutdown"],
                "Cisco": ["show interface Gi0/0", "no shutdown"],
            },
        },
    }

    out = []
    for a in anomalies:
        t = template.get(a["type"].lower()) or template.get(a["type"].lower().split("_")[0])
        if t:
            cmds = t["commands"].get(vendor.capitalize()) or next(iter(t["commands"].values()))
            out.append({"action": t["action"], "commands": cmds})
    return out


def _build_summary(anomalies: List[Dict[str, Any]], log_type: str, vendor: str) -> str:
    if not anomalies:
        return f"未检测到明显异常（日志类型: {log_type}, 厂商: {vendor}）。"
    types = ", ".join(sorted({a["type"] for a in anomalies}))
    return f"检测到异常类型：{types}。请根据建议进行排查处理。"


def _build_query_from_parsed(parsed: Dict[str, Any], req: LogParsingRequest) -> str:
    base = parsed.get("summary", "")
    if not base:
        base = req.logContent[:500]
    # 拼接关键字以增强检索效果
    keywords = [a.get("type", "") for a in parsed.get("anomalies", [])]
    return (base + " " + " ".join(keywords)).strip()


def _search_related_knowledge(query: str, user_id: str, request: Request) -> List[Dict[str, Any]]:
    # 获取可访问的知识库
    if not query:
        return []
    kbs = Knowledges.get_knowledge_bases_by_user_id(user_id, "read")

    # 构建嵌入函数
    ef = get_ef(
        engine=RAG_EMBEDDING_ENGINE.value,
        embedding_model=RAG_EMBEDDING_MODEL.value,
        auto_update=False,
    )
    embedding_function = get_embedding_function(
        embedding_engine=RAG_EMBEDDING_ENGINE.value,
        embedding_model=RAG_EMBEDDING_MODEL.value,
        embedding_function=ef,
        url=(RAG_AZURE_OPENAI_BASE_URL.value or RAG_OPENAI_API_BASE_URL.value),
        key=RAG_OPENAI_API_KEY.value,
        embedding_batch_size=RAG_EMBEDDING_BATCH_SIZE.value,
        azure_api_version=None,
    )

    qvec = embedding_function(query, prefix=None)

    # 针对每个知识库检索Top-3，合并排序取Top-5
    agg: List[Dict[str, Any]] = []
    for kb in kbs:
        try:
            res = VECTOR_DB_CLIENT.search(collection_name=kb.id, vectors=[qvec], limit=3)
            if not res or not res.ids:
                continue
            for i, _id in enumerate(res.ids[0]):
                agg.append(
                    {
                        "knowledge_id": kb.id,
                        # distances semantics vary by backend; normalize later
                        "distance": float(res.distances[0][i]) if res.distances else None,
                        "content": res.documents[0][i] if res.documents else "",
                        "metadata": res.metadatas[0][i] if res.metadatas else {},
                    }
                )
        except Exception as e:
            log.debug(f"kb search failed for {kb.id}: {e}")
            continue

    # 归一化分数：
    for item in agg:
        d = item.get("distance")
        if d is None:
            # 没有提供距离，无法归一化；设为0
            item["score"] = 0.0
        else:
            if str(VECTOR_DB).lower() == "weaviate":
                # 距离越小越相似，将其映射到(0,1]，越大越低
                item["score"] = 1.0 / (1.0 + float(d))
            else:
                # 其他后端一般返回相似度或得分，保留为“越大越好”的语义
                item["score"] = float(d)

    agg_sorted = sorted(agg, key=lambda x: x.get("score", 0), reverse=True)[:5]
    # 输出统一结构
    for it in agg_sorted:
        if "distance" in it:
            del it["distance"]
    return agg_sorted
