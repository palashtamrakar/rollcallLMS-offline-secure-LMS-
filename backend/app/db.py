import os
from pathlib import Path
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./roll_call.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

# Upload directory configuration for local videos and presentations
BASE_DIR = Path(__file__).resolve().parent.parent.parent
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads" / "videos")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PRESENTATIONS_DIR = Path(os.getenv("PRESENTATIONS_DIR", str(BASE_DIR / "uploads" / "presentations")))
PRESENTATIONS_DIR.mkdir(parents=True, exist_ok=True)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def migrate_sqlite_schema() -> None:
    """Safely migrate existing sqlite database to include new video/presentation columns and tables."""
    with engine.begin() as conn:
        tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='videos';")).fetchall()
        if tables:
            columns_info = conn.execute(text("PRAGMA table_info(videos);")).fetchall()
            col_map = {col[1]: col for col in columns_info}
            
            # Check if youtube_id has notnull == 1 or missing columns
            youtube_id_notnull = col_map.get("youtube_id", (None, None, None, 0))[3] == 1
            missing_cols = "video_type" not in col_map or "file_path" not in col_map or "chunks_json" not in col_map
            
            if youtube_id_notnull or missing_cols:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS videos_new (
                        id VARCHAR NOT NULL PRIMARY KEY,
                        course_id VARCHAR NOT NULL,
                        title VARCHAR NOT NULL,
                        video_type VARCHAR DEFAULT 'youtube',
                        youtube_id VARCHAR,
                        file_path VARCHAR,
                        file_name VARCHAR,
                        content_type VARCHAR,
                        file_size INTEGER,
                        chunks_json VARCHAR DEFAULT '[]',
                        FOREIGN KEY(course_id) REFERENCES courses (id)
                    );
                """))
                # Check existing columns in old table to construct safe SELECT
                old_cols = set(col_map.keys())
                vtype_expr = "video_type" if "video_type" in old_cols else "'youtube'"
                fpath_expr = "file_path" if "file_path" in old_cols else "NULL"
                fname_expr = "file_name" if "file_name" in old_cols else "NULL"
                ctype_expr = "content_type" if "content_type" in old_cols else "NULL"
                fsize_expr = "file_size" if "file_size" in old_cols else "NULL"
                chunks_expr = "chunks_json" if "chunks_json" in old_cols else "'[]'"
                
                conn.execute(text(f"""
                    INSERT OR IGNORE INTO videos_new (id, course_id, title, video_type, youtube_id, file_path, file_name, content_type, file_size, chunks_json)
                    SELECT id, course_id, title, {vtype_expr}, youtube_id, {fpath_expr}, {fname_expr}, {ctype_expr}, {fsize_expr}, {chunks_expr}
                    FROM videos;
                """))
                conn.execute(text("DROP TABLE videos;"))
                conn.execute(text("ALTER TABLE videos_new RENAME TO videos;"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_videos_course_id ON videos (course_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_videos_video_type ON videos (video_type);"))

        # Create presentations table if not exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS presentations (
                id VARCHAR NOT NULL PRIMARY KEY,
                course_id VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                description VARCHAR,
                presentation_type VARCHAR DEFAULT 'local',
                embed_url VARCHAR,
                file_path VARCHAR,
                file_name VARCHAR,
                file_size INTEGER,
                content_type VARCHAR,
                slide_count INTEGER DEFAULT 0,
                slides_json VARCHAR DEFAULT '[]',
                FOREIGN KEY(course_id) REFERENCES courses (id)
            );
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_presentations_course_id ON presentations (course_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_presentations_presentation_type ON presentations (presentation_type);"))




def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    if DATABASE_URL.startswith("sqlite"):
        migrate_sqlite_schema()


def get_session():
    with Session(engine) as session:
        yield session

