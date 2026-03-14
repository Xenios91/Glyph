from flask import Blueprint
binaries_bp = Blueprint("binaries", __name__)
from . import routes  # noqa