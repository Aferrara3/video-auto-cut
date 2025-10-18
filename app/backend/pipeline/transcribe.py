import os
import subprocess
import pandas as pd
from pathlib import Path
import whisper
from pyannote.audio import Pipeline


def transcribe_video(input_path: str, hf_token: str, model_size="base", diarization_device="gpu") -> Path:
    """Run Whisper + PyAnnote diarization and save aligned SRT."""
    input_path = Path(input_path)
    audio_path = input_path.with_suffix(".wav")
    srt_path = input_path.with_suffix(".srt")


    if not hf_token:
        raise ValueError("HuggingFace token is required for PyAnnote diarization.")

    # --- Extract audio ---
    if not audio_path.exists():
        subprocess.run([
            "ffmpeg", "-y", "-i", str(input_path),
            "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(audio_path)
        ], check=True)
    print(f"✅ Extracted audio: {audio_path}")

    # --- Transcribe ---
    print(f"🔊 Transcribing {input_path.name} with Whisper ({model_size})")
    model = whisper.load_model(model_size)
    result = model.transcribe(str(input_path), verbose=False)
    df_w = pd.DataFrame(result["segments"])[["start", "end", "text"]]

    # --- Diarize ---
    print(f"🗣️ Running PyAnnote diarization...")
    if diarization_device.lower() == "gpu":
        import torch
        device = torch.device("cuda")
        diar_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=hf_token
        ).to(device)
    else:
        diar_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", use_auth_token=hf_token
        )
    diarization = diar_pipeline({"audio": audio_path})

    # --- Align transcripts with speakers ---
    PAD = 0.2
    df_d = pd.DataFrame(
        [(turn.start - PAD, turn.end + PAD, spk)
        for turn, _, spk in diarization.itertracks(yield_label=True)],
        columns=["d_start", "d_end", "speaker"]
    )
    audio_dur = df_w["end"].max()
    df_d["d_start"] = df_d["d_start"].clip(lower=0)
    df_d["d_end"] = df_d["d_end"].clip(upper=audio_dur)

    df_join = (
        df_w.assign(key=1)
        .merge(df_d.assign(key=1), on="key")
        .drop("key", axis=1)
        .query("end > d_start and start < d_end")
    )

    df_join["overlap"] = (
        df_join[["end", "d_end"]].min(axis=1)
        - df_join[["start", "d_start"]].max(axis=1)
    )
    df_join = df_join[df_join["overlap"] > 0]

    df_aligned = (
        df_join.loc[df_join.groupby(["start", "end", "text"])["overlap"].idxmax()]
        [["start", "end", "text", "speaker"]]
        .sort_values("start")
    )

    def write_srt(df, filename):
        def fmt(ts):
            h, m, s = int(ts // 3600), int((ts % 3600) // 60), ts % 60
            return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

        with open(filename, "w", encoding="utf-8") as f:
            for i, row in enumerate(df.itertuples(index=False), start=1):
                dur = row.end - row.start
                f.write(
                    f"{i}\n"
                    f"{fmt(row.start)} --> {fmt(row.end)} (duration: {dur:.2f}s)\n"
                    f"[{row.speaker}] {row.text.strip()}\n\n"
                )

    # --- Write SRT ---
    write_srt(df_aligned, srt_path)
    print(f"✅ SRT saved: {srt_path}")
    return srt_path


def write_srt(df, filename):
    def fmt(ts):
        h, m, s = int(ts // 3600), int((ts % 3600) // 60), ts % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    with open(filename, "w", encoding="utf-8") as f:
        for i, row in enumerate(df.itertuples(index=False), start=1):
            f.write(
                f"{i}\n{fmt(row.start)} --> {fmt(row.end)}\n[{row.speaker}] {row.text.strip()}\n\n"
            )


if __name__ == "__main__":
    import json
    from dotenv import load_dotenv

    load_dotenv()
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

    input_video = "interview1.mp4"
    srt_path = transcribe_video(
        input_video,
        hf_token=HF_TOKEN,
        model_size="base",
        diarization_device="gpu"
    )