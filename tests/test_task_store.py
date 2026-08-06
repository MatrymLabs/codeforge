from kernel.seedlab.task import FileTaskStore, TaskError, TaskRecord


def _task(**changes):
    values = {
        "task_id": "task-001",
        "seed_id": "seed-a",
        "owner_id": "owner-a",
        "title": "A bounded implementation task",
        "description": "A redacted observation-backed description.",
        "source_proposal": "proposal.json",
        "evidence_ids": ("INS-001",),
        "created_at": "2026-08-06T12:00:00+00:00",
    }
    values.update(changes)
    return TaskRecord(**values)


def test_task_record_rejects_invalid_ids_and_status():
    try:
        _task(task_id="bad id")
    except TaskError as exc:
        assert "task_id" in str(exc)
    else:
        raise AssertionError("invalid task id was accepted")

    try:
        _task(status="done")
    except TaskError as exc:
        assert "unsupported task status" in str(exc)
    else:
        raise AssertionError("unsupported status was accepted")


def test_file_task_store_persists_and_idempotently_replays_identical_tasks(tmp_path):
    path = tmp_path / "seedlab" / "tasks.json"
    store = FileTaskStore(path)
    task = _task()

    assert store.create(task) == task
    assert store.create(_task()) == task
    assert FileTaskStore(path).all_for_seed("seed-a") == (task,)

    try:
        store.create(_task(title="different"))
    except TaskError as exc:
        assert "different content" in str(exc)
    else:
        raise AssertionError("conflicting task was accepted")
