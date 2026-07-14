"""校验安全扫描豁免是否完整且仍在有效期内。"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml

REQUIRED_FIELDS = {"id", "tool", "scope", "reason", "owner", "expires"}


def main() -> int:
    """校验命令行指定的安全豁免文件。"""
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ".security-exceptions.yml")
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    exceptions = document.get("exceptions", [])
    today = dt.date.today()

    for index, exception in enumerate(exceptions, start=1):
        missing = REQUIRED_FIELDS - set(exception)
        if missing:
            print(f"exception {index} missing fields: {', '.join(sorted(missing))}")
            return 1
        expires = exception["expires"]
        expiry = expires if isinstance(expires, dt.date) else dt.date.fromisoformat(str(expires))
        if expiry < today:
            print(f"exception {exception['id']} expired on {expiry.isoformat()}")
            return 1

    print(f"validated {len(exceptions)} security exception(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
