"""Tests for web endpoints."""

import logging
from typing import Any

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


class TestWebEndpoints:
    """Tests for web endpoint routes."""

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_home_json_response(self, mock_ml_persistance: Any, web_client: TestClient) -> None:
        """Test home endpoint returns JSON for API clients."""
        mock_ml_persistance.get_models_list = AsyncMock(return_value=set())

        response = web_client.get("/", headers={"Accept": "application/json"})

        assert response.status_code == 200
        data = response.json()
        assert "version" in data

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_home_html_response(self, mock_ml_persistance: Any, web_client: TestClient) -> None:
        """Test home endpoint returns HTML for browsers."""
        mock_ml_persistance.get_models_list = AsyncMock(return_value=set())

        response = web_client.get(
            "/",
            headers={"Accept": "text/html,application/xhtml+xml"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @patch("app.web.endpoints.web.get_settings")
    def test_config_endpoint(self, mock_get_settings: Any, web_client: TestClient) -> None:
        """Test config endpoint."""
        mock_settings = Mock()
        mock_settings.cpu_cores = 4
        mock_settings.max_file_size_mb = 100
        mock_get_settings.return_value = mock_settings

        response = web_client.get(
            "/config",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    def test_error_endpoint_default(self, web_client: TestClient) -> None:
        """Test error endpoint with default message."""
        response = web_client.get(
            "/error",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "unknown error" in response.text.lower()

    def test_error_endpoint_upload_error(self, web_client: TestClient) -> None:
        """Test error endpoint with upload error type."""
        response = web_client.get(
            "/error?type=uploadError",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "ELF" in response.text

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    @patch("app.web.endpoints.web.TaskManager")
    def test_get_models_json_response(self, mock_task_manager: Any, mock_ml_persistance: Any, web_client: TestClient) -> None:
        """Test get models endpoint returns JSON for API clients."""
        mock_ml_persistance.get_models_list = AsyncMock(return_value={"model1", "model2"})
        mock_task_manager.get_all_status.return_value = {}

        response = web_client.get(
            "/getModels",
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert set(data["models"]) == {"model1", "model2"}

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    @patch("app.web.endpoints.web.TaskManager")
    def test_get_models_html_response(self, mock_task_manager: Any, mock_ml_persistance: Any, web_client: TestClient) -> None:
        """Test get models endpoint returns HTML for browsers."""
        mock_ml_persistance.get_models_list = AsyncMock(return_value={"model1", "model2"})
        mock_task_manager.get_all_status.return_value = {}

        response = web_client.get(
            "/getModels",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_predictions_json_response(self, mock_pred_persistance: Any, web_client: TestClient) -> None:
        """Test get predictions endpoint returns JSON for API clients."""
        mock_pred_persistance.get_predictions_list = AsyncMock(return_value=[])

        response = web_client.get(
            "/getPredictions",
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_predictions_html_response(self, mock_pred_persistance: Any, web_client: TestClient) -> None:
        """Test get predictions endpoint returns HTML for browsers."""
        mock_pred_persistance.get_predictions_list = AsyncMock(return_value=[])

        response = web_client.get(
            "/getPredictions",
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_json_success(self, mock_func_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction details returns JSON on success."""
        mock_func_persistance.get_function = AsyncMock(return_value={
            "model_name": "test_model",
            "function_name": "test_func",
            "entrypoint": "0x1000",
            "tokens": "test tokens",
        })
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "prediction tokens",
        })

        response = web_client.get(
            "/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_name" in data
        assert "model_name" in data

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_function_not_found(self, mock_func_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction details returns 404 when function not found."""
        mock_func_persistance.get_function = AsyncMock(return_value=None)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "prediction tokens",
        })

        response = web_client.get(
            "/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_prediction_not_found(self, mock_func_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction details returns 404 when prediction not found."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_model_info)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value=None)

        response = web_client.get(
            "/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_prediction_json_response(self, mock_pred_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction returns JSON for API clients."""
        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"
        mock_prediction.model_name = "test_model"
        mock_prediction.predictions = []
        mock_pred_persistance.get_predictions = AsyncMock(return_value=mock_prediction)

        response = web_client.get(
            "/getPrediction",
            params={"task_name": "test_task", "model_name": "test_model"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "task_name" in data
        assert "model_name" in data

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_prediction_html_response(self, mock_pred_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction returns HTML for browsers."""
        mock_prediction = Mock()
        mock_prediction.task_name = "test_task"
        mock_prediction.model_name = "test_model"
        mock_prediction.predictions = []
        mock_pred_persistance.get_predictions = AsyncMock(return_value=mock_prediction)

        response = web_client.get(
            "/getPrediction",
            params={"task_name": "test_task", "model_name": "test_model"},
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200

    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_get_prediction_not_found(self, mock_pred_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction returns 404 when not found."""
        mock_pred_persistance.get_predictions = AsyncMock(return_value=None)

        response = web_client.get(
            "/getPrediction",
            params={"task_name": "missing", "model_name": "missing"},
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 404

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_html_response(self, mock_func_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction details returns HTML for browsers."""
        mock_model_info = Mock()
        mock_model_info.tokens = "test tokens"
        mock_func_persistance.get_function = AsyncMock(return_value=mock_model_info)
        mock_func_persistance.get_prediction_function = AsyncMock(return_value={
            "tokens": "prediction tokens",
        })

        response = web_client.get(
            "/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @patch("app.web.endpoints.web.FunctionPersistanceUtil")
    def test_get_prediction_details_type_error(self, mock_func_persistance: Any, web_client: TestClient) -> None:
        """Test get prediction details returns 400 on TypeError."""
        mock_func_persistance.get_function = AsyncMock(side_effect=TypeError("bad data"))

        response = web_client.get(
            "/getPredictionDetails",
            params={
                "model_name": "test_model",
                "function_name": "test_func",
                "task_name": "test_task",
            },
            headers={"Accept": "application/json"},
        )

        assert response.status_code == 400

    def test_dangerous_functions_page(self, web_client: TestClient) -> None:
        """Test dangerous functions page loads."""
        response = web_client.get(
            "/getDangerousFunctions",
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    def test_profile_page(self, web_client: TestClient) -> None:
        """Test profile page loads."""
        response = web_client.get(
            "/profile",
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    def test_binary_library_page(self, web_client: TestClient) -> None:
        """Test binary library page loads."""
        response = web_client.get(
            "/binary-library",
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    def test_binary_detail_page(self, web_client: TestClient) -> None:
        """Test binary detail page loads."""
        response = web_client.get(
            "/binary/42",
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    @patch("app.web.endpoints.web.MLPersistanceUtil")
    def test_run_task_page(self, mock_ml_persistance: Any, web_client: TestClient) -> None:
        """Test run task page loads."""
        mock_ml_persistance.get_models_list = AsyncMock(return_value=["model1"])
        response = web_client.get(
            "/run-task",
            params={"binary_id": 1, "binary_name": "test.bin"},
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    def test_create_model_page(self, web_client: TestClient) -> None:
        """Test create model page loads."""
        response = web_client.get(
            "/create-model",
            params={"binary_id": 1},
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    def test_create_prediction_page(self, web_client: TestClient) -> None:
        """Test create prediction page loads."""
        response = web_client.get(
            "/create-prediction",
            params={"binary_id": 1},
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    def test_task_results_page(self, web_client: TestClient) -> None:
        """Test task results page loads."""
        response = web_client.get(
            "/task-results",
            params={"task_uuid": "test-uuid"},
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    def test_similarity_dashboard_page(self, web_client: TestClient) -> None:
        """Test similarity dashboard page loads."""
        response = web_client.get(
            "/similarity-dashboard",
            headers={"Accept": "text/html"},
        )
        assert response.status_code == 200

    @patch("app.database.sql_service.SQLUtil")
    @patch("app.web.endpoints.web.MLPersistanceUtil")
    @patch("app.web.endpoints.web.PredictionPersistanceUtil")
    def test_home_stats(
        self,
        mock_pred_persistance: Any,
        mock_ml_persistance: Any,
        mock_sql: Any,
        web_client: TestClient,
    ) -> None:
        """Test home stats endpoint."""
        mock_sql.get_binaries_by_user = AsyncMock(return_value=[1, 2, 3])
        mock_ml_persistance.get_models_list = AsyncMock(return_value={"model1", "model2"})
        mock_pred_persistance.get_predictions_list = AsyncMock(return_value=[Mock(), Mock()])

        response = web_client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["binaries"] == 3
        assert data["models"] == 2
        assert data["predictions"] == 2

    # Tests for login/register pages (need separate client without auth override)
    def test_login_page_shows_login_form(self) -> None:
        """Test login page shows form when not authenticated."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user

        app = FastAPI()
        app.include_router(web_router)
        app.dependency_overrides[get_optional_user] = lambda: None
        try:
            app.mount("/static", StaticFiles(directory="static"), name="static")
        except Exception as exc:
            logger.debug("Failed to mount static files: %s", exc)

        with TestClient(app) as test_client:
            response = test_client.get(
                "/login",
                headers={"Accept": "text/html"},
            )
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")

    def test_login_page_redirects_when_authenticated(self) -> None:
        """Test login page redirects to home when already authenticated."""
        from fastapi import FastAPI
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user

        app = FastAPI()
        app.include_router(web_router)

        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = "testuser"
        app.dependency_overrides[get_optional_user] = lambda: mock_user

        with TestClient(app) as test_client:
            response = test_client.get(
                "/login",
                headers={"Accept": "text/html"},
                follow_redirects=False,
            )
            assert response.status_code == 307

    def test_register_page_shows_form(self) -> None:
        """Test register page shows form when not authenticated."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user

        app = FastAPI()
        app.include_router(web_router)
        app.dependency_overrides[get_optional_user] = lambda: None
        try:
            app.mount("/static", StaticFiles(directory="static"), name="static")
        except Exception as exc:
            logger.debug("Failed to mount static files: %s", exc)

        with TestClient(app) as test_client:
            response = test_client.get(
                "/register",
                headers={"Accept": "text/html"},
            )
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")

    def test_register_page_redirects_when_authenticated(self) -> None:
        """Test register page redirects when already authenticated."""
        from fastapi import FastAPI
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user

        app = FastAPI()
        app.include_router(web_router)

        mock_user = Mock()
        mock_user.id = 1
        mock_user.username = "testuser"
        app.dependency_overrides[get_optional_user] = lambda: mock_user

        with TestClient(app) as test_client:
            response = test_client.get(
                "/register",
                headers={"Accept": "text/html"},
                follow_redirects=False,
            )
            assert response.status_code == 307

    # Tests for login POST handler (lines 283-331)
    @patch("app.web.endpoints.web.get_settings")
    def test_login_submit_success(
        self,
        mock_get_settings: Any,
    ) -> None:
        """Test successful login with form data."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db, get_jwt_handler

        mock_settings = Mock()
        mock_settings.use_https = False
        mock_settings.access_token_expire_minutes = 30
        mock_settings.refresh_token_expire_days = 7
        mock_get_settings.return_value = mock_settings

        mock_jwt = Mock()
        mock_jwt.create_access_token = Mock(return_value="access_token_value")
        mock_jwt.create_refresh_token = Mock(return_value="refresh_token_value")

        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        mock_user = Mock()
        mock_user.id = 1
        mock_user.is_active = True
        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.verify_credentials = AsyncMock(return_value=mock_user)
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            app.dependency_overrides[get_jwt_handler] = lambda: mock_jwt
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/login",
                    data={"username": "testuser", "password": "testpass"},
                    follow_redirects=False,
                )
                assert response.status_code == 303

    @patch("app.web.endpoints.web.get_settings")
    def test_login_submit_json_body(
        self,
        mock_get_settings: Any,
    ) -> None:
        """Test successful login with JSON body."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db, get_jwt_handler

        mock_settings = Mock()
        mock_settings.use_https = False
        mock_settings.access_token_expire_minutes = 30
        mock_settings.refresh_token_expire_days = 7
        mock_get_settings.return_value = mock_settings

        mock_jwt = Mock()
        mock_jwt.create_access_token = Mock(return_value="access_token_value")
        mock_jwt.create_refresh_token = Mock(return_value="refresh_token_value")

        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        mock_user = Mock()
        mock_user.id = 1
        mock_user.is_active = True
        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.verify_credentials = AsyncMock(return_value=mock_user)
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            app.dependency_overrides[get_jwt_handler] = lambda: mock_jwt
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/login",
                    json={"username": "testuser", "password": "testpass"},
                    follow_redirects=False,
                )
                assert response.status_code == 303

    def test_login_submit_invalid_credentials(self) -> None:
        """Test login with invalid credentials returns error page."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db, get_jwt_handler

        mock_jwt = Mock()
        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.verify_credentials = AsyncMock(return_value=None)
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            app.dependency_overrides[get_jwt_handler] = lambda: mock_jwt
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/login",
                    data={"username": "testuser", "password": "wrongpass"},
                )
                assert response.status_code == 200
                assert "Incorrect username or password" in response.text

    def test_login_submit_inactive_user(self) -> None:
        """Test login with inactive user returns error page."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db, get_jwt_handler

        mock_jwt = Mock()
        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        mock_user = Mock()
        mock_user.id = 1
        mock_user.is_active = False
        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.verify_credentials = AsyncMock(return_value=mock_user)
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            app.dependency_overrides[get_jwt_handler] = lambda: mock_jwt
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/login",
                    data={"username": "testuser", "password": "testpass"},
                )
                assert response.status_code == 200
                assert "User account is disabled" in response.text

    # Tests for register POST handler (lines 360-406)
    def test_register_submit_success(self) -> None:
        """Test successful registration redirects to login."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db

        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        mock_user = Mock()
        mock_user.id = 1
        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.get_by_username = AsyncMock(return_value=None)
            mock_user_repo.get_by_email = AsyncMock(return_value=None)
            mock_user_repo.create_user = AsyncMock(return_value=mock_user)
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/register",
                    data={
                        "username": "newuser",
                        "email": "new@example.com",
                        "password": "testpass",
                        "full_name": "New User",
                    },
                    follow_redirects=False,
                )
                assert response.status_code == 303

    def test_register_submit_json_body(self) -> None:
        """Test successful registration with JSON body."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db

        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        mock_user = Mock()
        mock_user.id = 1
        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.get_by_username = AsyncMock(return_value=None)
            mock_user_repo.get_by_email = AsyncMock(return_value=None)
            mock_user_repo.create_user = AsyncMock(return_value=mock_user)
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/register",
                    json={
                        "username": "newuser",
                        "email": "new@example.com",
                        "password": "testpass",
                        "full_name": "New User",
                    },
                    follow_redirects=False,
                )
                assert response.status_code == 303

    def test_register_submit_username_exists(self) -> None:
        """Test registration with existing username returns error."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db

        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.get_by_username = AsyncMock(return_value=Mock())
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/register",
                    data={
                        "username": "existing",
                        "email": "new@example.com",
                        "password": "testpass",
                    },
                )
                # Template returns 200 with register.html (error passed but not rendered server-side)
                assert response.status_code == 200
                assert "REGISTER" in response.text

    def test_register_submit_email_exists(self) -> None:
        """Test registration with existing email returns error."""
        from fastapi import FastAPI
        from fastapi.staticfiles import StaticFiles
        from app.web.endpoints.web import router as web_router
        from app.auth.dependencies import get_optional_user, get_db

        mock_db = AsyncMock()

        async def mock_db_gen():
            yield mock_db

        with patch("app.web.endpoints.web.UserRepository") as mock_user_repo_cls:
            mock_user_repo = Mock()
            mock_user_repo.get_by_username = AsyncMock(return_value=None)
            mock_user_repo.get_by_email = AsyncMock(return_value=Mock())
            mock_user_repo_cls.return_value = mock_user_repo

            app = FastAPI()
            app.include_router(web_router)
            app.dependency_overrides[get_optional_user] = lambda: None
            app.dependency_overrides[get_db] = mock_db_gen
            try:
                app.mount("/static", StaticFiles(directory="static"), name="static")
            except Exception as exc:
                logger.debug("Failed to mount static files: %s", exc)

            with TestClient(app) as test_client:
                response = test_client.post(
                    "/register",
                    data={
                        "username": "newuser",
                        "email": "existing@example.com",
                        "password": "testpass",
                    },
                )
                # Template returns 200 with register.html (error passed but not rendered server-side)
                assert response.status_code == 200
                assert "REGISTER" in response.text
