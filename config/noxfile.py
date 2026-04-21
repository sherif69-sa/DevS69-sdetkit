import nox


@nox.session
def tests(session: nox.Session) -> None:
    session.install("-r", "requirements-test.txt")
    session.run("pytest")


@nox.session
def lint(session: nox.Session) -> None:
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")
