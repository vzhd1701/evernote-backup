import pytest

from evernote_backup.evernote_types import (
    EvernoteEntityType,
    EvernoteSyncInstanceType,
    EvernoteSyncOperationType,
)


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_unknown_operation_type(cli_invoker, mock_evernote_client):
    unknown_operation_type = 200

    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": 15},
                "type": EvernoteSyncInstanceType.ENTITY,
                "version": 123,
                "created": 123,
                "updated": 123,
                "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTE},
            },
            "operation": unknown_operation_type,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0
    assert "Sync data inconsistency - unknown operation type" in result.stdout


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_unknown_instance_type(cli_invoker, mock_evernote_client):
    unknown_instance_type = 100

    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": EvernoteEntityType.TASK},
                "type": unknown_instance_type,
                "version": 123,
                "created": 123,
                "updated": 123,
                "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTE},
            },
            "operation": EvernoteSyncOperationType.UPDATE,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0
    assert "Sync data inconsistency - unknown instance type" in result.stdout


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_unknown_entity_type(cli_invoker, mock_evernote_client):
    unknown_entity_type = 100

    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": unknown_entity_type},
                "type": EvernoteSyncInstanceType.ENTITY,
                "version": 123,
                "created": 123,
                "updated": 123,
                "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTE},
            },
            "operation": EvernoteSyncOperationType.UPDATE,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0
    assert "Sync data inconsistency - unknown entity type" in result.stdout


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_entity_without_parent(cli_invoker, mock_evernote_client):
    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": EvernoteEntityType.TASK},
                "type": EvernoteSyncInstanceType.ENTITY,
                "version": 123,
                "created": 123,
                "updated": 123,
                # "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTE},
            },
            "operation": EvernoteSyncOperationType.UPDATE,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0
    assert "Sync data inconsistency - entity without parent" in result.stdout


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_task_outside_note(cli_invoker, mock_evernote_client):
    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": EvernoteEntityType.TASK},
                "type": EvernoteSyncInstanceType.ENTITY,
                "version": 123,
                "created": 123,
                "updated": 123,
                "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTEBOOK},
            },
            "operation": EvernoteSyncOperationType.UPDATE,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0
    assert "Sync data inconsistency - task outside of note" in result.stdout


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_reminder_outside_task(cli_invoker, mock_evernote_client):
    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": EvernoteEntityType.REMINDER},
                "type": EvernoteSyncInstanceType.ENTITY,
                "version": 123,
                "created": 123,
                "updated": 123,
                "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTEBOOK},
            },
            "operation": EvernoteSyncOperationType.UPDATE,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0
    assert "Sync data inconsistency - reminder outside of task" in result.stdout


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_skip_non_entity(cli_invoker, mock_evernote_client):
    non_entity_type = EvernoteSyncInstanceType.AGENT

    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": EvernoteEntityType.TASK},
                "type": non_entity_type,
                "version": 123,
                "created": 123,
                "updated": 123,
                "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTE},
            },
            "operation": EvernoteSyncOperationType.UPDATE,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0


@pytest.mark.usefixtures("fake_init_db")
def test_bad_sync_data_skip_notify_operation(cli_invoker, mock_evernote_client):
    mock_evernote_client.fake_updates = [
        {
            "acl": {"agentIds": ["123:;2"], "updated": 1744277698325},
            "instance": {
                "ref": {"id": "123", "type": EvernoteEntityType.TASK},
                "type": EvernoteSyncInstanceType.ENTITY,
                "version": 123,
                "created": 123,
                "updated": 123,
                "parentEntity": {"id": "123", "type": EvernoteEntityType.NOTE},
            },
            "operation": EvernoteSyncOperationType.NOTIFY,
            "updated": 1744277698547,
        }
    ]

    result = cli_invoker("-v", "sync", "--database", "fake_db", "--include-tasks")

    assert result.exit_code == 0
