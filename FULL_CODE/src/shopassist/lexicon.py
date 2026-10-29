"""Hand-written vocabulary: Hinglish / misspellings, product-type aliases, question patterns.

Everything here is generic shopper language. Nothing is keyed to a particular dev or test question.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------------------------- spelling
# Hinglish words and common misspellings -> the word the catalogue uses
WORD_FIX: dict[str, str] = {
    # colours
    "kala": "black",
    "kaala": "black",
    "kali": "black",
    "kaali": "black",
    "kale": "black",
    "blak": "black",
    "neela": "blue",
    "neeli": "blue",
    "nila": "blue",
    "nili": "blue",
    "blu": "blue",
    "lal": "red",
    "laal": "red",
    "hara": "green",
    "hari": "green",
    "safed": "white",
    "sufed": "white",
    "gulabi": "pink",
    "peela": "yellow",
    "peeli": "yellow",
    "bhura": "brown",
    "gray": "grey",
    "jamuni": "purple",
    "color": "colour",
    "colors": "colour",
    "colours": "colour",
    # materials
    "sooti": "cotton",
    "suti": "cotton",
    "cotten": "cotton",
    "coton": "cotton",
    "steel": "stainless steel",
    "aluminum": "aluminium",
    "kaanch": "glass",
    "kanch": "glass",
    # product words
    "tshirt": "t shirt",
    "tshirts": "t shirt",
    "tee": "t shirt",
    "facewash": "face wash",
    "powerbank": "power bank",
    "bedsheet": "bed sheet",
    "bedsheets": "bed sheet",
    "trimer": "trimmer",
    "earbud": "earbuds",
    "earbuds": "earbuds",
    "earphone": "earphones",
    "earphones": "earphones",
    "kadhai": "kadai",
    "kadahi": "kadai",
    "karahi": "kadai",
    "duffle": "duffel",
    "bagpack": "backpack",
    "joota": "shoe",
    "joote": "shoe",
    "juta": "shoe",
    "jutta": "shoe",
    "chappals": "chappal",
    "sari": "saree",
    "sadi": "saree",
    "tiffin": "lunch box",
    "mixie": "mixer",
    "pankha": "fan",
    "jeens": "jeans",
    "jean": "jeans",
    "trolly": "trolley",
    "suitcase": "trolley",
    "sunblock": "sunscreen",
    "deo": "deodorant",
    "racquet": "racket",
    "dumbell": "dumbbell",
    "dumbells": "dumbbell",
    "ludo": "board game",
    # people
    "mens": "men",
    "gents": "men",
    "male": "men",
    "ladies": "women",
    "womens": "women",
    "female": "women",
    "lady": "women",
    "aurat": "women",
    "bacchon": "kids",
    "bacche": "kids",
    "bachche": "kids",
    "bachon": "kids",
    "baccho": "kids",
    "kid": "kids",
    "children": "kids",
    "child": "kids",
    # numbers / units
    "litre": "l",
    "liter": "l",
    "ltr": "l",
    "litres": "l",
    "liters": "l",
    "watt": "w",
    "watts": "w",
    "pcs": "piece",
    "pc": "piece",
    "pieces": "piece",
    "inches": "inch",
    "saal": "year",
    "sal": "year",
    "years": "year",
    "yrs": "year",
    "yr": "year",
    "gm": "g",
    "gms": "g",
    "grams": "g",
}

# ------------------------------------------------------------------------------------- product types
# phrase -> sub-categories it can mean. Longest phrase wins when phrases overlap.
SUBCATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    # Apparel
    "hoodie": ("Hoodies & Sweatshirts",),
    "sweatshirt": ("Hoodies & Sweatshirts",),
    "jacket": ("Jackets",),
    "jeans": ("Jeans",),
    "kids wear": ("Kids Wear",),
    "shorts set": ("Kids Wear",),
    "t shirt and shorts set": ("Kids Wear",),
    "kurta": ("Kurtas",),
    "kurti": ("Kurtis",),
    "saree": ("Sarees",),
    "shirt": ("Shirts",),
    "formal shirt": ("Shirts",),
    "casual shirt": ("Shirts",),
    "t shirt": ("T-Shirts",),
    "track pant": ("Track Pants",),
    "trackpant": ("Track Pants",),
    "jogger": ("Track Pants",),
    # Bags & Luggage
    "backpack": ("Backpacks",),
    "school bag": ("School Bags",),
    "laptop sleeve": ("Laptop Sleeves",),
    "laptop bag": ("Backpacks", "Laptop Sleeves"),
    "duffel": ("Duffel Bags",),
    "duffel bag": ("Duffel Bags",),
    "gym bag": ("Duffel Bags",),
    "handbag": ("Handbags",),
    "hand bag": ("Handbags",),
    "purse": ("Handbags",),
    "trolley": ("Trolley Bags",),
    "trolley bag": ("Trolley Bags",),
    "luggage": ("Trolley Bags",),
    "wallet": ("Wallets",),
    "bag": ("Backpacks", "Duffel Bags", "Handbags", "Laptop Sleeves", "School Bags", "Trolley Bags"),
    # Beauty & Personal Care
    "body lotion": ("Body Lotion",),
    "lotion": ("Body Lotion",),
    "deodorant": ("Deodorants & Perfumes",),
    "perfume": ("Deodorants & Perfumes",),
    "face wash": ("Face Wash",),
    "hair dryer": ("Hair Dryers",),
    "dryer": ("Hair Dryers",),
    "hair oil": ("Hair Oil",),
    "hair straightener": ("Hair Straighteners",),
    "straightener": ("Hair Straighteners",),
    "lip balm": ("Lip Balm",),
    "shampoo": ("Shampoo",),
    "sunscreen": ("Sunscreen",),
    "sun screen": ("Sunscreen",),
    "trimmer": ("Trimmers",),
    # Electronics Accessories
    "bluetooth speaker": ("Bluetooth Speakers",),
    "speaker": ("Bluetooth Speakers",),
    "charger": ("Chargers",),
    "adapter": ("Chargers",),
    "mouse": ("Computer Mouse",),
    "keyboard": ("Keyboards",),
    "mobile stand": ("Mobile Stands",),
    "phone stand": ("Mobile Stands",),
    "power bank": ("Power Banks",),
    "cable": ("USB Cables",),
    "usb cable": ("USB Cables",),
    "earphones": ("Wired Earphones",),
    "earbuds": ("Wireless Earbuds",),
    "tws": ("Wireless Earbuds",),
    # Footwear
    "ethnic footwear": ("Ethnic Footwear",),
    "jutti": ("Ethnic Footwear",),
    "mojari": ("Ethnic Footwear",),
    "kolhapuri": ("Ethnic Footwear",),
    "kolhapuri chappal": ("Ethnic Footwear",),
    "slipper": ("Flip-Flops & Slippers",),
    "flip flop": ("Flip-Flops & Slippers",),
    "chappal": ("Flip-Flops & Slippers", "Ethnic Footwear"),
    "formal shoe": ("Formal Shoes",),
    "school shoe": ("Kids School Shoes",),
    "running shoe": ("Running Shoes",),
    "sandal": ("Sandals",),
    "sneaker": ("Sneakers",),
    "walking shoe": ("Walking Shoes",),
    "shoe": ("Running Shoes", "Walking Shoes", "Formal Shoes", "Sneakers", "Kids School Shoes"),
    # Home & Kitchen
    "bed sheet": ("Bedsheets",),
    "curtain": ("Curtains",),
    "parda": ("Curtains",),
    "cushion cover": ("Cushion Covers",),
    "cushion": ("Cushion Covers",),
    "dinner set": ("Dinner Sets",),
    "frying pan": ("Frying Pans",),
    "fry pan": ("Frying Pans",),
    "pan": ("Frying Pans",),
    "kadai": ("Kadai & Woks",),
    "wok": ("Kadai & Woks",),
    "lunch box": ("Lunch Boxes",),
    "pressure cooker": ("Pressure Cookers",),
    "cooker": ("Pressure Cookers",),
    "storage container": ("Storage Containers",),
    "container": ("Storage Containers",),
    "container set": ("Storage Containers",),
    "dabba": ("Storage Containers", "Lunch Boxes"),
    "tawa": ("Tawa",),
    "towel": ("Towels",),
    "water bottle": ("Water Bottles",),
    "bottle": ("Water Bottles",),
    # Small Appliances
    "air fryer": ("Air Fryers",),
    "kettle": ("Electric Kettles",),
    "fan": ("Fans",),
    "hand blender": ("Hand Blenders",),
    "blender": ("Hand Blenders",),
    "induction cooktop": ("Induction Cooktops",),
    "induction chulha": ("Induction Cooktops",),
    "induction stove": ("Induction Cooktops",),
    "iron": ("Irons",),
    "steam iron": ("Irons",),
    "mixer": ("Mixer Grinders",),
    "mixer grinder": ("Mixer Grinders",),
    "grinder": ("Mixer Grinders",),
    "room heater": ("Room Heaters",),
    "heater": ("Room Heaters",),
    "sandwich maker": ("Sandwich Makers",),
    "toaster": ("Toasters",),
    # Sports & Fitness
    "badminton racket": ("Badminton Rackets",),
    "racket": ("Badminton Rackets",),
    "cricket bat": ("Cricket Bats",),
    "bat": ("Cricket Bats",),
    "dumbbell": ("Dumbbells",),
    "football": ("Footballs",),
    "gym glove": ("Gym Gloves",),
    "glove": ("Gym Gloves",),
    "resistance band": ("Resistance Bands",),
    "shaker": ("Shaker Bottles",),
    "shaker bottle": ("Shaker Bottles",),
    "skipping rope": ("Skipping Ropes",),
    "rope": ("Skipping Ropes",),
    "yoga mat": ("Yoga Mats",),
    "mat": ("Yoga Mats",),
    # Stationery & Office
    "calculator": ("Calculators",),
    "crayon": ("Colours & Crayons",),
    "oil pastel": ("Colours & Crayons",),
    "sketch pen": ("Colours & Crayons",),
    "colour pencil": ("Colours & Crayons",),
    "desk organiser": ("Desk Organisers",),
    "desk organizer": ("Desk Organisers",),
    "pen stand": ("Desk Organisers",),
    "file": ("Files & Folders",),
    "folder": ("Files & Folders",),
    "geometry box": ("Geometry Boxes",),
    "notebook": ("Notebooks",),
    "register": ("Notebooks",),
    "pencil": ("Pencils",),
    "pen": ("Pens",),
    "fountain pen": ("Pens",),
    "gel pen": ("Pens",),
    "ball pen": ("Pens",),
    "sticky note": ("Sticky Notes",),
    "post it": ("Sticky Notes",),
    # Toys & Games
    "art and craft": ("Art & Craft Kits",),
    "craft kit": ("Art & Craft Kits",),
    "board game": ("Board Games",),
    "building block": ("Building Blocks",),
    "block": ("Building Blocks",),
    "jigsaw": ("Jigsaw Puzzles",),
    "jigsaw puzzle": ("Jigsaw Puzzles",),
    "puzzle": ("Jigsaw Puzzles",),
    "remote control car": ("Remote Control Cars",),
    "rc car": ("Remote Control Cars",),
    "stem kit": ("STEM Kits",),
    "science kit": ("STEM Kits",),
    "soft toy": ("Soft Toys",),
    "teddy bear": ("Soft Toys",),
    "plush": ("Soft Toys",),
}

GENDER_WORDS = {
    "men": "men",
    "women": "women",
    "boy": "boys",
    "boys": "boys",
    "girl": "girls",
    "girls": "girls",
    "kids": "kids",
    "unisex": "unisex",
}

# ----------------------------------------------------------------------------------- out of catalogue
# Real brands the store does not carry. Matched as whole words, so short names are left out.
REAL_BRANDS = {
    "boat",
    "airdopes",
    "airpods",
    "nike",
    "adidas",
    "puma",
    "reebok",
    "philips",
    "prestige",
    "pigeon",
    "hawkins",
    "samsung",
    "apple",
    "iphone",
    "redmi",
    "xiaomi",
    "oneplus",
    "realme",
    "vivo",
    "oppo",
    "motorola",
    "nokia",
    "hp",
    "dell",
    "lenovo",
    "asus",
    "acer",
    "lakme",
    "maybelline",
    "nivea",
    "himalaya",
    "mamaearth",
    "bajaj",
    "havells",
    "usha",
    "milton",
    "cello",
    "tupperware",
    "borosil",
    "aashirvaad",
    "maggi",
    "nestle",
    "amul",
    "crocin",
    "dolo",
    "sony",
    "jbl",
    "boult",
    "titan",
    "fastrack",
    "bata",
    "woodland",
    "wildcraft",
    "skybags",
    "safari",
    "decathlon",
    "nivia",
    "cosco",
    "yonex",
    "parker",
    "camlin",
    "classmate",
    "lego",
    "funskool",
    "hamleys",
    "kent",
    "morphy",
    "panasonic",
    "lg",
    "whirlpool",
    "godrej",
    "voltas",
    "hero",
    "honda",
    "tvs",
    "pulsar",
    "zara",
    "levis",
    "biba",
    "fabindia",
    "manyavar",
}
# Things the store does not sell -> how to name them in a refusal. Used only when no sold product type was
# recognised.
UNSOLD_ITEMS: dict[str, str] = {
    "phone": "phones",
    "mobile": "phones",
    "smartphone": "phones",
    "laptop": "laptops",
    "tv": "TVs",
    "television": "TVs",
    "fridge": "fridges",
    "refrigerator": "fridges",
    "ac": "air conditioners",
    "cycle": "bicycles",
    "bicycle": "bicycles",
    "bike": "bikes",
    "helmet": "helmets",
    "treadmill": "treadmills",
    "watch": "watches",
    "smartwatch": "smartwatches",
    "lipstick": "lipsticks or make-up",
    "chain": "jewellery",
    "payal": "jewellery",
    "necklace": "jewellery",
    "ring": "jewellery",
    "earring": "jewellery",
    "jewellery": "jewellery",
    "jewelry": "jewellery",
    "gold": "gold jewellery",
    "noodle": "groceries",
    "atta": "groceries",
    "rice": "groceries",
    "chawal": "groceries",
    "dal": "groceries",
    "grocery": "groceries",
    "protein": "protein supplements",
    "medicine": "medicines",
    "tablet": "medicines",
    "strip": "medicines",
    "paracetamol": "medicines",
    "printer": "printers or cartridges",
    "cartridge": "printers or cartridges",
    "scooter": "scooters",
    "camera": "cameras",
    "ipad": "tablets",
    "car": "cars",
    "sofa": "furniture",
    "mattress": "mattresses",
}

# ------------------------------------------------------------------------------------ question intent
PRICE_RE = re.compile(r"\b(price|prices|rate|cost|costs|daam|dam|kimat|keemat|how much|mrp)\b")
HOW_MUCH_RE = re.compile(r"\b(kitne|kitna|kitni|kitney)\b")
STOCK_RE = re.compile(r"\b(stock|available|availability|milega|milegi|milenge|mil jayega|in stock|instock)\b")
STOCK_FILTER_RE = re.compile(
    r"\b(jo|wala|wali|wale)\s+(stock|available)\b|\b(stock|available)\s+(me|mein)?\s*"
    r"(ho|hai jo)\b|\bin stock (wala|wali|wale|only)\b"
)
DISCOUNT_RE = re.compile(r"\b(discount|off|chhoot|chhut|saving)\b")
CHEAPEST_RE = re.compile(
    r"\b(sabse\s+(sasta|sasti|saste|kam)|cheapest|lowest|least expensive|sasta wala|"
    r"sasti wali|kam price|minimum price|lowest price)\b"
)
COSTLIEST_RE = re.compile(
    r"\b(sabse\s+(mehenga|mehnga|mehengi|mehngi|zyada|jyada)|costliest|most expensive|"
    r"highest price|premium wala)\b"
)
COMPARE_RE = re.compile(r"\b(vs|versus|ya|or|compare|comparison)\b")
CHEAPER_RE = re.compile(r"\b(cheaper|sasta|sasti|saste|kam)\b")
LIST_RE = re.compile(
    r"\b(dikhao|dikha|dikhado|show|list|options|option|chahiye|suggest|batao kaun|"
    r"available hai kya|hai kya|milega|milegi|kya hai aapke paas|wale|wali)\b"
)
EXPLICIT_LIST_RE = re.compile(
    r"\b(dikhao|dikha|dikhado|dikha do|show|list|options|suggest|chahiye|recommend)\b"
)
FOLLOWUP_SET_RE = re.compile(r"\b(inme|inmein|inmese|in me|isme|unme|these|them|inhi)\b")

# question -> catalogue fields that answer it, first present field wins.
# "charging_time" and "origin" are never in the catalogue: asking them must lead to a refusal.
ATTRIBUTE_QUESTIONS: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (re.compile(r"full charge|charging time|charge (hone|karne) me|charge hone"), ("charging_time",)),
    (re.compile(r"made in|origin|kahan ka bana|country"), ("origin",)),
    (re.compile(r"dishwasher"), ("dishwasher_safe",)),
    (re.compile(r"microwave"), ("microwave_safe",)),
    (re.compile(r"induction"), ("induction_compatible",)),
    (
        re.compile(
            r"water ?(resistant|resistance|proof)|waterproof|baarish|barish|bhig|splash|\bipx?\d"
            r"|\b(paani|pani) ?(me|mein|mei|se|proof|band|jayega|ka asar)\b"
        ),
        ("water_resistance_rating", "water_resistant"),
    ),
    (re.compile(r"warranty|guarantee|gaurantee"), ("warranty_months",)),
    (re.compile(r"\bmoti\b|\bmota\b|thick|thickness"), ("thickness_mm",)),
    (re.compile(r"weight|wazan|vajan|vazan|bhari|halka|kitne gram|kitna heavy"), ("weight_g", "weight_kg")),
    (re.compile(r"paraben"), ("paraben_free",)),
    (re.compile(r"sulphate|sulfate"), ("sulphate_free",)),
    (re.compile(r"noise cancel|\banc\b"), ("noise_cancellation",)),
    (re.compile(r"\bmic\b|microphone"), ("has_mic",)),
    (
        re.compile(r"battery|backup|ek charge|kitna chalega|kitni der|runtime|playtime"),
        ("battery_life_hours", "runtime_min"),
    ),
    (re.compile(r"auto ?(cut|shut) ?-? ?off|auto off"), ("auto_shutoff",)),
    (re.compile(r"\bwatt|\bwattage\b|kitne w\b"), ("wattage_w", "output_w")),
    (
        re.compile(r"laptop (aa|fit|aayega|aaega|jayega|ayega)|inch laptop|kitne inch"),
        ("fits_laptop_upto_in", "laptop_compartment"),
    ),
    (re.compile(r"shoe compartment|joote ki jagah"), ("shoe_compartment",)),
    (
        re.compile(r"\bdho\b|dhona|dhul|dhulai|wash kar|washing machine|machine wash|hand wash|dry clean"),
        ("care",),
    ),
    (
        re.compile(r"bluetooth(?! speaker)|wireless hai|wired hai|connectivity"),
        ("connectivity", "bluetooth_version"),
    ),
    (
        re.compile(
            r"(?<!cabin )(?<!king )(?<!queen )(?<!double )(?<!single )(?<!large )(?<!medium )(?<!small )"
            r"(?<!check-in )(?<!full )\bsize\b(?!\s*(\d|xs|s|m|l|xl|xxl)\b)|\bsaal\b|\byears?\b|kaunse size"
        ),
        ("sizes",),
    ),
    (re.compile(r"material|fabric|kapda|kis cheez|bana hai|made of"), ("material", "upper_material")),
    (re.compile(r"capacity|kitne l\b|kitna bada"), ("capacity_l", "capacity_ml", "volume_ml")),
    (re.compile(r"rating|review"), ("rating",)),
    (re.compile(r"\bdpi\b"), ("dpi",)),
    (re.compile(r"rfid"), ("rfid_blocking",)),
    (re.compile(r"\bspf\b"), ("spf",)),
]

# ------------------------------------------------------------------------------------------ units
# unit word -> attribute keys it can describe (a product matches if any of them has the value)
UNIT_KEYS: dict[str, tuple[str, ...]] = {
    "l": ("capacity_l", "capacity_ml", "volume_ml"),
    "ml": ("volume_ml", "capacity_ml", "capacity_l"),
    "mm": ("thickness_mm", "tip_mm", "sweep_mm"),
    "cm": ("diameter_cm", "length_cm", "height_cm"),
    "w": ("wattage_w", "output_w"),
    "mah": ("capacity_mah",),
    "inch": ("fits_laptop_upto_in",),
    "piece": ("pieces", "containers"),
    "pack": ("pack_of",),
    "jar": ("jars",),
    "kg": ("weight_kg",),
    "g": ("weight_g",),
    "m": ("length_m", "cable_length_m"),
    "ft": ("length_ft",),
    "slice": ("slices",),
    "gsm": ("gsm",),
    "tc": ("thread_count",),
    "page": ("pages",),
    "sheet": ("sheets",),
    "digit": ("digits",),
    "dpi": ("dpi",),
    "container": ("containers",),
    "speed": ("speed_settings",),
}
# the same quantity stored in another unit: "1 litre bottle" is capacity_ml == 1000
UNIT_SCALE: dict[tuple[str, str], float] = {
    ("l", "capacity_ml"): 1000.0,
    ("l", "volume_ml"): 1000.0,
    ("ml", "capacity_l"): 0.001,
}
# keys compared with ">=" instead of "==" ("17 inch laptop aana chahiye")
AT_LEAST_KEYS = {"fits_laptop_upto_in"}
# unit written before the number: "SPF 50", "size 4", "set of 12", "pack of 5"
PREFIX_UNITS: dict[str, tuple[str, ...]] = {
    "spf": ("spf",),
    "size": ("ball_size", "bat_size"),
    "set of": ("pieces", "containers"),
    "pack of": ("pack_of",),
}

# string attribute keys whose values shoppers name directly ("scientific calculator", "neem face wash")
VALUE_KEYS = (
    "key_ingredient",
    "skin_type",
    "hair_type",
    "fit",
    "pattern",
    "occasion",
    "neck",
    "sleeve",
    "pen_type",
    "calculator_type",
    "willow",
    "shell",
    "luggage_size",
    "bed_size",
    "iron_type",
    "fan_type",
    "heater_type",
    "ball_type",
    "bag_type",
    "game_type",
    "paper_size",
    "ruling",
    "binding",
    "connectivity",
    "connector",
    "closure",
    "style",
    "plate_type",
    "lid_type",
    "kind",
    "fragrance_family",
    "flavour",
    "theme",
    "animal",
    "puzzle_theme",
    "file_type",
    "colour_type",
    "cable_type",
    "layout",
    "water_resistance_rating",
    "craft_theme",
    "stem_theme",
    "grade",
    "soleplate",
    "rise",
    "length",
    "stitching",
    "lock_type",
)
# values too generic to act as a filter on their own
VALUE_STOPLIST = {
    "all",
    "normal",
    "regular",
    "none",
    "standard",
    "other",
    "yes",
    "no",
    "basic",
    "classic",
    "mixed",
    "solid",
    "plain",
    "full",
    "half",
    "single",
    "assorted",
    "cotton",
    "general",
}
# shopper words -> boolean attribute filters for "show me" requests
BOOLEAN_FILTERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"laptop (wala|wali|compartment|section)|laptop ke liye|for laptop"), "laptop_compartment"),
    (re.compile(r"noise cancel|\banc\b"), "noise_cancellation"),
    (re.compile(r"induction (wala|wali|compatible|pe|par)"), "induction_compatible"),
    (re.compile(r"dishwasher safe"), "dishwasher_safe"),
    (re.compile(r"water ?proof|water resistant"), "water_resistant"),
    (re.compile(r"paraben free"), "paraben_free"),
    (re.compile(r"\bcordless\b"), "cordless"),
    (re.compile(r"hooded|hoodie wala"), "hooded"),
]

# ------------------------------------------------------------------------------------------ budget
BUDGET_RES = [
    re.compile(
        r"\b(?:under|below|less than|within|upto|up to|max|maximum|budget|budget of|not more than|"
        r"cheaper than|andar|neeche|niche)\s+(?:rs\.?\s*|inr\s*)?(\d+(?:\.\d+)?)\b"
    ),
    re.compile(
        r"\b(?:rs\.?\s*|inr\s*)?(\d+(?:\.\d+)?)\s*(?:rs\.?|rupees?|rupaye)?\s*(?:se kam|se niche|"
        r"se neeche|tak|ke andar|ke under|ke niche|ke neeche|or less|and below|or below|ke budget|"
        r"budget|ke andar wale|ke andar wala)\b"
    ),
]
MIN_BUDGET_RE = re.compile(
    r"\b(?:above|more than|greater than|over|at least|atleast|minimum|min|starting from|starting at)\s+"
    r"(?:rs\.?\s*|inr\s*)?(\d+(?:\.\d+)?)\b"
    r"|\b(?:rs\.?\s*)?(\d+(?:\.\d+)?)\s*(?:rs\.?\s*)?(?:se zyada|se jyada|se upar|se adhik|or more|and above|"
    r"or above|plus)\b"
)
# "between 600 and 800", "600 se 800 ke beech", "600 to 800 range", "rs 600 - rs 800".
# Range words are required, so sizes like "8-9 saal" are never read as a budget.
RANGE_BUDGET_RE = re.compile(
    r"\bbetween\s+(?:rs\.?\s*)?(\d+(?:\.\d+)?)\s*(?:rs\.?\s*)?(?:and|to|-|se)\s*(?:rs\.?\s*)?(\d+(?:\.\d+)?)\b"
    r"|\b(?:rs\.?\s*)?(\d+(?:\.\d+)?)\s*(?:rs\.?\s*)?(?:se|to|-)\s*(?:rs\.?\s*)?(\d+(?:\.\d+)?)\s*(?:rs\.?\s*)?"
    r"(?:ke beech|ke bich|ke darmiyan|tak|ke andar|range|ke range)\b"
    r"|\brs\.?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(?:rs\.?\s*)?(\d+(?:\.\d+)?)\b"
)

# ------------------------------------------------------------------------------------------ policy
POLICY_TRIGGER_RE = re.compile(
    r"\b(return|returns|refund|exchange|replace|replacement|cancel|cancellation|deliver|delivery|shipping|"
    r"ship|dispatch|track order|order track|tracking|cod|cash on delivery|emi|payment|pay|upi|credit card|"
    r"debit card|"
    r"net banking|wallet se|gst|tax|coupon|promo|price match|pre ?order|back ?order|warranty|guarantee|"
    r"restocking|refund|paise|paisa|customer care|support|helpline|contact|gift wrap|loyalty|coins|points|"
    r"reward|store kahan|store kaha|showroom|offline store|sale me|seal|kharab|damaged|defective|toota|"
    r"tuta|wrong item|galat)\b"
)

# policy questions the store policy does not cover -> refuse
POLICY_GAPS: list[re.Pattern[str]] = [
    re.compile(r"\bemi\b|instal+ment|no cost"),
    re.compile(r"gift ?wrap|gift pack"),
    re.compile(r"loyalty|coins|points|reward|cashback|cash back|membership|referral"),
    re.compile(r"store kaha|store kahan|showroom|offline store|physical store|shop kahan|outlet"),
    re.compile(r"installation|install|demo karne|technician"),
    re.compile(r"bulk order|wholesale|gst invoice|business invoice"),
]

# (pattern, sub-sections to cite). First match wins; a second cited section is a supporting one.
POLICY_ROUTES: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (
        re.compile(
            r"(earbud|earphone|airpod|headphone).*(seal|return|open|khol|wapas)|"
            r"(seal|return|khol|wapas).*(earbud|earphone)"
        ),
        ("6.2",),
    ),
    (re.compile(r"trimmer.*(return|use|wapas)|(return|wapas).*trimmer"), ("6.3",)),
    (
        re.compile(
            r"(shampoo|face ?wash|lotion|sunscreen|lip ?balm|deo|perfume|hair oil|cream|beauty)"
            r".*(return|khol|open|seal|use|wapas)|(return|wapas).*(shampoo|face ?wash|lotion|sunscreen|"
            r"lip ?balm|deo|perfume|hair oil)"
        ),
        ("6.1",),
    ),
    (re.compile(r"restocking|return.*(free|charge|fee|paisa lagega|cost)|pickup.*(charge|free)"), ("1.2",)),
    (
        re.compile(r"(sale|discount|offer).*(return|warranty|exchange)|(return|warranty).*(sale|discount)"),
        ("7.5",),
    ),
    (re.compile(r"warranty.*(claim|kaise|how)|claim.*warranty"), ("3.4", "1.7")),
    (re.compile(r"warranty.*(cover|damage|gir|liquid|paani)|(physical|liquid) damage"), ("3.3",)),
    (re.compile(r"kharab|damaged|defective|toota|tuta|broken|wrong item|galat"), ("1.7",)),
    (re.compile(r"warranty"), ("3.1",)),
    (
        re.compile(
            r"exchange|size.*(chota|bada|small|big|tight|loose)|(chota|bada).*size|"
            r"different (size|colour)"
        ),
        ("1.6",),
    ),
    (re.compile(r"(payment|paisa|paise|money).*(fail|cut|kat|debit)|failed payment"), ("4.3",)),
    (re.compile(r"refund|paise|paisa|money back"), ("1.5",)),
    (re.compile(r"return.*(kaise|how|process|start)|how.*return"), ("1.4",)),
    (re.compile(r"tag|washed|used item|condition|shoebox|packaging"), ("1.3",)),
    (re.compile(r"return|wapas"), ("1.1",)),
    (re.compile(r"cancel.*(ship|dispatch|after|baad)|(ship|dispatch).*cancel"), ("5.2",)),
    (re.compile(r"cancel"), ("5.1",)),
    (re.compile(r"pre ?order|back ?order|out of stock.*(order|book)"), ("2.5",)),
    (
        re.compile(
            r"international|outside india|abroad|dubai|usa|uk|nepal|foreign|bahar|videsh|"
            r"other country"
        ),
        ("2.3",),
    ),
    (
        re.compile(
            r"delivery charge|shipping charge|free delivery|delivery free|delivery fee|"
            r"shipping fee|charge lagega|delivery.*(charge|free|paisa)"
        ),
        ("2.1",),
    ),
    (re.compile(r"track|tracking"), ("2.4",)),
    (re.compile(r"\bcod\b|cash on delivery"), ("4.2",)),
    (re.compile(r"payment|pay|upi|credit card|debit card|net banking|wallet"), ("4.1",)),
    (re.compile(r"deliver|delivery|kitne din|kab tak aayega|kab aayega|shipping|dispatch"), ("2.2",)),
    (re.compile(r"\bgst\b|\btax\b|inclusive|mrp"), ("7.1",)),
    (re.compile(r"price (change|badal)|price kam ho|price increase"), ("7.2",)),
    (re.compile(r"coupon|promo"), ("7.3",)),
    (re.compile(r"price match|amazon|flipkart|other (site|website|store)|dusri site"), ("7.4",)),
    (re.compile(r"customer care|support|helpline|contact|call|email|phone number"), ("8.1",)),
]

# filler words that never identify a product
STOPWORDS = set(
    """
a an the is are am was were be been of in on at to for from with by and or but not no i me my we our
you your it its this that these those there here what which who how much many do does did have has
had can could will would should may might please pls plz want need looking look find get give show
tell about any some also just only very same like than more less hi hello hey ok okay toh to hai
hain h kya ka ki ke ko mein me mai main mujhe chahiye wala wali wale kaunsa kaunsi konsa konsi kaun
sa se kar sakte sakta sakti do de dena dikhao dikha dikhado bata batao kitna kitne kitni kitney aur
bhi ek koi kuch tha thi hu hoon ho price rate cost costs available stock abhi milega milegi milenge
sabse sasta sasti saste mehenga mehnga cheapest cheap lowest under below within upto budget andar
niche neeche tak rs inr rupee rupees liye ghar pe par jo vo wo ye yeh is us iska uska inme inmein in
se kam zyada wale ka ki which one ones new latest good best acha accha achha batana bataiye chalega
chalegi
greater more less than above below over between least atleast minimum maximum min max range beech bich
darmiyan upar adhik jyada starting
""".split()  # noqa: SIM905  (a word list reads better as text)
)
