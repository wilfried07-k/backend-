"""Create the first administrator interactively: python -m app.create_admin."""
from getpass import getpass

from sqlmodel import Session, SQLModel, select

from . import models
from .auth import hash_password
from .database import DATABASE_URL, engine
from .models import AccountType, User


def main() -> None:
    if not DATABASE_URL.startswith("postgresql+psycopg://"):
        raise SystemExit(
            "Expected Render PostgreSQL. Set DATABASE_URL to the External Database URL "
            "from Render (postgres:// or postgresql://); do not use the local Oracle URL."
        )
    SQLModel.metadata.create_all(engine)
    email = input("Adresse e-mail administrateur: ").strip().lower()
    full_name = input("Nom affiché: ").strip()
    password = getpass("Mot de passe (12 caractères minimum): ")
    if len(password) < 12:
        raise SystemExit("Le mot de passe doit contenir au moins 12 caractères.")
    with Session(engine) as session:
        existing = session.exec(select(User).where(User.email == email)).first()
        if existing:
            raise SystemExit("Cette adresse e-mail existe déjà.")
        admin = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            account_type=AccountType.admin,
        )
        session.add(admin)
        session.commit()
    print("Compte administrateur créé.")


if __name__ == "__main__":
    main()
