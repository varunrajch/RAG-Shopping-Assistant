"use strict";

// One example per behaviour, for the demo. The last three form a multi-turn conversation.
const EXAMPLES = [
  "Chargit QuillBolt red earphones kitne ke",
  "green running shoes kitne ke hai",
  "yatrik vega dash brown duffel me shoe compartment hai?",
  "Trailnest DriftAir pink running shoe water resistant hai?",
  "redmi note 13 price",
  "earbuds ki seal khol di, return ho jayega?",
  "credit card pe EMI milega?",
  "6 mm yoga mat chahiye",
  "TPE wali 600 ke andar",
  "inme sabse sasti kitne ki hai?",
];
const CITATION_RE = /\[(SKU-[A-Z0-9]{8})\]/g;
const STOCK_TEXT = { in_stock: "In stock", low_stock: "Low stock", out_of_stock: "Out of stock" };

const $ = (sel) => document.querySelector(sel);
const messages = $("#messages");
let conversationId = newConversationId();

function newConversationId() {
  return "web-" + Math.random().toString(36).slice(2, 12);
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of children) {
    if (c === null || c === undefined) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

function rupees(n) {
  return "₹" + Number(n).toLocaleString("en-IN");
}

function attrText(v) {
  if (Array.isArray(v)) return v.join(", ");
  if (v === true) return "yes";
  if (v === false) return "no";
  return String(v);
}

// ------------------------------------------------------------------------------------------ source cards
function productCard(p) {
  const price = el("span", { class: "src-price" }, rupees(p.price_inr),
    p.mrp_inr > p.price_inr ? el("s", {}, rupees(p.mrp_inr)) : null);
  const attrs = Object.entries(p.attributes);
  const card = el("div", { class: "src", "data-source": p.product_id },
    el("div", { class: "src-head" }, el("span", { class: "src-title" }, p.title), price),
    el("div", { class: "src-meta" },
      el("button", { class: "chip", type: "button", onclick: () => focusSource(p.product_id) }, p.product_id),
      el("span", { class: "stock " + p.stock_status }, STOCK_TEXT[p.stock_status]),
      el("span", {}, p.rating === null ? "no reviews" : `★ ${p.rating} (${p.review_count})`),
      ...attrs.map(([k, v]) => el("span", {}, `${k.replaceAll("_", " ")}: ${attrText(v)}`))),
  );
  card.append(el("p", { class: "src-text" }, p.description),
    el("div", { class: "src-meta" }, `${p.category} › ${p.sub_category} · brand ${p.brand}`));
  return card;
}

function policyCard(s) {
  return el("div", { class: "src policy", "data-source": "policy-" + s.section_id },
    el("div", { class: "src-head" }, el("span", { class: "src-title" }, `Store policy §${s.section_id}: ${s.title}`)),
    el("p", { class: "src-text" }, s.text));
}

function showSourcesPanel(sources) {
  const panel = $("#panel-source");
  const cards = [...sources.policies.map(policyCard), ...sources.products.map(productCard)];
  panel.replaceChildren(
    el("p", { class: "muted" }, cards.length
      ? "Exact catalogue rows and policy text behind the latest answer:"
      : "This answer cites no product or policy (nothing in the catalogue matched)."),
    ...cards,
  );
}

function focusSource(id) {
  selectTab("source");
  const card = document.querySelector(`#panel-source [data-source="${CSS.escape(id)}"]`);
  if (card) {
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.remove("flash");
    void card.offsetWidth; // restart the highlight animation
    card.classList.add("flash");
  }
}

// ------------------------------------------------------------------------------------------ chat
function addUserMessage(text) {
  messages.append(el("div", { class: "msg user" }, el("div", { class: "bubble" }, text)));
  scrollDown();
}

// Text is rendered with textContent only; product IDs become chips that jump to their source in the panel.
function renderLine(line) {
  const p = el("p");
  let last = 0;
  for (const m of line.matchAll(CITATION_RE)) {
    p.append(document.createTextNode(line.slice(last, m.index)));
    p.append(el("button", { class: "chip", type: "button", onclick: () => focusSource(m[1]) }, m[1]));
    last = m.index + m[0].length;
  }
  p.append(document.createTextNode(line.slice(last)));
  return p;
}

function addBotMessage(result) {
  const reply = result.reply;
  const bubble = el("div", { class: "bubble" });
  reply.answer_text.split("\n").filter((l) => l.trim()).forEach((l) => bubble.append(renderLine(l)));
  const meta = el("div", { class: "meta" }, el("span", { class: "badge " + reply.action }, reply.action));
  if (result.llm_used) meta.append(el("span", { class: "pill llm" }, "LLM fallback"));
  messages.append(el("div", { class: "msg bot" }, bubble, meta));
  scrollDown();
  showSourcesPanel(result.sources);
  showReasoning(result);
}

function addError(text) {
  messages.append(el("div", { class: "msg bot" }, el("div", { class: "bubble" }, el("p", {}, text))));
  scrollDown();
}

function scrollDown() {
  messages.scrollTop = messages.scrollHeight;
}

async function send(text) {
  const input = $("#input");
  const button = $("#send");
  addUserMessage(text);
  setExamplesOpen(false);
  input.value = "";
  button.disabled = true;
  const typing = el("div", { class: "msg bot typing" }, "Checking the catalogue…");
  messages.append(typing);
  scrollDown();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message: text }),
    });
    const data = await res.json();
    typing.remove();
    if (!res.ok) {
      addError(typeof data.detail === "string" ? data.detail : "Please type a shorter question (max 300 characters).");
      return;
    }
    addBotMessage(data);
    refreshMetrics();
  } catch (err) {
    typing.remove();
    addError("The assistant is not reachable right now. Please try again.");
  } finally {
    button.disabled = false;
    input.focus();
  }
}

// ------------------------------------------------------------------------------------------ inspector
function selectTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("active", p.id === "panel-" + name));
}

function kv(pairs) {
  const dl = el("dl", { class: "kv" });
  for (const [k, v] of pairs) {
    if (v === undefined || v === null || v === "") continue;
    dl.append(el("dt", {}, k), el("dd", {}, typeof v === "object" ? JSON.stringify(v) : String(v)));
  }
  return dl;
}

function showReasoning(result) {
  const r = result.reply;
  const d = result.debug || {};
  const panel = $("#panel-reasoning");
  panel.replaceChildren(
    el("h3", {}, `Decision: ${r.action} (${r.kind})`),
    kv([["Products matched", d.matched], ["Cited products", r.cited_product_ids.join(", ") || "none"],
        ["Cited policy", r.cited_policy_sections.join(", ") || "none"],
        ["LLM fallback rewrite", d.llm_rewrite], ["Removed by guard", (result.removed_by_guard || []).join("; ")]]),
    el("h4", {}, "How the message was understood"),
    kv(Object.entries(d.parsed || {})),
    el("h4", {}, "Facts stated (copied from the catalogue)"),
    kv(r.stated_prices.map((s) => [s.product_id, "price " + rupees(s.price_inr)])
      .concat(r.stated_facts.map((f) => [f.product_id, `${f.field}: ${JSON.stringify(f.value)}`]))),
  );
}

async function refreshMetrics() {
  const res = await fetch("/api/metrics");
  if (!res.ok) return;
  const m = await res.json();
  const s = m.session;
  $("#llm-status").textContent = m.llm_model
    ? `LLM fallback: ${m.llm_model}`
    : "LLM: off (rules only, offline)";
  const stat = (v, l) => el("div", { class: "stat" }, el("div", { class: "v" }, v), el("div", { class: "l" }, l));
  const children = [
    el("h3", {}, "This session"),
    el("div", { class: "stat-row" },
      stat(s.turns, "turns"), stat(`${s.latency_ms_mean} ms`, "mean latency"),
      stat(`${s.latency_ms_p95} ms`, "p95 latency"), stat(`${s.tokens_in_total}/${s.tokens_out_total}`, "tokens in/out"),
      stat(`$${s.cost_usd_total}`, "LLM cost"), stat(`${s.actions.answer}/${s.actions.clarify}/${s.actions.refuse}`,
        "answer/clarify/refuse")),
  ];
  if (m.dev_score) {
    const c = m.dev_score.components || {};
    children.push(
      el("h4", {}, `Official evaluate.py on ${m.dev_score.n_truth_questions} dev questions`),
      el("div", { class: "stat-row" },
        stat(m.dev_score.primary_score.toFixed(3), "primary score (baseline 0.73)"),
        stat(c.hallucinated_prices_total ?? 0, "hallucinated prices"),
        stat((c.action_accuracy ?? 0).toFixed(3), "action accuracy"),
        stat((c.grounded_rate_when_action_correct ?? 0).toFixed(3), "grounded rate")),
      el("h4", {}, "Score by question type"),
      kv(Object.entries(m.dev_score.score_by_question_type || {}).map(([k, v]) => [k, v.toFixed(3)])),
    );
  }
  children.push(el("p", { class: "note" },
    "Decisions, prices and stock come from code over the catalogue, so a query costs ~1 ms and no tokens. " +
    "The LLM is called only when the rules cannot understand a message, and it only rewrites the message; " +
    "the rules still decide and every fact still comes from the catalogue."));
  $("#panel-metrics").replaceChildren(...children);
}

// ------------------------------------------------------------------------------------------ wiring
document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
  selectTab(t.dataset.tab);
  if (t.dataset.tab === "metrics") refreshMetrics();
}));
$("#composer").addEventListener("submit", (e) => {
  e.preventDefault();
  const text = $("#input").value.trim();
  if (text) send(text);
});
$("#new-chat").addEventListener("click", async () => {
  await fetch("/api/reset", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ conversation_id: conversationId }),
  });
  conversationId = newConversationId();
  messages.querySelectorAll(".msg:not(.intro)").forEach((m) => m.remove());
  setExamplesOpen(true);
  $("#panel-source").replaceChildren(el("p", { class: "muted" }, "Sources for the next answer will appear here."));
});
// Example questions: shown in full before the first message, then collapsed to a single link.
const examples = $("#examples");
const examplesToggle = el("button", { type: "button", class: "examples-toggle", "aria-expanded": "true",
  onclick: () => setExamplesOpen(examples.classList.contains("collapsed")) });
EXAMPLES.forEach((q) => examples.append(el("button", { type: "button", onclick: () => send(q) }, q)));
examples.before(examplesToggle);

function setExamplesOpen(open) {
  examples.classList.toggle("collapsed", !open);
  examplesToggle.setAttribute("aria-expanded", String(open));
  examplesToggle.textContent = open ? "Hide example questions" : "Show example questions";
  examplesToggle.hidden = open && !messages.querySelector(".msg.user");
}
setExamplesOpen(true);
refreshMetrics();
