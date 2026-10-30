import os
import sys

# Ensure project root is in sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from backend.app import create_app
    app = create_app()
except Exception as e:
    import traceback
    err_msg = traceback.format_exc()
    print("FATAL ERROR DURING APP INITIALIZATION:\n", err_msg)
    from flask import Flask
    app = Flask(__name__)
    
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def catch_all(path):
        return f"<h2>Application Startup Error</h2><pre style='background:#f1f5f9;padding:15px;border-radius:6px;'>{err_msg}</pre>", 500

if __name__ == "__main__":
    app.run()
