# 一次营销任务的闭环：理解、检索、编排、核验、导出。

import json
import os
import re
import urllib.request
from urllib.error import URLError

from agent.ima_client import ImaClient, ImaError, credentials_configured
from agent.prompts import SYSTEM_PROMPT
from agent.strategy import PLATFORMS, VAGUE_PRODUCTS, build_strategy

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")
FAMILY_WORDS = ("matebook", "擎云", "matepad")
UNIT_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:mm|cm|kg|g|wh|w|hz|nits|nit|小时|英寸)|usb|hdmi|雷电", re.I)
PRICE_ASK_RE = re.compile(r"价格|多少钱|补贴|国补|优惠|折扣|库存|赠品")
ABSOLUTE_WORDS = ["最强", "最轻", "最好", "第一", "唯一", "绝对", "100%", "永久", "全网最低", "无敌", "完美", "顶级"]
PROMISE_WORDS = ["免费送", "保本", "稳赚", "必买", "闭眼入", "秒杀", "零差评"]
BASH_WORDS = ["吊打", "碾压", "远超", "完胜", "垃圾"]
COMPETITORS = ["苹果", "MacBook", "联想", "戴尔", "小米", "惠普", "华硕", "ThinkPad", "微软"]
PRICE_RE = re.compile(r"(¥|￥|\d+\s*元|补贴|国补|优惠券|直降|立减)")


def normalize(text):
    return re.sub(r"\s+", "", text or "").lower()


def check_task(task):
    """信息不足时返回要追问的问题，不生成软文。"""
    questions = []
    product = (task.get("product") or "").strip()
    audience = (task.get("audience") or "").strip()
    scene = (task.get("scene") or "").strip()
    platform = (task.get("platform") or "").strip()
    if not product or normalize(product) in VAGUE_PRODUCTS:
        questions.append("请补充具体型号。只写「轻薄本」或「笔记本」还不够，相近型号的配置、接口和图片不能混用。")
    if not audience:
        questions.append("这篇内容写给谁？例如大学新生、经常出差的职场用户、家庭换新用户。")
    if not scene:
        questions.append("用在哪个业务场景？例如开学季、职场办公、门店到访。")
    if platform not in PLATFORMS:
        questions.append("发布到哪个平台？请选择公众号、小红书、门店朋友圈或门店海报。")
    return questions


def _looks_like_other_model(title, product):
    title_n = normalize(title)
    product_n = normalize(product)
    if not title_n or product_n in title_n:
        return False
    return any(word in title_n for word in FAMILY_WORDS)


def _is_image_item(item):
    title = item.get("title") or item.get("name") or ""
    media_type = item.get("media_type")
    if media_type == 9:
        return True
    lower = title.lower()
    return lower.endswith(IMAGE_EXT) or "主图" in title or "场景图" in title


def _strip_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _extract_lines(text, product):
    product_n = normalize(product)
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip().lstrip("-•*0123456789.、)） ").strip()
        if len(line) < 8 or len(line) > 180:
            continue
        if product_n in normalize(line) or UNIT_RE.search(line):
            lines.append(line)
    deduped = []
    seen = set()
    for line in lines:
        if line not in seen:
            seen.add(line)
            deduped.append(line)
    return deduped[:12]


def _fetch_url_text(url, headers):
    request = urllib.request.Request(url, headers=headers or {"User-Agent": "huawei-pc-agent"})
    with urllib.request.urlopen(request, timeout=12) as response:
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "image/" in content_type or "pdf" in content_type:
            return ""
        payload = response.read(5000)
    if payload.startswith(b"%PDF"):
        return ""
    return payload.decode("utf-8", errors="replace")


def _read_media_text(client, item):
    media_id = item.get("media_id") or ""
    highlight = _strip_html(item.get("highlight_content") or "")
    if not media_id:
        return highlight
    try:
        info = client.get_media_info(media_id)
    except ImaError:
        return highlight
    if info.get("media_type") == 11:
        note_id = ((info.get("notebook_ext_info") or {}).get("notebook_id")) or ""
        if not note_id:
            return highlight
        try:
            return client.get_note_text(note_id) or highlight
        except ImaError:
            return highlight
    url_info = info.get("url_info") or {}
    url = url_info.get("url") or ""
    if not url:
        return highlight
    try:
        text = _fetch_url_text(url, url_info.get("headers") or {})
    except (URLError, TimeoutError, OSError):
        return highlight
    return text or highlight


def _rank_facts(facts, priority):
    def score(fact):
        text = fact["text"]
        for index, word in enumerate(priority):
            if word in text:
                return index
        return len(priority) + 1

    return sorted(facts, key=score)


def retrieve(client, product):
    """按赛题顺序检索：先搜库，搜索为空时改浏览目录。"""
    kb = client.search_knowledge_base()
    queries = [product, product + " 参数", product + " 图片"]
    found = []
    seen = set()
    for query in queries:
        for item in client.search_knowledge(kb["id"], query):
            media_id = item.get("media_id") or item.get("folder_id") or item.get("title")
            if media_id in seen:
                continue
            seen.add(media_id)
            found.append(item)
    browsed = False
    if not found:
        browsed = True
        files, folders = client.list_knowledge(kb["id"])
        target = None
        for folder in folders:
            name = folder.get("name") or ""
            if "产品参数" in name or name.startswith("P1") or "P1" in name:
                target = folder
                break
        if target:
            folder_id = target.get("folder_id") or ""
            files, _nested = client.list_knowledge(kb["id"], folder_id)
        for item in files:
            title = item.get("title") or item.get("name") or ""
            if normalize(product) in normalize(title):
                found.append(item)
    documents = []
    images = []
    skipped_models = []
    for item in found:
        title = item.get("title") or item.get("name") or "未命名资料"
        if _looks_like_other_model(title, product):
            skipped_models.append(title)
            continue
        if _is_image_item(item):
            if normalize(product) not in normalize(title):
                skipped_models.append(title)
                continue
            images.append(
                {
                    "name": title,
                    "media_id": item.get("media_id") or "",
                    "source": "任德耀新建华为PC知识库 / " + title,
                }
            )
            continue
        text = _read_media_text(client, item)
        excerpt = text[:1200]
        facts = [{"text": line, "title": title} for line in _extract_lines(excerpt, product)]
        if not facts and _strip_html(item.get("highlight_content") or ""):
            facts = [{"text": _strip_html(item["highlight_content"])[:180], "title": title}]
        documents.append({"title": title, "media_id": item.get("media_id") or "", "excerpt": excerpt[:400], "facts": facts})
    flat_facts = []
    seen_facts = set()
    for document in documents:
        for fact in document["facts"]:
            if fact["text"] in seen_facts:
                continue
            seen_facts.add(fact["text"])
            flat_facts.append(fact)
    return {
        "kb_name": kb["name"],
        "kb_found": True,
        "browsed_catalog": browsed,
        "documents": documents[:6],
        "facts": flat_facts,
        "images": images[:6],
        "skipped_models": skipped_models[:8],
    }


def _drop_conflicts(facts):
    """同一事实点出现不同数字时，两条都拿掉，交给人工确认。"""
    groups = {}
    for fact in facts:
        for label in ("重量", "续航", "屏幕", "内存", "硬盘", "电池"):
            if label in fact["text"]:
                groups.setdefault(label, []).append(fact)
    blocked = set()
    pending = []
    for label, items in groups.items():
        numbers = []
        for item in items:
            numbers.append(tuple(re.findall(r"\d+(?:\.\d+)?", item["text"])))
        if len(set(numbers)) > 1:
            pending.append(label + "在资料里出现了不同数字，已停止写入，需要人工确认。")
            for item in items:
                blocked.add(item["text"])
    kept = [fact for fact in facts if fact["text"] not in blocked]
    return kept, pending


def compose(task, strategy, facts, images):
    """只用资料原句编排软文，不补写参数。"""
    platform = task["platform"]
    product = task["product"]
    audience = task["audience"]
    scene = task["scene"]
    angle = strategy["angle"]
    chosen = facts[: strategy["max_facts"]]
    chosen_images = images[: strategy["max_images"]]
    positions = {
        "公众号": ["导语之后", "第一节之后", "第二节之后", "结尾之前"],
        "小红书": ["封面", "第2张", "第3张", "第4张", "第5张", "第6张"],
        "门店朋友圈": ["第一条配图", "第二条配图", "第三条配图"],
        "门店海报": ["主视觉"],
    }[platform]
    image_plan = []
    for index, image in enumerate(chosen_images):
        image_plan.append(
            {
                "name": image["name"],
                "source": image["source"],
                "position": positions[index],
                "caption": product + "，资料图片「" + image["name"] + "」",
            }
        )
    fact_lines = [fact["text"] + "（资料：" + fact["title"] + "）" for fact in chosen]
    tags = []
    if platform == "公众号":
        title = scene + "怎么选：" + product + "，先看" + angle
        lead = "这篇写给" + audience + "。场景是" + scene + "，先回答「" + angle + "」，下面每条参数都能回到知识库原文。"
        body = "\n\n".join(fact_lines)
        cta = "当前配置、接口和重量建议到店再核对一次。这里没有写知识库之外的价格和活动。"
    elif platform == "小红书":
        title = audience + "看" + scene + "，先别只看一个参数"
        lead = "这不是个人亲测，是按「" + angle + "」把「" + product + "」的知识库资料整理成笔记。"
        body = "\n".join(fact_lines)
        cta = "想看实机的话，去门店对一下型号和接口，别只靠这篇笔记下单。"
        tags = ["#华为PC", "#" + scene, "#选机笔记"]
    elif platform == "门店朋友圈":
        title = ""
        only = fact_lines[0] if fact_lines else ""
        lead = audience + "如果在看" + scene + "，今天只说一件事。"
        body = only
        cta = "到店可以看实机，配置以门店展出的这台「" + product + "」为准。"
    else:
        title = angle
        lead = product + " · " + audience
        body = "\n".join("· " + line for line in fact_lines)
        cta = "知识库没有提供优惠、补贴或库存，海报不写这些内容。"
    return {
        "title": title,
        "lead": lead,
        "body": body,
        "cta": cta,
        "tags": tags,
        "images": image_plan,
        "used_facts": chosen,
    }


def _article_blob(article):
    parts = [article.get("title") or "", article.get("lead") or "", article.get("body") or "", article.get("cta") or ""]
    parts.extend(article.get("tags") or [])
    return "\n".join(parts)


def verify_facts(article, facts):
    source = "\n".join(fact["text"] for fact in facts)
    source_numbers = set(re.findall(r"\d+(?:\.\d+)?", source))
    results = []
    for fact in article.get("used_facts") or []:
        results.append({"claim": fact["text"], "supported": fact["text"] in source, "source": fact["title"]})
    stray = []
    for number in set(re.findall(r"\d+(?:\.\d+)?", _article_blob(article))):
        if number not in source_numbers:
            stray.append(number)
    return results, stray


def compliance_check(article, facts):
    text = _article_blob(article)
    source = "\n".join(fact["text"] for fact in facts)
    hits = []
    for word in ABSOLUTE_WORDS:
        if word in text and word not in source:
            hits.append({"rule": "绝对化宣传", "hit": word, "action": "资料没有该表述，不得出现在正文"})
    for word in PROMISE_WORDS:
        if word in text:
            hits.append({"rule": "虚假承诺", "hit": word, "action": "删除该承诺"})
    for word in BASH_WORDS:
        if word in text:
            hits.append({"rule": "无依据对比或竞品贬低", "hit": word, "action": "删除对比用语"})
    for name in COMPETITORS:
        if name.lower() in text.lower():
            hits.append({"rule": "竞品提及", "hit": name, "action": "正文不写竞品"})
    if PRICE_RE.search(text) and not PRICE_RE.search(source):
        hits.append({"rule": "价格误导", "hit": "价格或优惠用语", "action": "知识库没有对应依据，不写入正文"})
    return hits


def polish_with_llm(task, strategy, facts, article):
    """可选。把已核过的事实交给大模型润色，失败就保留原编排。"""
    base = (os.environ.get("LLM_BASE_URL") or "").rstrip("/")
    key = os.environ.get("LLM_API_KEY") or ""
    model = os.environ.get("LLM_MODEL") or ""
    if not base or not key or not model:
        return article, "未配置大模型，使用自研编排，正文只引用资料原句。"
    fact_block = "\n".join("- " + fact["text"] + "｜来源：" + fact["title"] for fact in facts)
    user = (
        "只根据下面这些资料原句写" + task["platform"] + "内容，不能新增参数、价格和体验。\n"
        + "人群：" + task["audience"] + "\n场景：" + task["scene"] + "\n切入点：" + strategy["angle"]
        + "\n型号：" + task["product"] + "\n资料：\n" + fact_block
    )
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    request = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
    except (URLError, TimeoutError, OSError, KeyError, json.JSONDecodeError, IndexError):
        return article, "大模型调用失败，已改用自研编排。"
    polished = dict(article)
    polished["body"] = content.strip()
    return polished, "已用大模型按系统提示词润色，并会再次核验。"


def to_markdown(result):
    scene = result.get("scene") or {}
    strategy = result.get("strategy") or {}
    article = result.get("article") or {}
    lines = [
        "一、场景判断",
        "- 目标人群：" + str(scene.get("audience") or ""),
        "- 使用场景：" + str(scene.get("scene") or ""),
        "- 用户问题：" + str(scene.get("problem") or ""),
        "- 内容目标：" + str(strategy.get("goal") or ""),
        "- 平台：" + str(scene.get("platform") or ""),
        "- 购买阶段：" + str(scene.get("stage") or ""),
        "",
        "二、知识库依据",
        "- 产品型号：" + str(result.get("product") or ""),
    ]
    for fact in result.get("facts") or []:
        lines.append("- 事实点：" + fact["text"])
        lines.append("  资料标题：" + fact["title"])
    if not result.get("facts"):
        lines.append("- 事实点：无。未把缺少依据的参数写入正文。")
    lines.extend(["", "三、图文软文"])
    if article.get("title"):
        lines.append("- 标题：" + article["title"])
    if article.get("lead"):
        lines.append("- 导语：" + article["lead"])
    if article.get("body"):
        lines.append("- 正文：")
        lines.append(article["body"])
    if article.get("cta"):
        lines.append("- 行动引导：" + article["cta"])
    for tag in article.get("tags") or []:
        lines.append("- 平台标签：" + tag)
    if article.get("images"):
        for image in article["images"]:
            lines.append("- 图片名称：" + image["name"])
            lines.append("  来源：" + image["source"])
            lines.append("  插入位置：" + image["position"])
            lines.append("  图片说明：" + image["caption"])
    else:
        lines.append("- 图片：没有找到型号一致的 ima 图片，因此不配图。")
    if result.get("blocked_reason"):
        lines.append("- 生成状态：" + result["blocked_reason"])
    lines.extend(["", "四、核验结果"])
    for item in (result.get("verification") or {}).get("facts") or []:
        flag = "有依据" if item["supported"] else "无依据"
        lines.append("- 产品事实（" + flag + "）：" + item["claim"] + "｜" + item["source"])
    for item in (result.get("verification") or {}).get("images") or []:
        lines.append("- 图片型号：" + item)
    for item in (result.get("verification") or {}).get("compliance") or []:
        lines.append("- 合规：" + item["rule"] + " / " + item["hit"] + " / " + item["action"])
    if not (result.get("verification") or {}).get("compliance"):
        lines.append("- 合规：未发现绝对化宣传、虚假承诺、无依据对比、价格误导或竞品贬低。")
    for item in (result.get("verification") or {}).get("pending") or []:
        lines.append("- 待确认：" + item)
    return "\n".join(lines).strip() + "\n"


def run(task, client=None):
    """执行一次任务。client 可替换，便于测试。"""
    task = {
        "product": (task.get("product") or "").strip(),
        "audience": (task.get("audience") or "").strip(),
        "scene": (task.get("scene") or "").strip(),
        "platform": (task.get("platform") or "").strip(),
        "stage": (task.get("stage") or "").strip(),
        "extra": (task.get("extra") or "").strip(),
    }
    questions = check_task(task)
    if questions:
        return {
            "status": "need_more",
            "questions": questions,
            "product": task["product"],
            "markdown": "",
        }
    strategy = build_strategy(task)
    pending = []
    if task["extra"] and PRICE_ASK_RE.search(task["extra"]):
        pending.append("补充说明里提到了价格、补贴、优惠或库存。这些内容只有知识库原文写了才会进入正文。")
    if task["stage"] == "":
        pending.append("购买阶段未说明，不猜测用户处在了解、对比还是决定购买。")
    scene = {
        "audience": task["audience"],
        "scene": task["scene"],
        "problem": strategy["problem"],
        "platform": task["platform"],
        "stage": strategy["stage"],
    }
    ima = client or ImaClient()
    if client is None and not credentials_configured():
        result = {
            "status": "blocked",
            "product": task["product"],
            "scene": scene,
            "strategy": strategy,
            "facts": [],
            "article": {},
            "blocked_reason": "未配置 ima 凭证，已停止生成具体参数、卖点和配图。",
            "verification": {
                "facts": [],
                "images": ["未检索图片"],
                "compliance": [],
                "pending": pending,
            },
            "connection": {"configured": False, "kb_name": "", "kb_found": False},
        }
        result["markdown"] = to_markdown(result)
        return result
    try:
        retrieved = retrieve(ima, task["product"])
    except ImaError as exc:
        result = {
            "status": "blocked",
            "product": task["product"],
            "scene": scene,
            "strategy": strategy,
            "facts": [],
            "article": {},
            "blocked_reason": "知识库检索没有完成：" + str(exc) + "。已停止生成具体参数。",
            "verification": {"facts": [], "images": ["未检索图片"], "compliance": [], "pending": pending},
            "connection": {"configured": True, "kb_name": "", "kb_found": False},
        }
        result["markdown"] = to_markdown(result)
        return result
    facts, conflict_pending = _drop_conflicts(retrieved["facts"])
    pending.extend(conflict_pending)
    if retrieved["skipped_models"]:
        pending.append("发现相近型号资料，未采用：" + "、".join(retrieved["skipped_models"]))
    facts = _rank_facts(facts, strategy["priority"])
    if not facts:
        result = {
            "status": "blocked",
            "product": task["product"],
            "scene": scene,
            "strategy": strategy,
            "facts": [],
            "article": {},
            "blocked_reason": "知识库没有返回可核对的「" + task["product"] + "」事实，已停止生成软文。",
            "verification": {
                "facts": [],
                "images": ["未引用图片"],
                "compliance": [],
                "pending": pending,
            },
            "connection": {"configured": True, "kb_name": retrieved["kb_name"], "kb_found": True},
        }
        result["markdown"] = to_markdown(result)
        return result
    article = compose(task, strategy, facts, retrieved["images"])
    article, polish_note = polish_with_llm(task, strategy, facts, article)
    fact_results, stray_numbers = verify_facts(article, facts)
    if stray_numbers:
        pending.append("润色结果出现了资料里没有的数字 " + "、".join(stray_numbers) + "，已放弃润色，改回资料原句。")
        article = compose(task, strategy, facts, retrieved["images"])
        fact_results, _ignored = verify_facts(article, facts)
        polish_note = "润色引入了资料外数字，已回退到自研编排。"
    hits = compliance_check(article, facts)
    if hits:
        pending.append("润色结果触发合规规则，已回退到资料原句。")
        article = compose(task, strategy, facts, retrieved["images"])
        fact_results, _ignored = verify_facts(article, facts)
        hits = compliance_check(article, facts)
        polish_note = "润色未通过合规检查，已回退到自研编排。"
    image_notes = []
    low, high = strategy["min_images"], strategy["max_images"]
    count = len(article["images"])
    if count < low:
        image_notes.append("平台建议 " + str(low) + "-" + str(high) + " 张，实际只有型号匹配的 " + str(count) + " 张，不补图。")
    else:
        image_notes.append("已引用 " + str(count) + " 张型号匹配的 ima 图片。")
    for image in article["images"]:
        image_notes.append(image["name"] + " 与型号「" + task["product"] + "」一致，建议放在" + image["position"] + "。")
    result = {
        "status": "ok",
        "product": task["product"],
        "scene": scene,
        "strategy": strategy,
        "facts": facts,
        "article": article,
        "blocked_reason": "",
        "polish_note": polish_note,
        "verification": {"facts": fact_results, "images": image_notes, "compliance": hits, "pending": pending},
        "connection": {
            "configured": True,
            "kb_name": retrieved["kb_name"],
            "kb_found": True,
            "browsed_catalog": retrieved["browsed_catalog"],
        },
    }
    result["markdown"] = to_markdown(result)
    return result
