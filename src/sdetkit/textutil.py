import shlex


_DUPLICATE_POLICIES = {"last", "first", "error"}


def normalize_line(line: str) -> str:
    return line.strip()


def parse_kv_line(
    line: str,
    *,
    allow_comments: bool = False,
    duplicate_policy: str = "last",
) -> dict[str, str]:
    if duplicate_policy not in _DUPLICATE_POLICIES:
        raise ValueError("bad duplicate policy")

    s = normalize_line(line)
    if s == "":
        return {}

    out: dict[str, str] = {}
    if allow_comments:
        lexer = shlex.shlex(s, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = "#"
        parts = list(lexer)
    else:
        parts = shlex.split(s)

    for part in parts:
        if "=" not in part:
            raise ValueError("bad token")

        k, v = part.split("=", 1)
        if k == "" or v == "":
            raise ValueError("bad kv")

        if duplicate_policy == "error" and k in out:
            raise ValueError(f"duplicate key: {k}")
        if duplicate_policy == "first" and k in out:
            continue

        out[k] = v

    return out
