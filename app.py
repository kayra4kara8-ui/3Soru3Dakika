"""
PPTX + Ses -> Senkronize MP4 | v7.0 | Streamlit Cloud uyumlu
Düzeltmeler:
  - Ses birleştirme: ham bayt kesme yerine ffmpeg concat filteri
  - Bellek optimizasyonu: kareler diske stream edilir, RAM'de tutulmaz
  - Timeout: 900s (15 dk) — uzun videolar için yeterli
  - Detaylı hata yönetimi: LibreOffice, pdftoppm, ffmpeg aşamaları ayrı ayrı
  - İlerleme: kare bazında gerçek zamanlı güncelleme
Widget key prefix: wu_   Session state prefix: ss_   HİÇBİR KEY ÇAKIŞMASI YOK
"""

import streamlit as st
import io, os, math, base64, tempfile, subprocess, shutil, json, time
import numpy as np

# ── Bundled ffmpeg ─────────────────────────────────────────────────────────
def _get_ffmpeg():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"

FFMPEG = _get_ffmpeg()
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import imageio.v3 as iio
    IMAGEIO_OK = True
except ImportError:
    IMAGEIO_OK = False

try:
    from pptx import Presentation
    PPTX_OK = True
except ImportError:
    PPTX_OK = False

LO_BIN  = "/usr/bin/libreoffice" if os.path.exists("/usr/bin/libreoffice") else "/usr/bin/soffice"
LO_OK   = os.path.exists(LO_BIN)
PPM_OK  = os.path.exists("/usr/bin/pdftoppm")

VIDEO_W, VIDEO_H, VIDEO_FPS = 1280, 720, 24
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]


# ─────────────────────────────────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────────────────────────────────────

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
    """
    subprocess.run wrapper — hata olursa açıklayıcı RuntimeError fırlatır.
    timeout varsayılan 900s (15 dk) uzun videolar için yeterli.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
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


def audio_duration_ffprobe(audio_path: str) -> float:
    """
    ffprobe ile gerçek ses süresini saniye cinsinden döndür.
    Başarısız olursa dosya boyutuna göre tahmin döndür.
    """
    try:
        r = subprocess.run(
            [FFMPEG.replace("ffmpeg", "ffprobe").replace("ffmpeg", "ffprobe"),
             "-v", "error", "-show_entries", "format=duration",
             "-of", "json", audio_path],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(r.stdout)
        return float(data["format"]["duration"])
    except Exception:
        # ffprobe yoksa veya hata verirse boyuttan tahmin
        size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
        return max(1.0, size / 16_000)


def audio_duration_sec_bytes(data: bytes) -> float:
    """Bytes verisinden ses süresini tahmin et (ffprobe için geçici dosya kullan)."""
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


# ─────────────────────────────────────────────────────────────────────────────
# PPTX → GÖRÜNTÜLER
# ─────────────────────────────────────────────────────────────────────────────

def pptx_to_images(pptx_bytes: bytes) -> list:
    """
    PPTX → LibreOffice → PDF → pdftoppm → PIL Image listesi.
    Her adım ayrı try-except ile yakalanır.
    """
    tmp = tempfile.mkdtemp(prefix="pptx2img_")
    try:
        # 1) PPTX kaydet
        pptx_path = os.path.join(tmp, "presentation.pptx")
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)

        # 2) LibreOffice → PDF
        try:
            _run(
                [LO_BIN, "--headless", "--convert-to", "pdf",
                 "--outdir", tmp, pptx_path],
                timeout=180,
                step_name="LibreOffice PDF dönüşümü",
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"LibreOffice PDF dönüşümü başarısız.\n"
                f"packages.txt içinde 'libreoffice' satırı var mı?\n\n{e}"
            )

        pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
        if not pdfs:
            raise RuntimeError(
                "LibreOffice çalıştı ama PDF üretmedi. "
                "PPTX dosyası bozuk olabilir."
            )
        pdf_path = os.path.join(tmp, pdfs[0])

        # 3) pdftoppm → JPEG
        img_prefix = os.path.join(tmp, "slide")
        try:
            _run(
                ["pdftoppm", "-jpeg", "-r", "150", pdf_path, img_prefix],
                timeout=120,
                step_name="pdftoppm görüntü üretimi",
            )
        except RuntimeError as e:
            raise RuntimeError(
                f"pdftoppm başarısız.\n"
                f"packages.txt içinde 'poppler-utils' satırı var mı?\n\n{e}"
            )

        files = sorted([
            os.path.join(tmp, f)
            for f in os.listdir(tmp)
            if f.startswith("slide") and (f.endswith(".jpg") or f.endswith(".jpeg"))
        ])
        if not files:
            raise RuntimeError(
                "pdftoppm çalıştı ama görüntü üretmedi. "
                "PDF içeriği boş veya bozuk olabilir."
            )

        images = [
            Image.open(p).convert("RGB").resize((VIDEO_W, VIDEO_H), Image.LANCZOS)
            for p in files
        ]
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


# ─────────────────────────────────────────────────────────────────────────────
# SES BİRLEŞTİRME — FFMPEG CONCAT (ham bayt kesme yok!)
# ─────────────────────────────────────────────────────────────────────────────

def prepare_audio_segments(
    audio_map: dict,         # {slide_idx: bytes}
    durations: dict,         # {slide_idx: float (saniye)}
    n_slides: int,
    global_audio: bytes | None,
    use_global: bool,
    work_dir: str,
) -> tuple[list[str | None], list[float]]:
    """
    Her slayt için WAV/MP3 dosya yolu ve süre listesi döndürür.
    - Global ses: ffmpeg ile tam süresini ölç, her slayta orantılı dilim kes
    - Bireysel ses: olduğu gibi kaydet, süreyi ffprobe ile ölç
    Döner: (audio_paths: list[str|None], dur_list: list[float])
    """
    audio_paths = []
    dur_list = []

    if use_global and global_audio:
        # Global sesi diske yaz
        global_path = os.path.join(work_dir, "global_audio.audio")
        with open(global_path, "wb") as f:
            f.write(global_audio)

        total_dur = audio_duration_ffprobe(global_path)
        per_slide = total_dur / max(n_slides, 1)

        for i in range(n_slides):
            start_sec = i * per_slide
            seg_path = os.path.join(work_dir, f"seg_{i:04d}.aac")
            # ffmpeg ile doğru zamansal kesim — bayt kesme değil!
            try:
                _run(
                    [FFMPEG, "-y",
                     "-ss", str(start_sec),
                     "-t", str(per_slide),
                     "-i", global_path,
                     "-c:a", "aac", "-b:a", "128k",
                     "-ar", "44100",
                     seg_path],
                    timeout=60,
                    step_name=f"Global ses segment {i+1}",
                )
                audio_paths.append(seg_path)
            except Exception:
                audio_paths.append(None)
            dur_list.append(per_slide)

    else:
        for i in range(n_slides):
            aud_bytes = audio_map.get(i)
            if aud_bytes:
                raw_path = os.path.join(work_dir, f"raw_{i:04d}.audio")
                with open(raw_path, "wb") as f:
                    f.write(aud_bytes)
                # AAC'ye normalize et
                aac_path = os.path.join(work_dir, f"seg_{i:04d}.aac")
                try:
                    _run(
                        [FFMPEG, "-y", "-i", raw_path,
                         "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                         aac_path],
                        timeout=60,
                        step_name=f"Ses normalize {i+1}",
                    )
                    dur = audio_duration_ffprobe(aac_path)
                    audio_paths.append(aac_path)
                    dur_list.append(dur)
                except Exception:
                    audio_paths.append(None)
                    dur_list.append(durations.get(i, 3.0))
            else:
                audio_paths.append(None)
                dur_list.append(durations.get(i, 3.0))

    return audio_paths, dur_list


# ─────────────────────────────────────────────────────────────────────────────
# KARE RENDER
# ─────────────────────────────────────────────────────────────────────────────

def render_frame(slide_img, slide_idx, total, t, has_audio):
    frame = slide_img.copy()
    draw = ImageDraw.Draw(frame)
    w, h = frame.size

    # Progress bar
    prog_w = int(w * (slide_idx + t) / max(total, 1))
    draw.rectangle([0, h - 6, w, h], fill=(14, 14, 28))
    draw.rectangle([0, h - 6, prog_w, h], fill=(201, 168, 76))

    # Slayt sayacı
    fn = _font(14)
    draw.text((w - 95, h - 30), f"{slide_idx+1} / {total}",
              font=fn, fill=(180, 180, 210))

    # Ses animasyonu (equalizer çubukları)
    if has_audio:
        bc, bw, bg = 9, 6, 4
        bx0 = w - bc * (bw + bg) - 14
        by = h - 9
        for bi in range(bc):
            bh = int(5 + 18 * abs(math.sin(t * math.pi * 4.0 + bi * 0.9)))
            bx = bx0 + bi * (bw + bg)
            draw.rounded_rectangle(
                [bx, by - bh, bx + bw, by], radius=2, fill=(201, 168, 76)
            )
    return np.array(frame)


# ─────────────────────────────────────────────────────────────────────────────
# VİDEO OLUŞTURMA — STREAMING (RAM optimizasyonu)
# ─────────────────────────────────────────────────────────────────────────────

def build_video(
    slide_images: list,
    audio_paths: list,
    durations: list,
    work_dir: str,
    cb=None,
) -> bytes:
    """
    Kareler tek tek diske yazılır (imageio FfmpegWriter stream).
    RAM'de tüm kare listesi tutulmaz — büyük videolar için kritik.
    Ses: ffmpeg concat demuxer ile senkronize birleştirilir.
    """
    n = len(slide_images)
    total_frames = sum(max(1, int(d * VIDEO_FPS)) for d in durations)
    done_frames = 0

    tmp_video = os.path.join(work_dir, "raw_video.mp4")
    tmp_audio = os.path.join(work_dir, "concat_audio.aac")
    tmp_out   = os.path.join(work_dir, "output.mp4")

    # ── 1. Video stream (ses yok) ───────────────────────────────────────────
    if cb:
        cb(0.05, "Video kareleri işleniyor...")

    writer = iio.get_writer(
        tmp_video,
        fps=VIDEO_FPS,
        codec="libx264",
        output_params=["-crf", "22", "-preset", "fast", "-pix_fmt", "yuv420p"],
        plugin="FFMPEG",
    )
    try:
        for idx, (img, aud_path, dur) in enumerate(zip(slide_images, audio_paths, durations)):
            nf = max(VIDEO_FPS, int(dur * VIDEO_FPS))
            has_audio = aud_path is not None
            for fi in range(nf):
                t = fi / max(nf - 1, 1)
                frame = render_frame(img, idx, n, t, has_audio)
                writer.append_data(frame)
                done_frames += 1
                if cb and done_frames % 12 == 0:
                    pct = 0.05 + 0.60 * (done_frames / total_frames)
                    cb(pct, f"Kare {done_frames} / {total_frames} — Slayt {idx+1}/{n}")
    finally:
        writer.close()

    if cb:
        cb(0.68, "Ses segmentleri birleştiriliyor (ffmpeg concat)...")

    # ── 2. Ses concat demuxer ───────────────────────────────────────────────
    # Sadece sesi olan slaytlar için concat listesi oluştur
    # Ses olmayan slaytlar için sessizlik (anull kaynağı) üret
    audio_segments_for_concat = []
    for i, (aud_path, dur) in enumerate(zip(audio_paths, durations)):
        if aud_path and os.path.exists(aud_path):
            audio_segments_for_concat.append(aud_path)
        else:
            # Sessizlik dosyası üret
            silence_path = os.path.join(work_dir, f"silence_{i:04d}.aac")
            try:
                _run(
                    [FFMPEG, "-y",
                     "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo",
                     "-t", str(dur),
                     "-c:a", "aac", "-b:a", "128k",
                     silence_path],
                    timeout=30,
                    step_name=f"Sessizlik üretimi slayt {i+1}",
                )
                audio_segments_for_concat.append(silence_path)
            except Exception:
                audio_segments_for_concat.append(None)

    # Geçerli ses dosyaları var mı?
    valid_audio = [p for p in audio_segments_for_concat if p and os.path.exists(p)]
    has_any_audio = len(valid_audio) > 0

    if has_any_audio:
        # concat list dosyası oluştur
        concat_list_path = os.path.join(work_dir, "concat_list.txt")
        with open(concat_list_path, "w") as f:
            for p in audio_segments_for_concat:
                if p and os.path.exists(p):
                    f.write(f"file '{p}'\n")
                # None olanlar (sessizlik üretilemedi) atlanır

        try:
            _run(
                [FFMPEG, "-y",
                 "-f", "concat", "-safe", "0",
                 "-i", concat_list_path,
                 "-c:a", "aac", "-b:a", "128k",
                 tmp_audio],
                timeout=300,
                step_name="Ses concat birleştirme",
            )
            audio_ok = os.path.exists(tmp_audio) and os.path.getsize(tmp_audio) > 256
        except RuntimeError as e:
            # Ses birleştirilemiyor ama video devam eder
            st.warning(f"⚠️ Ses birleştirme hatası, video sessiz oluşturulacak:\n{e}")
            audio_ok = False
    else:
        audio_ok = False

    if cb:
        cb(0.82, "Video + ses birleştiriliyor...")

    # ── 3. Video + Ses mux ──────────────────────────────────────────────────
    if audio_ok:
        try:
            _run(
                [FFMPEG, "-y",
                 "-i", tmp_video,
                 "-i", tmp_audio,
                 "-c:v", "copy",
                 "-c:a", "aac",
                 "-b:a", "128k",
                 "-shortest",
                 "-movflags", "+faststart",   # web uyumlu moov atom
                 tmp_out],
                timeout=600,
                step_name="Video+ses mux",
            )
        except RuntimeError as e:
            st.warning(f"⚠️ Mux hatası, sessiz video döndürülüyor:\n{e}")
            # Sessiz video ile devam et
            _run(
                [FFMPEG, "-y", "-i", tmp_video,
                 "-c:v", "copy", "-movflags", "+faststart", tmp_out],
                timeout=300,
                step_name="Sessiz video fallback",
            )
    else:
        _run(
            [FFMPEG, "-y", "-i", tmp_video,
             "-c:v", "copy", "-movflags", "+faststart", tmp_out],
            timeout=300,
            step_name="Sessiz video",
        )

    if cb:
        cb(1.0, "Tamamlandı! ✅")

    if os.path.exists(tmp_out):
        with open(tmp_out, "rb") as f:
            return f.read()
    raise RuntimeError("Çıktı MP4 dosyası oluşturulamadı. ffmpeg loglarını kontrol edin.")


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,600;0,9..40,700;1,9..40,300&display=swap');
:root{
  --gold:#C9A84C;--gold-dim:rgba(201,168,76,.18);--gold-glow:rgba(201,168,76,.08);
  --bg:#06060f;--surface:rgba(255,255,255,.025);--border:rgba(255,255,255,.06);
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.stApp{
  background:
    radial-gradient(ellipse 80% 50% at 10% 20%,rgba(30,15,60,.45) 0%,transparent 70%),
    radial-gradient(ellipse 60% 40% at 90% 80%,rgba(15,30,55,.35) 0%,transparent 70%),
    #06060f;
  color:#e8e8f0;
}
section[data-testid="stSidebar"]{
  background:rgba(4,4,14,.98);
  border-right:1px solid var(--gold-dim);
}

/* Hero banner */
.hero{
  text-align:center;padding:2.2rem 1rem 1.4rem;
  border-bottom:1px solid var(--gold-dim);margin-bottom:1.4rem;
  position:relative;
}
.hero::before{
  content:'';position:absolute;inset:0;
  background:radial-gradient(ellipse 60% 80% at 50% 0%,rgba(201,168,76,.04) 0%,transparent 70%);
  pointer-events:none;
}
.hero h1{
  font-family:'DM Serif Display',serif;font-size:2.4rem;font-weight:400;
  background:linear-gradient(135deg,#C9A84C 0%,#f5e090 45%,#C9A84C 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;margin:0 0 .35rem;letter-spacing:.01em;
}
.hero p{color:#4a5570;font-size:.75rem;letter-spacing:.18em;text-transform:uppercase;}

/* Labels */
.lbl{
  font-size:.6rem;letter-spacing:.22em;text-transform:uppercase;
  color:#3a4560;margin:.8rem 0 .4rem;
  border-left:2px solid var(--gold);padding-left:.5rem;
}

/* Stat row */
.srow{
  display:flex;gap:.9rem;flex-wrap:wrap;padding:.55rem 1rem;margin:.5rem 0;
  background:var(--gold-glow);border:1px solid var(--gold-dim);border-radius:9px;
  font-size:.78rem;color:#667;align-items:center;
}
.srow strong{color:var(--gold);}

/* Slide preview cards */
.scard{
  display:flex;align-items:flex-start;gap:.75rem;padding:.75rem 1rem;margin:.35rem 0;
  background:var(--surface);border:1px solid var(--border);border-radius:11px;
  transition:border-color .2s;
}
.scard:hover{border-color:var(--gold-dim);}
.snum{
  font-size:.95rem;font-weight:700;color:var(--gold);
  min-width:2rem;padding-top:.05rem;opacity:.85;
}
.snote{font-size:.83rem;color:#8899bb;line-height:1.6;}

/* Dependency list */
.dep{font-size:.73rem;margin:.14rem 0;line-height:1.5;}
.ok{color:#6ed46a;}.er{color:#e07b7b;}

audio{width:100%;border-radius:8px;margin:3px 0;}
hr{border-color:var(--border);}

/* Progress */
.stProgress>div>div{border-radius:10px;}

/* Buttons */
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#C9A84C,#e8c968) !important;
  color:#06060f !important;font-weight:700 !important;border:none !important;
}
.stButton>button[kind="primary"]:hover{
  background:linear-gradient(135deg,#e8c968,#C9A84C) !important;
  transform:translateY(-1px);
  box-shadow:0 4px 20px rgba(201,168,76,.3) !important;
}

/* Download button */
.dl-alt{
  display:block;text-align:center;padding:10px 14px;margin-top:8px;
  background:rgba(201,168,76,.08);border:1px solid rgba(201,168,76,.25);
  color:#C9A84C;border-radius:9px;font-weight:600;font-size:.82rem;
  text-decoration:none;transition:background .2s,border-color .2s;
}
.dl-alt:hover{background:rgba(201,168,76,.14);border-color:rgba(201,168,76,.45);}
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def init_state():
    defaults = {
        "ss_pptx_bytes":   None,
        "ss_slide_notes":  [],
        "ss_slide_images": [],
        "ss_audio_map":    {},
        "ss_global_audio": None,
        "ss_durations":    {},
        "ss_use_global":   True,
        "ss_video_bytes":  None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:.9rem 0 .5rem;">'
            '<div style="font-family:\'DM Serif Display\',serif;font-size:1.2rem;'
            'color:#C9A84C;letter-spacing:.1em;">🎬 VİDEO STÜDYO</div>'
            '<div style="font-size:.6rem;color:#3a4560;letter-spacing:.16em;'
            'text-transform:uppercase;margin-top:4px;">PPTX + SES → MP4</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        st.markdown('<p class="lbl">Sistem Durumu</p>', unsafe_allow_html=True)

        checks = [
            ("Pillow (PIL)",  PIL_OK,    "pip: pillow"),
            ("imageio",       IMAGEIO_OK,"pip: imageio[ffmpeg]"),
            ("python-pptx",   PPTX_OK,   "pip: python-pptx"),
            ("LibreOffice",   LO_OK,     "packages.txt: libreoffice"),
            ("pdftoppm",      PPM_OK,    "packages.txt: poppler-utils"),
            ("ffmpeg",        True,      "imageio_ffmpeg"),
        ]
        for name, ok, hint in checks:
            cls = "ok" if ok else "er"
            icon = "🟢" if ok else "🔴"
            st.markdown(
                f'<div class="dep {cls}">{icon} {name}'
                + (f' <span style="color:#334;font-size:.65rem;">— {hint}</span>' if not ok else "")
                + '</div>',
                unsafe_allow_html=True,
            )

        if not LO_OK or not PPM_OK:
            st.markdown("---")
            st.caption(
                "**packages.txt** dosyanıza şunları ekleyin:\n```\nlibreoffice\npoppler-utils\n```"
            )
        st.markdown("---")
        st.markdown(
            '<div style="font-size:.62rem;color:#2a3040;text-align:center;">'
            'v7.0 · ffmpeg concat · stream render</div>',
            unsafe_allow_html=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="PPTX → MP4 Stüdyo",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    render_sidebar()

    st.markdown(
        '<div class="hero">'
        '<h1>🎬 PPTX + Ses → MP4</h1>'
        '<p>PowerPoint sunumunuzu yükleyin · Ses ekleyin · Senkronize video alın</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════════════════════
    # ADIM 1 — PPTX
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="lbl">① PowerPoint Dosyası</p>', unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 1], gap="large")

    with col_a:
        pptx_file = st.file_uploader(
            "PPTX dosyası", type=["pptx"], key="wu_pptx_file",
            label_visibility="collapsed",
        )
        if pptx_file is not None:
            raw = pptx_file.read()
            if raw != st.session_state.ss_pptx_bytes:
                st.session_state.ss_pptx_bytes   = raw
                st.session_state.ss_slide_images  = []
                st.session_state.ss_video_bytes   = None
                st.session_state.ss_audio_map     = {}
                st.session_state.ss_durations     = {}
                with st.spinner("PPTX okunuyor..."):
                    try:
                        st.session_state.ss_slide_notes = read_pptx_notes(raw)
                    except Exception as e:
                        st.error(f"PPTX konuşmacı notları okunamadı: {e}")
                        st.session_state.ss_slide_notes = []

        if st.session_state.ss_pptx_bytes:
            n = len(st.session_state.ss_slide_notes)
            st.success(f"Yüklendi — **{n}** slayt")

    with col_b:
        notes = st.session_state.ss_slide_notes
        if notes:
            st.markdown(
                f'<div class="srow"><span>📊 <strong>{len(notes)}</strong> slayt</span></div>',
                unsafe_allow_html=True,
            )
            for i, note in enumerate(notes[:5]):
                preview = (note[:90] + "…") if len(note) > 90 else (note or "—")
                st.markdown(
                    f'<div class="scard">'
                    f'<div class="snum">{i+1}</div>'
                    f'<div class="snote">{preview}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if len(notes) > 5:
                st.caption(f"… ve {len(notes)-5} slayt daha")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════════
    # ADIM 2 — SES
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="lbl">② Ses Dosyaları</p>', unsafe_allow_html=True)

    if not st.session_state.ss_slide_notes:
        st.info("Önce bir PPTX dosyası yükleyin.")
    else:
        n_slides = len(st.session_state.ss_slide_notes)

        mode = st.radio(
            "Ses modu",
            ["🔊 Tek ses — tüm sunuma", "🎙️ Her slayta ayrı ses"],
            key="wu_mode_radio",
            horizontal=True,
            label_visibility="collapsed",
        )
        use_global = mode.startswith("🔊")
        st.session_state.ss_use_global = use_global

        if use_global:
            st.caption(
                "Tek bir ses dosyası yükleyin. "
                "Ses, **ffmpeg ile milisaniye hassasiyetinde** slaytlara bölünür."
            )
            gf = st.file_uploader(
                "Genel ses", type=["mp3", "wav", "m4a", "ogg"],
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
                    f"Toplam: ~{total_dur:.1f} sn  —  "
                    f"Slayt başına: ~{per_slide:.1f} sn  —  "
                    f"Bölme: ffmpeg zamansal kesim"
                )

        else:
            st.caption("Her slayt için ayrı ses dosyası yükleyin. Eksik slaytlara sessizlik eklenir.")
            per_row = min(n_slides, 4)
            n_rows = math.ceil(n_slides / per_row)
            col_grids = [st.columns(per_row) for _ in range(n_rows)]
            for i in range(n_slides):
                row, col = i // per_row, i % per_row
                with col_grids[row][col]:
                    st.markdown(f"**Slayt {i+1}**")
                    uf = st.file_uploader(
                        f"Slayt {i+1}", type=["mp3", "wav", "m4a", "ogg"],
                        key=f"wu_sl_{i}", label_visibility="collapsed",
                    )
                    if uf is not None:
                        ab = uf.read()
                        st.session_state.ss_audio_map[i] = ab
                        dur = audio_duration_sec_bytes(ab)
                        st.session_state.ss_durations[i] = dur
                        st.audio(ab, format="audio/mp3")
                        st.caption(f"~{dur:.1f} sn")
                    else:
                        if i not in st.session_state.ss_durations:
                            st.session_state.ss_durations[i] = 3.0
                        st.caption(f"Ses yok → {st.session_state.ss_durations[i]:.0f} sn sessizlik")

        with st.expander("⚙️ Slayt sürelerini manuel ayarla (opsiyonel)"):
            per_row2 = min(n_slides, 5)
            n_rows2  = math.ceil(n_slides / per_row2)
            dur_grids = [st.columns(per_row2) for _ in range(n_rows2)]
            for i in range(n_slides):
                row, col = i // per_row2, i % per_row2
                with dur_grids[row][col]:
                    default = float(st.session_state.ss_durations.get(i, 3.0))
                    d = st.number_input(
                        f"S{i+1} (sn)", min_value=0.5, max_value=300.0,
                        value=default, step=0.5, key=f"wu_dur_{i}",
                    )
                    st.session_state.ss_durations[i] = d

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════════
    # ADIM 3 — VİDEO
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown('<p class="lbl">③ Video Oluştur</p>', unsafe_allow_html=True)

    can_go = (
        st.session_state.ss_pptx_bytes is not None
        and PIL_OK and IMAGEIO_OK and PPTX_OK and LO_OK and PPM_OK
    )

    if not can_go:
        if not st.session_state.ss_pptx_bytes:
            st.info("Önce PPTX dosyası yükleyin.")
        else:
            missing = [
                name for name, ok in [
                    ("Pillow", PIL_OK), ("imageio", IMAGEIO_OK),
                    ("python-pptx", PPTX_OK), ("libreoffice", LO_OK),
                    ("poppler-utils", PPM_OK),
                ] if not ok
            ]
            st.error(f"Eksik bağımlılık: {', '.join(missing)}")
    else:
        n_slides = len(st.session_state.ss_slide_notes)
        total_secs = sum(st.session_state.ss_durations.get(i, 3.0) for i in range(n_slides))
        mins, secs = divmod(int(total_secs), 60)

        st.markdown(
            f'<div class="srow">'
            f'<span>🎞️ <strong>{n_slides}</strong> slayt</span>'
            f'<span>⏱️ ~<strong>{mins}:{secs:02d}</strong></span>'
            f'<span>📐 <strong>{VIDEO_W}×{VIDEO_H} px</strong></span>'
            f'<span>🎬 <strong>{VIDEO_FPS} FPS</strong></span>'
            f'<span>🔊 <strong>ffmpeg concat</strong></span>'
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
            prog  = st.progress(0)
            stat  = st.empty()
            t0    = time.time()

            def cb(pct: float, msg: str):
                elapsed = time.time() - t0
                prog.progress(min(float(pct), 1.0))
                stat.markdown(
                    f"⚙️ **{msg}** &nbsp;&nbsp; "
                    f'<span style="color:#3a4560;font-size:.78rem;">'
                    f"geçen süre: {elapsed:.0f}s</span>",
                    unsafe_allow_html=True,
                )

            work_dir = tempfile.mkdtemp(prefix="vidstudio_")
            try:
                # Adım A — Slayt görüntüleri
                cb(0.02, "Slaytlar işleniyor (LibreOffice + pdftoppm)…")
                slide_imgs = pptx_to_images(st.session_state.ss_pptx_bytes)
                n_actual   = len(slide_imgs)

                # Adım B — Ses hazırlama
                cb(0.10, f"Ses segmentleri hazırlanıyor ({n_actual} slayt)…")
                audio_paths, dur_list = prepare_audio_segments(
                    audio_map    = st.session_state.ss_audio_map,
                    durations    = st.session_state.ss_durations,
                    n_slides     = n_actual,
                    global_audio = st.session_state.ss_global_audio,
                    use_global   = st.session_state.ss_use_global,
                    work_dir     = work_dir,
                )

                # Adım C — Video oluşturma
                video_bytes = build_video(
                    slide_images = slide_imgs,
                    audio_paths  = audio_paths,
                    durations    = dur_list,
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
                with st.expander("🔍 Detaylı iz (traceback)"):
                    st.code(traceback.format_exc())
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)

        # ── Video çıktısı ────────────────────────────────────────────────────
        if st.session_state.ss_video_bytes:
            vb   = st.session_state.ss_video_bytes
            size = len(vb)
            size_str = f"{size // (1024*1024):.1f} MB" if size > 1_048_576 else f"{size // 1024:,} KB"
            st.success(f"✅ Video hazır — **{size_str}**")
            st.video(vb)

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    label="⬇️ MP4 İndir",
                    data=vb, file_name="sunum.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                    type="primary",
                    key="wu_dl",
                )
            with col_d2:
                b64 = base64.b64encode(vb).decode()
                st.markdown(
                    f'<a href="data:video/mp4;base64,{b64}" download="sunum.mp4" class="dl-alt">'
                    '📥 Alternatif İndirme</a>',
                    unsafe_allow_html=True,
                )

            # Slayt önizlemeleri
            imgs = st.session_state.ss_slide_images
            if imgs:
                st.markdown("---")
                st.markdown('<p class="lbl">Slayt Önizlemeleri</p>', unsafe_allow_html=True)
                pc = st.columns(min(len(imgs), 4))
                for i, img in enumerate(imgs):
                    with pc[i % 4]:
                        st.image(img, caption=f"Slayt {i+1}", use_container_width=True)


if __name__ == "__main__":
    main()
