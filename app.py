"""
🎬 3 Soru 3 Dakika — Sesli Animasyonlu Sunum + MP4 + PDF
Kendi klonlanmış sesinizle animasyonlu slaytlar, video ve PDF çıktısı.

Bağımlılıklar (pip install -r requirements.txt):
  streamlit, requests, Pillow, imageio[ffmpeg], reportlab
"""

import streamlit as st
import requests
import time
import json
import io
import os
import math
import tempfile
from typing import Optional

# ─────────────────────────────────────────────────────────
# 1. KONFİGÜRASYON  ← Buradan düzenleyin
# ─────────────────────────────────────────────────────────

CHARACTERS = {
    "Sunucu": {
        "color": "#E74C3C",
        "bg_rgb": (180, 30, 30),
        "dark_rgb": (90, 12, 12),
        "emoji": "🎤",
        "animation": "bounce",
        "svg_accent": "#ff8a80",
    },
    "Konuk": {
        "color": "#3498DB",
        "bg_rgb": (30, 100, 200),
        "dark_rgb": (10, 40, 100),
        "emoji": "👤",
        "animation": "pulse",
        "svg_accent": "#82cfff",
    },
    "Dis Ses": {
        "color": "#2ECC71",
        "bg_rgb": (30, 180, 90),
        "dark_rgb": (10, 80, 40),
        "emoji": "🎧",
        "animation": "float",
        "svg_accent": "#a8ffcb",
    },
    "Uzman": {
        "color": "#F39C12",
        "bg_rgb": (200, 130, 20),
        "dark_rgb": (90, 55, 5),
        "emoji": "👨‍🏫",
        "animation": "shake",
        "svg_accent": "#ffe082",
    },
    "Raportör": {
        "color": "#9B59B6",
        "bg_rgb": (140, 70, 180),
        "dark_rgb": (60, 20, 90),
        "emoji": "📰",
        "animation": "bounce",
        "svg_accent": "#e1bee7",
    },
    "Anlatici": {
        "color": "#1ABC9C",
        "bg_rgb": (20, 170, 140),
        "dark_rgb": (8, 80, 65),
        "emoji": "📖",
        "animation": "pulse",
        "svg_accent": "#b2dfdb",
    },
}

VOICE_IDS = {
    "Sunucu":    "KENDI_SES_ID_BURAYA",
    "Konuk":     "KENDI_SES_ID_BURAYA",
    "Dis Ses":   "KENDI_SES_ID_BURAYA",
    "Uzman":     "KENDI_SES_ID_BURAYA",
    "Raportör":  "KENDI_SES_ID_BURAYA",
    "Anlatici":  "KENDI_SES_ID_BURAYA",
}

FALLBACK_COLORS = [
    ("#FF6B6B", (220, 80, 80),  (100, 20, 20)),
    ("#4ECDC4", (60, 180, 170), (15, 80, 75)),
    ("#F7DC6F", (220, 200, 80), (100, 90, 20)),
    ("#BB8FCE", (160, 110, 190),(70, 40, 95)),
    ("#82E0AA", (100, 200, 140),(30, 90, 55)),
]

TEMPLATES = {
    "🎤 Röportaj": (
        "Sunucu: Merhaba ve podcastimize hos geldiniz! Bugun cok ozel bir konugumuz var.\n"
        "Konuk: Merhaba! Burada olmaktan gercekten mutluyum.\n"
        "Dis Ses: Bugunku konumuz yapay zekanin gelecegi.\n"
        "Sunucu: Peki, yapay zeka hayatimizi nasil degistirecek?\n"
        "Konuk: Inanilmaz gelismeler yasaniyor. On yil icinde her sey farkli olacak.\n"
        "Dis Ses: Ve simdi kisa bir ara veriyoruz.\n"
        "Sunucu: Tekrar hos geldiniz! Son sorumuz: Bize tavsiyeniz nedir?\n"
        "Konuk: Merak edin, ogreyin ve adapte olun. Bu uclu yeterli.\n"
        "Dis Ses: Bizi dinlediniz icin tesekkurler!"
    ),
    "📰 Haber": (
        "Dis Ses: 3 Soru 3 Dakika haber bultenine hos geldiniz.\n"
        "Sunucu: Bugünün one cikan gelismelerini aktariyoruz.\n"
        "Uzman: Teknoloji sektöründen carpici rakamlar aciklandi.\n"
        "Sunucu: Bu gelismeler sektoru nasil etkiliyor?\n"
        "Uzman: Donusum hizi beklentilerin cok üzerinde seyrediyor.\n"
        "Raportör: Uzmanlar onumüzdeki doneme dikkatli yaklasılmasini oneriyor.\n"
        "Dis Ses: Bultenimizin sonuna geldik. Yarin gorusmek uzere!"
    ),
    "📚 Egitim": (
        "Sunucu: Bilim dünyasina hos geldiniz!\n"
        "Dis Ses: Bu bolumde kuantum fiziginin temellerini ele alacagiz.\n"
        "Konuk: Kuantum fizigi, atom alti parcaciklarin davranisini inceler.\n"
        "Sunucu: Bu bilgi gunluk hayatimiza nasil yansiyor?\n"
        "Uzman: Akilli telefondan tibbi cihazlara kadar her yerde kuantum var.\n"
        "Konuk: Superpozisyon ilkesi en ilginc kavram. Parcacik ayni anda iki yerde olabilir.\n"
        "Anlatici: Bir sonraki bolumde kuantum dolanikligini inceleyecegiz. Takipte kalin!"
    ),
}

VIDEO_W, VIDEO_H = 1280, 720
VIDEO_FPS = 30


# ─────────────────────────────────────────────────────────
# 2. YARDIMCI
# ─────────────────────────────────────────────────────────

def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def wrap_text(text: str, max_chars: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        test = (line + " " + w).strip()
        if len(test) <= max_chars:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


# ─────────────────────────────────────────────────────────
# 3. SCRIPT PARSER
# ─────────────────────────────────────────────────────────

class ScriptParser:
    def __init__(self):
        self._dyn = {}
        self._ci  = 0

    def _info(self, name: str) -> dict:
        if name in CHARACTERS:
            return CHARACTERS[name]
        if name not in self._dyn:
            hex_c, bg, dark = FALLBACK_COLORS[self._ci % len(FALLBACK_COLORS)]
            self._dyn[name] = {
                "color": hex_c, "bg_rgb": bg, "dark_rgb": dark,
                "emoji": "🔊", "animation": "pulse", "svg_accent": "#fff",
            }
            self._ci += 1
        return self._dyn[name]

    def parse(self, script: str) -> list[dict]:
        segs, cur_char, cur_parts = [], None, []
        for raw in script.strip().split("\n"):
            line = raw.strip()
            if not line:
                continue
            if ":" in line:
                ci   = line.index(":")
                cand = line[:ci].strip()
                rest = line[ci+1:].strip()
                if 0 < len(cand) <= 35 and not any(x in cand for x in ".!?,;"):
                    if cur_char and cur_parts:
                        segs.append(self._make(cur_char, " ".join(cur_parts)))
                    cur_char, cur_parts = cand, [rest] if rest else []
                    continue
            if cur_char:
                cur_parts.append(line)
            else:
                cur_char = list(CHARACTERS.keys())[0]
                cur_parts = [line]
        if cur_char and cur_parts:
            segs.append(self._make(cur_char, " ".join(cur_parts)))
        return segs

    def _make(self, char: str, text: str) -> dict:
        return {"character": char, "text": text, "info": self._info(char)}

    @staticmethod
    def word_count(s: str) -> int:
        return len(s.split())

    @staticmethod
    def duration_str(wc: int) -> str:
        m, s = divmod(int(wc / 130 * 60), 60)
        return f"{m}:{s:02d}"


# ─────────────────────────────────────────────────────────
# 4. ELEVENLABS
# ─────────────────────────────────────────────────────────

class ElevenLabsAPI:
    BASE = "https://api.elevenlabs.io/v1"

    def __init__(self, key: str):
        self.key = key.strip()
        # ElevenLabs iki format kullanıyor:
        # Yeni format: sk_... → Authorization: Bearer sk_...
        # Eski format: xi-... → xi-api-key: xi-...
        if self.key.startswith("sk_"):
            self.h = {
                "xi-api-key": self.key,
                "Authorization": f"Bearer {self.key}",
            }
        else:
            self.h = {"xi-api-key": self.key}

    def check(self) -> tuple[bool, str]:
        try:
            # /v1/user bazı sk_ anahtarlarında 401 veriyor, /v1/voices daha güvenilir
            r = requests.get(f"{self.BASE}/voices", headers=self.h, timeout=10)
            if r.status_code == 200:
                voices = r.json().get("voices", [])
                count  = len(voices)
                names  = ", ".join(v["name"] for v in voices[:3])
                return True, f"Bağlandı ✓ — {count} ses bulundu ({names}...)"
            # Hata mesajını JSON'dan düzgün çek
            try:
                err_json = r.json()
                detail   = err_json.get("detail", {})
                if isinstance(detail, dict):
                    err_msg = detail.get("message", r.text[:120])
                else:
                    err_msg = str(detail)[:120]
            except Exception:
                err_msg = r.text[:120]
            return False, f"Hata {r.status_code}: {err_msg}"
        except Exception as e:
            return False, f"Baglanti hatasi: {e}"

    def list_voices(self) -> list[dict]:
        try:
            r = requests.get(f"{self.BASE}/voices", headers=self.h, timeout=10)
            return r.json().get("voices", []) if r.status_code == 200 else []
        except:
            return []

    def tts(self, text: str, voice_id: str, stab: float, sim: float) -> Optional[bytes]:
        try:
            r = requests.post(
                f"{self.BASE}/text-to-speech/{voice_id}",
                headers={**self.h, "Content-Type": "application/json"},
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": stab, "similarity_boost": sim},
                },
                timeout=60,
            )
            return r.content if r.status_code == 200 else None
        except:
            return None

    @staticmethod
    def mp3_duration(data: bytes) -> float:
        """128 kbps varsayımıyla tahmini süre."""
        return max(1.5, len(data) / 16_000) if data else 3.0


# ─────────────────────────────────────────────────────────
# 5. FRAME RENDERER (Pillow)
# ─────────────────────────────────────────────────────────

class FrameRenderer:
    """Her video karesi için PIL Image üretir."""

    FONT_PATHS = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]

    def __init__(self):
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        self.Image = Image
        self.Draw  = ImageDraw.Draw
        self.Font  = ImageFont
        self.Filter = ImageFilter
        self._font_cache: dict = {}

    def _font(self, size: int):
        if size in self._font_cache:
            return self._font_cache[size]
        for p in self.FONT_PATHS:
            if os.path.exists(p):
                try:
                    f = self.Font.truetype(p, size)
                    self._font_cache[size] = f
                    return f
                except:
                    pass
        f = self.Font.load_default()
        self._font_cache[size] = f
        return f

    def render(self, seg: dict, t: float) -> "Image":
        """t ∈ [0,1]: animation progress within this segment."""
        w, h = VIDEO_W, VIDEO_H
        info  = seg["info"]
        bg    = info["bg_rgb"]
        dark  = info["dark_rgb"]
        color = hex_to_rgb(info["color"])

        # --- gradient background ---
        img  = self.Image.new("RGB", (w, h))
        draw = self.Draw(img)
        for y in range(h):
            r_t = y / h
            r = int(dark[0] + (bg[0] - dark[0]) * r_t)
            g = int(dark[1] + (bg[1] - dark[1]) * r_t)
            b = int(dark[2] + (bg[2] - dark[2]) * r_t)
            draw.line([(0, y), (w, y)], fill=(r, g, b))

        # subtle dot grid overlay
        for gy in range(0, h, 40):
            for gx in range(0, w, 40):
                draw.ellipse([gx-1, gy-1, gx+1, gy+1], fill=(*color, 18))

        # --- animated orb ---
        anim   = info.get("animation", "pulse")
        cx, cy = w // 2, h // 2 - 100
        orb_r  = 108

        if anim == "bounce":
            cy   += int(16 * math.sin(t * math.pi * 3))
        elif anim == "pulse":
            orb_r = int(108 + 12 * math.sin(t * math.pi * 3))
        elif anim == "float":
            cx   += int(14 * math.sin(t * math.pi * 2))
            cy   += int(10 * math.cos(t * math.pi * 2))
        elif anim == "shake":
            cx   += int(8 * math.sin(t * math.pi * 6))

        # glow rings
        for gi in range(5, 0, -1):
            gr = orb_r + gi * 16
            ga = max(0, 22 - gi * 4)
            draw.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=(*color, ga))

        # main orb
        draw.ellipse([cx-orb_r, cy-orb_r, cx+orb_r, cy+orb_r], fill=(*color, 230))

        # inner highlight
        hi_r = orb_r // 3
        draw.ellipse([cx-hi_r, cy-orb_r+12, cx+hi_r//2, cy-orb_r//2+12],
                     fill=(255, 255, 255, 55))

        # --- character name ---
        fn36 = self._font(36)
        fn28 = self._font(28)
        fn24 = self._font(24)

        draw.text((cx, cy + orb_r + 32), seg["character"],
                  font=fn36, fill=(255, 255, 255, 230), anchor="mm")

        # --- speech bubble ---
        bub_margin = 80
        bub_y      = h - 220
        bub_h      = 175
        bub_x2     = w - bub_margin
        bub_y2     = bub_y + bub_h

        # shadow
        draw.rounded_rectangle(
            [bub_margin+5, bub_y+5, bub_x2+5, bub_y2+5],
            radius=24, fill=(0, 0, 0, 80),
        )
        # bubble
        draw.rounded_rectangle(
            [bub_margin, bub_y, bub_x2, bub_y2],
            radius=24, fill=(245, 245, 255, 215),
            outline=(*color, 200), width=3,
        )
        # bubble tip
        tip_cx = cx
        draw.polygon(
            [(tip_cx-14, bub_y), (tip_cx+14, bub_y), (tip_cx, bub_y-18)],
            fill=(245, 245, 255, 215),
        )

        # typewriter text reveal
        full_text  = seg["text"]
        reveal_fac = min(1.0, t * 2.2 + 0.03)
        partial    = full_text[: int(len(full_text) * reveal_fac)]
        bub_w_px   = (w - bub_margin * 2) - 60
        char_per_line = max(20, bub_w_px // 14)
        lines = wrap_text(partial, char_per_line)

        ty = bub_y + 26
        for line in lines[:4]:
            draw.text((w // 2, ty), line, font=fn24,
                      fill=(25, 20, 45, 245), anchor="mm")
            ty += 34

        # --- sound wave bars ---
        wy = bub_y - 52
        for bi in range(9):
            bar_h = int(13 + 26 * abs(math.sin(t * math.pi * 2.5 + bi * 0.55)))
            bx    = w // 2 - 72 + bi * 18
            draw.rounded_rectangle(
                [bx, wy - bar_h, bx + 10, wy],
                radius=4, fill=(*color, 190),
            )

        # --- slide-in overlay (fade from black at start) ---
        if t < 0.12:
            alpha = int(255 * (1 - t / 0.12))
            overlay = self.Image.new("RGB", (w, h), (0, 0, 0))
            img = self.Image.blend(img, overlay, alpha / 255)
            draw = self.Draw(img)

        # --- progress bar ---
        draw = self.Draw(img)
        draw.rectangle([0, h - 8, int(w * t), h], fill=color)
        draw.rectangle([0, h - 8, w, h - 7], fill=(255, 255, 255, 20))

        return img


# ─────────────────────────────────────────────────────────
# 6. VIDEO MAKER (imageio + imageio-ffmpeg, saf Python)
# ─────────────────────────────────────────────────────────

class VideoMaker:
    def __init__(self):
        self.has_imageio = False
        self.has_pil     = False
        try:
            import imageio
            import imageio.v3 as iio
            self._imageio = imageio
            self._iio     = iio
            self.has_imageio = True
        except ImportError:
            pass
        try:
            from PIL import Image
            self.has_pil = True
        except ImportError:
            pass

    def ready(self) -> bool:
        return self.has_imageio and self.has_pil

    def make(
        self,
        audio_segs: list[dict],
        progress_cb=None,
    ) -> Optional[bytes]:
        """Ses segmentlerini video kareleriyle birleştirir. bytes döner."""
        import imageio.v3 as iio
        import numpy as np

        fps      = VIDEO_FPS
        renderer = FrameRenderer()
        all_audio = b""
        frames    = []

        total_frames = sum(
            max(fps, int(s.get("duration", 3.0) * fps)) for s in audio_segs
        )
        done = 0

        for seg in audio_segs:
            dur    = seg.get("duration", 3.0)
            n      = max(fps, int(dur * fps))
            audio  = seg.get("audio") or b""
            all_audio += audio

            for fi in range(n):
                t   = fi / max(n - 1, 1)
                img = renderer.render(seg, t)
                frames.append(np.array(img))
                done += 1
                if progress_cb and done % 15 == 0:
                    progress_cb(done / total_frames * 0.80, f"Kare {done}/{total_frames}")

        if progress_cb:
            progress_cb(0.82, "Video kodlanıyor...")

        # Write video to temp file, then audio-mux via imageio ffmpeg plugin
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vtmp:
            vpath = vtmp.name
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as atmp:
            apath = atmp.name
            atmp.write(all_audio)

        # Write silent video
        iio.imwrite(
            vpath,
            frames,
            fps=fps,
            codec="libx264",
            output_params=["-crf", "23", "-preset", "fast", "-pix_fmt", "yuv420p"],
            plugin="FFMPEG",
        )

        if progress_cb:
            progress_cb(0.91, "Ses ekleniyor...")

        # Mux audio into video using imageio-ffmpeg
        out_path = vpath.replace(".mp4", "_final.mp4")
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

        import subprocess
        cmd = [
            ffmpeg_exe, "-y",
            "-i", vpath,
            "-i", apath,
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            out_path,
        ]
        subprocess.run(cmd, capture_output=True)

        # Cleanup
        os.unlink(vpath)
        os.unlink(apath)

        if progress_cb:
            progress_cb(1.0, "Tamamlandı!")

        if os.path.exists(out_path):
            with open(out_path, "rb") as f:
                data = f.read()
            os.unlink(out_path)
            return data
        return None


# ─────────────────────────────────────────────────────────
# 7. PDF MAKER (reportlab)
# ─────────────────────────────────────────────────────────

class PDFMaker:
    def __init__(self):
        self.ready = False
        try:
            from reportlab.pdfgen import canvas as rlcanvas
            from reportlab.lib.pagesizes import landscape, A4
            from reportlab.lib.colors import HexColor, white, Color
            from reportlab.lib.units import mm
            self._canvas  = rlcanvas
            self._A4L     = landscape(A4)
            self._Hex     = HexColor
            self._white   = white
            self._Color   = Color
            self._mm      = mm
            self.ready    = True
        except ImportError:
            pass

    def make(self, segments: list[dict]) -> Optional[bytes]:
        if not self.ready:
            return None

        buf = io.BytesIO()
        W, H = self._A4L          # 842 x 595 pt (landscape A4)
        c = self._canvas.Canvas(buf, pagesize=self._A4L)

        for idx, seg in enumerate(segments):
            info  = seg["info"]
            color = info["color"]
            bg    = info["bg_rgb"]
            dark  = info["dark_rgb"]
            hex_c = self._Hex(color)

            # gradient background (vertical strips approximation)
            steps = 40
            for i in range(steps):
                t   = i / steps
                r_  = int(dark[0] + (bg[0] - dark[0]) * t)
                g_  = int(dark[1] + (bg[1] - dark[1]) * t)
                b_  = int(dark[2] + (bg[2] - dark[2]) * t)
                c.setFillColorRGB(r_/255, g_/255, b_/255)
                strip_h = H / steps
                c.rect(0, H - strip_h * (i+1), W, strip_h, fill=1, stroke=0)

            # decorative dots
            c.setFillColorRGB(*[x/255 for x in hex_to_rgb(color)], alpha=None)
            for dx in range(0, int(W), 50):
                for dy in range(0, int(H), 50):
                    c.setFillAlpha(0.08)
                    c.circle(dx, dy, 2, fill=1, stroke=0)
            c.setFillAlpha(1)

            # orb
            orb_x, orb_y, orb_r = W * 0.5, H * 0.62, 70
            for ring in range(4, 0, -1):
                rr = orb_r + ring * 14
                c.setFillColorRGB(*[x/255 for x in hex_to_rgb(color)])
                c.setFillAlpha(0.06 - ring * 0.01)
                c.circle(orb_x, orb_y, rr, fill=1, stroke=0)
            c.setFillColorRGB(*[x/255 for x in hex_to_rgb(color)])
            c.setFillAlpha(0.88)
            c.circle(orb_x, orb_y, orb_r, fill=1, stroke=0)
            # highlight
            c.setFillColorRGB(1, 1, 1)
            c.setFillAlpha(0.22)
            c.circle(orb_x - orb_r * 0.28, orb_y + orb_r * 0.35, orb_r * 0.28, fill=1, stroke=0)

            # emoji (as text, best effort)
            c.setFillAlpha(1)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica-Bold", 46)
            c.drawCentredString(orb_x, orb_y - 16, info.get("emoji", ""))

            # character name
            c.setFillColorRGB(1, 1, 1)
            c.setFillAlpha(1)
            c.setFont("Helvetica-Bold", 26)
            c.drawCentredString(orb_x, orb_y - orb_r - 28, seg["character"])

            # speech bubble
            bub_margin = 50
            bub_w_pt   = W - bub_margin * 2
            bub_h_pt   = 140
            bub_y_pt   = 30
            bub_x_pt   = bub_margin

            c.setFillColorRGB(0.95, 0.95, 1)
            c.setFillAlpha(0.92)
            c.roundRect(bub_x_pt, bub_y_pt, bub_w_pt, bub_h_pt, 16, fill=1, stroke=0)
            # border
            c.setStrokeColorRGB(*[x/255 for x in hex_to_rgb(color)])
            c.setLineWidth(2.5)
            c.setStrokeAlpha(0.75)
            c.roundRect(bub_x_pt, bub_y_pt, bub_w_pt, bub_h_pt, 16, fill=0, stroke=1)

            # text in bubble
            c.setFillAlpha(1)
            c.setFillColorRGB(0.1, 0.08, 0.18)
            text    = seg["text"]
            lines   = wrap_text(text, 72)
            font_sz = 18 if len(lines) <= 3 else 15
            c.setFont("Helvetica", font_sz)
            line_h  = font_sz * 1.45
            start_y = bub_y_pt + bub_h_pt - 28
            for line in lines[:5]:
                c.drawCentredString(W / 2, start_y, line)
                start_y -= line_h

            # bubble tip (triangle)
            c.setFillColorRGB(0.95, 0.95, 1)
            c.setFillAlpha(0.92)
            tip_x = W / 2
            c.beginPath()
            c.moveTo(tip_x - 14, bub_y_pt + bub_h_pt)
            c.lineTo(tip_x + 14, bub_y_pt + bub_h_pt)
            c.lineTo(tip_x, bub_y_pt + bub_h_pt + 18)
            c.closePath()
            c.fill()

            # slide number
            c.setFillAlpha(0.45)
            c.setFillColorRGB(1, 1, 1)
            c.setFont("Helvetica", 11)
            c.drawRightString(W - 18, 10, f"{idx+1} / {len(segments)}")

            # progress bar
            c.setFillColorRGB(*[x/255 for x in hex_to_rgb(color)])
            c.setFillAlpha(0.9)
            prog_w = W * (idx + 1) / len(segments)
            c.rect(0, 0, prog_w, 5, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFillAlpha(0.08)
            c.rect(0, 0, W, 5, fill=1, stroke=0)

            c.showPage()

        c.save()
        buf.seek(0)
        return buf.read()


# ─────────────────────────────────────────────────────────
# 8. HTML SLAYT MOTORU
# ─────────────────────────────────────────────────────────

def build_slide_html(segments: list[dict]) -> str:
    data = json.dumps([
        {
            "char":  s["character"],
            "text":  s["text"],
            "emoji": s["info"]["emoji"],
            "color": s["info"]["color"],
            "bg":    s["info"].get("bg_rgb", [30, 30, 80]),
            "dark":  s["info"].get("dark_rgb", [10, 10, 30]),
            "anim":  s["info"].get("animation", "pulse"),
        }
        for s in segments
    ])

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden;height:100vh;display:flex;flex-direction:column;background:#0a0a14;}}
  #prog{{height:5px;flex-shrink:0;background:rgba(255,255,255,.07);}}
  #pfill{{height:100%;width:0%;transition:width .45s ease;}}
  #stage{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px 36px;position:relative;}}
  .orb{{width:120px;height:120px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:52px;position:relative;margin-bottom:10px;box-shadow:0 0 40px rgba(0,0,0,0.5);}}
  .orb::after{{content:'';position:absolute;top:14px;left:22px;width:36px;height:18px;border-radius:50%;background:rgba(255,255,255,.25);transform:rotate(-20deg);}}
  .cname{{font-size:18px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-bottom:18px;}}
  .bubble{{background:rgba(245,245,255,.13);backdrop-filter:blur(18px);border-radius:22px;padding:22px 34px;max-width:680px;text-align:center;font-size:18px;line-height:1.7;border:1.5px solid rgba(255,255,255,.15);box-shadow:0 12px 50px rgba(0,0,0,.45);position:relative;}}
  .bubble::after{{content:'';position:absolute;top:-14px;left:50%;transform:translateX(-50%);border:14px solid transparent;border-bottom-color:rgba(245,245,255,.13);}}
  .waves{{display:flex;gap:5px;align-items:flex-end;height:36px;margin-top:18px;}}
  .wb{{width:7px;border-radius:4px;animation:wb .5s ease-in-out infinite;}}
  #ctrl{{display:flex;gap:10px;align-items:center;justify-content:center;padding:12px;background:rgba(0,0,0,.55);flex-shrink:0;}}
  button{{padding:8px 20px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;letter-spacing:.03em;transition:all .18s;}}
  #bprev{{background:rgba(255,255,255,.1);color:#fff;}}
  #bnext{{background:#27ae60;color:#fff;}}
  #bplay{{background:#2980b9;color:#fff;}}
  button:hover{{transform:translateY(-2px);filter:brightness(1.15);}}
  #cnt{{color:rgba(255,255,255,.4);font-size:13px;padding:0 6px;min-width:50px;text-align:center;}}
  @keyframes wb{{0%,100%{{transform:scaleY(.3)}}50%{{transform:scaleY(1)}}}}
  @keyframes bounce{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-18px)}}}}
  @keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.14)}}}}
  @keyframes float{{0%,100%{{transform:translateY(-9px) rotate(-3deg)}}50%{{transform:translateY(9px) rotate(3deg)}}}}
  @keyframes shake{{0%,100%{{transform:rotate(0)}}25%{{transform:rotate(-7deg)}}75%{{transform:rotate(7deg)}}}}
  @keyframes slideIn{{from{{opacity:0;transform:translateY(32px)}}to{{opacity:1;transform:translateY(0)}}}}
  @keyframes typeText{{from{{clip-path:inset(0 100% 0 0)}}to{{clip-path:inset(0 0 0 0)}}}}
  .in{{animation:slideIn .4s ease both;}}
  #btext{{display:inline-block;}}
</style>
</head>
<body>
<div id="prog"><div id="pfill"></div></div>
<div id="stage" id="stage">
  <div class="orb" id="orb">🎤</div>
  <div class="cname" id="cname" style="color:#fff"></div>
  <div class="bubble">
    <span id="btext"></span>
  </div>
  <div class="waves" id="waves"></div>
</div>
<div id="ctrl">
  <button id="bprev" onclick="go(-1)">◀ Geri</button>
  <span id="cnt">1/1</span>
  <button id="bplay" onclick="togglePlay()">▶ Oynat</button>
  <button id="bnext" onclick="go(1)">İleri ▶</button>
</div>

<script>
const SLIDES = {data};
let cur = 0, playing = false, timer = null;

function rgb(arr){{ return `rgb(${{arr[0]}},${{arr[1]}},${{arr[2]}})`;}}
function lerp(a,b,t){{ return a+(b-a)*t; }}
function lerpRGB(a,b,t){{ return [lerp(a[0],b[0],t),lerp(a[1],b[1],t),lerp(a[2],b[2],t)].map(Math.round); }}

function buildGrad(bg, dark){{
  return `linear-gradient(170deg, ${{rgb(dark)}} 0%, ${{rgb(bg)}} 100%)`;
}}

function render(i){{
  const s = SLIDES[i];
  const stage = document.getElementById('stage');

  // background
  stage.style.background = buildGrad(s.bg, s.dark);

  // orb
  const orb = document.getElementById('orb');
  orb.textContent = s.emoji;
  orb.style.background = `radial-gradient(circle at 35% 40%, ${{s.color}}cc, ${{s.color}}44)`;
  orb.style.boxShadow = `0 0 60px ${{s.color}}55`;
  orb.style.animation = 'none';
  void orb.offsetWidth;
  orb.style.animation = s.anim + ' 0.8s ease-in-out infinite';

  // name
  const cn = document.getElementById('cname');
  cn.textContent = s.char;
  cn.style.color = s.color;

  // bubble border
  const bub = document.querySelector('.bubble');
  bub.style.borderColor = s.color + '44';
  bub.style.boxShadow = `0 12px 50px ${{s.color}}25`;

  // text typewriter
  const bt = document.getElementById('btext');
  bt.textContent = s.text;
  bt.style.animation = 'none';
  void bt.offsetWidth;
  bt.style.animation = 'typeText 1.6s steps(65,end) forwards';

  // wave bars
  const wv = document.getElementById('waves');
  wv.innerHTML = '';
  for(let j=0;j<9;j++){{
    const b = document.createElement('div');
    b.className = 'wb';
    b.style.background = s.color;
    b.style.height = (10 + Math.random()*30) + 'px';
    b.style.animationDelay = (j*0.06) + 's';
    b.style.animationDuration = (0.35 + Math.random()*0.45) + 's';
    wv.appendChild(b);
  }}

  // entrance
  stage.className = 'in';

  // progress
  document.getElementById('pfill').style.width = ((i+1)/SLIDES.length*100)+'%';
  document.getElementById('pfill').style.background = s.color;
  document.getElementById('cnt').textContent = (i+1)+' / '+SLIDES.length;
}}

function go(d){{
  cur = (cur + d + SLIDES.length) % SLIDES.length;
  render(cur);
}}

function togglePlay(){{
  playing = !playing;
  document.getElementById('bplay').textContent = playing ? '⏸ Durdur' : '▶ Oynat';
  if(playing) loop(); else clearTimeout(timer);
}}

function loop(){{
  if(!playing) return;
  go(1);
  timer = setTimeout(loop, 4500);
}}

if(SLIDES.length > 0) render(0);
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────
# 9. CSS
# ─────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@300;400;600;700;800&family=JetBrains+Mono:wght@400&display=swap');
html,body,[class*="css"]   { font-family:'Sora',sans-serif; }
.stApp                     { background:linear-gradient(145deg,#08080f,#0f1018 55%,#0a0d15); color:#e8e8f4; }
section[data-testid="stSidebar"] { background:rgba(8,8,18,.97); border-right:1px solid rgba(255,255,255,.05); }

.hdr   { text-align:center; padding:1.6rem 1rem .9rem; }
.hdr h1{ font-size:2.5rem; font-weight:800;
         background:linear-gradient(90deg,#E74C3C,#ff9a9a,#3498DB,#a8d8ff,#2ECC71);
         -webkit-background-clip:text; -webkit-text-fill-color:transparent;
         background-clip:text; letter-spacing:-1px; margin-bottom:.2rem; }
.hdr p { color:#778; font-size:.87rem; letter-spacing:.07em; }

.sc    { border-radius:12px; padding:.85rem 1.05rem; margin:.42rem 0;
         border-left:4px solid; background:rgba(255,255,255,.04);
         transition:transform .14s; }
.sc:hover { transform:translateX(4px); }
.sc-c  { font-size:.68rem; font-weight:700; letter-spacing:.12em;
         text-transform:uppercase; margin-bottom:.28rem; }
.sc-t  { font-size:.9rem; line-height:1.6; color:#ccd; }

.sr    { display:flex; gap:1rem; padding:.65rem .9rem;
         background:rgba(255,255,255,.04); border-radius:8px;
         margin:.6rem 0; font-size:.78rem; color:#aaa; }
.sr strong { color:#eee; }

.bdg   { display:inline-flex; align-items:center; gap:.3rem;
         padding:.26rem .65rem; border-radius:50px; font-size:.7rem;
         font-weight:600; margin:.15rem; }
.bok   { background:rgba(46,204,113,.12); color:#2ECC71; border:1px solid rgba(46,204,113,.28); }
.bwn   { background:rgba(231,76,60,.12);  color:#E74C3C; border:1px solid rgba(231,76,60,.28); }

.sct   { font-size:.66rem; letter-spacing:.14em; text-transform:uppercase;
         color:#555; margin:.75rem 0 .35rem; }

audio  { width:100%; border-radius:8px; margin:3px 0; }
textarea { background:rgba(255,255,255,.04)!important; border-radius:10px!important;
           color:#eee!important; font-family:'JetBrains Mono',monospace!important;
           font-size:.82rem!important; }
hr     { border-color:rgba(255,255,255,.07); }
.stProgress>div>div { border-radius:10px; }
</style>
"""


# ─────────────────────────────────────────────────────────
# 10. STATE & SIDEBAR
# ─────────────────────────────────────────────────────────

def init_state():
    defaults = dict(
        segs=[], audio_segs=[], full_audio=None,
        pres_html="", history=[], api_ok=False,
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def sidebar() -> tuple:
    with st.sidebar:
        st.markdown("### 🎬 3 Soru 3 Dakika")
        st.markdown("---")

        st.markdown('<p class="sct">🔑 ElevenLabs API</p>', unsafe_allow_html=True)

        # API key'i session_state'de sakla — sayfa yenilenince kaybolmasın
        if "api_key" not in st.session_state:
            st.session_state.api_key = ""

        key = st.text_input(
            "API Anahtarı",
            type="password",
            placeholder="xi-...",
            value=st.session_state.api_key,
        )
        if key:
            st.session_state.api_key = key

        # Nasıl alınır yardımı
        with st.expander("❓ API anahtarını nereden alırım?"):
            st.markdown(
                "1. [elevenlabs.io](https://elevenlabs.io) → kayıt ol (ücretsiz)\n"
                "2. Sağ üstteki profil ikonu → **Profile + API Key**\n"
                "3. Anahtarı kopyala, buraya yapıştır\n\n"
                "**Ücretsiz plan:** aylık 10.000 karakter"
            )

        api = None
        if key:
            if st.button("🔌 Bağlan", use_container_width=True):
                st.session_state.api_ok = False  # reset before check
                st.session_state.api_msg = ""
                try:
                    el = ElevenLabsAPI(key.strip())
                    ok, msg = el.check()
                    st.session_state.api_ok  = ok
                    st.session_state.api_msg = str(msg)
                except Exception as e:
                    st.session_state.api_ok  = False
                    st.session_state.api_msg = f"Bağlantı hatası: {e}"

            # Bağlantı sonucunu göster
            msg = st.session_state.get("api_msg", "")
            if msg:
                if st.session_state.api_ok:
                    st.success(f"✅ {msg}")
                else:
                    short_msg = str(msg).split("DeltaGenerator")[0].strip()
                    if "401" in short_msg:
                        st.error(
                            f"❌ **401 — Yetki Hatası**\n\n"
                            f"API yanıtı: `{short_msg}`\n\n"
                            "**Olası sebepler:**\n"
                            "- Anahtar yanlış kopyalanmış (başında/sonunda boşluk)\n"
                            "- ElevenLabs hesabında email doğrulanmamış\n"
                            "- Anahtar iptal edilmiş → yeni anahtar oluşturun"
                        )
                    elif "timeout" in short_msg.lower() or "connection" in short_msg.lower():
                        st.error("❌ Bağlantı hatası — internet bağlantınızı kontrol edin.")
                    else:
                        st.error(f"❌ {short_msg[:200]}")

            if st.session_state.api_ok and key:
                api = ElevenLabsAPI(key.strip())

        st.markdown("---")
        st.markdown('<p class="sct">⚙️ Ses Ayarları</p>', unsafe_allow_html=True)
        stab = st.slider("Kararlılık",  0.0, 1.0, 0.50, 0.05)
        sim  = st.slider("Benzerlik",   0.0, 1.0, 0.75, 0.05)

        st.markdown("---")
        st.markdown('<p class="sct">🎭 Karakterler</p>', unsafe_allow_html=True)
        for ch, info in CHARACTERS.items():
            vid = VOICE_IDS.get(ch, "")
            ok  = bool(vid and vid not in ("KENDI_SES_ID_BURAYA", ""))
            st.markdown(f"{'🟢' if ok else '🔴'} {info['emoji']} **{ch}**")

        if api:
            if st.button("🎧 Sesleri Listele", use_container_width=True):
                vs = api.list_voices()
                if vs:
                    for v in vs[:12]:
                        st.code(f"{v['name']}\n{v['voice_id']}", language=None)
                else:
                    st.info("Ses bulunamadı.")

        st.markdown("---")

        # dependency status
        st.markdown('<p class="sct">📦 Bağımlılıklar</p>', unsafe_allow_html=True)
        for lib, name in [("PIL", "Pillow"), ("imageio", "imageio[ffmpeg]"),
                          ("reportlab", "reportlab")]:
            try:
                __import__(lib)
                st.markdown(f"🟢 {name}")
            except ImportError:
                st.markdown(f"🔴 {name}")

        st.markdown("---")
        st.caption("v3.0 | Ses + Slayt + MP4 + PDF")

    return api, stab, sim


# ─────────────────────────────────────────────────────────
# 11. AUDIO GENERATION
# ─────────────────────────────────────────────────────────

def generate_audio(segs: list, api: ElevenLabsAPI, stab: float, sim: float) -> list:
    out = []
    n   = len(segs)
    pb  = st.progress(0, "Sesler hazırlanıyor...")
    ph  = st.empty()

    for i, seg in enumerate(segs):
        ch  = seg["character"]
        vid = VOICE_IDS.get(ch, "")
        ph.markdown(f"🎙️ **{seg['info']['emoji']} {ch}** seslendiriliyor… ({i+1}/{n})")

        if not vid or vid in ("KENDI_SES_ID_BURAYA", ""):
            out.append({**seg, "audio": None, "duration": 3.0})
        else:
            audio = api.tts(seg["text"], vid, stab, sim)
            dur   = ElevenLabsAPI.mp3_duration(audio) if audio else 3.0
            out.append({**seg, "audio": audio, "duration": dur})
            time.sleep(0.5)

        pb.progress((i+1)/n, f"{i+1}/{n} segment")

    ph.success(f"✅ {n} segment tamamlandı!")
    return out


# ─────────────────────────────────────────────────────────
# 12. MAIN
# ─────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="3 Soru 3 Dakika",
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    api, stab, sim = sidebar()

    st.markdown(
        '<div class="hdr"><h1>🎬 3 Soru 3 Dakika</h1>'
        '<p>Kendi sesinizle animasyonlu slaytlar · MP4 Video · PDF</p></div>',
        unsafe_allow_html=True,
    )

    tab_script, tab_live, tab_video, tab_pdf = st.tabs(
        ["✏️ Senaryo & Ses", "🖥️ Canlı Sunum", "🎞️ MP4 Video", "📄 PDF"]
    )

    # ═══════════════════════════════════════════
    # TAB 1 — Senaryo
    # ═══════════════════════════════════════════
    with tab_script:
        col_l, col_r = st.columns([1, 1], gap="large")

        with col_l:
            st.markdown('<p class="sct">📂 Hazır Şablonlar</p>', unsafe_allow_html=True)
            tc = st.columns(3)
            for idx, (lbl, content) in enumerate(TEMPLATES.items()):
                with tc[idx % 3]:
                    if st.button(lbl, use_container_width=True):
                        st.session_state["_tpl"] = content

            script = st.text_area(
                "Senaryo",
                value=st.session_state.get("_tpl", ""),
                height=390,
                placeholder=(
                    "Sunucu: Merhaba!\n"
                    "Konuk: Hoş geldiniz!\n"
                    "Dis Ses: Bugün..."
                ),
                label_visibility="collapsed",
            )

            if script.strip():
                parser = ScriptParser()
                segs   = parser.parse(script)
                wc     = parser.word_count(script)
                dur    = parser.duration_str(wc)
                chars  = list({s["character"] for s in segs})
                st.markdown(
                    f'<div class="sr">'
                    f'<span>📊 <strong>{wc}</strong> kelime</span>'
                    f'<span>⏱️ ~<strong>{dur}</strong></span>'
                    f'<span>💬 <strong>{len(segs)}</strong> satır</span>'
                    f'<span>🎭 <strong>{len(chars)}</strong> karakter</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.session_state.segs = segs

        with col_r:
            # voice status badges
            st.markdown('<p class="sct">🔊 Ses Durumu</p>', unsafe_allow_html=True)
            badges = ""
            for ch, info in CHARACTERS.items():
                vid = VOICE_IDS.get(ch, "")
                ok  = bool(vid and vid not in ("KENDI_SES_ID_BURAYA", ""))
                cls = "bok" if ok else "bwn"
                ic  = "✓" if ok else "✗"
                badges += f'<span class="bdg {cls}">{info["emoji"]} {ch} {ic}</span>'
            st.markdown(badges, unsafe_allow_html=True)

            st.markdown("---")

            # segment preview
            st.markdown('<p class="sct">👁️ Önizleme</p>', unsafe_allow_html=True)
            for s in st.session_state.segs:
                c = s["info"]["color"]
                st.markdown(
                    f'<div class="sc" style="border-color:{c};">'
                    f'<div class="sc-c" style="color:{c};">{s["info"]["emoji"]} {s["character"]}</div>'
                    f'<div class="sc-t">{s["text"]}</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            b1, b2 = st.columns(2)
            gen_btn = b1.button("🚀 Sesleri Oluştur", use_container_width=True, type="primary")
            clr_btn = b2.button("🗑️ Temizle",         use_container_width=True)

            if clr_btn:
                for k in ("segs", "audio_segs", "full_audio", "pres_html"):
                    st.session_state[k] = [] if isinstance(st.session_state[k], list) else None
                st.session_state.pres_html = ""
                if "_tpl" in st.session_state:
                    del st.session_state["_tpl"]
                st.rerun()

            if gen_btn:
                if not api:
                    st.error("❌ API bağlantısı yok — sol panelden bağlanın.")
                elif not script.strip():
                    st.warning("⚠️ Senaryo alanı boş.")
                else:
                    parser = ScriptParser()
                    segs   = parser.parse(script)
                    st.session_state.segs = segs

                    asegs = generate_audio(segs, api, stab, sim)
                    st.session_state.audio_segs = asegs

                    combined = b"".join(s["audio"] for s in asegs if s.get("audio"))
                    st.session_state.full_audio  = combined or None
                    st.session_state.pres_html   = build_slide_html(segs)
                    st.session_state.history.append(
                        {"preview": script[:55] + "...", "n": len(segs)}
                    )
                    st.rerun()

            # segment audio players
            if st.session_state.audio_segs:
                st.markdown('<p class="sct">🎵 Segment Oynatıcı</p>', unsafe_allow_html=True)
                for seg in st.session_state.audio_segs:
                    label = f"{seg['info']['emoji']} {seg['character']}: {seg['text'][:46]}…"
                    with st.expander(label, expanded=False):
                        if seg.get("audio"):
                            st.audio(seg["audio"], format="audio/mp3")
                            st.caption(f"⏱️ ~{seg['duration']:.1f} sn")
                        else:
                            st.caption("⚠️ Ses üretilemedi (voice ID eksik?)")

                if st.session_state.full_audio:
                    st.markdown("---")
                    st.audio(st.session_state.full_audio, format="audio/mp3")
                    st.download_button(
                        "⬇️ Tüm Sesi MP3 İndir",
                        st.session_state.full_audio,
                        "podcast.mp3", "audio/mpeg",
                        use_container_width=True,
                    )

    # ═══════════════════════════════════════════
    # TAB 2 — Canlı Sunum
    # ═══════════════════════════════════════════
    with tab_live:
        if not st.session_state.segs:
            st.info("ℹ️ Önce **Senaryo & Ses** sekmesinde senaryo girin.")
        else:
            if not st.session_state.pres_html:
                st.session_state.pres_html = build_slide_html(st.session_state.segs)

            st.components.v1.html(
                st.session_state.pres_html,
                height=640,
                scrolling=False,
            )

            st.markdown("---")
            st.caption(
                "**◀ ▶** ile manuel gezinme · **▶ Oynat** ile otomatik slayt gösterisi · "
                "Ses ile senkron için aşağıdan başlatın"
            )
            if st.session_state.full_audio:
                st.audio(st.session_state.full_audio, format="audio/mp3")

    # ═══════════════════════════════════════════
    # TAB 3 — MP4 Video
    # ═══════════════════════════════════════════
    with tab_video:
        st.markdown("### 🎞️ MP4 Video Oluşturucu")

        vm = VideoMaker()

        if not vm.has_pil:
            st.error("❌ **Pillow** bulunamadı → `pip install Pillow`")
        if not vm.has_imageio:
            st.error("❌ **imageio[ffmpeg]** bulunamadı → `pip install imageio[ffmpeg]`")

        if not st.session_state.audio_segs:
            st.info("ℹ️ Önce **Senaryo & Ses** sekmesinde sesleri oluşturun.")
        elif vm.ready():
            total_dur = sum(s.get("duration", 3.0) for s in st.session_state.audio_segs)
            total_frm = int(total_dur * VIDEO_FPS)
            st.info(
                f"**{len(st.session_state.audio_segs)}** segment · "
                f"~**{total_dur:.1f} sn** · "
                f"**{total_frm}** kare @ {VIDEO_FPS} FPS · "
                f"Çözünürlük: **{VIDEO_W}×{VIDEO_H}**"
            )

            if st.button("🎬 Video Oluştur", type="primary", use_container_width=True):
                sph = st.empty()
                pph = st.progress(0)

                def cb(v, m):
                    pph.progress(min(v, 1.0), m)
                    sph.markdown(f"⚙️ {m}")

                with st.spinner("Video işleniyor… Bu birkaç dakika sürebilir."):
                    video_bytes = vm.make(st.session_state.audio_segs, cb)

                if video_bytes:
                    st.success(f"✅ Video hazır! ({len(video_bytes)//1024} KB)")
                    st.video(video_bytes)
                    st.download_button(
                        "⬇️ MP4 İndir",
                        video_bytes,
                        "3soru3dakika.mp4",
                        "video/mp4",
                        use_container_width=True,
                    )
                else:
                    st.error(
                        "❌ Video oluşturulamadı. "
                        "`imageio[ffmpeg]` kurulu mu? "
                        "`pip install imageio[ffmpeg]` deneyin."
                    )

    # ═══════════════════════════════════════════
    # TAB 4 — PDF
    # ═══════════════════════════════════════════
    with tab_pdf:
        st.markdown("### 📄 PDF Slayt İndirici")

        pm = PDFMaker()

        if not pm.ready:
            st.error("❌ **reportlab** bulunamadı → `pip install reportlab`")
        elif not st.session_state.segs:
            st.info("ℹ️ Önce **Senaryo & Ses** sekmesinde senaryo girin.")
        else:
            st.info(
                f"**{len(st.session_state.segs)}** slayt · "
                "Yatay A4 (Landscape) · Her slayt bir karakter konuşması"
            )
            if st.button("📄 PDF Oluştur", type="primary", use_container_width=True):
                with st.spinner("PDF oluşturuluyor…"):
                    pdf_bytes = pm.make(st.session_state.segs)

                if pdf_bytes:
                    st.success(f"✅ PDF hazır! ({len(pdf_bytes)//1024} KB)")
                    st.download_button(
                        "⬇️ PDF İndir",
                        pdf_bytes,
                        "3soru3dakika.pdf",
                        "application/pdf",
                        use_container_width=True,
                    )
                else:
                    st.error("❌ PDF oluşturulamadı.")

        # history
        if st.session_state.history:
            st.markdown("---")
            st.markdown('<p class="sct">📜 Geçmiş</p>', unsafe_allow_html=True)
            for h in reversed(st.session_state.history[-5:]):
                st.markdown(f"🎬 *{h['preview']}* — {h['n']} satır")


if __name__ == "__main__":
    main()
