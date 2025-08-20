import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import Request

from open_webui.env import SRC_LOG_LEVELS
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.task import get_task_model_id
from open_webui.routers.pipelines import process_pipeline_inlet_filter


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


def _extract_text_from_node_content(raw: str) -> str:
    if not raw:
        return ""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return str(obj.get("text") or obj.get("analysis") or obj.get("answer") or "")
        return str(obj)
    except Exception:
        return str(raw)


def build_regeneration_messages(
    original_text: str,
    user_prompt: Optional[str] = None,
    strategy: Optional[str] = None,
    language: str = "zh",
) -> List[Dict[str, str]]:
    system_instr_zh = (
        "你是资深的网络诊断助手。基于提供的原始内容与可选的用户提示，"
        "请产出更高质量且结构清晰的结果：包含问题分析、可能原因、排查步骤、建议命令、结论摘要。"
        "保持客观、可执行、条理清晰；如有不确定之处请标注。"
    )
    system_instr_en = (
        "You are a senior network troubleshooting assistant. Based on the given content and optional user prompt, "
        "produce a higher-quality, well-structured result: include analysis, possible causes, troubleshooting steps, suggested commands, and a concise summary. "
        "Be objective, actionable, and explicit about uncertainties."
    )
    system_msg = system_instr_zh if language.startswith("zh") else system_instr_en

    user_parts = []
    if original_text:
        user_parts.append(f"[原始内容]\n{original_text}")
    if strategy:
        user_parts.append(f"[生成策略]\n{strategy}")
    if user_prompt:
        user_parts.append(f"[用户提示]\n{user_prompt}")
    user_msg = "\n\n".join(user_parts) if user_parts else "请重新组织并加强上述内容。"

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


async def regenerate_with_model(
    request: Request,
    user: Any,
    messages: List[Dict[str, str]],
    model_hint: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    # Select model
    models = request.app.state.MODELS
    if not models:
        raise RuntimeError("No models available for regeneration")

    base_model_id = None
    if model_hint and model_hint in models:
        base_model_id = model_hint
    else:
        # Pick an arbitrary model as default base
        base_model_id = next(iter(models.keys()))

    task_model_id = get_task_model_id(
        base_model_id,
        getattr(request.app.state.config, "TASK_MODEL", None),
        getattr(request.app.state.config, "TASK_MODEL_EXTERNAL", None),
        models,
    )

    payload = {
        "model": task_model_id,
        "messages": messages,
        "stream": False,
        "metadata": {
            **(metadata or {}),
        },
    }

    # Pipeline inlet filters
    payload = await process_pipeline_inlet_filter(request, payload, user, models)

    # Generate
    res = await generate_chat_completion(request, form_data=payload, user=user)

    # res is expected to be a JSONResponse-like
    try:
        body = res.body.decode("utf-8") if hasattr(res, "body") else str(res)
        data = json.loads(body)
        # OpenAI-style
        choices = data.get("choices") or []
        if choices:
            msg = choices[0].get("message") or {}
            content = msg.get("content")
            if content:
                return content
        # Fallbacks
        if isinstance(data, dict) and data.get("content"):
            return data["content"]
    except Exception as e:
        log.debug(f"Failed to parse model response: {e}")

    raise RuntimeError("Regeneration call succeeded but no content was returned")
