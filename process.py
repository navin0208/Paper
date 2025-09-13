from flask import Flask, request, render_template, jsonify, send_from_directory
import os
import uuid
import json
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker
import pymysql

# =========================
# CONFIG (SQL, no Mongo)
# =========================
DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    status = Column(String, default="queued")
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    questions_count = Column(Integer, default=0)
    pc_processor = Column(String, nullable=True)
    mmd_content = Column(Text, nullable=True)

    # 👇 Add this line
    job_metadata = Column(Text, nullable=True)  # JSON string


# Master Tables
class ChapterMaster(Base):
    __tablename__ = "chapter_master"
    chapter_id = Column(Integer, primary_key=True, autoincrement=True)
    chapter_name = Column(String, nullable=False)
    subject_master_subject_id = Column(Integer, nullable=False)  # 🔹 add this
    created_at = Column(DateTime, default=datetime.utcnow)


class EntranceExamMaster(Base):
    __tablename__ = "entrance_exam_master"
    entrance_exam_id = Column(Integer, primary_key=True, autoincrement=True)
    exam_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class PatternMaster(Base):
    __tablename__ = "pattern_master"
    pattern_id = Column(Integer, primary_key=True, autoincrement=True)
    pattern_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class QuestionLevelMaster(Base):
    __tablename__ = "question_level_master"
    question_level_id = Column(Integer, primary_key=True, autoincrement=True)
    level_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class QuestionTypeMaster(Base):
    __tablename__ = "question_type_master"
    question_type_id = Column(Integer, primary_key=True, autoincrement=True)
    type_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class StandardMaster(Base):
    __tablename__ = "standard_master"
    standard_id = Column(Integer, primary_key=True, autoincrement=True)
    standard_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SubTopicMaster(Base):
    __tablename__ = "sub_topic_master"
    sub_topic_id = Column(Integer, primary_key=True, autoincrement=True)
    sub_topic_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class SubjectMaster(Base):
    __tablename__ = "subject_master"
    subject_id = Column(Integer, primary_key=True, autoincrement=True)
    subject_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class TopicMaster(Base):
    __tablename__ = "topic_master"
    topic_id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class UserMaster(Base):
    __tablename__ = "user_master"
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False)
    email = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class YearOfAppearanceMaster(Base):
    __tablename__ = "year_of_appearance_master"
    year_of_appearance_id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Question(Base):
    __tablename__ = "questions"

    # Primary key matching target schema
    question_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Core question fields
    question = Column(Text)
    option1 = Column(Text)
    option2 = Column(Text)
    option3 = Column(Text)
    option4 = Column(Text)
    answer = Column(Text)
    explanation = Column(Text)
    solution = Column(Text)
    
    # Status and metadata fields
    asked = Column(String)
    asked_status = Column(String)
    date = Column(DateTime)
    marks = Column(Integer)
    question_category = Column(String)
    status = Column(String)

    # Foreign key fields matching target schema
    chapter_master_chapter_id = Column(Integer)
    entrance_exam_master_entrance_exam_id = Column(Integer)
    pattern_master_pattern_id = Column(Integer)
    question_level_question_level_id = Column(Integer)
    question_type_question_type_id = Column(Integer)
    standard_master_standard_id = Column(Integer)
    sub_topic_master_sub_topic_id = Column(Integer)
    subject_master_subject_id = Column(Integer)
    topic_master_topic_id = Column(Integer)
    user_id = Column(Integer)
    year_of_appearance_year_of_appearance_id = Column(Integer)


class PCProcessor(Base):
    __tablename__ = "pc_processors"

    pc_id = Column(String, primary_key=True)
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="online")


Base.metadata.create_all(bind=engine)


# =========================
# FLASK APP
# =========================
app = Flask(__name__)
app.secret_key = 'hybrid-pdf-processor-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chapters_by_subject/<int:subject_id>', methods=['GET'])
def get_chapters_by_subject(subject_id):
    db = SessionLocal()
    try:
        chapters = db.query(ChapterMaster).filter(
            ChapterMaster.subject_master_subject_id == subject_id
        ).order_by(ChapterMaster.chapter_name.asc()).all()

        data = [{"id": c.chapter_id, "name": c.chapter_name} for c in chapters]
        return jsonify(data)
    finally:
        db.close()


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file selected'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if file and allowed_file(file.filename):
        db = SessionLocal()
        try:
            job_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Extract metadata from form
            metadata = {}
            metadata_fields = [
                'question_category', 'marks', 'subject_master_subject_id', 'chapter_master_chapter_id',
                'standard_master_standard_id', 'question_level_question_level_id', 'entrance_exam_master_entrance_exam_id',
                'pattern_master_pattern_id', 'question_type_question_type_id', 'year_of_appearance_year_of_appearance_id',
                'topic_master_topic_id', 'sub_topic_master_sub_topic_id', 'user_id', 'asked_status',
                'asked', 'status'
            ]
            
            for field in metadata_fields:
                value = request.form.get(field)
                if value:
                    # Convert numeric fields
                    if field in ['marks', 'subject_master_subject_id', 'chapter_master_chapter_id', 
                               'standard_master_standard_id', 'question_level_question_level_id',
                               'entrance_exam_master_entrance_exam_id', 'pattern_master_pattern_id',
                               'question_type_question_type_id', 'year_of_appearance_year_of_appearance_id',
                               'topic_master_topic_id', 'sub_topic_master_sub_topic_id', 'user_id']:
                        try:
                            metadata[field] = int(value)
                        except ValueError:
                            metadata[field] = None
                    else:
                        metadata[field] = value

            job = Job(
                job_id=job_id,
                filename=filename,
                filepath=filepath,
                status="queued",
                created_at=datetime.now()
            )
            db.add(job)
            db.commit()

            # Store metadata in job_metadata field (as JSON)
            job.job_metadata = json.dumps(metadata)
            db.commit()

            return jsonify({
                'job_id': job_id,
                'message': 'PDF uploaded successfully! Added to processing queue.',
                'status': 'queued',
                'metadata': metadata
            })
        finally:
            db.close()
    else:
        return jsonify({'error': 'Invalid file type. Please upload a PDF file.'}), 400


@app.route('/status/<job_id>')
def get_status(job_id):
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        return jsonify({
            'job_id': job.job_id,
            'filename': job.filename,
            'filepath': job.filepath,
            'status': job.status,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'processed_at': job.processed_at.isoformat() if job.processed_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'error_message': job.error_message,
            'questions_count': job.questions_count,
            'pc_processor': job.pc_processor
        })
    finally:
        db.close()


@app.route('/queue')
def view_queue():
    db = SessionLocal()
    try:
        jobs = db.query(Job).order_by(Job.created_at.desc()).all()
        return render_template('queue.html', jobs=jobs)
    finally:
        db.close()


@app.route('/questions')
def questions():
    db = SessionLocal()
    try:
        qs = db.query(Question).order_by(Question.created_at.desc()).all()
        return render_template('questions.html', questions=qs)
    finally:
        db.close()


# ================================
# Masters read-only API (local SQLite)
# ================================
@app.route('/api/masters', methods=['GET'])
def get_masters():
    db = SessionLocal()
    try:
        def rows_to_list(rows, id_attr, name_attr):
            return [{"id": getattr(r, id_attr), "name": getattr(r, name_attr)} for r in rows]

        data = {
            "subjects": rows_to_list(db.query(SubjectMaster).order_by(SubjectMaster.subject_name.asc()).all(), "subject_id", "subject_name"),
            "chapters": rows_to_list(db.query(ChapterMaster).order_by(ChapterMaster.chapter_name.asc()).all(), "chapter_id", "chapter_name"),
            "standards": rows_to_list(db.query(StandardMaster).order_by(StandardMaster.standard_name.asc()).all(), "standard_id", "standard_name"),
            "levels": rows_to_list(db.query(QuestionLevelMaster).order_by(QuestionLevelMaster.level_name.asc()).all(), "question_level_id", "level_name"),
            "exams": rows_to_list(db.query(EntranceExamMaster).order_by(EntranceExamMaster.exam_name.asc()).all(), "entrance_exam_id", "exam_name"),
            "patterns": rows_to_list(db.query(PatternMaster).order_by(PatternMaster.pattern_name.asc()).all(), "pattern_id", "pattern_name"),
            "types": rows_to_list(db.query(QuestionTypeMaster).order_by(QuestionTypeMaster.type_name.asc()).all(), "question_type_id", "type_name"),
            "years": rows_to_list(db.query(YearOfAppearanceMaster).order_by(YearOfAppearanceMaster.year.asc()).all(), "year_of_appearance_id", "year"),
            "topics": rows_to_list(db.query(TopicMaster).order_by(TopicMaster.topic_name.asc()).all(), "topic_id", "topic_name"),
            "sub_topics": rows_to_list(db.query(SubTopicMaster).order_by(SubTopicMaster.sub_topic_name.asc()).all(), "sub_topic_id", "sub_topic_name"),
        }
        # Users: some SQLite schemas may not have the optional 'email' column; fall back to raw SELECT
        try:
            data["users"] = rows_to_list(db.query(UserMaster).order_by(UserMaster.username.asc()).all(), "user_id", "username")
        except Exception:
            with engine.connect() as conn:
                result = conn.exec_driver_sql("SELECT user_id AS id, username AS name FROM user_master ORDER BY username ASC")
                data["users"] = [dict(row) for row in result.mappings().all()]
        return jsonify(data)
    finally:
        db.close()


# ================================
# Masters read-only API (external MySQL)
# ================================
@app.route('/api/masters_external', methods=['GET'])
def get_masters_external():
    host = os.getenv('EXT_DB_HOST')
    port = int(os.getenv('EXT_DB_PORT', '3306'))
    user = os.getenv('EXT_DB_USER')
    password = os.getenv('EXT_DB_PASSWORD')
    database = os.getenv('EXT_DB_NAME')

    if not all([host, user, password, database]):
        return jsonify({'error': 'External DB environment variables not set'}), 400

    conn = None
    try:
        conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database, cursorclass=pymysql.cursors.DictCursor, read_default_file=None)
        cur = conn.cursor()

        def fetch(table, id_col, name_col):
            # Strictly read-only query
            cur.execute(f"SELECT {id_col} AS id, {name_col} AS name FROM {table} ORDER BY {name_col} ASC")
            return cur.fetchall()

        data = {
            "subjects": fetch('subject_master', 'subject_id', 'subject_name'),
            "chapters": fetch('chapter_master', 'chapter_id', 'chapter_name'),
            "standards": fetch('standard_master', 'standard_id', 'standard_name'),
            "levels": fetch('question_level_master', 'question_level_id', 'level_name'),
            "exams": fetch('entrance_exam_master', 'entrance_exam_id', 'exam_name'),
            "patterns": fetch('pattern_master', 'pattern_id', 'pattern_name'),
            "types": fetch('question_type_master', 'question_type_id', 'type_name'),
            "years": fetch('year_of_appearance_master', 'year_of_appearance_id', 'year'),
            "topics": fetch('topic_master', 'topic_id', 'topic_name'),
            "sub_topics": fetch('sub_topic_master', 'sub_topic_id', 'sub_topic_name'),
            "users": fetch('user_master', 'user_id', 'username'),
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if conn:
            conn.close()


# ================================
# PC PROCESSOR API ENDPOINTS
# ================================
@app.route('/api/poll', methods=['GET'])
def poll_for_jobs():
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.status == "queued").order_by(Job.created_at.asc()).first()
        if job:
            job.status = "processing"
            job.processed_at = datetime.now()
            job.pc_processor = request.remote_addr
            db.commit()
            
            # Parse metadata if available
            metadata = {}
            if job.job_metadata:
                try:
                    metadata = json.loads(job.job_metadata)
                except json.JSONDecodeError:
                    metadata = {}
            
            return jsonify({
                "job_id": job.job_id,
                "filepath": job.filepath,
                "filename": job.filename,
                "metadata": metadata
            })
        return jsonify({"message": "No jobs available"})
    finally:
        db.close()


@app.route('/api/upload_results', methods=['POST'])
def upload_results():
    data = request.get_json()
    job_id = data.get('job_id')
    questions = data.get('questions', [])
    mmd_content = data.get('mmd_content', '')
    error_message = data.get('error_message')

    if not job_id:
        return jsonify({'error': 'Job ID required'}), 400

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.job_id == job_id).first()
        if not job:
            return jsonify({'error': 'Job not found'}), 404

        if error_message:
            job.status = "error"
            job.error_message = error_message
            job.completed_at = datetime.now()
            db.commit()
            return jsonify({'message': 'Error recorded'})

        saved = 0
        for q in questions:
            # Duplicate prevention: exact match on normalized question+answer
            question_text = (q.get('question') or '').strip()
            answer_text = (q.get('answer') or '').strip()
            if question_text:
                existing = db.query(Question).filter(
                    func.lower(func.trim(Question.question)) == question_text.lower(),
                    func.lower(func.trim(Question.answer)) == answer_text.lower()
                ).first()
                if existing:
                    continue

            q_row = Question(
                job_id=job_id,
                created_at=datetime.now(),
                question=question_text,
                option1=q.get('option1', ''),
                option2=q.get('option2', ''),
                option3=q.get('option3', ''),
                option4=q.get('option4', ''),
                answer=answer_text,
                explanation=q.get('explanation', ''),
                solution=q.get('solution', ''),
                asked=q.get('asked', ''),
                asked_status=q.get('asked_status', ''),
                date=q.get('date'),
                marks=q.get('marks'),
                question_category=q.get('question_category', ''),
                status=q.get('status', ''),
                chapter_master_chapter_id=q.get('chapter_master_chapter_id'),
                entrance_exam_master_entrance_exam_id=q.get('entrance_exam_master_entrance_exam_id'),
                pattern_master_pattern_id=q.get('pattern_master_pattern_id'),
                question_level_question_level_id=q.get('question_level_question_level_id'),
                question_type_question_type_id=q.get('question_type_question_type_id'),
                standard_master_standard_id=q.get('standard_master_standard_id'),
                sub_topic_master_sub_topic_id=q.get('sub_topic_master_sub_topic_id'),
                subject_master_subject_id=q.get('subject_master_subject_id'),
                topic_master_topic_id=q.get('topic_master_topic_id'),
                user_id=q.get('user_id'),
                year_of_appearance_year_of_appearance_id=q.get('year_of_appearance_year_of_appearance_id')
            )
            db.add(q_row)
            saved += 1

        job.status = "completed"
        job.questions_count = saved
        job.completed_at = datetime.now()
        job.mmd_content = mmd_content
        db.commit()

        return jsonify({
            'message': 'Results uploaded successfully',
            'questions_count': saved
        })
    finally:
        db.close()


@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    data = request.get_json()
    pc_id = data.get('pc_id', request.remote_addr)

    db = SessionLocal()
    try:
        proc = db.query(PCProcessor).filter(PCProcessor.pc_id == pc_id).first()
        if not proc:
            proc = PCProcessor(pc_id=pc_id)
            db.add(proc)
        proc.last_heartbeat = datetime.now()
        proc.status = "online"
        db.commit()
        return jsonify({'message': 'Heartbeat received'})
    finally:
        db.close()


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/api/pc_status')
def pc_status():
    db = SessionLocal()
    try:
        processors = db.query(PCProcessor).all()
        return jsonify([
            {
                'pc_id': p.pc_id,
                'last_heartbeat': p.last_heartbeat.isoformat() if p.last_heartbeat else None,
                'status': p.status
            } for p in processors
        ])
    finally:
        db.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)


