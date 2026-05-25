from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from db.session import get_db
from models.db.rep import Rep
from core.auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_current_rep(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Rep:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise credentials_exc
    rep_pk = payload.get("sub")
    if not rep_pk:
        raise credentials_exc
    rep = db.query(Rep).filter(Rep.id == rep_pk).first()
    if not rep or not rep.is_active:
        raise credentials_exc
    return rep