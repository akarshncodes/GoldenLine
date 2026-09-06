"""ORM models package.

Every model module must be imported here so that Alembic autogenerate and
`Base.metadata.create_all` see the tables.
"""
from app.models.assessment import Assessment  # noqa: F401
from app.models.auth import (  # noqa: F401
    DeletionRequest,
    DuplicateMergeLog,
    OtpVerification,
    PasswordResetToken,
    RateLimitFlag,
    User,
)
from app.models.bed_category import BedCategory  # noqa: F401
from app.models.bed_lock import BedLock, ConflictLog  # noqa: F401
from app.models.blood import BloodBank, BloodBankHold, BloodCheck  # noqa: F401
from app.models.case import Case  # noqa: F401
from app.models.case_note import CaseNote  # noqa: F401
from app.models.control_room import Flag  # noqa: F401
from app.models.feedback import CaseFeedback, FeedbackInvite  # noqa: F401
from app.models.handoff import QrHandoffToken  # noqa: F401
from app.models.hospital import Hospital  # noqa: F401
from app.models.hospital_bed_report import HospitalBedReport  # noqa: F401
from app.models.hospital_inventory import HospitalInventoryItem, HospitalInventoryMovement  # noqa: F401
from app.models.hospital_staff import HospitalStaffMember  # noqa: F401
from app.models.hospital_sync import HospitalSyncEvent  # noqa: F401
from app.models.import_session import ImportSession  # noqa: F401
from app.models.patient import BedAssignment, Patient  # noqa: F401
from app.models.prep import PrepAction  # noqa: F401
from app.models.route import (  # noqa: F401
    CaseRoute,
    TrafficAlert,
    Waypoint,
    WaypointSuggestion,
)
from app.models.sms import SmsMessage  # noqa: F401
from app.models.staff_attendance import StaffAttendance  # noqa: F401
from app.models.tracking import CaseTrackingToken  # noqa: F401
