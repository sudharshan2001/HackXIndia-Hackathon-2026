# Medral AI Healthcare Platform

AI-powered healthcare assistant for rural Indian health centers. Built for HackX India 2026.

## Team

**Team Name:** sslash  
**Developer:** Sudharshan N

## Presentation

🎯 **Project Presentation:** [View on Google Drive](https://drive.google.com/file/d/1jvI6Q-88w2qz-HHjgppMZC2bNxLT3OBS/view?usp=sharing)

## Features

**Triage** - Analyzes patient vitals + photos to assign RED/YELLOW/GREEN priority  
**Reports** - Converts complex lab reports into simple explanations  
**Scribe** - Digitizes handwritten doctor notes into structured summaries  
**Polypharmacy** - Detects dangerous drug interactions from prescription images  

## Setup

```bash
# Clone repository
git clone https://github.com/sudharshan2001/HackXIndia-Hackathon-2026
cd HackXIndia-Hackathon-2026/medral

# Create conda environment
conda create -n trial python=3.10.2
conda activate trial

# Install dependencies
pip install -r requirements.txt

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull Qwen3-VL model
ollama pull qwen3-vl:4b

# Start Ollama (separate terminal)
ollama serve

# Start Medral server
python app.py
```

Open `http://localhost:8000`

## Technology

- **Vision AI**: Qwen3-VL 4B for image analysis and OCR, medgemma 1.5 4B
- **Backend**: FastAPI + Python 3.10.2
- **Frontend**: HTML/CSS/JS with drag-drop uploads
- **CUDA**: 12.8 for GPU acceleration

## Usage

1. **Triage**: Upload vitals slip + patient photo for emergency prioritization
2. **Reports**: Upload lab reports for patient-friendly explanations  
3. **Scribe**: Upload handwritten notes for digital transcription
4. **Polypharmacy**: Upload medicine photos for safety analysis
