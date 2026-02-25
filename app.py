"""
3 Soru 3 Dakika | Eczacı Elif Aracıoğlu | Video Stüdyo v11.0
──────────────────────────────────────────────────────────────
• Site adı: 3 Soru 3 Dakika — Eczacı Elif Aracıoğlu markası
• BİREBİR SENKRON: slayt başına ayrı MP4 segment (video+ses birlikte)
• Senkron garantisi: video kare sayısı = round(gerçek_ses_süresi × FPS)
• AAC priming delay: aresample async=1 first_pts=0 ile sıfırlanır
• Sessizlik analizi (global mod): doğal duraksamalarda kesim
• Letterbox/pillarbox: slayt orijinal en-boy oranı korunur
• Dinamik karakter yönetimi: istediğiniz kadar konuşmacı
• Stream render: RAM'de kare biriktirme yok
"""
import streamlit as st
import io, os, math, base64, tempfile, subprocess, shutil, json, time
import numpy as np

# ── ffmpeg ────────────────────────────────────────────────────────────────────
def _get_ffmpeg():
    # 1. imageio_ffmpeg (en güvenilir yol — kendi binary'sini barındırır)
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    # 2. PATH'te ffmpeg
    found = shutil.which("ffmpeg")
    if found:
        return found
    # 3. Yaygın sabit konumlar
    for p in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
        if os.path.exists(p):
            return p
    # 4. Bulunamadı — None döndür, kontrol build_video'da yapılır
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

LO_BIN = "/usr/bin/libreoffice" if os.path.exists("/usr/bin/libreoffice") else "/usr/bin/soffice"
LO_OK  = os.path.exists(LO_BIN)
PPM_OK = os.path.exists("/usr/bin/pdftoppm")
FFMPEG_OK = FFMPEG is not None

VIDEO_W, VIDEO_H, VIDEO_FPS = 1280, 720, 24
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]

# ── Varsayılan renk paleti (yeni eklenen karakterler için sırayla atanır) ───
PALETTE = [
    {"hex": "C9A84C", "rgb": (201,168, 76), "emoji": "🎤"},  # Altın — Elif
    {"hex": "4C9FCA", "rgb": ( 76,159,202), "emoji": "👩‍💼"},  # Mavi
    {"hex": "A0C878", "rgb": (160,200,120), "emoji": "🎧"},  # Yeşil
    {"hex": "E07B7B", "rgb": (195, 90, 90), "emoji": "🎙️"},  # Kırmızı
    {"hex": "B57FCC", "rgb": (155,105,195), "emoji": "💬"},  # Mor
    {"hex": "7EC8C8", "rgb": ( 80,178,178), "emoji": "📢"},  # Teal
    {"hex": "F0A060", "rgb": (220,140, 70), "emoji": "🗣️"},  # Turuncu
    {"hex": "88BBEE", "rgb": (100,160,220), "emoji": "👤"},  # Açık mavi
]

# Varsayılan karakter listesi — sadece Elif
DEFAULT_CHARACTERS = [
    {"name": "Elif Aracıoğlu", "role": "Eczacı", **PALETTE[0]}
]

# ═════════════════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ═════════════════════════════════════════════════════════════════════════════
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
            stderr_snippet = result.stderr[-600:] if result.stderr else "(çıktı yok)"
            raise RuntimeError(
                f"[{step_name}] Komut başarısız (kod {result.returncode}):\n"
                f"CMD: {' '.join(str(c) for c in cmd)}\n"
                f"STDERR: {stderr_snippet}"
            )
        return result
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"[{step_name}] Zaman aşımı — {timeout}s doldu.\n"
            f"CMD: {' '.join(str(c) for c in cmd)}"
        )

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

def audio_duration_ffprobe(audio_path: str) -> float:
    try:
        r = subprocess.run(
            [_ffprobe_path(), "-v", "error", "-show_entries", "format=duration",
             "-of", "json", audio_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
        return float(data["format"]["duration"])
    except Exception:
        size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
        return max(1.0, size / 16_000)

def audio_duration_sec_bytes(data: bytes) -> float:
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

# ═════════════════════════════════════════════════════════════════════════════
# PPTX → GÖRÜNTÜLER
# ═════════════════════════════════════════════════════════════════════════════
def pptx_to_images(pptx_bytes: bytes) -> list:
    tmp = tempfile.mkdtemp(prefix="pptx2img_")
    try:
        pptx_path = os.path.join(tmp, "presentation.pptx")
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)
        try:
            _run(
                [LO_BIN, "--headless", "--convert-to", "pdf",
                 "--outdir", tmp, pptx_path],
                timeout=180, step_name="LibreOffice PDF dönüşümü",
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"LibreOffice PDF dönüşümü başarısız.\n"
                f"packages.txt içinde 'libreoffice' satırı var mı?\n\n{e}"
            )
        pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
        if not pdfs:
            raise RuntimeError("LibreOffice çalıştı ama PDF üretmedi.")
        pdf_path = os.path.join(tmp, pdfs[0])
        img_prefix = os.path.join(tmp, "slide")
        try:
            _run(
                ["pdftoppm", "-jpeg", "-r", "192", pdf_path, img_prefix],
                timeout=120, step_name="pdftoppm görüntü üretimi",
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"pdftoppm başarısız.\npackages.txt içinde 'poppler-utils' var mı?\n\n{e}"
            )
        files = sorted([
            os.path.join(tmp, f)
            for f in os.listdir(tmp)
            if f.startswith("slide") and (f.endswith(".jpg") or f.endswith(".jpeg"))
        ])
        if not files:
            raise RuntimeError("pdftoppm çalıştı ama görüntü üretmedi.")
        images = []
        for p in files:
            src = Image.open(p).convert("RGB")
            sw, sh = src.size
            scale = min(VIDEO_W / sw, VIDEO_H / sh)
            nw, nh = int(sw * scale), int(sh * scale)
            canvas = Image.new("RGB", (VIDEO_W, VIDEO_H), (6, 6, 18))
            canvas.paste(src.resize((nw, nh), Image.LANCZOS),
                         ((VIDEO_W - nw) // 2, (VIDEO_H - nh) // 2))
            images.append(canvas)
        return images
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def read_pptx_notes(pptx_bytes: bytes) -> list:
    prs = Presentation(io.BytesIO(pptx_bytes))
    notes = []
    for slide in prs.slides:
        txt = ""
        try:
            txt = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            pass
        notes.append(txt)
    return notes

import re as _re

def _find_silence_splits(audio_path: str, n_slides: int, total_dur: float) -> list:
    """Sessizlik noktalarında slayt sınırlarını bul."""
    per_slide = total_dur / max(n_slides, 1)
    split_times = []
    try:
        r = subprocess.run(
            [FFMPEG, "-y", "-i", audio_path,
             "-af", "silencedetect=noise=-35dB:duration=0.25",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=60,
        )
        starts = [float(m) for m in _re.findall(r"silence_start: ([\d.]+)", r.stderr)]
        ends   = [float(m) for m in _re.findall(r"silence_end: ([\d.]+)",   r.stderr)]
        mids   = [(s + e) / 2 for s, e in zip(starts, ends)]
    except Exception:
        mids = []
    for i in range(1, n_slides):
        target = i * per_slide
        tol    = per_slide * 0.15
        cands  = [m for m in mids if abs(m - target) <= tol]
        split_times.append(min(cands, key=lambda x: abs(x - target)) if cands else target)
    return split_times

# ═════════════════════════════════════════════════════════════════════════════
# SES HAZIRLAMA
# ═════════════════════════════════════════════════════════════════════════════
def prepare_audio_segments(
    slide_audio_map: dict,
    durations: dict,
    n_slides: int,
    global_audio: bytes | None,
    use_global: bool,
    work_dir: str,
) -> tuple[list, list]:
    audio_paths = []
    dur_list    = []
    if use_global and global_audio:
        global_path = os.path.join(work_dir, "global_audio.audio")
        with open(global_path, "wb") as f:
            f.write(global_audio)
        total_dur   = audio_duration_ffprobe(global_path)
        splits      = _find_silence_splits(global_path, n_slides, total_dur)
        boundaries  = [0.0] + splits + [total_dur]
        for i in range(n_slides):
            ss      = boundaries[i]
            seg_dur = boundaries[i + 1] - boundaries[i]
            seg_path = os.path.join(work_dir, f"seg_{i:04d}.aac")
            try:
                _run(
                    [FFMPEG, "-y",
                     "-ss", f"{ss:.6f}", "-t", f"{seg_dur:.6f}",
                     "-i", global_path,
                     "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                     "-af", "aresample=async=1:min_hard_comp=0.1:first_pts=0",
                     seg_path],
                    timeout=60, step_name=f"Global ses segment {i+1}",
                )
                audio_paths.append(seg_path)
                dur_list.append(audio_duration_ffprobe(seg_path))
            except Exception:
                audio_paths.append(None)
                dur_list.append(seg_dur)
    else:
        for i in range(n_slides):
            aud_bytes = slide_audio_map.get(i)
            if aud_bytes:
                raw_path = os.path.join(work_dir, f"raw_{i:04d}.audio")
                with open(raw_path, "wb") as f:
                    f.write(aud_bytes)
                aac_path = os.path.join(work_dir, f"seg_{i:04d}.aac")
                try:
                    _run(
                        [FFMPEG, "-y", "-i", raw_path,
                         "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                         "-af", "aresample=async=1:min_hard_comp=0.1:first_pts=0",
                         aac_path],
                        timeout=60, step_name=f"Ses normalize {i+1}",
                    )
                    audio_paths.append(aac_path)
                    dur_list.append(audio_duration_ffprobe(aac_path))
                except Exception:
                    audio_paths.append(None)
                    dur_list.append(durations.get(i, 3.0))
            else:
                audio_paths.append(None)
                dur_list.append(durations.get(i, 3.0))
    return audio_paths, dur_list

# ═════════════════════════════════════════════════════════════════════════════
# KARE RENDER — 3 Soru 3 Dakika + Eczacı Elif Aracıoğlu markası
# ═════════════════════════════════════════════════════════════════════════════
def render_frame(slide_img, slide_idx, total, t, speaker: dict, has_audio: bool):
    frame = slide_img.copy()
    draw  = ImageDraw.Draw(frame)
    w, h  = frame.size
    color = speaker.get("rgb", (201, 168, 76))
    name  = speaker.get("name", "Elif Aracıoğlu")
    role  = speaker.get("role", "Eczacı")
    emoji = speaker.get("emoji", "🎤")

    fn18 = _font(18); fn15 = _font(15); fn13 = _font(13); fn11 = _font(11)

    # ── Üst şerit ─────────────────────────────────────────────────────────────
    bar_h = 56
    draw.rectangle([0, 0, w, bar_h], fill=(4, 4, 12, 220))
    draw.rectangle([0, bar_h - 3, w, bar_h], fill=color)

    # Sol: program adı (büyük)
    draw.text((18, 8),  "3 SORU", font=fn18, fill=(*color, 240))
    draw.text((18, 30), "3 DAKİKA", font=fn11, fill=(*color, 160))

    # Dikey ayraç
    draw.rectangle([115, 10, 117, 44], fill=(*color, 60))

    # Sol-orta: konuşmacı
    spk_label = f"{emoji}  {name}  ·  {role}"
    draw.text((128, 20), spk_label, font=fn13, fill=(210, 210, 230, 215))

    # Orta: YAYIN kırmızı nokta (animasyonlu)
    da = int(180 + 75 * math.sin(t * math.pi * 4))
    cx = w // 2
    draw.ellipse([cx - 8, 21, cx + 4, 33], fill=(220, 50, 50, da))
    draw.text((cx + 8, 19), "YAYIN", font=fn11, fill=(220, 50, 50, 210))

    # Sağ: "Eczacı Elif Aracıoğlu" marka yazısı
    draw.text((w - 285, 10),  "Eczacı",        font=fn11, fill=(*color, 140))
    draw.text((w - 285, 26),  "Elif Aracıoğlu", font=fn15, fill=(*color, 220))

    # ── Alt şerit ─────────────────────────────────────────────────────────────
    bot_y = h - 52
    draw.rectangle([0, bot_y, w, h], fill=(4, 4, 12, 225))
    draw.rectangle([0, bot_y, w, bot_y + 3], fill=color)

    # Sol: slayt numarası
    draw.text((18, bot_y + 15), f"Slayt {slide_idx + 1}  /  {total}",
              font=fn13, fill=(160, 160, 190, 210))

    # Orta-sol: "3 Soru 3 Dakika" alt slogan
    draw.text((w // 2 - 80, bot_y + 15), "3 Soru · 3 Dakika",
              font=fn11, fill=(*color, 100))

    # İlerleme çubuğu (en alt 6px)
    prog_w = int(w * (slide_idx + t) / max(total, 1))
    draw.rectangle([0, h - 6, w, h], fill=(10, 10, 22))
    draw.rectangle([0, h - 6, prog_w, h], fill=color)

    # Ses dalgası animasyonu (sağ alt)
    if has_audio:
        bc, bw, bg = 9, 5, 4
        bx0 = w - bc * (bw + bg) - 18
        by  = h - 10
        for bi in range(bc):
            bh = int(4 + 16 * abs(math.sin(t * math.pi * 4.0 + bi * 0.9)))
            bx = bx0 + bi * (bw + bg)
            draw.rounded_rectangle([bx, by - bh, bx + bw, by], radius=2, fill=color)

    return np.array(frame)

# ═════════════════════════════════════════════════════════════════════════════
# BİREBİR SENKRON VİDEO — Slayt başına segment encode → concat
# ─────────────────────────────────────────────────────────────────────────────
# Her slayt için ffmpeg'e hem video pipe hem ses dosyası aynı anda verilir.
# -t ses_süresi ile ikisi de aynı noktada kesilir → timestamp kayması = 0.
# Final adımda segment'ler concat demuxer + stream copy ile birleştirilir.
# ═════════════════════════════════════════════════════════════════════════════
def _make_silence_aac(work_dir: str, idx: int, dur: float) -> str:
    path = os.path.join(work_dir, f"sil_{idx:04d}.aac")
    _run(
        [FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{dur:.6f}", "-c:a", "aac", "-b:a", "128k", path],
        timeout=30, step_name=f"Sessizlik {idx}",
    )
    return path

def _encode_slide_segment(
    img, slide_idx: int, total: int,
    audio_path, dur: float,
    speaker: dict, work_dir: str, seg_idx: int,
) -> str:
    has_audio = audio_path is not None and os.path.exists(audio_path)
    if not has_audio:
        try:
            audio_path = _make_silence_aac(work_dir, seg_idx, dur)
            has_audio  = True
        except Exception:
            pass

    actual_dur = audio_duration_ffprobe(audio_path) if has_audio else dur
    nf         = max(1, round(actual_dur * VIDEO_FPS))
    seg_path   = os.path.join(work_dir, f"chunk_{seg_idx:04d}.mp4")

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
                render_frame(img, slide_idx, total, t, speaker, has_audio)
                .astype(np.uint8).tobytes()
            )
        proc.stdin.close()
        proc.wait(timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"Segment encode başarısız (kod {proc.returncode})")
    except Exception as e:
        proc.kill()
        raise RuntimeError(f"[Segment {seg_idx}] {e}")
    return seg_path

def build_video(
    slide_images: list,
    audio_paths: list,
    durations: list,
    speakers: list,
    work_dir: str,
    cb=None,
) -> bytes:
    if not FFMPEG or not os.path.exists(FFMPEG):
        raise RuntimeError(
            "ffmpeg bulunamadı!\n\n"
            "Çözüm 1 — requirements.txt:\n  imageio[ffmpeg]\n\n"
            "Çözüm 2 — packages.txt:\n  ffmpeg\n\n"
            f"Aranan yol: {FFMPEG!r}"
        )

    n       = len(slide_images)
    tmp_out = os.path.join(work_dir, "output.mp4")
    segs    = []

    for idx, (img, aud_path, dur, spk) in enumerate(
            zip(slide_images, audio_paths, durations, speakers)):
        if cb:
            pct = 0.05 + 0.82 * (idx / n)
            cb(pct, f"Slayt {idx+1}/{n} encode ediliyor… (ses+video birlikte)")
        segs.append(_encode_slide_segment(
            img, idx, n, aud_path, dur, spk, work_dir, idx))

    if cb: cb(0.90, f"{n} segment birleştiriliyor (stream copy)…")
    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for p in segs:
            f.write(f"file '{p}'\n")
    _run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", "-vsync", "vfr", "-movflags", "+faststart", tmp_out],
        timeout=600, step_name="Final concat (stream copy)",
    )

    if cb: cb(1.0, "Tamamlandı! ✅")
    if os.path.exists(tmp_out):
        with open(tmp_out, "rb") as f:
            return f.read()
    raise RuntimeError("Çıktı MP4 oluşturulamadı.")

# ═════════════════════════════════════════════════════════════════════════════
# CSS
# ═════════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;1,400&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600;9..40,700&display=swap');
:root{
  --gold:#C9A84C;--gold-dim:rgba(201,168,76,.16);--gold-glow:rgba(201,168,76,.06);
  --teal:#2ec4a0;--teal-dim:rgba(46,196,160,.15);
  --bg:#07080d;--surface:rgba(255,255,255,.025);--border:rgba(255,255,255,.07);
  --text:#e2e4ee;--muted:#4a5068;
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;background:var(--bg);}

/* ── App bg ── */
.stApp{
  background:
    radial-gradient(ellipse 90% 45% at 0% 0%,rgba(201,168,76,.05) 0%,transparent 55%),
    radial-gradient(ellipse 60% 50% at 100% 100%,rgba(46,196,160,.04) 0%,transparent 55%),
    var(--bg);
  color:var(--text);
}

/* ── Sidebar ── */
section[data-testid="stSidebar"]{
  background:rgba(5,5,11,.98);
  border-right:1px solid var(--gold-dim);
}

/* ── Hero ── */
.hero{
  position:relative;overflow:hidden;
  padding:2.6rem 1rem 1.6rem;
  border-bottom:1px solid var(--gold-dim);
  margin-bottom:1.6rem;
  text-align:center;
}
.hero::before{
  content:'';position:absolute;inset:0;
  background:
    radial-gradient(ellipse 70% 90% at 50% -10%,rgba(201,168,76,.07),transparent 60%);
  pointer-events:none;
}
.hero-eyebrow{
  display:inline-block;
  font-size:.62rem;letter-spacing:.28em;text-transform:uppercase;
  color:var(--teal);border:1px solid var(--teal-dim);
  padding:.22rem .8rem;border-radius:50px;margin-bottom:1rem;
  background:rgba(46,196,160,.06);
}
.hero h1{
  font-family:'Playfair Display',serif;
  font-size:3rem;font-weight:700;line-height:1.1;
  color:#f0e8cc;margin:0 0 .4rem;letter-spacing:-.02em;
}
.hero h1 span{
  font-style:italic;font-weight:400;color:var(--gold);
}
.hero-name{
  font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;
  color:var(--muted);margin-top:.6rem;
}
.hero-name strong{color:var(--gold);font-weight:600;letter-spacing:.18em;}
.hero-divider{
  width:56px;height:1px;background:linear-gradient(90deg,transparent,var(--gold),transparent);
  margin:1rem auto 0;
}

/* ── Adım etiketi ── */
.lbl{
  font-size:.58rem;letter-spacing:.24em;text-transform:uppercase;color:var(--muted);
  margin:.9rem 0 .45rem;padding-left:.55rem;
  border-left:2px solid var(--gold);
}

/* ── Info satırı ── */
.srow{
  display:flex;gap:.9rem;flex-wrap:wrap;padding:.55rem 1rem;margin:.5rem 0;
  background:var(--gold-glow);border:1px solid var(--gold-dim);border-radius:10px;
  font-size:.78rem;color:var(--muted);align-items:center;
}
.srow strong{color:var(--gold);}

/* ── Karakter kartı ── */
.char-card{
  display:flex;align-items:center;gap:.8rem;padding:.65rem 1rem;margin:.32rem 0;
  background:var(--surface);border:1px solid var(--border);border-radius:11px;
  transition:border-color .2s,background .2s;
}
.char-card:hover{border-color:var(--gold-dim);background:rgba(255,255,255,.04);}
.char-dot{width:11px;height:11px;border-radius:50%;flex-shrink:0;box-shadow:0 0 7px currentColor;}
.char-name{font-size:.88rem;font-weight:600;color:#dde;}
.char-role{font-size:.7rem;color:#4a5068;margin-left:auto;}

/* ── Slayt kartı ── */
.sl-card{
  padding:.6rem .9rem;margin:.26rem 0;
  background:var(--surface);border:1px solid var(--border);border-radius:9px;
  border-left:3px solid;
}
.sl-num{font-size:.63rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.18rem;}
.sl-note{font-size:.78rem;color:#7a8090;line-height:1.5;font-style:italic;}

/* ── Badge ── */
.badge{display:inline-flex;align-items:center;gap:.28rem;
  padding:.18rem .55rem;border-radius:50px;font-size:.65rem;font-weight:700;}
.badge-gold{background:rgba(201,168,76,.1);color:var(--gold);border:1px solid rgba(201,168,76,.2);}
.badge-teal{background:rgba(46,196,160,.1);color:var(--teal);border:1px solid rgba(46,196,160,.2);}

/* ── Sistem durum ── */
.dep{font-size:.72rem;margin:.1rem 0;line-height:1.55;}
.ok{color:#5dd68a;}.er{color:#e07b7b;}

/* ── ffmpeg uyarı ── */
.ffmpeg-warn{
  padding:.8rem 1rem;margin:.6rem 0;border-radius:10px;
  background:rgba(224,123,123,.07);border:1px solid rgba(224,123,123,.22);
  font-size:.78rem;color:#e07b7b;line-height:1.6;
}
.ffmpeg-warn code{
  background:rgba(255,255,255,.07);padding:.1rem .32rem;
  border-radius:4px;font-size:.73rem;
}

/* ── İndirme ── */
.dl-alt{
  display:block;text-align:center;padding:9px 14px;margin-top:8px;
  background:rgba(201,168,76,.07);border:1px solid rgba(201,168,76,.2);
  color:var(--gold);border-radius:9px;font-weight:600;font-size:.8rem;
  text-decoration:none;transition:background .18s;
}
.dl-alt:hover{background:rgba(201,168,76,.14);}

/* ── Butonlar ── */
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#b8923e,#e0b95a)!important;
  color:#06050a!important;font-weight:700!important;border:none!important;
  letter-spacing:.03em;
}
.stButton>button[kind="primary"]:hover{
  filter:brightness(1.08);transform:translateY(-1px);
  box-shadow:0 4px 22px rgba(201,168,76,.28)!important;
}
.stProgress>div>div{border-radius:10px;}

/* ── Sidebar marka ── */
.sb-brand{
  text-align:center;padding:1.1rem 0 .8rem;
  border-bottom:1px solid var(--gold-dim);margin-bottom:1rem;
}
.sb-title{
  font-family:'Playfair Display',serif;
  font-size:1.15rem;font-weight:700;color:#f0e8cc;letter-spacing:-.01em;
}
.sb-title span{font-style:italic;font-weight:400;color:var(--gold);}
.sb-name{font-size:.62rem;color:var(--muted);letter-spacing:.18em;
  text-transform:uppercase;margin-top:.35rem;}

audio{width:100%;border-radius:8px;margin:3px 0;}
hr{border-color:var(--border);}
input[type="text"]{
  background:rgba(255,255,255,.04)!important;
  border:1px solid rgba(255,255,255,.09)!important;
  color:#e2e4ee!important;border-radius:8px!important;
}
</style>
"""

# ═════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═════════════════════════════════════════════════════════════════════════════
def init_state():
    defaults = {
        "ss_pptx_bytes":    None,
        "ss_slide_notes":   [],
        "ss_slide_images":  [],
        "ss_slide_audio":   {},
        "ss_slide_speaker": {},
        "ss_global_audio":  None,
        "ss_durations":     {},
        "ss_use_global":    True,
        "ss_video_bytes":   None,
        "ss_characters":    [c.copy() for c in DEFAULT_CHARACTERS],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ═════════════════════════════════════════════════════════════════════════════
# KARAKTERLERİ YÖNETME
# ═════════════════════════════════════════════════════════════════════════════
def character_manager_ui():
    chars = st.session_state.ss_characters
    st.markdown('<p class="lbl">🎭 Konuşmacılar</p>', unsafe_allow_html=True)
    st.caption(
        "Elif Aracıoğlu varsayılan konuşmacıdır. İstediğiniz kadar ekleyip çıkarabilirsiniz. "
        "Her konuşmacıya ayrı ses dosyası atayabilir veya tek sesi tüm sunuma uygulayabilirsiniz."
    )
    to_delete = None
    for i, ch in enumerate(chars):
        is_default = (i == 0)
        with st.container():
            c1, c2, c3, c4 = st.columns([2.5, 2, 1.2, 0.7])
            with c1:
                new_name = st.text_input(
                    "İsim", value=ch["name"],
                    key=f"ch_name_{i}",
                    label_visibility="collapsed",
                    disabled=is_default,
                    placeholder="İsim..."
                )
                if not is_default:
                    chars[i]["name"] = new_name or ch["name"]
            with c2:
                new_role = st.text_input(
                    "Rol", value=ch["role"],
                    key=f"ch_role_{i}",
                    label_visibility="collapsed",
                    placeholder="Rol..."
                )
                chars[i]["role"] = new_role or ch["role"]
            with c3:
                emoji_options = ["🎤","👩‍💼","🎧","🎙️","💬","📢","🗣️","👤","🎵","📡"]
                cur_emoji = ch.get("emoji","🎤")
                cur_idx   = emoji_options.index(cur_emoji) if cur_emoji in emoji_options else 0
                sel_emoji = st.selectbox(
                    "Emoji", emoji_options, index=cur_idx,
                    key=f"ch_emoji_{i}", label_visibility="collapsed",
                )
                chars[i]["emoji"] = sel_emoji
            with c4:
                if is_default:
                    st.markdown(
                        '<span class="badge badge-gold">Varsayılan</span>',
                        unsafe_allow_html=True
                    )
                else:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✕", key=f"ch_del_{i}", help=f"{ch['name']} sil",
                                 use_container_width=True):
                        to_delete = i
            st.markdown(
                f'<div class="char-card" style="margin-top:-6px;padding:.4rem .9rem;">'
                f'<div class="char-dot" style="background:#{ch["hex"]};color:#{ch["hex"]};"></div>'
                f'<span class="char-name">{ch["emoji"]}  {chars[i]["name"]}</span>'
                f'<span class="char-role">{chars[i]["role"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
    if to_delete is not None:
        chars.pop(to_delete)
        new_speaker_map = {}
        for k, v in st.session_state.ss_slide_speaker.items():
            new_v = v if v < to_delete else max(0, v - 1)
            new_speaker_map[k] = new_v
        st.session_state.ss_slide_speaker = new_speaker_map
        st.rerun()
    st.markdown("---")
    with st.expander("➕ Yeni Konuşmacı Ekle", expanded=False):
        col_n, col_r, col_add = st.columns([2, 2, 1])
        with col_n:
            new_name = st.text_input("İsim", key="wu_new_name", placeholder="Örn: Ecem")
        with col_r:
            new_role = st.text_input("Rol",  key="wu_new_role", placeholder="Örn: Konuk")
        with col_add:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Ekle ➕", use_container_width=True, key="wu_add_char"):
                if new_name.strip():
                    palette_idx = len(chars) % len(PALETTE)
                    chars.append({
                        **PALETTE[palette_idx],
                        "name": new_name.strip(),
                        "role": new_role.strip() or "Konuşmacı",
                    })
                    st.rerun()
                else:
                    st.warning("İsim boş olamaz.")
    st.session_state.ss_characters = chars
    return chars

# ═════════════════════════════════════════════════════════════════════════════
# SES ATAMA BÖLÜMÜ
# ═════════════════════════════════════════════════════════════════════════════
def audio_assignment_ui(n_slides: int, chars: list):
    mode = st.radio(
        "Ses Modu",
        ["🔊 Tek ses — tüm sunuma", "🎙️ Her slayta ayrı ses"],
        key="wu_mode_radio", horizontal=True, label_visibility="collapsed",
    )
    use_global = mode.startswith("🔊")
    st.session_state.ss_use_global = use_global

    if use_global:
        st.caption(
            "**Tek ses modu:** Yüklediğiniz ses, sessizlik noktalarında slaytlara akıllıca bölünür. "
            "Konuşmacı olarak Elif Aracıoğlu veya seçtiğiniz kişi tüm slaytlarda görünür."
        )
        col_g1, col_g2 = st.columns([2, 1])
        with col_g1:
            gf = st.file_uploader(
                "Genel ses", type=["mp3","wav","m4a","ogg"],
                key="wu_glob_upload", label_visibility="collapsed",
            )
            if gf is not None:
                ab = gf.read()
                st.session_state.ss_global_audio = ab
                total_dur = audio_duration_sec_bytes(ab)
                per_slide = total_dur / max(n_slides, 1)
                for i in range(n_slides):
                    st.session_state.ss_durations[i] = per_slide
                st.audio(ab, format="audio/mp3")
                st.caption(
                    f"Toplam ~{total_dur:.1f} sn  ·  "
                    f"Slayt başına ~{per_slide:.1f} sn  ·  "
                    f"ffmpeg zamansal kesim"
                )
        with col_g2:
            st.markdown('<p class="lbl">Tüm Slaytlar İçin Konuşmacı</p>', unsafe_allow_html=True)
            char_names = [f'{c["emoji"]} {c["name"]}' for c in chars]
            sel_global_speaker = st.selectbox(
                "Konuşmacı", char_names, index=0,
                key="wu_global_speaker", label_visibility="collapsed",
            )
            sel_idx = char_names.index(sel_global_speaker)
            for i in range(n_slides):
                st.session_state.ss_slide_speaker[i] = sel_idx
    else:
        st.caption(
            "**Slayt bazlı mod:** Her slayta farklı konuşmacı ve ses dosyası atayabilirsiniz. "
            "Ses yüklenmeyen slaytlara otomatik sessizlik eklenir."
        )
        char_names = [f'{c["emoji"]} {c["name"]}' for c in chars]
        notes = st.session_state.ss_slide_notes
        col_qa1, col_qa2 = st.columns([3, 1])
        with col_qa1:
            quick_speaker = st.selectbox(
                "Tüm slaytlara ata:",
                char_names, index=0, key="wu_quick_speaker",
            )
        with col_qa2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Tümüne Uygula", key="wu_quick_apply", use_container_width=True):
                q_idx = char_names.index(quick_speaker)
                for i in range(n_slides):
                    st.session_state.ss_slide_speaker[i] = q_idx
                st.rerun()
        st.markdown("---")
        for i in range(n_slides):
            note_preview = (notes[i][:80]+"…") if i < len(notes) and len(notes[i])>80 else (notes[i] if i < len(notes) else "")
            cur_spk_idx = st.session_state.ss_slide_speaker.get(i, 0)
            cur_spk_idx = min(cur_spk_idx, len(chars)-1)
            spk_color = f'#{chars[cur_spk_idx]["hex"]}'
            st.markdown(
                f'<div class="sl-card" style="border-left-color:{spk_color};">'
                f'<div class="sl-num" style="color:{spk_color};">'
                f'Slayt {i+1}  ·  {chars[cur_spk_idx]["emoji"]} {chars[cur_spk_idx]["name"]}'
                f'</div>'
                f'<div class="sl-note">{note_preview or "—"}</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            sl_col1, sl_col2, sl_col3 = st.columns([1.5, 2.5, 0.5])
            with sl_col1:
                sel = st.selectbox(
                    f"Konuşmacı S{i+1}", char_names,
                    index=cur_spk_idx, key=f"wu_spk_{i}",
                    label_visibility="collapsed",
                )
                new_idx = char_names.index(sel)
                st.session_state.ss_slide_speaker[i] = new_idx
            with sl_col2:
                uf = st.file_uploader(
                    f"Ses S{i+1}", type=["mp3","wav","m4a","ogg"],
                    key=f"wu_sl_{i}", label_visibility="collapsed",
                )
                if uf is not None:
                    ab = uf.read()
                    st.session_state.ss_slide_audio[i] = ab
                    dur = audio_duration_sec_bytes(ab)
                    st.session_state.ss_durations[i]   = dur
                    st.audio(ab, format="audio/mp3")
            with sl_col3:
                dur_val = st.session_state.ss_durations.get(i, 3.0)
                if i in st.session_state.ss_slide_audio:
                    st.caption(f"⏱️ {dur_val:.1f}s")
                else:
                    st.caption(f"🔇 {dur_val:.0f}s")

    with st.expander("⚙️ Slayt sürelerini manuel ayarla (opsiyonel)", expanded=False):
        per_row = min(n_slides, 5)
        n_rows  = math.ceil(n_slides / per_row)
        dur_grids = [st.columns(per_row) for _ in range(n_rows)]
        for i in range(n_slides):
            row, col = i // per_row, i % per_row
            with dur_grids[row][col]:
                default = float(st.session_state.ss_durations.get(i, 3.0))
                d = st.number_input(
                    f"S{i+1} (sn)", min_value=0.5, max_value=300.0,
                    value=default, step=0.5, key=f"wu_dur_{i}",
                )
                st.session_state.ss_durations[i] = d
    return use_global

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="sb-brand">'
            '<div class="sb-title">3 <span>Soru</span> 3 <span>Dakika</span></div>'
            '<div class="sb-name">Eczacı <strong style="color:#C9A84C;">Elif Aracıoğlu</strong></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        character_manager_ui()
        st.markdown("---")
        st.markdown('<p class="lbl">Sistem Durumu</p>', unsafe_allow_html=True)

        # ffmpeg durum mesajı
        ffmpeg_label = "ffmpeg"
        ffmpeg_hint  = "requirements.txt: imageio[ffmpeg]  VEYA  packages.txt: ffmpeg"
        if FFMPEG_OK:
            ffmpeg_short = FFMPEG.split("/")[-1] if FFMPEG else "ffmpeg"
            ffmpeg_label = f"ffmpeg <span style='color:#2a3040;font-size:.6rem;'>({FFMPEG})</span>"

        checks = [
            ("Pillow",       PIL_OK,      "pip: pillow"),
            ("imageio",      IMAGEIO_OK,  "pip: imageio[ffmpeg]"),
            ("python-pptx",  PPTX_OK,     "pip: python-pptx"),
            ("LibreOffice",  LO_OK,       "packages.txt: libreoffice"),
            ("pdftoppm",     PPM_OK,      "packages.txt: poppler-utils"),
            ("ffmpeg",       FFMPEG_OK,   ffmpeg_hint),
        ]
        for name, ok, hint in checks:
            cls = "ok" if ok else "er"
            icon = "🟢" if ok else "🔴"
            extra = f' <span style="color:#2a3040;font-size:.63rem;">— {hint}</span>' if not ok else ""
            display_name = ffmpeg_label if name == "ffmpeg" else name
            st.markdown(
                f'<div class="dep {cls}">{icon} {display_name}{extra}</div>',
                unsafe_allow_html=True,
            )

        # ffmpeg bulunamadıysa detaylı kılavuz
        if not FFMPEG_OK:
            st.markdown(
                '<div class="ffmpeg-warn">'
                '⚠️ <b>ffmpeg bulunamadı!</b><br>'
                'requirements.txt dosyasına ekleyin:<br>'
                '<code>imageio[ffmpeg]</code><br><br>'
                'VEYA packages.txt dosyasına:<br>'
                '<code>ffmpeg</code>'
                '</div>',
                unsafe_allow_html=True,
            )

        if not LO_OK or not PPM_OK:
            st.markdown("---")
            st.caption("**packages.txt** dosyasına ekleyin:\n```\nlibreoffice\npoppler-utils\n```")

        st.markdown("---")
        chars = st.session_state.ss_characters
        st.markdown('<p class="lbl">Aktif Konuşmacılar</p>', unsafe_allow_html=True)
        for ch in chars:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:.5rem;'
                f'padding:.2rem 0;font-size:.78rem;">'
                f'<div style="width:9px;height:9px;border-radius:50%;'
                f'background:#{ch["hex"]};"></div>'
                f'<span style="color:#ccd;">{ch["emoji"]} {ch["name"]}</span>'
                f'<span style="color:#445;margin-left:auto;font-size:.65rem;">{ch["role"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        st.markdown("---")
        st.markdown(
            '<div style="font-size:.6rem;color:#2a3040;text-align:center;">'
            'v11.0 · 3 Soru 3 Dakika · Birebir Senkron</div>',
            unsafe_allow_html=True,
        )

# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="3 Soru 3 Dakika · Elif Aracıoğlu",
        page_icon="💊", layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    render_sidebar()
    st.markdown(
        '<div class="hero">'
        '<div class="hero-eyebrow">💊 Video Stüdyo</div>'
        '<h1>3 <span>Soru</span><br>3 Dakika</h1>'
        '<div class="hero-name">Eczacı &nbsp;<strong>Elif Aracıoğlu</strong></div>'
        '<div class="hero-divider"></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    chars = st.session_state.ss_characters

    # ══════════════════════════════════════════════════════════
    # ADIM 1 — PPTX
    # ══════════════════════════════════════════════════════════
    st.markdown('<p class="lbl">① PowerPoint Dosyası</p>', unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        pptx_file = st.file_uploader(
            "PPTX", type=["pptx"], key="wu_pptx",
            label_visibility="collapsed",
        )
        if pptx_file is not None:
            raw = pptx_file.read()
            if raw != st.session_state.ss_pptx_bytes:
                st.session_state.ss_pptx_bytes   = raw
                st.session_state.ss_slide_images  = []
                st.session_state.ss_video_bytes   = None
                st.session_state.ss_slide_audio   = {}
                st.session_state.ss_slide_speaker = {}
                st.session_state.ss_durations     = {}
                with st.spinner("PPTX okunuyor..."):
                    try:
                        st.session_state.ss_slide_notes = read_pptx_notes(raw)
                    except Exception as e:
                        st.error(f"PPTX okunamadı: {e}")
                        st.session_state.ss_slide_notes = []
        if st.session_state.ss_pptx_bytes:
            n = len(st.session_state.ss_slide_notes)
            st.success(f"✅ Yüklendi — **{n}** slayt")
            char_names = [f'{c["emoji"]} {c["name"]}' for c in chars]
            spk_counts = {}
            for i in range(n):
                idx = st.session_state.ss_slide_speaker.get(i, 0)
                idx = min(idx, len(chars)-1)
                name = chars[idx]["name"]
                spk_counts[name] = spk_counts.get(name, 0) + 1
            badges = " ".join(
                f'<span class="badge badge-gold">{name}: {cnt}</span>'
                for name, cnt in spk_counts.items()
            )
            st.markdown(badges, unsafe_allow_html=True)
    with col_b:
        notes = st.session_state.ss_slide_notes
        if notes:
            st.markdown(
                f'<div class="srow"><span>📊 <strong>{len(notes)}</strong> slayt</span>'
                f'<span>🎭 <strong>{len(chars)}</strong> konuşmacı</span></div>',
                unsafe_allow_html=True,
            )
            for i, note in enumerate(notes[:6]):
                spk_idx = min(
                    st.session_state.ss_slide_speaker.get(i, 0), len(chars)-1)
                spk = chars[spk_idx]
                preview = (note[:88]+"…") if len(note)>88 else (note or "—")
                st.markdown(
                    f'<div class="sl-card" style="border-left-color:#{spk["hex"]};">'
                    f'<div class="sl-num" style="color:#{spk["hex"]};">'
                    f'{spk["emoji"]} {spk["name"]}  ·  Slayt {i+1}</div>'
                    f'<div class="sl-note">{preview}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if len(notes) > 6:
                st.caption(f"… ve {len(notes)-6} slayt daha")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════
    # ADIM 2 — SES & KONUŞMACI ATAMA
    # ══════════════════════════════════════════════════════════
    st.markdown('<p class="lbl">② Ses Dosyaları & Konuşmacı Atama</p>', unsafe_allow_html=True)
    if not st.session_state.ss_slide_notes:
        st.info("Önce bir PPTX dosyası yükleyin.")
    else:
        n_slides = len(st.session_state.ss_slide_notes)
        audio_assignment_ui(n_slides, chars)

    st.markdown("---")

    # ══════════════════════════════════════════════════════════
    # ADIM 3 — VİDEO OLUŞTUR
    # ══════════════════════════════════════════════════════════
    st.markdown('<p class="lbl">③ Video Oluştur</p>', unsafe_allow_html=True)

    can_go = (
        st.session_state.ss_pptx_bytes is not None
        and PIL_OK and IMAGEIO_OK and PPTX_OK and LO_OK and PPM_OK and FFMPEG_OK
    )
    if not can_go:
        if not st.session_state.ss_pptx_bytes:
            st.info("Önce PPTX dosyası yükleyin.")
        else:
            missing = []
            if not PIL_OK:      missing.append("Pillow")
            if not IMAGEIO_OK:  missing.append("imageio")
            if not PPTX_OK:     missing.append("python-pptx")
            if not LO_OK:       missing.append("libreoffice")
            if not PPM_OK:      missing.append("poppler-utils")
            if not FFMPEG_OK:   missing.append("ffmpeg")
            st.error(f"Eksik bağımlılık: {', '.join(missing)}")
            if not FFMPEG_OK:
                st.markdown(
                    '<div class="ffmpeg-warn">'
                    '🔧 <b>ffmpeg kurulumu için:</b><br><br>'
                    '<b>requirements.txt</b> dosyasına ekleyin:<br>'
                    '<code>imageio[ffmpeg]</code><br><br>'
                    '<b>VEYA packages.txt</b> dosyasına ekleyin:<br>'
                    '<code>ffmpeg</code>'
                    '</div>',
                    unsafe_allow_html=True,
                )
    else:
        n_slides    = len(st.session_state.ss_slide_notes)
        total_secs  = sum(st.session_state.ss_durations.get(i, 3.0) for i in range(n_slides))
        mins, secs  = divmod(int(total_secs), 60)
        st.markdown(
            f'<div class="srow">'
            f'<span>🎞️ <strong>{n_slides}</strong> slayt</span>'
            f'<span>⏱️ ~<strong>{mins}:{secs:02d}</strong></span>'
            f'<span>📐 <strong>{VIDEO_W}×{VIDEO_H}</strong></span>'
            f'<span>🎬 <strong>{VIDEO_FPS} FPS</strong></span>'
            f'<span>🎭 <strong>{len(chars)}</strong> konuşmacı</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        c1, c2 = st.columns([3, 1])
        with c1:
            make_btn = st.button(
                "🎬 Video Oluştur", type="primary",
                use_container_width=True, key="wu_btn_make",
                disabled=(st.session_state.ss_video_bytes is not None),
            )
        with c2:
            if st.button("🔄 Sıfırla", use_container_width=True, key="wu_btn_reset"):
                st.session_state.ss_video_bytes = None
                st.rerun()

        if make_btn:
            prog = st.progress(0); stat = st.empty(); t0 = time.time()
            def cb(pct, msg):
                elapsed = time.time() - t0
                prog.progress(min(float(pct), 1.0))
                stat.markdown(
                    f"⚙️ **{msg}** &nbsp;"
                    f'<span style="color:#3a4560;font-size:.76rem;">— {elapsed:.0f}s</span>',
                    unsafe_allow_html=True,
                )
            work_dir = tempfile.mkdtemp(prefix="vidstudio_")
            try:
                cb(0.02, "Slaytlar görüntüye dönüştürülüyor (LibreOffice + pdftoppm)…")
                slide_imgs = pptx_to_images(st.session_state.ss_pptx_bytes)
                n_actual   = len(slide_imgs)
                cb(0.10, f"Ses segmentleri hazırlanıyor ({n_actual} slayt)…")
                audio_paths, dur_list = prepare_audio_segments(
                    slide_audio_map = st.session_state.ss_slide_audio,
                    durations       = st.session_state.ss_durations,
                    n_slides        = n_actual,
                    global_audio    = st.session_state.ss_global_audio,
                    use_global      = st.session_state.ss_use_global,
                    work_dir        = work_dir,
                )
                slide_speakers = [
                    chars[min(st.session_state.ss_slide_speaker.get(i, 0), len(chars)-1)]
                    for i in range(n_actual)
                ]
                video_bytes = build_video(
                    slide_images = slide_imgs,
                    audio_paths  = audio_paths,
                    durations    = dur_list,
                    speakers     = slide_speakers,
                    work_dir     = work_dir,
                    cb           = cb,
                )
                st.session_state.ss_video_bytes  = video_bytes
                st.session_state.ss_slide_images = slide_imgs
            except RuntimeError as e:
                st.error(f"❌ Hata:\n\n{e}")
            except Exception as e:
                import traceback
                st.error(f"❌ Beklenmedik hata: {e}")
                with st.expander("🔍 Traceback"):
                    st.code(traceback.format_exc())
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)

        # ── Video çıktısı ─────────────────────────────────────
        if st.session_state.ss_video_bytes:
            vb   = st.session_state.ss_video_bytes
            size = len(vb)
            size_str = (f"{size//(1024*1024):.1f} MB"
                        if size > 1_048_576 else f"{size//1024:,} KB")
            st.success(f"✅ Video hazır — **{size_str}**")
            st.video(vb)
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    "⬇️ MP4 İndir", data=vb,
                    file_name="3soru3dakika_elif_aracıoglu.mp4", mime="video/mp4",
                    use_container_width=True, type="primary", key="wu_dl",
                )
            with col_d2:
                b64v = base64.b64encode(vb).decode()
                st.markdown(
                    f'<a href="data:video/mp4;base64,{b64v}" download="3soru3dakika_elif_aracıoglu.mp4" class="dl-alt">'
                    '📥 Alternatif İndirme</a>',
                    unsafe_allow_html=True,
                )
            imgs = st.session_state.ss_slide_images
            if imgs:
                st.markdown("---")
                st.markdown('<p class="lbl">Slayt Önizlemeleri</p>', unsafe_allow_html=True)
                pc = st.columns(min(len(imgs), 4))
                for i, img in enumerate(imgs):
                    spk_idx = min(
                        st.session_state.ss_slide_speaker.get(i, 0), len(chars)-1)
                    spk = chars[spk_idx]
                    with pc[i % 4]:
                        st.image(img, caption=f"{spk['emoji']} {spk['name']} — S{i+1}",
                                 use_container_width=True)

if __name__ == "__main__":
    main()
