# Questions you can ask the Shopping Assistant

Every question below was run through the assistant (rules engine, offline) and behaves as its section describes. Product names are real catalogue items. Product types such as "kettle" or "yoga mat" work for any product of that type.

Type them in the web demo (`uv run python main.py serve`) or the terminal chat (`uv run python main.py chat`).

## ⭐ Top 10 questions to try first

A quick tour of everything the assistant does. Ask them in this order in one chat; the multi-turn one is three messages.

| # | Tag | Question |
|---|---|---|
| 1 | `ANSWER · price` | Chargit QuillBolt red earphones kitne ke |
| 2 | `CLARIFY` | green running shoes kitne ke hai |
| 3 | `ANSWER · feature` | yatrik vega dash brown duffel me shoe compartment hai? |
| 4 | `ANSWER · cheapest` | king size cotton bedsheet sabse sasti jo stock me ho |
| 5 | `ANSWER · compare` | wavefin ripple loop purple ya teal earbuds kaunsa sasta |
| 6 | `POLICY` | earbuds ki seal khol di, return ho jayega? |
| 7 | `MULTI-TURN` | 6 mm yoga mat chahiye → TPE wali 600 ke andar → inme sabse sasti kitne ki hai? |
| 8 | `LLM FALLBACK` | bread garam karne wali machine kitne ki |
| 9 | `REFUSE · not sold` | redmi note 13 price |
| 10 | `REFUSE · not in catalogue` | Trailnest DriftAir pink running shoe water resistant hai? |

Question 8 needs the Groq key in `FULL_CODE/.env`. Without it, the assistant politely refuses that one.

### 🚫 What the assistant will not answer

| It will not… | Example | What it says instead |
|---|---|---|
| Sell or price products the store doesn't carry | 43 inch smart tv kitne ka hai | "I don't have that. Our store doesn't sell TVs…" |
| Talk about other companies' brands | nike running shoes hai kya | "We don't carry Nike products…" |
| Guess a fact the catalogue doesn't list | Kesariya Ektara beige kurta made in india hai? | "The catalogue doesn't say this…" |
| Promise a policy that doesn't exist | credit card pe EMI milega? | "Our store policy doesn't cover this…" |
| Look up your orders or account (there is no order system) | mera order kab aayega | "I couldn't find that in our catalogue or store policy…" |
| Give opinions or reviews beyond the listed rating | ye product achha hai kya, review batao | same as above |
| Chat about unrelated topics | aaj mausam kaisa hai | same as above |
| Pick one product for you when several match | black yoga mat ka price | lists the options and asks which one you mean |
| Invent a price | any question | every ₹ amount is checked against the catalogue before the reply is shown |

**Contents**

- ⭐ Top 10 questions to try first, and what the assistant will not answer
- A. Product questions → the assistant answers
- B. Ambiguous questions → the assistant asks which one (clarify)
- C. Multi-turn conversations (follow-ups remember the context)
- D. Store policy → answer with the policy section
- E. Refusals → the assistant says "I don't have that"
- F. Misspellings, split names and Hinglish (still understood)
- G. LLM fallback: describing a product instead of naming it (needs a Groq key)
- H. What the assistant will never do

## A. Product questions → the assistant answers

### A1. Price of a specific product

States the selling price and stock, citing the product ID.

- Chargit QuillBolt red earphones kitne ke
- Zentrix DriftEdge 900 white mouse price
- What is the price of Zestro OpalLoop kettle?
- Herbique DriftPrime hair dryer kitne ka hai
- Groomex MiraLite trimmer price
- Kitchora RippleStep teal water bottle ka rate
- price of Boltek EchoPrime keyboard black?

### A2. Stock / availability

States `in stock`, `low stock` or `out of stock` with the price.

- Pagecraft BlazePro 10 pack fountain pen stock me hai?
- Is Glowveda CloudLoop trimmer in stock?
- Tanvika Saawan lavender kurti available hai?
- Sanchayo OrbitBolt bedsheet abhi milega?

### A3. Product features and specifications

Answers from the product's catalogue attributes. A `false` value is a grounded "No".

- yatrik vega dash brown duffel me shoe compartment hai?
- Strikeforce VistaAir teal mat kitni moti hai
- Zentrix DriftEdge 900 blue mouse bluetooth hai?
- Sootli DuneTrek 26 cm kadai induction pe chalegi?
- Rasoiya AstraMini 2 litre cooker induction compatible hai?
- Chargit EmberRun earbuds ka battery backup kitna hai
- Boltek CoralStep earbuds water resistant hai?
- Pavana NovaFlex mixer kitne watt ka hai
- Kitchora UltraEdge fan oscillate karta hai?
- Kitchora RippleStep teal bottle dishwasher safe hai?
- Ghoomo AmberWave brown wallet me kitne card slots hai
- tanvika jharokha white kurta ghar pe dho sakte hai?
- yatrik sage dash black bag me 15.6 inch laptop aayega?
- threadcraft coral loop charcoal set 8-9 saal ke bacche ka size milega?

### A4. Discount and MRP

States the selling price, MRP and discount (MRP − price).

- rasoiya flux plus steel dabba set pe kitna discount hai
- Herbique DriftPrime hair dryer ka MRP kya hai

### A5. Product warranty

States `warranty_months`. If none is listed, says there is no brand warranty and cites policy §3.1.

- Grindora CoralAir brown fan pe kitni warranty hai
- doodlr comet zip calculator ki warranty kitni hai
- trekora nimbus wave cabin trolley pe warranty hai kya

### A6. Cheapest / most expensive

Filters in code and returns the single cheapest (or costliest) match. "jo stock me ho" excludes out-of-stock items.

- king size cotton bedsheet sabse sasti jo stock me ho
- 5.5 litre air fryer sabse sasta kaunsa
- sabse mehenga air fryer kitne ka hai
- cheapest hard shell cabin trolley bag?
- english willow bat sabse sasta kitne ka hai
- SPF 50 sunscreen sabse sasta jo stock me ho
- cheapest scientific calculator

### A7. Comparing products

Lists each product with its price and says which is cheaper.

- wavefin ripple loop purple ya teal earbuds kaunsa sasta
- pavana jetair grey mixer vs grindora orbitgrip 200 red mixer which is cheaper
- padvi astra one blue ya stepzo dune mini blue running shoe, kaunsa sasta hai?

### A8. Browsing with filters

Lists up to 10 matching products. Filters can be product type, colour, material, gender, size, budget, capacity, wattage, IP rating, and so on.

- 65W charger dikhao
- 6 mm yoga mat chahiye
- cotton kurta under 1500 hai kya
- wireless mouse 500 se kam me
- 20000 mah powerbank 1000 ke andar milega?
- IPX7 wala bluetooth speaker hai?
- 4 jar wala mixer grinder dikhao
- laptop wala backpack chahiye
- women running shoes dikhao
- show me 1000 piece building blocks
- neem face wash dikhao
- show me 1 litre water bottles

## B. Ambiguous questions → the assistant asks which one (clarify)

Several products match, and they differ in what was asked (price, stock or a feature). The assistant lists the options with IDs, prices and stock, and asks which one is meant. If all the matches give the same answer, it simply answers.

- green running shoes kitne ke hai
- black yoga mat ka price
- krida ion flex football rate?
- Sanchayo NimbusMax steel container set stock me hai?
- groomex breeze prime coconut hair oil price
- Chandni kurti kitne ki hai
- scientific calculator kitne ka hai
- white earbuds ka price batao
- Rasoiya AstraMini cooker kitne ka hai
- teddy bear kitne ka hai

## C. Multi-turn conversations (follow-ups remember the context)

Type the turns (separated by →) one after another in the same chat. Budget, colour, material and the product list carry over ("lavender wali", "inme sabse sasti").

- `strikeforce vistaair yoga mat kitne ki hai` → `lavender wali`
- `6 mm yoga mat chahiye` → `TPE wali 600 ke andar` → `inme sabse sasti kitne ki hai?`
- `1.5 litre ki kettle chahiye` → `glass wali ho` → `inme sabse sasti kitne ki hai?`
- `mens linen kurta dikhao` → `1500 ke andar wale?` → `inme sabse sasta kaunsa hai, price bhi batao`
- `laptop wala backpack chahiye` → `17 inch wala laptop aana chahiye` → `ghoomo wala kitne ka hai`
- `sanchayo jetcore cooker kitne ka hai` → `3 litre wala`
- `women running shoes dikhao` → `blue colour me hai?` → `inme se sabse sasti wali kitne ki hai`

## D. Store policy → answer with the policy section

Answers from `policy.md` and cites the sub-section (e.g. §1.1).

- return kitne din me kar sakte hai
- restocking fee lagti hai kya return pe
- return kaise karu?
- paise kab tak wapas aayenge
- maine COD kiya tha toh refund kaise milega
- kurta ka size chota aa gaya exchange ho jayega?
- product damaged aaya hai kya karu
- free delivery kitne ke order pe milti hai
- 300 rs ka order hai delivery charge lagega?
- delivery me kitne din lagenge
- dubai me deliver karte ho?
- order track kaise karu
- out of stock wala item pre order kar sakte?
- mixer kharab ho gaya warranty claim kaise karu
- warranty me physical damage cover hota hai?
- payment ke kaun kaun se options hai
- 12000 ka order hai COD ho jayega?
- payment fail ho gaya par paisa kat gaya
- order cancel kaise kare
- order ship ho gaya ab cancel kar sakte kya
- shampoo khol ke use kiya pasand nahi aaya return kar du?
- earbuds ki seal khol di, return ho jayega?
- trimmer use kar liya, return hoga?
- GST alag se lagega kya
- do coupon ek saath laga sakte hai?
- amazon pe same cheez sasti hai, price match karoge?
- sale me liya tha return hoga?
- customer care ka number kya hai

## E. Refusals → the assistant says "I don't have that"

### E1. Products the store does not sell

Phones, laptops, TVs, appliances outside the range, groceries, medicines, jewellery, vehicles.

- redmi note 13 price
- maggi noodles 12 pack
- crocin ki strip hai?
- silver payal dikhao
- 43 inch smart tv kitne ka hai
- laptop chahiye college ke liye 40k budget
- bike helmet ISI wala
- whey protein powder 1kg
- double door fridge price

### E2. Other brands the store does not carry

Only the store's own brands are in the catalogue.

- nike running shoes hai kya
- philips trimmer milega?
- boat airdopes kitne ke hai
- prestige ka pressure cooker 5 litre
- lakme lipstick red shade

### E3. Facts the catalogue does not list

The product exists but the attribute is missing. Missing does not mean "no", so the assistant does not guess.

- Trailnest DriftAir pink running shoe water resistant hai?
- Wavefin SageDash X2 purple speaker paani me chalega?
- groomex nova air vitamin c facewash 100ml paraben free?
- Kesariya Ektara beige kurta made in india hai?
- Sonique NovaTrek 200 black earbuds full charge hone me kitna time lagta hai
- stepzo vista fusion pink shoe ka weight kitna hai

### E4. Policy topics the policy does not cover

No EMI, gift-wrap, loyalty, physical-store or installation rules exist in the policy.

- credit card pe EMI milega?
- gift wrap karke bhej sakte ho?
- saffron coins ya loyalty points kaise milte hai
- pune me saffron ka store kahan hai
- installation ke liye technician aayega?

### E5. Nothing matches the constraints

The product type is sold, but no product meets the request (size, colour, budget).

- 10 litre air fryer hai?
- running shoes 500 se kam me
- red school shoes bacchon ke

## F. Misspellings, split names and Hinglish (still understood)

Brand and product-line names are matched even when misspelt or split into words.

- ironnest ripple flex blue yoga mat kitne ki
- ghar kraft quil edge steel container set price?
- herbiqe ultraflex trimer kitne ka h
- kadamb luma pro navy chappal in stock?
- page craft aero prime scientific calculator kitne ka milega
- sonic novatrek 200 black earbuds ka battery backup kitna hai
- urban loom swift fit ladies shirt kitne ka hai?

## G. LLM fallback: describing a product instead of naming it (needs a Groq key)

Shoppers often describe what a product *does* instead of naming it. The rules engine alone refuses these. With
`LLM_PROVIDER=groq` and a key in `FULL_CODE/.env`, the LLM translates the message and picks the product type. The rules
engine then decides as usual, so prices, stock and IDs still come from the catalogue. Replies show an **LLM fallback** tag.

Each question was run live through Groq. "Understood as" is the product type the LLM picked.

### G1. Hinglish

| Question | Understood as | Result |
|---|---|---|
| bread garam karne wali machine kitne ki | toaster | asks which toaster (prices differ) |
| kapde press karne wala machine sasta wala | iron | cheapest iron |
| chai banane ke liye paani garam karne wali machine | electric kettle | list of kettles |
| baal seedha karne wali machine ka price | hair straightener | asks which one |
| baal sukhane wala machine dikhao | hair dryer | list of hair dryers |
| dadhi banane wali machine dikhao | trimmer | list of trimmers |
| sardi me kamra garam karne wali machine | room heater | list of room heaters |
| bina tel ke fry karne wali machine dikhao | air fryer | list of air fryers |
| kaan me lagane wale wireless gaane sunne wale | wireless earbuds | list of earbuds |
| dhoop se chehra bachane wali cream | sunscreen | list of sunscreens |
| sir ke baalon ke liye tel dikhao | hair oil | list of hair oils |
| remote se chalne wali khilona gaadi kitne ki | remote control car | asks which one |

### G2. The same in English

| Question | Understood as | Result |
|---|---|---|
| How much is a machine that toasts bread? | toaster | asks which toaster (prices differ) |
| I need something to press my clothes, the cheapest one | iron | cheapest iron |
| Show me a gadget to boil water for tea | electric kettle | list of kettles |
| What do you have to straighten my hair? | hair straightener | list of straighteners |
| Show me something to dry my hair quickly | hair dryer | list of hair dryers |
| I want something to shave my beard | trimmer | list of trimmers |
| Show me a machine that fries food without oil | air fryer | list of air fryers |
| Something to keep my room warm in winter | room heater | list of room heaters |
| Cream to protect my face from the sun | sunscreen | list of sunscreens |
| Do you have oil for my hair? | hair oil | list of hair oils |
| Show me something to carry my lunch to office | lunch box | list of lunch boxes |
| A toy vehicle that I can control remotely, what is the price? | remote control car | asks which one |
| Show me a game the whole family can play together | board game | list of board games |
| Something to blend soup directly in the pot | hand blender | list of hand blenders |
| I need something to write my college notes in | notebook | list of notebooks |
| Show me a pot that cooks fast using steam | pressure cooker | list of pressure cookers |

**The LLM also knows when to say no.** These describe products the store doesn't sell, so the assistant still refuses:

- kapde dhone wali machine / A machine to wash my clothes *(washing machine)*
- kapde sukhane wali machine dikhao *(clothes dryer)*
- Something to keep my food cold at home *(fridge)*

**Testing tips:** wait a few seconds between LLM questions. Groq's free tier limits tokens per minute, and if you hit the
limit the assistant answers with rules only for up to 30 seconds. LLM output can vary slightly between runs.

## H. What the assistant will never do

- State a price, stock status or feature that is not in the catalogue. Every amount is checked before the reply is shown.
- Guess between several matching products. It asks which one instead.
- Treat a missing attribute as "no".
- Promise something the store policy does not say.
- Recommend products from brands or categories the store does not sell.
