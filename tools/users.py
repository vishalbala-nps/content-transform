"""Manage user accounts. The only way accounts are made: there is no sign-up.

    uv run --env-file .env python -m tools.users create someone@example.org
    uv run --env-file .env python -m tools.users passwd someone@example.org
    uv run --env-file .env python -m tools.users disable someone@example.org
    uv run --env-file .env python -m tools.users enable someone@example.org
    uv run --env-file .env python -m tools.users list
    uv run --env-file .env python -m tools.users adopt someone@example.org

Passwords are asked for without echoing. `--password` gives one on the
command line instead, for scripts; it is then visible in shell history.
`adopt` gives every job and brand kit with no owner (made before accounts
existed) to that user.
"""

import argparse
import getpass
import sys

from app.core import users
from app.db.models import init_db


def _password(given: str | None) -> str:
    if given is not None:
        password = given
    else:
        password = getpass.getpass("Password: ")
        if getpass.getpass("Again: ") != password:
            sys.exit("The passwords do not match.")
    if len(password) < users.RECOMMENDED_PASSWORD_LENGTH:
        print(
            f"warning: shorter than {users.RECOMMENDED_PASSWORD_LENGTH} characters; "
            "fine for testing, weak for real use",
            file=sys.stderr,
        )
    return password


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m tools.users", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("create", "make an account"),
        ("passwd", "set a new password (signs the user out everywhere)"),
    ]:
        command = commands.add_parser(name, help=help_text)
        command.add_argument("email")
        command.add_argument("--password", help="instead of being asked; visible in shell history")
    for name, help_text in [
        ("disable", "stop an account signing in, and sign it out"),
        ("enable", "let a disabled account sign in again"),
        ("adopt", "give every job and brand kit with no owner to this user"),
    ]:
        commands.add_parser(name, help=help_text).add_argument("email")
    commands.add_parser("list", help="every account")
    args = parser.parse_args()

    init_db()  # the users table may not exist yet
    try:
        match args.command:
            case "create":
                if users.get_user_by_email(args.email):  # also checks it is an email, before asking
                    raise users.UserError(f"{users.normalise_email(args.email)} already has an account.")
                user = users.create_user(args.email, _password(args.password))
                print(f"created {user.email}")
            case "passwd":
                if not users.get_user_by_email(args.email):
                    raise users.UserError(f"No account for {users.normalise_email(args.email)}.")
                users.set_password(args.email, _password(args.password))
                print(f"password changed for {users.normalise_email(args.email)}")
            case "disable" | "enable":
                users.set_active(args.email, args.command == "enable")
                print(f"{args.command}d {users.normalise_email(args.email)}")
            case "adopt":
                jobs, kits = users.adopt_unowned(args.email)
                print(f"{users.normalise_email(args.email)} now also owns {jobs} job(s) and {kits} brand kit(s)")
            case "list":
                for user in users.list_users():
                    state = "active" if user.active else "disabled"
                    print(f"{user.email}\t{state}\tcreated {user.created_at:%Y-%m-%d}")
    except users.UserError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
