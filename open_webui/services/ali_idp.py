"""
Alibaba Document Intelligence (DocMind) service integration for Open WebUI.

This module wraps Alibaba Cloud DocMind API (20220711) to parse documents
and retrieve structured results. It prefers environment/default credentials
via `alibabacloud_credentials` just like the reference backend.

Notes:
- If the required SDKs are not installed, the client will raise a clear
  error when used.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict

log = logging.getLogger(__name__)


class AliIDPClient:
    def __init__(self) -> None:
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            from alibabacloud_docmind_api20220711.client import (
                Client as DocmindClient,
            )
            from alibabacloud_tea_openapi import models as open_api_models
            from alibabacloud_credentials.client import Client as CredClient

            cred = CredClient()
            conf = open_api_models.Config(
                access_key_id=cred.get_credential().access_key_id,
                access_key_secret=cred.get_credential().access_key_secret,
            )
            conf.endpoint = os.getenv(
                "ALIBABA_IDP_ENDPOINT", "docmind-api.cn-hangzhou.aliyuncs.com"
            )
            self._client = DocmindClient(conf)
            log.info("AliIDPClient initialized")
        except Exception as e:
            log.error(
                "AliIDPClient init failed (SDK not installed or credential error): %s",
                e,
            )
            self._client = None

    def _require_client(self):
        if self._client is None:
            raise RuntimeError(
                "AliIDPClient not initialized. Ensure Alibaba Cloud SDKs are installed and credentials are set."
            )
        return self._client

    def parse_document(self, file_path: str, enable_llm: bool = True, enable_formula: bool = True) -> Dict[str, Any]:
        client = self._require_client()
        try:
            from alibabacloud_docmind_api20220711 import models as docmind_models
            from alibabacloud_tea_util import models as util_models

            request = docmind_models.SubmitDocParserJobAdvanceRequest(
                file_url_object=open(file_path, "rb"),
                file_name=os.path.basename(file_path),
                llm_enhancement=enable_llm,
                formula_enhancement=enable_formula,
            )
            runtime = util_models.RuntimeOptions()
            resp = self._client.submit_doc_parser_job_advance(request, runtime)
            job_id = resp.body.data.id
            return self._poll_and_collect(job_id)
        except Exception as e:
            raise RuntimeError(f"Ali IDP parse_document failed: {e}")

    def parse_document_from_url(
        self, file_url: str, file_name: str, enable_llm: bool = True, enable_formula: bool = True
    ) -> Dict[str, Any]:
        client = self._require_client()
        try:
            from alibabacloud_docmind_api20220711 import models as docmind_models

            req = docmind_models.SubmitDocParserJobRequest(
                file_url=file_url,
                file_name=file_name,
                llm_enhancement=enable_llm,
                formula_enhancement=enable_formula,
            )
            resp = client.submit_doc_parser_job(req)
            job_id = resp.body.data.id
            return self._poll_and_collect(job_id)
        except Exception as e:
            raise RuntimeError(f"Ali IDP parse_document_from_url failed: {e}")

    def _poll_and_collect(self, job_id: str) -> Dict[str, Any]:
        from alibabacloud_docmind_api20220711 import models as docmind_models

        max_attempts = int(os.getenv("ALIBABA_IDP_MAX_POLLING_ATTEMPTS", "120"))
        interval = int(os.getenv("ALIBABA_IDP_POLLING_INTERVAL", "10"))
        attempt = 0

        while attempt < max_attempts:
            try:
                st_req = docmind_models.QueryDocParserStatusRequest(id=job_id)
                st_resp = self._client.query_doc_parser_status(st_req)
                status = st_resp.body.data.status
                if status == "success":
                    return self._get_complete_result(job_id)
                if status == "Fail":
                    raise RuntimeError(f"Ali IDP job failed: {job_id}")
                time.sleep(interval)
                attempt += 1
            except Exception as e:
                log.warning("Ali IDP status check error: %s", e)
                time.sleep(interval)
                attempt += 1
                continue
        raise TimeoutError(f"Ali IDP job timeout: {job_id}")

    def _get_complete_result(self, job_id: str) -> Dict[str, Any]:
        from alibabacloud_docmind_api20220711 import models as docmind_models

        result: Dict[str, Any] = {
            "layouts": [],
            "logics": None,
            "tables": [],
            "paragraphs": [],
            "images": [],
        }
        layout_num = 0
        step = int(os.getenv("ALIBABA_IDP_LAYOUT_STEP_SIZE", "100"))

        while True:
            req = docmind_models.GetDocParserResultRequest(
                id=job_id, layout_num=layout_num, layout_step_size=step
            )
            resp = self._client.get_doc_parser_result(req)
            data = resp.body.data
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except Exception:
                    data = {}

            layouts = data.get("layouts") or []
            result["layouts"].extend(layouts)
            if layout_num == 0:
                result["logics"] = data.get("logics")
                result["tables"] = data.get("tables", [])
                result["paragraphs"] = data.get("paragraphs", [])
                result["images"] = data.get("images", [])

            layout_num += len(layouts)
            if len(layouts) < step:
                break
        return result
