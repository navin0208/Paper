from flask import Flask, request, render_template, jsonify, send_from_directory
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, Column, String, Integer, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

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


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # core fields
    question = Column(Text)
    option1 = Column(Text)
    option2 = Column(Text)
    option3 = Column(Text)
    option4 = Column(Text)

    # metadata fields mirroring DEFAULT_DATA
    entranceExamId = Column(String)
    standardId = Column(Integer)
    subjectId = Column(Integer)
    chapterId = Column(Integer)
    marks = Column(Integer)
    yearOfAppearanceId = Column(Integer)
    yearOfAppearance = Column(String)
    asked = Column(String)
    answer = Column(String)
    questionLevelId = Column(Integer)
    questionTypeId = Column(Integer)
    multiAnswers = Column(Text)  # store JSON string if provided
    explanation = Column(Text)
    status = Column(String)
    patternId = Column(Integer)
    solution = Column(Text)
    questionCategory = Column(String)


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

            job = Job(
                job_id=job_id,
                filename=filename,
                filepath=filepath,
                status="queued",
                created_at=datetime.now()
            )
            db.add(job)
            db.commit()

            return jsonify({
                'job_id': job_id,
                'message': 'PDF uploaded successfully! Added to processing queue.',
                'status': 'queued'
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
            return jsonify({
                "job_id": job.job_id,
                "filepath": job.filepath,
                "filename": job.filename
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
            q_row = Question(
                job_id=job_id,
                created_at=datetime.now(),
                question=q.get('question', ''),
                option1=q.get('option1', ''),
                option2=q.get('option2', ''),
                option3=q.get('option3', ''),
                option4=q.get('option4', ''),
                entranceExamId=str(q.get('entranceExamId', '')),
                standardId=q.get('standardId'),
                subjectId=q.get('subjectId'),
                chapterId=q.get('chapterId'),
                marks=q.get('marks'),
                yearOfAppearanceId=q.get('yearOfAppearanceId'),
                yearOfAppearance=q.get('yearOfAppearance', ''),
                asked=str(q.get('asked', '')),
                answer=q.get('answer', ''),
                questionLevelId=q.get('questionLevelId'),
                questionTypeId=q.get('questionTypeId'),
                multiAnswers=str(q.get('multiAnswers', '')),
                explanation=q.get('explanation', ''),
                status=q.get('status', ''),
                patternId=q.get('patternId'),
                solution=q.get('solution', ''),
                questionCategory=q.get('questionCategory', '')
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
    app.run(debug=True, host='0.0.0.0', port=5001)


