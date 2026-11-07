import sys


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    rest = sys.argv[2:]
    if cmd == "refresh":
        from .refresh import main as m
        m(rest)
    elif cmd == "run":
        from .server import main as m
        m(rest)
    elif cmd == "test":
        import unittest
        suite = unittest.defaultTestLoader.discover("tests")
        ok = unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
        sys.exit(0 if ok else 1)
    else:
        print("usage: python3 -m oracle [refresh|run|test]")


main()
