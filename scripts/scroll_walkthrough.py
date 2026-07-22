#!/usr/bin/env python3
"""
Scroll-Video Walkthrough — a folder of clips in, a scroll-driven web page out.

Scrolling scrubs each clip: the video plays exactly as fast as the reader
scrolls, scene by scene, and arrow keys jump between scene starts for
keyboard navigation. Plain HTML/CSS/JS — no framework, no build step.

  python3 scroll_walkthrough.py --clips ./clips --out ./walkthrough --title "My Tour"

Scene titles come from the filenames:
  01-the-real-city.mp4  ->  "The Real City"

The clips are re-encoded with a tiny keyframe interval (that's what makes
scrubbing feel liquid instead of chunky) and the page is a single index.html
next to a videos/ and posters/ folder. Open it, or host it anywhere static.
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi", ".mts"}


def die(msg):
    sys.exit(f"error: {msg}")


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True)


def probe(path):
    try:
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                   "-show_entries", "stream=width,height,duration",
                   "-show_entries", "format=duration", "-of", "json",
                   path]).stdout
        info = json.loads(out)
        st = info["streams"][0]
        dur = float(st.get("duration") or info["format"]["duration"])
        return int(st["width"]), int(st["height"]), dur
    except Exception:
        return None


def serve(folder, port):
    """Serve the page locally WITH HTTP Range support.

    Browsers refuse to seek (scrub) video served without Range requests,
    and Python's stock `http.server` doesn't do ranges — so we add them.
    """
    import http.server
    import socketserver

    class RangeHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=folder, **kw)

        def log_message(self, *a):
            pass

        def send_head(self):
            path = self.translate_path(self.path)
            if os.path.isdir(path):
                return super().send_head()
            rng = self.headers.get("Range")
            if not rng:
                return super().send_head()
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            try:
                f = open(path, "rb")
            except OSError:
                self.send_error(404, "File not found")
                return None
            size = os.fstat(f.fileno()).st_size
            if not m or (not m.group(1) and not m.group(2)):
                f.close()
                return super().send_head()
            start = int(m.group(1)) if m.group(1) else size - int(m.group(2))
            end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
            start, end = max(0, start), min(end, size - 1)
            if start > end:
                f.close()
                self.send_error(416, "Requested Range Not Satisfiable")
                return None
            self.send_response(206)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(end - start + 1))
            self.end_headers()
            f.seek(start)
            self._range_left = end - start + 1
            return f

        def copyfile(self, source, outputfile):
            left = getattr(self, "_range_left", None)
            if left is None:
                return super().copyfile(source, outputfile)
            self._range_left = None
            while left > 0:
                chunk = source.read(min(65536, left))
                if not chunk:
                    break
                outputfile.write(chunk)
                left -= len(chunk)

    with socketserver.ThreadingTCPServer(("", port), RangeHandler) as httpd:
        httpd.allow_reuse_address = True
        print(f"serving http://localhost:{port}/   (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def title_from_filename(name):
    stem = os.path.splitext(name)[0]
    stem = re.sub(r"^[\s0-9_.-]+", "", stem)          # strip leading numbering
    stem = re.sub(r"[_-]+", " ", stem).strip()
    return stem.title() if stem else "Scene"


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="data:,">
<title>__TITLE__</title>
<style>
  :root { --accent: __ACCENT__; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html { scroll-behavior: auto; }
  body {
    background: #0b0d10; color: #f2f4f6;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 Helvetica, Arial, sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .intro, .outro {
    min-height: 100vh; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    text-align: center; padding: 8vh 6vw; gap: 1.2rem;
  }
  .intro h1 {
    font-size: clamp(2.2rem, 7vw, 5rem); font-weight: 800;
    letter-spacing: -0.02em; line-height: 1.05; max-width: 16ch;
  }
  .intro p, .outro p { color: #9aa3ad; font-size: clamp(1rem, 2.2vw, 1.25rem);
    max-width: 44ch; line-height: 1.6; }
  .scroll-hint { margin-top: 4vh; color: #9aa3ad; font-size: .85rem;
    letter-spacing: .25em; text-transform: uppercase; }
  .scroll-hint::after {
    content: ""; display: block; width: 1px; height: 56px;
    margin: 14px auto 0; background: linear-gradient(var(--accent), transparent);
    animation: drip 1.6s ease-in-out infinite;
  }
  @keyframes drip { 0% {transform: scaleY(0); transform-origin: top}
    45% {transform: scaleY(1); transform-origin: top}
    55% {transform: scaleY(1); transform-origin: bottom}
    100% {transform: scaleY(0); transform-origin: bottom} }

  .scene { position: relative; height: __SCROLL__vh; }
  .scene .stick {
    position: sticky; top: 0; height: 100vh; overflow: hidden;
    display: flex; align-items: center; justify-content: center;
    background: #000;
  }
  .scene video {
    width: 100%; height: 100%; object-fit: __FIT__; display: block;
  }
  .scene .overlay {
    position: absolute; left: 0; right: 0; bottom: 0;
    padding: 6vh 6vw;
    background: linear-gradient(transparent, rgba(5,7,9,.72));
    opacity: 0; transform: translateY(12px);
    transition: opacity .45s ease, transform .45s ease;
    pointer-events: none;
  }
  .scene .overlay.on { opacity: 1; transform: none; }
  .overlay .num {
    color: var(--accent); font-weight: 700; font-size: .85rem;
    letter-spacing: .3em;
  }
  .overlay h2 {
    font-size: clamp(1.6rem, 4.5vw, 3rem); font-weight: 800;
    letter-spacing: -0.01em; margin-top: .35rem;
  }

  .bar { position: fixed; top: 0; left: 0; height: 3px; width: 0;
    background: var(--accent); z-index: 10; }
  .dots { position: fixed; right: 18px; top: 50%;
    transform: translateY(-50%); display: flex; flex-direction: column;
    gap: 10px; z-index: 10; }
  .dots span { width: 8px; height: 8px; border-radius: 50%;
    background: #3a4149; transition: background .3s, transform .3s; }
  .dots span.on { background: var(--accent); transform: scale(1.35); }

  .outro .credit { color: #5c656e; font-size: .85rem; margin-top: 2rem; }
  .outro .credit a { color: #9aa3ad; }
  @media (max-width: 640px) { .dots { right: 10px; } }
</style>
</head>
<body>

<div class="bar" id="bar"></div>
<div class="dots" id="dots" aria-hidden="true"></div>

<header class="intro">
  <h1>__TITLE__</h1>
  __SUBTITLE__
  <div class="scroll-hint">Scroll</div>
</header>

__SCENES__

<footer class="outro">
  <p>__OUTRO__</p>
  <p class="credit">__CREDIT__</p>
</footer>

<script>
(function () {
  var scenes = Array.prototype.slice.call(document.querySelectorAll(".scene"));
  var bar = document.getElementById("bar");
  var dotsBox = document.getElementById("dots");
  var state = scenes.map(function (sec, i) {
    var dot = document.createElement("span");
    dotsBox.appendChild(dot);
    var v = sec.querySelector("video");
    v.muted = true;             // belt & suspenders for mobile inline scrub
    return { sec: sec, video: v, overlay: sec.querySelector(".overlay"),
             dot: dot, target: 0, current: 0, dur: 0 };
  });

  state.forEach(function (s) {
    if (s.video.readyState >= 1) s.dur = s.video.duration || 0;
    s.video.addEventListener("loadedmetadata", function () {
      s.dur = s.video.duration || 0;
    });
  });

  // nudge iOS Safari to allow programmatic seeking on inline muted video
  var kicked = false;
  function kick() {
    if (kicked) return; kicked = true;
    state.forEach(function (s) {
      var p = s.video.play();
      if (p && p.then) p.then(function () { s.video.pause(); })
                        .catch(function () {});
      else s.video.pause();
    });
  }
  window.addEventListener("touchstart", kick, { once: true, passive: true });
  window.addEventListener("scroll", kick, { once: true, passive: true });

  function onScroll() {
    var vh = window.innerHeight;
    var doc = document.documentElement;
    var max = doc.scrollHeight - vh;
    bar.style.width = (max > 0 ? (window.scrollY / max) * 100 : 0) + "%";

    state.forEach(function (s) {
      var r = s.sec.getBoundingClientRect();
      var span = r.height - vh;
      var p = span > 0 ? -r.top / span : 0;
      p = Math.max(0, Math.min(1, p));
      s.target = p;
      var active = r.top < vh && r.bottom > 0;
      s.overlay.classList.toggle("on", active && p > 0.02 && p < 0.92);
      s.dot.classList.toggle("on", r.top <= vh * 0.5 && r.bottom > vh * 0.5);
    });
  }

  // Framerate-independent easing (half-life 80 ms), driven by BOTH rAF and
  // an interval timer — rAF alone stalls when the tab is throttled.
  var last = performance.now();
  function step() {
    var now = performance.now();
    var dt = Math.min(0.15, (now - last) / 1000);
    last = now;
    if (dt <= 0) return;
    var k = 1 - Math.pow(2, -dt / 0.08);
    state.forEach(function (s) {
      if (!s.dur || s.video.readyState < 2) return;
      var want = s.target * Math.max(0, s.dur - 0.05);
      s.current += (want - s.current) * k;
      if (Math.abs(s.video.currentTime - s.current) > 0.02) {
        try { s.video.currentTime = s.current; } catch (e) {}
      }
    });
  }
  function raf() { step(); requestAnimationFrame(raf); }
  function onScrollStep() { onScroll(); step(); }

  function sceneTop(i) {
    return state[i].sec.offsetTop;
  }

  function activeSceneIndex() {
    var y = window.scrollY;
    var i;
    for (i = state.length - 1; i >= 0; i--) {
      if (y >= sceneTop(i) - 1) return i;
    }
    return -1;
  }

  function jumpScene(delta) {
    if (!state.length) return;
    var current = activeSceneIndex();
    if (current < 0 && delta < 0) return;
    var next = Math.max(0, Math.min(state.length - 1, current + delta));
    if (next === current) return;
    window.scrollTo({ top: sceneTop(next), behavior: "auto" });
    onScrollStep();
  }

  window.addEventListener("keydown", function (e) {
    if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
    var target = e.target;
    if (target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName))) return;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") {
      e.preventDefault();
      jumpScene(1);
    } else if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
      e.preventDefault();
      jumpScene(-1);
    }
  });

  window.addEventListener("scroll", onScrollStep, { passive: true });
  window.addEventListener("resize", onScroll);
  onScroll();
  requestAnimationFrame(raf);
  setInterval(step, 66);
})();
</script>
</body>
</html>
"""

SCENE = """<section class="scene">
  <div class="stick">
    <video src="videos/%(src)s" poster="posters/%(poster)s"
           muted playsinline preload="auto" tabindex="-1"></video>
    <div class="overlay">
      <span class="num">%(num)s</span>
      <h2>%(title)s</h2>
    </div>
  </div>
</section>
"""


def main():
    ap = argparse.ArgumentParser(description="Folder of clips -> scroll page.")
    ap.add_argument("--clips", required=True, help="folder of video clips")
    ap.add_argument("--out", default="walkthrough", help="output folder")
    ap.add_argument("--title", default="A Scroll-Video Walkthrough")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--outro", default="Thanks for scrolling.")
    ap.add_argument("--credit",
                    default="Made with the Scroll-Video Walkthrough skill.")
    ap.add_argument("--scroll", type=int, default=220,
                    help="scroll length per scene, in vh (bigger = slower)")
    ap.add_argument("--fit", choices=["cover", "contain"], default="cover")
    ap.add_argument("--width", type=int, default=1920,
                    help="max encoded video width")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--crf", type=int, default=21)
    ap.add_argument("--accent", default="#59d1ff")
    ap.add_argument("--serve", type=int, nargs="?", const=8907, default=0,
                    metavar="PORT",
                    help="after building, serve the page locally "
                         "(with the Range support scrubbing needs)")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            die(f"{tool} not found on PATH")
    if not os.path.isdir(args.clips):
        die(f"not a folder: {args.clips}")
    if not re.fullmatch(r"#[0-9a-fA-F]{3,8}", args.accent):
        die(f"--accent must be a hex color like #59d1ff, got {args.accent!r}")

    names = [n for n in sorted(os.listdir(args.clips))
             if os.path.splitext(n)[1].lower() in VIDEO_EXTS]
    if not names:
        die(f"no video clips found in {args.clips}")

    os.makedirs(os.path.join(args.out, "videos"), exist_ok=True)
    os.makedirs(os.path.join(args.out, "posters"), exist_ok=True)

    scenes = []
    for i, name in enumerate(names, 1):
        src = os.path.join(args.clips, name)
        meta = probe(src)
        if not meta:
            print(f"  ! skipping unreadable: {name}")
            continue
        w, h, dur = meta
        out_name = f"{i:02d}.mp4"
        poster_name = f"{i:02d}.jpg"
        out_vid = os.path.join(args.out, "videos", out_name)
        scale = f"scale='min({args.width},iw)':-2"
        if (os.path.isfile(out_vid)
                and os.path.getmtime(out_vid) > os.path.getmtime(src)):
            print(f"  scene {i:02d}: {name} (already encoded, skipping)")
        else:
            print(f"  encoding scene {i:02d}: {name} ({dur:.1f}s)")
            # tiny GOP + no B-frames = the liquid scrub
            run(["ffmpeg", "-y", "-v", "error", "-i", src,
                 "-vf", f"{scale},fps={args.fps},format=yuv420p",
                 "-c:v", "libx264", "-preset", "medium", "-crf", str(args.crf),
                 "-g", "6", "-bf", "0", "-an", "-movflags", "+faststart",
                 out_vid])
            run(["ffmpeg", "-y", "-v", "error", "-i", src,
                 "-vf", f"{scale}", "-frames:v", "1", "-q:v", "3",
                 os.path.join(args.out, "posters", poster_name)])
        scenes.append(SCENE % {
            "src": out_name, "poster": poster_name,
            "num": f"{i:02d} / {len(names):02d}",
            "title": html.escape(title_from_filename(name)),
        })

    if not scenes:
        die("no usable clips")

    subtitle = (f"<p>{html.escape(args.subtitle)}</p>" if args.subtitle else "")
    page = (PAGE
            .replace("__TITLE__", html.escape(args.title))
            .replace("__SUBTITLE__", subtitle)
            .replace("__OUTRO__", html.escape(args.outro))
            .replace("__CREDIT__", html.escape(args.credit))
            .replace("__SCROLL__", str(max(120, args.scroll)))
            .replace("__FIT__", args.fit)
            .replace("__ACCENT__", args.accent)
            .replace("__SCENES__", "\n".join(scenes)))
    index = os.path.join(args.out, "index.html")
    with open(index, "w") as f:
        f.write(page)

    print(f"done: {index}  ({len(scenes)} scenes)")
    if args.serve:
        serve(args.out, args.serve)
    else:
        print(f"view it:  python3 {os.path.abspath(sys.argv[0])} "
              f"--clips {args.clips} --out {args.out} --serve")
        print("(don't use `python3 -m http.server` — it lacks the Range "
              "support video scrubbing needs; any real web host is fine)")


if __name__ == "__main__":
    main()
