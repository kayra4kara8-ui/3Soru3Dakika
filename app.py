"""
Elif Aracıoğlu · Eczacı Video Stüdyo
──────────────────────────────────────
PPTX + Ses → Senkronize MP4
Birebir senkron: slayt başına segment encode → concat
"""
import streamlit as st
import io, os, math, base64, tempfile, subprocess, shutil, json, time, re
import numpy as np

# ─── ffmpeg ───────────────────────────────────────────────────────────────────
def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.exists(p):
            return p
    return None

FFMPEG = _get_ffmpeg()
if FFMPEG:
    os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False
try:
    import imageio  # noqa
    IMAGEIO_OK = True
except ImportError:
    IMAGEIO_OK = False
try:
    from pptx import Presentation
    PPTX_OK = True
except ImportError:
    PPTX_OK = False

LO_BIN   = "/usr/bin/libreoffice" if os.path.exists("/usr/bin/libreoffice") else "/usr/bin/soffice"
LO_OK    = os.path.exists(LO_BIN)
PPM_OK   = os.path.exists("/usr/bin/pdftoppm")
FFMPEG_OK = FFMPEG is not None

VIDEO_W, VIDEO_H, VIDEO_FPS = 1280, 720, 24

# Slayt watermark için Elif'in rengi — eczacı yeşili
BRAND_RGB = (52, 168, 131)   # teal-yeşil
BRAND_HEX = "34A883"

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]

# ═══════════════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYONLAR
# ═══════════════════════════════════════════════════════════════════════════════
def _font(size):
    if not PIL_OK:
        return None
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _run(cmd, timeout=900, step_name=""):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            stderr_snippet = result.stderr[-800:] if result.stderr else "(çıktı yok)"
            raise RuntimeError(
                f"[{step_name}] Komut başarısız (kod {result.returncode}):\n"
                f"CMD: {' '.join(str(c) for c in cmd)}\n"
                f"STDERR: {stderr_snippet}"
            )
        return result
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"[{step_name}] Zaman aşımı — {timeout}s doldu.")

def _ffprobe_path():
    if FFMPEG:
        ffprobe = FFMPEG.replace("ffmpeg", "ffprobe")
        if os.path.exists(ffprobe):
            return ffprobe
    found = shutil.which("ffprobe")
    if found:
        return found
    for p in ["/usr/bin/ffprobe", "/usr/local/bin/ffprobe"]:
        if os.path.exists(p):
            return p
    return "ffprobe"

def audio_duration_ffprobe(path: str) -> float:
    try:
        r = subprocess.run(
            [_ffprobe_path(), "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=30,
        )
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        size = os.path.getsize(path) if os.path.exists(path) else 0
        return max(1.0, size / 16_000)

def audio_duration_from_bytes(data: bytes) -> float:
    if not data:
        return 3.0
    tmp = tempfile.mktemp(suffix=".audio")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
        return audio_duration_ffprobe(tmp)
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass

def find_silence_splits(audio_path: str, n_slides: int, total_dur: float) -> list:
    """Sessizlik noktalarında kesim yap (global mod için)."""
    per_slide = total_dur / max(n_slides, 1)
    split_times = []
    try:
        r = subprocess.run(
            [FFMPEG, "-y", "-i", audio_path,
             "-af", "silencedetect=noise=-35dB:duration=0.25",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
        ends   = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
        mids   = [(s + e) / 2 for s, e in zip(starts, ends)]
    except Exception:
        mids = []

    for i in range(1, n_slides):
        target = i * per_slide
        tol = per_slide * 0.15
        cands = [m for m in mids if abs(m - target) <= tol]
        split_times.append(min(cands, key=lambda x: abs(x - target)) if cands else target)
    return split_times

# ═══════════════════════════════════════════════════════════════════════════════
# PPTX → GÖRÜNTÜLER
# ═══════════════════════════════════════════════════════════════════════════════
def pptx_to_images(pptx_bytes: bytes) -> list:
    tmp = tempfile.mkdtemp(prefix="pptx2img_")
    try:
        pptx_path = os.path.join(tmp, "presentation.pptx")
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)
        _run([LO_BIN, "--headless", "--convert-to", "pdf",
              "--outdir", tmp, pptx_path],
             timeout=180, step_name="LibreOffice PDF")
        pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
        if not pdfs:
            raise RuntimeError("LibreOffice PDF üretemedi.")
        pdf_path = os.path.join(tmp, pdfs[0])
        img_prefix = os.path.join(tmp, "slide")
        _run(["pdftoppm", "-jpeg", "-r", "192", pdf_path, img_prefix],
             timeout=120, step_name="pdftoppm")
        files = sorted([
            os.path.join(tmp, f) for f in os.listdir(tmp)
            if f.startswith("slide") and f.endswith((".jpg", ".jpeg"))
        ])
        if not files:
            raise RuntimeError("pdftoppm görüntü üretemedi.")
        images = []
        for p in files:
            src = Image.open(p).convert("RGB")
            sw, sh = src.size
            scale = min(VIDEO_W / sw, VIDEO_H / sh)
            nw, nh = int(sw * scale), int(sh * scale)
            canvas = Image.new("RGB", (VIDEO_W, VIDEO_H), (8, 8, 18))
            canvas.paste(src.resize((nw, nh), Image.LANCZOS),
                         ((VIDEO_W - nw) // 2, (VIDEO_H - nh) // 2))
            images.append(canvas)
        return images
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def read_pptx_slide_count(pptx_bytes: bytes) -> int:
    try:
        prs = Presentation(io.BytesIO(pptx_bytes))
        return len(prs.slides)
    except Exception:
        return 0

# ═══════════════════════════════════════════════════════════════════════════════
# SES HAZIRLAMA
# ═══════════════════════════════════════════════════════════════════════════════
def prepare_audio_segments(
    global_audio: bytes | None,
    use_global: bool,
    slide_audio_map: dict,
    durations: dict,
    n_slides: int,
    work_dir: str,
) -> tuple[list, list]:
    audio_paths, dur_list = [], []

    if use_global and global_audio:
        gpath = os.path.join(work_dir, "global.audio")
        with open(gpath, "wb") as f:
            f.write(global_audio)
        total_dur = audio_duration_ffprobe(gpath)
        splits    = find_silence_splits(gpath, n_slides, total_dur)
        boundaries = [0.0] + splits + [total_dur]
        for i in range(n_slides):
            ss  = boundaries[i]
            dur = boundaries[i + 1] - boundaries[i]
            seg = os.path.join(work_dir, f"seg_{i:04d}.aac")
            try:
                _run([FFMPEG, "-y",
                      "-ss", f"{ss:.6f}", "-t", f"{dur:.6f}", "-i", gpath,
                      "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                      "-af", "aresample=async=1:min_hard_comp=0.1:first_pts=0",
                      seg], timeout=60, step_name=f"Global seg {i+1}")
                audio_paths.append(seg)
                dur_list.append(audio_duration_ffprobe(seg))
            except Exception:
                audio_paths.append(None)
                dur_list.append(dur)
    else:
        for i in range(n_slides):
            ab = slide_audio_map.get(i)
            if ab:
                raw = os.path.join(work_dir, f"raw_{i:04d}.audio")
                aac = os.path.join(work_dir, f"seg_{i:04d}.aac")
                with open(raw, "wb") as f:
                    f.write(ab)
                try:
                    _run([FFMPEG, "-y", "-i", raw,
                          "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                          "-af", "aresample=async=1:min_hard_comp=0.1:first_pts=0",
                          aac], timeout=60, step_name=f"Ses {i+1}")
                    audio_paths.append(aac)
                    dur_list.append(audio_duration_ffprobe(aac))
                except Exception:
                    audio_paths.append(None)
                    dur_list.append(durations.get(i, 3.0))
            else:
                audio_paths.append(None)
                dur_list.append(durations.get(i, 3.0))
    return audio_paths, dur_list

# ═══════════════════════════════════════════════════════════════════════════════
# KARE RENDER — Elif Aracıoğlu markası + slayt overlay
# ═══════════════════════════════════════════════════════════════════════════════
def render_frame(slide_img, slide_idx: int, total: int, t: float, has_audio: bool):
    frame = slide_img.copy()
    draw  = ImageDraw.Draw(frame)
    w, h  = frame.size
    c     = BRAND_RGB

    # ── Üst bant ──────────────────────────────────────────────
    draw.rectangle([0, 0, w, 48], fill=(6, 12, 10, 215))
    draw.rectangle([0, 45, w, 48], fill=c)

    fn15 = _font(15); fn13 = _font(13); fn11 = _font(11)
    draw.text((16, 13), "💊 Eczacı Elif Aracıoğlu", font=fn15, fill=(*c, 230))

    # Canlı göstergesi (sağ üst)
    da = int(170 + 85 * math.sin(t * math.pi * 5))
    draw.ellipse([w - 95, 16, w - 84, 27], fill=(220, 60, 60, da))
    draw.text((w - 80, 13), "YAYIN", font=fn11, fill=(220, 60, 60, 220))

    # ── Alt bant ──────────────────────────────────────────────
    by = h - 48
    draw.rectangle([0, by, w, h], fill=(6, 12, 10, 225))
    draw.rectangle([0, by, w, by + 3], fill=c)
    draw.text((16, by + 14), f"Slayt {slide_idx + 1}  /  {total}",
              font=fn13, fill=(170, 220, 200, 210))

    # İlerleme çubuğu
    pw = int(w * (slide_idx + t) / max(total, 1))
    draw.rectangle([0, h - 5, w, h], fill=(14, 22, 18))
    draw.rectangle([0, h - 5, pw, h], fill=c)

    # Ses dalgası animasyonu
    if has_audio:
        bc, bw, bg = 8, 5, 4
        bx0 = w - bc * (bw + bg) - 18
        by2 = h - 9
        for bi in range(bc):
            bh = int(3 + 14 * abs(math.sin(t * math.pi * 4.5 + bi * 1.1)))
            bx = bx0 + bi * (bw + bg)
            draw.rounded_rectangle([bx, by2 - bh, bx + bw, by2], radius=2, fill=c)

    return np.array(frame)

# ═══════════════════════════════════════════════════════════════════════════════
# BİREBİR SENKRON VİDEO — Segment bazlı encode
# ═══════════════════════════════════════════════════════════════════════════════
def _make_silence(work_dir: str, idx: int, dur: float) -> str:
    path = os.path.join(work_dir, f"sil_{idx:04d}.aac")
    _run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
          "-t", f"{dur:.6f}", "-c:a", "aac", "-b:a", "128k", path],
         timeout=30, step_name=f"Sessizlik {idx}")
    return path

def _encode_segment(img, slide_idx: int, total: int,
                    audio_path, dur: float, work_dir: str, idx: int) -> str:
    has_audio = audio_path is not None and os.path.exists(audio_path)
    if not has_audio:
        try:
            audio_path = _make_silence(work_dir, idx, dur)
            has_audio  = True
        except Exception:
            pass

    actual_dur = audio_duration_ffprobe(audio_path) if has_audio else dur
    nf         = max(1, round(actual_dur * VIDEO_FPS))
    seg_path   = os.path.join(work_dir, f"chunk_{idx:04d}.mp4")

    cmd = (
        [FFMPEG, "-y",
         "-f", "rawvideo", "-vcodec", "rawvideo",
         "-s", f"{VIDEO_W}x{VIDEO_H}", "-pix_fmt", "rgb24",
         "-r", str(VIDEO_FPS), "-i", "pipe:0"]
        + (["-i", audio_path] if has_audio
           else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
        + ["-t", f"{actual_dur:.6f}",
           "-map", "0:v:0", "-map", "1:a:0",
           "-vcodec", "libx264", "-crf", "22", "-preset", "fast",
           "-pix_fmt", "yuv420p", "-r", str(VIDEO_FPS), "-vsync", "cfr",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           "-af", "aresample=async=1:min_hard_comp=0.1:first_pts=0",
           "-movflags", "+faststart", seg_path]
    )
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise RuntimeError(f"ffmpeg çalıştırılamadı: '{FFMPEG}'")
    try:
        for fi in range(nf):
            t = fi / max(nf - 1, 1)
            proc.stdin.write(
                render_frame(img, slide_idx, total, t, has_audio).astype(np.uint8).tobytes()
            )
        proc.stdin.close()
        proc.wait(timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"Segment encode başarısız (kod {proc.returncode})")
    except Exception as e:
        proc.kill()
        raise RuntimeError(f"[Segment {idx}] {e}")
    return seg_path

def build_video(slide_images, audio_paths, durations, work_dir, cb=None) -> bytes:
    if not FFMPEG or not os.path.exists(FFMPEG):
        raise RuntimeError("ffmpeg bulunamadı!\npackages.txt → ffmpeg\nveya requirements.txt → imageio[ffmpeg]")

    n       = len(slide_images)
    tmp_out = os.path.join(work_dir, "output.mp4")
    segs    = []

    for idx, (img, aud, dur) in enumerate(zip(slide_images, audio_paths, durations)):
        if cb:
            cb(0.05 + 0.82 * (idx / n),
               f"Slayt {idx+1}/{n} encode ediliyor…")
        segs.append(_encode_segment(img, idx, n, aud, dur, work_dir, idx))

    if cb: cb(0.90, "Segmentler birleştiriliyor…")
    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for p in segs:
            f.write(f"file '{p}'\n")
    _run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
          "-c", "copy", "-vsync", "vfr", "-movflags", "+faststart", tmp_out],
         timeout=600, step_name="Final concat")

    if cb: cb(1.0, "Tamamlandı! ✅")
    if os.path.exists(tmp_out):
        with open(tmp_out, "rb") as f:
            return f.read()
    raise RuntimeError("Çıktı MP4 oluşturulamadı.")

# ═══════════════════════════════════════════════════════════════════════════════
# CSS — Eczacı yeşili, medikal premium tema
# ═══════════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');
:root{
  --green:#34A883;--green-dim:rgba(52,168,131,.15);--green-glow:rgba(52,168,131,.06);
  --cream:#f0ede6;--ink:#0d1a16;
  --bg:#080f0c;--surface:rgba(255,255,255,.028);--border:rgba(255,255,255,.07);
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;background:var(--bg);}
.stApp{
  background:
    radial-gradient(ellipse 70% 55% at 15% 10%,rgba(52,168,131,.07) 0%,transparent 65%),
    radial-gradient(ellipse 50% 40% at 85% 85%,rgba(30,80,60,.12) 0%,transparent 60%),
    var(--bg);
  color:#dde8e3;
}

/* Sidebar */
section[data-testid="stSidebar"]{
  background:rgba(5,10,8,.97);
  border-right:1px solid var(--green-dim);
}

/* Hero */
.hero{
  display:flex;flex-direction:column;align-items:center;
  padding:2.8rem 1rem 1.8rem;
  border-bottom:1px solid var(--green-dim);
  margin-bottom:1.8rem;
  background:radial-gradient(ellipse 55% 70% at 50% 0%,rgba(52,168,131,.05),transparent 65%);
}
.hero-pill{
  display:inline-flex;align-items:center;gap:.45rem;
  padding:.28rem .85rem;border-radius:50px;
  background:var(--green-dim);border:1px solid rgba(52,168,131,.3);
  font-size:.67rem;letter-spacing:.18em;text-transform:uppercase;
  color:var(--green);margin-bottom:1.1rem;font-weight:600;
}
.hero h1{
  font-family:'Cormorant Garamond',serif;
  font-size:2.6rem;font-weight:600;
  color:var(--cream);letter-spacing:-.01em;
  text-align:center;margin:0 0 .3rem;line-height:1.1;
}
.hero h1 em{
  font-style:italic;color:var(--green);
}
.hero-sub{
  font-size:.75rem;color:#4a6558;letter-spacing:.16em;
  text-transform:uppercase;text-align:center;
}
.hero-line{
  width:48px;height:2px;background:var(--green);
  margin:1rem auto 0;border-radius:2px;opacity:.6;
}

/* Adım başlığı */
.step-head{
  display:flex;align-items:center;gap:.75rem;
  padding:.9rem 0 .5rem;
  border-bottom:1px solid var(--border);
  margin-bottom:.9rem;
}
.step-num{
  width:28px;height:28px;border-radius:50%;flex-shrink:0;
  background:var(--green-dim);border:1px solid rgba(52,168,131,.35);
  display:flex;align-items:center;justify-content:center;
  font-size:.72rem;font-weight:700;color:var(--green);
}
.step-title{
  font-size:.8rem;letter-spacing:.14em;text-transform:uppercase;
  color:#4a7060;font-weight:600;
}

/* Info kartı */
.info-row{
  display:flex;flex-wrap:wrap;gap:.6rem;padding:.6rem .9rem;
  background:var(--green-glow);border:1px solid var(--green-dim);
  border-radius:10px;font-size:.78rem;color:#5a8070;
  align-items:center;margin:.5rem 0;
}
.info-row strong{color:var(--green);}

/* Ses kutusu */
.audio-box{
  padding:.9rem 1rem;background:var(--surface);
  border:1px solid var(--border);border-radius:12px;
  margin:.4rem 0;
}
.audio-label{
  font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;
  color:#4a6558;margin-bottom:.5rem;font-weight:600;
}

/* Slide önizleme kartı */
.sl-card{
  padding:.55rem .8rem;margin:.22rem 0;
  background:var(--surface);border:1px solid var(--border);
  border-radius:9px;border-left:3px solid var(--green);
}
.sl-num{font-size:.63rem;font-weight:700;letter-spacing:.12em;
  text-transform:uppercase;color:var(--green);margin-bottom:.15rem;}
.sl-dur{font-size:.7rem;color:#4a6558;}

/* Butonlar */
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#2d9970,#45c294)!important;
  color:#040a07!important;font-weight:700!important;
  border:none!important;letter-spacing:.04em;
}
.stButton>button[kind="primary"]:hover{
  filter:brightness(1.08);transform:translateY(-1px);
  box-shadow:0 4px 22px rgba(52,168,131,.28)!important;
}

/* Progress */
.stProgress>div>div{border-radius:10px;}

/* İndirme linki */
.dl-alt{
  display:block;text-align:center;padding:9px 14px;margin-top:8px;
  background:rgba(52,168,131,.07);border:1px solid rgba(52,168,131,.2);
  color:var(--green);border-radius:9px;font-weight:600;font-size:.8rem;
  text-decoration:none;transition:background .18s;
}
.dl-alt:hover{background:rgba(52,168,131,.14);}

/* Sistem durumu */
.dep{font-size:.72rem;margin:.1rem 0;line-height:1.6;}
.ok{color:#5cba8a;}.er{color:#d97070;}

/* Hata kutusu */
.warn-box{
  padding:.75rem 1rem;margin:.5rem 0;border-radius:10px;
  background:rgba(217,112,112,.07);border:1px solid rgba(217,112,112,.22);
  font-size:.78rem;color:#d97070;line-height:1.6;
}
.warn-box code{
  background:rgba(255,255,255,.07);padding:.1rem .3rem;
  border-radius:4px;font-size:.73rem;
}

/* Sidebar marka */
.sb-brand{
  text-align:center;padding:1.1rem 0 .7rem;
  border-bottom:1px solid var(--green-dim);margin-bottom:1rem;
}
.sb-brand-name{
  font-family:'Cormorant Garamond',serif;
  font-size:1.1rem;color:var(--cream);letter-spacing:.04em;
}
.sb-brand-sub{
  font-size:.59rem;color:#3a5548;letter-spacing:.17em;
  text-transform:uppercase;margin-top:3px;
}

audio{width:100%;border-radius:8px;margin:4px 0;}
hr{border-color:var(--border);}
input[type="text"],input[type="number"]{
  background:rgba(255,255,255,.04)!important;
  border:1px solid rgba(255,255,255,.09)!important;
  color:#dde8e3!important;border-radius:8px!important;
}
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "pptx_bytes":    None,
        "n_slides":      0,
        "slide_audio":   {},   # {idx: bytes}
        "global_audio":  None,
        "use_global":    True,
        "durations":     {},   # {idx: float}
        "video_bytes":   None,
        "slide_images":  [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">
          <div class="sb-brand-name">💊 Elif Aracıoğlu</div>
          <div class="sb-brand-sub">Eczacı · Video Stüdyo</div>
        </div>
        """, unsafe_allow_html=True)

        # Sistem durumu
        checks = [
            ("Pillow",       PIL_OK,    "pip: pillow"),
            ("python-pptx",  PPTX_OK,   "pip: python-pptx"),
            ("imageio",      IMAGEIO_OK,"pip: imageio[ffmpeg]"),
            ("LibreOffice",  LO_OK,     "packages.txt: libreoffice"),
            ("pdftoppm",     PPM_OK,    "packages.txt: poppler-utils"),
            ("ffmpeg",       FFMPEG_OK, "packages.txt: ffmpeg"),
        ]
        st.markdown('<div style="font-size:.6rem;letter-spacing:.15em;text-transform:uppercase;color:#3a5548;margin-bottom:.4rem;">Sistem Durumu</div>', unsafe_allow_html=True)
        for name, ok, hint in checks:
            icon = "🟢" if ok else "🔴"
            cls  = "ok" if ok else "er"
            extra = f' <span style="color:#2a3d34;font-size:.61rem;">— {hint}</span>' if not ok else ""
            st.markdown(f'<div class="dep {cls}">{icon} {name}{extra}</div>', unsafe_allow_html=True)

        if not all([PIL_OK, PPTX_OK, IMAGEIO_OK, LO_OK, PPM_OK, FFMPEG_OK]):
            st.markdown('<div class="warn-box">⚠️ Eksik bağımlılık var. Yukarıdaki ipuçlarını inceleyin.</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
        <div style="font-size:.6rem;color:#2a3d34;text-align:center;line-height:1.8;">
          v10.0 · Segment Bazlı Birebir Senkron<br>
          Sessizlik Analizi · Letterbox · 192 DPI
        </div>
        """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ANA SAYFA
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="Elif Aracıoğlu · Video Stüdyo",
        page_icon="💊",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    render_sidebar()

    # ── Hero ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero">
      <div class="hero-pill">💊 Eczacı Video Stüdyo</div>
      <h1>Elif <em>Aracıoğlu</em></h1>
      <div class="hero-sub">Sunum · Ses · Senkronize Video</div>
      <div class="hero-line"></div>
    </div>
    """, unsafe_allow_html=True)

    col_main, col_side = st.columns([3, 2], gap="large")

    # ══════════════════════════════════════════════════════════════════════════
    # SOL SÜTUN — PPTX + SES
    # ══════════════════════════════════════════════════════════════════════════
    with col_main:

        # ── ADIM 1: PPTX ──────────────────────────────────────────────────────
        st.markdown("""
        <div class="step-head">
          <div class="step-num">1</div>
          <div class="step-title">PowerPoint Dosyası</div>
        </div>
        """, unsafe_allow_html=True)

        pptx_file = st.file_uploader(
            "PPTX yükleyin", type=["pptx"],
            key="up_pptx", label_visibility="collapsed",
        )
        if pptx_file is not None:
            raw = pptx_file.read()
            if raw != st.session_state.pptx_bytes:
                st.session_state.pptx_bytes   = raw
                st.session_state.video_bytes  = None
                st.session_state.slide_audio  = {}
                st.session_state.durations    = {}
                st.session_state.slide_images = []
                with st.spinner("Slayt sayısı okunuyor…"):
                    st.session_state.n_slides = read_pptx_slide_count(raw)

        n = st.session_state.n_slides
        if n > 0:
            st.markdown(
                f'<div class="info-row">📊 <strong>{n}</strong> slayt yüklendi'
                f'  ·  📐 <strong>1280×720</strong>  ·  🎬 <strong>24 FPS</strong></div>',
                unsafe_allow_html=True
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── ADIM 2: SES ───────────────────────────────────────────────────────
        st.markdown("""
        <div class="step-head">
          <div class="step-num">2</div>
          <div class="step-title">Ses Dosyası</div>
        </div>
        """, unsafe_allow_html=True)

        if n == 0:
            st.info("Önce PPTX yükleyin.")
        else:
            mode = st.radio(
                "Ses modu",
                ["🔊 Tek ses — tüm sunuma otomatik böl", "🎙️ Her slayta ayrı ses"],
                key="up_mode", horizontal=True, label_visibility="collapsed",
            )
            use_global = mode.startswith("🔊")
            st.session_state.use_global = use_global

            if use_global:
                st.caption("Ses, sessizlik noktalarında slaytlara akıllıca bölünür.")
                gf = st.file_uploader(
                    "Genel ses", type=["mp3","wav","m4a","ogg"],
                    key="up_glob", label_visibility="collapsed",
                )
                if gf is not None:
                    ab = gf.read()
                    st.session_state.global_audio = ab
                    dur = audio_duration_from_bytes(ab)
                    per = dur / max(n, 1)
                    for i in range(n):
                        st.session_state.durations[i] = per
                    st.audio(ab, format="audio/mp3")
                    st.markdown(
                        f'<div class="info-row">⏱️ Toplam <strong>{dur:.1f}s</strong>'
                        f'  ·  Slayt başına ~<strong>{per:.1f}s</strong></div>',
                        unsafe_allow_html=True
                    )
            else:
                st.caption("Her slayta bağımsız ses atayın. Ses yüklenmeyen slaytlara sessizlik eklenir.")
                for i in range(n):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        uf = st.file_uploader(
                            f"Slayt {i+1}", type=["mp3","wav","m4a","ogg"],
                            key=f"up_sl_{i}", label_visibility="visible",
                        )
                        if uf is not None:
                            ab = uf.read()
                            st.session_state.slide_audio[i] = ab
                            d = audio_duration_from_bytes(ab)
                            st.session_state.durations[i]   = d
                            st.audio(ab, format="audio/mp3")
                    with c2:
                        dv = st.session_state.durations.get(i, 3.0)
                        icon = "🔊" if i in st.session_state.slide_audio else "🔇"
                        st.metric(f"S{i+1}", f"{icon} {dv:.1f}s")

            # Manuel süre ayarı
            with st.expander("⚙️ Süreleri manuel ayarla (opsiyonel)"):
                per_row = min(n, 6)
                rows = [st.columns(per_row) for _ in range(math.ceil(n / per_row))]
                for i in range(n):
                    r, c = i // per_row, i % per_row
                    with rows[r][c]:
                        d = st.number_input(
                            f"S{i+1}(s)", min_value=0.5, max_value=300.0,
                            value=float(st.session_state.durations.get(i, 3.0)),
                            step=0.5, key=f"up_dur_{i}",
                        )
                        st.session_state.durations[i] = d

    # ══════════════════════════════════════════════════════════════════════════
    # SAĞ SÜTUN — ÖZET + VİDEO OLUŞTUR
    # ══════════════════════════════════════════════════════════════════════════
    with col_side:
        st.markdown("""
        <div class="step-head">
          <div class="step-num">3</div>
          <div class="step-title">Video Oluştur</div>
        </div>
        """, unsafe_allow_html=True)

        n = st.session_state.n_slides
        can_go = (
            st.session_state.pptx_bytes is not None
            and n > 0
            and PIL_OK and IMAGEIO_OK and PPTX_OK and LO_OK and PPM_OK and FFMPEG_OK
        )

        if n > 0:
            # Özet
            total_secs = sum(st.session_state.durations.get(i, 3.0) for i in range(n))
            mins, secs = divmod(int(total_secs), 60)

            # Slayt süresi kartları
            for i in range(min(n, 8)):
                dur_v = st.session_state.durations.get(i, 3.0)
                has_a = (i in st.session_state.slide_audio) or st.session_state.use_global
                icon  = "🔊" if has_a else "🔇"
                st.markdown(
                    f'<div class="sl-card">'
                    f'<div class="sl-num">Slayt {i+1}</div>'
                    f'<div class="sl-dur">{icon} {dur_v:.1f} saniye</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            if n > 8:
                st.caption(f"… ve {n-8} slayt daha")

            st.markdown(
                f'<div class="info-row" style="margin-top:.8rem;">'
                f'⏱️ Toplam ~<strong>{mins}:{secs:02d}</strong>'
                f'  ·  <strong>{n}</strong> slayt</div>',
                unsafe_allow_html=True
            )

        if not can_go and st.session_state.pptx_bytes:
            missing = [n for n, ok, _ in [
                ("Pillow",PIL_OK,""), ("imageio",IMAGEIO_OK,""),
                ("python-pptx",PPTX_OK,""), ("libreoffice",LO_OK,""),
                ("poppler-utils",PPM_OK,""), ("ffmpeg",FFMPEG_OK,"")
            ] if not ok]
            st.markdown(
                f'<div class="warn-box">❌ Eksik: {", ".join(missing)}</div>',
                unsafe_allow_html=True
            )

        if can_go:
            make_btn = st.button(
                "🎬 Video Oluştur", type="primary",
                use_container_width=True, key="btn_make",
                disabled=(st.session_state.video_bytes is not None),
            )
            if st.button("🔄 Sıfırla", use_container_width=True, key="btn_reset"):
                st.session_state.video_bytes = None
                st.rerun()

            if make_btn:
                prog = st.progress(0)
                stat = st.empty()
                t0   = time.time()

                def cb(pct, msg):
                    prog.progress(min(float(pct), 1.0))
                    stat.markdown(
                        f"⚙️ **{msg}**  "
                        f'<span style="color:#3a5548;font-size:.75rem;">'
                        f'— {time.time()-t0:.0f}s</span>',
                        unsafe_allow_html=True,
                    )

                work_dir = tempfile.mkdtemp(prefix="elif_studio_")
                try:
                    cb(0.02, "Slaytlar görüntüye dönüştürülüyor…")
                    slide_imgs = pptx_to_images(st.session_state.pptx_bytes)
                    n_actual   = len(slide_imgs)

                    cb(0.10, f"Ses segmentleri hazırlanıyor ({n_actual} slayt)…")
                    audio_paths, dur_list = prepare_audio_segments(
                        global_audio    = st.session_state.global_audio,
                        use_global      = st.session_state.use_global,
                        slide_audio_map = st.session_state.slide_audio,
                        durations       = st.session_state.durations,
                        n_slides        = n_actual,
                        work_dir        = work_dir,
                    )
                    video_bytes = build_video(
                        slide_images = slide_imgs,
                        audio_paths  = audio_paths,
                        durations    = dur_list,
                        work_dir     = work_dir,
                        cb           = cb,
                    )
                    st.session_state.video_bytes  = video_bytes
                    st.session_state.slide_images = slide_imgs
                except RuntimeError as e:
                    st.error(f"❌ Hata:\n\n{e}")
                except Exception as e:
                    import traceback
                    st.error(f"❌ Beklenmedik hata: {e}")
                    with st.expander("Traceback"):
                        st.code(traceback.format_exc())
                finally:
                    shutil.rmtree(work_dir, ignore_errors=True)

        # ── Çıktı ─────────────────────────────────────────────────────────────
        if st.session_state.video_bytes:
            vb   = st.session_state.video_bytes
            size = len(vb)
            size_str = (f"{size/(1024*1024):.1f} MB" if size > 1_048_576
                        else f"{size//1024:,} KB")
            st.success(f"✅ Video hazır — {size_str}")
            st.video(vb)
            st.download_button(
                "⬇️ MP4 İndir", data=vb,
                file_name="elif_aracıoglu_sunum.mp4",
                mime="video/mp4",
                use_container_width=True, type="primary",
            )
            b64v = base64.b64encode(vb).decode()
            st.markdown(
                f'<a href="data:video/mp4;base64,{b64v}" '
                f'download="elif_aracıoglu_sunum.mp4" class="dl-alt">'
                '📥 Alternatif İndirme</a>',
                unsafe_allow_html=True,
            )

    # ── Önizleme ──────────────────────────────────────────────────────────────
    if st.session_state.slide_images:
        st.markdown("---")
        st.markdown("""
        <div class="step-head">
          <div class="step-num">👁</div>
          <div class="step-title">Slayt Önizlemeleri</div>
        </div>
        """, unsafe_allow_html=True)
        imgs = st.session_state.slide_images
        cols = st.columns(min(len(imgs), 4))
        for i, img in enumerate(imgs):
            with cols[i % 4]:
                st.image(img, caption=f"Slayt {i+1}", use_container_width=True)

if __name__ == "__main__":
    main()
