import json
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Optional


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
    sourceId: Optional[str] = None
    sourceType: Optional[int] = None
    noteLevelID: Optional[str] = None
    reminderDate: Optional[int] = None
    reminderDateUIOption: Optional[str] = None
    timeZone: Optional[str] = None
    dueDateOffset: Optional[int] = None
    status: Optional[str] = None
    ownerId: Optional[int] = None
    created: Optional[int] = None
    updated: Optional[int] = None

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
    parentId: Optional[str] = None
    parentType: Optional[int] = None
    noteLevelID: Optional[str] = None
    taskGroupNoteLevelID: Optional[str] = None
    label: Optional[str] = None
    description: Optional[str] = None
    dueDate: Optional[int] = None
    dueDateUIOption: Optional[str] = None
    timeZone: Optional[str] = None
    status: Optional[str] = None
    statusUpdated: Optional[int] = None
    inNote: Optional[bool] = None
    flag: Optional[bool] = None
    taskFlag: Optional[int] = None
    priority: Optional[int] = None
    idClock: Optional[int] = None
    sortWeight: Optional[str] = None
    creator: Optional[int] = None
    lastEditor: Optional[int] = None
    ownerId: Optional[int] = None
    created: Optional[int] = None
    updated: Optional[int] = None
    assigneeEmail: Optional[str] = None
    assigneeIdentityId: Optional[int] = None
    assigneeUserId: Optional[int] = None
    assignedByUserId: Optional[int] = None
    recurrence: Optional[str] = None
    repeatAfterCompletion: Optional[bool] = None
    reminders: list[Reminder] = field(default_factory=list)

    def to_json(self) -> str:
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Task":
        data = json.loads(json_str)
        return cls(**data)


@dataclass
class SyncChunkV2:
    last_timestamp: int
    tasks: list[Task] = field(default_factory=list)
    reminders: list[Reminder] = field(default_factory=list)
    expunged_tasks: list[str] = field(default_factory=list)
    expunged_reminders: list[str] = field(default_factory=list)


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
