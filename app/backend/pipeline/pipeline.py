import os
from app.backend.pipeline.transcribe import transcribe_video
from app.backend.pipeline.summarize import select_story_segments
from app.backend.pipeline.video_utils import concat_clips, cut_segments


def run_full_pipeline(input_path: str, hf_token: str) -> dict:
    """Run entire AutoCut pipeline and return output paths."""
    srt_path = transcribe_video(input_path, hf_token)
    story_json = select_story_segments(srt_path)
    clips_dir = cut_segments(input_path, story_json)
    final_video = concat_clips(clips_dir)

    return {
        "srt": str(srt_path),
        "final_video": str(final_video),
        "segments_json": str(story_json),
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    INPUT_VIDEO = "interview1.mp4"
    HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

    output_paths = run_full_pipeline(INPUT_VIDEO, HUGGINGFACE_TOKEN)
    print("Pipeline completed. Output paths:")
    for key, path in output_paths.items():
        print(f"{key}: {path}")