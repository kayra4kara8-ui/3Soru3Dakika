"""
🎙️ 3 Soru 3 Dakika — Profesyonel Podcast & Sunum Stüdyosu
Streamlit Cloud uyumlu — ffmpeg/node olmadan da çalışır.
"""

import streamlit as st
import json
import io
import os
import math
import tempfile
import time
import base64
import subprocess
from typing import Optional

# ══════════════════════════════════════════════════════════════
# 1. KARAKTER KONFİGÜRASYONU
# ══════════════════════════════════════════════════════════════

CHARACTERS = {
    "Elif": {
        "color":    "#C9A84C",
        "bg_rgb":   (140, 90, 20),
        "dark_rgb": (40, 22, 5),
        "emoji":    "🎤",
        "role":     "Sunucu",
        "animation": "bounce",
        "hex_pptx":  "C9A84C",
    },
    "Ecem": {
        "color":    "#4C9FCA",
        "bg_rgb":   (20, 80, 140),
        "dark_rgb": (5, 20, 50),
        "emoji":    "👩‍💼",
        "role":     "Konuk",
        "animation": "pulse",
        "hex_pptx":  "4C9FCA",
    },
    "Eba": {
        "color":    "#A0C878",
        "bg_rgb":   (50, 110, 40),
        "dark_rgb": (12, 30, 10),
        "emoji":    "🎧",
        "role":     "Dış Ses",
        "animation": "float",
        "hex_pptx":  "A0C878",
    },
}

FALLBACK_CHARS = [
    ("#E07B7B", (160,60,60),  (50,15,15),  "E07B7B"),
    ("#B57FCC", (130,70,180), (40,15,60),  "B57FCC"),
    ("#7EC8C8", (50,160,160), (10,55,55),  "7EC8C8"),
]

TEMPLATES = {
    "🏥 Medikal": (
        "Elif: Merhaba ve 3 Soru 3 Dakika'ya hoş geldiniz. Ben Elif, bugün sağlık teknolojilerinin geleceğini konuşacağız.\n"
        "Eba: Bugünün konuğu, dijital sağlık dönüşümünde öncü çalışmalar yürüten kıdemli bir uzman hekim.\n"
        "Ecem: Merhaba Elif, bu platforma davet edildiğim için çok mutluyum.\n"
        "Elif: İlk sorumuzla başlayalım. Yapay zeka gerçekten tanı koyabilir mi?\n"
        "Ecem: Henüz tam anlamıyla değil. Ama destekleyici rolü inanılmaz güçlendi. Özellikle görüntü analizinde.\n"
        "Eba: Araştırmalar, yapay zekanın bazı patoloji görüntülerinde uzman hekimlerle yarışabilir doğruluk sağladığını gösteriyor.\n"
        "Elif: İkinci sorumuz: Hekimler bu teknolojiyi nasıl karşılıyor?\n"
        "Ecem: İki kutup var. Bir kesim çok heyecanlı, diğer kesim temkinli. Ben temkinli heyecanlıların safındayım.\n"
        "Elif: Son olarak, Türkiye bu dönüşüme hazır mı?\n"
        "Ecem: Altyapı hızla gelişiyor. Ama en büyük açık insan kaynağında. Dijital okuryazarlık şart.\n"
        "Eba: 3 Soru 3 Dakika'yı izlediğiniz için teşekkürler. Sağlıkla kalın."
    ),
    "💼 İş Dünyası": (
        "Elif: Hoş geldiniz. Bugün girişim ekosistemi ve startup kültürünü masaya yatırıyoruz.\n"
        "Eba: Konuğumuz, son beş yılda üç başarılı exit gerçekleştirmiş deneyimli bir girişimci.\n"
        "Ecem: Merhaba, bu konuşmayı çok önemsiyorum.\n"
        "Elif: İlk soru: Türk startup ekosistemi global rekabete hazır mı?\n"
        "Ecem: Potansiyel muazzam. Ama sabırsızlık en büyük düşmanımız. Hızlı büyümek yerine sağlam büyümek lazım.\n"
        "Eba: Son verilere göre Türkiye, Orta Doğu ve Afrika'nın en aktif startup ekosistemlerinden biri konumunda.\n"
        "Elif: İkinci soru: Yatırımcı bulmak artık daha mı zor?\n"
        "Ecem: Akıllı para daha seçici. Bu aslında iyi. Gerçek değer yaratan şirketler için fırsatlar arttı.\n"
        "Elif: Son soru: Yeni girişimcilere tek bir tavsiye?\n"
        "Ecem: Problemi iyi tanımlayın. Çözümü değil, problemi sevin. Gerisi gelir.\n"
        "Eba: Değerli bilgiler için teşekkürler. Bir sonraki bölümde görüşmek üzere."
    ),
    "🎓 Eğitim": (
        "Elif: 3 Soru 3 Dakika'ya hoş geldiniz. Bugün eğitimin geleceğini tartışıyoruz.\n"
        "Eba: Konuğumuz, eğitim teknolojileri alanında on yılı aşkın deneyime sahip bir akademisyen.\n"
        "Ecem: Merhaba, eğitim hepimizin ortak meselesi, bu yüzden burada olmaktan mutluyum.\n"
        "Elif: İlk sorum şu: Yapay zeka öğretmenlerin yerini alacak mı?\n"
        "Ecem: Kesinlikle hayır. Ama öğretmenlik mesleğini köklü biçimde dönüştürecek. Rutin görevler azalacak, insan teması öne çıkacak.\n"
        "Eba: Dünya Ekonomik Forumu verilerine göre 2030'a kadar eğitimde en değerli beceriler eleştirel düşünme ve yaratıcılık olacak.\n"
        "Elif: İkinci soru: Uzaktan eğitim kalıcı mı oldu?\n"
        "Ecem: Hibrit model kalıcı oldu. Saf uzaktan veya saf yüz yüze değil. En iyi ikisini birleştiren model kazanacak.\n"
        "Elif: Son soru: Türk eğitim sistemi ne yapmalı?\n"
        "Ecem: Ezber kültüründen soru sorma kültürüne geçmeli. Bu bir nesil işi ama başlamak için en iyi an şimdi.\n"
        "Eba: Teşekkürler. Öğrenmeye devam edin, görüşmek üzere."
    ),
}

VIDEO_W, VIDEO_H, VIDEO_FPS = 1280, 720, 24

# ══════════════════════════════════════════════════════════════
# 2. YARDIMCI FONKSİYONLAR
# ══════════════════════════════════════════════════════════════

def hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def wrap_text(text: str, max_chars: int) -> list:
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

def mp3_duration(data: bytes) -> float:
    return max(1.5, len(data) / 16_000) if data else 3.0

def audio_to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode()

def safe_run(cmd: list, **kwargs) -> Optional[subprocess.CompletedProcess]:
    """subprocess.run with FileNotFoundError protection."""
    try:
        return subprocess.run(cmd, **kwargs)
    except (FileNotFoundError, OSError):
        return None

def get_ffmpeg() -> Optional[str]:
    """Returns path to ffmpeg binary, or None if unavailable."""
    # Try system ffmpeg
    r = safe_run(["ffmpeg", "-version"], capture_output=True, timeout=5)
    if r and r.returncode == 0:
        return "ffmpeg"
    # Try imageio_ffmpeg bundled binary
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe:
            return exe
    except Exception:
        pass
    return None

def get_node() -> bool:
    """Returns True if node + pptxgenjs are available."""
    r = safe_run(["node", "--version"], capture_output=True, text=True, timeout=5)
    if not r or r.returncode != 0:
        return False
    r2 = safe_run(
        ["node", "-e", "require('pptxgenjs'); console.log('ok')"],
        capture_output=True, text=True, timeout=10
    )
    return r2 is not None and "ok" in r2.stdout

# ══════════════════════════════════════════════════════════════
# 3. SCRIPT PARSER
# ══════════════════════════════════════════════════════════════

class ScriptParser:
    def __init__(self):
        self._dyn = {}
        self._ci  = 0

    def _info(self, name: str) -> dict:
        if name in CHARACTERS:
            return CHARACTERS[name]
        if name not in self._dyn:
            hex_c, bg, dark, hp = FALLBACK_CHARS[self._ci % len(FALLBACK_CHARS)]
            self._dyn[name] = {
                "color": hex_c, "bg_rgb": bg, "dark_rgb": dark,
                "emoji": "🔊", "role": "Konuşmacı",
                "animation": "pulse", "hex_pptx": hp,
            }
            self._ci += 1
        return self._dyn[name]

    def parse(self, script: str) -> list:
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
    def word_count(s): return len(s.split())

    @staticmethod
    def duration_str(wc):
        m, s = divmod(int(wc / 130 * 60), 60)
        return f"{m}:{s:02d}"


# ══════════════════════════════════════════════════════════════
# 4. SES YÖNETİMİ
# ══════════════════════════════════════════════════════════════

class VoiceManager:
    def __init__(self, voice_map: dict):
        self.voice_map = voice_map
        self.default   = next(iter(voice_map.values())) if voice_map else None

    def get_audio(self, character: str) -> Optional[bytes]:
        return self.voice_map.get(character) or self.default


# ══════════════════════════════════════════════════════════════
# 5. FRAME RENDERER (Pillow)
# ══════════════════════════════════════════════════════════════

class FrameRenderer:
    FONT_PATHS = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/home/adminuser/venv/lib/python3.13/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf",
    ]

    def __init__(self):
        from PIL import Image, ImageDraw, ImageFont
        self.Image = Image
        self.Draw  = ImageDraw.Draw
        self.Font  = ImageFont
        self._fc   = {}

    def _font(self, size: int):
        if size in self._fc:
            return self._fc[size]
        for p in self.FONT_PATHS:
            if os.path.exists(p):
                try:
                    f = self.Font.truetype(p, size)
                    self._fc[size] = f
                    return f
                except Exception:
                    pass
        f = self.Font.load_default()
        self._fc[size] = f
        return f

    def render(self, seg: dict, t: float):
        w, h  = VIDEO_W, VIDEO_H
        info  = seg["info"]
        color = hex_to_rgb(info["color"])
        bg    = info["bg_rgb"]
        dark  = info["dark_rgb"]

        img  = self.Image.new("RGB", (w, h))
        draw = self.Draw(img)

        # Gradient background
        for y in range(h):
            r_t = y / h
            r = int(dark[0] + (bg[0]-dark[0]) * r_t)
            g = int(dark[1] + (bg[1]-dark[1]) * r_t)
            b = int(dark[2] + (bg[2]-dark[2]) * r_t)
            draw.line([(0,y),(w,y)], fill=(r,g,b))

        # Grid
        for gx in range(0, w, 60):
            draw.line([(gx,0),(gx,h)], fill=(*color, 8))
        for gy in range(0, h, 60):
            draw.line([(0,gy),(w,gy)], fill=(*color, 8))

        # Top bar
        draw.rectangle([0, 0, w, 64], fill=(8, 8, 18))
        draw.rectangle([0, 60, w, 64], fill=color)
        draw.text((32, 18), "3 SORU 3 DAKİKA", font=self._font(22), fill=(*color, 230), anchor="lm")
        draw.text((w-32, 18), "● CANLI", font=self._font(14), fill=(255, 80, 80), anchor="rm")

        # Animated orb
        anim  = info.get("animation", "pulse")
        cx, cy = w // 2, h // 2 - 65
        orb_r  = 105
        if anim == "bounce":
            cy   += int(14 * math.sin(t * math.pi * 3))
        elif anim == "pulse":
            orb_r = int(105 + 11 * math.sin(t * math.pi * 3))
        elif anim == "float":
            cx   += int(12 * math.sin(t * math.pi * 2))
            cy   += int(9  * math.cos(t * math.pi * 2))

        for gi in range(5, 0, -1):
            gr = orb_r + gi * 18
            ga = max(0, 18 - gi * 3)
            draw.ellipse([cx-gr, cy-gr, cx+gr, cy+gr], fill=(*color, ga))

        draw.ellipse([cx-orb_r, cy-orb_r, cx+orb_r, cy+orb_r], fill=(*color, 220))
        hr = orb_r // 3
        draw.ellipse([cx-hr, cy-orb_r+14, cx+hr//2, cy-orb_r//2+14], fill=(255, 255, 255, 50))
        draw.text((cx, cy), info["emoji"], font=self._font(62), fill=(255,255,255,220), anchor="mm")
        draw.text((cx, cy + orb_r + 28), seg["character"], font=self._font(32), fill=(255,255,255,230), anchor="mm")
        draw.text((cx, cy + orb_r + 62), info.get("role",""), font=self._font(18), fill=(*color, 180), anchor="mm")

        # Wave bars
        wy = h - 230
        for bi in range(11):
            bh_val = int(10 + 28 * abs(math.sin(t*math.pi*2.5 + bi*0.5)))
            bx = w//2 - 90 + bi * 18
            draw.rounded_rectangle([bx, wy-bh_val, bx+10, wy], radius=4, fill=(*color, 185))

        # Speech bubble
        bub_m, bub_y, bub_h = 70, h - 210, 170
        bub_x2, bub_y2 = w - bub_m, bub_y + bub_h
        draw.rounded_rectangle([bub_m+4, bub_y+4, bub_x2+4, bub_y2+4], radius=20, fill=(0,0,0,70))
        draw.rounded_rectangle([bub_m, bub_y, bub_x2, bub_y2], radius=20,
                               fill=(245,245,255,210), outline=(*color,190), width=3)
        draw.polygon([(cx-16,bub_y),(cx+16,bub_y),(cx,bub_y-20)], fill=(245,245,255,210))

        full    = seg["text"]
        rev     = int(len(full) * min(1.0, t*2.4 + 0.02))
        partial = full[:rev]
        cpline  = max(22, (w - bub_m*2 - 60) // 13)
        lines   = wrap_text(partial, cpline)
        ty = bub_y + 24
        for ln in lines[:4]:
            draw.text((w//2, ty), ln, font=self._font(22), fill=(20,18,40,245), anchor="mm")
            ty += 36

        # Bottom bar
        draw.rectangle([0, h-48, w, h], fill=(8,8,18))
        draw.rectangle([0, h-48, w, h-45], fill=color)
        draw.text((32, h-24), f"{seg['character']}  ·  {info.get('role','')}", font=self._font(18), fill=(255,255,255,200), anchor="lm")

        # Progress bar
        pw = int(w * t)
        draw.rectangle([0, h-6, pw, h], fill=color)

        return img.convert("RGB")


# ══════════════════════════════════════════════════════════════
# 6. VIDEO MAKER
# ══════════════════════════════════════════════════════════════

class VideoMaker:
    def __init__(self):
        self.has_pil     = False
        self.has_imageio = False
        self.ffmpeg      = None
        try:
            from PIL import Image
            self.has_pil = True
        except ImportError:
            pass
        try:
            import imageio
            self.has_imageio = True
        except ImportError:
            pass
        self.ffmpeg = get_ffmpeg()

    def ready(self):
        return self.has_pil and self.has_imageio and self.ffmpeg is not None

    def make(self, audio_segs: list, cb=None) -> Optional[bytes]:
        if not self.ready():
            return None
        import imageio.v3 as iio
        import numpy as np

        renderer  = FrameRenderer()
        all_audio = b""
        frames    = []
        total_f   = sum(max(VIDEO_FPS, int(s.get("duration",3)*VIDEO_FPS)) for s in audio_segs)
        done = 0

        for seg in audio_segs:
            dur   = seg.get("duration", 3.0)
            n     = max(VIDEO_FPS, int(dur * VIDEO_FPS))
            audio = seg.get("audio") or b""
            all_audio += audio
            for fi in range(n):
                frames.append(np.array(renderer.render(seg, fi/max(n-1,1))))
                done += 1
                if cb and done % 15 == 0:
                    cb(done/total_f*0.75, f"Kare {done}/{total_f}")

        if cb:
            cb(0.78, "Video kodlanıyor…")

        vpath = tempfile.mktemp(suffix=".mp4")
        apath = tempfile.mktemp(suffix=".mp3")

        try:
            # Set env var for imageio to use correct ffmpeg
            if self.ffmpeg != "ffmpeg":
                os.environ["IMAGEIO_FFMPEG_EXE"] = self.ffmpeg

            writer = iio.imopen(vpath, "w", plugin="FFMPEG")
            writer.write(frames, fps=VIDEO_FPS, codec="libx264",
                         output_params=["-crf","23","-preset","fast","-pix_fmt","yuv420p"])
            writer.close()

            with open(apath, "wb") as f:
                f.write(all_audio)

            if cb:
                cb(0.90, "Ses ekleniyor…")

            out = tempfile.mktemp(suffix="_final.mp4")
            if all_audio and len(all_audio) > 100:
                cmd = [self.ffmpeg, "-y", "-i", vpath, "-i", apath,
                       "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", out]
            else:
                cmd = [self.ffmpeg, "-y", "-i", vpath, "-c:v", "copy", out]

            safe_run(cmd, capture_output=True, timeout=300)

            if cb:
                cb(1.0, "Tamamlandı!")

            if os.path.exists(out):
                data = open(out, "rb").read()
                return data
            return None

        finally:
            for p in [vpath, apath]:
                try:
                    if os.path.exists(p):
                        os.unlink(p)
                except Exception:
                    pass
            out_path = locals().get("out")
            if out_path and os.path.exists(out_path):
                try:
                    os.unlink(out_path)
                except Exception:
                    pass


# ══════════════════════════════════════════════════════════════
# 7. PDF MAKER
# ══════════════════════════════════════════════════════════════

class PDFMaker:
    def __init__(self):
        self._ready = False
        try:
            from reportlab.pdfgen import canvas as rlc
            from reportlab.lib.pagesizes import landscape, A4
            self._canvas = rlc
            self._A4L    = landscape(A4)
            self._ready  = True
        except ImportError:
            pass

    def ready(self): return self._ready

    def make(self, segments: list) -> Optional[bytes]:
        if not self._ready:
            return None
        buf = io.BytesIO()
        W, H = self._A4L
        c = self._canvas.Canvas(buf, pagesize=self._A4L)

        for idx, seg in enumerate(segments):
            info  = seg["info"]
            color = hex_to_rgb(info["color"])
            bg    = info["bg_rgb"]
            dark  = info["dark_rgb"]

            # Gradient
            steps = 50
            for i in range(steps):
                t = i / steps
                r_ = int(dark[0]+(bg[0]-dark[0])*t)
                g_ = int(dark[1]+(bg[1]-dark[1])*t)
                b_ = int(dark[2]+(bg[2]-dark[2])*t)
                c.setFillColorRGB(r_/255, g_/255, b_/255)
                c.rect(0, H-H/steps*(i+1), W, H/steps+1, fill=1, stroke=0)

            # Top bar
            c.setFillColorRGB(0.03, 0.03, 0.07)
            c.rect(0, H-50, W, 50, fill=1, stroke=0)
            c.setFillColorRGB(*[x/255 for x in color])
            c.rect(0, H-54, W, 4, fill=1, stroke=0)
            c.setFont("Helvetica-Bold", 16)
            c.setFillColorRGB(*[x/255 for x in color])
            c.drawString(24, H-34, "3 SORU 3 DAKİKA")
            c.setFont("Helvetica", 10)
            c.setFillColorRGB(1, 0.3, 0.3)
            c.drawRightString(W-24, H-34, "● YAYIN")

            # Orb
            orb_x, orb_y, orb_r = W*0.5, H*0.58, 65
            for ring in range(4, 0, -1):
                rr = orb_r + ring*14
                c.setFillColorRGB(*[x/255 for x in color])
                c.setFillAlpha(max(0.02, 0.07-ring*0.015))
                c.circle(orb_x, orb_y, rr, fill=1, stroke=0)
            c.setFillColorRGB(*[x/255 for x in color])
            c.setFillAlpha(0.88)
            c.circle(orb_x, orb_y, orb_r, fill=1, stroke=0)
            c.setFillColorRGB(1,1,1); c.setFillAlpha(0.18)
            c.circle(orb_x-orb_r*0.28, orb_y+orb_r*0.32, orb_r*0.26, fill=1, stroke=0)
            c.setFillColorRGB(1,1,1); c.setFillAlpha(1)
            c.setFont("Helvetica-Bold", 36)
            c.drawCentredString(orb_x, orb_y-12, info.get("emoji",""))
            c.setFont("Helvetica-Bold", 22)
            c.setFillColorRGB(1,1,1)
            c.drawCentredString(orb_x, orb_y-orb_r-26, seg["character"])
            c.setFont("Helvetica", 13)
            c.setFillColorRGB(*[x/255 for x in color])
            c.drawCentredString(orb_x, orb_y-orb_r-46, info.get("role",""))

            # Wave bars
            bar_y = orb_y - orb_r - 65
            for bi in range(9):
                bh = 8 + (bi%3+1)*5
                bx = orb_x - 68 + bi*17
                c.setFillColorRGB(*[x/255 for x in color])
                c.setFillAlpha(0.7)
                c.roundRect(bx, bar_y-bh, 10, bh, 3, fill=1, stroke=0)

            # Bubble
            bub_m, bub_h_pt, bub_y_pt = 45, 130, 38
            bub_w_pt = W - bub_m*2
            c.setFillColorRGB(0.96,0.96,1); c.setFillAlpha(0.93)
            c.roundRect(bub_m, bub_y_pt, bub_w_pt, bub_h_pt, 14, fill=1, stroke=0)
            c.setStrokeColorRGB(*[x/255 for x in color])
            c.setStrokeAlpha(0.7); c.setLineWidth(2)
            c.roundRect(bub_m, bub_y_pt, bub_w_pt, bub_h_pt, 14, fill=0, stroke=1)

            tip_x = W/2
            tip_yb = bub_y_pt + bub_h_pt
            c.setFillColorRGB(0.96,0.96,1); c.setFillAlpha(0.93)
            p = c.beginPath()
            p.moveTo(tip_x-14, tip_yb)
            p.lineTo(tip_x+14, tip_yb)
            p.lineTo(tip_x, tip_yb+16)
            p.close()
            c.drawPath(p, fill=1, stroke=0)

            c.setFillAlpha(1); c.setFillColorRGB(0.1,0.08,0.18)
            lines = wrap_text(seg["text"], 75)
            fsz   = 16 if len(lines) <= 3 else 13
            c.setFont("Helvetica", fsz)
            lh = fsz * 1.5
            ty = bub_y_pt + bub_h_pt - 22
            for ln in lines[:5]:
                c.drawCentredString(W/2, ty, ln)
                ty -= lh

            # Bottom bar
            c.setFillColorRGB(0.03,0.03,0.07); c.setFillAlpha(1)
            c.rect(0, 0, W, 38, fill=1, stroke=0)
            c.setFillColorRGB(*[x/255 for x in color])
            c.rect(0, 36, W, 2, fill=1, stroke=0)
            c.setFont("Helvetica-Bold", 12)
            c.setFillColorRGB(*[x/255 for x in color])
            c.drawString(24, 14, f"{seg['character']}  ·  {info.get('role','')}")
            c.setFillColorRGB(1,1,1)
            c.drawRightString(W-24, 14, f"{idx+1} / {len(segments)}")
            c.setFillColorRGB(*[x/255 for x in color]); c.setFillAlpha(0.9)
            c.rect(0, 0, W*(idx+1)/len(segments), 5, fill=1, stroke=0)
            c.showPage()

        c.save()
        buf.seek(0)
        return buf.read()


# ══════════════════════════════════════════════════════════════
# 8. PPTX MAKER — python-pptx (Streamlit Cloud uyumlu, Node.js gerektirmez)
# ══════════════════════════════════════════════════════════════

class PPTXMaker:
    """python-pptx tabanlı PPTX üretici. Streamlit Cloud dahil her ortamda çalışır."""

    def __init__(self):
        self._ready = False
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor
            from pptx.enum.text import PP_ALIGN
            self._ready = True
        except ImportError:
            pass

    def ready(self): return self._ready

    def make(self, segments: list, audio_segs: list = None, **kwargs) -> Optional[bytes]:
        if not self._ready:
            return None
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.dml.color import RGBColor
        from pptx.enum.text import PP_ALIGN

        prs = Presentation()
        prs.slide_width  = Inches(10)
        prs.slide_height = Inches(5.625)
        blank_layout = prs.slide_layouts[6]
        total = len(segments)

        def to_rgb(hex_str):
            h = hex_str.lstrip("#")
            return RGBColor(int(h[0:2],16), int(h[2:4],16), int(h[4:6],16))

        def add_rect(slide, x, y, w, h, fill_rgb, line_rgb=None):
            from pptx.util import Inches
            shp = slide.shapes.add_shape(1, Inches(x), Inches(y), Inches(w), Inches(h))
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill_rgb
            if line_rgb:
                shp.line.color.rgb = line_rgb
                shp.line.width = Pt(1)
            else:
                shp.line.fill.background()
            return shp

        def add_oval(slide, x, y, w, h, fill_rgb):
            from pptx.util import Inches
            shp = slide.shapes.add_shape(9, Inches(x), Inches(y), Inches(w), Inches(h))
            shp.fill.solid()
            shp.fill.fore_color.rgb = fill_rgb
            shp.line.fill.background()
            return shp

        def add_textbox(slide, text, x, y, w, h, size, bold=False,
                        color=None, align="center", italic=False):
            from pptx.util import Inches, Pt
            if color is None:
                color = RGBColor(255,255,255)
            txb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
            tf  = txb.text_frame
            tf.word_wrap = True
            p   = tf.paragraphs[0]
            p.alignment = {"center": PP_ALIGN.CENTER,
                           "right":  PP_ALIGN.RIGHT,
                           "left":   PP_ALIGN.LEFT}.get(align, PP_ALIGN.CENTER)
            run = p.add_run()
            run.text = text
            run.font.size  = Pt(size)
            run.font.bold  = bold
            run.font.italic = italic
            run.font.color.rgb = color

        for idx, seg in enumerate(segments):
            info    = seg["info"]
            col_rgb = to_rgb(info["color"])
            bg      = info["bg_rgb"]
            dark    = info["dark_rgb"]

            slide = prs.slides.add_slide(blank_layout)

            # ── Gradient background (16 stacked rectangles) ──
            steps = 16
            for i in range(steps):
                t = i / steps
                r_ = int(dark[0]+(bg[0]-dark[0])*t)
                g_ = int(dark[1]+(bg[1]-dark[1])*t)
                b_ = int(dark[2]+(bg[2]-dark[2])*t)
                seg_h = 5.625 / steps
                add_rect(slide, 0, seg_h*i, 10, seg_h+0.05, RGBColor(r_,g_,b_))

            # ── Top bar ──
            add_rect(slide, 0, 0, 10, 0.55, RGBColor(8,8,18))
            add_rect(slide, 0, 0.52, 10, 0.05, col_rgb)
            add_textbox(slide, "3 SORU · 3 DAKİKA",
                        0.2, 0.07, 4, 0.42, 12, bold=True, color=col_rgb, align="left")
            add_textbox(slide, "● YAYIN",
                        8.5, 0.07, 1.3, 0.42, 9, bold=True, color=RGBColor(255,60,60), align="right")

            # ── Orb ──
            orbX, orbY, orbR = 4.25, 1.45, 1.5   # top-left corner coords for oval
            # Glow rings (3 layers)
            for gi in range(3, 0, -1):
                gr = orbR + gi * 0.18
                gx = (10 - gr) / 2
                gy = orbY - (gr - orbR) / 2
                add_oval(slide, gx, gy, gr, gr, col_rgb)
            # Main orb
            add_oval(slide, orbX, orbY, orbR, orbR, col_rgb)
            # Highlight
            add_oval(slide, orbX+0.18, orbY+0.14, 0.4, 0.2, RGBColor(255,255,255))

            # Emoji
            add_textbox(slide, info["emoji"], orbX, orbY+0.3, orbR, 0.8, 30, align="center")
            # Name
            add_textbox(slide, seg["character"],
                        3.0, orbY+orbR+0.08, 4.0, 0.42, 18, bold=True, align="center")
            # Role
            add_textbox(slide, info.get("role","").upper(),
                        3.0, orbY+orbR+0.52, 4.0, 0.28, 8, bold=True, color=col_rgb, align="center")

            # ── Wave bars ──
            wave_heights = [0.12,0.22,0.18,0.30,0.22,0.30,0.18,0.22,0.12]
            waveY = orbY + orbR + 0.88
            for wi, wh in enumerate(wave_heights):
                bx = 4.4 + wi * 0.145
                add_rect(slide, bx, waveY-wh, 0.09, wh, col_rgb)

            # ── Speech bubble ──
            bubY = 3.72
            add_rect(slide, 0.5, bubY+0.05, 9.0, 1.35, RGBColor(12,12,30))   # shadow
            add_rect(slide, 0.5, bubY, 9.0, 1.35, RGBColor(240,240,252),     # bubble
                     line_rgb=col_rgb)
            # Bubble pointer
            add_rect(slide, 4.85, bubY-0.12, 0.3, 0.15, RGBColor(240,240,252))

            lines    = wrap_text(seg["text"], 90)
            display  = "\n".join(lines[:4])
            fsz      = 13 if len(seg["text"]) > 120 else 14
            add_textbox(slide, display,
                        0.7, bubY+0.12, 8.6, 1.08, fsz,
                        color=RGBColor(24,16,58), align="center")

            # ── Bottom bar ──
            add_rect(slide, 0, 5.23, 10, 0.395, RGBColor(8,8,18))
            add_rect(slide, 0, 5.23, 10, 0.03, col_rgb)
            add_textbox(slide, f"{seg['character']}  ·  {info.get('role','')}",
                        0.2, 5.24, 5.5, 0.34, 8, bold=True, color=col_rgb, align="left")
            add_textbox(slide, f"{idx+1} / {total}",
                        8.5, 5.24, 1.3, 0.34, 8,
                        color=RGBColor(170,170,204), align="right")

            # ── Progress bar ──
            prog_w = 10 * (idx+1) / total
            add_rect(slide, 0, 5.565, 10, 0.06, RGBColor(26,26,46))
            add_rect(slide, 0, 5.565, prog_w, 0.06, col_rgb)

            # ── Speaker notes ──
            dur = 3.0
            if audio_segs:
                for as_ in audio_segs:
                    if as_["character"] == seg["character"]:
                        dur = as_.get("duration", 3.0)
                        break
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = (
                f"{seg['character']} ({info.get('role','')}): {seg['text']}\n\n"
                f"Süre: ~{dur:.0f} saniye"
            )

        buf = io.BytesIO()
        prs.save(buf)
        buf.seek(0)
        return buf.read()


# ══════════════════════════════════════════════════════════════
# 9. HTML SLIDE BUILDER
# ══════════════════════════════════════════════════════════════

def build_slide_html(segments: list, audio_map: dict = None) -> str:
    data = json.dumps([
        {
            "char":  s["character"],
            "text":  s["text"],
            "emoji": s["info"]["emoji"],
            "color": s["info"]["color"],
            "role":  s["info"].get("role",""),
            "bg":    list(s["info"].get("bg_rgb",  [20,40,80])),
            "dark":  list(s["info"].get("dark_rgb",[5,10,25])),
            "anim":  s["info"].get("animation","pulse"),
            "audio": (audio_map or {}).get(s["character"], ""),
        }
        for s in segments
    ], ensure_ascii=False)

    return """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{--gold:#C9A84C;}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'DM Sans',sans-serif;background:#06060f;color:#eee;height:100vh;overflow:hidden;display:flex;flex-direction:column;}
#topbar{height:52px;flex-shrink:0;background:rgba(6,6,18,.97);display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-bottom:2px solid var(--gold);}
#show-title{font-family:'DM Serif Display',serif;font-size:16px;letter-spacing:.12em;color:var(--gold);}
#live-dot{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:#ff5050;}
#live-dot span{width:8px;height:8px;border-radius:50%;background:#ff5050;animation:lp 1.2s ease-in-out infinite;}
@keyframes lp{0%,100%{opacity:1}50%{opacity:.3}}
#prog{height:3px;flex-shrink:0;background:rgba(255,255,255,.08);}
#pfill{height:100%;width:0%;transition:width .5s ease;}
#stage{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px 32px;position:relative;transition:background .7s;}
#stage::before{content:'';position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:55px 55px;pointer-events:none;}
.orb{width:130px;height:130px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:56px;position:relative;margin-bottom:8px;}
.orb::after{content:'';position:absolute;top:16px;left:24px;width:34px;height:16px;border-radius:50%;background:rgba(255,255,255,.22);transform:rotate(-20deg);}
.char-name{font-family:'DM Serif Display',serif;font-size:22px;letter-spacing:.06em;margin-bottom:4px;}
.char-role{font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;opacity:.7;margin-bottom:18px;}
.waves{display:flex;gap:4px;align-items:flex-end;height:32px;margin-bottom:16px;}
.wb{width:7px;border-radius:4px;animation:wb .5s ease-in-out infinite;}
@keyframes wb{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}
.bubble{background:rgba(248,248,255,.11);backdrop-filter:blur(20px);border-radius:20px;padding:20px 32px;max-width:700px;width:100%;text-align:center;font-size:17px;line-height:1.75;border:1.5px solid rgba(255,255,255,.13);box-shadow:0 16px 60px rgba(0,0,0,.5);position:relative;}
.bubble::before{content:'';position:absolute;top:-13px;left:50%;transform:translateX(-50%);border:13px solid transparent;border-bottom-color:rgba(248,248,255,.11);}
#ctrl{display:flex;gap:8px;align-items:center;justify-content:center;padding:12px;background:rgba(6,6,18,.85);border-top:1px solid rgba(255,255,255,.07);flex-shrink:0;}
button{padding:8px 18px;border:none;border-radius:7px;cursor:pointer;font-size:12px;font-weight:700;transition:all .18s;}
#bprev{background:rgba(255,255,255,.09);color:#fff;}
#bnext{background:#1a6e3a;color:#fff;}
#bplay{background:#1a3f6e;color:#fff;}
button:hover{transform:translateY(-2px);filter:brightness(1.2);}
#cnt{color:rgba(255,255,255,.35);font-size:12px;min-width:48px;text-align:center;}
#botbar{height:38px;flex-shrink:0;background:rgba(6,6,18,.95);display:flex;align-items:center;justify-content:space-between;padding:0 24px;border-top:2px solid rgba(255,255,255,.07);}
#char-info{font-size:12px;font-weight:600;}
#slide-no{font-size:11px;color:rgba(255,255,255,.35);}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-18px)}}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.12)}}
@keyframes float{0%,100%{transform:translateY(-9px) rotate(-3deg)}50%{transform:translateY(9px) rotate(3deg)}}
@keyframes slideUp{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:translateY(0)}}
.in{animation:slideUp .42s ease both;}
</style>
</head>
<body>
<div id="topbar">
  <div id="show-title">3 SORU · 3 DAKİKA</div>
  <div id="live-dot"><span></span>YAYIN</div>
</div>
<div id="prog"><div id="pfill"></div></div>
<div id="stage">
  <div class="orb" id="orb">🎤</div>
  <div class="char-name" id="cname">—</div>
  <div class="char-role" id="crole">—</div>
  <div class="waves" id="waves"></div>
  <div class="bubble"><span id="btext"></span></div>
</div>
<div id="ctrl">
  <button id="bprev" onclick="go(-1)">◀ Geri</button>
  <span id="cnt">1/1</span>
  <button id="bplay" onclick="togglePlay()">▶ Oynat</button>
  <button id="bnext" onclick="go(1)">İleri ▶</button>
</div>
<div id="botbar">
  <div id="char-info"></div>
  <div id="slide-no"></div>
</div>
<audio id="player" style="display:none"></audio>
<script>
const SLIDES=__DATA__;
let cur=0,playing=false,timer=null;
function rgb(a){return `rgb(${a[0]},${a[1]},${a[2]})`;}
function render(i){
  const s=SLIDES[i];
  document.getElementById('stage').style.background=
    `linear-gradient(160deg,${rgb(s.dark)} 0%,${rgb(s.bg)} 100%)`;
  const orb=document.getElementById('orb');
  orb.textContent=s.emoji;
  orb.style.background=`radial-gradient(circle at 35% 38%,${s.color}cc,${s.color}33)`;
  orb.style.boxShadow=`0 0 55px ${s.color}44`;
  orb.style.animation='none'; void orb.offsetWidth;
  orb.style.animation=s.anim+' .85s ease-in-out infinite';
  document.getElementById('cname').textContent=s.char;
  document.getElementById('cname').style.color=s.color;
  document.getElementById('crole').textContent=s.role;
  document.getElementById('crole').style.color=s.color;
  document.querySelector('.bubble').style.borderColor=s.color+'44';
  document.getElementById('btext').textContent=s.text;
  const wv=document.getElementById('waves');
  wv.innerHTML='';
  for(let j=0;j<11;j++){
    const b=document.createElement('div');
    b.className='wb';
    b.style.background=s.color;
    b.style.height=(8+Math.random()*26)+'px';
    b.style.animationDelay=(j*.06)+'s';
    b.style.animationDuration=(.32+Math.random()*.42)+'s';
    wv.appendChild(b);
  }
  document.getElementById('stage').className='in';
  document.getElementById('pfill').style.width=((i+1)/SLIDES.length*100)+'%';
  document.getElementById('pfill').style.background=s.color;
  document.getElementById('cnt').textContent=(i+1)+' / '+SLIDES.length;
  document.getElementById('char-info').textContent=s.char+' · '+s.role;
  document.getElementById('char-info').style.color=s.color;
  document.getElementById('slide-no').textContent=(i+1)+' / '+SLIDES.length;
  if(s.audio){
    const p=document.getElementById('player');
    p.src='data:audio/mp3;base64,'+s.audio;
    p.play().catch(()=>{});
  }
}
function go(d){cur=(cur+d+SLIDES.length)%SLIDES.length;render(cur);}
function togglePlay(){
  playing=!playing;
  document.getElementById('bplay').textContent=playing?'⏸ Durdur':'▶ Oynat';
  if(playing)loop();
  else{clearTimeout(timer);document.getElementById('player').pause();}
}
function loop(){
  if(!playing)return;
  const s=SLIDES[cur];
  if(s.audio){
    const p=document.getElementById('player');
    p.onended=()=>{if(playing){if(cur===SLIDES.length-1){playing=false;document.getElementById('bplay').textContent='▶ Oynat';}else{go(1);loop();}}};
  } else {
    timer=setTimeout(()=>{if(playing){go(1);loop();}},4500);
  }
}
if(SLIDES.length>0)render(0);
</script>
</body>
</html>""".replace("__DATA__", data)


# ══════════════════════════════════════════════════════════════
# 10. CSS
# ══════════════════════════════════════════════════════════════

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;600;700&family=JetBrains+Mono:wght@400&display=swap');
:root{--gold:#C9A84C;}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;}
.stApp{background:radial-gradient(ellipse at 20% 50%,#0d1a2e 0%,#06060f 60%);color:#e8e8f0;}
section[data-testid="stSidebar"]{background:rgba(6,6,18,.97);border-right:1px solid rgba(201,168,76,.15);}
.hdr{text-align:center;padding:1.4rem 1rem .8rem;border-bottom:1px solid rgba(201,168,76,.15);margin-bottom:1rem;}
.hdr h1{font-family:'DM Serif Display',serif;font-size:2.4rem;font-weight:400;letter-spacing:.05em;background:linear-gradient(90deg,#C9A84C,#f0d080,#C9A84C);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:.2rem;}
.hdr p{color:#667;font-size:.82rem;letter-spacing:.1em;text-transform:uppercase;}
.sc{border-radius:10px;padding:.8rem 1rem;margin:.4rem 0;border-left:3px solid;background:rgba(255,255,255,.03);}
.sc-c{font-size:.66rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;margin-bottom:.25rem;}
.sc-t{font-size:.88rem;line-height:1.6;color:#bbc;}
.sr{display:flex;gap:1rem;padding:.6rem .9rem;background:rgba(201,168,76,.07);border-radius:8px;margin:.5rem 0;font-size:.77rem;color:#888;border:1px solid rgba(201,168,76,.15);}
.sr strong{color:#C9A84C;}
.bdg{display:inline-flex;align-items:center;gap:.3rem;padding:.24rem .62rem;border-radius:50px;font-size:.7rem;font-weight:700;margin:.15rem;}
.bok{background:rgba(160,200,120,.1);color:#A0C878;border:1px solid rgba(160,200,120,.25);}
.bwn{background:rgba(220,80,80,.1);color:#E07B7B;border:1px solid rgba(220,80,80,.25);}
.sct{font-size:.63rem;letter-spacing:.16em;text-transform:uppercase;color:#445;margin:.7rem 0 .32rem;}
audio{width:100%;border-radius:7px;margin:3px 0;}
textarea{background:rgba(255,255,255,.04)!important;border-radius:10px!important;color:#eee!important;font-family:'JetBrains Mono',monospace!important;font-size:.82rem!important;border:1px solid rgba(201,168,76,.15)!important;}
hr{border-color:rgba(255,255,255,.06);}
</style>
"""

# ══════════════════════════════════════════════════════════════
# 11. STATE
# ══════════════════════════════════════════════════════════════

def init_state():
    defaults = dict(
        segs=[], audio_segs=[], full_audio=None,
        pres_html="", history=[], voice_map={},
        video_bytes=None, pptx_bytes=None,
    )
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ══════════════════════════════════════════════════════════════
# 12. SIDEBAR
# ══════════════════════════════════════════════════════════════

def sidebar():
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:1rem 0 .5rem;">'
            '<div style="font-family:serif;font-size:1.3rem;color:#C9A84C;letter-spacing:.1em;">🎙️ STÜDYO</div>'
            '<div style="font-size:.65rem;color:#445;letter-spacing:.15em;text-transform:uppercase;">3 Soru 3 Dakika</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("---")

        st.markdown('<p class="sct">🎤 Kendi Sesinizi Yükleyin</p>', unsafe_allow_html=True)
        st.caption("Her karaktere farklı ses atayabilir veya hepsine aynı sesi verebilirsiniz.")

        voice_map = {}
        use_single = st.checkbox("Hepsi için tek ses kullan", value=True)

        if use_single:
            uf = st.file_uploader("Genel ses (MP3/WAV)", type=["mp3","wav","m4a","ogg"], key="voice_single")
            if uf:
                audio_bytes = uf.read()
                for ch in CHARACTERS:
                    voice_map[ch] = audio_bytes
                st.audio(audio_bytes, format="audio/mp3")
                st.success(f"✅ {len(CHARACTERS)} karaktere atandı")
        else:
            for ch, info in CHARACTERS.items():
                st.markdown(
                    f'<div style="font-size:.75rem;font-weight:700;color:{info["color"]};margin:.5rem 0 .15rem;">'
                    f'{info["emoji"]} {ch} · {info["role"]}</div>',
                    unsafe_allow_html=True,
                )
                uf = st.file_uploader(f"{ch} ses", type=["mp3","wav","m4a","ogg"],
                                      key=f"voice_{ch}", label_visibility="collapsed")
                if uf:
                    ab = uf.read()
                    voice_map[ch] = ab
                    st.audio(ab, format="audio/mp3")

        if voice_map:
            st.session_state.voice_map = voice_map

        st.markdown("---")

        # Kütüphane durumu — TÜM kontrollar try/except ile sarılı
        st.markdown('<p class="sct">📦 Sistem</p>', unsafe_allow_html=True)

        for lib, name in [("PIL","Pillow"), ("imageio","imageio"), ("reportlab","reportlab"), ("pptx","python-pptx")]:
            try:
                __import__(lib)
                st.markdown(f"🟢 {name}")
            except ImportError:
                st.markdown(f"🔴 {name}")

        # ffmpeg — safe check
        ffmpeg_path = get_ffmpeg()
        if ffmpeg_path:
            st.markdown("🟢 ffmpeg")
        else:
            st.markdown("🟡 ffmpeg (video devre dışı)")

        st.markdown("---")
        st.caption("v6.0 · Streamlit Cloud uyumlu")

    return st.session_state.get("voice_map", {})


# ══════════════════════════════════════════════════════════════
# 13. PODCAST BUILD
# ══════════════════════════════════════════════════════════════

def build_podcast(segs: list, voice_map: dict) -> list:
    vm  = VoiceManager(voice_map)
    out = []
    n   = len(segs)
    pb  = st.progress(0, "Ses segmentleri hazırlanıyor…")
    ph  = st.empty()

    for i, seg in enumerate(segs):
        ch    = seg["character"]
        ph.markdown(f'🎙️ **{seg["info"]["emoji"]} {ch}** hazırlanıyor… ({i+1}/{n})')
        audio = vm.get_audio(ch)
        dur   = mp3_duration(audio) if audio else 3.0
        out.append({**seg, "audio": audio, "duration": dur})
        pb.progress((i+1)/n, f"{i+1}/{n}")
        time.sleep(0.03)

    ph.success(f"✅ {n} segment hazır!")
    return out


# ══════════════════════════════════════════════════════════════
# 14. MAIN
# ══════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="3 Soru 3 Dakika · Stüdyo",
        page_icon="🎙️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    init_state()
    voice_map = sidebar()

    st.markdown(
        '<div class="hdr"><h1>3 Soru · 3 Dakika</h1>'
        '<p>Profesyonel Podcast &amp; Sunum Stüdyosu</p></div>',
        unsafe_allow_html=True,
    )

    tab_script, tab_live, tab_pptx, tab_video, tab_pdf = st.tabs(
        ["✏️ Senaryo", "🖥️ Canlı Sunum", "📊 PowerPoint", "🎞️ Video", "📄 PDF"]
    )

    # ══ TAB 1: Senaryo ════════════════════════════════════
    with tab_script:
        col_l, col_r = st.columns([1,1], gap="large")

        with col_l:
            st.markdown('<p class="sct">📂 Hazır Şablonlar</p>', unsafe_allow_html=True)
            tc = st.columns(3)
            for idx2, (lbl, content) in enumerate(TEMPLATES.items()):
                with tc[idx2 % 3]:
                    if st.button(lbl, use_container_width=True):
                        st.session_state["_tpl"] = content

            script = st.text_area(
                "Senaryo",
                value=st.session_state.get("_tpl",""),
                height=380,
                placeholder="Elif: Merhaba!\nEcem: Hoş geldiniz!\nEba: Bugünün konusu…",
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

            st.markdown('<p class="sct">🔊 Ses Durumu</p>', unsafe_allow_html=True)
            vm_now = st.session_state.get("voice_map",{})
            badges = ""
            for ch, info in CHARACTERS.items():
                ok  = ch in vm_now
                cls = "bok" if ok else "bwn"
                ic  = "✓" if ok else "✗"
                badges += f'<span class="bdg {cls}">{info["emoji"]} {ch} {ic}</span>'
            st.markdown(badges, unsafe_allow_html=True)
            if not vm_now:
                st.info("💡 Sol panelden ses dosyanızı yükleyin.")

        with col_r:
            st.markdown('<p class="sct">👁️ Önizleme</p>', unsafe_allow_html=True)
            for s in st.session_state.segs:
                c = s["info"]["color"]
                st.markdown(
                    f'<div class="sc" style="border-color:{c};">'
                    f'<div class="sc-c" style="color:{c};">'
                    f'{s["info"]["emoji"]} {s["character"]} · {s["info"]["role"]}</div>'
                    f'<div class="sc-t">{s["text"]}</div></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            b1, b2 = st.columns(2)
            gen_btn = b1.button("🚀 Podcast Oluştur", use_container_width=True, type="primary")
            clr_btn = b2.button("🗑️ Temizle", use_container_width=True)

            if clr_btn:
                for k in ("segs","audio_segs","pres_html","video_bytes","pptx_bytes"):
                    st.session_state[k] = [] if isinstance(st.session_state.get(k), list) else None
                st.session_state.full_audio = None
                st.session_state.pres_html  = ""
                if "_tpl" in st.session_state:
                    del st.session_state["_tpl"]
                st.rerun()

            if gen_btn:
                vm_now = st.session_state.get("voice_map",{})
                if not script.strip():
                    st.warning("⚠️ Senaryo alanı boş.")
                elif not vm_now:
                    st.error("❌ Sol panelden ses dosyanızı yükleyin.")
                else:
                    parser = ScriptParser()
                    segs   = parser.parse(script)
                    st.session_state.segs = segs

                    asegs = build_podcast(segs, vm_now)
                    st.session_state.audio_segs = asegs

                    combined = b"".join(s["audio"] for s in asegs if s.get("audio"))
                    st.session_state.full_audio = combined or None

                    audio_b64 = {ch: audio_to_b64(ab) for ch, ab in vm_now.items()}
                    st.session_state.pres_html = build_slide_html(segs, audio_b64)
                    st.session_state.video_bytes = None
                    st.session_state.pptx_bytes  = None
                    st.session_state.history.append({"preview": script[:55]+"…", "n": len(segs)})
                    st.rerun()

            # Segment player
            if st.session_state.audio_segs:
                st.markdown('<p class="sct">🎵 Segmentler</p>', unsafe_allow_html=True)
                for seg in st.session_state.audio_segs:
                    label = f"{seg['info']['emoji']} {seg['character']}: {seg['text'][:48]}…"
                    with st.expander(label, expanded=False):
                        if seg.get("audio"):
                            st.audio(seg["audio"], format="audio/mp3")
                            st.caption(f"⏱️ ~{seg['duration']:.1f} sn")
                        else:
                            st.caption("⚠️ Ses yok.")

                if st.session_state.full_audio:
                    st.markdown("---")
                    st.markdown('<p class="sct">🎧 Tam Podcast</p>', unsafe_allow_html=True)
                    st.audio(st.session_state.full_audio, format="audio/mp3")
                    st.download_button(
                        "⬇️ Podcast MP3 İndir",
                        data=st.session_state.full_audio,
                        file_name="3soru3dakika.mp3",
                        mime="audio/mpeg",
                        use_container_width=True,
                    )

    # ══ TAB 2: Canlı Sunum ════════════════════════════════
    with tab_live:
        if not st.session_state.segs:
            st.info("ℹ️ Senaryo sekmesinde senaryo girin ve podcast oluşturun.")
        else:
            if not st.session_state.pres_html:
                vm_now    = st.session_state.get("voice_map",{})
                audio_b64 = {ch: audio_to_b64(ab) for ch, ab in vm_now.items()}
                st.session_state.pres_html = build_slide_html(st.session_state.segs, audio_b64)
            st.components.v1.html(st.session_state.pres_html, height=640, scrolling=False)
            st.caption("**◀ ▶** manuel gezinme · **▶ Oynat** otomatik sıralı oynatma · ses yüklendiyse her slayta otomatik çalar")

    # ══ TAB 3: PowerPoint ═════════════════════════════════
    with tab_pptx:
        st.markdown(
            '<div style="font-family:serif;font-size:1.5rem;color:#C9A84C;margin-bottom:.5rem;">'
            '📊 PowerPoint Slayt Kitapçığı</div>',
            unsafe_allow_html=True,
        )
        pm = PPTXMaker()

        if not pm.ready():
            st.error("❌ `pip install python-pptx` gerekli")
        elif not st.session_state.segs:
            st.info("ℹ️ Önce Senaryo sekmesinden senaryo girin.")
        else:
            n_seg = len(st.session_state.segs)
            st.info(
                f"**{n_seg}** slayt · python-pptx · 16:9 · "
                "Gradient arka plan, karakter orb, konuşma balonu, dalga barları, "
                "ilerleme çubuğu, konuşmacı notları"
            )

            col1, col2 = st.columns([3,1])
            with col1:
                gen_pptx = st.button("📊 PPTX Oluştur", type="primary", use_container_width=True)
            with col2:
                if st.button("🔄 Sıfırla", use_container_width=True):
                    st.session_state.pptx_bytes = None
                    st.rerun()

            if gen_pptx:
                with st.spinner("PPTX oluşturuluyor…"):
                    pptx = pm.make(
                        st.session_state.segs,
                        audio_segs=st.session_state.audio_segs or None,
                    )
                if pptx:
                    st.session_state.pptx_bytes = pptx
                    st.success(f"✅ PPTX hazır! ({len(pptx)//1024} KB)")
                else:
                    st.error("❌ PPTX oluşturulamadı.")

            if st.session_state.pptx_bytes:
                st.success(f"✅ PPTX hazır — {len(st.session_state.pptx_bytes)//1024} KB")
                st.download_button(
                    label="⬇️ PowerPoint İndir (.pptx)",
                    data=st.session_state.pptx_bytes,
                    file_name="3soru3dakika.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                    type="primary",
                )
                st.markdown("---")
                for i, seg in enumerate(st.session_state.segs):
                    c = seg["info"]["color"]
                    st.markdown(
                        f'<div class="sc" style="border-color:{c};">'
                        f'<div class="sc-c" style="color:{c};">Slayt {i+1} · {seg["info"]["emoji"]} {seg["character"]}</div>'
                        f'<div class="sc-t">{seg["text"][:120]}{"…" if len(seg["text"])>120 else ""}</div></div>',
                        unsafe_allow_html=True,
                    )

    # ══ TAB 4: Video ══════════════════════════════════════
    with tab_video:
        st.markdown(
            '<div style="font-family:serif;font-size:1.5rem;color:#C9A84C;margin-bottom:.5rem;">'
            '🎞️ MP4 Video Üretici</div>',
            unsafe_allow_html=True,
        )
        vm_maker = VideoMaker()

        if not vm_maker.has_pil:
            st.error("❌ Pillow kurulu değil.")
        elif not vm_maker.has_imageio:
            st.error("❌ imageio kurulu değil.")
        elif not vm_maker.ffmpeg:
            st.warning(
                "⚠️ ffmpeg bu ortamda bulunamadı. Video üretimi için ffmpeg gereklidir. "
                "Streamlit Cloud'da `packages.txt` dosyanıza `ffmpeg` ekleyin."
            )
        elif not st.session_state.audio_segs:
            st.info("ℹ️ Önce Senaryo sekmesinde podcast oluşturun.")
        else:
            total_dur = sum(s.get("duration",3.0) for s in st.session_state.audio_segs)
            st.info(
                f"**{len(st.session_state.audio_segs)}** segment · "
                f"~**{total_dur:.0f} sn** · **{VIDEO_W}×{VIDEO_H}** · **{VIDEO_FPS} FPS**"
            )

            col1, col2 = st.columns([3,1])
            with col1:
                make_video = st.button("🎬 Video Oluştur", type="primary", use_container_width=True)
            with col2:
                if st.button("🔄 Sıfırla ", use_container_width=True):
                    st.session_state.video_bytes = None
                    st.rerun()

            if make_video:
                sph = st.empty()
                pph = st.progress(0)
                def cb(v, m):
                    pph.progress(min(float(v), 1.0), m)
                    sph.markdown(f"⚙️ {m}")
                with st.spinner("Video işleniyor… (1–3 dk sürebilir)"):
                    vbytes = vm_maker.make(st.session_state.audio_segs, cb)
                if vbytes:
                    st.session_state.video_bytes = vbytes
                    st.success(f"✅ Video hazır! ({len(vbytes)//1024} KB)")
                else:
                    st.error("❌ Video oluşturulamadı.")

            if st.session_state.video_bytes:
                vb = st.session_state.video_bytes
                st.success(f"✅ Video hazır — {len(vb)//1024} KB")
                st.video(vb)
                st.download_button(
                    label="⬇️ MP4 Video İndir",
                    data=vb,
                    file_name="3soru3dakika.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                    type="primary",
                )
                # Alternatif HTML indirme linki
                b64v = base64.b64encode(vb).decode()
                st.markdown(
                    f'<a href="data:video/mp4;base64,{b64v}" download="3soru3dakika.mp4" '
                    f'style="display:inline-block;padding:10px 22px;background:#1a5c38;'
                    f'color:#fff;border-radius:8px;font-weight:700;font-size:13px;'
                    f'text-decoration:none;margin-top:6px;">📥 Alternatif İndir Linki</a>',
                    unsafe_allow_html=True,
                )

    # ══ TAB 5: PDF ════════════════════════════════════════
    with tab_pdf:
        st.markdown(
            '<div style="font-family:serif;font-size:1.5rem;color:#C9A84C;margin-bottom:.5rem;">'
            '📄 PDF Slayt Kitapçığı</div>',
            unsafe_allow_html=True,
        )
        pmaker = PDFMaker()
        if not pmaker.ready():
            st.error("❌ `pip install reportlab` gerekli")
        elif not st.session_state.segs:
            st.info("ℹ️ Önce Senaryo sekmesinden senaryo girin.")
        else:
            st.info(f"**{len(st.session_state.segs)}** slayt · Broadcast tasarım · Landscape A4")
            if st.button("📄 PDF Oluştur", type="primary", use_container_width=True):
                with st.spinner("PDF oluşturuluyor…"):
                    pdf = pmaker.make(st.session_state.segs)
                if pdf:
                    st.success(f"✅ PDF hazır! ({len(pdf)//1024} KB)")
                    st.download_button(
                        label="⬇️ PDF İndir",
                        data=pdf,
                        file_name="3soru3dakika.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary",
                    )
                else:
                    st.error("❌ PDF oluşturulamadı.")

        if st.session_state.history:
            st.markdown("---")
            st.markdown('<p class="sct">📜 Geçmiş</p>', unsafe_allow_html=True)
            for h in reversed(st.session_state.history[-5:]):
                st.markdown(
                    f'<div style="font-size:.82rem;color:#667;padding:.2rem 0;">'
                    f'🎙️ {h["preview"]} — {h["n"]} satır</div>',
                    unsafe_allow_html=True,
                )


if __name__ == "__main__":
    main()
