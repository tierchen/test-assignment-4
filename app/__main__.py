import asyncio
import sys

import uvicorn
from alembic import command as alembic_command
from alembic.config import Config

from app.config import load_settings
from app.infra.queue import run_worker


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "api"

    if command == "api":
        uvicorn.run("app.app:create_app", factory=True, host="0.0.0.0", port=8000)
    elif command == "worker":
        asyncio.run(run_worker(load_settings()))
    elif command == "migrate":
        alembic_command.upgrade(Config("alembic.ini"), "head")
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
