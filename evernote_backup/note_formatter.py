# -*- coding: utf-8 -*-
import json
import re
import uuid
from typing import List, Optional

import xmltodict
from evernote.edam.type.ttypes import Note, Resource

from evernote_backup.evernote_types import Reminder, Task
from evernote_backup.note_formatter_util import fmt_binary, fmt_content, fmt_time


class NoteFormatter(object):
    """https://xml.evernote.com/pub/evernote-export3.dtd"""

    def __init__(self, add_guid: bool = False) -> None:
        self._raw_elements: dict = {}
        self.add_guid = add_guid

    def format_note(self, note: Note, note_tasks: List[Task]) -> str:
        self._raw_elements = {}

        note_skeleton = {
            "note": {
                "title": note.title,
                "created": fmt_time(note.created),
                "updated": fmt_time(note.updated),
                "tag": note.tagNames,
                "note-attributes": {},
                "content": self._fmt_raw(fmt_content(note.content)),
                "resource": map(self._fmt_resource, note.resources or []),
                "task": map(self._fmt_task, note_tasks or []),
            }
        }

        if self.add_guid:
            note_skeleton["note"]["guid"] = note.guid

        if note.attributes:
            note_skeleton["note"]["note-attributes"] = {
                "subject-date": fmt_time(note.attributes.subjectDate),
                "latitude": note.attributes.latitude,
                "longitude": note.attributes.longitude,
                "altitude": note.attributes.altitude,
                "author": note.attributes.author,
                "source": note.attributes.source,
                "source-url": note.attributes.sourceURL,
                "source-application": note.attributes.sourceApplication,
                "reminder-order": note.attributes.reminderOrder,
                "reminder-time": fmt_time(note.attributes.reminderTime),
                "reminder-done-time": fmt_time(note.attributes.reminderDoneTime),
                "place-name": note.attributes.placeName,
                "content-class": note.attributes.contentClass,
            }

        note_template = xmltodict.unparse(
            note_skeleton,
            pretty=True,
            short_empty_elements=True,
            full_document=False,
            indent="  ",
            depth=1,
        )

        # Remove empty tags
        note_template = re.sub(r"^\s+<.*?/>\n", "", note_template, flags=re.M)

        for r_uuid, r_body in self._raw_elements.items():
            note_template = note_template.replace(r_uuid, r_body)

        return str(note_template)

    def _fmt_resource(self, resource: Resource) -> dict:
        return {
            "data": {
                "@encoding": "base64",
                "#text": self._fmt_raw(fmt_binary(resource.data.body)),
            },
            "mime": resource.mime,
            "width": resource.width,
            "height": resource.height,
            "duration": resource.duration,
            "resource-attributes": {
                "source-url": resource.attributes.sourceURL,
                "timestamp": fmt_time(resource.attributes.timestamp),
                "latitude": resource.attributes.latitude,
                "longitude": resource.attributes.longitude,
                "altitude": resource.attributes.altitude,
                "camera-make": resource.attributes.cameraMake,
                "camera-model": resource.attributes.cameraModel,
                "reco-type": resource.attributes.recoType,
                "file-name": resource.attributes.fileName,
                "attachment": resource.attributes.attachment,
            },
        }

    def _fmt_raw(self, body: Optional[str]) -> Optional[str]:
        if body is None:
            return body
        content_uuid = str(uuid.uuid4())
        self._raw_elements[content_uuid] = body
        return content_uuid

    # <!ELEMENT task
    #  (title, created, updated, taskStatus, inNote, taskFlag, sortWeight,
    #   noteLevelID, taskGroupNoteLevelID, dueDate?, dueDateUIOption?, timeZone?,
    #   recurrence?, repeatAfterCompletion?, statusUpdated?, creator?, lastEditor?,
    #   reminder*)
    # >
    def _fmt_task(self, task: Task) -> dict:
        return {
            "title": task.label,
            "created": fmt_time(task.created),
            "updated": fmt_time(task.updated),
            "taskStatus": task.status,
            # not exported by Evernote client
            # "inNote": task.inNote,
            "taskFlag": task.flag,
            "sortWeight": task.sortWeight,
            "noteLevelID": task.noteLevelID,
            "taskGroupNoteLevelID": task.taskGroupNoteLevelID,
            "dueDate": fmt_time(task.dueDate),
            "dueDateUIOption": task.dueDateUIOption,
            "timeZone": task.timeZone,
            "recurrence": task.recurrence and json.dumps(task.recurrence)[1:-1],
            "repeatAfterCompletion": task.repeatAfterCompletion,
            "statusUpdated": fmt_time(task.statusUpdated),
            "creator": task.creator,
            "lastEditor": task.lastEditor,
            "reminder": map(self._fmt_reminder, task.reminders or []),
        }

    # <!ELEMENT reminder
    #   (created, updated, noteLevelID, reminderDate?, reminderDateUIOption?,
    #    timeZone?, dueDateOffset?, reminderStatus?)
    # >
    def _fmt_reminder(self, reminder: Reminder) -> dict:
        return {
            "created": fmt_time(reminder.created),
            "updated": fmt_time(reminder.updated),
            "noteLevelID": reminder.noteLevelID,
            "reminderDate": fmt_time(reminder.reminderDate),
            "reminderDateUIOption": reminder.reminderDateUIOption,
            "timeZone": reminder.timeZone,
            "dueDateOffset": reminder.dueDateOffset,
            "reminderStatus": reminder.status,
        }
