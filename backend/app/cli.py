"""
Administration commands (UI-2). Run from the backend folder with the virtual environment active:

    python -m app.cli reset-password someone@example.com     # asks for the new password twice
    python -m app.cli list-users
    python -m app.cli list-projects                          # which database, every project and its owner
    python -m app.cli assign-projects you@example.com        # give projects without an owner to that account
    python -m app.cli assign-projects you@example.com --from old@example.com   # move another account's projects
    python -m app.cli assign-projects you@example.com --all  # every project in the database

Resetting a password also signs that account out everywhere (its sessions are deleted). Until "forgot password"
by email arrives with deployment (it needs an email service), this is how a forgotten password is reset.
"""
import argparse
import getpass
import sys

from app.core.database import SessionLocal, init_db
from app.core.security import hash_password, normalize_email, password_problem
from app.models.user import User, UserSession


def reset_password(email: str, new_password: str) -> str:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == normalize_email(email)).first()
        if user is None:
            raise SystemExit(f"No account with the email {email!r}.")
        problem = password_problem(new_password)
        if problem:
            raise SystemExit(problem)
        user.password_hash = hash_password(new_password)
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        db.commit()
        return f"Password reset for {user.email}; signed out of all sessions."
    finally:
        db.close()


def list_users() -> str:
    db = SessionLocal()
    try:
        rows = db.query(User).order_by(User.created_at).all()
        return "\n".join(f"{u.email}\t{u.full_name}\tcreated {u.created_at:%Y-%m-%d}" for u in rows) or "No accounts yet."
    finally:
        db.close()


def list_projects() -> str:
    from app.core.config import settings
    from app.models.project import Project

    db = SessionLocal()
    try:
        emails = {u.id: u.email for u in db.query(User).all()}
        lines = [f"Database: {settings.database_url}  (relative paths are relative to the folder the backend runs in)"]
        rows = db.query(Project).order_by(Project.created_at).all()
        for p in rows:
            owner = emails.get(p.owner_id, "NO OWNER") if p.owner_id else "NO OWNER"
            lines.append(f"{p.id}\t{p.name}\towner: {owner}")
        lines.append(f"{len(rows)} project(s), {len(emails)} account(s).")
        return "\n".join(lines)
    finally:
        db.close()


def assign_projects(email: str, from_email: str | None = None, everything: bool = False) -> str:
    """Give projects to an account: those without an owner (default), those of another account, or all of them."""
    from app.models.project import Project

    db = SessionLocal()
    try:
        target = db.query(User).filter(User.email == normalize_email(email)).first()
        if target is None:
            raise SystemExit(f"No account with the email {email!r}. Create it in the app first.")
        q = db.query(Project)
        if everything:
            q = q.filter((Project.owner_id.is_(None)) | (Project.owner_id != target.id))
        elif from_email:
            source = db.query(User).filter(User.email == normalize_email(from_email)).first()
            if source is None:
                raise SystemExit(f"No account with the email {from_email!r}.")
            q = q.filter(Project.owner_id == source.id)
        else:
            q = q.filter(Project.owner_id.is_(None))
        names = [p.name for p in q.all()]
        q.update({Project.owner_id: target.id}, synchronize_session=False)
        db.commit()
        return f"{len(names)} project(s) now belong to {target.email}" + (": " + ", ".join(names) if names else ".")
    finally:
        db.close()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("reset-password", help="set a new password for an account")
    r.add_argument("email")
    sub.add_parser("list-users", help="list the accounts")
    sub.add_parser("list-projects", help="show the database in use, every project and its owner")
    a = sub.add_parser("assign-projects", help="give projects to an account")
    a.add_argument("email")
    a.add_argument("--from", dest="from_email", help="move the projects of this account")
    a.add_argument("--all", action="store_true", help="every project in the database")
    args = p.parse_args(argv)
    init_db()
    if args.cmd == "list-users":
        print(list_users())
        return 0
    if args.cmd == "list-projects":
        print(list_projects())
        return 0
    if args.cmd == "assign-projects":
        print(assign_projects(args.email, args.from_email, args.all))
        return 0
    first = getpass.getpass("New password: ")
    if first != getpass.getpass("Repeat it: "):
        print("The passwords don't match.", file=sys.stderr)
        return 1
    print(reset_password(args.email, first))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
