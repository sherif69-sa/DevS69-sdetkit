import httpx


def fetch_json_dict(client: httpx.Client, path: str, retries: int = 1) -> dict:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    last_err = None  # pragma: no mutate
    for _ in range(retries):
        try:
            r = client.get(path)
            last_err = None  # pragma: no mutate
            break
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            r = None  # pragma: no mutate
    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    if r.status_code < 200 or r.status_code >= 300:
        raise RuntimeError("non-2xx response")

    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("expected json object")
    return data


async def fetch_json_dict_async(client: httpx.AsyncClient, path: str, retries: int = 1) -> dict:
    if retries < 1:
        raise ValueError("retries must be >= 1")

    last_err = None  # pragma: no mutate
    for _ in range(retries):
        try:
            r = await client.get(path)
            last_err = None  # pragma: no mutate
            break
        except httpx.TimeoutException as e:
            raise TimeoutError("request timed out") from e
        except httpx.RequestError as e:
            last_err = e
            r = None  # pragma: no mutate
    if last_err is not None:
        raise RuntimeError("request failed") from last_err

    if r.status_code < 200 or r.status_code >= 300:
        raise RuntimeError("non-2xx response")

    data = r.json()
    if not isinstance(data, dict):
        raise ValueError("expected json object")
    return data
