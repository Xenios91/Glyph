from flask import jsonify, render_template, request
from config import GlyphConfig, MAX_CPU_CORES
from . import views_bp
from app import _version
from helpers import ACCEPT_TYPE


@views_bp.route("/")
def home():
    """
    Loads the homepage of Glyph
    """
    headers = request.headers
    accept = headers.get("Accept")
    if ACCEPT_TYPE not in accept:
        return jsonify(version=_version.__version__), 200

    return render_template("main.html")


@views_bp.route("/config")
def config():
    """
    Loads the configuration page of Glyph
    """
    cfg = GlyphConfig()
    return render_template(
        "config.html",
        max_cpu_cores=MAX_CPU_CORES,
        current_cpu_cores=cfg.get_config_value("cpu_cores") or 2,
        current_max_file_size=cfg.get_config_value("max_file_size_mb") or 512,
    )


@views_bp.route("/api/config/save", methods=["POST"])
def save_config():
    """
    Saves the configuration settings
    """
    config_values: dict = request.get_json()
    max_file_size_mb = config_values.get("max_file_size_mb")
    if max_file_size_mb is not None and isinstance(max_file_size_mb, int):
        GlyphConfig.set_max_file_size(max_file_size_mb)

    cpu_cores = config_values.get("cpu_cores")
    if cpu_cores is not None and isinstance(cpu_cores, int):
        if 1 <= cpu_cores <= MAX_CPU_CORES:
            GlyphConfig._config["cpu_cores"] = cpu_cores
        else:
            return jsonify(
                error=f"CPU cores must be between 1 and {MAX_CPU_CORES}"
            ), 400

    return jsonify(), 200
