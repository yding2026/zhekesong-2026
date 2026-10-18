# 赛题第五、六项：检查技能和凭证，并只读调用共享知识库。
# 终端里只打印名称、数量和正文字数，不打印密钥、知识库 ID 和原文。

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.ima_client import ImaClient, ImaError, credentials_configured
from agent.pipeline import _read_media_text
from agent.server import load_dotenv

KB_NAME = "任德耀新建华为PC知识库"
TARGET_FOLDER = "P1-产品参数库"
SAMPLE_MODEL = "HUAWEI MateBook 14"
FACT_NAMES = ("产品事实.md", "article.md")


def title_of(item):
    if not isinstance(item, dict):
        return ""
    return (item.get("title") or item.get("name") or item.get("kb_name") or "").strip()


def find_named(items, name):
    for item in items:
        if title_of(item) == name:
            return item
    return None


def library_root(client, kb_id):
    """接口根目录只有一个同名文件夹，真正的 P1–P8 在它里面。"""
    files, folders = client.list_knowledge(kb_id)
    if not files and len(folders) == 1:
        files, folders = client.list_knowledge(kb_id, folders[0].get("folder_id") or "")
    return files, folders


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv()
    print("技能脚本：", "存在" if (ROOT / "ima-skill" / "ima_api.cjs").exists() else "缺失")
    print("技能版本文件：", "存在" if (ROOT / "ima-skill" / "meta.json").exists() else "缺失")
    print("Node 调用入口：ima-skill/ima_api.cjs")
    if not credentials_configured():
        print("凭证：未配置")
        print("请先完成这两步，再重新运行本脚本：")
        print("1. 用加入知识库的同一个 ima 账号打开 https://ima.qq.com/agent-interface")
        print("2. 把 Client ID 和 API Key 写入 huawei-pc-agent/.env 的 IMA_OPENAPI_CLIENTID 和 IMA_OPENAPI_APIKEY")
        return 2

    print("凭证：已从环境变量读到，不显示内容")
    client = ImaClient()
    try:
        kb = client.search_knowledge_base()
    except ImaError as exc:
        print("A. 查找知识库失败：", exc)
        print("请确认当前凭证所属账号已经扫码加入「%s」。" % KB_NAME)
        return 1
    print("A. 已找到知识库：", kb.get("name") or KB_NAME)

    try:
        files, folders = library_root(client, kb["id"])
    except ImaError as exc:
        print("B. 浏览目录失败：", exc)
        return 1
    names = [title_of(item) for item in folders + files if title_of(item)]
    print("B. 库内顶层条目：", len(names))
    for name in names[:12]:
        print("   -", name)
    if len(names) > 12:
        print("   - …其余 %d 项省略" % (len(names) - 12))

    folder = find_named(folders, TARGET_FOLDER)
    if folder is None:
        print("B. 没有找到「%s」。" % TARGET_FOLDER)
        return 1
    try:
        _series_files, series = client.list_knowledge(kb["id"], folder.get("folder_id") or "")
    except ImaError as exc:
        print("B. 读取产品参数库失败：", exc)
        return 1
    print("B. 已进入：", TARGET_FOLDER, "；子目录", len(series))
    for item in series:
        print("   -", title_of(item))

    model = None
    model_files = []
    for series_folder in series:
        try:
            children, nested = client.list_knowledge(kb["id"], series_folder.get("folder_id") or "")
        except ImaError as exc:
            print("B. 读取子目录失败：", title_of(series_folder), exc)
            return 1
        found = find_named(nested, SAMPLE_MODEL)
        if found is not None:
            model = found
            try:
                model_files, _images = client.list_knowledge(kb["id"], found.get("folder_id") or "")
            except ImaError as exc:
                print("B. 读取型号目录失败：", exc)
                return 1
            print("B. 型号目录：", title_of(series_folder), "/", SAMPLE_MODEL)
            break
    if model is None:
        print("B. 在产品参数库里没有找到型号「%s」。" % SAMPLE_MODEL)
        return 1
    print("   该型号文件：")
    for item in model_files:
        print("   -", title_of(item))

    fact = None
    for name in FACT_NAMES:
        fact = find_named(model_files, name)
        if fact is not None:
            break
    if fact is None:
        print("D. 型号目录里没有产品事实文件。")
        return 1

    try:
        hits = client.search_knowledge(kb["id"], SAMPLE_MODEL)
    except ImaError as exc:
        print("C. 按型号搜索失败：", exc)
        return 1
    print("C. 搜索「%s」命中：" % SAMPLE_MODEL, len(hits))
    shown = []
    for item in hits:
        name = title_of(item)
        if name and name not in shown:
            shown.append(name)
        if len(shown) >= 5:
            break
    for name in shown:
        print("   -", name)

    try:
        info = client.get_media_info(fact.get("media_id") or "")
        text = _read_media_text(client, fact)
    except ImaError as exc:
        print("D. 读取原文失败：", exc)
        return 1
    has_url = bool(((info.get("url_info") or {}).get("url")))
    print("D. 已读取", title_of(fact), "；媒体类型", info.get("media_type"), "；有访问链接" if has_url else "；没有访问链接", "；正文", len(text or ""), "字")
    if not text:
        print("D. 原文是空的，请到 ima 客户端里打开该文件确认。")
        return 1
    print("接入测试通过：知识库可查找、目录可浏览、型号可搜索、原文可读取。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
