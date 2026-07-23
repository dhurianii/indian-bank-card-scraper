# Sprint 3.4 — HDFC Card Detail Page Discovery

> Sprint 3.4 is **discovery only**. No parser was written, no models were
> changed, no database writes happened. This document records exactly
> what was found in one real card detail page and proposes what fields
> `CardRecord` should eventually grow to support.

---

## 1. Input artifact

- **Source URL requested:**
  `https://www.hdfcbank.com/personal/pay/cards/credit-cards/millennia-credit-card`
- **Downloaded with:** the existing `HttpClient` (Sprint 3.1, **not modified**)
- **Download script:** `scripts/download_millennia_credit_card.py` (new, follows
  the `download_hdfc_credit_cards.py` pattern)
- **Saved HTML:** `logs/debug/millennia_credit_card.html` (1,227,341 bytes)
- **Page `<title>`:** `Regalia First Credit Card - Apply for Luxury Credit Card | HDFC Bank`

### ⚠ Critical discovery — URL aliasing

The URL we downloaded is the one Sprint 3.3 reported as **"Millennia Credit
Card"** (the canonical-looking `card_name` / `card_url` pair from the credit
cards listing), but **the page HDFC actually serves is for "Regalia First
Credit Card"**, not Millennia. HDFC silently aliases the millennia URL to the
Regalia First page. This has two consequences for the rest of Sprint 3.4 and
future sprints:

1. The page we inspected is in fact a Regalia First page, not a Millennia
   page. The discovery below is therefore based on a **real, current HDFC
   credit card detail page** — just not the one we asked for. This is
   actually *more* useful, because the content we extracted is real, varied,
   and recent.
2. The scraper will need to be defensive about this: never trust the
   `card_name` returned by the listing page as the source of truth. Always
   re-derive it from the detail page's `<h1>` / canonical URL / JSON-LD
   `name`. (The Sprint 3.3 `card_name` is fine as a "label" only; the
   authoritative name lives on the detail page.)

The downloaded HTML is preserved as-is. The fact that the URL maps to
Regalia First is recorded here so the discrepancy is traceable.

---

## 2. Page structure (high level)

The page is server-rendered AEM (Adobe Experience Manager), with a few
beefy blocks built from `cmp-teaser` components. High-level layout:

1. **Hero / banner** — contains the card name (`<h1>`), a one-line status
   paragraph (e.g. "New applications … currently unavailable"), and the
   hero card image. The `Apply Online` CTA in the hero is present but its
   `href` is empty on this card (new applications are paused).
2. **Three big teaser blocks** — `CashBack Benefits`, `Banking Benefits`,
   `Insurance Benefits`. Each is a `cmp-teaser` with an `<h3>` title and a
   `<ul>` of short bullet points.
3. **Two tabbed section groups** (the page renders the same tab structure
   twice — once for "Card Benefits / Lifestyle / Usage / Rewards / Travel /
   Fees & Charges / T&C" and once for "Credit Card Management & Controls /
   Card Control and Redemption / Comprehensive Protection / CashBack with
   SmartPay: / Fees and Renewal / T&C"). Each tab panel is a
   `div.cmp-tabs__tabpanel` containing a long `div.cmp-teaser__description`
   with the actual prose.
4. **FAQ** — `div.cmp-accordion__item` panels, each with an `<h3>`
   question and a panel with the answer.
5. **Footer** — generic HDFC footer with cross-sell cards and apply CTAs
   for **other** cards (must not be confused with this card's apply URL).

There is exactly **one `<table>`** on the entire page, and it is the
"Value of 1 Reward Point" redemption table.

---

## 3. Field-by-field discovery

The "Required?" column is the recommendation for `CardRecord` — fields that
are reliably present on every HDFC detail page should be required; others
should be optional.

### 3.1 Identity / routing fields (HIGH confidence, present here)

| Field name        | Example value                                                  | Extraction strategy                                                                                                                                                  | Required? |
| ----------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `card_name`       | `"Regalia First Credit Card"`                                  | `soup.find("h1").get_text(strip=True)`. (Inside the `<h1>` there is a `<span class="banner-title">` wrapping the same text — both work; the `<h1>` is more stable.)   | ✅ Yes    |
| `card_slug`       | `"regalia-first-credit-card"`                                  | Derive from `link[rel="canonical"]` (`/credit-cards/regalia-first-credit-card`), or last path segment. **Do not** derive from the listing page's `card_name`.       | ✅ Yes    |
| `source_url`      | `https://www.hdfc.bank.in/credit-cards/regalia-first-credit-card` | `link[rel="canonical"]["href"]`. The page's `og:url` and `twitter:url` carry the same value. (Use the canonical, not the originally requested URL, since HDFC aliases them.) | ✅ Yes    |
| `image_url`       | `https://s7ap1.scene7.com/is/image/hdfcbankPWS/regalia-first-credit-card-desktop?fmt=webp` | Inside `div.pd-banner` (the hero container) find `img.cmp-image__image` and read its `data-src` (the lazy-load `lozad` pattern). **The `src` attribute itself is just a generic preview placeholder** (`/content/dam/hdfcbankpws/in/en/preview-img.png`) and must be ignored. | ✅ Yes    |
| `description`     | `"Regalia First Credit Card offers premium travel & lifestyle privileges like Rewards on shopping, Taj Epicure Plus Membership, Club Vistara S..."` | `meta[name="description"]["content"]` (also mirrored in `og:description` and `twitter:description`).                          | ✅ Yes    |
| `card_type`       | `"credit"` (not on page — but is known from the crawler)       | Currently inferred from the listing-page URL path (`/credit-cards/...`). Carry it in the crawler's request, not the parser.                                        | ✅ Yes    |
| `bank_id`         | `"hdfc"` (not on page)                                         | Currently inferred from the parser module.                                                                                                                           | ✅ Yes    |

### 3.2 Network / brand fields

| Field name | Present on this page? | Extraction strategy | Required? |
| ---------- | --------------------- | ------------------- | --------- |
| `network`  | ❌ Not found          | There is **no** Visa / Mastercard / RuPay / Diners / Amex network logo or text anywhere on the detail page (only in cross-sell blocks for *other* cards). The card's network can only be inferred by the slug (`regalia-first-credit-card-desktop` filename), the breadcrumb, or a separate, card-level metadata source. Sprint 3.4 cannot extract this reliably. | ⏸ Defer — leave on `CardRecord` (it is already there) but mark it **optional** for HDFC. |

### 3.3 Fees & charges (MEDIUM confidence, present here, varies per card)

The page exposes two duplicate-but-not-identical fees sections: an older
**"Fees & Charges"** tab and a newer **"Fees and Renewal"** tab. They each
contain a single sentence and then a "Click here" link to a separate PDF /
detail page. The raw text is consistent enough to regex out the
membership-fee figure.

| Field name           | Example value                                   | Extraction strategy                                                                                                                                                                                                                                                                                                                       | Required? |
| -------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `fees.joining`       | `1000`                                          | Inside the *active* `div.cmp-tabs__tabpanel` that contains an `<h3>` whose text equals "Fees and Renewal" (or "Fees & Charges" as fallback), find `div.cmp-teaser__description`. Match the first regex of `r"Joining(?:\s*/\s*Renewal)?(?:\s*Membership)?\s*Fee\s*[:\-]?\s*₹?\s*([\d,]+)"`. Convert to `int`. | 🟡 Optional |
| `fees.annual`        | `1000`                                          | Same container, match `r"(?:Annual\s*)?(?:Membership\s*)?Renewal\s*Fee\s*[:\-]?\s*₹?\s*([\d,]+)"`. Falls back to `fees.joining` if absent (this card uses the same number for both). | 🟡 Optional |
| `fees.currency`      | `"INR"`                                         | Hard-coded / known from the bank. JSON-LD `amount.currency` confirms `"INR"`.                                                                                                                                                                                                                                                              | 🟡 Optional |
| `fees.annual_percentage_rate` | `"23.88% to 43.2%*"`                    | From JSON-LD `annualPercentageRate` (`script[type="application/ld+json"]` containing `"@type": "CreditCard"`).                                                                                                                                                                                                                                | 🟡 Optional |
| `fees.waiver_text`   | `"Spend ₹1,00,000 or more in a year, before your Credit Card renewal date and get your renewal fee waived off."` | Same fees container, sibling text after the fee numbers.                                                                                                                                                                                                                                                                                   | 🟡 Optional |
| `fees_detail_url`    | URL inside the "Click here" link                | Same fees container, find `a` whose text is "Click here" and grab `href`. Points at the full fees PDF / page.                                                                                                                                                                                                                              | 🟡 Optional |

> Note: the fees text is free-form and changes wording per card. The regex
> is a *best-effort* strategy. A future sprint should re-validate against
> several more cards before treating it as canonical.

### 3.4 Rewards & redemption (MEDIUM confidence, present here)

| Field name             | Example value                                                                                                              | Extraction strategy                                                                                                                                                                                                                                                       | Required? |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `rewards.points_per_150` | `4`                                                                                                                      | Inside the "Card Benefits" / "Rewards Programme" tab panel, regex `r"(\d+)\s*Reward\s*Points?\s*(?:on\s*)?(?:for\s*)?every\s*₹?\s*150"` (returns the first match; this card says "Earn 4 Reward Points on every ₹150 spent"). The page also mentions a 3-RP alternate rate, so store both if needed. | 🟡 Optional |
| `rewards.redemption_table` | list of `{redemption_option, value, platform}`                                                                             | The single `<table>` on the page (selector `table`). Each row's three cells are: `redemption_option`, `value`, `platform`. Example: `{redemption_option: "Flights and hotel bookings", value: "₹0.30", platform: "SmartBuy"}`.                                       | 🟡 Optional |
| `rewards.bonus_tiers`  | list of strings, e.g. `"7,500 Bonus RP on ₹6 lakh spends"`, `"5,000 Bonus RP on ₹9 lakh spends"`                        | Same tab panel, regex `r"([\d,]+)\s*Bonus\s*RP\s*on\s*₹?\s*([\d.]+)\s*(lakh|crore)"` per match.                                                                                                                                                                            | 🟡 Optional |

### 3.5 Cashback (MEDIUM confidence, varies per card)

| Field name                | Example value                                                                                            | Extraction strategy                                                                                                                                            | Required? |
| ------------------------- | -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `rewards.cashback_summary`| list of strings, e.g. `"5% CashBack on electricity, telecom, tax payments (₹500 max, first year only)"` | "Banking Benefits" or "CashBack with SmartPay:" `cmp-teaser__description` text. Split on sentence boundaries. Keep raw strings — too varied to normalize. | 🟡 Optional |
| `rewards.cashback_smartpay_max` | `1800`                                                                                              | Regex `r"(?:up\s*to\s*|assured\s*)?₹?\s*([\d,]+)\s*Cashback"` in the "CashBack with SmartPay:" panel.                                                            | 🟡 Optional |

### 3.6 Insurance (MEDIUM confidence, varies per card)

| Field name          | Example value                                                          | Extraction strategy                                                                                                                                                  | Required? |
| ------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `insurance.summary` | list of strings, e.g. `"Accidental air death cover worth ₹50 lakh"`, `"Emergency overseas hospitalization up to ₹10 lakh in case of emergencies"`, `"Lost card liability cover of up to ₹5 lakh"` | "Insurance Benefits" or "Comprehensive Protection" `cmp-teaser` block. Each `<li>` inside its `<ul>`.                        | 🟡 Optional |

### 3.7 Lounge access (LOW–MEDIUM confidence, present here, status varies)

| Field name         | Example value                                                            | Extraction strategy                                                                                                                                | Required? |
| ------------------ | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `benefits.lounge_access` | `"discontinued"` / `"available"` / string with conditions            | Inferred from the FAQ: if the answer to the lounge FAQ starts with "used to offer" + "has been discontinued", set to `"discontinued"`. Otherwise take the bullet text from the "Travel Benefits" tab. The field should be a short free-form string, not a boolean, because the wording varies. | 🟡 Optional |

> The literal text on this card is "Airport Lounge Access & Comprehensive
> Protection Benefit offers discontinued*." which is enough to mark the
> field, but a clean parser is non-trivial. Defer normalization.

### 3.8 Other travel / lifestyle benefits (LOW confidence, very free-form)

| Field name            | Example value                                  | Extraction strategy                                                                                                                                                                                                                | Required? |
| --------------------- | ---------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `benefits.lifestyle`  | list of strings                                | "Lifestyle Benefits" tab `cmp-teaser__description` text. The bullets vary wildly between cards (fuel surcharge, dining, hotel memberships). Store as raw strings.                                                                  | 🟡 Optional |
| `benefits.usage_perks`| list of strings                                | "Usage Perks" tab. E.g. "Utility Bill Payments: ...", "Zero Lost card liability: ...".                                                                                                                                              | 🟡 Optional |
| `benefits.travel`     | list of strings                                | "Travel Benefits" tab.                                                                                                                                                                                                              | 🟡 Optional |

### 3.9 FAQ (HIGH confidence, present here)

| Field name | Example value                                                                       | Extraction strategy                                                                                                                                       | Required? |
| ---------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- |
| `faq`      | list of `{question, answer}` dicts, e.g. `{"What is the Regalia First Credit Card", "The Regalia First Credit Card is a Credit Card from HDFC Bank, ..."}` | Two equivalent paths:<br>1. **HTML**: `soup.select("div.cmp-accordion__item")` → each item has `<h3>` (question) and `div.cmp-accordion__panel` (answer text).<br>2. **JSON-LD**: `script[type="application/ld+json"]` containing `"@type": "FAQPage"` → `mainEntity[*].name` (question) and `mainEntity[*].acceptedAnswer.text` (answer).<br>JSON-LD is cleaner; prefer it. | 🟡 Optional |

### 3.10 Breadcrumb (HIGH confidence, present here)

| Field name      | Example value                                                                                       | Extraction strategy                                                                                  | Required? |
| --------------- | --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | --------- |
| `breadcrumb`    | `[{"name": "Home", "url": "https://www.hdfc.bank.in"}, {"name": "Credit Cards", "url": "..."}, {"name": "Business Regalia First Credit Card", "url": "..."}]` | JSON-LD `script[type="application/ld+json"]` with `"@type": "BreadcrumbList"` → `itemListElement[]`. (HTML breadcrumb is also present but JSON-LD is simpler.) | 🟡 Optional |

### 3.11 Apply / CTA URLs (MEDIUM confidence, varies per card)

| Field name     | Example value     | Extraction strategy                                                                                                                                                            | Required? |
| -------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- |
| `apply_url`    | `None` / `""`     | On this card, the hero "Apply Online" anchor has an **empty** `href` because new applications are paused. Strategy: in the hero `cmp-teaser`, find `a.cmp-teaser__action-link` whose text contains "Apply" and read its `href`. If empty, set `apply_url = None`. | 🟡 Optional |
| `apply_status` | `"closed"`        | If the hero contains a `<p>` saying "New applications … are currently unavailable" (or similar), set `apply_status = "closed"`. Otherwise `"open"`.                          | 🟡 Optional |

> The "Apply Online" links in the *footer* point at **other** cards
> (Regalia Gold, Tata Neu, Marriott, etc.) and **must not** be used as
> `apply_url` for this card.

### 3.12 JSON-LD structured data (bonus, low density here but worth keeping)

The page emits multiple `<script type="application/ld+json">` blocks. The
ones that are reliable across cards and worth parsing are:

- `"@type": "CreditCard"` — gives `name`, `annualPercentageRate`,
  `feesAndCommissionsSpecification` (the fees PDF URL), `offers.offeredBy.name`.
- `"@type": "FAQPage"` — gives the FAQ list.
- `"@type": "BreadcrumbList"` — gives the breadcrumb.
- `"@type": "LoanOrCredit"` — duplicates some CreditCard fields plus a logo
  URL. The logo URL is the HDFC bank logo, **not** the card image, so it
  should not be used as `image_url`.

The `WebPage` and `FinancialProduct` blocks are generic and add little.
Strategy: keep the raw JSON-LD in `extra["json_ld"]` (one of the few things
HDFC's CMS gives us for free) so we don't lose data we don't yet know how
to interpret.

---

## 4. Field map — does this fit `CardRecord` today?

Current `CardRecord` (from Sprint 2):

```python
@dataclass
class CardRecord:
    bank_id: str
    card_slug: str
    card_name: str
    card_type: str            # "debit" | "credit"
    network: str              # "Visa" | "Mastercard" | "RuPay" | ...
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    fees: dict[str, Any] = field(default_factory=dict)
    rewards: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
```

Mapping the discovered fields to `CardRecord` slots:

- ✅ `bank_id`, `card_slug`, `card_name`, `card_type`, `image_url`,
  `source_url` already exist. No change needed.
- ✅ `fees.joining`, `fees.annual`, `fees.annual_percentage_rate`,
  `fees.waiver_text`, `fees_detail_url` fit cleanly inside `fees`.
- ✅ `rewards.points_per_150`, `rewards.redemption_table`,
  `rewards.bonus_tiers`, `rewards.cashback_*` fit inside `rewards`.
- ❌ **`network` is currently required (`str`)** but is **not** present on
  this page. Two options:
  - **Recommended:** change `network: str` → `network: Optional[str] = None`
    in `models.py`. Most other fields are already Optional; this aligns.
  - Alternatively, fill `network` from the slug at parser-time. Not
    recommended — it's a guess, not extracted data.
- ❌ **No first-class slot for `faq`, `breadcrumb`, `apply_url`,
  `apply_status`, or `insurance` / `benefits.*`** — these all currently
  have to live in `extra` because the dataclass has no `faq` / `benefits`
  / `insurance` fields.

---

## 5. Recommended `CardRecord` expansion (proposal only — do not apply yet)

These are the **new fields** the detail-page parser would populate. None
of them is a hard requirement; each could be expressed as a key inside
`extra` instead. The recommendation below is the minimal structured
expansion that makes the new parser honest about what it has:

```python
@dataclass
class CardRecord:
    # --- existing fields, mostly unchanged ---
    bank_id: str
    card_slug: str
    card_name: str
    card_type: str            # "debit" | "credit"
    network: Optional[str]    # CHANGED: was str, see §4
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    description: Optional[str] = None            # NEW
    apply_url: Optional[str] = None              # NEW
    apply_status: Optional[str] = None           # NEW (e.g. "open" | "closed")
    fees: dict[str, Any] = field(default_factory=dict)
    rewards: dict[str, Any] = field(default_factory=dict)
    benefits: dict[str, Any] = field(default_factory=dict)   # NEW
    insurance: dict[str, Any] = field(default_factory=dict)  # NEW
    faq: list[dict[str, str]] = field(default_factory=list)  # NEW
    breadcrumb: list[dict[str, str]] = field(default_factory=list)  # NEW
    extra: dict[str, Any] = field(default_factory=dict)
```

Suggested `fees` / `rewards` / `benefits` / `insurance` shapes (all
best-effort, all free-form string-friendly):

```json
"fees": {
  "joining": 1000,
  "annual": 1000,
  "currency": "INR",
  "annual_percentage_rate": "23.88% to 43.2%*",
  "waiver_text": "Spend ₹1,00,000 or more in a year ...",
  "detail_url": "https://www.hdfcbank.com/...fees-and-charges"
}

"rewards": {
  "points_per_150": 4,
  "bonus_tiers": ["7,500 Bonus RP on ₹6 lakh spends", "5,000 Bonus RP on ₹9 lakh spends"],
  "redemption_table": [
    {"redemption_option": "Flights and hotel bookings", "value": "₹0.30", "platform": "SmartBuy"},
    ...
  ],
  "cashback_summary": ["5% CashBack on electricity, telecom, tax payments (₹500 max, first year only)"],
  "cashback_smartpay_max": 1800
}

"benefits": {
  "lounge_access": "discontinued",
  "lifestyle": ["Fuel surcharge waiver: 1% ...", "Exclusive dining privileges: ..."],
  "usage_perks": ["Utility Bill Payments: ...", "Zero Lost card liability: ..."],
  "travel": ["Airport Lounge Access & Comprehensive Protection Benefit offers discontinued*."]
}

"insurance": {
  "summary": [
    "Accidental air death cover worth ₹50 lakh",
    "Emergency overseas hospitalization up to ₹10 lakh in case of emergencies",
    "Lost card liability cover of up to ₹5 lakh"
  ]
}

"faq": [
  {"question": "What is the Regalia First Credit Card", "answer": "The Regalia First Credit Card is ..."}
]

"breadcrumb": [
  {"name": "Home", "url": "https://www.hdfc.bank.in"},
  {"name": "Credit Cards", "url": "https://www.hdfc.bank.in/credit-cards"},
  {"name": "Business Regalia First Credit Card", "url": "https://www.hdfc.bank.in/credit-cards/regalia-first-credit-card"}
]
```

### Migration impact

- `network: str → Optional[str] = None` is a **breaking change** to the
  type signature. Sprint 2's database tests don't populate `network` for
  every record, so most callers will be fine, but this must be
  coordinated with the next sprint.
- All other additions are additive (default empty), so they are
  **non-breaking**.

---

## 6. Open questions for the user (block on these before designing the parser)

1. **URL aliasing** — when the listing-page URL and the detail-page `<h1>`
   disagree (as they do here), which is the source of truth? The
   recommendation is the detail page's `<h1>` / canonical URL. Confirm.
2. **`network`** — since HDFC's detail pages do not surface the network
   anywhere, are we OK either (a) demoting `network` to `Optional[str]`,
   or (b) leaving it required and not extracting it on HDFC? The
   recommendation is (a).
3. **Apply URL** — when new applications are paused (`href=""` in hero),
   do we still want to store `apply_url = None` and `apply_status =
   "closed"`, or do we want to skip these cards entirely? The
   recommendation is to keep the card, since the metadata is still
   valuable.
4. **Free-form text fields** — many of the new fields
   (`benefits.lifestyle`, `insurance.summary`, etc.) are best stored as
   lists of raw strings. That preserves fidelity but means no
   structured querying later. The alternative is a small fixed schema
   per field, but that will underfit some cards. The recommendation is
   to start with raw strings, normalize in a later sprint.
5. **Scope of parser for Sprint 3.5** — do we want the next parser to
   extract only the **high-confidence** fields (card_name, image_url,
   source_url, faq, breadcrumb, fees.joining, fees.annual, apply_url) and
   defer the rest, or do we want to try the full set? The recommendation
   is high-confidence first, expand in a later sprint after we see
   another card or two.

---

## 7. What was NOT done (per Sprint 3.4 rules)

- ❌ No parser was written.
- ❌ `models.py` was **not** modified.
- ❌ `database.py` was **not** modified.
- ❌ No tests were added.
- ❌ `PROJECT_STATUS.md` was **not** modified.
- ❌ `CHANGELOG.md` was **not** modified.
- ❌ `HttpClient` was **not** modified.
- ❌ No images were downloaded.
- ✅ `scripts/download_millennia_credit_card.py` was added (a tiny
  one-shot downloader in the style of `download_hdfc_credit_cards.py`).
- ✅ `logs/debug/millennia_credit_card.html` was saved for inspection.
- ✅ `docs/sprint3_4_discovery.md` (this file) was added.

---

## 8. Awaiting approval

Per the Sprint 3.4 brief, work stops here pending the user's review of
this report. The next sprint (3.5) should only start after the user
signs off on:

- The discovered field set in §3.
- The proposed `CardRecord` expansion in §5.
- The answers to the open questions in §6.
