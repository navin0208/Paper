from flask import Flask, request, render_template, jsonify, redirect, url_for, flash
import os
import uuid
from datetime import datetime
from pymongo import MongoClient
from werkzeug.utils import secure_filename
import threading
import time

app = Flask(__name__)
app.secret_key = 'hybrid-pdf-processor-2024'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# MongoDB setup - using same database as test3.py
client = MongoClient("mongodb://localhost:27017/")
db = client["hybrid_pdf_processor"]  # For queue management
collection = db["processing_queue"]
questions_collection = db["questions"]  # For questions storage

# Default values for questions
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
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Create job entry in database
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
        
        collection.insert_one(job_data)
        
        return jsonify({
            'job_id': job_id, 
            'message': 'PDF uploaded successfully! Added to processing queue.',
            'status': 'queued'
        })
    else:
        return jsonify({'error': 'Invalid file type. Please upload a PDF file.'}), 400

@app.route('/status/<job_id>')
def get_status(job_id):
    """Get processing status for a job"""
    job = collection.find_one({"job_id": job_id})
    if job:
        # Remove MongoDB ObjectId for JSON serialization
        job['_id'] = str(job['_id'])
        return jsonify(job)
    else:
        return jsonify({'error': 'Job not found'}), 404

@app.route('/queue')
def view_queue():
    """View processing queue"""
    jobs = list(collection.find().sort("created_at", -1))
    return render_template('queue.html', jobs=jobs)

@app.route('/questions')
def questions():
    """View all processed questions"""
    questions = list(questions_collection.find().sort("created_at", -1))
    return render_template('questions.html', questions=questions)

# ================================
# PC PROCESSOR API ENDPOINTS
# ================================

@app.route('/api/poll', methods=['GET'])
def poll_for_jobs():
    """PC processor polls this endpoint for new jobs"""
    # Find oldest queued job
    job = collection.find_one({"status": "queued"})
    if job:
        # Mark as processing
        collection.update_one(
            {"job_id": job["job_id"]}, 
            {
                "$set": {
                    "status": "processing",
                    "processed_at": datetime.now(),
                    "pc_processor": request.remote_addr
                }
            }
        )
        return jsonify({
            "job_id": job["job_id"],
            "filepath": job["filepath"],
            "filename": job["filename"]
        })
    else:
        return jsonify({"message": "No jobs available"})

@app.route('/api/upload_results', methods=['POST'])
def upload_results():
    """PC processor uploads results here"""
    data = request.get_json()
    job_id = data.get('job_id')
    questions = data.get('questions', [])
    mmd_content = data.get('mmd_content', '')
    error_message = data.get('error_message')
    
    if not job_id:
        return jsonify({'error': 'Job ID required'}), 400
    
    job = collection.find_one({"job_id": job_id})
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if error_message:
        # Update job with error
        collection.update_one(
            {"job_id": job_id},
            {
                "$set": {
                    "status": "error",
                    "error_message": error_message,
                    "completed_at": datetime.now()
                }
            }
        )
        return jsonify({'message': 'Error recorded'})
    
    # Store questions in database
    if questions:
        for question in questions:
            question['created_at'] = datetime.now()
            question['job_id'] = job_id
        questions_collection.insert_many(questions)
    
    # Update job status
    collection.update_one(
        {"job_id": job_id},
        {
            "$set": {
                "status": "completed",
                "questions_count": len(questions),
                "completed_at": datetime.now(),
                "mmd_content": mmd_content
            }
        }
    )
    
    return jsonify({
        'message': 'Results uploaded successfully',
        'questions_count': len(questions)
    })

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """PC processor sends heartbeat to show it's alive"""
    data = request.get_json()
    pc_id = data.get('pc_id', request.remote_addr)
    
    # Update or create PC status
    db.pc_processors.update_one(
        {"pc_id": pc_id},
        {
            "$set": {
                "pc_id": pc_id,
                "last_heartbeat": datetime.now(),
                "status": "online"
            }
        },
        upsert=True
    )
    
    return jsonify({'message': 'Heartbeat received'})

@app.route('/api/pc_status')
def pc_status():
    """Get status of all PC processors"""
    processors = list(db.pc_processors.find())
    for proc in processors:
        proc['_id'] = str(proc['_id'])
    return jsonify(processors)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
