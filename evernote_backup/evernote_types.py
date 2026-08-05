import json
from dataclasses import asdict, dataclass, field
from enum import IntEnum


# @evernote/tasks-data-model/dist/ReminderEntity.js
# <!--
#   Corresponds to the EDAM Task.Reminder type.
# -->
# <!ELEMENT reminder
#   (created, updated, noteLevelID, reminderDate?, reminderDateUIOption?,
#    timeZone?, dueDateOffset?, reminderStatus?)
# >
@dataclass
class Reminder:
    reminderId: str
    sourceId: str | None = None
    sourceType: int | None = None
    noteLevelID: str | None = None
    reminderDate: int | None = None
    reminderDateUIOption: str | None = None
    timeZone: str | None = None
    dueDateOffset: int | None = None
    status: str | None = None
    ownerId: int | None = None
    created: int | None = None
    updated: int | None = None

    def to_json(self) -> str:
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Reminder":
        return cls(**json.loads(json_str))


# @evernote/tasks-data-model/dist/TaskEntity.js
# <!--
#  Corresponds to the EDAM Task type.
# -->
# <!ELEMENT task
#  (title, created, updated, taskStatus, inNote, taskFlag, sortWeight,
#   noteLevelID, taskGroupNoteLevelID, dueDate?, dueDateUIOption?, timeZone?,
#   recurrence?, repeatAfterCompletion?, statusUpdated?, creator?, lastEditor?,
#   reminder*)
# >
@dataclass
class Task:
    taskId: str
    parentId: str | None = None
    parentType: int | None = None
    noteLevelID: str | None = None
    taskGroupNoteLevelID: str | None = None
    label: str | None = None
    description: str | None = None
    dueDate: int | None = None
    dueDateUIOption: str | None = None
    timeZone: str | None = None
    status: str | None = None
    statusUpdated: int | None = None
    inNote: bool | None = None
    flag: bool | None = None
    taskFlag: int | None = None
    priority: int | None = None
    idClock: int | None = None
    sortWeight: str | None = None
    creator: int | None = None
    lastEditor: int | None = None
    ownerId: int | None = None
    created: int | None = None
    updated: int | None = None
    assigneeEmail: str | None = None
    assigneeIdentityId: int | None = None
    assigneeUserId: int | None = None
    assignedByUserId: int | None = None
    recurrence: str | None = None
    repeatAfterCompletion: bool | None = None
    reminders: list[Reminder] = field(default_factory=list)

    def to_json(self) -> str:
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Task":
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class SharedNoteMembership:
    note_guid: str
    shard_id: str
    owner_id: int


@dataclass
class SyncChunkV2:
    last_timestamp: int
    tasks: list[Task] = field(default_factory=list)
    reminders: list[Reminder] = field(default_factory=list)
    expunged_tasks: list[str] = field(default_factory=list)
    expunged_reminders: list[str] = field(default_factory=list)
    # Single-note shares (v2 membership + NOTE entity events)
    shared_note_memberships: list[SharedNoteMembership] = field(default_factory=list)
    expunged_shared_note_memberships: list[str] = field(default_factory=list)
    notes_to_sync: list[str] = field(default_factory=list)
    expunged_notes: list[str] = field(default_factory=list)


# @evernote/data-model/dist/sync-types/SyncDocuments.js
class EvernoteSyncOperationType(IntEnum):
    ACCESS_FANOUT = 0
    CREATE = 1
    UPDATE = 2
    DELETE = 3
    EXPUNGE = 4
    MIGRATE = 5
    WITH_ENTITY_CREATE = 6
    FORCE_FANOUT = 7
    NOTIFY = 8


EVERNOTE_DEL_OPERATIONS = {
    EvernoteSyncOperationType.DELETE,
    EvernoteSyncOperationType.EXPUNGE,
}


# @evernote/data-model/dist/sync-types/SyncInstances.js
class EvernoteSyncInstanceType(IntEnum):
    AGENT = 0
    ENTITY = 1
    MEMBERSHIP = 2
    ASSOCIATION = 3


# @evernote/data-model/dist/sync-types/CommonTypes.js
class EvernoteAgentType(IntEnum):
    PUBLIC = 0
    IDENTITY = 1
    USER = 2
    BUSINESS = 3
    PROFILE = 4


# @evernote/data-model/dist/sync-types/CommonTypes.js
class EvernoteMembershipType(IntEnum):
    INVITATION = 0
    SHARE = 1


# @evernote/data-model/dist/EntityTypes.js
class EvernoteEntityType(IntEnum):
    NOTE = 0
    NOTEBOOK = 1
    WORKSPACE = 2
    ATTACHMENT = 3
    TAG = 4
    SAVED_SEARCH = 5
    PREFERENCES = 6
    RECIPIENT_SETTINGS = 7
    NOTE_TAGS = 8
    NOTE_ATTACHMENTS = 9
    ACCESS_INFO = 10
    MUTATION_TRACKER = 11
    BOARD = 12
    WIDGET = 13
    NOTE_CONTENT_INFO = 14
    TASK = 15
    REMINDER = 16
    TASK_USER_SETTINGS = 17
    WIDGET_CONTENT_CONFLICT = 18
    SCHEDULED_NOTIFICATION = 19
    GAMIFICATION_SUMMARY = 20
    GAMIFICATION_MILESTONE = 21
    GAMIFICATION_GOAL = 22
    CALENDAR_SETTINGS = 23
    CALENDAR_ACCOUNT = 24
    USER_CALENDAR_SETTINGS = 25
    CALENDAR_EVENT = 26
    GAMIFICATION_LEVEL = 27
    TASK_OUTLIER = 28
    PROMOTION = 29
    SCORES = 30
    COMMENT = 31
    COMMENT_THREAD = 32
    WORKSPACE_PINNED_CONTENT_LIST = 33
    WORKSPACE_USER_INTERFACE_PROPERTIES = 34
    USER_CONTENT_METADATA = 35
    EXAMPLE_PARENT = 998
    EXAMPLE = 999
