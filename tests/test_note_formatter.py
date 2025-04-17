from evernote.edam.type.ttypes import (
    Data,
    Note,
    NoteAttributes,
    Resource,
    ResourceAttributes,
)

from evernote_backup.evernote_types import Reminder, Task
from evernote_backup.note_formatter import NoteFormatter

test_note_data = Note(
    guid="7473cb3f-411e-4545-9df4-5eb731de4358",
    title="Test Title",
    content="<test content>",
    contentHash=b"1234",
    contentLength=2706,
    created=1612902877000,
    updated=1617813805000,
    active=True,
    updateSequenceNum=6711,
    notebookGuid="c2ab541f-b704-4051-a2fa-40805e0fbf74",
    tagGuids=[
        "a51d61c3-8ff6-475f-b7ac-d72caf2ec84d",
        "9e7d0ea5-9ff8-46c7-9b43-ccc468ba1adb",
    ],
    resources=[
        Resource(
            guid="fe747857-92ea-4633-b415-6b9946f67519",
            noteGuid="7473cb3f-411e-4545-9df4-5eb731de4358",
            mime="image/png",
            width=403,
            height=613,
            active=True,
            recognition=Data(bodyHash=b"1234", size=4332, body=b"1234"),
            data=Data(bodyHash=b"1234", size=58387, body=b"1234"),
            updateSequenceNum=6461,
            attributes=ResourceAttributes(
                fileName="test.png",
                attachment=True,
            ),
        )
    ],
    attributes=NoteAttributes(
        author="test@gmail.com",
        source="desktop.win",
        sourceURL="https://www.example.com/page?category=blog&post_id=123",
        sourceApplication="evernote.win32",
        reminderOrder=100,
        reminderTime=1744008231000,
        reminderDoneTime=1744018231000,
    ),
    tagNames=["test1", "test2"],
)


expected = """  <note>
    <title>Test Title</title>
    <created>20210209T203437Z</created>
    <updated>20210407T164325Z</updated>
    <tag>test1</tag>
    <tag>test2</tag>
    <note-attributes>
      <author>test@gmail.com</author>
      <source>desktop.win</source>
      <source-url>https://www.example.com/page?category=blog&amp;post_id=123</source-url>
      <source-application>evernote.win32</source-application>
      <reminder-order>100</reminder-order>
      <reminder-time>20250407T064351Z</reminder-time>
      <reminder-done-time>20250407T093031Z</reminder-done-time>
    </note-attributes>
    <content>
      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<test content>]]>
    </content>
    <resource>
      <data encoding="base64">
MTIzNA==
      </data>
      <mime>image/png</mime>
      <width>403</width>
      <height>613</height>
      <resource-attributes>
        <file-name>test.png</file-name>
        <attachment>true</attachment>
      </resource-attributes>
    </resource>
  </note>
"""

test_note_data_empty_tags = Note(
    guid="7473cb3f-411e-4545-9df4-5eb731de4358",
    title="Test Title",
    content="<test content>",
    contentHash=b"1234",
    contentLength=2706,
    created=1612902877000,
    updated=1617813805000,
    active=True,
    updateSequenceNum=6711,
    notebookGuid="c2ab541f-b704-4051-a2fa-40805e0fbf74",
    attributes=NoteAttributes(
        author="test@gmail.com",
        source="desktop.win",
        sourceApplication="evernote.win32",
    ),
)

expected_empty_tags = """  <note>
    <title>Test Title</title>
    <created>20210209T203437Z</created>
    <updated>20210407T164325Z</updated>
    <note-attributes>
      <author>test@gmail.com</author>
      <source>desktop.win</source>
      <source-application>evernote.win32</source-application>
    </note-attributes>
    <content>
      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<test content>]]>
    </content>
  </note>
"""


def test_formatter():
    formatter = NoteFormatter()

    formatted_note = formatter.format_note(test_note_data, [])

    assert formatted_note == expected


def test_formatter_empty_tags_resources():
    formatter = NoteFormatter()

    formatted_note = formatter.format_note(test_note_data_empty_tags, [])

    assert formatted_note == expected_empty_tags


def test_formatter_empty_note():
    formatter = NoteFormatter()

    test_empty_note = Note()
    expected_empty_note = "  <note>\n  </note>\n"

    formatted_note = formatter.format_note(test_empty_note, [])

    assert formatted_note == expected_empty_note


def test_formatter_xml_note():
    formatter = NoteFormatter()

    test_xml_note = Note(content="<?xml test xml stuff ?>\ntest content")
    expected_xml_note = (
        "  <note>\n"
        "    <content>\n"
        '      <![CDATA[<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        "test content]]>\n"
        "    </content>\n"
        "  </note>\n"
    )

    formatted_note = formatter.format_note(test_xml_note, [])

    assert formatted_note == expected_xml_note


def test_note_from_future(mocker):
    formatter = NoteFormatter()

    # 9999-12-31 23:59:59
    end_of_times_bad = 999999999999999
    end_of_times = 243402300799999

    # Emulate windows limit
    mock_timestamp = mocker.patch(
        "evernote_backup.note_formatter_util._get_max_timestamp"
    )
    mock_timestamp.return_value = 32503748400

    note_from_future = Note(
        title="test",
        created=end_of_times_bad,
        updated=end_of_times,
    )

    formatted_note = formatter.format_note(note_from_future, [])

    assert "<created>99991231T235959Z</created>" in formatted_note
    assert "<updated>96830210T061319Z</updated>" in formatted_note


def test_note_from_past(mocker):
    formatter = NoteFormatter()

    before_times_bad = -999999999999999
    before_times = -50000000000000

    note_from_future = Note(
        title="test",
        created=before_times_bad,
        updated=before_times,
    )

    formatted_note = formatter.format_note(note_from_future, [])

    assert "<created>00010101T000000Z</created>" in formatted_note
    assert "<updated>03850725T070640Z</updated>" in formatted_note


def test_formatter_add_guid(mocker):
    formatter = NoteFormatter(add_guid=True)

    test_note = Note(
        guid="test-guid",
        title="test",
    )

    formatted_note = formatter.format_note(test_note, [])

    assert "<guid>test-guid</guid>" in formatted_note


def test_note_with_task(mocker):
    formatter = NoteFormatter()

    note_from_future = Note(
        guid="test-guid",
        title="test",
    )

    note_tasks = [
        Task(
            taskId="c16d6ec7-9a4f-4860-b490-12d93774897c",
            parentId="a4fa08f9-4517-47d1-9762-e5045cf1681c",
            parentType=0,
            noteLevelID="nl-abcdef123456",
            taskGroupNoteLevelID="be9a14f8-06f8-44df-bcd3-945adf5b282a",
            label="Test Label",
            description="Test Description",
            dueDate=1713129600000,
            dueDateUIOption="date_only",
            timeZone="America/New_York",
            status="open",
            statusUpdated=1712692800000,
            inNote=True,
            flag=True,
            taskFlag=2,
            priority=3,
            idClock=1,
            sortWeight="A",
            creator=5678901,
            lastEditor=5678901,
            ownerId=5678901,
            created=1712261000000,
            updated=1712692800000,
            assigneeEmail="test@test.com",
            assigneeIdentityId=9012345,
            assigneeUserId=9012345,
            assignedByUserId=5678901,
            recurrence="RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO",
            repeatAfterCompletion=False,
            reminders=[
                Reminder(
                    reminderId="5d48e464-1dad-4624-9523-24f2bd8f8fe3",
                    sourceId="c16d6ec7-9a4f-4860-b490-12d93774897c",
                    sourceType=15,
                    noteLevelID="38e93c9d-f34e-4754-bb08-5f5ceb62154a",
                    reminderDate=1713042000000,
                    reminderDateUIOption="date_time",
                    timeZone="America/New_York",
                    dueDateOffset=86400,
                    status="active",
                    ownerId=5678901,
                    created=1712175600000,
                    updated=1712520000000,
                )
            ],
        )
    ]

    expected_note = """  <note>
    <title>test</title>
    <task>
      <title>Test Label</title>
      <created>20240404T200320Z</created>
      <updated>20240409T200000Z</updated>
      <taskStatus>open</taskStatus>
      <taskFlag>true</taskFlag>
      <sortWeight>A</sortWeight>
      <noteLevelID>nl-abcdef123456</noteLevelID>
      <taskGroupNoteLevelID>be9a14f8-06f8-44df-bcd3-945adf5b282a</taskGroupNoteLevelID>
      <dueDate>20240414T212000Z</dueDate>
      <dueDateUIOption>date_only</dueDateUIOption>
      <timeZone>America/New_York</timeZone>
      <recurrence>RRULE:FREQ=WEEKLY;INTERVAL=1;BYDAY=MO</recurrence>
      <repeatAfterCompletion>false</repeatAfterCompletion>
      <statusUpdated>20240409T200000Z</statusUpdated>
      <creator>5678901</creator>
      <lastEditor>5678901</lastEditor>
      <reminder>
        <created>20240403T202000Z</created>
        <updated>20240407T200000Z</updated>
        <noteLevelID>38e93c9d-f34e-4754-bb08-5f5ceb62154a</noteLevelID>
        <reminderDate>20240413T210000Z</reminderDate>
        <reminderDateUIOption>date_time</reminderDateUIOption>
        <timeZone>America/New_York</timeZone>
        <dueDateOffset>86400</dueDateOffset>
        <reminderStatus>active</reminderStatus>
      </reminder>
    </task>
  </note>
"""

    formatted_note = formatter.format_note(note_from_future, note_tasks)

    assert formatted_note == expected_note


def test_note_with_many_tasks(mocker):
    formatter = NoteFormatter()

    note_from_future = Note(
        guid="test-guid",
        title="test",
    )

    note_tasks = [
        Task(taskId="tid1", label="test1"),
        Task(
            taskId="tid2",
            label="test2",
            reminders=[
                Reminder(reminderId="rid1", created=1713129600000),
                Reminder(reminderId="rid2", created=1713159600000),
            ],
        ),
    ]

    expected_note = """  <note>
    <title>test</title>
    <task>
      <title>test1</title>
    </task>
    <task>
      <title>test2</title>
      <reminder>
        <created>20240414T212000Z</created>
      </reminder>
      <reminder>
        <created>20240415T054000Z</created>
      </reminder>
    </task>
  </note>
"""

    formatted_note = formatter.format_note(note_from_future, note_tasks)

    assert formatted_note == expected_note
