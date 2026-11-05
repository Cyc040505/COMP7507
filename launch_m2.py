"""Start the shared app directly on M2, with a configurable local port."""

import argparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    from src import layout
    layout.DEFAULT_MODULE = "M2"
    import app
    print(f"COMP7507 M2: http://127.0.0.1:{args.port}")
    app.app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
