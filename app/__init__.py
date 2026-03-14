import threading
from flasgger import Swagger
from flask import Flask
from sql_service import SQLUtil
from config import GlyphConfig
from services import TaskService

def create_app():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 500 * 1000 * 1000
    app.config["UPLOAD_FOLDER"] = "./binaries"

    Swagger(app)
    GlyphConfig.load_config()
    SQLUtil.init_db()
    threading.Thread(target=TaskService().start_service, daemon=True).start()

    from .blueprints.views import views_bp
    from .blueprints.models_api import models_bp
    from .blueprints.predictions_api import predictions_bp
    from .blueprints.tasks_api import tasks_bp
    from .blueprints.binaries_api import binaries_bp

    app.register_blueprint(views_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(predictions_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(binaries_bp)

    return app