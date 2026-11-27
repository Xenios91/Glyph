"""Repository for ScanReport entity database operations."""

from app.database.models import ScanReport
from app.database.scan_report_repository_base import ScanReportRepositoryBase


class ScanReportRepository(ScanReportRepositoryBase):
    """Repository for ScanReport CRUD operations.

    All methods manage their own database sessions via
    get_async_session/close_async_session (inherited from
    :class:`ScanReportRepositoryBase`).
    """

    model = ScanReport
    label = "scan report"
