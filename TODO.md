Review of state of this repo - 

- Application (static html/js/css + app/backend supporting capability set) enabling:
  - input: video, normally interviews
  - output: story 'cut'
    - intermediary artifacts:
      - video diarized transcript srt file
      - llm generated story cut script
      - story cut video files
      - story cut assembled video file
- Notebook for b-roll library building and searching (keyframe_analysis.ipynb)
  - videos
  -> keyframe detection with opencv
  -> key term extraction with llm
  -> embedding of key terms
  -> storing of embeddings + metadata in vector db
  -> search for source video keyframes based on search query cosine similarity 

Next up I'd like to get a basic frontend flow going for the b-roll library and then the total combination.
Gotta make it sexy, consider React with MaterialUI. 
I need to be able to view the intermediary artifacts as well. 

So we need 2 sort of flows going, 
1. b-roll library ingest, keyframes identified + generated metadata for each
  1.1 basic search interface for quick query/previewing
2. and then for the videos to be cut into a story currently the app is simple in -> output files. We need to be able to view the intermediary artifacts as well.
  2.1 video ingest with human in the loop checkpoints in UI for each step for human review, edit, re-processing


Chat a course.

------------
/home/alex/.copilot/session-state/d7d522cd-4ce6-42c7-92f9-d1a57629226d/plan.md
------------

Okay so now what is next?
Action Cut workflow (ground 0 somewhat)
Story Cut workflow (intermediary artifacts display and HitL type expereince)s




-------------------------------------------------
2/16/26 Testing Notes

BRoll Library
- Keyframe detection needs work. See "black screen" example when frame[0] is black, frame[~1] starts actual video but our setup prevents that histogram pickup due to min_interval=30 default. Need more robust handling in event of drastic changes of scene.

Action Studio
- Needs another human-in-the-loop step to review keyframes before describing them!
- Needs more verbose logging
  - Runtime have no idea in logs what is happening; try long video to reproduce
  "Extracting keyframes from uploads/8619af8c-22a0-40d7-99ca-296ad7cca7d7_rawfootage_mary(Interview Original).mp4..." then crickets

Story Studio
- Upload video -> starts polling a new job_id, but frontend just seems stuck, doesn't indicate anything, still showing click to upload box
  - Maybe transcribing in background? On machine without whisper/pyanote it was falling back to cache default properly...
  - Bring over Jobs UI, show some status indicator that it is transcribing
  - Network instpector shows "status": "uploaded". Running for many minutes, no log indicating anything else happening.


----

Fixed most of above. Keyframe detection is still ass, but will address later.
My computer also seems to be grinding to a halt rn, idk what that is about, was fine before this incoming commit but YOLO.

Some smaller bugs like broll segment delete works but doesn't reflect in UI until closing out of the selected video.