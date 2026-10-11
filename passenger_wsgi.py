import os
import sys

# Ensure current application directory is on sys.path
app_dir = os.path.dirname(os.path.abspath(__file__))
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Auto-install python-multipart if missing in the environment
try:
    import multipart  # python-multipart package installs as 'multipart'
except ImportError:
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-multipart"])
    except Exception:
        pass

try:
    from a2wsgi import ASGIMiddleware
    from app.main import app
    application = ASGIMiddleware(app)
except Exception as e:
    import traceback
    error_trace = traceback.format_exc()

    def application(environ, start_response):
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain; charset=utf-8'),
            ('Access-Control-Allow-Origin', '*'),
            ('Access-Control-Allow-Headers', '*'),
            ('Access-Control-Allow-Methods', '*')
        ])
        return [f"Error starting application under Passenger WSGI:\n\n{error_trace}".encode('utf-8')]
