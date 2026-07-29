from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List
from zoneinfo import ZoneInfo


def _to_currency(amount: Decimal) -> Decimal:
    """Rounds a monetary amount to 2 decimal places using standard currency rounding."""
    return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Dict[str, Any]:
    """
    Calculates revenue for a specific calendar month, using the property's own
    local timezone to compute month boundaries (a UTC boundary would mis-bucket
    reservations that check in near midnight local time, e.g. late Feb 29 UTC
    that is already March 1st in Europe/Paris).
    """
    from app.core.database_pool import DatabasePool
    from sqlalchemy import text

    db_pool = DatabasePool()
    await db_pool.initialize()

    async with db_pool.get_session() as session:
        tz_result = await session.execute(
            text("SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"),
            {"property_id": property_id, "tenant_id": tenant_id},
        )
        tz_row = tz_result.fetchone()
        tz = ZoneInfo(tz_row.timezone if tz_row and tz_row.timezone else "UTC")

        start_date = datetime(year, month, 1, tzinfo=tz)
        end_date = datetime(year + 1, 1, 1, tzinfo=tz) if month == 12 else datetime(year, month + 1, 1, tzinfo=tz)

        result = await session.execute(
            text("""
                SELECT SUM(total_amount) as total_revenue, COUNT(*) as reservation_count
                FROM reservations
                WHERE property_id = :property_id AND tenant_id = :tenant_id
                AND check_in_date >= :start_date AND check_in_date < :end_date
            """),
            {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
        row = result.fetchone()

    total = _to_currency(Decimal(str(row.total_revenue))) if row and row.total_revenue else Decimal('0.00')

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(total),
        "currency": "USD",
        "count": row.reservation_count if row else 0,
    }

async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Import database pool
        from app.core.database_pool import DatabasePool
        
        # Initialize pool if needed
        db_pool = DatabasePool()
        await db_pool.initialize()
        
        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)
                
                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    total_revenue = _to_currency(Decimal(str(row.total_revenue)))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        
        # Create property-specific mock data for testing when DB is unavailable
        # This ensures each property shows different figures
        mock_data = {
            'prop-001': {'total': '1000.00', 'count': 3},
            'prop-002': {'total': '4975.50', 'count': 4}, 
            'prop-003': {'total': '6100.50', 'count': 2},
            'prop-004': {'total': '1776.50', 'count': 4},
            'prop-005': {'total': '3256.00', 'count': 3}
        }
        
        mock_property_data = mock_data.get(property_id, {'total': '0.00', 'count': 0})
        
        return {
            "property_id": property_id,
            "tenant_id": tenant_id, 
            "total": mock_property_data['total'],
            "currency": "USD",
            "count": mock_property_data['count']
        }
