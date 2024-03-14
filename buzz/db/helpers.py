import os
from datetime import datetime
from sqlite3 import Connection

from buzz.cache import TasksCache
from buzz.db.migrator import dumb_migrate_db


def copy_transcriptions_from_json_to_sqlite(conn: Connection):
    cache = TasksCache()
    if os.path.exists(cache.tasks_list_file_path):
        tasks = cache.load()
        cursor = conn.cursor()
        for task in tasks:
            cursor.execute(
                """
                INSERT INTO transcription (id, error_message, export_formats, file, output_folder, progress, language, model_type, source, status, task, time_ended, time_queued, time_started, url, whisper_model_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id;
                """,
                (
                    str(task.uid),
                    task.error,
                    ", ".join(
                        [
                            format.value
                            for format in task.file_transcription_options.output_formats
                        ]
                    ),
                    task.file_path,
                    task.output_directory,
                    task.fraction_completed,
                    task.transcription_options.language,
                    task.transcription_options.model.model_type.value,
                    task.source.value,
                    task.status.value,
                    task.transcription_options.task.value,
                    task.completed_at,
                    task.queued_at,
                    task.started_at,
                    task.url,
                    task.transcription_options.model.whisper_model_size.value
                    if task.transcription_options.model.whisper_model_size
                    else None,
                ),
            )
            transcription_id = cursor.fetchone()[0]

            for segment in task.segments:
                cursor.execute(
                    """
                    INSERT INTO transcription_segment (end_time, start_time, text, transcription_id)
                    VALUES (?, ?, ?, ?);
                    """,
                    (
                        segment.end,
                        segment.start,
                        segment.text,
                        transcription_id,
                    ),
                )
        # os.remove(cache.tasks_list_file_path)
        conn.commit()


def run_sqlite_migrations(db: Connection):
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    with open(schema_path) as schema_file:
        schema = schema_file.read()
        dumb_migrate_db(db=db, schema=schema)


def mark_in_progress_and_queued_transcriptions_as_canceled(conn: Connection):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE transcription
        SET status = 'canceled', time_ended = ?
        WHERE status = 'in_progress' OR status = 'queued';
        """,
        (datetime.now().isoformat(),),
    )
    conn.commit()
