import logging
import os
from flask import Flask
from dotenv import load_dotenv

from extensions import limiter
from database import init_db, close_db
from scheduler_module import start_scheduler
from routes import routes_bp

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)

    # Logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
    )

    # Attach limiter
    limiter.init_app(app)

    # DB
    init_db()
    app.teardown_appcontext(close_db)

    # Blueprints
    app.register_blueprint(routes_bp)

    # Scheduler
    start_scheduler(app)

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('FLASK_RUN_PORT', 6020))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode) 