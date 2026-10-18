# 用夹具验证闭环。夹具不是华为资料，也不能当作参赛运行结果。

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.pipeline import run

FIXTURE_DOC = "MateBook 测试型号 重量约 1.28 kg，资料标明续航最长 10 小时。屏幕为 14 英寸。"


class FixtureClient:
    """只在单元测试里使用，模拟 ima 返回的一条资料和一张同型号图片。"""

    def search_knowledge_base(self):
        return {"id": "kb-test", "name": "任德耀新建华为PC知识库"}

    def search_knowledge(self, kb_id, query):
        if "图片" in query:
            return [{"media_id": "img-1", "title": "MateBook 测试型号-主图.png", "media_type": 9}]
        if "相近" in query:
            return []
        return [
            {
                "media_id": "doc-1",
                "title": "MateBook 测试型号 article.md",
                "highlight_content": FIXTURE_DOC,
            },
            {
                "media_id": "doc-2",
                "title": "MateBook 另一型号 article.md",
                "highlight_content": "MateBook 另一型号 重量约 1.90 kg",
            },
        ]

    def list_knowledge(self, kb_id, folder_id=""):
        return [], []

    def get_media_info(self, media_id):
        if media_id == "img-1":
            return {"media_type": 9}
        return {"media_type": 7, "url_info": {}}

    def get_note_text(self, note_id):
        return ""


def main():
    os.environ.pop("LLM_API_KEY", None)
    os.environ.pop("IMA_OPENAPI_CLIENTID", None)
    os.environ.pop("IMA_OPENAPI_APIKEY", None)
    os.environ.pop("IMA_CLIENT_ID", None)
    os.environ.pop("IMA_API_KEY", None)
    incomplete = run({"product": "轻薄本", "audience": "大学新生", "scene": "开学季", "platform": "小红书"})
    assert incomplete["status"] == "need_more", incomplete
    assert any("具体型号" in item for item in incomplete["questions"])

    blocked = run(
        {"product": "MateBook 测试型号", "audience": "大学新生", "scene": "开学季", "platform": "小红书"},
        client=None,
    )
    assert blocked["status"] == "blocked"
    assert "1.28" not in blocked.get("markdown", "")

    client = FixtureClient()
    xiaohongshu = run(
        {
            "product": "MateBook 测试型号",
            "audience": "大学新生",
            "scene": "开学季",
            "platform": "小红书",
            "extra": "请写上国补价格",
        },
        client=client,
    )
    wechat = run(
        {
            "product": "MateBook 测试型号",
            "audience": "出差的商务人士",
            "scene": "职场办公",
            "platform": "公众号",
        },
        client=client,
    )
    moments = run(
        {
            "product": "MateBook 测试型号",
            "audience": "附近顾客",
            "scene": "门店到访",
            "platform": "门店朋友圈",
        },
        client=client,
    )
    assert xiaohongshu["status"] == "ok", xiaohongshu
    assert "1.28" in xiaohongshu["markdown"]
    assert "亲测" in xiaohongshu["article"]["lead"]
    assert xiaohongshu["strategy"]["angle"] != wechat["strategy"]["angle"]
    assert xiaohongshu["strategy"]["max_images"] == 6
    assert moments["strategy"]["max_facts"] == 1
    assert "另一型号" not in xiaohongshu["article"]["body"]
    assert any("国补" in item or "价格" in item for item in xiaohongshu["verification"]["pending"])
    assert "1.90" not in xiaohongshu["markdown"]
    print("selfcheck ok")


if __name__ == "__main__":
    main()
