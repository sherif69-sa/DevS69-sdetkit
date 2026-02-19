import shlex


def normalize_line(line: str) -> str:
    return line.strip()


def parse_kv_line(line: str, *, allow_comments: bool = False) -> dict[str, str]:
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

        out[k] = v

    return out
