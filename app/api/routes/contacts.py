from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.contact import ConsentCreate, ConsentRead, ContactCreate, ContactRead
from app.services.contacts import create_consent, create_contact, get_contact, list_contacts

router = APIRouter()


@router.post("/contacts", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
def create_contact_endpoint(payload: ContactCreate, db: Session = Depends(get_db)) -> ContactRead:
    return create_contact(db, payload)


@router.get("/contacts", response_model=list[ContactRead])
def list_contacts_endpoint(db: Session = Depends(get_db)) -> list[ContactRead]:
    return list_contacts(db)


@router.get("/contacts/{contact_id}", response_model=ContactRead)
def get_contact_endpoint(contact_id: UUID, db: Session = Depends(get_db)) -> ContactRead:
    contact = get_contact(db, contact_id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.post("/consents", response_model=ConsentRead, status_code=status.HTTP_201_CREATED)
def create_consent_endpoint(payload: ConsentCreate, db: Session = Depends(get_db)) -> ConsentRead:
    return create_consent(db, payload)

