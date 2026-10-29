# R3 — The Conversational Shopping Assistant That Doesn't Lie

**Saffron Retail Group** (a fictional Indian omnichannel retailer) wants a chat assistant on its online store, saffronretail.example. Retailers everywhere are rushing to put chatbots on their catalogues. Most of those bots confidently invent products, prices and return policies. A hallucinated price (a price the bot made up) is a legal and trust problem, not a cosmetic one.

**Your job:** build a *grounded* product-discovery assistant over a fixed catalogue. "Grounded" means every fact it says comes from the catalogue or the store policy. Your assistant:

1. answers natural shopper questions;
2. refuses when the catalogue doesn't support an answer;
3. cites a product ID or a policy section for every factual claim (this is a must);
4. asks a short question back when a question is ambiguous (more than one product matches and they differ in what was asked), instead of guessing;
5. says "I don't have that." when the store doesn't have something.

> **In short**
>
> - **You get:** a catalogue of 5,000 products, a store policy, 40 dev (practice) questions with their expected behaviour, and 150 test questions. The expected behaviour for the test questions is hidden.
> - **You build:** a chat assistant that uses only the catalogue and policy. For each question it picks one action: `answer`, `clarify` (ask which product they mean) or `refuse`. Every fact it states cites a product ID or policy section.
> - **You submit:** one file, `submission/R3_predictions.jsonl`, inside your team zip `teamID_R3.zip`. It has one line for every test question. You also include all your code and a `README.md` (see **What to submit**).
> - **How you're scored:** each test question earns up to 1.0 for the right action, a grounded answer and a helpful answer. Your primary score is the mean over the 150 test questions.
> - **Main special rule:** never invent a price. Each wrong or made-up price takes **3** off (−3) that question's score.
> - **Also show in your demo:** a working chat interface and a latency (response time) and token-cost report per query (see sections 7 and 10).

---

## 1. Synthetic data notice

Everything in this folder is **synthetic** (made up by a computer program). Saffron Retail Group, every brand (Runvex, Kitchora, Zentrix, Glowveda, …), every product, price, rating and policy is invented for the TalentAP Mega Hackathon 2026. The data contains no real customers and no real personal data. Any real-world brand or product name you see appears only inside shopper questions.

---

## 2. What's in the box

| File | Rows | What it is |
|---|---|---|
| `data/catalogue.csv` | 5,000 | The full product catalogue. This is the **single source of truth**. The `attributes` column is a JSON string (JSON text stored in one cell). |
| `data/catalogue.jsonl` | 5,000 | The same catalogue in JSONL format (one JSON object per line). Here `attributes` is a nested object. |
| `data/policy.md` | 8 sections / 30 sub-sections | Store policy: returns, shipping, warranty, payments/COD (cash on delivery), cancellations, non-returnable items, prices & offers, support. Cite it by sub-section number, e.g. `1.2`. |
| `data/questions_dev.csv` | 40 | Practice questions. They include 2 multi-turn conversations (conversations with more than one question). |
| `data/questions_dev_truth.jsonl` | 40 | Expected behaviour + reference answers for the 40 dev questions. |
| `data/questions_test.csv` | 150 | **The scored questions.** Their expected behaviour is hidden. They include 8 multi-turn conversations (21 turns). |
| `sample_submission.jsonl` | 150 | A *valid* submission for the test questions. It is useless (it refuses everything), but it shows the exact format. |
| `evaluate.py` | — | The official scorer. The organisers run this same file with the hidden test answers. |
| `baseline/baseline.py` | — | A simple starting solution: keyword retrieval (finding products by matching words) + rules. It writes a valid submission. |
| `MODELS.md`, `download_models.py` | — | Recommended small, open-licence models: an embedding model (turns text into numbers for search) and an instruct model (a small chat AI model). The script caches (saves) them for offline use. |

Product categories (5,000 products): Apparel 900, Home & Kitchen 650, Footwear 550, Beauty & Personal Care 550, Electronics Accessories 450, Sports & Fitness 450, Bags & Luggage 400, Small Appliances 350, Toys & Games 350, Stationery & Office 350.

The store does **not** sell phones, laptops, TVs, groceries, medicines, jewellery or vehicles.

---

## 3. Data dictionary

### 3.1 `catalogue.csv` / `catalogue.jsonl`

| Column | Type | Description | Example | Can be missing? |
|---|---|---|---|---|
| `product_id` | string | Unique product ID. Cite this. | `SKU-002OFXUN` | No |
| `title` | string | Product title (brand + product line + type + variant). | `Threadcraft TerraDash Boys' Cotton T-Shirt and Shorts Set - Green` | No |
| `brand` | string | Fictional brand. | `Threadcraft` | No |
| `category` | string | One of the 10 categories above. | `Apparel` | No |
| `sub_category` | string | 91 sub-categories, e.g. `Running Shoes`, `Mixer Grinders`. | `Kids Wear` | No |
| `description` | string | 2–4 sentences of marketing copy. It never contradicts `attributes`, but it does not repeat all of them. | `A striped t-shirt and shorts set from Threadcraft TerraDash. ...` | No |
| `attributes` | JSON object | Structured facts (see 3.2). **If a key is absent, the catalogue does not know that fact.** | `{"gender": "boys", "material": "cotton", ...}` | Keys vary by product |
| `price_inr` | integer | **Selling price** in ₹, inclusive of GST (goods and services tax), current as of the snapshot (1 Oct 2026). | `239` | No |
| `mrp_inr` | integer | MRP (maximum retail price) in ₹. It is always ≥ `price_inr`. Discount = MRP − price. | `349` | No |
| `stock_status` | string | `in_stock`, `low_stock` (only a few left) or `out_of_stock` (cannot be ordered). | `in_stock` | No |
| `rating` | float | Average rating, 1.0–5.0, one decimal. | `3.9` | **Yes**: empty / `null` when `review_count` is 0 |
| `review_count` | integer | Number of reviews. | `63` | No |

### 3.2 Attribute keys (inside `attributes`)

Not every product has every key that is relevant to its sub-category. A missing key means **unknown**. It does not mean "no".

| Key(s) | Meaning | Example values |
|---|---|---|
| `colour` | Colour of this product (each colour is a separate product) | `blue`, `navy`, `charcoal`, `assorted` |
| `gender` | Intended wearer | `men`, `women`, `unisex`, `boys`, `girls`, `kids` |
| `sizes` | **List** of sizes this product is sold in | `["S","M","L","XL","XXL"]`, `["UK 6", … "UK 11"]`, `["28","30",…]`, `["2-3Y",…]` |
| `material`, `upper_material`, `sole_material`, `blade_material`, `handle_material`, `plate_material` | Materials | `cotton`, `stainless steel`, `mesh`, `EVA`, `TPE` |
| `fit`, `neck`, `sleeve`, `pattern`, `occasion`, `rise`, `length`, `care`, `saree_length_m`, `blouse_piece`, `hooded`, `zip_pockets` | Apparel details | `slim`, `round neck`, `3/4 sleeve`, `printed`, `festive`, `dry clean only` |
| `closure`, `style`, `embroidered`, `weight_g` | Footwear details | `lace-up`, `kolhapuri`, `240` |
| `water_resistant` | Explicit water-resistance claim (true/false) | `true` |
| `water_resistance_rating` | IP rating of electronics (a standard code for how water-resistant a device is) | `IPX4`, `IPX7` |
| `capacity_l`, `capacity_ml`, `volume_ml`, `capacity_mah` | Capacities | `3`, `750`, `100`, `20000` |
| `diameter_cm`, `thickness_mm`, `length_m`, `length_cm`, `length_ft`, `cable_length_m`, `height_cm`, `sweep_mm`, `fits_laptop_upto_in` | Dimensions | `24`, `6`, `1.5`, `15.6` |
| `induction_compatible`, `dishwasher_safe`, `microwave_safe`, `bpa_free`, `insulated`, `leak_proof`, `airtight`, `lid_included`, `lid_type` | Kitchen details | `true`, `outer lid` |
| `pieces`, `containers`, `pack_of`, `pillow_covers`, `thread_count`, `gsm`, `bed_size`, `blackout` | Sets, counts and textiles | `24`, `2`, `210`, `king` |
| `wattage_w`, `output_w`, `jars`, `speed_settings`, `heat_settings`, `browning_levels`, `preset_menus`, `slices`, `max_temp_c`, `auto_shutoff`, `overload_protection`, `overheat_protection`, `oscillation`, `iron_type`, `fan_type`, `heater_type`, `plate_type`, `soleplate`, `foldable` | Appliance details | `750`, `3`, `steam`, `pedestal` |
| `warranty_months` | Brand warranty in months (see policy 3.1) | `12`, `24` |
| `battery_life_hours`, `runtime_min`, `bluetooth_version`, `noise_cancellation`, `has_mic`, `connectivity`, `connector`, `cable_type`, `ports`, `cable_included`, `braided`, `dpi`, `layout`, `backlit`, `adjustable`, `charging_port`, `cordless`, `washable`, `length_settings` | Electronics / device details | `40`, `5.3`, `bluetooth`, `USB-C` |
| `key_ingredient`, `skin_type`, `hair_type`, `spf`, `pa_rating`, `paraben_free`, `sulphate_free`, `non_sticky`, `flavour`, `fragrance_family`, `kind` | Beauty & personal care | `neem`, `oily`, `50`, `PA+++` |
| `weight_kg`, `willow`, `ball_type`, `bat_size`, `ball_size`, `stitching`, `strung`, `anti_slip`, `carry_strap`, `ball_bearing`, `resistance_levels`, `wrist_support` | Sports | `English`, `tennis ball`, `5` |
| `laptop_compartment`, `compartments`, `shell`, `luggage_size`, `wheels`, `lock_type`, `shoe_compartment`, `bag_type`, `card_slots`, `rfid_blocking`, `rain_cover` | Bags & luggage | `true`, `cabin`, `8` |
| `age_group`, `theme`, `animal`, `scale`, `rechargeable`, `range_m`, `players`, `game_type`, `puzzle_theme`, `craft_theme`, `stem_theme`, `battery_required`, `non_toxic` | Toys | `8+ years`, `1:16`, `2-4` |
| `ruling`, `paper_size`, `binding`, `pages`, `pen_type`, `ink_colour`, `tip_mm`, `grade`, `eraser_tip`, `file_type`, `sheets`, `colour_type`, `calculator_type`, `digits`, `power` | Stationery | `ruled`, `A4`, `gel`, `0.5`, `scientific` |

### 3.3 `questions_dev.csv` / `questions_test.csv`

| Column | Type | Description | Example |
|---|---|---|---|
| `question_id` | string | Unique question ID. You must return it. | `Q-YZLP9KRR` |
| `conversation_id` | string | Questions with the same ID are turns of one conversation. Most conversations have a single turn. | `C-7VPQ1NOY` |
| `turn` | integer | 1, 2, 3 … within a conversation. Later turns depend on earlier ones (e.g. "2000 ke andar wale?"). | `1` |
| `question_text` | string | What the shopper typed. It is short, often ungrammatical, often misspelt, and often in Hinglish (Hindi words written in English letters, mixed with English). | `Chargit QuillBolt red earphones kitne ke` |

### 3.4 `questions_dev_truth.jsonl` (same keys as the hidden test answers)

| Key | Description |
|---|---|
| `question_id`, `conversation_id`, `turn`, `question_text` | As above. |
| `expected_action` | `answer`, `clarify` or `refuse` (see section 6). |
| `question_type` | `answer_lookup`, `answer_attribute`, `answer_superlative`, `answer_filter`, `answer_compare`, `answer_policy`, `clarify_ambiguous`, `refuse_out_of_catalogue`, `refuse_unanswerable`, `refuse_policy_gap`. This is for your own analysis. You don't predict it. |
| `acceptable_product_ids` | For `answer`: citing **any** of these counts as finding the right product. For a "show me options" question, every matching product is listed. |
| `required_facts` | List of `{product_id, field, value}` that a complete answer must state (e.g. the price, the stock status, `dishwasher_safe: false`). |
| `clarify_candidate_ids` | For `clarify`: all catalogue products that match the shopper's under-specified (not specific enough) request. |
| `policy_sections` | For policy questions: the sub-section(s) that must be cited. `"7.5\|1.1"` means either section is fully correct. |
| `notes`, `reference_answer` | A human-readable explanation and a reference answer. These are not used for scoring. |

### 3.5 `policy.md`

Plain Markdown. It has `## N. Title` sections and `### N.M Title` sub-sections.

- Cite sub-sections as strings like `"1.1"`.
- Section `"1"` alone is valid, but it earns only half credit when `"1.1"` was needed.

---

## 4. Know your data (honest warnings)

- **Shoppers type badly.** Questions are short and code-mixed (English and Hinglish mixed together), with typos. Brand and product-line names are often split or misspelt (`"ironnest ripple flex"` for *Ironnest RippleFlex*, `"krida"` for *Kridaa*). Exact keyword matching will miss many of them.
- **Near-duplicates are deliberate.** One product line usually has several colours, sizes or capacities. **Each variant is a separate product with its own price and stock.** A few products even share an *identical title* and differ only inside `attributes` (for example colour or `pack_of`).
- **Many products match a vague request.** "green running shoes" matches several products at different prices.
- **Missing ≠ false.** If `water_resistant` is absent, the catalogue doesn't say. If it is `false`, the catalogue says "no".
    - **One exception, defined by the policy:** if `warranty_months` is absent, policy 3.1 says the product has **no brand warranty**. That is a grounded answer, so cite 3.1.
- **Colours, materials and sub-categories match exactly.**
    - `navy`, `teal` and `blue` are different colours ("blue" means `colour: blue`).
    - "cotton" means `material: cotton`, not `cotton blend`.
    - "earbuds" (Wireless Earbuds) are not "earphones" (Wired Earphones).
- **Descriptions are marketing copy.** They never contradict the attributes. But they may mention activities or items that are not themselves sold (a kettle "for instant noodles" does not mean noodles are sold).
- Some products are **out of stock** or **low stock**. Many are discounted (`price_inr < mrp_inr`). The price you quote must be `price_inr`.
- `rating` is empty when there are no reviews.
- Questions include things the store does not sell, real brands it does not carry, and policy topics the policy doesn't cover.
- Most of the time the answer is in the structured columns. Use the description only as supporting text.

---

## 5. Dev / test split

- There is no time axis.
- The 40 dev questions come with full expected behaviour, so you can practise and debug.
- The 150 test questions are scored against hidden answers.
- Dev and test questions about specific products target **different** product lines.
- Generic category questions (e.g. "black yoga mat") naturally touch overlapping parts of the catalogue.
- Both sets mix single-turn questions with multi-turn conversations (dev: 2 conversations, test: 8 conversations of 2–3 turns).

Approximate test mix:

| Kind of question | Share of test |
|---|---|
| Answerable product questions | ≈ 45% |
| Ambiguous/trap (clarify) | ≈ 20% |
| Out-of-catalogue (refuse) | ≈ 15% |
| Unanswerable-from-catalogue (refuse) | ≈ 8% |
| Policy (a few of which the policy does not cover → refuse) | ≈ 12% |

---

## 6. Expected behaviour — the three actions

For every question, your assistant picks exactly one action: `answer`, `clarify` or `refuse`.

### 6.1 `answer`

**When:** the catalogue/policy contains the answer. This includes:

- grounded "no" answers ("is it induction compatible?" → catalogue says `false`);
- "show me options" requests;
- cheapest/most-expensive questions;
- comparisons.

**Example (dev):** "yatrik vega dash brown duffel me shoe compartment hai?" → "Yes (`shoe_compartment: true`) [SKU-…]"

### 6.2 `clarify` (ask which product they mean)

**When:** all three of these are true:

1. the shopper refers to **one** product (asks *its* price, stock, …);
2. **two or more** catalogue products match;
3. **and they differ in what was asked**.

Then ask which one they mean. If all matches share the same answer, just `answer`.

Listing the options with their prices/stock is a great clarification, but the action is still `clarify`. (An `answer` that lists ≥ 2 of the matching products with correct prices gets half the action credit.)

**Examples (dev):**

- "green running shoes kitne ke hai" (8 matches, different prices);
- "Sanchayo NimbusMax steel container set stock me hai?" (one variant in stock, one out of stock).

### 6.3 `refuse`

**When:** either of these is true:

- the store has **no matching product** (out of catalogue, e.g. "redmi note 13 price", or nothing satisfies the constraints);
- the catalogue/policy **does not contain** the requested information (attribute absent, policy silent).

You are allowed to suggest real alternatives while refusing, as long as every claim is grounded.

**Example (dev):** "Trailnest DriftAir pink running shoe water resistant hai?" when `water_resistant` is absent → "The catalogue doesn't say."

### 6.4 Multi-turn conversations

Interpret each turn using the earlier turns of the same `conversation_id`. Budget, material and colour constraints carry over.

---

## 7. What to submit

### 7.1 Where the file goes

Inside your team zip, the file must be at this path:

```
teamID_R3.zip                  a zip of your project (a fresh git clone)
├── README.md                  how to set up and run your code
├── submission/
│   └── R3_predictions.jsonl
└── FULL_CODE/                 This folder should contain all of your code:
                               your demo app + the code that created the
                               submission/ files
```

**Your code is required too.** Every team submits one zip of its whole project, as the *Participant Coding Guidelines* explain (zip a fresh `git clone` of your project). The zip holds **all** your code, not only the code that makes your submission files: also the code of the solution you demo (for example a web or mobile app, dashboard, API, command-line tool or notebook). It also holds your own `README.md` that explains how to set up and run everything. It is fine if everything sits inside one project folder in the zip.

- Write your **own** `README.md`. The *Participant Coding Guidelines* (rule 12) list what it must cover. If you built inside this pack's folder, replace this pack's README with yours (rename this one to `PACK_README.md` if you want to keep it).
- Put **all** your code inside a folder named exactly `FULL_CODE/`, at the top of your project: your demo app + the code that created the `submission/` files. At the top of your project, keep only `README.md`, `submission/`, `FULL_CODE/` and your `.gitignore` (plus a `LICENSE` file if you have one).
- Put `submission/` at the top of your project, next to your `README.md`.
- Commit the files in `submission/` to git. Make sure your `.gitignore` does not exclude them (for example with `*.csv` or `*.jsonl`).
- Before you commit, list `data/`, `models/`, `.env`, `.venv/` and `node_modules/` in your `.gitignore`. This keeps the pack's data files and downloaded models out of your zip. Your README should say where to put the data and how to get any models.

`R3_predictions.jsonl` is a JSONL file: one JSON object per line, one line for **every** test question.

### 7.2 Keys on each line

| Key | Type | Required? | Meaning |
|---|---|---|---|
| `question_id` | string | **Required** | From `questions_test.csv`. |
| `action` | string | **Required** | `answer`, `clarify` or `refuse`. |
| `answer_text` | string | **Required** | What your assistant says to the shopper. |
| `cited_product_ids` | list of strings | **Required** | Product IDs your answer relies on (`[]` if none). |
| `cited_policy_sections` | list of strings | **Required** | Policy sub-sections, e.g. `["1.1"]` (`[]` if none). |
| `stated_prices` | list of `{product_id, price_inr}` | **Required** | Every price you state, as structured data (`[]` if none). Selling price only. |
| `stated_facts` | list of `{product_id, field, value}` | Optional (but see 7.3) | Other facts you state, e.g. `{"product_id": "SKU-…", "field": "stock_status", "value": "out_of_stock"}` or `{"field": "dishwasher_safe", "value": false}`. |
| `latency_ms` | number ≥ 0 | **Required** | Wall-clock time (real time taken) to produce this answer. |
| `tokens_in`, `tokens_out` | integer ≥ 0 | **Required** | LLM (large language model) tokens used (0 if no LLM). |

### 7.3 Rules for `stated_facts`

1. `evaluate.py` accepts a line without `stated_facts`. But you need it to earn credit for non-price facts.
2. `field` must be **exactly** a catalogue column or attribute key (e.g. `water_resistant`, not `waterproof`).
3. `discount_inr` (= MRP − price) is also accepted.
4. Price-like names (`price`, `selling_price`, …) are treated as `price_inr`.
5. Entries whose value is `null` or "unknown" are ignored.
6. For list attributes like `sizes`, state one size (`"8-9Y"`) or the full list.

### 7.4 Example lines

```json
{"question_id": "Q-YZLP9KRR", "action": "answer", "answer_text": "Chargit QuillBolt Wired Earphones USB-C - Red (SKU-LIF2LAV2) is ₹249 and in stock.", "cited_product_ids": ["SKU-LIF2LAV2"], "cited_policy_sections": [], "stated_prices": [{"product_id": "SKU-LIF2LAV2", "price_inr": 249}], "stated_facts": [{"product_id": "SKU-LIF2LAV2", "field": "stock_status", "value": "in_stock"}], "latency_ms": 412.5, "tokens_in": 950, "tokens_out": 60}
{"question_id": "Q-YYYYYYYY", "action": "refuse", "answer_text": "Sorry, we don't sell phones.", "cited_product_ids": [], "cited_policy_sections": [], "stated_prices": [], "stated_facts": [], "latency_ms": 35, "tokens_in": 0, "tokens_out": 0}
```

### 7.5 Checklist before you submit

1. The file is `submission/R3_predictions.jsonl` inside `teamID_R3.zip`.
2. There is one line for every test question in `questions_test.csv`. Missing question IDs score 0 and are reported. Extra question IDs are ignored.
3. Every line has all the required keys from the table in 7.2.
4. Every price in `stated_prices` is the selling price (`price_inr`), and every product whose price or MRP you mention is in `cited_product_ids`.
5. Format errors make `evaluate.py` exit with code 2 and a message that tells you what to fix. So it is a good idea (not required) to first run `evaluate.py` on a dev file made by the same code.

### 7.6 Latency and token-cost report

The PS (problem statement) asks for one. `evaluate.py` prints mean/p95 latency and token counts from your file. (p95 latency = about 95% of your answers were at least this fast.) In your demo, explain the latency and cost per query of your design.

---

## 8. How you're scored

The `evaluate.py` score is **20% of the judging rubric**. The other criteria are Problem framing 20%, Technical soundness 25%, Real-world usability 15%, Responsibility 15% and Demo 5%.

### 8.1 The formula

For every test question:

```
question_score = action_correct × (0.4 + 0.3 × grounded + 0.3 × helpful) − 3 × hallucinated_prices
primary_score  = mean(question_score) over the 150 test questions        (best 1.0; can be negative)
```

**In words:** if your action is right, you get 0.4, plus up to 0.3 for a grounded answer and up to 0.3 for a helpful one. Then every hallucinated price subtracts 3. A perfect question scores 1.0. One made-up price makes that question negative.

### 8.2 The four parts

**action_correct** (0/1)

- Your `action` equals the expected action.
- If the action is wrong, the question earns 0 (penalties still apply).
- One exception: a `clarify` was expected, and you `answer` while citing and pricing at least 2 of the matching products (correctly, in `stated_prices`). Then action_correct = 0.5.

**grounded** (0/1): every claim is supported **and relevant**. All of these must be true:

1. An `answer` or `clarify` cites at least one product or policy section that the question actually needed (one that earns helpfulness). Irrelevant or missing citations are not grounded.
2. All cited product IDs and policy sections exist. Write sections as `"1.2"`, `"§1.2"`, `"Section 1.2"` or `"1.2 Return window"`, one per list item.
3. No hallucinated price.
4. Every `stated_facts` entry:
    - is about a **cited** product;
    - uses a field that product actually has;
    - has the catalogue value. The check is case-insensitive (capital and small letters are treated the same). `true/false/yes/no` are accepted for booleans. `rating` has a tolerance of ±0.05.

**helpful** (0–1), scored per expected action.

- An empty `answer_text` earns no helpfulness for answer/clarify.
- Citing more than **10** products earns no product, fact or clarify credit (don't spam citations).
- For `answer`: the mean of these components:
    - *product credit* = `hit × (0.5 + 0.5 × precision)`. Here `hit` = you cited at least one acceptable product, and `precision` = the fraction of your cited products that are acceptable. In words: citing a right product earns at least 0.5, and citing only right products earns 1.0.
    - one component per *required fact*: 1 if you stated it for that product and you cited that product. Prices can be stated via `stated_prices` or `stated_facts`; other facts only via `stated_facts`. For a "kitna discount" question (price + MRP required), a correct `discount_inr` fact satisfies both.
    - *policy credit* for policy questions: 1 per required sub-section cited (0.5 if you cited only its parent section; `"a|b"` means either is fine), averaged. If you cite more than (required + 1) sections, the credit is multiplied by (required + 1) / (number cited). In words: one extra section is free; each further section lowers the credit.
- For `clarify`: you must cite **at least 2** of the matching candidate products. Then credit = `0.5 + 0.5 × precision`. Otherwise it is 0.
- For `refuse`: 1.

**hallucinated_prices** (count, **−3 each**). Each of these counts as one hallucinated price:

1. A `stated_prices` entry (or a price-like stated fact: any field whose name contains price / mrp / cost / rate / amount / discount) where:
    - the product doesn't exist, or
    - the product isn't in `cited_product_ids`, or
    - the value differs from the catalogue by more than ₹0.5.
2. Any rupee amount written in `answer_text` that is **not** one of these:
    - the price, MRP or MRP−price of a product you cited;
    - a ₹ amount in `policy.md` (only if you cite a policy section);
    - a budget number the shopper typed in the same conversation (measurements like "65W" or "17 inch" don't count).

What counts as a rupee amount:

- A number with ₹, ₨, Rs, Rs., Rs:, INR, rupees, rupaye or `/-`, e.g. "₹1,299", "Rs.499", "2k rupees", "1299/-".
- "k" means thousand only when it is attached to the number ("2k", "1.2k"). "₹449 k andar" is ₹449.
- Text is Unicode-normalised first (converted to standard characters), so Devanagari or full-width digits are caught too.

So never write a price you didn't take from the catalogue. Always cite the product whose price you mention. Sums or per-unit maths in rupees will be flagged, so avoid them.

### 8.3 Other numbers in the report

`evaluate.py` also reports:

- action accuracy;
- refusal precision/recall/F1 and clarify precision/recall/F1:
    - precision = the share of your refusals (or clarifications) that were expected;
    - recall = the share of expected refusals (or clarifications) that you made;
    - F1 combines the two;
- grounded rate, helpfulness and the hallucinated-price count;
- the score per question type;
- latency (mean/p50/p95) and tokens.

### 8.4 Constants and reference points

Constants (top of `evaluate.py`): `W_ACTION=0.4`, `W_GROUNDED=0.3`, `W_HELPFUL=0.3`, `HALLUCINATED_PRICE_PENALTY=3.0`, `PRECISION_FLOOR=0.5`, `MIN_CLARIFY_CANDIDATES=2`, `CLARIFY_AS_ANSWER_CREDIT=0.5`, `MAX_CITED_PRODUCTS=10`, `PARENT_SECTION_CREDIT=0.5`, `FREE_EXTRA_POLICY_CITATIONS=1`, `PRICE_TOLERANCE=0.5`, `RATING_TOLERANCE=0.05`.

Reference points on the test set:

- refusing everything (`sample_submission.jsonl`) ≈ 0.25;
- the shipped baseline ≈ 0.64;
- a perfect system = 1.0.

---

## 9. Hour Zero quick start

Run these from this folder, with Python ≥ 3.9 and `pandas` + `numpy` installed. On Mac/Linux, type `python3` instead of `python`.

Copy and run the three commands one at a time:

```
python baseline/baseline.py --questions data/questions_dev.csv --out submission/R3_dev_predictions.jsonl
python evaluate.py --submission submission/R3_dev_predictions.jsonl --truth data/questions_dev_truth.jsonl --out dev_score.json --details
python baseline/baseline.py --questions data/questions_test.csv --out submission/R3_predictions.jsonl
```

What each command does:

1. **Command 1** runs the baseline on the 40 dev questions. It writes the practice file `submission/R3_dev_predictions.jsonl`.
2. **Command 2** scores that practice file against `questions_dev_truth.jsonl` and prints the score.
    - Find the line `PRIMARY SCORE`. For the baseline it is **about 0.73 on dev**. If you see this, your setup works.
    - The full report is saved in `dev_score.json`. To read it later, run `python -m json.tool dev_score.json`.
    - `--details` also writes `score_details.jsonl`, which explains every dev question (what was wrong, which fact was missing).
3. **Command 3** runs the baseline on the 150 test questions. It writes `submission/R3_predictions.jsonl`. **This is your test submission file: the file you submit.** You cannot score it yourself, because the test answers are hidden. On test, the baseline scores ≈ 0.64 (see section 8.4).

Optional, while you have internet: run `python download_models.py` to cache the recommended models (see `MODELS.md`).

---

## 10. Assumptions you may make (from the problem statement)

- The catalogue is the single source of truth. Nothing outside it may be asserted.
- Prices and stock are current as of the snapshot (1 October 2026).
- No user account, order history or payment integration exists.
- Shoppers write short, ungrammatical, code-mixed queries.

**Desired output:**

1. a working chat interface (notebook, CLI or simple web page; all score equally);
2. every factual claim carries a citation to a product ID or policy section;
3. an explicit refusal/clarification path;
4. the `evaluate.py` score;
5. a latency and token-cost report per query.

**Stretch:** a multi-turn budget constraint ("under ₹2,000, and I already said I want cotton").

---

## 11. Licence

Synthetic data generated for the TalentAP Mega Hackathon 2026. CC BY 4.0. Contains no real personal data.
