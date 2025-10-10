# 🎬 Auto-Story Video Cutter

This notebook automates the process of turning a long interview video (e.g., `.mp4`) into a concise, 2-minute story sequence using **Whisper** for transcription, an **LLM** for story selection, and **ffmpeg** for trimming and concatenation.

---

## 🧩 Features

* 🎙️ **Transcribe** audio directly from `.mp4` to `.srt` subtitles using OpenAI Whisper
* 🧠 **Downselect** meaningful dialogue segments via GPT-4o / GPT-4o-mini
* ✂️ **Automatically trim** the original video to those segments
* 🎞️ **Concatenate** trimmed clips into one continuous short story
* 💾 All outputs saved as reproducible files:

  * `output.srt` → raw transcript
  * `story_segments.json` → LLM-selected timestamps
  * `trimmed_clips/` → individual sub-clips
  * `story_concat.mp4` → final 2-minute video

---

## ⚙️ System Requirements

You’ll need the following system-level dependencies:

| Dependency       | Version  | Purpose                                    |
| ---------------- | -------- | ------------------------------------------ |
| **Python**       | ≥ 3.10   | Core runtime                               |
| **ffmpeg**       | ≥ 4.4    | Video trimming & merging                   |
| **pip / venv**   | latest   | Environment management                     |
| **CUDA toolkit** | optional | For GPU-accelerated Whisper (if available) |

### 🧰 Ubuntu / WSL install

```bash
sudo apt update
sudo apt install -y ffmpeg python3 python3-venv python3-pip
```

For GPU users:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

---

## 📦 Python Dependencies

Create a virtual environment and install:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### `requirements.txt`

```text
# Core
openai>=1.12.0
whisper>=1.1.10
tqdm>=4.66.0

# Optional faster alternatives
faster-whisper>=0.10.0

# Utility
moviepy>=1.0.3
jupyter>=1.0.0
```

---

## 🧠 API Setup

Export your OpenAI API key (for GPT-4o / GPT-4o-mini):

```bash
export OPENAI_API_KEY="sk-..."
```

You can also use Ollama locally by swapping out the OpenAI call in the notebook.

---

## 🚀 Workflow

1. **Place** your input video in the project folder, e.g.
   `rawfootage_mary(Interview Original).mp4`

2. **Run the notebook cells** in order:

   1. **Transcription cell** → generates `output.srt`
   2. **LLM downselect cell** → generates `story_segments.json`
   3. **Trimming cell** → extracts individual `.mp4` clips
   4. **Concatenation cell** → merges them into `story_concat.mp4`

3. **Inspect results**

   * `trimmed_clips/` → check each clip
   * `story_concat.mp4` → final 2-minute story reel

---

## 🧹 Common Issues

| Symptom                          | Likely Cause                  | Fix                                                                          |
| -------------------------------- | ----------------------------- | ---------------------------------------------------------------------------- |
| `Error opening input file`       | Wrong `input_video` path      | Use full absolute path                                                       |
| `Invalid duration for option ss` | Commas in timestamps          | The notebook auto-converts now, but ensure `00:00:12.560` not `00:00:12,560` |
| Empty clips                      | Used `-c copy` (no re-encode) | Use the provided re-encode version                                           |
| Model output not JSON            | LLM formatting drift          | Save raw output & re-prompt with stricter JSON instructions                  |

---

## 🧭 Example Outputs

```bash
output.srt
story_segments.json
trimmed_clips/
├── clip_01_00-00-12.560_00-00-16.120.mp4
├── clip_02_00-01-05.120_00-01-13.080.mp4
└── ...
story_concat.mp4
```

---

## 🧩 Extending the Notebook

* Add `whisperx` for speaker diarization and alignment.
* Insert a second LLM stage for **scene-level b-roll suggestions**.
* Add text overlays or titles using `ffmpeg` filters or `moviepy`.


