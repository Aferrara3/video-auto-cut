# AutoCut Studio

AutoCut Studio is a full-stack AI-assisted video editing application designed to streamline the post-production workflow for interview-based storytelling. It combines the power of **OpenAI Whisper** for transcription, **LLMs** (GitHub Models, Copilot, OpenAI) for editorial decision-making, and **FFmpeg** for rendering.

The application features two main workflows (in progress):
1.  **Story Studio**: A text-based editing environment where users can review transcripts, generate story arcs via LLM, and render the final cut.
2.  **B-Roll Library**: A searchable database of video assets, allowing editors to find "a person typing on a laptop" within their own footage library.

## Features

*   **Transcription Engine**: Automated speech-to-text using Whisper (local or API-based).
*   **LLM Editorial Assistant**:
    *   Generates coherent story arcs from raw transcripts.
    *   Supports **GitHub Copilot CLI** for high-context tasks (processing full transcripts without token limits).
    *   Supports **Azure AI Inference** (GitHub Models) and **OpenAI** for standard tasks.
*   **B-Roll Semantic Search**:
    *   Extracts keyframes from raw footage.
    *   Generates semantic descriptions of keyframes using Multimodal LLMs (GPT-4o).
    *   Embeds descriptions for vector-based natural language search.
*   **Modern Web UI**: Built with React, Vite, and MaterialUI.
*   **REST API**: FastAPI backend for robust job management and processing.

## Architecture

*   **Backend**: FastAPI (Python)
    *   `app/backend/pipeline`: Core video processing logic (transcribe, summarize, render).
    *   `app/backend/broll`: B-roll management (extraction, description, embedding).
    *   `app/backend/llm_client.py`: Abstracted LLM client supporting multiple providers.
*   **Frontend**: React + TypeScript + Vite
    *   `app/frontend`: Single Page Application (SPA).
*   **Storage**:
    *   Local filesystem for video artifacts (`uploads/`, `outputs/`).
    *   JSON-based vector store for B-roll metadata (prototype).
*   **Legacy/Experiments**:
    *   `notebooks/`: Jupyter notebooks containing initial prototypes and experiments (`init_pipeline.ipynb`, `keyframe_analysis.ipynb`).
    *   `sample_videos/`: Sample input files for testing.

## Prerequisites

*   **Python 3.10+**
*   **Node.js 18+**
*   **FFmpeg** (must be in system PATH)
*   **GitHub CLI (`gh`)** (optional, recommended for free LLM access via Copilot)

## Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/video-auto-cut.git
    cd video-auto-cut
    ```

2.  **Backend Setup**:
    ```bash
    # Install Python dependencies using Poetry
    poetry install
    
    # Or using pip/venv manually
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt (if available, or rely on pyproject.toml)
    ```

3.  **Frontend Setup**:
    ```bash
    cd app/frontend
    npm install
    ```

4.  **Environment Configuration**:
    Create a `.env` file in the root directory:
    ```env
    # LLM Provider Selection: azure, gh_copilot, openai, ollama
    LLM_PROVIDER=azure

    # Credentials
    GITHUB_TOKEN=ghp_...        # Required for Azure AI Inference (GitHub Models)
    OPENAI_API_KEY=sk-...       # Required if using OpenAI provider
    HUGGINGFACE_TOKEN=hf_...    # Required for diarization models (optional)
    
    # Optional
    OLLAMA_BASE_URL=http://localhost:11434
    ```

    *Note: To use `LLM_PROVIDER=gh_copilot`, ensure you have the GitHub CLI installed and authenticated with `gh auth login` and the Copilot extension installed.*

## Running the Application

Use the provided `Makefile` to run the development server:

```bash
# Run both Backend (port 8000) and Frontend (port 5173) in parallel
make dev
```

*   **Frontend**: http://localhost:5173
*   **Backend API Docs**: http://localhost:8000/docs

## Usage

### Story Studio (API Workflow)
1.  **Upload**: `POST /api/jobs/upload` with a video file.
2.  **Transcribe**: `POST /api/jobs/{id}/transcribe` to generate SRT.
3.  **Plan**: `POST /api/jobs/{id}/plan` to let the LLM select the best segments.
4.  **Render**: `POST /api/jobs/{id}/render` to generate the final cut.

### B-Roll Library
1.  **Ingest**: `POST /api/broll/ingest` to analyze a video clip.
2.  **Search**: `GET /api/broll/search?query=office+environment` to find matching timestamps.

## Development Status

*   ✅ Backend API Core
*   ✅ LLM Abstraction Layer (Copilot/Azure/OpenAI)
*   ✅ B-Roll Ingest & Search
*   🚧 Frontend UI Implementation
*   🚧 Action Studio Workflow
