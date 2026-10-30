from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import get_clock
from ..db import get_db
from ..schemas import RFQCreate, RFQOut
from ..services import create_rfq, get_rfq, to_out

router = APIRouter(prefix="/api/rfqs", tags=["RFQs"])


@router.post("", response_model=RFQOut, status_code=201)
def create(data: RFQCreate, db: Session = Depends(get_db), clock=Depends(get_clock)):
    now = clock()
    rfq = create_rfq(db, data, now)
    return to_out(rfq, now)


@router.get("/{rfq_id}", response_model=RFQOut)
def read(rfq_id: int, db: Session = Depends(get_db), clock=Depends(get_clock)):
    return to_out(get_rfq(db, rfq_id), clock())
