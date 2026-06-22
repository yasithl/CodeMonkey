from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Category, CategoryRule, Transaction
from ..schemas import CategoryCreate, CategoryOut, CategoryRuleCreate, CategoryRuleOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


def _enrich(cat: Category, db: Session) -> dict:
    count = db.query(Transaction).filter_by(category_id=cat.id).count()
    return {
        "id": cat.id,
        "name": cat.name,
        "description": cat.description,
        "gst_claimable": cat.gst_claimable,
        "color": cat.color,
        "is_income": cat.is_income,
        "created_at": cat.created_at,
        "rules": cat.rules,
        "transaction_count": count,
    }


@router.get("")
def list_categories(db: Session = Depends(get_db)):
    cats = db.query(Category).order_by(Category.name).all()
    return [_enrich(c, db) for c in cats]


@router.post("", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryCreate, db: Session = Depends(get_db)):
    if db.query(Category).filter_by(name=body.name).first():
        raise HTTPException(409, f"Category '{body.name}' already exists")
    cat = Category(**body.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/{cat_id}", response_model=CategoryOut)
def update_category(cat_id: int, body: CategoryCreate, db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    for k, v in body.model_dump().items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{cat_id}")
def delete_category(cat_id: int, db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    count = db.query(Transaction).filter_by(category_id=cat_id).count()
    if count > 0:
        raise HTTPException(
            409, f"Cannot delete: {count} transactions reference this category. "
                 "Re-assign them first."
        )
    db.delete(cat)
    db.commit()
    return {"ok": True}


@router.get("/{cat_id}/rules", response_model=list[CategoryRuleOut])
def list_rules(cat_id: int, db: Session = Depends(get_db)):
    if not db.get(Category, cat_id):
        raise HTTPException(404, "Category not found")
    return (
        db.query(CategoryRule)
        .filter_by(category_id=cat_id)
        .order_by(CategoryRule.priority.desc(), CategoryRule.confidence.desc())
        .all()
    )


@router.post("/{cat_id}/rules", response_model=CategoryRuleOut, status_code=201)
def add_rule(cat_id: int, body: CategoryRuleCreate, db: Session = Depends(get_db)):
    if not db.get(Category, cat_id):
        raise HTTPException(404, "Category not found")
    rule = CategoryRule(category_id=cat_id, source="manual", confidence=1.0, **body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    db.commit()
    return {"ok": True}


@router.post("/rules/{rule_id}/promote", response_model=CategoryRuleOut)
def promote_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(404, "Rule not found")
    rule.source = "manual"
    rule.confidence = 1.0
    rule.priority = max(rule.priority, 1)
    db.commit()
    db.refresh(rule)
    return rule
