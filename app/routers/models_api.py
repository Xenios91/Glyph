@app.route("/getModels", methods=["GET"])
@swag_from("swagger/models.yml")
def get_list_models():
    """
    Handles a GET request to obtain all models available
    """
    models: set[str] = MLPersistanceUtil.get_models_list()

    headers = request.headers
    accept = headers.get("Accept")
    if ACCEPT_TYPE not in accept:
        return jsonify(models=list(models)), 200

    models_status: dict = TaskManager.get_all_status()
    for model in models:
        models_status[model] = "complete"
    return render_template("get_models.html", title="Models List", models=models_status)

@app.route("/deleteModel", methods=["DELETE"])
@swag_from("swagger/delete_model.yml")
def delete_model():
    """
    Handles a GET request to delete a supplied model by name
    """
    args = request.args

    try:
        model_name = args.get("modelName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return jsonify(error=str(key_error)), 400

    if not model_name:
        return jsonify(error="invalid model name"), 400

    try:
        MLPersistanceUtil.delete_model(model_name)
        PredictionPersistanceUtil.delete_model_predictions(model_name)
    except Exception as error:
        logging.error(error)
    return jsonify(), 200


@app.route("/getFunction", methods=["GET"])
@swag_from("swagger/get_function.yml")
def get_function():
    """
    Handles a GET request to return all identified functions associated with a model
    """
    args = request.args
    try:
        function_name = args.get("functionName").strip()
        model_name = args.get("modelName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return jsonify(error=str(key_error)), 400

    if not model_name or not function_name:
        return jsonify(error="invalid model or function name"), 400

    function_information: list = FunctionPersistanceUtil.get_function(
        model_name, function_name
    )

    function_name = function_information[1]
    function_entry: str = function_information[2]
    function_tokens: str = function_information[3]
    function_tokens = format_code(function_tokens)

    headers = request.headers
    accept = headers.get("Accept")
    if ACCEPT_TYPE not in accept:
        return jsonify(functions=function_information), 200

    return render_template(
        "get_function.html",
        model_name=model_name,
        function_name=function_name,
        function_entry=function_entry,
        tokens=function_tokens,
    )

@app.route("/getFunctions", methods=["GET"])
@swag_from("swagger/get_functions.yml")
def get_functions():
    """
    Handles a GET request to return all identified functions associated with a model
    """
    args = request.args
    try:
        model_name = args.get("modelName").strip()
    except KeyError as key_error:
        logging.error(key_error)
        return jsonify(error=str(key_error)), 400

    if not model_name:
        return jsonify(error="invalid model name"), 400

    functions: list = FunctionPersistanceUtil.get_functions(model_name)

    headers = request.headers
    accept = headers.get("Accept")
    if ACCEPT_TYPE not in accept:
        return jsonify(functions=functions), 200

    return render_template(
        "get_symbols.html", bin_name="test", model_name=model_name, functions=functions
    )



