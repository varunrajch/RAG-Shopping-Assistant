"""
parse.py
Turns a user message into structured filters, rules first:
  "blu running shoe sasta wala"  ->  sub_category=Running Shoes, colour=Blue, cheapest=True
  "cotton kurta 1500 se kam"     ->  category=Kurtas, material=Cotton, max_price=1500

Steps
  1. Normalise: lower case, fix Hinglish words and misspellings (dictionary,
     then a fuzzy match against catalogue words), "2,000" -> "2000", "2k" -> "2000".
  2. Spot policy questions (return, refund, shipping, warranty ...).
  3. Pull out price, size, stock, "cheapest", "show me a list", category,
     colour and material with regular expressions and keyword tables.
  4. Whatever words are left over are sorted into product names we know
     ("aeroglide", "stridex") and unknown words ("iphone", "laptop").
  5. Only if no category was found and unknown words remain, ask the language
     model to fill the gap, and accept only values from our allowed lists.
"""
import difflib
import re
from dataclasses import asdict, dataclass, field

from index import STOPWORDS, singular

# ---------------------------------------------------------------- dictionaries
# Hinglish words and common misspellings -> standard English word
WORD_FIX = {
    # cheap
    "sasta": "cheap", "sasti": "cheap", "saste": "cheap", "sastaa": "cheap", "cheep": "cheap",
    "chep": "cheap", "cheapst": "cheapest", "sabse": "",
    # colours
    "kala": "black", "kaala": "black", "kali": "black", "kaali": "black", "kale": "black",
    "blak": "black", "blck": "black", "neela": "blue", "neeli": "blue", "neele": "blue",
    "nila": "blue", "nili": "blue", "blu": "blue", "bleu": "blue", "lal": "red", "laal": "red",
    "hara": "green", "hari": "green", "hare": "green", "safed": "white", "safaid": "white",
    "sufed": "white", "whte": "white", "wite": "white", "peela": "yellow", "peeli": "yellow",
    "pila": "yellow", "gulabi": "pink", "bhura": "brown", "gray": "grey", "narangi": "orange",
    "baingani": "purple", "chandi": "silver",
    # materials
    "sooti": "cotton", "suti": "cotton", "cotten": "cotton", "coton": "cotton",
    "resham": "silk", "reshmi": "silk", "chamda": "leather", "chamde": "leather",
    "lether": "leather", "leathr": "leather", "lethar": "leather", "lakdi": "wood",
    "wooden": "wood", "aluminum": "aluminium",
    # products
    "joota": "shoe", "joote": "shoe", "jootey": "shoe", "juta": "shoe", "jutta": "shoe",
    "runing": "running", "runnig": "running", "snekers": "sneakers",
    "sneakrs": "sneakers", "sneekers": "sneakers", "snikers": "sneakers", "kurtha": "kurta",
    "kurtta": "kurta", "sare": "saree", "sarre": "saree", "sari": "saree", "saari": "saree",
    "sadi": "saree", "jens": "jeans", "jeens": "jeans", "bagpack": "backpack",
    "presure": "pressure", "pressur": "pressure", "preshar": "pressure", "kadai": "kadhai",
    "karahi": "kadhai", "thaila": "bag", "jhola": "bag", "ghadi": "clock", "tshirt": "t shirt",
    "tee": "t shirt", "tees": "t shirt", "shrt": "shirt",
    # policy words
    "wapas": "return", "wapis": "return", "vapas": "return", "din": "days",
}

# phrase -> sub-category (written in singular, as the text is singularised)
SUB_KEYWORDS = {
    "running shoe": "Running Shoes", "jogging shoe": "Running Shoes", "sports shoe": "Running Shoes",
    "sneaker": "Sneakers", "sandal": "Sandals", "formal shoe": "Formal Shoes",
    "office shoe": "Formal Shoes", "slipper": "Slippers", "chappal": "Slippers",
    "flip flop": "Slippers",
    "casual shirt": "Casual Shirt", "formal shirt": "Formal Shirt", "t shirt": "T-Shirt",
    "polo shirt": "Polo Shirt", "polo": "Polo Shirt",
    "straight kurta": "Straight Kurta", "anarkali kurta": "Anarkali Kurta", "anarkali": "Anarkali Kurta",
    "short kurti": "Short Kurti", "kurti": "Short Kurti", "pathani kurta": "Pathani Kurta",
    "pathani": "Pathani Kurta",
    "printed saree": "Printed Saree", "embroidered saree": "Embroidered Saree",
    "banarasi saree": "Banarasi Saree", "banarasi": "Banarasi Saree",
    "party wear saree": "Party Wear Saree", "party saree": "Party Wear Saree",
    "slim fit jean": "Slim Fit Jeans", "slim fit": "Slim Fit Jeans",
    "regular fit jean": "Regular Fit Jeans", "regular fit": "Regular Fit Jeans",
    "skinny jean": "Skinny Jeans", "skinny": "Skinny Jeans", "bootcut jean": "Bootcut Jeans",
    "bootcut": "Bootcut Jeans",
    "backpack": "Backpack", "school bag": "Backpack", "handbag": "Handbag", "purse": "Handbag",
    "laptop bag": "Laptop Bag", "tote bag": "Tote Bag", "tote": "Tote Bag",
    "sling bag": "Sling Bag", "sling": "Sling Bag",
    "pressure cooker": "Pressure Cooker", "cooker": "Pressure Cooker",
    "non stick pan": "Non-Stick Pan", "non stick": "Non-Stick Pan", "frying pan": "Non-Stick Pan",
    "pan": "Non-Stick Pan", "tawa": "Non-Stick Pan", "kadhai": "Kadhai", "wok": "Kadhai",
    "water bottle": "Water Bottle", "bottle": "Water Bottle", "lunch box": "Lunch Box",
    "tiffin": "Lunch Box", "dabba": "Lunch Box", "dinner set": "Dinner Set",
    "cushion cover": "Cushion Cover", "cushion": "Cushion Cover", "wall clock": "Wall Clock",
    "clock": "Wall Clock", "table lamp": "Table Lamp", "lamp": "Table Lamp",
    "photo frame": "Photo Frame", "frame": "Photo Frame", "flower vase": "Flower Vase",
    "vase": "Flower Vase",
}
SUB_TO_CATEGORY = {
    "Running Shoes": "Footwear", "Sneakers": "Footwear", "Sandals": "Footwear",
    "Formal Shoes": "Footwear", "Slippers": "Footwear", "Casual Shirt": "Shirts",
    "Formal Shirt": "Shirts", "T-Shirt": "Shirts", "Polo Shirt": "Shirts",
    "Straight Kurta": "Kurtas", "Anarkali Kurta": "Kurtas", "Short Kurti": "Kurtas",
    "Pathani Kurta": "Kurtas", "Printed Saree": "Sarees", "Embroidered Saree": "Sarees",
    "Banarasi Saree": "Sarees", "Party Wear Saree": "Sarees", "Slim Fit Jeans": "Jeans",
    "Regular Fit Jeans": "Jeans", "Skinny Jeans": "Jeans", "Bootcut Jeans": "Jeans",
    "Backpack": "Bags", "Handbag": "Bags", "Laptop Bag": "Bags", "Tote Bag": "Bags",
    "Sling Bag": "Bags", "Pressure Cooker": "Kitchen", "Non-Stick Pan": "Kitchen",
    "Kadhai": "Kitchen", "Water Bottle": "Kitchen", "Lunch Box": "Kitchen", "Dinner Set": "Kitchen",
    "Cushion Cover": "Home Decor", "Wall Clock": "Home Decor", "Table Lamp": "Home Decor",
    "Photo Frame": "Home Decor", "Flower Vase": "Home Decor",
}
CATEGORY_KEYWORDS = {
    "shoe": "Footwear", "footwear": "Footwear", "shirt": "Shirts", "kurta": "Kurtas",
    "saree": "Sarees", "jean": "Jeans", "bag": "Bags", "kitchen": "Kitchen",
    "cookware": "Kitchen", "bartan": "Kitchen", "home decor": "Home Decor",
    "decor": "Home Decor", "decoration": "Home Decor",
}
COLOURS = {c.lower(): c for c in ["Black", "White", "Blue", "Red", "Green", "Grey", "Brown",
                                  "Pink", "Yellow", "Maroon", "Beige", "Orange", "Purple", "Silver"]}
MATERIALS = {m.lower(): m for m in [
    "Cotton", "Linen", "Silk", "Polyester", "Rayon", "Khadi", "Georgette", "Chiffon",
    "Stretch Denim", "Denim", "Leather", "Mesh", "Knit", "Canvas", "Synthetic", "Suede",
    "Rubber", "Nylon", "Jute", "Stainless Steel", "Aluminium", "Cast Iron", "Copper",
    "Ceramic", "Glass", "Plastic", "Velvet", "Wood", "Metal", "Brass"]}
MATERIALS["steel"] = "Stainless Steel"

POLICY_WORDS = ["return", "refund", "exchange", "shipping", "ship", "delivery", "deliver",
                "warranty", "guarantee", "cod", "cancel", "cancellation", "emi", "instalment",
                "installment", "gift", "damaged", "defective", "policy"]
POLICY_RE = re.compile(r"\b(" + "|".join(POLICY_WORDS) + r")\b")
PRICE_RES = [
    re.compile(r"\b(?:under|below|less than|within|upto|up to|max|maximum|budget of|budget|"
               r"not more than|cheaper than|lower than)\s+(?:rs\s+|inr\s+)?(\d+)\b"),
    re.compile(r"\b(?:rs\s+|inr\s+)?(\d+)\s+(?:rs\s+|rupee\s+)?(?:se kam|se neeche|se niche|"
               r"tak|ke andar|ke under|ke niche|or less|and below|or below)\b"),
]
SIZE_RES = [re.compile(r"\b(?:size|uk)\s+(\d{1,2}|xxl|xl|xs|s|m|l)\b"), re.compile(r"\b(xxl|xl)\b")]
STOCK_RE = re.compile(r"\b(in stock|instock|available|stock mein|stock me)\b")
CHEAP_RE = re.compile(r"\b(cheapest|cheap|lowest price|least expensive|lowest)\b")
LIST_RE = re.compile(r"\b(show|list|dikhao|dikha|options|all|any|do you have|hai kya)\b")


@dataclass
class ParsedQuery:
    original: str
    text: str = ""                  # normalised text, used for search
    is_policy: bool = False
    category: str = None
    sub_category: str = None
    colour: str = None
    material: str = None
    size: str = None
    max_price: int = None
    in_stock: bool = False
    wants_cheapest: bool = False
    wants_list: bool = False
    named_words: list = field(default_factory=list)    # rare product names, e.g. "aeroglide"
    known_words: list = field(default_factory=list)    # brand words, e.g. "stridex"
    unknown_words: list = field(default_factory=list)  # words we do not sell, e.g. "iphone"
    category_from_llm: bool = False

    def as_dict(self):
        return {k: v for k, v in asdict(self).items() if v not in (None, False, [], "")}


def _phrase_re(phrases):
    """One regex for many phrases, longest first so 'laptop bag' wins over 'bag'."""
    alts = sorted(phrases, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(p) for p in alts) + r")\b")


SUB_RE, CAT_RE = _phrase_re(SUB_KEYWORDS), _phrase_re(CATEGORY_KEYWORDS)
COLOUR_RE, MATERIAL_RE = _phrase_re(COLOURS), _phrase_re(MATERIALS)


def normalise(query, known_words):
    """Lower case, fix spellings and Hinglish, singular nouns, plain numbers."""
    text = query.lower().replace("₹", " rs ")
    text = re.sub(r"(\d),(\d)", r"\1\2", text)                                  # 2,000 -> 2000
    text = re.sub(r"\b(\d+)\s*k\b", lambda m: str(int(m.group(1)) * 1000), text)  # 2k -> 2000
    out = []
    for tok in re.findall(r"[a-z0-9]+", text):
        tok = WORD_FIX.get(tok, tok)
        if tok not in known_words and tok.isalpha() and len(tok) >= 5:
            close = difflib.get_close_matches(tok, known_words, n=1, cutoff=0.85)
            tok = close[0] if close else tok   # "aeroglyde" -> "aeroglide"
        out.extend(singular(t) for t in tok.split())
    return " ".join(out)


def _take(regex, text):
    """Find the first match, return (match, text with the match blanked out)."""
    m = regex.search(text)
    if not m:
        return None, text
    return m, text[:m.start()] + " " + text[m.end():]


def parse_query(query, index, llm=None):
    known = _known_words(index)
    p = ParsedQuery(original=query)
    p.text = rest = normalise(query, known)
    p.is_policy = bool(POLICY_RE.search(rest))
    if p.is_policy:
        return p  # policy questions are answered from the policy, no product filters

    for regex in PRICE_RES:
        m, rest = _take(regex, rest)
        if m:
            p.max_price = int(m.group(1))
            break
    for regex in SIZE_RES:
        m, rest = _take(regex, rest)
        if m:
            p.size = m.group(1).upper()
            break
    m, rest = _take(STOCK_RE, rest)
    p.in_stock = bool(m)
    m, rest = _take(CHEAP_RE, rest)
    p.wants_cheapest = bool(m)
    m, rest = _take(LIST_RE, rest)
    p.wants_list = bool(m)

    m, rest = _take(SUB_RE, rest)
    if m:
        p.sub_category = SUB_KEYWORDS[m.group(1)]
        p.category = SUB_TO_CATEGORY[p.sub_category]
    m, rest = _take(CAT_RE, rest)
    if m and not p.category:
        p.category = CATEGORY_KEYWORDS[m.group(1)]
    m, rest = _take(COLOUR_RE, rest)
    if m:
        p.colour = COLOURS[m.group(1)]
    m, rest = _take(MATERIAL_RE, rest)
    if m:
        p.material = MATERIALS[m.group(1)]

    # sort the words that are left over
    for tok in rest.split():
        if tok in STOPWORDS or tok.isdigit() or len(tok) < 2:
            continue
        if tok in index.rare_words:
            p.named_words.append(tok)
        elif tok in index.name_words:
            p.known_words.append(tok)
        else:
            p.unknown_words.append(tok)

    if not p.category and p.unknown_words and llm is not None:
        _fill_gaps_with_llm(p, llm)
    return p


def _known_words(index):
    """Words we never 'correct': catalogue words, keywords, stop words."""
    if not hasattr(index, "_known_words"):
        words = set(index.vocab) | STOPWORDS | set(WORD_FIX.values())
        for table in (SUB_KEYWORDS, CATEGORY_KEYWORDS, COLOURS, MATERIALS):
            for phrase in table:
                words |= set(phrase.split())
        words |= set(POLICY_WORDS)
        index._known_words = sorted(w for w in words if w)
    return index._known_words


def _fill_gaps_with_llm(p, llm):
    """Ask the language model for missing filters. Only allowed values are kept."""
    categories = sorted(set(SUB_TO_CATEGORY.values()))
    prompt = (f'Shopper query: "{p.original}"\n'
              f"Allowed categories: {categories}\n"
              f"Allowed colours: {sorted(set(COLOURS.values()))}\n"
              f"Allowed materials: {sorted(set(MATERIALS.values()))}\n"
              'Reply with JSON: {"category": ..., "colour": ..., "material": ..., "max_price": ...}. '
              "Use null for anything not stated. If the item is not in the allowed categories, "
              "category must be null.")
    out = llm.chat("You extract shopping filters and reply with strict JSON only.", prompt,
                   json_mode=True, max_tokens=60)
    if not isinstance(out, dict):
        return
    if out.get("category") in categories:
        p.category = out["category"]
        p.category_from_llm = True
    if not p.colour and out.get("colour") in COLOURS.values():
        p.colour = out["colour"]
    if not p.material and out.get("material") in MATERIALS.values():
        p.material = out["material"]
    if not p.max_price and isinstance(out.get("max_price"), (int, float)) and out["max_price"] > 0:
        p.max_price = int(out["max_price"])
