# 场景和平台策略。这是自研规则，用来保证换场景、换平台时输出实质变化。

SCENES = {
    "开学季": {
        "people": "大学新生、家长",
        "goal": "判断这台电脑能不能覆盖学习、携带和续航，而不是只比一个性能数字",
        "angle": "上课、背着走、一天续航",
        "priority": ["重量", "续航", "屏幕", "接口", "协同"],
        "avoid": "不要把学生需求收成单一性能指标",
    },
    "职场办公": {
        "people": "商务人士、移动办公者",
        "goal": "说明会议、差旅、文档和安全方面，资料里哪些事实用得上",
        "angle": "开会、出差、文档和数据安全",
        "priority": ["重量", "续航", "接口", "安全", "屏幕", "协同"],
        "avoid": "不要把办公场景写成游戏性能稿",
    },
    "内容创作": {
        "people": "设计、摄影、视频创作者",
        "goal": "只写资料里有的屏幕、性能和素材流转信息",
        "angle": "屏幕、性能和素材怎么在设备间流转",
        "priority": ["屏幕", "色域", "性能", "接口", "存储"],
        "avoid": "不得虚构软件测试结果或跑分",
    },
    "家庭换新": {
        "people": "家庭用户、旧机换新者",
        "goal": "说明好不好上手、一家人能不能用、资料怎么迁过来",
        "angle": "全家使用、数据迁移和长期使用",
        "priority": ["易用", "迁移", "屏幕", "续航", "售后"],
        "avoid": "不要假设所有家人都需要高性能",
    },
    "企业采购": {
        "people": "中小企业、团队采购",
        "goal": "只陈述资料里有的部署、管理和服务信息",
        "angle": "部署、管理和稳定性",
        "priority": ["管理", "安全", "服务", "接口", "稳定"],
        "avoid": "知识库没写的采购政策和折扣不能承诺",
    },
    "门店到访": {
        "people": "附近潜在顾客",
        "goal": "只留一个明确卖点，并给出到店理由",
        "angle": "一个卖点，加上到店就能看到的理由",
        "priority": ["外观", "重量", "屏幕", "续航"],
        "avoid": "避免信息堆叠",
    },
    "新品首发": {
        "people": "关注新品的用户",
        "goal": "只写资料里能核对的变化、适合人群和购买建议",
        "angle": "这代资料里写明的变化",
        "priority": ["新品", "变化", "屏幕", "重量", "续航"],
        "avoid": "价格和权益必须有资料依据",
    },
    "节日营销": {
        "people": "送礼、家庭购机",
        "goal": "给出使用场景和选择建议",
        "angle": "送给谁、到家后怎么用",
        "priority": ["易用", "屏幕", "重量", "外观"],
        "avoid": "不得虚构优惠、补贴或库存",
    },
}

PLATFORMS = {
    "公众号": {
        "title_rule": "完整标题，先写场景问题，再出现型号",
        "length": "导语加若干短节，每节对应一条资料事实",
        "structure": "标题、导语、分段正文、结尾行动引导",
        "tone": "说明文，句子完整，不喊口号",
        "image_rule": "2-4 张，写明来源和插入位置",
        "cta": "引导读者到店核对当前配置，不写未经证实的价格",
        "tags": False,
        "min_images": 2,
        "max_images": 4,
        "max_facts": 6,
    },
    "小红书": {
        "title_rule": "口语化标题，点出人群和场景，不写亲测",
        "length": "短段落，一行一个意思",
        "structure": "标题、场景短句、可核对事实、话题标签",
        "tone": "像笔记，不像广告通稿，也不假装个人体验",
        "image_rule": "3-6 张",
        "cta": "用资料整理的口吻收束，引导看实机，不伪造使用体验",
        "tags": True,
        "min_images": 3,
        "max_images": 6,
        "max_facts": 5,
    },
    "门店朋友圈": {
        "title_rule": "可以没有长标题",
        "length": "短文案",
        "structure": "一个核心卖点，加一句咨询或到店引导",
        "tone": "像导购跟附近顾客说话，只留一件事",
        "image_rule": "1-3 张，优先主图和场景图",
        "cta": "邀请到店看实机或咨询，不堆参数",
        "tags": False,
        "min_images": 1,
        "max_images": 3,
        "max_facts": 1,
    },
    "门店海报": {
        "title_rule": "主标题短，副标题带型号和人群",
        "length": "卖点不超过 3 条",
        "structure": "主标题、副标题、卖点、活动说明",
        "tone": "海报语句短，不写长段",
        "image_rule": "1 张主视觉，型号必须一致",
        "cta": "活动说明只能源自资料；没有优惠信息就明确不写优惠",
        "tags": False,
        "min_images": 1,
        "max_images": 1,
        "max_facts": 3,
    },
}

VAGUE_PRODUCTS = {
    "轻薄本",
    "笔记本",
    "笔记本电脑",
    "电脑",
    "华为电脑",
    "华为笔记本",
    "华为pc",
    "pc",
    "本子",
    "新电脑",
    "想买轻薄本",
}


def build_strategy(task):
    """根据人群、场景、平台生成可解释的内容策略。"""
    scene_name = task["scene"]
    platform_name = task["platform"]
    scene = SCENES.get(scene_name)
    platform = PLATFORMS[platform_name]
    if scene is None:
        scene = {
            "people": task["audience"],
            "goal": "按用户写下的场景组织内容，事实仍然只来自知识库",
            "angle": "用户指定的场景：" + scene_name,
            "priority": ["屏幕", "重量", "续航", "接口"],
            "avoid": "不要把资料里没有的需求写成卖点",
        }
    stage = task.get("stage") or "未说明"
    return {
        "audience": task["audience"],
        "scene": scene_name,
        "stage": stage,
        "problem": scene["goal"],
        "goal": scene["goal"],
        "angle": scene["angle"],
        "priority": scene["priority"],
        "avoid": scene["avoid"],
        "platform": platform_name,
        "title_rule": platform["title_rule"],
        "length": platform["length"],
        "structure": platform["structure"],
        "tone": platform["tone"],
        "image_rule": platform["image_rule"],
        "cta_rule": platform["cta"],
        "use_tags": platform["tags"],
        "min_images": platform["min_images"],
        "max_images": platform["max_images"],
        "max_facts": platform["max_facts"],
    }
