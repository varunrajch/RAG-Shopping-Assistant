"""
generate_data.py
Creates the demo data with plain Python and a fixed random seed.
No language model is used, so the data is the same on every run.

Output (in data/generated/):
  catalogue.csv        5,000 products
  policy.md            returns (R), shipping (S) and warranty (W) rules
  test_questions.json  60 labelled test questions (51 single + 3 conversations x 3 turns)

Run:  python generate_data.py
"""
import json
import random

import pandas as pd

from config import GENERATED_DIR

SEED = 42
N_PRODUCTS = 5000

# ---------------------------------------------------------------- catalogue spec
# For every category: brands, and for every sub-category its materials,
# sizes and price range in rupees. All brand names are made up.
SPEC = {
    "Footwear": {
        "brands": ["Stridex", "UrbanPace", "Trailmark", "Padukaa"],
        "colours": ["Black", "White", "Blue", "Red", "Grey", "Brown", "Green"],
        "subs": {
            "Running Shoes": (["Mesh", "Synthetic", "Knit"], None, 999, 4999),
            "Sneakers": (["Canvas", "Leather", "Synthetic", "Suede"], None, 799, 3999),
            "Sandals": (["Leather", "Synthetic", "Rubber"], None, 399, 1999),
            "Formal Shoes": (["Leather", "Synthetic"], None, 1299, 4999),
            "Slippers": (["Rubber", "Synthetic"], None, 199, 899),
        },
        "sizes": [f"UK {n}" for n in range(6, 12)],
        "features": ["Cushioned sole for all-day comfort.", "Lightweight build with a firm grip.",
                     "Breathable lining keeps feet cool."],
    },
    "Shirts": {
        "brands": ["Threadline", "Collarwise", "UrbanPace"],
        "colours": ["White", "Blue", "Black", "Grey", "Pink", "Green", "Beige", "Maroon"],
        "subs": {
            "Casual Shirt": (["Cotton", "Linen", "Rayon"], None, 499, 1999),
            "Formal Shirt": (["Cotton", "Polyester", "Linen"], None, 699, 2499),
            "T-Shirt": (["Cotton", "Polyester"], None, 299, 999),
            "Polo Shirt": (["Cotton", "Polyester"], None, 499, 1499),
        },
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "features": ["Regular fit with a soft finish.", "Easy to wash and quick to dry.",
                     "Comfortable for office and casual wear."],
    },
    "Kurtas": {
        "brands": ["Kalaa", "Sutra", "Bunkar"],
        "colours": ["White", "Blue", "Red", "Yellow", "Pink", "Green", "Maroon", "Beige", "Orange"],
        "subs": {
            "Straight Kurta": (["Cotton", "Rayon", "Linen", "Khadi"], None, 599, 2999),
            "Anarkali Kurta": (["Cotton", "Rayon", "Silk"], None, 999, 3999),
            "Short Kurti": (["Cotton", "Rayon"], None, 399, 1499),
            "Pathani Kurta": (["Cotton", "Linen", "Khadi"], None, 899, 2999),
        },
        "sizes": ["S", "M", "L", "XL", "XXL"],
        "features": ["Hand block print with a relaxed fit.", "Three quarter sleeves and side slits.",
                     "Festive look that is comfortable all day."],
    },
    "Sarees": {
        "brands": ["Bunkar", "Rangoli", "Kaashi"],
        "colours": ["Red", "Maroon", "Pink", "Green", "Blue", "Yellow", "Purple", "Orange"],
        "subs": {
            "Printed Saree": (["Cotton", "Georgette", "Chiffon"], None, 799, 2999),
            "Embroidered Saree": (["Georgette", "Silk", "Chiffon"], None, 1499, 5999),
            "Banarasi Saree": (["Silk"], None, 2999, 12999),
            "Party Wear Saree": (["Georgette", "Chiffon", "Silk"], None, 1999, 7999),
        },
        "sizes": ["Free Size"],
        "features": ["Comes with an unstitched blouse piece.", "Elegant drape with a woven border.",
                     "Light enough for long functions."],
    },
    "Jeans": {
        "brands": ["DenimCo", "Rivet", "Threadline"],
        "colours": ["Blue", "Black", "Grey"],
        "subs": {
            "Slim Fit Jeans": (["Denim", "Stretch Denim"], None, 799, 2999),
            "Regular Fit Jeans": (["Denim"], None, 799, 2499),
            "Skinny Jeans": (["Stretch Denim"], None, 899, 2999),
            "Bootcut Jeans": (["Denim", "Stretch Denim"], None, 999, 2999),
        },
        "sizes": ["28", "30", "32", "34", "36"],
        "features": ["Five pocket design with a mid rise.", "Fade resistant wash.",
                     "Comfortable fit for daily wear."],
    },
    "Bags": {
        "brands": ["Trekka", "Carryall", "Zaira"],
        "colours": ["Black", "Brown", "Blue", "Grey", "Red", "Beige", "Green"],
        "subs": {
            "Backpack": (["Polyester", "Nylon", "Canvas"], None, 599, 2999),
            "Handbag": (["Leather", "Synthetic", "Jute"], None, 699, 4999),
            "Laptop Bag": (["Polyester", "Nylon", "Leather"], None, 899, 3999),
            "Tote Bag": (["Canvas", "Jute", "Cotton"], None, 299, 1499),
            "Sling Bag": (["Leather", "Canvas", "Nylon"], None, 399, 1999),
        },
        "sizes": ["One Size"],
        "features": ["Padded straps and many pockets.", "Strong zips and stitched seams.",
                     "Fits daily essentials with room to spare."],
    },
    "Kitchen": {
        "brands": ["Rasoi Pro", "Steelwala", "Handi House"],
        "colours": ["Silver", "Black", "Red", "Blue", "Green"],
        "subs": {
            "Pressure Cooker": (["Stainless Steel", "Aluminium"], ["3 L", "5 L"], 1199, 3999),
            "Non-Stick Pan": (["Aluminium"], ["24 cm", "28 cm"], 499, 1999),
            "Kadhai": (["Cast Iron", "Stainless Steel", "Aluminium"], ["24 cm", "28 cm"], 599, 2499),
            "Water Bottle": (["Stainless Steel", "Copper", "Glass"], ["750 ml", "1 L"], 299, 1499),
            "Lunch Box": (["Stainless Steel", "Plastic"], ["2 Containers", "3 Containers"], 299, 999),
            "Dinner Set": (["Ceramic", "Stainless Steel"], ["18 Pcs", "24 Pcs"], 1499, 5999),
        },
        "sizes": None,
        "features": ["Works on gas and induction.", "Easy to clean and long lasting.",
                     "Food grade material."],
    },
    "Home Decor": {
        "brands": ["GharSaaj", "Nook", "Diya"],
        "colours": ["White", "Black", "Brown", "Beige", "Blue", "Green", "Yellow", "Red"],
        "subs": {
            "Cushion Cover": (["Cotton", "Velvet", "Jute"], ["16 x 16 in"], 199, 799),
            "Wall Clock": (["Wood", "Metal", "Plastic"], ["12 in"], 499, 2499),
            "Table Lamp": (["Brass", "Wood", "Metal", "Ceramic"], ["Standard"], 799, 3999),
            "Photo Frame": (["Wood", "Metal"], ["8 x 10 in"], 199, 999),
            "Flower Vase": (["Ceramic", "Glass", "Brass"], ["10 in"], 299, 1999),
        },
        "sizes": None,
        "features": ["Adds a warm touch to any room.", "Handcrafted finish.",
                     "Makes a thoughtful gift."],
    },
}

# Hand placed products. Products with a model name (AeroGlide, Chikankari, ...)
# are used by test questions that need exactly one correct answer.
# The others make sure the near duplicates and multi turn tests always exist.
# (brand, model, colour, material, category, sub_category, size, price, stock, rating)
FIXED = [
    ("Stridex", "AeroGlide", "White", "Mesh", "Footwear", "Running Shoes", "UK 9", 3499, "in_stock", 4.6),
    ("Kalaa", "Chikankari", "White", "Cotton", "Kurtas", "Straight Kurta", "M", 1299, "in_stock", 4.5),
    ("Bunkar", "Rajmahal", "Maroon", "Silk", "Sarees", "Banarasi Saree", "Free Size", 8999, "low_stock", 4.8),
    ("Rasoi Pro", "Everlast", "Silver", "Stainless Steel", "Kitchen", "Pressure Cooker", "5 L", 2499, "in_stock", 4.4),
    ("Trekka", "Voyager", "Black", "Polyester", "Bags", "Laptop Bag", "One Size", 1899, "out_of_stock", 4.3),
    ("GharSaaj", "Moonbeam", "Beige", "Brass", "Home Decor", "Table Lamp", "Standard", 2199, "in_stock", 4.2),
    ("DenimCo", "Flexmax", "Blue", "Stretch Denim", "Jeans", "Slim Fit Jeans", "32", 1799, "in_stock", 4.1),
    ("Threadline", "Coastline", "Green", "Linen", "Shirts", "Casual Shirt", "L", 1499, "in_stock", 4.3),
    # deliberate near duplicates: three blue running shoes from one brand at different prices
    ("Stridex", "", "Blue", "Mesh", "Footwear", "Running Shoes", "UK 8", 1299, "in_stock", 4.0),
    ("Stridex", "", "Blue", "Mesh", "Footwear", "Running Shoes", "UK 9", 1899, "in_stock", 4.2),
    ("Stridex", "", "Blue", "Mesh", "Footwear", "Running Shoes", "UK 10", 2799, "low_stock", 4.4),
    # rows the multi turn conversations rely on
    ("Sutra", "", "Maroon", "Cotton", "Kurtas", "Straight Kurta", "L", 1149, "in_stock", 4.1),
    ("Collarwise", "", "White", "Cotton", "Shirts", "Casual Shirt", "M", 749, "in_stock", 3.9),
    ("UrbanPace", "", "Black", "Mesh", "Footwear", "Running Shoes", "UK 9", 1599, "in_stock", 4.0),
    ("Trailmark", "", "Black", "Synthetic", "Footwear", "Running Shoes", "UK 9", 1899, "in_stock", 3.8),
]

STOCK_CHOICES = ["in_stock", "low_stock", "out_of_stock"]
STOCK_WEIGHTS = [0.75, 0.10, 0.15]


def make_price(rng, low, high):
    """Random price that ends in 9, like most Indian retail prices."""
    return int(round(rng.uniform(low, high) / 10) * 10 - 1)


def make_row(brand, model, colour, material, category, sub, size, price, stock, rating, rng):
    name = f"{brand} {model} " if model else f"{brand} "
    title = f"{name}{colour} {material} {sub}"
    feature = rng.choice(SPEC[category]["features"])
    description = (f"{sub} by {brand} in {colour.lower()} {material.lower()}. "
                   f"{feature} Size: {size}.")
    return {"title": title, "description": description, "category": category,
            "sub_category": sub, "brand": brand, "colour": colour, "size": size,
            "material": material, "price": price, "stock_status": stock, "rating": rating}


def make_catalogue(rng):
    rows = [make_row(*f, rng=rng) for f in FIXED]
    categories = list(SPEC)
    while len(rows) < N_PRODUCTS:
        category = rng.choice(categories)
        spec = SPEC[category]
        sub = rng.choice(list(spec["subs"]))
        materials, sub_sizes, low, high = spec["subs"][sub]
        size = rng.choice(sub_sizes or spec["sizes"])
        rows.append(make_row(
            rng.choice(spec["brands"]), "", rng.choice(spec["colours"]), rng.choice(materials),
            category, sub, size, make_price(rng, low, high),
            rng.choices(STOCK_CHOICES, STOCK_WEIGHTS)[0], round(rng.uniform(2.8, 4.9), 1), rng))
    rng.shuffle(rows)  # mix the fixed rows in with the rest
    df = pd.DataFrame(rows)
    df.insert(0, "product_id", [f"P{i:05d}" for i in range(1, len(df) + 1)])
    return df


# ---------------------------------------------------------------- policy
POLICY = """# Store Policy

## R1. Return window
You can return most items within 10 days of delivery for a full refund. The item must be unused, with the original tags and packaging. Start a return from the My Orders page.

## R2. Items that cannot be returned
Sarees with a stitched blouse, items marked Final Sale, and kitchen items that have been used cannot be returned. Lunch boxes and water bottles cannot be returned once the seal is opened.

## R3. Refunds
Refunds go to the original payment method within 5 to 7 working days after the item passes a quality check at our warehouse. For orders paid in cash, the refund is sent to your bank account by NEFT.

## R4. Exchanges
Footwear, shirts, kurtas and jeans can be exchanged once for a different size within 10 days of delivery, subject to stock. Exchanges for a different colour or product are not possible; please place a new order.

## R5. Damaged or wrong item
If an item arrives damaged, defective or different from what you ordered, report it within 48 hours of delivery with photos. We arrange a free pickup and send a replacement or a full refund.

## S1. Where we ship
We ship to all serviceable pin codes in India. We do not ship outside India; international shipping is not available.

## S2. Shipping charges
Shipping is free on orders of ₹999 and above. A shipping fee of ₹79 applies to orders below ₹999.

## S3. Delivery time
Orders to metro cities are delivered in 2 to 4 business days. Other locations take 4 to 7 business days. You get a tracking link by SMS and email once the order is dispatched.

## S4. Cash on delivery
Cash on delivery (COD) is available on orders up to ₹10,000. A COD fee of ₹49 is charged per order.

## S5. Order cancellation
You can cancel an order free of charge before it is dispatched. Once an order has been dispatched it cannot be cancelled, but you can send it back under section R1.

## W1. Kitchen warranty
Pressure cookers come with a 5 year manufacturer warranty against manufacturing defects. Non-stick pans carry a 1 year warranty on the coating. Kadhais, bottles, lunch boxes and dinner sets have no warranty.

## W2. Home decor warranty
Wall clocks carry a 1 year warranty on the clock movement and table lamps a 1 year warranty on electrical parts. Bulbs and breakage of glass or ceramic are not covered.

## W3. Clothing, footwear and bags
Clothing, footwear and bags do not carry a warranty. Quality problems are handled under sections R1 and R5.

## W4. How to claim warranty
Email support with your order number, invoice and photos of the defect. We repair or replace the product within 15 working days after inspection.
"""


# ---------------------------------------------------------------- test questions
def match(df, category=None, sub=None, colour=None, material=None, size=None,
          max_price=None, in_stock=False, name=None):
    """Rows that satisfy a structured spec. Used to compute the expected answers."""
    m = pd.Series(True, index=df.index)
    if category:
        m &= df.category == category
    if sub:
        m &= df.sub_category == sub
    if colour:
        m &= df.colour == colour
    if material:
        m &= df.material == material
    if size:
        m &= df["size"].isin([size, f"UK {size}"])
    if max_price:
        m &= df.price <= max_price
    if in_stock:
        m &= df.stock_status != "out_of_stock"
    if name:
        m &= df.title.str.contains(name)
    return df[m]


def make_questions(df):
    questions = []

    def add(query, qtype, expected, ids=(), section=None, spec=None, conv=None, turn=None):
        questions.append({"id": f"Q{len(questions) + 1:02d}", "query": query, "type": qtype,
                          "expected": expected, "expected_ids": list(ids),
                          "expected_policy": section, "spec": spec or {},
                          "conversation": conv, "turn": turn})

    def single(query, qtype, name, **kw):
        rows = match(df, name=name)
        assert len(rows) == 1, name
        add(query, qtype, "answer", rows.product_id, spec={"name": name}, **kw)

    def listing(query, qtype, conv=None, turn=None, **spec):
        rows = match(df, **spec)
        assert len(rows) >= 1, spec
        add(query, qtype, "answer", sorted(rows.product_id), spec=spec, conv=conv, turn=turn)

    def cheapest(query, qtype, conv=None, turn=None, **spec):
        rows = match(df, **spec)
        assert len(rows) >= 1, spec
        best = rows[rows.price == rows.price.min()]
        add(query, qtype, "answer", sorted(best.product_id), spec=spec, conv=conv, turn=turn)

    def auto(query, qtype, conv=None, turn=None, **spec):
        # 0 matches -> refuse, 1 -> answer, 2 or more -> clarify
        rows = match(df, **spec)
        label = "refuse" if len(rows) == 0 else "answer" if len(rows) == 1 else "clarify"
        add(query, qtype, label, rows.product_id if label == "answer" else [], spec=spec,
            conv=conv, turn=turn)

    def refuse(query, qtype):
        add(query, qtype, "refuse")

    def policy(query, qtype, section):
        add(query, qtype, "answer", section=section)

    # English
    single("How much is the Stridex AeroGlide?", "english", "AeroGlide")
    single("Is the Everlast pressure cooker in stock?", "english", "Everlast")
    single("Tell me about the Voyager laptop bag", "english", "Voyager")
    single("Rajmahal saree price", "english", "Rajmahal")
    single("What material is the Moonbeam lamp?", "english", "Moonbeam")
    single("What colour is the Coastline shirt?", "english", "Coastline")
    listing("Show me white cotton shirts under ₹1,000", "english",
            category="Shirts", colour="White", material="Cotton", max_price=1000)
    cheapest("Cheapest non-stick pan", "english", sub="Non-Stick Pan")
    listing("List backpacks under ₹800 in stock", "english",
            sub="Backpack", max_price=800, in_stock=True)
    listing("Do you have green cushion covers?", "english", sub="Cushion Cover", colour="Green")
    auto("I need a maroon silk saree", "english", category="Sarees", colour="Maroon", material="Silk")

    # Hinglish
    cheapest("blu running shoe sasta wala", "hinglish", sub="Running Shoes", colour="Blue")
    listing("cotton kurta 1500 se kam hai kya", "hinglish",
            category="Kurtas", material="Cotton", max_price=1500)
    listing("kala joota size 9 dikhao", "hinglish", category="Footwear", colour="Black", size="9")
    auto("neeli jeans 1000 tak", "hinglish", category="Jeans", colour="Blue", max_price=1000)
    auto("lal saree chahiye", "hinglish", category="Sarees", colour="Red")
    cheapest("steel ka pressure cooker sasta wala", "hinglish",
             sub="Pressure Cooker", material="Stainless Steel")
    single("Chikankari kurta ka price kya hai?", "hinglish", "Chikankari")
    listing("laptop bag 2000 ke andar dikhao", "hinglish", sub="Laptop Bag", max_price=2000)

    # Misspelt
    single("aeroglyde runing shoes price", "misspelt", "AeroGlide")
    cheapest("cheep cotton kurtha", "misspelt", category="Kurtas", material="Cotton")
    auto("blak lether handbag under 3000", "misspelt",
         sub="Handbag", colour="Black", material="Leather", max_price=3000)
    listing("show sneakrs under 1500", "misspelt", sub="Sneakers", max_price=1500)
    cheapest("presure cooker cheapest", "misspelt", sub="Pressure Cooker")
    auto("pink sare", "misspelt", category="Sarees", colour="Pink")
    single("chikankri kurta", "misspelt", "Chikankari")

    # Out of catalogue
    refuse("Do you sell iPhones?", "out_of_catalogue")
    refuse("Do you have a gaming laptop?", "out_of_catalogue")
    refuse("Any LED TV under 20000?", "out_of_catalogue")
    refuse("I want a gold necklace", "out_of_catalogue")
    refuse("Do you sell washing machines?", "out_of_catalogue")
    refuse("football boots size 9", "out_of_catalogue")

    # Traps: ambiguous or impossible requests where a made up answer is tempting
    auto("Price of the blue running shoe?", "trap", sub="Running Shoes", colour="Blue")
    refuse("What is the price of the iPhone 15?", "trap")
    auto("Is the red saree in stock?", "trap", category="Sarees", colour="Red", in_stock=True)
    refuse("What is the cheapest laptop?", "trap")
    auto("Silk saree under ₹500", "trap", category="Sarees", material="Silk", max_price=500)
    auto("Green leather jeans", "trap", category="Jeans", colour="Green", material="Leather")
    auto("Running shoes in size 14", "trap", sub="Running Shoes", size="14")
    assert len(match(df, name="Voyager", colour="Red")) == 0
    refuse("Do you have the Voyager laptop bag in red?", "trap")

    # Policy
    policy("What is your return policy?", "policy", "R1")
    policy("How many days do I have to return an item?", "policy", "R1")
    policy("When will I get my refund?", "policy", "R3")
    policy("Is shipping free?", "policy", "S2")
    policy("Do you ship outside India?", "policy", "S1")
    policy("Is cash on delivery available?", "policy", "S4")
    policy("What is the warranty on pressure cookers?", "policy", "W1")
    policy("Can I exchange shoes for a different size?", "policy", "R4")
    policy("return kitne din mein kar sakte hai?", "policy", "R1")
    refuse("Do you offer EMI?", "policy")
    refuse("Do you offer gift wrapping?", "policy")

    # Multi turn: a limit set in an earlier turn must still apply later
    auto("I want a kurta under ₹2,000", "multi_turn", conv="C1", turn=1,
         category="Kurtas", max_price=2000)
    listing("show me cotton ones", "multi_turn", conv="C1", turn=2,
            category="Kurtas", material="Cotton", max_price=2000)
    cheapest("which is the cheapest in maroon?", "multi_turn", conv="C1", turn=3,
             category="Kurtas", material="Cotton", colour="Maroon", max_price=2000)

    auto("I want a cotton shirt", "multi_turn", conv="C2", turn=1, category="Shirts", material="Cotton")
    listing("show me white ones under ₹800", "multi_turn", conv="C2", turn=2,
            category="Shirts", material="Cotton", colour="White", max_price=800)
    cheapest("I already said cotton, give me the cheapest", "multi_turn", conv="C2", turn=3,
             category="Shirts", material="Cotton", colour="White", max_price=800)

    auto("running shoes under 2000", "multi_turn", conv="C3", turn=1, sub="Running Shoes", max_price=2000)
    auto("black ones in size 9", "multi_turn", conv="C3", turn=2,
         sub="Running Shoes", colour="Black", size="9", max_price=2000)
    cheapest("sasta wala kaunsa hai?", "multi_turn", conv="C3", turn=3,
             sub="Running Shoes", colour="Black", size="9", max_price=2000)

    assert len(questions) == 60, len(questions)
    return questions


def main():
    rng = random.Random(SEED)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    df = make_catalogue(rng)
    df.to_csv(GENERATED_DIR / "catalogue.csv", index=False)
    (GENERATED_DIR / "policy.md").write_text(POLICY, encoding="utf-8")
    questions = make_questions(df)
    with open(GENERATED_DIR / "test_questions.json", "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    counts = pd.Series([q["expected"] for q in questions]).value_counts().to_dict()
    print(f"Wrote {len(df)} products, policy and {len(questions)} questions to {GENERATED_DIR}")
    print("Expected behaviour counts:", counts)


if __name__ == "__main__":
    main()
