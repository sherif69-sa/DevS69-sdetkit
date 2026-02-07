def kvcli():
    import sys
    from sdetkit.cli import main
    sys.argv = ["kvcli", "kv", *sys.argv[1:]]
    raise SystemExit(main())

def apigetcli():
    import sys
    from sdetkit.cli import main
    sys.argv = ["apigetcli", "apiget", *sys.argv[1:]]
    raise SystemExit(main())
