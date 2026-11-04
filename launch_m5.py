"""Open this local course project directly on M5 without changing other modules."""

import argparse
import threading
import webbrowser
from src import layout

layout.DEFAULT_MODULE = "M5"
import app

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--port", type=int, default=8050)
    args = p.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    print("COMP7507 M5:", url)
    if not args.no_browser:
        timer = threading.Timer(2, lambda: webbrowser.open(url))
        timer.daemon = True
        timer.start()
    app.app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)
