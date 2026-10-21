"""Lista fechada de lojas e rotas de produto, compartilhada com o frontend."""

import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit


POLICY = json.loads((Path(__file__).resolve().parents[3] / "shared/trusted-stores.json").read_text(encoding="utf-8"))


def trusted_store(value: object) -> str | None:
    if (not isinstance(value, str) or not value.startswith("https://") or len(value) > 2000
            or any(ord(c) < 33 or ord(c) > 126 or c in "\\%<>\"'`" for c in value)):
        return None
    try:
        parts = urlsplit(value)
        if (not parts.hostname or parts.netloc.lower() != parts.hostname or parts.fragment
                or parts.port is not None or "#" in value
                or any(segment in {".", ".."} for segment in parts.path.split("/"))):
            return None
        for store in POLICY["stores"]:
            if parts.hostname not in store["hosts"] or not re.fullmatch(store["path"], parts.path):
                continue
            pairs = parse_qsl(parts.query, keep_blank_values=True, strict_parsing=True)
            if len({key for key, _ in pairs}) != len(pairs):
                return None
            if any(key not in store["query"] or not re.fullmatch(store["query"][key], value)
                   for key, value in pairs):
                return None
            return store["name"]
    except ValueError:
        return None
    return None
