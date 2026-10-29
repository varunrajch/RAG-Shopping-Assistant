"""
app.py
Streamlit chat for the shopping assistant.
  Chat tab     chat window; citations show as small tags, click one to see the
               product row or policy text it points to
  Side panel   for each reply: decision, filters, session memory, latency, tokens
  Results tab  the evaluation summary from eval.py

Run:  streamlit run app.py
"""
import json
import re
import time

import pandas as pd
import streamlit as st

import config
from assistant import ShoppingAssistant
from memory import SessionMemory
from reply import STOCK_LABEL, limits_text

st.set_page_config(page_title="Honest Shopping Assistant", page_icon="🛍️", layout="wide")

# Preloaded questions for the demo, one per behaviour we want to show.
EXAMPLES = [
    "Price of the blue running shoe?",
    "blu running shoe sasta wala",
    "cotton kurta 1500 se kam hai kya",
    "Do you sell iPhones?",
    "How much is the Stridex AeroGlide?",
    "What is the warranty on pressure cookers?",
    "Do you offer EMI?",
    "I want a kurta under ₹2,000",
    "show me cotton ones",
    "which is the cheapest in maroon?",
]
DECISION_BADGE = {"answer": "🟢 answer", "clarify": "🟡 clarify", "refuse": "🔴 refuse"}


@st.cache_resource(show_spinner="Loading the catalogue and the embedding model...")
def get_bot():
    return ShoppingAssistant()


bot = get_bot()
ss = st.session_state
if "messages" not in ss:
    ss.messages = []          # chat history: {"role", "content", "result"}
    ss.memory = SessionMemory()

# ---------------------------------------------------------------- sidebar: demo buttons
with st.sidebar:
    st.subheader("Demo questions")
    for q in EXAMPLES:
        if st.button(q, width="stretch"):
            ss.pending = q
    if st.button("🔄 Reset conversation", width="stretch", type="primary"):
        ss.messages, ss.memory = [], SessionMemory()
        ss.pop("pending", None)
        ss.pop("pick", None)
    llm_on = bot.llm.available()
    st.caption(f"Language model: **{config.LLM_MODEL}** "
               + ("(running)" if llm_on else "(not running, template replies)"))


def as_tags(text):
    """[P01234] -> `P01234` so citations look like small tags."""
    return re.sub(r"\[(P\d{5}|Policy [A-Z]\d+)\]", r" `\1`", text)


def show_citations(result, msg_no):
    """One small clickable tag per citation; the popover shows the source."""
    cites = list(dict.fromkeys(result["citations"]))
    if not cites:
        return
    cols = st.columns(min(len(cites), 6))
    for i, (kind, cid) in enumerate(cites):
        label = cid if kind == "product" else f"Policy {cid}"
        with cols[i % len(cols)].popover(label, key=f"cite-{msg_no}-{i}"):
            if kind == "product":
                row = bot.index.df[bot.index.df.product_id == cid].iloc[0]
                st.markdown(f"**Catalogue row {cid}**")
                st.dataframe(row.astype(str).rename("value"), width="stretch")
            else:
                sec = next(s for s in bot.index.policy if s["id"] == cid)
                st.markdown(f"**Policy {sec['id']}. {sec['title']}**\n\n{sec['text']}")


def show_evidence(result):
    """Right hand panel: one small card per cited product row or policy section."""
    cites = list(dict.fromkeys(result["citations"]))
    if not cites:
        st.caption("No sources: this reply states no catalogue or policy facts.")
        return
    df = bot.index.df
    for kind, cid in cites:
        with st.container(border=True):
            if kind == "product":
                row = df[df.product_id == cid].iloc[0]
                st.markdown(f"`{cid}` **{row.title}**")
                st.caption(f"₹{int(row.price):,} · {STOCK_LABEL[row.stock_status]} · "
                           f"{row.colour} · {row.material} · size {row['size']} · "
                           f"rated {row.rating}/5 · {row.category} › {row.sub_category}")
            else:
                sec = next(s for s in bot.index.policy if s["id"] == cid)
                st.markdown(f"`Policy {cid}` **{sec['title']}**")
                st.caption(sec["text"])


REASONS = {
    "single": "One clear match, so I answer with it.",
    "list": "You asked to see options, so I list the best matches.",
    "cheapest": "You asked for the cheapest, so I pick the lowest price among the matches.",
    "options": "Several close matches that differ in {differ}, so I ask instead of guessing.",
    "policy": "Policy section {section} covers this, so I quote it.",
    "not_sold": "Nothing in the catalogue matches {words}, so I say I don't have it.",
    "no_match": "No product meets every filter, so I say I don't have it.",
    "policy_missing": "No policy section covers this, so I say I don't have that information.",
}


def pipeline_steps(r):
    """The real steps the pipeline took for one reply, as (title, detail) pairs."""
    p, f = r["parsed"], r["filters"]
    remembered = {k: v for k, v in f.items() if k not in p and k != "in_stock"}
    detail = f'Read as "{p["text"]}". '
    if p.get("is_policy"):
        detail += "This is a store policy question."
    else:
        detail += f"Looking for: {limits_text(f)}." if limits_text(f) else "No filters found."
        if remembered:
            detail += f" Remembered from earlier: {limits_text(remembered)}."
    steps = [("🔎 Understanding the question", detail)]
    if p.get("is_policy"):
        found = ", ".join(c for _, c in r["citations"])
        steps.append((f"📚 Searching {len(bot.index.policy)} policy sections (BM25 + MiniLM)",
                      f"Best section: {found}." if found else "No section is close enough."))
    elif r["mode"] == "not_sold":
        steps.append((f"🛍️ Searching {len(bot.index.df):,} products (BM25 keywords + MiniLM meaning)",
                      "These words appear in no product: "
                      + ", ".join(f'"{w}"' for w in p.get("unknown_words", [])) + "."))
    else:
        steps.append((f"🛍️ Searching {len(bot.index.df):,} products (BM25 keywords + MiniLM meaning)",
                      f"{r['matches']} products pass every filter."))
    reason = REASONS[r["mode"]].format(
        differ=", ".join(r.get("differ_on", [])) or "price",
        section=", ".join(c for _, c in r["citations"]),
        words=", ".join(f'"{w}"' for w in p.get("unknown_words", [])) or "these words")
    steps.append((f"⚖️ Deciding: {r['decision']}", reason))
    if r["decision"] == "refuse":
        checked = "No product or policy facts stated, so nothing can be wrong."
    elif r["removed_by_check"]:
        checked = "Removed unsupported text: " + ", ".join(r["removed_by_check"])
    else:
        checked = "Every price, stock status and ID comes from a cited source."
    steps.append(("✅ Checking facts against the sources", checked))
    return steps


def summary_label(r):
    if r["mode"] in ("policy", "policy_missing"):
        found = "Policy " + r["citations"][0][1] if r["citations"] else "no section"
        return f"Searched policy in {r['latency_ms']} ms · {found} · {DECISION_BADGE[r['decision']]}"
    return (f"Searched {len(bot.index.df):,} products in {r['latency_ms']} ms · "
            f"{r['matches']} matches · {DECISION_BADGE[r['decision']]}")


def show_steps(r, live):
    """A status box with the pipeline steps. For a new reply the steps appear one by
    one; this pause is only for display, the real latency is shown under the reply."""
    summary = summary_label(r)
    if not live:
        with st.status(summary, state="complete", expanded=False):
            for title, detail in pipeline_steps(r):
                st.markdown(f"**{title}**  \n{detail}")
        return
    with st.status("Searching the catalogue...", expanded=True) as box:
        for title, detail in pipeline_steps(r):
            time.sleep(config.DEMO_STEP_DELAY_S)
            st.markdown(f"**{title}**  \n{detail}")
        time.sleep(config.DEMO_STEP_DELAY_S)
        box.update(label=summary, state="complete", expanded=False)


def stream_words(text):
    """Show the reply a few words at a time, like a chat assistant typing."""
    for word in re.split(r"(\s+)", text):
        yield word
        if word.strip():
            time.sleep(config.DEMO_WORD_DELAY_S)


# ---------------------------------------------------------------- tabs
tab_chat, tab_results = st.tabs(["💬 Chat", "📊 Results"])

with tab_chat:
    st.title("The Shopping Assistant That Doesn't Lie")
    st.caption("Answers only from the catalogue and the store policy. Every fact carries a "
               "citation, and prices are copied from the catalogue by code, never generated.")
    chat_col, evidence_col = st.columns([3, 1], gap="medium")
    with chat_col:
        history = st.container()
        typed = st.chat_input("Ask about products, returns, shipping or warranty")
    query = typed or ss.pop("pending", None)
    new_reply = None
    if query:
        result = bot.ask(query, ss.memory)
        ss.messages.append({"role": "user", "content": query})
        ss.messages.append({"role": "assistant", "content": result["reply"], "result": result})
        ss.pick = len(ss.messages) // 2 - 1  # show the newest reply's evidence
        new_reply = len(ss.messages) - 1      # this one is played step by step

    with history:
        for n, m in enumerate(ss.messages):
            with st.chat_message(m["role"]):
                if m["role"] == "user":
                    st.markdown(m["content"])
                    continue
                r = m["result"]
                show_steps(r, live=(n == new_reply))
                if n == new_reply:
                    st.write_stream(stream_words(as_tags(m["content"])))
                else:
                    st.markdown(as_tags(m["content"]))
                show_citations(r, n)
                st.caption(f"{DECISION_BADGE[r['decision']]} · {r['latency_ms']} ms · "
                           f"LLM {'used' if r['llm_called'] else 'not used'}")

    replies = [m["result"] for m in ss.messages if m["role"] == "assistant"]
    with evidence_col:
        st.subheader("📎 Evidence")
        if not replies:
            st.caption("The catalogue rows and policy sections behind each reply appear here.")
        else:
            # the same choice also drives "Reply details" in the side panel
            st.selectbox("Reply", range(len(replies)), key="pick",
                         format_func=lambda i: f"#{i + 1}: {replies[i]['query'][:30]}")
            show_evidence(replies[ss.pick])

# ---------------------------------------------------------------- sidebar: reply details
with st.sidebar:
    st.divider()
    st.subheader("Reply details")
    if not replies:
        st.caption("Ask something to see how the assistant decided.")
    else:
        r = replies[ss.pick]
        st.caption(f"Reply #{ss.pick + 1}: {r['query']}")
        st.markdown(f"**Decision:** {DECISION_BADGE[r['decision']]} ({r['mode']})")
        st.markdown(f"**Matching products:** {r['matches']}")
        st.markdown("**Filters applied**")
        st.json(r["filters"] or {}, expanded=True)
        st.markdown("**Session memory**")
        st.json(r["memory"] or {}, expanded=False)
        c1, c2, c3 = st.columns(3)
        c1.metric("Latency", f"{r['latency_ms']:.0f} ms")
        c2.metric("Tokens in", r["tokens_in"])
        c3.metric("Tokens out", r["tokens_out"])
        st.caption(f"LLM called: {'yes' if r['llm_called'] else 'no'}")
        if r["removed_by_check"]:
            st.warning(f"Final check removed: {', '.join(r['removed_by_check'])}")

# ---------------------------------------------------------------- results tab
with tab_results:
    st.header("Evaluation on the 60 test questions")
    summary_path = config.RESULTS_DIR / "summary.json"
    if not summary_path.exists():
        st.info("No results yet. Run `python eval.py` in a terminal, then refresh.")
    else:
        s = json.loads(summary_path.read_text())
        st.caption(f"Language model during evaluation: {s['llm_model']}")
        cols = st.columns(4)
        cols[0].metric("Groundedness", f"{s['groundedness']:.0%}")
        cols[1].metric("Invented prices", s["invented_prices"])
        cols[2].metric("Refusal accuracy", f"{s['refusal_accuracy']:.0%}")
        cols[3].metric("Clarification accuracy", f"{s['clarification_accuracy']:.0%}")
        cols = st.columns(4)
        cols[0].metric("Answer hit rate", f"{s['answer_hit_rate']:.0%}")
        cols[1].metric("Median latency", f"{s['latency_median_ms']:.0f} ms")
        cols[2].metric("p95 latency", f"{s['latency_p95_ms']:.0f} ms")
        cols[3].metric("Avg tokens (in / out)", f"{s['avg_tokens_in']:.0f} / {s['avg_tokens_out']:.0f}")
        st.subheader("Decision accuracy by question type")
        st.dataframe(pd.Series(s["by_type"], name="accuracy").to_frame(), width="content")
        st.subheader("Every question")
        df = pd.read_csv(config.RESULTS_DIR / "eval_results.csv")
        st.dataframe(df[["id", "type", "query", "expected", "decision", "hit", "grounded",
                         "invented_prices", "latency_ms", "tokens_in", "tokens_out", "cited"]],
                     width="stretch", hide_index=True)
