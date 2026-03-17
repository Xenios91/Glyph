@app.route("/getStatus", methods=["GET"])
@swag_from("swagger/status.yml")
def get_status():
    """
    Handles a GET request to obtain the supplied uuid task status
    """
    args = request.args
    status: str
    status_code: int

    try:
        job_uuid: str = args["uuid"]
        if job_uuid == "all":
            status = "test"
            status_code = 200
        else:
            status = Trainer().get_status(job_uuid)
            if status == "UUID Not Found":
                status_code = 404
            else:
                status_code = 200
    except KeyError as key_error:
        logging.error(key_error)
        return jsonify(error=str(key_error)), 400

    return jsonify(status=status), status_code









@app.route("/statusUpdate", methods=["POST"])
@swag_from("swagger/status_update.yml")
def update_status():
    """
    Handles a POST request from Ghidra to update the current status of a task
    """
    args = request.json

    try:
        status = args.get("status").strip()
        if "uuid" in args:
            uuid = args.get("uuid").strip()
        else:
            uuid = ""

    except KeyError as key_error:
        logging.error(key_error)
        return jsonify(error=str(key_error)), 400

    if not status or not uuid:
        return jsonify(error="Invalid request, missing query strings"), 400

    updated: bool = Trainer().set_status(uuid, status)
    if not updated:
        return jsonify(error="UUID not found"), 404

    return jsonify(), 200