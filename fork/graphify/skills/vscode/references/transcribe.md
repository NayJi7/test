# graphify reference: video and audio files

Video and audio transcription is **not available** in this build of graphify (graphify-local): it needed `yt-dlp` and a Whisper model downloaded from the internet, and graphify-local never sends or fetches anything over the network.

When the corpus contains video or audio files (`files['video']` in `.graphify_detect.json`):
- do not try to transcribe them, and do not pass them to semantic subagents (raw media is unreadable);
- tell the user how many were skipped, and that they can add a `.txt` or `.md` transcript next to the media file; transcripts are indexed as documents on the next run.
