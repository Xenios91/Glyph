"""Repository for SimilarityComputation and SimilarityPair entity database operations."""

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import SimilarityComputation, SimilarityPair
from app.database.session_handler import close_async_session, get_async_session


class SimilarityRepository:
    """Repository for SimilarityComputation and SimilarityPair CRUD operations.

    All methods manage their own database sessions via get_async_session/close_async_session.
    """

    @staticmethod
    async def create(
        task_name: str,
        computed_by: int,
        binary_count: int,
        status: str = "pending",
    ) -> SimilarityComputation:
        """Create a new similarity computation record.

        Args:
            task_name: Human-readable name for this computation.
            computed_by: User ID who initiated it.
            binary_count: Number of binaries being compared.
            status: Initial status.

        Returns:
            The created SimilarityComputation instance.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            comp = SimilarityComputation(
                task_name=task_name,
                computed_by=computed_by,
                binary_count=binary_count,
                total_comparisons=0,
                status=status,
            )
            session.add(comp)
            await session.commit()
            await session.refresh(comp)
            logger.info("Similarity computation '{}' created (id={})", task_name, comp.id)
            return comp
        except Exception:
            await session.rollback()
            logger.exception("Failed to create similarity computation '%s'", task_name)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def update_status(
        computation_id: int,
        status: str,
        total_comparisons: int | None = None,
    ) -> None:
        """Update status (and optionally total_comparisons) of a computation.

        Args:
            computation_id: Database id.
            status: New status string.
            total_comparisons: Optional override for total comparisons count.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            comp = await session.get(SimilarityComputation, computation_id)
            if comp is None:
                logger.warning("Similarity computation {} not found", computation_id)
                return
            comp.status = status
            if total_comparisons is not None:
                comp.total_comparisons = total_comparisons
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to update computation {}", computation_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def save_pairs(
        computation_id: int,
        pairs: list[SimilarityPair],
    ) -> None:
        """Bulk-insert similarity pair results.

        Args:
            computation_id: Parent computation id.
            pairs: List of SimilarityPair ORM instances to save.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            for pair in pairs:
                pair.computation_id = computation_id
                session.add(pair)
            await session.commit()
            logger.info(
                "Saved {} similarity pairs for computation {}",
                len(pairs),
                computation_id,
            )
        except Exception:
            await session.rollback()
            logger.exception("Failed to save similarity pairs for computation {}", computation_id)
            raise
        finally:
            await close_async_session(session)

    @staticmethod
    async def get(computation_id: int) -> SimilarityComputation | None:
        """Retrieve a similarity computation with its pairs.

        Args:
            computation_id: Database id.

        Returns:
            SimilarityComputation instance with loaded pairs, or None.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            result = await session.execute(
                select(SimilarityComputation)
                .options(selectinload(SimilarityComputation.pairs))
                .where(SimilarityComputation.id == computation_id)
            )
            comp = result.scalar_one_or_none()
            if comp is not None:
                session.expunge_all()
            return comp
        except Exception:
            logger.exception("Failed to retrieve computation {}", computation_id)
            return None
        finally:
            await close_async_session(session)

    @staticmethod
    async def list_all(
        computed_by: int | None = None,
    ) -> list[SimilarityComputation]:
        """List similarity computations, optionally filtered by user.

        Args:
            computed_by: Optional user ID filter.

        Returns:
            List of SimilarityComputation instances.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            stmt = select(SimilarityComputation)
            if computed_by is not None:
                stmt = stmt.where(SimilarityComputation.computed_by == computed_by)
            stmt = stmt.order_by(SimilarityComputation.created_at.desc())
            result = await session.execute(stmt)
            comps = list(result.scalars().all())
            session.expunge_all()
            return comps
        except Exception:
            logger.exception("Failed to list similarity computations")
            return []
        finally:
            await close_async_session(session)

    @staticmethod
    async def delete(computation_id: int) -> None:
        """Delete a similarity computation and its pairs.

        Args:
            computation_id: Database id.
        """
        session: AsyncSession = await get_async_session("intelligence")
        try:
            await session.execute(delete(SimilarityPair).where(SimilarityPair.computation_id == computation_id))
            await session.execute(delete(SimilarityComputation).where(SimilarityComputation.id == computation_id))
            await session.commit()
            logger.info("Similarity computation {} deleted", computation_id)
        except Exception:
            await session.rollback()
            logger.exception("Failed to delete computation {}", computation_id)
            raise
        finally:
            await close_async_session(session)
