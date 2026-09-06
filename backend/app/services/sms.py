"""The single outbound-SMS seam. A real gateway plugs in here; callers don't change.

    send_sms(phone_number, message, category=..., case_id=...)
"""
import logging

from sqlalchemy.orm import Session

from app.models.sms import SmsCategory, SmsMessage

logger = logging.getLogger(__name__)


def send_sms(
    db: Session,
    phone_number: str | None,
    message: str,
    *,
    category: SmsCategory,
    case_id: str | None = None,
) -> SmsMessage:
    """STUB: log the message and record it in `sms_messages`. Returns the row.

    Swap the body for a real gateway call (Twilio, MSG91, ...) later — the
    signature and the `sms_messages` audit row stay the same.
    """
    logger.info("[SMS:%s] to=%s :: %s", category.value, phone_number, message)
    row = SmsMessage(
        to_phone=phone_number,
        category=category,
        message=message,
        case_id=case_id,
        provider="stub",
    )
    db.add(row)
    db.flush()  # caller owns the commit
    return row
