"""CSV export service for campaign leads."""

import csv
import io
from typing import Any

from sqlalchemy.orm import Session

from src.models.lead import Lead


DEFAULT_COLUMNS = [
    "first_name",
    "last_name",
    "email",
    "email_status",
    "phone",
    "title",
    "seniority",
    "company_name",
    "company_industry",
    "company_size",
    "company_location",
    "score",
    "score_reason",
    "status",
    "linkedin_url",
]

COLUMN_HEADERS = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email",
    "email_status": "Email Status",
    "phone": "Phone",
    "title": "Title",
    "seniority": "Seniority",
    "company_name": "Company",
    "company_industry": "Industry",
    "company_size": "Company Size",
    "company_location": "Location",
    "company_domain": "Domain",
    "company_revenue": "Revenue",
    "score": "Score",
    "score_reason": "Score Reason",
    "status": "Status",
    "linkedin_url": "LinkedIn",
    "department": "Department",
    "headline": "Headline",
}


_CSV_INJECTION_CHARS = frozenset("=+-@\t\r")


def _sanitize_csv_cell(value: object) -> str:
    """Sanitize a cell value to prevent CSV formula injection.

    Prefixes cells starting with dangerous characters (=, +, -, @, tab, CR)
    with a single quote so spreadsheet apps treat them as text.
    """
    s = str(value) if value is not None else ""
    if s and s[0] in _CSV_INJECTION_CHARS:
        return f"'{s}"
    return s


def export_leads_csv(
    db: Session,
    campaign_id: str,
    min_score: int = 0,
    status_filter: str | None = None,
    columns: list[str] | None = None,
) -> str:
    """
    Export campaign leads as a CSV string.

    Args:
        db: Database session.
        campaign_id: Campaign to export.
        min_score: Minimum score filter.
        status_filter: Optional status filter.
        columns: Columns to include (defaults to DEFAULT_COLUMNS).

    Returns:
        CSV content as a string.
    """
    cols = columns or DEFAULT_COLUMNS
    # Validate columns
    cols = [c for c in cols if c in COLUMN_HEADERS]

    query = db.query(Lead).filter(Lead.campaign_id == campaign_id)
    if min_score > 0:
        query = query.filter(Lead.score >= min_score)
    if status_filter:
        query = query.filter(Lead.status == status_filter)

    leads = query.order_by(Lead.score.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([COLUMN_HEADERS[c] for c in cols])

    # Data rows
    for lead in leads:
        row = [_sanitize_csv_cell(getattr(lead, col, "")) for col in cols]
        writer.writerow(row)

    return output.getvalue()
