# 调用赛题指定的 ima OpenAPI 脚本。凭证只从环境变量读取。

import json
import os
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "ima-skill" / "ima_api.cjs"
CACHE = ROOT / ".ima-cache"
KB_QUERY = "任德耀新建华为PC知识库"


class ImaError(RuntimeError):
    pass


def credentials_configured():
    client_id = os.environ.get("IMA_OPENAPI_CLIENTID") or os.environ.get("IMA_CLIENT_ID")
    api_key = os.environ.get("IMA_OPENAPI_APIKEY") or os.environ.get("IMA_API_KEY")
    return bool(client_id and api_key)


def _seed_update_check():
    """官方脚本每天会先检查技能更新。把检查日记到本地，避免更新提示挡住检索。"""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / "last_update_check"
    path.write_text(date.today().isoformat(), encoding="utf-8")
    return path


def redact(text):
    if not text:
        return ""
    cleaned = text
    for name in ("IMA_OPENAPI_APIKEY", "IMA_API_KEY", "IMA_OPENAPI_CLIENTID", "IMA_CLIENT_ID"):
        value = os.environ.get(name) or ""
        if len(value) >= 6:
            cleaned = cleaned.replace(value, "（已隐藏）")
    return cleaned


class ImaClient:
    def __init__(self, runner=None):
        self.runner = runner or self._run_script

    def _run_script(self, api_path, body):
        if not SCRIPT.exists():
            raise ImaError("找不到 ima-skill/ima_api.cjs")
        if not credentials_configured():
            raise ImaError("未配置 ima 凭证")
        env = os.environ.copy()
        env["IMA_LAST_CHECK_FILE"] = str(_seed_update_check())
        try:
            completed = subprocess.run(
                ["node", str(SCRIPT), api_path, json.dumps(body, ensure_ascii=False)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=40,
                env=env,
                cwd=str(ROOT),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ImaError("ima 接口超时") from exc
        except FileNotFoundError as exc:
            raise ImaError("未安装 Node.js，无法调用 ima 脚本") from exc
        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if completed.returncode != 0:
            message = stderr or stdout or "ima 调用失败"
            try:
                payload = json.loads(stderr or stdout or "{}")
                message = payload.get("msg") or message
            except json.JSONDecodeError:
                pass
            raise ImaError(redact(message))
        try:
            payload = json.loads(stdout or "{}")
        except json.JSONDecodeError as exc:
            raise ImaError("ima 返回的不是 JSON") from exc
        code = payload.get("code", 0) if isinstance(payload, dict) else 0
        if code not in (0, "0", None):
            raise ImaError(redact(str(payload.get("msg") or "ima 接口返回错误")))
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return payload["data"]
        return payload if isinstance(payload, dict) else {}

    def call(self, api_path, body):
        return self.runner(api_path, body)

    def search_knowledge_base(self):
        data = self.call(
            "openapi/wiki/v1/search_knowledge_base",
            {"query": KB_QUERY, "cursor": "", "limit": 20},
        )
        items = _as_list(data, "info_list", "knowledge_base_list")
        exact = []
        fuzzy = []
        for item in items:
            name = item.get("kb_name") or item.get("name") or ""
            kb_id = item.get("kb_id") or item.get("id") or item.get("knowledge_base_id") or ""
            record = {"id": kb_id, "name": name}
            if name == KB_QUERY:
                exact.append(record)
            elif KB_QUERY in name or name in KB_QUERY:
                fuzzy.append(record)
        found = exact or fuzzy
        if not found:
            raise ImaError("当前账号下没有找到共享知识库「" + KB_QUERY + "」")
        return found[0]

    def search_knowledge(self, kb_id, query):
        data = self.call(
            "openapi/wiki/v1/search_knowledge",
            {"query": query, "cursor": "", "knowledge_base_id": kb_id},
        )
        return _as_list(data, "info_list")

    def list_knowledge(self, kb_id, folder_id=""):
        """翻页浏览目录。media_type 99 是文件夹，其余带 media_id 的是文件。"""
        files = []
        folders = []
        cursor = ""
        for _ in range(20):
            body = {"knowledge_base_id": kb_id, "cursor": cursor, "limit": 50}
            if folder_id:
                body["folder_id"] = folder_id
            data = self.call("openapi/wiki/v1/get_knowledge_list", body)
            if not isinstance(data, dict):
                break
            page_files, page_folders = _split_entries(data)
            files.extend(page_files)
            folders.extend(page_folders)
            next_cursor = data.get("next_cursor") or ""
            if data.get("is_end") or not next_cursor or next_cursor == cursor:
                break
            if not page_files and not page_folders:
                break
            cursor = next_cursor
        return files, folders

    def get_media_info(self, media_id):
        return self.call("openapi/wiki/v1/get_media_info", {"media_id": media_id})

    def get_note_text(self, note_id):
        data = self.call(
            "openapi/note/v1/get_doc_content",
            {"note_id": note_id, "target_content_format": 0},
        )
        return data.get("content") or ""


def _as_list(data, *keys):
    if not isinstance(data, dict):
        return []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _split_entries(data):
    files = []
    folders = []
    if not isinstance(data, dict):
        return files, folders
    for key in ("knowledge_list", "info_list", "folder_list"):
        for item in _as_list(data, key):
            if not isinstance(item, dict):
                continue
            if item.get("media_type") == 99 or (item.get("folder_id") and not item.get("media_id")):
                folder = dict(item)
                folder["folder_id"] = item.get("folder_id") or item.get("media_id") or ""
                folder["name"] = item.get("name") or item.get("title") or ""
                folders.append(folder)
            elif item.get("media_id"):
                files.append(item)
            elif item.get("name"):
                folders.append(item)
    return files, folders
