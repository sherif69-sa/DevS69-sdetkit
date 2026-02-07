import shlex


def normalize_line(line: str) -> str:
    return line.strip()


def parse_kv_line(line: str) -> dict[str, str]:
    s = normalize_line(line)
    if s == "":
        return {}

    out: dict[str, str] = {}
    parts = shlex.split(s)

    for part in parts:
        if part.count("=") < 1:
            raise ValueError("bad token")

        k, v = part.split("=", 1)
        if k == "" or v == "":
            raise ValueError("bad kv")

        out[k] = v

    return out
