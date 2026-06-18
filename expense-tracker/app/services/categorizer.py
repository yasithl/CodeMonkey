import re
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from ..models import Category, CategoryRule, Transaction

CONFIDENCE_THRESHOLD = 0.70

STOPWORDS = {
    "the", "and", "ltd", "pty", "plc", "inc", "llc", "com", "www",
    "for", "from", "pos", "trf", "ref", "payment", "purchase", "card",
    "direct", "debit", "standing", "order", "faster", "pay", "via",
    "gbp", "usd", "eur", "gbr", "uk", "online", "mobile", "internet",
}

DEFAULT_CATEGORIES = [
    # (name, color, gst_claimable, is_income)
    ("Groceries",           "#198754", False, False),
    ("Fuel",                "#fd7e14", True,  False),
    ("Software & SaaS",     "#0d6efd", True,  False),
    ("Subscriptions",       "#6610f2", False, False),
    ("Travel",              "#20c997", True,  False),
    ("Meals & Entertainment","#e83e8c", False, False),
    ("Office Supplies",     "#0dcaf0", True,  False),
    ("Professional Services","#6f42c1", True,  False),
    ("Taxes & Fees",        "#dc3545", False, False),
    ("Equipment",           "#fd7e14", True,  False),
    ("Utilities",           "#ffc107", True,  False),
    ("Marketing",           "#198754", True,  False),
    ("Bank Fees",           "#6c757d", False, False),
    ("Salary / Wages",      "#198754", False, True),
    ("Client Income",       "#28a745", False, True),
    ("Other",               "#adb5bd", False, False),
]

SEED_RULES = [
    # (keyword, category_name, match_type)
    # Supermarkets
    ("tesco",               "Groceries",            "contains"),
    ("sainsbury",           "Groceries",            "contains"),
    ("waitrose",            "Groceries",            "contains"),
    ("asda",                "Groceries",            "contains"),
    ("morrisons",           "Groceries",            "contains"),
    ("lidl",                "Groceries",            "contains"),
    ("aldi",                "Groceries",            "contains"),
    ("co-op",               "Groceries",            "contains"),
    ("marks & spencer",     "Groceries",            "contains"),
    # Fuel
    ("bp ",                 "Fuel",                 "contains"),
    ("shell ",              "Fuel",                 "contains"),
    ("esso",                "Fuel",                 "contains"),
    ("texaco",              "Fuel",                 "contains"),
    ("gulf petrol",         "Fuel",                 "contains"),
    # Software/Cloud
    ("github",              "Software & SaaS",      "contains"),
    ("aws",                 "Software & SaaS",      "contains"),
    ("amazon web services", "Software & SaaS",      "contains"),
    ("digitalocean",        "Software & SaaS",      "contains"),
    ("google cloud",        "Software & SaaS",      "contains"),
    ("microsoft 365",       "Software & SaaS",      "contains"),
    ("atlassian",           "Software & SaaS",      "contains"),
    ("slack",               "Software & SaaS",      "contains"),
    ("zoom",                "Software & SaaS",      "contains"),
    ("heroku",              "Software & SaaS",      "contains"),
    ("vercel",              "Software & SaaS",      "contains"),
    ("cloudflare",          "Software & SaaS",      "contains"),
    # Subscriptions
    ("netflix",             "Subscriptions",        "contains"),
    ("spotify",             "Subscriptions",        "contains"),
    ("adobe",               "Subscriptions",        "contains"),
    ("jetbrains",           "Subscriptions",        "contains"),
    ("dropbox",             "Subscriptions",        "contains"),
    ("1password",           "Subscriptions",        "contains"),
    ("apple.com/bill",      "Subscriptions",        "contains"),
    # Travel
    ("trainline",           "Travel",               "contains"),
    ("national rail",       "Travel",               "contains"),
    ("tfl",                 "Travel",               "contains"),
    ("uber",                "Travel",               "contains"),
    ("bolt.eu",             "Travel",               "contains"),
    ("british airways",     "Travel",               "contains"),
    ("easyjet",             "Travel",               "contains"),
    ("ryanair",             "Travel",               "contains"),
    ("airbnb",              "Travel",               "contains"),
    ("booking.com",         "Travel",               "contains"),
    # Meals
    ("deliveroo",           "Meals & Entertainment","contains"),
    ("uber eats",           "Meals & Entertainment","contains"),
    ("just eat",            "Meals & Entertainment","contains"),
    # Office
    ("staples",             "Office Supplies",      "contains"),
    ("viking",              "Office Supplies",      "contains"),
    ("ryman",               "Office Supplies",      "contains"),
    # Professional
    ("hmrc",                "Taxes & Fees",         "contains"),
    ("companies house",     "Professional Services","contains"),
    # Utilities
    ("bt group",            "Utilities",            "contains"),
    ("virgin media",        "Utilities",            "contains"),
    ("ee limited",          "Utilities",            "contains"),
    ("o2",                  "Utilities",            "contains"),
    ("british gas",         "Utilities",            "contains"),
    ("octopus energy",      "Utilities",            "contains"),
]


def seed_defaults(db: Session) -> None:
    for name, color, gst_claimable, is_income in DEFAULT_CATEGORIES:
        if not db.query(Category).filter_by(name=name).first():
            db.add(Category(
                name=name, color=color,
                gst_claimable=gst_claimable, is_income=is_income,
            ))
    db.flush()

    for keyword, cat_name, match_type in SEED_RULES:
        cat = db.query(Category).filter_by(name=cat_name).first()
        if cat and not db.query(CategoryRule).filter_by(keyword=keyword, category_id=cat.id).first():
            db.add(CategoryRule(
                category_id=cat.id,
                keyword=keyword,
                match_type=match_type,
                source="seed",
                confidence=0.9,
                priority=0,
            ))
    db.commit()


def categorize(description: str, db: Session) -> tuple[Optional[int], float, Optional[int]]:
    """Returns (category_id, confidence, matched_rule_id)."""
    desc_lower = description.lower().strip()

    rules = (
        db.query(CategoryRule)
        .order_by(CategoryRule.priority.desc(), CategoryRule.confidence.desc())
        .all()
    )

    best_cat_id: Optional[int] = None
    best_conf = 0.0
    best_rule_id: Optional[int] = None

    for rule in rules:
        kw = rule.keyword.lower()
        matched = False
        if rule.match_type == "contains":
            matched = kw in desc_lower
        elif rule.match_type == "startswith":
            matched = desc_lower.startswith(kw)
        elif rule.match_type == "regex":
            try:
                matched = bool(re.search(kw, desc_lower))
            except re.error:
                pass

        if matched and rule.confidence > best_conf:
            best_cat_id = rule.category_id
            best_conf = rule.confidence
            best_rule_id = rule.id

    return best_cat_id, best_conf, best_rule_id


def _compute_gst(amount: Decimal, gst_claimable: bool, is_expense: bool, gst_rate: float) -> Decimal:
    if gst_claimable and is_expense:
        rate = Decimal(str(gst_rate))
        return (abs(amount) * rate / (1 + rate)).quantize(Decimal("0.0001"))
    return Decimal("0")


def apply_category(
    transaction: Transaction,
    category_id: int,
    status: str,
    db: Session,
    gst_rate: float,
) -> None:
    transaction.category_id = category_id
    transaction.reconciliation_status = status

    cat = db.get(Category, category_id)
    if cat:
        transaction.gst_claimable = cat.gst_claimable
        transaction.gst_amount = _compute_gst(
            transaction.amount, cat.gst_claimable,
            transaction.amount < 0, gst_rate,
        )
    else:
        transaction.gst_claimable = False
        transaction.gst_amount = Decimal("0")


def learn_from_manual(
    transaction: Transaction,
    category_id: int,
    db: Session,
    gst_rate: float,
) -> None:
    apply_category(transaction, category_id, "manual", db, gst_rate)

    # Extract candidate keywords
    tokens = re.split(r"[^a-z0-9]+", transaction.description.lower())
    tokens = [t for t in tokens if len(t) >= 3 and t not in STOPWORDS]

    if tokens:
        # Pick best keyword by co-occurrence with existing transactions in this category
        sibling_descs = " ".join(
            d[0].lower()
            for d in db.query(Transaction.description)
            .filter(
                Transaction.category_id == category_id,
                Transaction.id != transaction.id,
            )
            .limit(200)
            .all()
        )

        best_kw = max(tokens, key=lambda t: sibling_descs.count(t), default=tokens[0])

        existing = (
            db.query(CategoryRule)
            .filter_by(keyword=best_kw, category_id=category_id)
            .first()
        )
        if existing:
            existing.hit_count += 1
            existing.confidence = min(0.6 + existing.hit_count * 0.05, 0.95)
        else:
            db.add(CategoryRule(
                category_id=category_id,
                keyword=best_kw,
                match_type="contains",
                source="learned",
                confidence=0.6,
                priority=0,
            ))

    db.commit()
    _rerun_pending(db, gst_rate)


def rerun_all_pending(db: Session, gst_rate: float) -> int:
    return _rerun_pending(db, gst_rate)


def _rerun_pending(db: Session, gst_rate: float) -> int:
    pending = (
        db.query(Transaction)
        .filter_by(reconciliation_status="pending")
        .limit(1000)
        .all()
    )
    updated = 0
    for tx in pending:
        cat_id, conf, _ = categorize(tx.description, db)
        if cat_id and conf >= CONFIDENCE_THRESHOLD:
            apply_category(tx, cat_id, "auto", db, gst_rate)
            tx.category_confidence = conf
            updated += 1
    db.commit()
    return updated
