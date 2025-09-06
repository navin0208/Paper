from flask import Flask, request, render_template, jsonify
import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename

# =========================
# CONFIG
# =========================
USE_DB = False  # 🔹 Toggle this: True = use Mongo, False = in-memory (local testing)

if USE_DB:
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017/")
    db = client["hybrid_pdf_processor"]
    collection = db["processing_queue"]
    questions_collection = db["questions"]
else:
    # Simple in-memory replacements
    collection = []
    questions_collection = []
    pc_processors = []

# =========================
# FLASK APP
# =========================
app = Flask(__name__)
app.secret_key = 'hybrid-pdf-processor-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DEFAULT_DATA = {
    "entranceExamId": "1",
    "standardId": 2,
    "subjectId": 7,
    "chapterId": 69,
    "marks": 2,
    "yearOfAppearanceId": 10,
    "yearOfAppearance": "",
    "asked": True,
    "answer": "",
    "questionLevelId": 1,
    "questionTypeId": 1,
    "multiAnswers": ["option1"],
    "explanation": "",
    "status": "pending",
    "patternId": 1,
    "solution": "",
    "questionCategory": "Numerical"
}


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
        job_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        job_data = {
            "job_id": job_id,
            "filename": filename,
            "filepath": filepath,
            "status": "queued",
            "created_at": datetime.now(),
            "processed_at": None,
            "completed_at": None,
            "error_message": None,
            "questions_count": 0,
            "pc_processor": None
        }

        if USE_DB:
            collection.insert_one(job_data)
        else:
            collection.append(job_data)

        return jsonify({
            'job_id': job_id,
            'message': 'PDF uploaded successfully! Added to processing queue.',
            'status': 'queued'
        })
    else:
        return jsonify({'error': 'Invalid file type. Please upload a PDF file.'}), 400


@app.route('/status/<job_id>')
def get_status(job_id):
    if USE_DB:
        job = collection.find_one({"job_id": job_id})
        if job:
            job['_id'] = str(job['_id'])
    else:
        job = next((j for j in collection if j["job_id"] == job_id), None)

    return jsonify(job if job else {'error': 'Job not found'}), (200 if job else 404)


@app.route('/queue')
def view_queue():
    if USE_DB:
        jobs = list(collection.find().sort("created_at", -1))
    else:
        jobs = sorted(collection, key=lambda j: j["created_at"], reverse=True)
    return render_template('queue.html', jobs=jobs)


@app.route('/questions')
def questions():
    if USE_DB:
        questions = list(questions_collection.find().sort("created_at", -1))
    else:
        questions = sorted(questions_collection, key=lambda q: q["created_at"], reverse=True)
    return render_template('questions.html', questions=questions)


# ================================
# PC PROCESSOR API ENDPOINTS
# ================================
@app.route('/api/poll', methods=['GET'])
def poll_for_jobs():
    if USE_DB:
        job = collection.find_one({"status": "queued"})
    else:
        job = next((j for j in collection if j["status"] == "queued"), None)

    if job:
        if USE_DB:
            collection.update_one(
                {"job_id": job["job_id"]},
                {"$set": {
                    "status": "processing",
                    "processed_at": datetime.now(),
                    "pc_processor": request.remote_addr
                }}
            )
        else:
            job["status"] = "processing"
            job["processed_at"] = datetime.now()
            job["pc_processor"] = request.remote_addr

        return jsonify({
            "job_id": job["job_id"],
            "filepath": job["filepath"],
            "filename": job["filename"]
        })
    return jsonify({"message": "No jobs available"})


@app.route('/api/upload_results', methods=['POST'])
def upload_results():
    data = request.get_json()
    job_id = data.get('job_id')
    questions = data.get('questions', [])
    mmd_content = data.get('mmd_content', '')
    error_message = data.get('error_message')

    if not job_id:
        return jsonify({'error': 'Job ID required'}), 400

    if USE_DB:
        job = collection.find_one({"job_id": job_id})
    else:
        job = next((j for j in collection if j["job_id"] == job_id), None)

    if not job:
        return jsonify({'error': 'Job not found'}), 404

    if error_message:
        if USE_DB:
            collection.update_one(
                {"job_id": job_id},
                {"$set": {
                    "status": "error",
                    "error_message": error_message,
                    "completed_at": datetime.now()
                }}
            )
        else:
            job["status"] = "error"
            job["error_message"] = error_message
            job["completed_at"] = datetime.now()
        return jsonify({'message': 'Error recorded'})

    if questions:
        for q in questions:
            q['created_at'] = datetime.now()
            q['job_id'] = job_id
        if USE_DB:
            questions_collection.insert_many(questions)
        else:
            questions_collection.extend(questions)

    if USE_DB:
        collection.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "completed",
                "questions_count": len(questions),
                "completed_at": datetime.now(),
                "mmd_content": mmd_content
            }}
        )
    else:
        job["status"] = "completed"
        job["questions_count"] = len(questions)
        job["completed_at"] = datetime.now()
        job["mmd_content"] = mmd_content

    return jsonify({
        'message': 'Results uploaded successfully',
        'questions_count': len(questions)
    })


@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    data = request.get_json()
    pc_id = data.get('pc_id', request.remote_addr)

    if USE_DB:
        db.pc_processors.update_one(
            {"pc_id": pc_id},
            {"$set": {
                "pc_id": pc_id,
                "last_heartbeat": datetime.now(),
                "status": "online"
            }},
            upsert=True
        )
    else:
        existing = next((p for p in pc_processors if p["pc_id"] == pc_id), None)
        if existing:
            existing.update({
                "last_heartbeat": datetime.now(),
                "status": "online"
            })
        else:
            pc_processors.append({
                "pc_id": pc_id,
                "last_heartbeat": datetime.now(),
                "status": "online"
            })

    return jsonify({'message': 'Heartbeat received'})

from flask import send_from_directory

@app.route('/download/<filename>')
def download_file(filename):
    """Serve uploaded PDFs to PC processors"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)



@app.route('/api/pc_status')
def pc_status():
    if USE_DB:
        processors = list(db.pc_processors.find())
        for proc in processors:
            proc['_id'] = str(proc['_id'])
    else:
        processors = pc_processors
    return jsonify(processors)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
