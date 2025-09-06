# Hybrid PDF Processor System

A distributed PDF processing system that combines a lightweight web server with powerful local PC processing using Nougat AI.

## 🏗️ Architecture

### Web Server (Lightweight)
- PDF upload interface
- Queue management
- Database storage
- Status tracking
- Results display

### Local PC (Heavy Processing)
- Runs Nougat AI model
- Processes PDFs from queue
- Uploads results back to server
- Handles GPU-intensive work

## 🚀 Quick Start

### 1. Setup Web Server

```bash
# Install dependencies
pip install -r requirements.txt

# Start MongoDB
brew services start mongodb-community

# Run web server
python web_server.py
```

Web server will be available at: `http://localhost:5001`

### 2. Setup Local PC Processor

```bash
# Install Nougat AI
pip install nougat-ocr

# Install Pandoc
brew install pandoc

# Run PC processor
python pc_processor.py
```

## 📁 File Structure

```
hybrid/
├── web_server.py          # Flask web server
├── pc_processor.py        # Local PC processor
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── templates/            # HTML templates
    ├── base.html         # Base template
    ├── index.html        # Upload page
    ├── queue.html        # Queue management
    └── questions.html    # Questions display
```

## 🔄 How It Works

1. **User uploads PDF** → Web server stores file
2. **PDF added to queue** → Database entry created
3. **PC polls server** → "Any new PDFs to process?"
4. **PC downloads PDF** → Runs Nougat AI locally
5. **PC uploads results** → Sends MMD file + extracted questions
6. **Web server updates status** → "Processing complete!"
7. **User gets notification** → Can view extracted questions

## 🖥️ PC Requirements

- **GPU**: RTX 3060+ recommended (or equivalent)
- **RAM**: 16GB+ recommended
- **Storage**: 10GB+ free space
- **Python**: 3.8+ with Nougat installed
- **Internet**: Stable connection to web server

## 🌐 Web Interface Features

### Upload Page
- Drag & drop PDF upload
- Real-time system status
- PC processor monitoring
- Queue status display

### Queue Management
- View all processing jobs
- Real-time status updates
- Error handling display
- Processing statistics

### Questions Display
- View extracted questions
- Search and filter functionality
- Question management
- Option display

## 🔧 Configuration

### Web Server
- **Port**: 5001 (configurable in `web_server.py`)
- **Upload Limit**: 16MB (configurable)
- **Database**: MongoDB (localhost:27017)

### PC Processor
- **Polling Interval**: 5 seconds
- **Heartbeat**: 30 seconds
- **Batch Size**: 2 (configurable)

## 📊 API Endpoints

### Web Server APIs
- `POST /upload` - Upload PDF file
- `GET /status/<job_id>` - Get job status
- `GET /queue` - View processing queue
- `GET /questions` - View extracted questions

### PC Processor APIs
- `GET /api/poll` - Poll for new jobs
- `POST /api/upload_results` - Upload processing results
- `POST /api/heartbeat` - Send heartbeat
- `GET /api/pc_status` - Get PC processor status

## 🛠️ Troubleshooting

### Common Issues

1. **PC can't connect to server**
   - Check server is running
   - Verify network connectivity
   - Check firewall settings

2. **Nougat not found**
   - Install: `pip install nougat-ocr`
   - Check PATH environment variable

3. **MongoDB connection error**
   - Start MongoDB: `brew services start mongodb-community`
   - Check connection string

4. **Processing stuck**
   - Check PC processor logs
   - Verify GPU is available
   - Check system resources

### Logs

- **Web Server**: Console output
- **PC Processor**: Console output with detailed processing logs
- **Database**: MongoDB logs

## 🔒 Security Considerations

- Add authentication for production use
- Use HTTPS for file transfers
- Implement rate limiting
- Add input validation
- Secure API endpoints

## 📈 Scaling

- Multiple PC processors can connect to one server
- Load balancing for multiple servers
- Database clustering for high availability
- CDN for file storage

## 🎯 Benefits

- **Cost Effective**: No expensive GPU servers
- **Scalable**: Multiple PCs can process in parallel
- **Reliable**: AI runs on dedicated hardware
- **Fast**: No server resource constraints
- **Flexible**: Easy to add more processing power

## 📝 License

This project is open source and available under the MIT License.
