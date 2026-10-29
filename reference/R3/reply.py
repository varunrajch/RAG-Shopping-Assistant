"""
reply.py
Writes the reply. The split of work is the main safety idea of the project:
  - the language model writes ONE connecting sentence and nothing else
  - every price, stock status and product ID is copied by code from the
    catalogue row, and every fact line ends with its citation [P01234] or
    [Policy R2]
  - a final check deletes any rupee amount or ID in the reply that does not
    belong to a cited row or policy section
The first sentence answers what was asked (price, stock, material ...) and is also
written by code from the row. If Ollama runs, it only adds one friendly sentence.
"""
import re

STOCK_LABEL = {"in_stock": "In stock", "low_stock": "Low stock (few left)",
               "out_of_stock": "Out of stock"}
WE_SELL = "footwear, shirts, kurtas, sarees, jeans, bags, kitchen and home decor items"

SITUATION = {
    "single": "one matching product will be shown below",
    "list": "a list of matching products will be shown below",
    "cheapest": "the lowest priced matching product will be shown below",
    "options": "several products match, so we will show options below and ask which one they mean",
    "policy": "the relevant store policy section will be quoted below",
}

PRICE_RE = re.compile(r"(?:₹|\brs\.?|\binr)\s?(\d[\d,]*)|(\d[\d,]*)\s?(?:rupees|rs\b)", re.I)
ID_RE = re.compile(r"\[?\b(P\d{5})\b\]?")
POLICY_CITE_RE = re.compile(r"\[Policy ([A-Z]\d+)\]")


def rupees(amount):
    return f"₹{int(amount):,}"


def product_line(row):
    return (f"**{row.title}**: {rupees(row.price)}, {STOCK_LABEL[row.stock_status]}, "
            f"colour {row.colour}, material {row.material}, size {row.size}, "
            f"rated {row.rating}/5 [{row.product_id}]")


def short_line(row):
    return f"{row.title}: {rupees(row.price)}, {STOCK_LABEL[row.stock_status]} [{row.product_id}]"


def limits_text(filters):
    parts = [filters.get(k) for k in ["colour", "material", "sub_category"] if filters.get(k)]
    if not filters.get("sub_category") and filters.get("category"):
        parts.append(filters["category"])
    if filters.get("size"):
        parts.append(f"size {filters['size']}")
    if filters.get("max_price"):
        parts.append(f"under {rupees(filters['max_price'])}")
    if filters.get("in_stock"):
        parts.append("in stock")
    return " ".join(str(p) for p in parts)


def what_was_asked(query):
    """Which detail the shopper asked about, so the first sentence answers it."""
    q = query.lower()
    for topic, pattern in [("price", r"\b(price|cost|costs|how much|kitna|kitne|rate)\b"),
                           ("stock", r"\b(stock|available|availability)\b"),
                           ("material", r"\b(material|made of|fabric)\b"),
                           ("colour", r"\b(colou?r)\b"),
                           ("rating", r"\b(rating|rated|reviews?)\b")]:
        if re.search(pattern, q):
            return topic
    return "overview"


def stock_sentence(row):
    if row.stock_status == "in_stock":
        return f"It is in stock [{row.product_id}]."
    if row.stock_status == "low_stock":
        return f"It is in stock, but only a few are left [{row.product_id}]."
    return f"It is currently out of stock [{row.product_id}]."


def direct_answer(row, topic):
    """One or two sentences that answer the question, built only from the row."""
    name, pid = f"the {row.title}", row.product_id
    first = {
        "price": f"The {row.title} costs {rupees(row.price)} [{pid}].",
        "stock": stock_sentence(row).replace("It is", f"The {row.title} is", 1),
        "material": f"The {row.title} is made of {row.material.lower()} [{pid}].",
        "colour": f"The {row.title} comes in {row.colour.lower()} [{pid}].",
        "rating": f"The {row.title} is rated {row.rating}/5 by shoppers [{pid}].",
        "overview": (f"The {row.title} is priced at {rupees(row.price)} and rated "
                     f"{row.rating}/5 by shoppers [{pid}]."),
    }[topic]
    if topic == "stock":
        return first + f" It costs {rupees(row.price)} [{pid}]."
    if topic == "price":
        return first + " " + stock_sentence(row)
    return first + ("" if topic == "overview" and row.stock_status == "in_stock"
                    else " " + stock_sentence(row)).replace(name, "it")


def what_they_want(filters):
    """'Cotton Kurtas under ₹2,000' style description of the search."""
    text = limits_text(filters)
    if not (filters.get("category") or filters.get("sub_category")):
        text = f"{text} products".strip()
    return text


def lead_sentence(decision, rows, query, filters):
    """The opening of the reply, written by code so it can contain facts."""
    if decision.mode == "single":
        return direct_answer(rows.iloc[0], what_was_asked(query))
    if decision.mode == "cheapest":
        r = rows.iloc[0]
        return (f"The cheapest of the {decision.total} {what_they_want(filters)} is the "
                f"{r.title} at {rupees(r.price)} [{r.product_id}]. {stock_sentence(r)}")
    if decision.mode == "list":
        shown = f"Here are the top {len(rows)}:" if decision.total > len(rows) else "Here they are:"
        return f"I found {decision.total} {what_they_want(filters)}. {shown}"
    if decision.mode == "options":
        return (f"I found {decision.total} {what_they_want(filters)}, so I don't want to guess "
                f"which one you mean. Here are {len(rows)} across the price range:")
    sec = decision.sections[0]
    return f"Our store policy covers this in section {sec['id']} ({sec['title']}):"


def clarifying_question(decision):
    if decision.refine:
        attr, values = decision.refine
        return (f"Which {attr} do you prefer: {', '.join(values[:-1])} or {values[-1]}? "
                "Or tell me a budget, size or the ID of one of these.")
    return "Which one would you like? You can also tell me a budget or size."


def connecting_sentence(decision, query, llm):
    """One friendly sentence from the language model (only if Ollama runs), else nothing."""
    if llm is None:
        return None
    text = llm.chat(
        "You write ONE short friendly sentence (under 20 words) for a shopping assistant. "
        "Never mention prices, numbers, product names, brands, IDs, stock or any product "
        "details: the system adds those facts itself.",
        f'Shopper said: "{query}"\nSituation: {SITUATION[decision.mode]}.\nWrite the sentence.',
        max_tokens=40)
    if not text or len(text.split()) > 30:
        return None
    return text.strip().strip('"').splitlines()[0]


def build_reply(decision, query, filters, index, llm=None):
    """Returns (reply text, citations, removed) where citations is a list of
    ("product", "P01234") or ("policy", "R1")."""
    rows = index.df.iloc[decision.rows]
    if decision.kind == "refuse":
        body = refusal_text(decision, filters)  # fixed wording, no language model
    else:
        friendly = connecting_sentence(decision, query, llm)
        lead = lead_sentence(decision, rows, query, filters)
        if decision.mode == "policy":
            facts = [f"> {s['text']} [Policy {s['id']}]" for s in decision.sections]
        elif decision.mode == "options":
            facts = [f"{i}. {short_line(r)}" for i, r in enumerate(rows.itertuples(), 1)]
            facts.append("\n" + clarifying_question(decision))
        elif decision.mode == "list":
            facts = [f"- {short_line(r)}" for r in rows.itertuples()]
            if decision.total > len(rows):
                facts.append("\nTell me a colour, size or budget to narrow it down.")
        else:
            facts = [f"Details: {product_line(r)}" for r in rows.itertuples()]
        body = (f"{friendly} " if friendly else "") + lead + "\n\n" + "\n".join(facts)

    citations = [("product", pid) for pid in rows.product_id]
    citations += [("policy", s["id"]) for s in decision.sections]
    allowed_amounts = set(int(p) for p in rows.price)
    for s in decision.sections:
        allowed_amounts |= _amounts(s["text"])
    if filters.get("max_price"):
        allowed_amounts.add(int(filters["max_price"]))  # the shopper's own budget
    text, removed = final_check(body, set(rows.product_id), {s["id"] for s in decision.sections},
                                allowed_amounts)
    return text, citations, removed


def refusal_text(decision, filters):
    cat, sub = decision.nearest or (None, None)
    if decision.mode == "policy_missing":
        return ("I don't have that information in our store policy. I can answer questions "
                "about returns (sections R1 to R5), shipping (S1 to S5) and warranty (W1 to W4).")
    if decision.mode == "no_match":
        wanted = limits_text(filters)
        return (f"I don't have that{f' ({wanted})' if wanted else ''} in our catalogue. "
                f"We do sell {(filters.get('sub_category') or filters.get('category') or sub or WE_SELL)}; "
                "try a different budget, colour, size or material.")
    text = f"I don't have that. We only sell {WE_SELL}."
    if sub:
        text += f" The closest thing we sell is {sub} ({cat})."
    return text


def _amounts(text):
    return {int((a or b).replace(",", "")) for a, b in PRICE_RE.findall(text)}


def final_check(text, allowed_ids, allowed_sections, allowed_amounts):
    """Delete any rupee amount, product ID or policy citation that is not backed
    by a cited row or section. Returns (clean text, list of removed strings)."""
    removed = []

    def price(m):
        value = int((m.group(1) or m.group(2)).replace(",", ""))
        if value in allowed_amounts:
            return m.group(0)
        removed.append(m.group(0))
        return "[price removed]"

    def pid(m):
        if m.group(1) in allowed_ids:
            return m.group(0)
        removed.append(m.group(0))
        return ""

    def section(m):
        if m.group(1) in allowed_sections:
            return m.group(0)
        removed.append(m.group(0))
        return ""

    text = PRICE_RE.sub(price, text)
    text = ID_RE.sub(pid, text)
    text = POLICY_CITE_RE.sub(section, text)
    return text, removed
