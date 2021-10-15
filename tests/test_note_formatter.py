from datetime import datetime

from evernote.edam.type.ttypes import (
    Data,
    Note,
    NoteAttributes,
    Resource,
    ResourceAttributes,
)

from evernote_backup import note_formatter_util
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

    formatted_note = formatter.format_note(test_note_data)

    assert formatted_note == expected


def test_formatter_empty_tags_resources():
    formatter = NoteFormatter()

    formatted_note = formatter.format_note(test_note_data_empty_tags)

    assert formatted_note == expected_empty_tags


def test_formatter_empty_note():
    formatter = NoteFormatter()

    test_empty_note = Note()
    expected_empty_note = "  <note>\n  </note>\n"

    formatted_note = formatter.format_note(test_empty_note)

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

    formatted_note = formatter.format_note(test_xml_note)

    assert formatted_note == expected_xml_note


def test_note_from_future(mocker):
    formatter = NoteFormatter()

    # 9999-12-31 23:59:59
    end_of_times = 253402300799999

    # Emulate windows limit
    mock_timestamp = mocker.patch(
        "evernote_backup.note_formatter_util._get_max_timestamp"
    )
    mock_timestamp.return_value = 32503748400

    note_from_future = Note(
        title="test",
        created=end_of_times,
        updated=end_of_times,
    )

    formatted_note = formatter.format_note(note_from_future)

    assert "<created>99991231T235959Z</created>" in formatted_note
    assert "<updated>99991231T235959Z</updated>" in formatted_note
