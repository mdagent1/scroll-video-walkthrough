# Scroll-Video Walkthrough — a Claude skill

Turn a **folder of clips** into a **scroll-driven web page**: each clip is a
full-screen scene, and scrolling scrubs the video. Stop scrolling, it stops.
Scroll back, it plays backward. The video *is* the website.

Plain HTML/CSS/JS out — no framework, no build step. No npm. No pip installs.

## Quick start
```bash
python3 scripts/scroll_walkthrough.py --clips ./clips --out ./walkthrough \
  --title "My Walkthrough" --serve
```
Then scroll: `http://localhost:8907/`. Drop the output folder on any static
host to publish it.

Scene titles come from the filenames — `02-point-cloud.mp4` becomes
"Point Cloud". Number the files to set the order.

## Why it feels liquid
- **Keyframe every 6 frames** on the re-encode — the whole trick. Without it,
  seeking is chunky and the illusion dies.
- **Eased scrub** — the video chases the scroll with an 80 ms half-life, so
  wheel steps read as motion, not slideshow clicks.
- **Throttle-proof loop** — scrub updates from rAF, a timer, and scroll
  events, so it survives browser throttling.

## The one gotcha worth knowing
Browsers refuse to scrub video served without **HTTP Range requests** —
and Python's stock `python3 -m http.server` doesn't support them. The page
loads, but every scene sticks on frame one. That's why `--serve` exists
(a tiny server *with* ranges). Any real static host is fine.

## Options
See [`SKILL.md`](SKILL.md) for the full flag reference and troubleshooting.

## Install as a Claude skill
Copy this folder into your Claude skills directory (e.g.
`~/.claude/skills/scroll-video-walkthrough/`), then ask Claude to
"turn these clips into a scroll-video page."

## Requirements
- `ffmpeg` + `ffprobe` on PATH
- Python 3 (standard library only)

---
Part of the **Dunham Motion Skills** series — free craft skills for people new to Claude.
