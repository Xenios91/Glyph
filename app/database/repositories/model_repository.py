"""Repository for model database operations."""

import logging
from io import BytesIO

import joblib
from sqlalchemy.orm import Session

from app.database.models import Model
from app.database.session_handler import get_session

logger = logging.getLogger(__name__)


class ModelRepository:
    """Repository for managing model data in the database."""

    @staticmethod
    def save_model(model_name: str, label_encoder: object, model_bytes: bytes) -> Model:
        """Save a model to the database.

        Args:
            model_name: Name of the model to save.
            label_encoder: The label encoder to save.
            model_bytes: The model bytes to save.

        Returns:
            The created Model instance.
        """
        with get_session("models") as session:
            # Serialize label encoder
            label_encoder_buffer = BytesIO()
            joblib.dump(label_encoder, label_encoder_buffer)
            label_encoder_bytes = label_encoder_buffer.getvalue()

            # Create model instance
            model = Model(
                model_name=model_name,
                model_data=model_bytes,
                label_encoder_data=label_encoder_bytes,
            )
            session.add(model)
            return model

    @staticmethod
    def get_models_list() -> set[str]:
        """Get the list of model names from the database.

        Returns:
            A set of model names.
        """
        with get_session("models") as session:
            models = session.query(Model).all()
            return {model.model_name for model in models}

    @staticmethod
    def get_model(model_name: str) -> Model | None:
        """Retrieve a model from the database.

        Args:
            model_name: Name of the model to retrieve.

        Returns:
            The Model instance if found, otherwise None.
        """
        with get_session("models") as session:
            model = session.query(Model).filter(Model.model_name == model_name).first()
            if model:
                return model
            logger.warning("Model '%s' not found.", model_name)
            return None

    @staticmethod
    def delete_model(model_name: str) -> bool:
        """Delete a model from the database.

        Args:
            model_name: Name of the model to delete.

        Returns:
            True if the model was deleted, False if not found.
        """
        with get_session("models") as session:
            model = session.query(Model).filter(Model.model_name == model_name).first()
            if model:
                session.delete(model)
                logger.info(f"Model '{model_name}' deleted successfully.")
                return True
            logger.warning("Model '%s' not found for deletion.", model_name)
            return False

    @staticmethod
    def get_model_data(model_name: str) -> tuple[object, object] | None:
        """Retrieve and deserialize model data from the database.

        Args:
            model_name: Name of the model to retrieve.

        Returns:
            Tuple of (label_encoder, model) if found, otherwise None.
        """
        model = ModelRepository.get_model(model_name)
        if model is None:
            return None

        try:
            label_encoder = joblib.load(BytesIO(model.label_encoder_data))
            model_obj = joblib.load(BytesIO(model.model_data))
            return label_encoder, model_obj
        except Exception as e:
            logger.error(f"Failed to deserialize model '{model_name}': {e}")
            return None
