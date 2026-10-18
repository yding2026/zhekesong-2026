const result = document.querySelector("#result");
const status = document.querySelector("#status");

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function addList(parent, items) {
  const list = el("ul", "kv");
  items.forEach((item) => list.append(el("li", "", item)));
  parent.append(list);
}

function render(data) {
  result.replaceChildren();
  if (data.status === "need_more") {
    result.append(el("h2", "", "还不能生成"));
    const box = el("div", "ask");
    addList(box, data.questions || []);
    result.append(box);
    return;
  }

  const scene = data.scene || {};
  const strategy = data.strategy || {};
  result.append(el("h2", "", "一、场景判断"));
  addList(result, [
    "目标人群：" + (scene.audience || ""),
    "使用场景：" + (scene.scene || ""),
    "用户问题：" + (scene.problem || ""),
    "内容目标：" + (strategy.goal || ""),
    "平台：" + (scene.platform || ""),
    "购买阶段：" + (scene.stage || ""),
  ]);

  result.append(el("h2", "", "平台策略"));
  addList(result, [
    "切入点：" + (strategy.angle || ""),
    "结构：" + (strategy.structure || ""),
    "语气：" + (strategy.tone || ""),
    "篇幅：" + (strategy.length || ""),
    "配图：" + (strategy.image_rule || ""),
    "行动引导：" + (strategy.cta_rule || ""),
    "不要这样做：" + (strategy.avoid || ""),
  ]);

  result.append(el("h2", "", "二、知识库依据"));
  if ((data.facts || []).length === 0) {
    result.append(el("p", "stop", data.blocked_reason || "没有可引用的资料。"));
  } else {
    addList(result, data.facts.map((fact) => fact.text + "（资料：" + fact.title + "）"));
  }

  const article = data.article || {};
  if (article.body) {
    result.append(el("h2", "", "三、图文软文"));
    if (article.title) result.append(el("p", "", "标题：" + article.title));
    if (article.lead) result.append(el("p", "", "导语：" + article.lead));
    result.append(el("div", "body", article.body));
    if (article.cta) result.append(el("p", "", "行动引导：" + article.cta));
    (article.tags || []).forEach((tag) => result.append(el("p", "", "平台标签：" + tag)));
    (article.images || []).forEach((image) => {
      result.append(el("p", "", "图片：" + image.name + "｜" + image.source + "｜放在" + image.position));
    });
  }

  const check = data.verification || {};
  result.append(el("h2", "", "四、核验结果"));
  const notes = [];
  (check.facts || []).forEach((item) => {
    notes.push((item.supported ? "有依据：" : "无依据：") + item.claim);
  });
  (check.images || []).forEach((item) => notes.push(item));
  if ((check.compliance || []).length === 0) {
    notes.push("未发现绝对化宣传、虚假承诺、无依据对比、价格误导或竞品贬低。");
  } else {
    check.compliance.forEach((item) => notes.push(item.rule + "：" + item.hit + "，" + item.action));
  }
  (check.pending || []).forEach((item) => notes.push("待确认：" + item));
  if (data.polish_note) notes.push(data.polish_note);
  addList(result, notes);

  if (data.markdown) {
    const bar = el("div", "toolbar");
    const copy = el("button", "ghost", "复制全文");
    copy.type = "button";
    copy.addEventListener("click", () => navigator.clipboard.writeText(data.markdown));
    const download = el("button", "ghost", "下载 Markdown");
    download.type = "button";
    download.addEventListener("click", () => {
      const blob = new Blob([data.markdown], { type: "text/markdown;charset=utf-8" });
      const link = el("a");
      link.href = URL.createObjectURL(blob);
      link.download = "软文结果.md";
      link.click();
      URL.revokeObjectURL(link.href);
    });
    bar.append(copy, download);
    result.append(bar);
  }
}

document.querySelector("#task").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = Object.fromEntries(form.entries());
  result.replaceChildren(el("h2", "", "正在处理"));
  const response = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  render(await response.json());
});

document.querySelector("#sample").addEventListener("click", () => {
  document.querySelector("#audience").value = "准备开学的大学新生";
  document.querySelector("#scene").value = "开学季";
  document.querySelector("#platform").value = "小红书";
  document.querySelector("#stage").value = "对比";
  document.querySelector("#product").focus();
});

fetch("/api/status")
  .then((response) => response.json())
  .then((data) => {
    status.textContent = data.configured
      ? "ima 凭证已配置，将检索「" + data.kb_query + "」"
      : "ima 凭证未配置。可以先看追问和平台策略，配好凭证后才会检索知识库。";
  })
  .catch(() => {
    status.textContent = "状态接口没有响应";
  });
