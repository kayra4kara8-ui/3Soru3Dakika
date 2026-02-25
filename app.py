"""
3 Soru 3 Dakika | Eczacı Elif Aracıoğlu | Video Stüdyo v14.0
──────────────────────────────────────────────────────────────
• Marka rengi: Eczacı yeşili #34A883, Cormorant Garamond + DM Sans
• Ses temizleme: highpass(80Hz) + afftdn(gürültü azaltma) + loudnorm(−16 LUFS)
• Sessizlik analizi KALDIRILDI — ses kesilip atlamıyor, temiz devam ediyor
• Birebir senkron: slayt başına ayrı MP4 segment (video+ses birlikte encode)
• YENİ v13: Slayt içeriği bantların DIŞINDA — başlıklar/içerik tam görünür
  - Üst bant: 0..TOP_BAR px
  - Alt bant: (H-BOT_BAR)..H px
  - Slayt alanı: TOP_BAR..(H-BOT_BAR) — slayt buraya tam sığdırılır, kesinlikle kesilmez
• Letterbox/pillarbox: slayt orijinal en-boy oranı korunur, bantlar dışında
• Slayt görüntüsüne 'Eczacı Elif Aracıoğlu' yazılmaz — sadece overlay'de
"""
import streamlit as st
import io, os, math, base64, tempfile, subprocess, shutil, json, time
import numpy as np

# ── ffmpeg ────────────────────────────────────────────────────────────────────
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

LO_BIN  = "/usr/bin/libreoffice" if os.path.exists("/usr/bin/libreoffice") else "/usr/bin/soffice"
LO_OK   = os.path.exists(LO_BIN)
PPM_OK  = os.path.exists("/usr/bin/pdftoppm")
FFMPEG_OK = FFMPEG is not None

# ── Video boyutları ────────────────────────────────────────────────────────────
VIDEO_W   = 1280
VIDEO_H   = 720
VIDEO_FPS = 24

# ── Overlay bantları — slayt BUNLARIN DIŞINDA kalır ───────────────────────────
TOP_BAR = 58   # üst bant yüksekliği (piksel)
BOT_BAR = 48   # alt bant yüksekliği (piksel)

# Slayt için kullanılabilir alan
SLIDE_AREA_H = VIDEO_H - TOP_BAR - BOT_BAR  # 614 px
SLIDE_AREA_W = VIDEO_W                       # 1280 px

BRAND_RGB = (52, 168, 131)
BRAND_HEX = "34A883"

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
]

PALETTE = [
    {"hex": BRAND_HEX, "rgb": BRAND_RGB,      "emoji": "💊"},
    {"hex": "4C9FCA",  "rgb": ( 76,159,202),  "emoji": "👩‍💼"},
    {"hex": "C9A84C",  "rgb": (201,168, 76),  "emoji": "🎤"},
    {"hex": "E07B7B",  "rgb": (195, 90, 90),  "emoji": "🎙️"},
    {"hex": "B57FCC",  "rgb": (155,105,195),  "emoji": "💬"},
    {"hex": "7EC8C8",  "rgb": ( 80,178,178),  "emoji": "📢"},
    {"hex": "F0A060",  "rgb": (220,140, 70),  "emoji": "🗣️"},
    {"hex": "88BBEE",  "rgb": (100,160,220),  "emoji": "👤"},
]

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
            snippet = result.stderr[-800:] if result.stderr else "(çıktı yok)"
            raise RuntimeError(
                f"[{step_name}] Komut başarısız (kod {result.returncode}):\n"
                f"CMD: {' '.join(str(c) for c in cmd)}\n"
                f"STDERR: {snippet}"
            )
        return result
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"[{step_name}] Zaman aşımı — {timeout}s doldu.\n"
            f"CMD: {' '.join(str(c) for c in cmd)}"
        )

def _ffprobe_path():
    if FFMPEG:
        fp = FFMPEG.replace("ffmpeg", "ffprobe")
        if os.path.exists(fp):
            return fp
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
# SES TEMİZLEME FİLTRE ZİNCİRİ
# ═════════════════════════════════════════════════════════════════════════════
CLEAN_AF = (
    "highpass=f=80,"
    "afftdn=nf=-20,"
    "loudnorm=I=-16:LRA=11:TP=-1.5,"
    "aresample=async=1:min_hard_comp=0.1:first_pts=0"
)

def clean_audio(inp: str, out: str, step: str = "Ses temizleme"):
    _run(
        [FFMPEG, "-y", "-i", inp,
         "-af", CLEAN_AF,
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         out],
        timeout=180, step_name=step,
    )

# ═════════════════════════════════════════════════════════════════════════════
# PPTX → GÖRÜNTÜLER
# ─────────────────────────────────────────────────────────────────────────────
# YENİ MANTIK: Slayt görüntüsü, bantların dışındaki alana (SLIDE_AREA_W x SLIDE_AREA_H)
# sığdırılır. Bant alanlarına kesinlikle taşmaz — başlıklar tam görünür.
# ═════════════════════════════════════════════════════════════════════════════
def pptx_to_images(pptx_bytes: bytes) -> list:
    tmp = tempfile.mkdtemp(prefix="pptx2img_")
    try:
        pptx_path = os.path.join(tmp, "presentation.pptx")
        with open(pptx_path, "wb") as f:
            f.write(pptx_bytes)
        try:
            _run([LO_BIN, "--headless", "--convert-to", "pdf",
                  "--outdir", tmp, pptx_path],
                 timeout=180, step_name="LibreOffice PDF dönüşümü")
        except RuntimeError as e:
            raise RuntimeError(
                f"LibreOffice PDF dönüşümü başarısız.\n"
                f"packages.txt içinde 'libreoffice' var mı?\n\n{e}"
            )
        pdfs = [f for f in os.listdir(tmp) if f.endswith(".pdf")]
        if not pdfs:
            raise RuntimeError("LibreOffice çalıştı ama PDF üretmedi.")
        pdf_path = os.path.join(tmp, pdfs[0])
        img_prefix = os.path.join(tmp, "slide")
        try:
            _run(["pdftoppm", "-jpeg", "-r", "192", pdf_path, img_prefix],
                 timeout=120, step_name="pdftoppm görüntü üretimi")
        except RuntimeError as e:
            raise RuntimeError(
                f"pdftoppm başarısız.\npackages.txt içinde 'poppler-utils' var mı?\n\n{e}"
            )
        files = sorted([
            os.path.join(tmp, f) for f in os.listdir(tmp)
            if f.startswith("slide") and (f.endswith(".jpg") or f.endswith(".jpeg"))
        ])
        if not files:
            raise RuntimeError("pdftoppm çalıştı ama görüntü üretmedi.")

        images = []
        for p in files:
            src = Image.open(p).convert("RGB")
            sw, sh = src.size

            # ── Tam video canvas ─────────────────────────────────────────────
            canvas = Image.new("RGB", (VIDEO_W, VIDEO_H), (6, 10, 8))

            # Slayt yalnızca ORTA alana (bantlar dışına) sığdırılır
            # SLIDE_AREA_W x SLIDE_AREA_H = 1280 x 614
            scale = min(SLIDE_AREA_W / sw, SLIDE_AREA_H / sh)
            nw, nh = int(sw * scale), int(sh * scale)

            # Orta alana ortalanmış paste pozisyonu
            paste_x = (SLIDE_AREA_W - nw) // 2          # yatay ortalama
            paste_y = TOP_BAR + (SLIDE_AREA_H - nh) // 2  # üst bant altından başlayıp ortalanır

            canvas.paste(src.resize((nw, nh), Image.LANCZOS), (paste_x, paste_y))
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

# ═════════════════════════════════════════════════════════════════════════════
# SES HAZIRLAMA — v14 KÖK SENKRON ÇÖZÜMÜ
# ─────────────────────────────────────────────────────────────────────────────
# SORUN: Ses önce ayrı dosyalara bölünüyor, sonra video o dosyalara
#   uyduruluyor. AAC encoder delay + timestamp birikimi → senkron kayıyor.
#
# ÇÖZÜM: Global modda ses HİÇ bölünmüyor.
#   _encode_slide_segment, her segment için ffmpeg'e -ss (seek) ve -t (süre)
#   parametresiyle DOĞRUDAN ana ses dosyasını okur.
#   Seek noktası = kullanıcının girdiği kümülatif sürelerden hesaplanır.
#   Video süresi = kullanıcının girdiği süre.
#   Ses süresi  = aynı değer (-t ile kesilir).
#   → Video frame sayısı ve ses süresi matematiksel olarak eşit → senkron
#     kayması MÜMKÜN DEĞİL.
#
# Dönüş: (audio_paths, seek_starts, dur_list)
#   audio_paths : ses dosyası yolu (global modda hepsi aynı dosya)
#   seek_starts : ffmpeg -ss değeri (global: kümülatif, slayt: 0.0)
#   dur_list    : her slaytın video ve ses süresi (saniye) — birebir eşit
# ═════════════════════════════════════════════════════════════════════════════
def prepare_audio_segments(
    slide_audio_map: dict,
    durations: dict,
    n_slides: int,
    global_audio: bytes | None,
    use_global: bool,
    work_dir: str,
) -> tuple[list, list, list]:
    audio_paths, seek_starts, dur_list = [], [], []

    if use_global and global_audio:
        # 1. Ham sesi diske yaz
        raw_g = os.path.join(work_dir, "global_raw.audio")
        with open(raw_g, "wb") as f:
            f.write(global_audio)

        # 2. Tek seferlik temizle
        clean_g = os.path.join(work_dir, "global_clean.aac")
        clean_audio(raw_g, clean_g, step="Global ses temizleme (highpass+afftdn+loudnorm)")
        total_audio_dur = audio_duration_ffprobe(clean_g)

        # 3. Ses süresini EŞIT böl — kullanıcı girişi görmezden geliniyor
        #
        # NEDEN: Kullanıcının girdiği süreler toplamı ses süresinden
        # farklı olduğunda ölçekleme hatası oluşuyor.
        # En güvenli yol: total_audio_dur / n_slides → her slayt eşit.
        # Video süresi = ses süresi = matematiksel kesinlik.
        per_slide = total_audio_dur / max(n_slides, 1)

        acc = 0.0
        for i in range(n_slides):
            audio_paths.append(clean_g)
            seek_starts.append(acc)
            dur_list.append(per_slide)
            acc += per_slide

    else:
        # Slayt bazlı mod: her ses ayrı temizlenir, seek=0
        for i in range(n_slides):
            ab = slide_audio_map.get(i)
            if ab:
                raw   = os.path.join(work_dir, f"raw_{i:04d}.audio")
                clean = os.path.join(work_dir, f"seg_{i:04d}.aac")
                with open(raw, "wb") as f:
                    f.write(ab)
                try:
                    clean_audio(raw, clean, step=f"Slayt {i+1} ses temizleme")
                    real_dur = audio_duration_ffprobe(clean)
                    audio_paths.append(clean)
                    seek_starts.append(0.0)
                    dur_list.append(real_dur)
                except Exception:
                    audio_paths.append(None)
                    seek_starts.append(0.0)
                    dur_list.append(durations.get(i, 3.0))
            else:
                audio_paths.append(None)
                seek_starts.append(0.0)
                dur_list.append(durations.get(i, 3.0))

    return audio_paths, seek_starts, dur_list

# ═════════════════════════════════════════════════════════════════════════════
# KARE RENDER — v13
# ─────────────────────────────────────────────────────────────────────────────
# Slayt canvas zaten bantların dışında oluşturuldu (pptx_to_images içinde).
# Burası sadece üst ve alt bantları çizer — slayt içeriğine DOKUNMAZ.
#
# Üst bant: [0 .. TOP_BAR]   → program adı + konuşmacı + canlı göstergesi
# Alt bant: [(H-BOT_BAR) .. H] → slayt no + ilerleme çubuğu + ses dalgası
#
# Slayt alanı: [TOP_BAR .. (H-BOT_BAR)] — bu bölgeye HİÇBİR ŞEY çizilmez.
# ═════════════════════════════════════════════════════════════════════════════
def _draw_speaker_dot(draw, x, y, r, color):
    """Emoji yerine renkli dolu daire — font bağımlılığı yok."""
    draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

def _draw_pill(draw, x, y, w, h, color, alpha=60):
    """Arka plan hap şekli."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=h // 2,
                            fill=(*color, alpha))

def render_frame(slide_img, slide_idx, total, t, speaker: dict, has_audio: bool):
    frame = slide_img.copy()
    draw  = ImageDraw.Draw(frame, "RGBA")
    wi, hi = frame.size
    color = speaker.get("rgb", BRAND_RGB)
    name  = speaker.get("name", "Elif Aracıoğlu")
    role  = speaker.get("role", "Eczacı")
    # emoji artık kullanılmıyor — renkli daire kullanıyoruz

    fn18 = _font(18)
    fn13 = _font(13)
    fn11 = _font(11)

    # ── ÜST BANT [0 .. TOP_BAR] ───────────────────────────────────────────────
    draw.rectangle([0, 0, wi, TOP_BAR], fill=(4, 8, 6, 255))
    draw.rectangle([0, TOP_BAR - 2, wi, TOP_BAR], fill=(*color, 255))

    # Sol: program adı
    draw.text((16, 8),  "3 SORU",   font=fn18, fill=(*color, 255))
    draw.text((16, 32), "3 DAKiKA", font=fn11, fill=(*color, 170))

    # Dikey ayraç
    draw.rectangle([108, 10, 110, TOP_BAR - 8], fill=(*color, 50))

    # Konuşmacı — renkli daire + isim + rol (emoji YOK)
    dot_cx = 122
    dot_cy = TOP_BAR // 2
    _draw_speaker_dot(draw, dot_cx, dot_cy, 6, color)
    draw.text((dot_cx + 12, dot_cy - 7),
              f"{name}  |  {role}",
              font=fn13, fill=(195, 235, 215, 220))

    # CANLI — animasyonlu kırmızı daire + yazı
    da  = int(175 + 80 * math.sin(t * math.pi * 4))
    cx  = wi // 2 + 80
    draw.ellipse([cx - 6, dot_cy - 6, cx + 6, dot_cy + 6],
                 fill=(210, 55, 55, da))
    draw.text((cx + 12, dot_cy - 7), "CANLI",
              font=fn11, fill=(210, 55, 55, 210))

    # Sağ: marka — renkli daire + metin (emoji YOK)
    brand_text = "Eczaci Elif Aracıoglu"
    try:
        btw = draw.textlength(brand_text, font=fn11)
    except Exception:
        btw = len(brand_text) * 6
    bx = wi - int(btw) - 28
    _draw_speaker_dot(draw, bx - 8, dot_cy, 5, color)
    draw.text((bx, dot_cy - 7), brand_text,
              font=fn11, fill=(*color, 145))

    # ── ALT BANT [(H-BOT_BAR) .. H] ───────────────────────────────────────────
    bot_y = hi - BOT_BAR
    draw.rectangle([0, bot_y, wi, hi], fill=(4, 8, 6, 255))
    draw.rectangle([0, bot_y, wi, bot_y + 2], fill=(*color, 255))

    # Sol: slayt numarası
    draw.text((16, bot_y + (BOT_BAR - 14) // 2),
              f"Slayt {slide_idx + 1}  /  {total}",
              font=fn13, fill=(140, 205, 175, 210))

    # Orta: program adı
    mid_text = "3 Soru  |  3 Dakika"
    try:
        mw = draw.textlength(mid_text, font=fn11)
    except Exception:
        mw = len(mid_text) * 6
    draw.text((wi // 2 - int(mw) // 2, bot_y + (BOT_BAR - 12) // 2),
              mid_text, font=fn11, fill=(*color, 90))

    # İlerleme çubuğu
    pw = int(wi * (slide_idx + t) / max(total, 1))
    draw.rectangle([0, hi - 5, wi, hi], fill=(8, 14, 11, 255))
    draw.rectangle([0, hi - 5, pw, hi], fill=(*color, 255))

    # Ses dalgası (sağ alt)
    if has_audio:
        bc, bw2, bg = 9, 4, 4
        bx0 = wi - bc * (bw2 + bg) - 16
        by  = hi - 8
        for bi in range(bc):
            bh  = int(3 + 14 * abs(math.sin(t * math.pi * 4.2 + bi * 0.95)))
            bx2 = bx0 + bi * (bw2 + bg)
            draw.rounded_rectangle([bx2, by - bh, bx2 + bw2, by],
                                   radius=2, fill=(*color, 255))

    # RGBA → RGB
    return np.array(frame.convert("RGB"))

# ═════════════════════════════════════════════════════════════════════════════
# BİREBİR SENKRON VİDEO — Slayt başına ayrı MP4 → concat
# ═════════════════════════════════════════════════════════════════════════════
def _make_silence_aac(work_dir: str, idx: int, dur: float) -> str:
    path = os.path.join(work_dir, f"sil_{idx:04d}.aac")
    _run(
        [FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
         "-t", f"{dur:.6f}", "-c:a", "aac", "-b:a", "128k",
         "-ar", "44100", "-ac", "2", path],
        timeout=30, step_name=f"Sessizlik {idx}",
    )
    return path

def _encode_slide_segment(
    img, slide_idx: int, total: int,
    audio_path, seek_start: float, dur: float,
    speaker: dict, work_dir: str, seg_idx: int,
) -> str:
    # ── SENKRON YAKLAŞIMI v15 ─────────────────────────────────────────────
    # Video süresi = SES SÜRESİ (dur), kesinlikle başka hiçbir şeyden değil.
    #
    # Adım 1: Ses segmentini ana dosyadan kes → ayrı .aac dosyası
    #         Bu dosyanın gerçek süresini ffprobe ile ölç → real_dur
    # Adım 2: real_dur kadar video frame üret (nf = round(real_dur * FPS))
    # Adım 3: Video + ses mux (-shortest YOK, süreler zaten eşit)
    #
    # Neden Adım 1 ayrı dosya? -ss ile pipe+audio aynı anda kullanınca
    # ffmpeg timestamp hizalama sorunu yaşıyor. Ses önceden kesilince
    # hem süre garantili hem timestamp sıfırlanmış oluyor.
    # ─────────────────────────────────────────────────────────────────────
    has_audio = audio_path is not None and os.path.exists(audio_path)
    raw_vid   = os.path.join(work_dir, f"vid_{seg_idx:04d}.mp4")
    seg_path  = os.path.join(work_dir, f"chunk_{seg_idx:04d}.mp4")

    # ── ADIM 1: Ses segmentini kes, gerçek süreyi ölç ─────────────────────
    if has_audio:
        seg_audio = os.path.join(work_dir, f"aud_{seg_idx:04d}.aac")
        _run(
            [FFMPEG, "-y",
             "-ss", f"{seek_start:.6f}",
             "-t",  f"{dur:.6f}",
             "-i",  audio_path,
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
             "-af", "aresample=async=1:min_hard_comp=0.1:first_pts=0",
             seg_audio],
            timeout=60, step_name=f"Ses kes seg {seg_idx}",
        )
        real_dur = audio_duration_ffprobe(seg_audio)
    else:
        seg_audio = _make_silence_aac(work_dir, seg_idx, dur)
        real_dur  = dur

    # ── ADIM 2: Video karelerini ses süresiyle üret ────────────────────────
    # nf tamamen real_dur'dan türüyor — başka hiçbir kaynaktan değil
    nf = max(1, round(real_dur * VIDEO_FPS))

    cmd_vid = [
        FFMPEG, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{VIDEO_W}x{VIDEO_H}", "-pix_fmt", "rgb24",
        "-r", str(VIDEO_FPS), "-i", "pipe:0",
        "-vcodec", "libx264", "-crf", "22", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-r", str(VIDEO_FPS), "-vsync", "cfr",
        "-an",
        raw_vid,
    ]
    try:
        proc = subprocess.Popen(cmd_vid, stdin=subprocess.PIPE,
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
            raise RuntimeError(f"Video encode başarısız (segment {seg_idx})")
    except Exception as e:
        proc.kill()
        raise RuntimeError(f"[Video adım2 seg {seg_idx}] {e}")

    # ── ADIM 3: Mux — video + ses ─────────────────────────────────────────
    # Video süresi = nf/FPS, ses süresi = real_dur → matematiksel olarak eşit
    # -shortest KULLANILMIYOR: ikisi zaten eşit, -shortest kullanmak
    # bazen 1 frame eksik kesebiliyor
    _run(
        [FFMPEG, "-y",
         "-i", raw_vid,
         "-i", seg_audio,
         "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "copy",
         "-c:a", "copy",
         "-movflags", "+faststart",
         seg_path],
        timeout=120, step_name=f"Mux seg {seg_idx}",
    )

    # Geçici dosyaları temizle
    for tmp in [raw_vid, seg_audio]:
        try:
            os.unlink(tmp)
        except Exception:
            pass

    return seg_path

def build_video(
    slide_images: list,
    audio_paths: list,
    seek_starts: list,
    durations: list,
    speakers: list,
    work_dir: str,
    cb=None,
) -> bytes:
    if not FFMPEG or not os.path.exists(FFMPEG):
        raise RuntimeError(
            "ffmpeg bulunamadı!\n\n"
            "requirements.txt → imageio[ffmpeg]\n"
            "packages.txt    → ffmpeg\n\n"
            f"Aranan yol: {FFMPEG!r}"
        )
    n       = len(slide_images)
    tmp_out = os.path.join(work_dir, "output.mp4")
    segs    = []

    for idx, (img, aud_path, seek, dur, spk) in enumerate(
            zip(slide_images, audio_paths, seek_starts, durations, speakers)):
        if cb:
            cb(0.05 + 0.82 * (idx / n),
               f"Slayt {idx+1}/{n} encode ediliyor… seek={seek:.1f}s dur={dur:.1f}s")
        segs.append(_encode_slide_segment(
            img, idx, n, aud_path, seek, dur, spk, work_dir, idx))

    if cb:
        cb(0.90, f"{n} segment birleştiriliyor…")
    concat_list = os.path.join(work_dir, "concat.txt")
    with open(concat_list, "w") as f:
        for p in segs:
            f.write(f"file '{p}'\n")
    _run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c", "copy", "-vsync", "vfr", "-movflags", "+faststart", tmp_out],
        timeout=600, step_name="Final concat (stream copy)",
    )
    if cb:
        cb(1.0, "Tamamlandı! ✅")
    if os.path.exists(tmp_out):
        with open(tmp_out, "rb") as f:
            return f.read()
    raise RuntimeError("Çıktı MP4 oluşturulamadı.")

# ═════════════════════════════════════════════════════════════════════════════
# CSS — Eczacı yeşili #34A883 · Cormorant Garamond + DM Sans
# ═════════════════════════════════════════════════════════════════════════════
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400;1,600&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');
:root{
  --g:#34A883;--gd:rgba(52,168,131,.15);--gg:rgba(52,168,131,.055);
  --gl:rgba(52,168,131,.32);
  --bg:#060d0a;--sf:rgba(255,255,255,.024);--br:rgba(255,255,255,.065);
  --tx:#ddeee8;--mu:#42665a;--mu2:#2a4038;
}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;background:var(--bg);}
.stApp{
  background:
    radial-gradient(ellipse 75% 50% at 5%  5%, rgba(52,168,131,.06) 0%,transparent 55%),
    radial-gradient(ellipse 55% 45% at 95% 95%,rgba(52,168,131,.04) 0%,transparent 55%),
    var(--bg);
  color:var(--tx);
}
section[data-testid="stSidebar"]{
  background:rgba(4,9,7,.98);border-right:1px solid var(--gd);
}
.hero{
  position:relative;overflow:hidden;padding:3rem 1rem 1.8rem;
  border-bottom:1px solid var(--gd);margin-bottom:1.8rem;text-align:center;
}
.hero::before{
  content:'';position:absolute;inset:0;pointer-events:none;
  background:radial-gradient(ellipse 65% 100% at 50% -5%,rgba(52,168,131,.07),transparent 60%);
}
.hero-pill{
  display:inline-flex;align-items:center;gap:.4rem;padding:.24rem .85rem;
  border-radius:50px;background:var(--gg);border:1px solid var(--gl);
  font-size:.62rem;letter-spacing:.22em;text-transform:uppercase;
  color:var(--g);margin-bottom:1.1rem;font-weight:600;
}
.hero h1{
  font-family:'Cormorant Garamond',serif;
  font-size:3.2rem;font-weight:700;line-height:1.05;
  color:#e8f5ef;margin:0 0 .15rem;letter-spacing:-.02em;
}
.hero h1 em{font-style:italic;font-weight:400;color:var(--g);}
.hero-author{
  font-size:.72rem;letter-spacing:.22em;text-transform:uppercase;
  color:var(--mu);margin-top:.65rem;
}
.hero-author strong{color:var(--g);font-weight:600;letter-spacing:.18em;}
.hero-rule{
  width:52px;height:1px;margin:1rem auto 0;
  background:linear-gradient(90deg,transparent,var(--g),transparent);
}
.lbl{
  font-size:.58rem;letter-spacing:.24em;text-transform:uppercase;
  color:var(--mu);margin:.9rem 0 .45rem;
  padding-left:.55rem;border-left:2px solid var(--g);
}
.srow{
  display:flex;gap:.9rem;flex-wrap:wrap;padding:.55rem 1rem;margin:.5rem 0;
  background:var(--gg);border:1px solid var(--gd);border-radius:10px;
  font-size:.78rem;color:var(--mu);align-items:center;
}
.srow strong{color:var(--g);}
.char-card{
  display:flex;align-items:center;gap:.8rem;padding:.65rem 1rem;margin:.32rem 0;
  background:var(--sf);border:1px solid var(--br);border-radius:11px;
}
.char-dot{width:11px;height:11px;border-radius:50%;flex-shrink:0;}
.char-name{font-size:.88rem;font-weight:600;color:#c8e8d8;}
.char-role{font-size:.7rem;color:var(--mu);margin-left:auto;}
.sl-card{
  padding:.6rem .9rem;margin:.26rem 0;background:var(--sf);
  border:1px solid var(--br);border-radius:9px;border-left:3px solid;
}
.sl-num{font-size:.63rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.18rem;}
.sl-note{font-size:.78rem;color:#5a8070;line-height:1.5;font-style:italic;}
.badge{display:inline-flex;align-items:center;gap:.28rem;
  padding:.18rem .55rem;border-radius:50px;font-size:.65rem;font-weight:700;}
.badge-gold{background:rgba(52,168,131,.1);color:var(--g);border:1px solid rgba(52,168,131,.22);}
.dep{font-size:.72rem;margin:.1rem 0;line-height:1.55;}
.ok{color:#55c98a;}.er{color:#d97070;}
.ffmpeg-warn{
  padding:.8rem 1rem;margin:.6rem 0;border-radius:10px;
  background:rgba(217,112,112,.07);border:1px solid rgba(217,112,112,.22);
  font-size:.78rem;color:#d97070;line-height:1.6;
}
.ffmpeg-warn code{background:rgba(255,255,255,.07);padding:.1rem .3rem;border-radius:4px;font-size:.73rem;}
.audio-info{
  padding:.5rem .85rem;margin:.4rem 0;
  background:rgba(52,168,131,.05);border:1px solid rgba(52,168,131,.14);
  border-radius:8px;font-size:.72rem;color:var(--mu);line-height:1.6;
}
.audio-info strong{color:var(--g);}
/* YENİ: Slayt tam görünür uyarı kutusu */
.slide-info{
  padding:.6rem 1rem;margin:.5rem 0;border-radius:8px;
  background:rgba(52,168,131,.08);border:1px solid rgba(52,168,131,.25);
  font-size:.75rem;color:#7cc8a8;line-height:1.6;
}
.slide-info strong{color:var(--g);}
.dl-alt{
  display:block;text-align:center;padding:9px 14px;margin-top:8px;
  background:rgba(52,168,131,.07);border:1px solid rgba(52,168,131,.2);
  color:var(--g);border-radius:9px;font-weight:600;font-size:.8rem;
  text-decoration:none;
}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#289970,#3ec49a)!important;
  color:#030a07!important;font-weight:700!important;border:none!important;letter-spacing:.04em;
}
.stButton>button[kind="primary"]:hover{
  filter:brightness(1.07);transform:translateY(-1px);
  box-shadow:0 4px 22px rgba(52,168,131,.3)!important;
}
.stProgress>div>div{border-radius:10px;}
.sb-brand{
  text-align:center;padding:1.15rem 0 .9rem;
  border-bottom:1px solid var(--gd);margin-bottom:1rem;
}
.sb-title{
  font-family:'Cormorant Garamond',serif;
  font-size:1.25rem;font-weight:700;color:#e0f0e8;letter-spacing:-.01em;
}
.sb-title em{font-style:italic;font-weight:400;color:var(--g);}
.sb-name{font-size:.61rem;color:var(--mu);letter-spacing:.2em;text-transform:uppercase;margin-top:.35rem;}
.sb-name strong{color:var(--g);font-weight:600;}
audio{width:100%;border-radius:8px;margin:3px 0;}
hr{border-color:var(--br);}
input[type="text"]{
  background:rgba(255,255,255,.04)!important;
  border:1px solid rgba(255,255,255,.08)!important;
  color:var(--tx)!important;border-radius:8px!important;
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
    st.caption("Elif Aracıoğlu varsayılan konuşmacıdır. İstediğiniz kadar ekleyip çıkarabilirsiniz.")
    to_delete = None
    for i, ch in enumerate(chars):
        is_default = (i == 0)
        with st.container():
            c1, c2, c3, c4 = st.columns([2.5, 2, 1.2, 0.7])
            with c1:
                new_name = st.text_input(
                    "İsim", value=ch["name"], key=f"ch_name_{i}",
                    label_visibility="collapsed", disabled=is_default, placeholder="İsim...")
                if not is_default:
                    chars[i]["name"] = new_name or ch["name"]
            with c2:
                new_role = st.text_input(
                    "Rol", value=ch["role"], key=f"ch_role_{i}",
                    label_visibility="collapsed", placeholder="Rol...")
                chars[i]["role"] = new_role or ch["role"]
            with c3:
                emojis = ["💊","🎤","👩‍💼","🎧","🎙️","💬","📢","🗣️","👤","🎵"]
                cur_e  = ch.get("emoji", "💊")
                sel_e  = st.selectbox(
                    "Emoji", emojis,
                    index=emojis.index(cur_e) if cur_e in emojis else 0,
                    key=f"ch_emoji_{i}", label_visibility="collapsed")
                chars[i]["emoji"] = sel_e
            with c4:
                if is_default:
                    st.markdown('<span class="badge badge-gold">Varsayılan</span>',
                                unsafe_allow_html=True)
                else:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✕", key=f"ch_del_{i}",
                                 help=f"{ch['name']} sil", use_container_width=True):
                        to_delete = i
            st.markdown(
                f'<div class="char-card" style="margin-top:-6px;padding:.4rem .9rem;">'
                f'<div class="char-dot" style="background:#{ch["hex"]};"></div>'
                f'<span class="char-name">{ch["emoji"]}  {chars[i]["name"]}</span>'
                f'<span class="char-role">{chars[i]["role"]}</span></div>',
                unsafe_allow_html=True)
    if to_delete is not None:
        chars.pop(to_delete)
        new_map = {}
        for k, v in st.session_state.ss_slide_speaker.items():
            new_map[k] = v if v < to_delete else max(0, v - 1)
        st.session_state.ss_slide_speaker = new_map
        st.rerun()
    st.markdown("---")
    with st.expander("➕ Yeni Konuşmacı Ekle", expanded=False):
        c_n, c_r, c_add = st.columns([2, 2, 1])
        with c_n:
            nn = st.text_input("İsim", key="wu_new_name", placeholder="Örn: Ecem")
        with c_r:
            nr = st.text_input("Rol",  key="wu_new_role", placeholder="Örn: Konuk")
        with c_add:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Ekle ➕", use_container_width=True, key="wu_add_char"):
                if nn.strip():
                    chars.append({**PALETTE[len(chars) % len(PALETTE)],
                                  "name": nn.strip(), "role": nr.strip() or "Konuşmacı"})
                    st.rerun()
                else:
                    st.warning("İsim boş olamaz.")
    st.session_state.ss_characters = chars
    return chars

# ═════════════════════════════════════════════════════════════════════════════
# SES ATAMA
# ═════════════════════════════════════════════════════════════════════════════
def audio_assignment_ui(n_slides: int, chars: list):
    mode = st.radio(
        "Ses Modu",
        ["🔊 Tek ses — tüm sunuma", "🎙️ Her slayta ayrı ses"],
        key="wu_mode_radio", horizontal=True, label_visibility="collapsed",
    )
    use_global = mode.startswith("🔊")
    st.session_state.ss_use_global = use_global

    st.markdown(
        '<div class="audio-info">'
        '🧹 <strong>Otomatik ses temizleme:</strong> '
        'Alçak frekans gürültüsü (highpass 80 Hz), arka plan sesi (afftdn −20 dB) '
        've ses seviyesi dengeleme (loudnorm −16 LUFS) uygulanır. '
        'Seste atlama olmaz — temiz, kesintisiz ses.'
        '</div>',
        unsafe_allow_html=True,
    )

    if use_global:
        st.caption(
            "**Tek ses modu:** Ses önce temizlenir, ardından slayt sayısına eşit bölünür. "
            "Sessizlik analizi yapılmaz — cümle ortası kesilmez."
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
                # Sadece henüz ayarlanmamış (0 veya çok küçük) slaytlara varsayılan yaz
                for i in range(n_slides):
                    if st.session_state.ss_durations.get(i, 0.0) <= 0.5:
                        st.session_state.ss_durations[i] = per_slide
                st.audio(ab, format="audio/mp3")
                cur_weights = [st.session_state.ss_durations.get(i, per_slide) for i in range(n_slides)]
                cur_total   = sum(cur_weights)
                st.caption(
                    f"Toplam ses ~{total_dur:.1f} sn  ·  "
                    f"Slayt süre toplamı: {cur_total:.1f} sn  ·  "
                    f"Ses, ayarlanan sürelere orantılı bölünür"
                )
        with col_g2:
            st.markdown('<p class="lbl">Tüm Slaytlar — Konuşmacı</p>', unsafe_allow_html=True)
            char_names = [f'{c["emoji"]} {c["name"]}' for c in chars]
            sel = st.selectbox(
                "Konuşmacı", char_names, index=0,
                key="wu_global_speaker", label_visibility="collapsed",
            )
            sel_idx = char_names.index(sel)
            for i in range(n_slides):
                st.session_state.ss_slide_speaker[i] = sel_idx
    else:
        st.caption(
            "**Slayt bazlı mod:** Her slayta farklı ses ve konuşmacı atayabilirsiniz. "
            "Her ses ayrı ayrı temizlenir. Ses yüklenmeyen slaytlara sessizlik eklenir."
        )
        char_names = [f'{c["emoji"]} {c["name"]}' for c in chars]
        notes = st.session_state.ss_slide_notes
        cqa1, cqa2 = st.columns([3, 1])
        with cqa1:
            qs = st.selectbox("Tüm slaytlara ata:", char_names, index=0, key="wu_quick_speaker")
        with cqa2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Tümüne Uygula", key="wu_quick_apply", use_container_width=True):
                qi = char_names.index(qs)
                for i in range(n_slides):
                    st.session_state.ss_slide_speaker[i] = qi
                st.rerun()
        st.markdown("---")
        for i in range(n_slides):
            note_preview = (notes[i][:80]+"…") if i < len(notes) and len(notes[i])>80 \
                else (notes[i] if i < len(notes) else "")
            ci = min(st.session_state.ss_slide_speaker.get(i, 0), len(chars)-1)
            sc = f'#{chars[ci]["hex"]}'
            st.markdown(
                f'<div class="sl-card" style="border-left-color:{sc};">'
                f'<div class="sl-num" style="color:{sc};">'
                f'Slayt {i+1}  ·  {chars[ci]["emoji"]} {chars[ci]["name"]}</div>'
                f'<div class="sl-note">{note_preview or "—"}</div></div>',
                unsafe_allow_html=True)
            sc1, sc2, sc3 = st.columns([1.5, 2.5, 0.5])
            with sc1:
                sel = st.selectbox(f"Konuşmacı S{i+1}", char_names,
                                   index=ci, key=f"wu_spk_{i}", label_visibility="collapsed")
                st.session_state.ss_slide_speaker[i] = char_names.index(sel)
            with sc2:
                uf = st.file_uploader(f"Ses S{i+1}", type=["mp3","wav","m4a","ogg"],
                                      key=f"wu_sl_{i}", label_visibility="collapsed")
                if uf is not None:
                    ab = uf.read()
                    st.session_state.ss_slide_audio[i] = ab
                    dur = audio_duration_sec_bytes(ab)
                    st.session_state.ss_durations[i] = dur
                    st.audio(ab, format="audio/mp3")
            with sc3:
                dv   = st.session_state.ss_durations.get(i, 3.0)
                icon = "🔊" if i in st.session_state.ss_slide_audio else "🔇"
                st.caption(f"{icon} {dv:.1f}s")

    with st.expander("⚙️ Slayt sürelerini manuel ayarla (opsiyonel)", expanded=False):
        per_row   = min(n_slides, 5)
        dur_grids = [st.columns(per_row) for _ in range(-(-n_slides // per_row))]
        for i in range(n_slides):
            r, c = i // per_row, i % per_row
            with dur_grids[r][c]:
                d = st.number_input(
                    f"S{i+1} (sn)", min_value=0.5, max_value=300.0,
                    value=float(st.session_state.ss_durations.get(i, 3.0)),
                    step=0.5, key=f"wu_dur_{i}")
                st.session_state.ss_durations[i] = d
    return use_global

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════
def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="sb-brand">'
            '<div class="sb-title">3 <em>Soru</em> 3 Dakika</div>'
            '<div class="sb-name">Eczacı <strong>Elif Aracıoğlu</strong></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
        character_manager_ui()
        st.markdown("---")
        st.markdown('<p class="lbl">Sistem Durumu</p>', unsafe_allow_html=True)
        ffmpeg_hint  = "requirements.txt: imageio[ffmpeg]  VEYA  packages.txt: ffmpeg"
        ffmpeg_label = "ffmpeg"
        if FFMPEG_OK:
            ffmpeg_label = (f"ffmpeg <span style='color:#2a4038;font-size:.6rem;'>"
                            f"({FFMPEG})</span>")
        checks = [
            ("Pillow",       PIL_OK,    "pip: pillow"),
            ("imageio",      IMAGEIO_OK,"pip: imageio[ffmpeg]"),
            ("python-pptx",  PPTX_OK,   "pip: python-pptx"),
            ("LibreOffice",  LO_OK,     "packages.txt: libreoffice"),
            ("pdftoppm",     PPM_OK,    "packages.txt: poppler-utils"),
            ("ffmpeg",       FFMPEG_OK, ffmpeg_hint),
        ]
        for name, ok, hint in checks:
            cls  = "ok" if ok else "er"
            icon = "🟢" if ok else "🔴"
            extra = f' <span style="color:#2a4038;font-size:.62rem;">— {hint}</span>' if not ok else ""
            dn = ffmpeg_label if name == "ffmpeg" else name
            st.markdown(f'<div class="dep {cls}">{icon} {dn}{extra}</div>',
                        unsafe_allow_html=True)
        if not FFMPEG_OK:
            st.markdown(
                '<div class="ffmpeg-warn">⚠️ <b>ffmpeg bulunamadı!</b><br>'
                'requirements.txt:<br><code>imageio[ffmpeg]</code><br><br>'
                'VEYA packages.txt:<br><code>ffmpeg</code></div>',
                unsafe_allow_html=True)
        if not LO_OK or not PPM_OK:
            st.markdown("---")
            st.caption("**packages.txt**:\n```\nlibreoffice\npoppler-utils\n```")
        st.markdown("---")
        chars = st.session_state.ss_characters
        st.markdown('<p class="lbl">Aktif Konuşmacılar</p>', unsafe_allow_html=True)
        for ch in chars:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:.5rem;'
                f'padding:.2rem 0;font-size:.78rem;">'
                f'<div style="width:9px;height:9px;border-radius:50%;'
                f'background:#{ch["hex"]};"></div>'
                f'<span style="color:#c8e8d8;">{ch["emoji"]} {ch["name"]}</span>'
                f'<span style="color:#2a4038;margin-left:auto;font-size:.65rem;">'
                f'{ch["role"]}</span></div>',
                unsafe_allow_html=True)
        st.markdown("---")
        # Bant bilgisi
        st.markdown(
            f'<div style="font-size:.6rem;color:#2a4038;line-height:1.7;">'
            f'📐 Video: {VIDEO_W}×{VIDEO_H} · {VIDEO_FPS}fps<br>'
            f'🟩 Slayt alanı: {SLIDE_AREA_W}×{SLIDE_AREA_H}px<br>'
            f'📌 Üst bant: {TOP_BAR}px · Alt bant: {BOT_BAR}px<br>'
            f'✅ Başlıklar tam görünür — bant dışı'
            f'</div>',
            unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(
            '<div style="font-size:.6rem;color:#2a4038;text-align:center;">'
            'v13.0 · Slayt Tam Görünür · Temiz Ses · Birebir Senkron</div>',
            unsafe_allow_html=True)

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
        '<div class="hero-pill">💊 Video Stüdyo</div>'
        '<h1>3 <em>Soru</em><br>3 Dakika</h1>'
        '<div class="hero-author">Eczacı &nbsp;<strong>Elif Aracıoğlu</strong></div>'
        '<div class="hero-rule"></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    chars = st.session_state.ss_characters

    # ── ADIM 1: PPTX ──────────────────────────────────────────────────────────
    st.markdown('<p class="lbl">① PowerPoint Dosyası</p>', unsafe_allow_html=True)

    # Slayt tam görünür bilgisi
    st.markdown(
        f'<div class="slide-info">'
        f'✅ <strong>v13 — Slayt içeriği bantların dışında:</strong> '
        f'Üst bant ({TOP_BAR}px) ve alt bant ({BOT_BAR}px) slayt alanının dışındadır. '
        f'Slayt görüntüsü {SLIDE_AREA_W}×{SLIDE_AREA_H}px alana tam sığdırılır — '
        f'başlıklar, metinler ve içerik kesinlikle görünür.'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        pptx_file = st.file_uploader(
            "PPTX", type=["pptx"], key="wu_pptx", label_visibility="collapsed")
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
                idx = min(st.session_state.ss_slide_speaker.get(i, 0), len(chars)-1)
                nm  = chars[idx]["name"]
                spk_counts[nm] = spk_counts.get(nm, 0) + 1
            badges = " ".join(
                f'<span class="badge badge-gold">{nm}: {cnt}</span>'
                for nm, cnt in spk_counts.items()
            )
            st.markdown(badges, unsafe_allow_html=True)
    with col_b:
        notes = st.session_state.ss_slide_notes
        if notes:
            st.markdown(
                f'<div class="srow">'
                f'<span>📊 <strong>{len(notes)}</strong> slayt</span>'
                f'<span>🎭 <strong>{len(chars)}</strong> konuşmacı</span>'
                f'<span>📐 Slayt: <strong>{SLIDE_AREA_W}×{SLIDE_AREA_H}</strong></span>'
                f'</div>',
                unsafe_allow_html=True)
            for i, note in enumerate(notes[:6]):
                si  = min(st.session_state.ss_slide_speaker.get(i, 0), len(chars)-1)
                spk = chars[si]
                prev = (note[:88]+"…") if len(note)>88 else (note or "—")
                st.markdown(
                    f'<div class="sl-card" style="border-left-color:#{spk["hex"]};">'
                    f'<div class="sl-num" style="color:#{spk["hex"]};">'
                    f'{spk["emoji"]} {spk["name"]}  ·  Slayt {i+1}</div>'
                    f'<div class="sl-note">{prev}</div></div>',
                    unsafe_allow_html=True)
            if len(notes) > 6:
                st.caption(f"… ve {len(notes)-6} slayt daha")

    st.markdown("---")

    # ── ADIM 2: SES ───────────────────────────────────────────────────────────
    st.markdown('<p class="lbl">② Ses Dosyaları & Konuşmacı Atama</p>', unsafe_allow_html=True)
    if not st.session_state.ss_slide_notes:
        st.info("Önce bir PPTX dosyası yükleyin.")
    else:
        audio_assignment_ui(len(st.session_state.ss_slide_notes), chars)

    st.markdown("---")

    # ── ADIM 3: VİDEO ─────────────────────────────────────────────────────────
    st.markdown('<p class="lbl">③ Video Oluştur</p>', unsafe_allow_html=True)
    can_go = (
        st.session_state.ss_pptx_bytes is not None
        and PIL_OK and IMAGEIO_OK and PPTX_OK and LO_OK and PPM_OK and FFMPEG_OK
    )
    if not can_go:
        if not st.session_state.ss_pptx_bytes:
            st.info("Önce PPTX dosyası yükleyin.")
        else:
            missing = [n for n, ok in [
                ("Pillow",PIL_OK),("imageio",IMAGEIO_OK),("python-pptx",PPTX_OK),
                ("libreoffice",LO_OK),("poppler-utils",PPM_OK),("ffmpeg",FFMPEG_OK)
            ] if not ok]
            st.error(f"Eksik bağımlılık: {', '.join(missing)}")
            if not FFMPEG_OK:
                st.markdown(
                    '<div class="ffmpeg-warn">🔧 <b>ffmpeg:</b><br>'
                    'requirements.txt → <code>imageio[ffmpeg]</code><br>'
                    'packages.txt → <code>ffmpeg</code></div>',
                    unsafe_allow_html=True)
    else:
        n_slides   = len(st.session_state.ss_slide_notes)
        total_secs = sum(st.session_state.ss_durations.get(i, 3.0) for i in range(n_slides))
        mins, secs = divmod(int(total_secs), 60)
        st.markdown(
            f'<div class="srow">'
            f'<span>🎞️ <strong>{n_slides}</strong> slayt</span>'
            f'<span>⏱️ ~<strong>{mins}:{secs:02d}</strong></span>'
            f'<span>📐 <strong>{VIDEO_W}×{VIDEO_H}</strong></span>'
            f'<span>🎬 <strong>{VIDEO_FPS} FPS</strong></span>'
            f'<span>🎭 <strong>{len(chars)}</strong> konuşmacı</span>'
            f'<span>🟩 Slayt: <strong>{SLIDE_AREA_W}×{SLIDE_AREA_H}</strong></span>'
            f'</div>',
            unsafe_allow_html=True)
        c1, c2 = st.columns([3, 1])
        with c1:
            make_btn = st.button(
                "🎬 Video Oluştur", type="primary",
                use_container_width=True, key="wu_btn_make",
                disabled=(st.session_state.ss_video_bytes is not None))
        with c2:
            if st.button("🔄 Sıfırla", use_container_width=True, key="wu_btn_reset"):
                st.session_state.ss_video_bytes = None
                st.rerun()

        if make_btn:
            prog = st.progress(0)
            stat = st.empty()
            t0   = time.time()

            def cb(pct, msg):
                prog.progress(min(float(pct), 1.0))
                stat.markdown(
                    f"⚙️ **{msg}** &nbsp;"
                    f'<span style="color:#2a4038;font-size:.76rem;">— {time.time()-t0:.0f}s</span>',
                    unsafe_allow_html=True)

            work_dir = tempfile.mkdtemp(prefix="3soru_")
            try:
                cb(0.02, "Slaytlar görüntüye dönüştürülüyor…")
                slide_imgs = pptx_to_images(st.session_state.ss_pptx_bytes)
                n_actual   = len(slide_imgs)
                cb(0.10, f"Ses temizleniyor ve segmentler hazırlanıyor ({n_actual} slayt)…")
                audio_paths, seek_starts, dur_list = prepare_audio_segments(
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
                    seek_starts  = seek_starts,
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

        if st.session_state.ss_video_bytes:
            vb       = st.session_state.ss_video_bytes
            size     = len(vb)
            size_str = (f"{size//(1024*1024):.1f} MB"
                        if size > 1_048_576 else f"{size//1024:,} KB")
            st.success(f"✅ Video hazır — **{size_str}**")
            st.video(vb)
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    "⬇️ MP4 İndir", data=vb,
                    file_name="elif_aracıoglu_sunum.mp4", mime="video/mp4",
                    use_container_width=True, type="primary", key="wu_dl")
            with col_d2:
                b64v = base64.b64encode(vb).decode()
                st.markdown(
                    f'<a href="data:video/mp4;base64,{b64v}" '
                    'download="elif_aracıoglu_sunum.mp4" class="dl-alt">'
                    '📥 Alternatif İndirme</a>',
                    unsafe_allow_html=True)
            imgs = st.session_state.ss_slide_images
            if imgs:
                st.markdown("---")
                st.markdown('<p class="lbl">Slayt Önizlemeleri</p>', unsafe_allow_html=True)
                pc = st.columns(min(len(imgs), 4))
                for i, img in enumerate(imgs):
                    si  = min(st.session_state.ss_slide_speaker.get(i, 0), len(chars)-1)
                    spk = chars[si]
                    with pc[i % 4]:
                        st.image(img, caption=f"{spk['emoji']} {spk['name']} — S{i+1}",
                                 use_container_width=True)

if __name__ == "__main__":
    main()
