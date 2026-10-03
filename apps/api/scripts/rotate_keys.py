"""Re-encrypts every saved provider key under the current encryption key.
RUN BY THE PROJECT OWNER ONLY (the assistant never runs it).

To rotate KEY_ENCRYPTION_SECRET without anyone losing their saved API keys:

  1. Generate a new key:  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  2. Put it FIRST in KEY_ENCRYPTION_SECRET and keep the old one after a comma:
         KEY_ENCRYPTION_SECRET=<new>,<old>
  3. Restart the API (new keys are now encrypted with <new>; old ones still read).
  4. python -m scripts.rotate_keys            # dry run: counts what would change
     python -m scripts.rotate_keys --apply    # re-encrypts every stored key under <new>
  5. Remove <old> from KEY_ENCRYPTION_SECRET and restart.

No provider is called; keys are never printed.
"""

import argparse
import asyncio
import sys

from cryptography.fernet import InvalidToken

from app.core.security import reencrypt_key
from app.db import maintenance


async def main() -> int:
    parser = argparse.ArgumentParser(description="Re-encrypt stored API keys (owner-run).")
    parser.add_argument("--apply", action="store_true", help="write the re-encrypted values (default: dry run)")
    args = parser.parse_args()

    rows = await maintenance.all_encrypted_keys()
    changed = unreadable = 0
    for row in rows:
        try:
            fresh = reencrypt_key(row["encrypted_key"])
        except InvalidToken:
            unreadable += 1
            continue
        if fresh != row["encrypted_key"]:
            changed += 1
            if args.apply:
                await maintenance.set_encrypted_key(row["id"], fresh)
    print(f"{len(rows)} stored keys: {changed} {'re-encrypted' if args.apply else 'would be re-encrypted'}, "
          f"{unreadable} unreadable with the configured keys (their owners must re-enter them).")
    if not args.apply:
        print("(dry run: pass --apply to write)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
