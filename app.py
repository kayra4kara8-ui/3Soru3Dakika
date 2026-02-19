"""
🎬 PPTX + Ses → Senkronize MP4
PowerPoint sununuzu yükleyin, sesi ekleyin, profesyonel video alın.
Streamlit Cloud uyumlu — ffmpeg sistem gerekmez (imageio-ffmpeg bundled).
"""

import streamlit as st
import io, os, math, json, base64, tempfile, subprocess, time
from pathlib import Path
from typing import Optional
import numpy as np

# ── Bundled ffmpeg (Streamlit Cloud'da sistem ffmpeg olmadığı için) ──────────
def get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"          # son çare: PATH'teki

FFMPEG = get_ffmpeg()
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG

# ── İkincil bağımlılıklar ────────────────────────────────────────────────────
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
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    PPTX_OK = True
except ImportError:
    PPTX_OK = False

# ─────────────────────────────────────────────────────────────────────────────
# SABITLER
# ─────────────────────────────────────────────────────────────────────────────
VIDEO_W, VIDEO_H, VIDEO_FPS = 1280, 720, 24
SLIDE_W_IN, SLIDE_H_IN = 10.0, 5.625      # 16:9 inç

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]

# ─────────────────────────────────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────────────────────────────────────

def best_font(size: int):
    for p in FONT_PATHS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def audio_duration_sec(data: bytes) -> float:
    """MP3 byte uzunluğundan yaklaşık süre (sn)."""
    if not data:
        return 3.0
    return max(1.0, len(data) / 16_000)


def pptx_to_slide_images(pptx_bytes: bytes, w=VIDEO_W, h=VIDEO_H) -> list:
    """
    PPTX → her slayt için PIL.Image listesi.
    Pipeline: pptx bytes → geçici .pptx → LibreOffice → PDF → pdftoppm → JPG → PIL
    """
    tmp = tempfile.mkdtemp()
    pptx_path = os.path.join(tmp, "presentation.pptx")
    pdf_path  = os.path.join(tmp, "presentation.pdf")

    with open(pptx_path, "wb") as f:
        f.write(pptx_bytes)

    # 1. LibreOffice ile PDF'e çevir
    r = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf",
         "--outdir", tmp, pptx_path],
        capture_output=True, text=True, timeout=60
    )
    if r.returncode != 0 or not os.path.exists(pdf_path):
        # PDF adı farklı çıkabilir
        pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
        if not pdfs:
            raise RuntimeError(f"LibreOffice PDF dönüşümü başarısız:\n{r.stderr}")
        pdf_path = os.path.join(tmp, pdfs[0])

    # 2. PDF → JPG (her sayfa ayrı dosya)
    img_base = os.path.join(tmp, "slide")
    r2 = subprocess.run(
        ["pdftoppm", "-jpeg", "-r", "150", pdf_path, img_base],
        capture_output=True, text=True, timeout=60
    )
    if r2.returncode != 0:
        raise RuntimeError(f"pdftoppm başarısız:\n{r2.stderr}")

    # 3. Dosyaları sırala ve yükle
    imgs = sorted(
        [os.path.join(tmp, f) for f in os.listdir(tmp)
         if f.startswith("slide") and f.endswith(".jpg")]
    )
    if not imgs:
        raise RuntimeError("Slayt görüntüsü üretilemedi.")

    result = []
    for img_path in imgs:
        img = Image.open(img_path).convert("RGB").resize((w, h), Image.LANCZOS)
        result.append(img)

    # Temp temizle
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    return result


def make_overlay_frame(slide_img: "Image", slide_idx: int, total: int,
                        t: float, audio_active: bool) -> "Image":
    """
    Slayt görüntüsü üzerine broadcast katmanı ekler:
    - Alt progress bar
    - Ses dalga animasyonu (aktifse)
    - Slayt numarası
    """
    frame = slide_img.copy()
    draw  = ImageDraw.Draw(frame)
    w, h  = frame.size

    # ── Alt karartma bandı ──────────────────────────────────
    band_h = 48
    for y in range(h - band_h, h):
        alpha = int(200 * (y - (h - band_h)) / band_h)
        for x in range(0, w, 1):
            try:
                r_, g_, b_ = frame.getpixel((x, y))
                nr = max(0, r_ - alpha // 3)
                ng = max(0, g_ - alpha // 3)
                nb = max(0, b_ - alpha // 3)
                draw.point((x, y), fill=(nr, ng, nb))
            except Exception:
                pass

    # ── Progress bar ────────────────────────────────────────
    prog_w = int(w * (slide_idx + t) / total)
    draw.rectangle([0, h - 5, w, h], fill=(20, 20, 40))
    draw.rectangle([0, h - 5, prog_w, h], fill=(201, 168, 76))

    # ── Slayt numarası ───────────────────────────────────────
    fn = best_font(16)
    label = f"{slide_idx + 1}  /  {total}"
    draw.text((w - 90, h - 36), label, font=fn, fill=(200, 200, 220))

    # ── Ses dalgası (aktifse animasyonlu) ───────────────────
    if audio_active:
        bar_count = 9
        bar_w     = 6
        gap       = 4
        total_bar_w = bar_count * (bar_w + gap)
        bx_start  = w - total_bar_w - 16
        by_base   = h - 12
        for bi in range(bar_count):
            bh = int(4 + 18 * abs(math.sin(t * math.pi * 3 + bi * 0.7)))
            bx = bx_start + bi * (bar_w + gap)
            draw.rounded_rectangle(
                [bx, by_base - bh, bx + bar_w, by_base],
                radius=2, fill=(201, 168, 76, 200)
            )

    return frame


def build_video(
    slide_images: list,          # [PIL.Image, ...]
    audio_segments: list,        # [bytes or None, ...]  — her slayta karşılık
    durations: list,             # [float, ...]          — sn cinsinden
    progress_cb=None,
) -> bytes:
    """
    Slayt görüntüleri + ses segmentleri → MP4 bytes.
    Her slayt kendi sesi ile senkronize edilir.
    """
    all_frames = []
    all_audio  = b""

    total_slides = len(slide_images)
    total_frames_est = sum(max(1, int(d * VIDEO_FPS)) for d in durations)
    done_frames = 0

    for idx, (img, audio, dur) in enumerate(zip(slide_images, audio_segments, durations)):
        n_frames = max(VIDEO_FPS, int(dur * VIDEO_FPS))
        audio    = audio or b""
        all_audio += audio

        for fi in range(n_frames):
            t = fi / max(n_frames - 1, 1)
            frame = make_overlay_frame(img, idx, total_slides, t, len(audio) > 0)
            all_frames.append(np.array(frame))
            done_frames += 1

            if progress_cb and done_frames % 12 == 0:
                pct = done_frames / max(total_frames_est, 1)
                progress_cb(pct * 0.75, f"Kare {done_frames}/{total_frames_est}")

    if progress_cb:
        progress_cb(0.78, "Video kodlanıyor…")

    # ── Geçici dosyalar ──────────────────────────────────────
    tmp_video = tempfile.mktemp(suffix=".mp4")
    tmp_audio = tempfile.mktemp(suffix=".mp3")
    tmp_final = tempfile.mktemp(suffix="_final.mp4")

    # ── Video karelerini yaz ─────────────────────────────────
    iio.imwrite(
        tmp_video, all_frames,
        fps=VIDEO_FPS,
        codec="libx264",
        output_params=["-crf", "22", "-preset", "fast", "-pix_fmt", "yuv420p"],
        plugin="FFMPEG",
    )

    if progress_cb:
        progress_cb(0.88, "Ses birleştiriliyor…")

    # ── Ses + video mux ─────────────────────────────────────
    if all_audio and len(all_audio) > 256:
        with open(tmp_audio, "wb") as f:
            f.write(all_audio)
        cmd = [
            FFMPEG, "-y",
            "-i", tmp_video,
            "-i", tmp_audio,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            tmp_final,
        ]
    else:
        # Sessiz video
        cmd = [FFMPEG, "-y", "-i", tmp_video, "-c:v", "copy", tmp_final]

    subprocess.run(cmd, capture_output=True, timeout=300)

    if progress_cb:
        progress_cb(1.0, "Tamamlandı!")

    # ── Oku ve temizle ───────────────────────────────────────
    for p in [tmp_video, tmp_audio]:
        try: os.unlink(p)
        except: pass

    if os.path.exists(tmp_final):
        data = open(tmp_final, "rb").read()
        os.unlink(tmp_final)
        return data

    raise RuntimeError("MP4 oluşturulamadı.")


# ─────────────────────────────────────────────────────────────────────────────
# PPTX BİLGİ OKUYUCU
# ─────────────────────────────────────────────────────────────────────────────

def read_pptx_info(pptx_bytes: bytes) -> list:
    """
    PPTX'ten slayt sayısı ve konuşmacı notlarını okur.
    Döner: [{"idx": 0, "notes": "..."}, ...]
    """
    prs = Presentation(io.BytesIO(pptx_bytes))
    slides = []
    for i, slide in enumerate(prs.slides):
        notes_text = ""
        try:
            notes_slide = slide.notes_slide
            tf = notes_slide.notes_text_frame
            notes_text = tf.text.strip()
        except Exception:
            pass
        slides.append({"idx": i, "notes": notes_text})
    return slides


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;600;700&display=swap');

:root {
  --gold: #C9A84C;
  --dark: #06060f;
  --surface: #0e0e1c;
  --border: rgba(201,168,76,.18);
}

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
.stApp { background: radial-gradient(ellipse at 20% 40%, #0d1525 0%, #06060f 65%); color: #e8e8f0; }

section[data-testid="stSidebar"] {
  background: rgba(6,6,18,.97);
  border-right: 1px solid var(--border);
}

.page-header {
  text-align: center;
  padding: 1.6rem 1rem 1rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.2rem;
}
.page-header h1 {
  font-family: 'DM Serif Display', serif;
  font-size: 2.2rem;
  background: linear-gradient(90deg,#C9A84C,#f0d080,#C9A84C);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 .2rem;
}
.page-header p { color: #556; font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; }

/* Section labels */
.sec-label {
  font-size: .62rem; letter-spacing: .16em; text-transform: uppercase;
  color: #445; margin: .9rem 0 .3rem;
}

/* Slide cards */
.slide-card {
  display: flex; align-items: flex-start; gap: .75rem;
  padding: .75rem 1rem; margin: .35rem 0;
  background: rgba(255,255,255,.03);
  border: 1px solid rgba(255,255,255,.06);
  border-radius: 10px;
  transition: background .15s;
}
.slide-card:hover { background: rgba(255,255,255,.06); }
.slide-num {
  font-size: 1.1rem; font-weight: 700; color: var(--gold);
  min-width: 2rem; padding-top: .1rem;
}
.slide-notes { font-size: .85rem; color: #aab; line-height: 1.55; }
.slide-dur   { font-size: .72rem; color: #556; margin-top: .2rem; }

/* Status row */
.status-row {
  display: flex; gap: 1rem; flex-wrap: wrap;
  padding: .55rem .9rem; margin: .5rem 0;
  background: rgba(201,168,76,.06);
  border: 1px solid var(--border);
  border-radius: 8px; font-size: .78rem; color: #778;
}
.status-row strong { color: var(--gold); }

/* Dep badge */
.dep { font-size: .72rem; margin: .1rem 0; }
.dep-ok  { color: #7ec878; }
.dep-err { color: #e07b7b; }

audio { width: 100%; border-radius: 7px; margin: 2px 0; }
textarea {
  background: rgba(255,255,255,.04) !important;
  border-radius: 10px !important;
  color: #eee !important;
  font-size: .84rem !important;
  border: 1px solid var(--border) !important;
}
.stProgress > div > div { border-radius: 10px; }
hr { border-color: rgba(255,255,255,.06); }
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def init_state():
    defs = dict(
        pptx_bytes=None,
        slide_info=[],       # [{"idx", "notes"}, ...]
        slide_images=[],     # [PIL.Image, ...]
        audio_map={},        # {slide_idx: bytes}
        durations={},        # {slide_idx: float}
        global_audio=None,   # bytes — genel ses
        use_global=True,
        video_bytes=None,
    )
    for k, v in defs.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

def sidebar():
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:.8rem 0 .4rem;">'
            '<div style="font-family:serif;font-size:1.2rem;color:#C9A84C;letter-spacing:.1em;">🎬 VİDEO STÜDYO</div>'
            '<div style="font-size:.62rem;color:#445;letter-spacing:.14em;text-transform:uppercase;margin-top:3px;">PPTX + Ses → MP4</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        # ── Bağımlılıklar ─────────────────────────────────
        st.markdown('<p class="sec-label">📦 Sistem Durumu</p>', unsafe_allow_html=True)

        deps = {
            "Pillow": PIL_OK,
            "imageio": IMAGEIO_OK,
            "python-pptx": PPTX_OK,
        }
        for name, ok in deps.items():
            cls = "dep-ok" if ok else "dep-err"
            ic  = "🟢" if ok else "🔴"
            st.markdown(f'<div class="dep {cls}">{ic} {name}</div>', unsafe_allow_html=True)

        # LibreOffice
        lo_ok = os.path.exists("/usr/bin/libreoffice") or os.path.exists("/usr/bin/soffice")
        st.markdown(
            f'<div class="dep {"dep-ok" if lo_ok else "dep-err"}">{"🟢" if lo_ok else "🔴"} LibreOffice</div>',
            unsafe_allow_html=True,
        )
        # pdftoppm
        pp_ok = os.path.exists("/usr/bin/pdftoppm")
        st.markdown(
            f'<div class="dep {"dep-ok" if pp_ok else "dep-err"}">{"🟢" if pp_ok else "🔴"} pdftoppm</div>',
            unsafe_allow_html=True,
        )
        # ffmpeg (bundled)
        ffmpeg_ok = os.path.exists(FFMPEG) or FFMPEG == "ffmpeg"
        st.markdown(
            f'<div class="dep dep-ok">🟢 ffmpeg (bundled)</div>',
            unsafe_allow_html=True,
        )

        if not all(deps.values()) or not lo_ok or not pp_ok:
            st.caption("packages.txt'e: `poppler-utils libreoffice`")

        st.markdown("---")
        st.caption("v6.0 · Streamlit Cloud uyumlu")


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
    sidebar()

    st.markdown(
        '<div class="page-header">'
        '<h1>🎬 PPTX + Ses → MP4</h1>'
        '<p>PowerPoint sunumunuzu yükleyin · Sesi ekleyin · Senkronize video alın</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ══════════════════════════════════════════════════════════
    # BÖLÜM 1 — PPTX YÜKLEME
    # ══════════════════════════════════════════════════════════
    st.markdown('<p class="sec-label">1 · PowerPoint Dosyası</p>', unsafe_allow_html=True)

    col_upload, col_info = st.columns([1, 1], gap="large")

    with col_upload:
        pptx_file = st.file_uploader(
            "PPTX dosyasını sürükleyin",
            type=["pptx"],
            key="pptx_upload",
            label_visibility="collapsed",
        )
        if pptx_file:
            raw = pptx_file.read()
            if raw != st.session_state.pptx_bytes:
                st.session_state.pptx_bytes  = raw
                st.session_state.slide_images = []
                st.session_state.video_bytes  = None
                with st.spinner("Slaytlar okunuyor…"):
                    try:
                        st.session_state.slide_info = read_pptx_info(raw)
                    except Exception as e:
                        st.error(f"PPTX okunamadı: {e}")
                        st.session_state.slide_info = []

        if st.session_state.pptx_bytes:
            n = len(st.session_state.slide_info)
            st.success(f"✅ {pptx_file.name if pptx_file else 'Dosya'} yüklendi — **{n}** slayt")

    with col_info:
        if st.session_state.slide_info:
            st.markdown(
                f'<div class="status-row">'
                f'<span>📊 <strong>{len(st.session_state.slide_info)}</strong> slayt</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            # Konuşmacı notları önizleme
            for s in st.session_state.slide_info[:5]:
                note_preview = (s["notes"][:80] + "…") if len(s["notes"]) > 80 else s["notes"]
                st.markdown(
                    f'<div class="slide-card">'
                    f'<div class="slide-num">{s["idx"]+1}</div>'
                    f'<div><div class="slide-notes">{note_preview or "<em style=\'color:#445\'>Konuşmacı notu yok</em>"}</div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            if len(st.session_state.slide_info) > 5:
                st.caption(f"…ve {len(st.session_state.slide_info)-5} slayt daha")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════
    # BÖLÜM 2 — SES ATAMA
    # ══════════════════════════════════════════════════════════
    st.markdown('<p class="sec-label">2 · Ses Dosyaları</p>', unsafe_allow_html=True)

    if not st.session_state.slide_info:
        st.info("ℹ️ Önce bir PPTX dosyası yükleyin.")
    else:
        n_slides = len(st.session_state.slide_info)

        mode = st.radio(
            "Ses modu",
            ["🔊 Tek ses (tüm slaytlara bölünür)", "🎙️ Her slayta ayrı ses"],
            horizontal=True,
            label_visibility="collapsed",
        )
        use_global = "Tek ses" in mode
        st.session_state.use_global = use_global

        if use_global:
            # ── Tek ses ────────────────────────────────────
            st.caption("Ses dosyasını yükleyin. Her slayt eşit süre alır veya sürelerini aşağıdan ayarlayabilirsiniz.")
            gf = st.file_uploader(
                "Genel ses (MP3/WAV/M4A)",
                type=["mp3","wav","m4a","ogg"],
                key="global_audio",
                label_visibility="collapsed",
            )
            if gf:
                ab = gf.read()
                st.session_state.global_audio = ab
                total_dur = audio_duration_sec(ab)
                per_slide = total_dur / n_slides
                for i in range(n_slides):
                    st.session_state.durations[i] = per_slide
                st.audio(ab, format="audio/mp3")
                st.caption(f"Toplam: ~{total_dur:.1f} sn — Slayt başı: ~{per_slide:.1f} sn")

        else:
            # ── Slayt bazlı ses ─────────────────────────────
            st.caption("Her slayt için ayrı ses dosyası yükleyin.")
            cols = st.columns(min(n_slides, 4))
            for i, sinfo in enumerate(st.session_state.slide_info):
                with cols[i % min(n_slides, 4)]:
                    uf = st.file_uploader(
                        f"Slayt {i+1}",
                        type=["mp3","wav","m4a","ogg"],
                        key=f"audio_slide_{i}",
                    )
                    if uf:
                        ab = uf.read()
                        st.session_state.audio_map[i] = ab
                        st.session_state.durations[i] = audio_duration_sec(ab)
                        st.audio(ab, format="audio/mp3")
                        st.caption(f"~{st.session_state.durations[i]:.1f} sn")
                    elif i not in st.session_state.audio_map:
                        st.caption("Ses yok → 3 sn")
                        st.session_state.durations[i] = 3.0

        st.markdown("---")

        # ── Slayt süre ayarı (override) ─────────────────────
        with st.expander("⚙️ Slayt sürelerini manuel ayarla (opsiyonel)"):
            st.caption("Her slayt için süreyi saniye cinsinden girin. Ses varsa otomatik hesaplanır; buradan ezebilirsiniz.")
            dur_cols = st.columns(min(n_slides, 5))
            for i in range(n_slides):
                with dur_cols[i % min(n_slides, 5)]:
                    default_dur = st.session_state.durations.get(i, 3.0)
                    d = st.number_input(
                        f"S{i+1}",
                        min_value=0.5, max_value=60.0,
                        value=float(default_dur),
                        step=0.5, key=f"dur_{i}",
                    )
                    st.session_state.durations[i] = d

    # ══════════════════════════════════════════════════════════
    # BÖLÜM 3 — VIDEO OLUŞTUR
    # ══════════════════════════════════════════════════════════
    st.markdown('<p class="sec-label">3 · Video Oluştur</p>', unsafe_allow_html=True)

    can_render = (
        st.session_state.pptx_bytes is not None
        and PIL_OK and IMAGEIO_OK and PPTX_OK
    )

    if not can_render:
        if not st.session_state.pptx_bytes:
            st.info("ℹ️ PPTX dosyası yükleyin.")
        else:
            st.error("❌ Gerekli kütüphaneler eksik. Sidebar'daki durumu kontrol edin.")
    else:
        n_slides   = len(st.session_state.slide_info)
        total_secs = sum(st.session_state.durations.get(i, 3.0) for i in range(n_slides))
        mins, secs = divmod(int(total_secs), 60)
        st.markdown(
            f'<div class="status-row">'
            f'<span>🎞️ <strong>{n_slides}</strong> slayt</span>'
            f'<span>⏱️ ~<strong>{mins}:{secs:02d}</strong> dakika</span>'
            f'<span>📐 <strong>{VIDEO_W}×{VIDEO_H}</strong></span>'
            f'<span>🎬 <strong>{VIDEO_FPS} FPS</strong></span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        make_btn = st.button(
            "🎬 Video Oluştur",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.video_bytes is not None,
        )

        if st.session_state.video_bytes:
            st.button("🔄 Yeniden Oluştur", on_click=lambda: st.session_state.update(video_bytes=None), use_container_width=True)

        if make_btn:
            status_ph = st.empty()
            prog_ph   = st.progress(0)

            def cb(pct, msg):
                prog_ph.progress(min(float(pct), 1.0), msg)
                status_ph.markdown(f"⚙️ {msg}")

            try:
                # 1. PPTX → slayt görüntüleri
                cb(0.02, "Slaytlar görüntüye dönüştürülüyor… (LibreOffice)")
                slide_imgs = pptx_to_slide_images(st.session_state.pptx_bytes)
                st.session_state.slide_images = slide_imgs
                n_actual = len(slide_imgs)

                # 2. Ses segmentlerini hazırla
                cb(0.08, "Ses segmentleri hazırlanıyor…")
                use_global = st.session_state.use_global
                global_audio = st.session_state.global_audio

                audio_segs = []
                durations  = []

                if use_global and global_audio:
                    # Sesi n_actual eşit parçaya böl (ham byte bölme — player destekler)
                    chunk = len(global_audio) // n_actual
                    for i in range(n_actual):
                        start = i * chunk
                        end   = start + chunk if i < n_actual - 1 else len(global_audio)
                        audio_segs.append(global_audio[start:end])
                        durations.append(st.session_state.durations.get(i, 3.0))
                else:
                    for i in range(n_actual):
                        audio_segs.append(st.session_state.audio_map.get(i))
                        durations.append(st.session_state.durations.get(i, 3.0))

                # 3. Video oluştur
                video = build_video(slide_imgs, audio_segs, durations, progress_cb=cb)
                st.session_state.video_bytes = video

            except Exception as e:
                st.error(f"❌ Hata: {e}")
                import traceback
                st.code(traceback.format_exc())

        # ── Video önizleme + indirme ─────────────────────────
        if st.session_state.video_bytes:
            vb = st.session_state.video_bytes
            st.success(f"✅ Video hazır — {len(vb)//1024:,} KB")
            st.video(vb)

            # Streamlit download button
            st.download_button(
                label="⬇️ MP4 İndir",
                data=vb,
                file_name="sunum_video.mp4",
                mime="video/mp4",
                use_container_width=True,
                type="primary",
            )

            # Base64 fallback linki
            b64 = base64.b64encode(vb).decode()
            st.markdown(
                f'<a href="data:video/mp4;base64,{b64}" download="sunum_video.mp4" '
                f'style="display:block;text-align:center;padding:9px;margin-top:6px;'
                f'background:rgba(201,168,76,.15);border:1px solid rgba(201,168,76,.3);'
                f'color:#C9A84C;border-radius:8px;font-weight:600;font-size:13px;'
                f'text-decoration:none;letter-spacing:.05em;">📥 Alternatif İndirme Linki</a>',
                unsafe_allow_html=True,
            )

            # Slayt önizlemeleri
            if st.session_state.slide_images:
                st.markdown("---")
                st.markdown('<p class="sec-label">📸 Slayt Önizlemeleri</p>', unsafe_allow_html=True)
                preview_cols = st.columns(min(len(st.session_state.slide_images), 4))
                for i, img in enumerate(st.session_state.slide_images):
                    with preview_cols[i % 4]:
                        st.image(img, caption=f"Slayt {i+1}", use_container_width=True)


if __name__ == "__main__":
    main()
