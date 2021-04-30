# -*- coding: utf-8 -*-

import re
import uuid
from typing import Optional

import xmltodict
from evernote.edam.type.ttypes import Note, Resource

from evernote_backup.note_formatter_util import fmt_binary, fmt_content, fmt_time


class NoteFormatter(object):
    """https://xml.evernote.com/pub/evernote-export3.dtd"""

    def __init__(self) -> None:
        self._raw_elements: dict = {}

    def format_note(self, note: Note) -> str:
        self._raw_elements = {}

        note_skeleton = {
            "note": {
                "title": note.title,
                "created": fmt_time(note.created),
                "updated": fmt_time(note.updated),
                "tag": note.tagNames,
                "note-attributes": None,
                "content": self._fmt_raw(fmt_content(note.content)),
                "resource": map(self._fmt_resource, note.resources or []),
            }
        }

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
                "reminder-time": note.attributes.reminderTime,
                "reminder-done-time": note.attributes.reminderDoneTime,
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
