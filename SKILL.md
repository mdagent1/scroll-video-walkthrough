---
name: scroll-video-walkthrough
description: >-
  Turn a folder of video clips into a scroll-driven web page where scrolling
  scrubs the video scene by scene — the video plays exactly as fast as the
  reader scrolls. Use when the user wants a scroll-video page, scrollytelling,
  an interactive walkthrough/tour, a portfolio or product page where "the
  video is the website". Plain HTML/CSS/JS output — no framework, no build
  step. ffmpeg + Python stdlib only.
---

# Scroll-Video Walkthrough

A folder of clips becomes a web page where **scrolling drives the video**:
each clip is a full-screen scene, and the reader's scroll position scrubs
through it. Stop scrolling, the video stops. Scroll back, it plays backward.

## When to use
The user has **short clips** (a tour, a build, a transformation, a portfolio)
and wants an **interactive page**, not a video file: product walkthroughs,
before/after stories, travel pages, case studies.

## Requirements
- `ffmpeg` and `ffprobe` on PATH.
- Python 3 (standard library only — no pip installs).

## How to run
```bash
python3 scripts/scroll_walkthrough.py --clips ./clips --out ./walkthrough \
  --title "My Walkthrough" --serve
```
`--serve` opens it at `http://localhost:8907/`. The output folder
(`index.html` + `videos/` + `posters/`) can be dropped onto any static host.

Scene titles come from filenames: `01-the-real-city.mp4` → "The Real City".
Number the files to control order.

## Options
| Flag | Default | What it does |
|------|---------|--------------|
| `--clips` | (required) | Folder of clips; one clip = one scene. |
| `--out` | `walkthrough` | Output folder. |
| `--title` | ... | Big headline on the intro screen. |
| `--subtitle` | (none) | Smaller line under the title. |
| `--outro` | ... | Closing line on the last screen. |
| `--credit` | ... | Small credit line in the footer. |
| `--scroll` | `220` | Scroll length per scene in vh — bigger = slower scrub. |
| `--fit` | `cover` | `cover` fills the screen (crops); `contain` letterboxes. |
| `--width` | `1920` | Max encoded video width. |
| `--fps` | `30` | Encoded frame rate. |
| `--crf` | `21` | Quality (lower = better/bigger). |
| `--accent` | `#59d1ff` | Accent color (scene numbers, dots, progress bar). |
| `--serve` | off | Serve the result locally (with Range support — see below). |

## What makes it feel liquid (the design, so you can tune it)
- **Tiny keyframe interval.** Clips are re-encoded with a keyframe every 6
  frames and no B-frames — that's what makes seeking fast enough to feel like
  the page is made of video. Skipping this step is why naive attempts feel
  chunky.
- **Eased scrub.** The video eases toward the scroll position
  (framerate-independent, 80 ms half-life) instead of snapping — wheel steps
  feel like motion, not slideshow clicks.
- **Triple-driven loop.** The scrub updates from rAF, a timer, *and* scroll
  events, so it keeps working where browsers throttle one of them.
- **One scene = one clip.** Titles overlay on a bottom gradient, fade with
  scene progress; dots + a top bar show where you are.

## The big gotcha: HTTP Range requests
Browsers **refuse to scrub video** served without HTTP Range support, and
`python3 -m http.server` doesn't have it — the page will load but every scene
will stick at frame one. Use the built-in `--serve` (it adds Range support),
open `index.html` directly from disk, or host on any real static host
(they all support ranges).

## Tips
- 2–8 clips of 2–15 seconds each is the sweet spot. Very long clips scrub
  too fast; raise `--scroll` to compensate.
- iOS/mobile: works — videos are muted + `playsinline`, and posters show
  until first interaction.
- Vertical clips on a desktop page: use `--fit contain` if the crop hurts.
- Total page weight is roughly the sum of the re-encoded clips; keep it under
  ~50 MB for polite mobile loading (drop `--width` to 1280 if needed).

## Troubleshooting
- *Every scene stuck on its first frame* → your server doesn't support Range
  requests (see the gotcha above). Use `--serve`.
- *Scrub feels chunky* → the source may have low motion sampling; check the
  encode step ran (look for the `-g 6` re-encode) rather than serving originals.
- *A clip is skipped* → ffprobe couldn't read it; re-export it.
