"""Repository for BehavioralScanReport entity database operations."""

from app.database.models import BehavioralScanReport
from app.database.scan_report_repository_base import ScanReportRepositoryBase


class BehavioralScanReportRepository(ScanReportRepositoryBase):
    """Repository for BehavioralScanReport CRUD operations.

    All methods manage their own database sessions via
    get_async_session/close_async_session (inherited from
    :class:`ScanReportRepositoryBase`).
    """

    model = BehavioralScanReport
    label = "behavioral scan report"
