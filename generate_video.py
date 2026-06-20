from __future__ import annotations

import asyncio
import base64
import json
import math
import os
import shutil
import subprocess
import sys
import textwrap
import wave
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
IMAGES = ASSETS / "images"
AUDIO = ASSETS / "audio"
TEMP = ASSETS / "temp"
DIST = ROOT / "dist"
WIDTH, HEIGHT = 1080, 1920
FPS = 24
TARGET_SECONDS = 54.0

SCRIPT = """如果你的手机日程表突然提醒你：

8:15，不要进入教学楼三楼男厕所。

你会信吗？

在我的新网文设定里，全球副本突然降临。

学校变成考场。
地铁变成迷宫。
医院夜班开始点名死人。

所有人都开始觉醒能力。

有人觉醒火焰。
有人觉醒雷霆。
有人觉醒召唤。

但主角林昼觉醒的，却是一张日程表。

它不会让他变强。
不会给他武器。
也不会直接告诉他答案。

它只会提醒他：

8:20，不要回答自己的名字。

9:00，通关第一次副本。

别人以为这是废物能力。

但林昼很快发现，副本真正考的不是战斗。

而是审题。

这是一个AI网文实验。

我会用AI辅助创作，公开连载，公开测试。

看看AI到底能不能写出一本真正让人追更的小说。

评论区可以设计副本规则。

好玩的，我真写进下一章。"""

SUBTITLE_LINES = [
    "如果你的手机日程表突然提醒你", "8:15，不要进入教学楼三楼男厕所", "你会信吗",
    "在我的新网文设定里|全球副本突然降临", "学校变成考场|地铁变成迷宫",
    "医院夜班开始点名死人", "所有人都开始觉醒能力", "有人觉醒火焰|有人觉醒雷霆",
    "有人觉醒召唤", "但主角林昼觉醒的|却是一张日程表", "它不会让他变强",
    "不会给他武器|也不会直接告诉他答案", "它只会提醒他",
    "8:20，不要回答自己的名字", "9:00，通关第一次副本", "别人以为这是废物能力",
    "但林昼很快发现|副本真正考的不是战斗", "而是审题", "这是一个AI网文实验",
    "我会用AI辅助创作|公开连载，公开测试", "看看AI到底能不能写出一本|真正让人追更的小说",
    "评论区可以设计副本规则", "好玩的，我真写进下一章",
]

SCENES = [
    ("日程表发来警告", "8:15  不要进入三楼男厕所", "手机震动 / 规则已刷新"),
    ("青曜高中", "教学楼走廊进入异常状态", "虚构地点：星澜市青曜高中"),
    ("今日生存日程", "8:15 禁止进入 · 8:20 禁止回应", "9:00  通关第一次副本"),
    ("门消失了", "三楼尽头只剩一面白墙", "没有出口，也没有门把手"),
    ("全球副本化", "SYSTEM COUNTDOWN  00:59:59", "星澜市区域规则加载中"),
    ("能力觉醒", "火焰 · 雷霆 · 召唤 · 预知", "所有人都获得了战斗能力"),
    ("林昼", "他的能力只有一张日程表", "冷静、计划、寻找规则漏洞"),
    ("第三节课开始", "点名册正在自动翻页", "不要回答自己的名字"),
    ("AI 网文实验", "公开连载 · 公开测试 · 评论共创", "好玩的规则，写进下一章"),
]

IMAGE_PROMPTS = [
    "black smartphone notification floating in darkness, red warning UI, cinematic",
    "fictional Qingyao High School corridor, cold blue lights, suspense, no people identifiable",
    "smartphone calendar close-up with futuristic warning entries, Chinese UI style",
    "fictional school corridor where a restroom door has become a seamless white wall, surprised students, nonviolent",
    "fictional futuristic city Xinglan under a red system countdown in the sky, cinematic",
    "fictional students awakening fire lightning summoning holograms and prediction screens, nonviolent",
    "fictional Chinese male student Lin Zhou calmly looking at smartphone in blue school corridor",
    "classroom blackboard and an attendance book turning pages by itself, suspense, non-horror",
    "AI writing workstation showing novel outline chapter board and community comments, futuristic",
]


def log(message: str) -> None:
    print(f"[builder] {message}", flush=True)


def ensure_dirs() -> None:
    for path in (DIST, IMAGES, AUDIO, TEMP, ASSETS / "fonts"):
        path.mkdir(parents=True, exist_ok=True)


def load_env() -> dict[str, str]:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:
        env_path = ROOT / ".env"
        if env_path.exists():
            for raw in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in raw and not raw.lstrip().startswith("#"):
                    key, value = raw.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
    return {
        "key": os.getenv("OPENAI_API_KEY", "").strip(),
        "images": os.getenv("USE_OPENAI_IMAGES", "true").lower() == "true",
        "tts": os.getenv("USE_OPENAI_TTS", "true").lower() == "true",
    }


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for item in candidates:
        if item.exists():
            return ImageFont.truetype(str(item), size=size)
    return ImageFont.load_default()


def gradient_background(index: int) -> Image.Image:
    y = np.linspace(0, 1, HEIGHT, dtype=np.float32)[:, None]
    palettes = [
        ((3, 8, 18), (17, 29, 54)), ((4, 18, 30), (8, 44, 61)),
        ((5, 8, 20), (24, 18, 46)), ((8, 20, 32), (25, 39, 53)),
        ((12, 5, 18), (42, 8, 24)), ((3, 16, 28), (9, 48, 67)),
        ((4, 11, 20), (17, 37, 55)), ((7, 14, 24), (28, 23, 39)),
        ((4, 11, 22), (13, 38, 55)),
    ]
    top, bottom = palettes[index % len(palettes)]
    arr = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for channel in range(3):
        arr[:, :, channel] = (top[channel] * (1 - y) + bottom[channel] * y).astype(np.uint8)
    image = Image.fromarray(arr, "RGB")
    noise = Image.effect_noise((WIDTH, HEIGHT), 12).convert("L")
    noise = ImageEnhance.Contrast(noise).enhance(0.45)
    texture = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(image, texture, 0.07)


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, fnt: ImageFont.ImageFont,
             fill: tuple[int, int, int], stroke: int = 0) -> None:
    box = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    draw.text(((WIDTH - (box[2] - box[0])) / 2, y), text, font=fnt, fill=fill,
              stroke_width=stroke, stroke_fill=(0, 0, 0))


def make_card(index: int, output: Path) -> None:
    image = gradient_background(index)
    draw = ImageDraw.Draw(image, "RGBA")
    accent = (238, 45, 73, 255) if index in (0, 3, 4, 7) else (33, 207, 255, 255)
    draw.rectangle((68, 80, 1012, 86), fill=accent)
    draw.text((72, 116), f"RULE / SCENE  {index + 1:02d}", font=font(28, True), fill=accent)
    for x in range(90, 1040, 150):
        draw.line((x, 260, x + 70, 260), fill=(*accent[:3], 75), width=2)
    if index == 1:
        for depth in range(7):
            inset = 80 + depth * 60
            draw.rectangle((inset, 390 + depth * 65, WIDTH - inset, 1580 - depth * 65),
                           outline=(*accent[:3], 95), width=4)
    elif index == 2:
        draw.rounded_rectangle((100, 300, 980, 1550), radius=58, fill=(7, 12, 24, 235),
                               outline=accent, width=5)
        for row, value in enumerate(("8:15", "8:20", "9:00")):
            yy = 550 + row * 220
            draw.text((170, yy), value, font=font(68, True), fill=accent)
            draw.line((170, yy + 105, 900, yy + 105), fill=(255, 255, 255, 55), width=2)
    elif index == 4:
        for radius in (450, 350, 250):
            draw.ellipse((WIDTH // 2 - radius, 770 - radius, WIDTH // 2 + radius, 770 + radius),
                         outline=(*accent[:3], 65), width=5)
        centered(draw, "00:59:59", 675, font(125, True), accent[:3], 2)
    elif index == 5:
        for x, label, color in [(185, "火", (255, 91, 50, 230)), (420, "雷", (48, 191, 255, 230)),
                                (655, "召", (174, 87, 255, 230)), (890, "预", (255, 219, 65, 230))]:
            draw.ellipse((x - 85, 640, x + 85, 810), fill=(5, 10, 20, 210), outline=color, width=6)
            centered_x = draw.textbbox((0, 0), label, font=font(74, True))
            draw.text((x - (centered_x[2] - centered_x[0]) / 2, 678), label, font=font(74, True), fill=color)
    elif index == 8:
        draw.rounded_rectangle((95, 350, 985, 1420), radius=24, fill=(5, 12, 23, 235),
                               outline=accent, width=4)
        for n, length in enumerate((620, 710, 480, 680, 390, 740, 550)):
            yy = 510 + n * 105
            draw.rounded_rectangle((165, yy, 165 + length, yy + 27), radius=12,
                                   fill=(*accent[:3], 190 if n % 3 == 0 else 80))
    title, subtitle, footer = SCENES[index]
    wrapped = textwrap.wrap(title, width=11)
    base_y = 300 if index not in (2, 4) else 300
    for line_no, line in enumerate(wrapped):
        centered(draw, line, base_y + line_no * 120, font(88, True), (245, 249, 255), 2)
    centered(draw, subtitle, 1480, font(42, True), accent[:3], 1)
    centered(draw, footer, 1570, font(31), (205, 218, 232), 1)
    draw.rectangle((70, 1780, 1010, 1784), fill=(*accent[:3], 110))
    draw.text((70, 1810), "《全球副本化：我的日程表成了通关攻略》", font=font(25), fill=(165, 185, 205))
    image.save(output, quality=95)


def try_openai_image(client, index: int, output: Path) -> bool:
    try:
        prompt = (
            IMAGE_PROMPTS[index] +
            ". Vertical 9:16, photorealistic cinematic suspense technology aesthetic, blue-black palette, "
            "nonviolent, no gore, no real school, no real person, all names and places fictional, no readable text."
        )
        result = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1536")
        data = result.data[0]
        if getattr(data, "b64_json", None):
            raw = base64.b64decode(data.b64_json)
        else:
            import requests
            raw = requests.get(data.url, timeout=90).content
        source = TEMP / f"openai_{index + 1:02d}.png"
        source.write_bytes(raw)
        with Image.open(source) as img:
            img = img.convert("RGB")
            scale = max(WIDTH / img.width, HEIGHT / img.height)
            img = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
            left, top = (img.width - WIDTH) // 2, (img.height - HEIGHT) // 2
            img.crop((left, top, left + WIDTH, top + HEIGHT)).save(output)
        return True
    except Exception as exc:
        log(f"OpenAI image {index + 1} failed ({type(exc).__name__}); using Pillow")
        return False


def generate_images(config: dict[str, str], state: dict) -> list[Path]:
    client = None
    if config["key"] and config["images"]:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config["key"])
        except Exception as exc:
            state["fallbacks"].append(f"OpenAI Images unavailable: {type(exc).__name__}")
    outputs = []
    for index in range(len(SCENES)):
        output = IMAGES / f"scene_{index + 1:02d}.png"
        used_api = bool(client and try_openai_image(client, index, output))
        if not used_api:
            make_card(index, output)
            state["image_mode"] = "pillow"
        else:
            state["openai_images_used"] = True
        outputs.append(output)
    return outputs


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / wav.getframerate()


def try_openai_tts(config: dict[str, str], output: Path, state: dict) -> bool:
    if not config["key"] or not config["tts"]:
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config["key"])
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts", voice="coral", input=SCRIPT,
            instructions="中文普通话，年轻清晰，悬疑但克制，语速稍快。", response_format="wav",
        ) as response:
            response.stream_to_file(output)
        state["openai_tts_used"] = True
        state["voice_mode"] = "openai"
        return True
    except Exception as exc:
        state["fallbacks"].append(f"OpenAI TTS failed: {type(exc).__name__}")
        return False


async def edge_tts_task(output: Path) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(SCRIPT.replace("\n", " "), "zh-CN-XiaoxiaoNeural", rate="+20%")
    await communicate.save(str(output))


def try_edge_tts(output: Path, state: dict, ffmpeg: str | None) -> bool:
    try:
        mp3 = TEMP / "narration_edge.mp3"
        asyncio.run(edge_tts_task(mp3))
        if not ffmpeg:
            return False
        subprocess.run([ffmpeg, "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(output)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        state["voice_mode"] = "edge-tts"
        return True
    except Exception as exc:
        state["fallbacks"].append(f"edge-tts failed: {type(exc).__name__}")
        return False


def try_windows_sapi(output: Path, state: dict) -> bool:
    if os.name != "nt":
        return False
    ps1 = TEMP / "sapi_tts.ps1"
    text_file = TEMP / "narration.txt"
    text_file.write_text(SCRIPT.replace("\n", " "), encoding="utf-8-sig")
    ps1.write_text(
        "param([string]$TextPath,[string]$OutPath)\n"
        "$ErrorActionPreference='Stop'\n"
        "Add-Type -AssemblyName System.Speech\n"
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        "$v=$s.GetInstalledVoices() | Where-Object {$_.VoiceInfo.Culture.Name -eq 'zh-CN'} | Select-Object -First 1\n"
        "if($v){$s.SelectVoice($v.VoiceInfo.Name)}\n"
        "$s.Rate=3; $s.Volume=100\n"
        "$s.SetOutputToWaveFile($OutPath)\n"
        "$s.Speak([IO.File]::ReadAllText($TextPath,[Text.Encoding]::UTF8))\n"
        "$s.Dispose()\n",
        encoding="utf-8-sig",
    )
    try:
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1),
             "-TextPath", str(text_file), "-OutPath", str(output)],
            check=True, timeout=180, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        state["voice_mode"] = "windows-sapi"
        return output.exists() and output.stat().st_size > 1000
    except Exception as exc:
        state["fallbacks"].append(f"Windows SAPI failed: {type(exc).__name__}")
        return False


def make_silence(output: Path, seconds: float = TARGET_SECONDS) -> None:
    samples = np.zeros(int(44100 * seconds), dtype=np.int16)
    write_wav(output, samples, 44100)


def write_wav(path: Path, samples: np.ndarray, rate: int = 44100) -> None:
    samples = np.clip(samples, -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(samples.tobytes())


def normalize_voice(input_path: Path, output_path: Path, ffmpeg: str | None) -> float:
    duration = wav_duration(input_path)
    if duration <= 58.0 or not ffmpeg:
        shutil.copyfile(input_path, output_path)
        return duration
    factor = duration / 58.0
    subprocess.run(
        [ffmpeg, "-y", "-i", str(input_path), "-filter:a", f"atempo={factor:.5f}",
         "-ar", "44100", "-ac", "1", str(output_path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return wav_duration(output_path)


def generate_narration(config: dict[str, str], state: dict, ffmpeg: str | None) -> tuple[Path, float]:
    raw = TEMP / "narration_raw.wav"
    final = AUDIO / "narration.wav"
    for path in (raw, final):
        path.unlink(missing_ok=True)
    ok = try_openai_tts(config, raw, state)
    if not ok:
        ok = try_edge_tts(raw, state, ffmpeg)
    if not ok:
        ok = try_windows_sapi(raw, state)
    if not ok:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 230)
            engine.save_to_file(SCRIPT.replace("\n", " "), str(raw))
            engine.runAndWait()
            ok = raw.exists()
            state["voice_mode"] = "pyttsx3"
        except Exception as exc:
            state["fallbacks"].append(f"pyttsx3 failed: {type(exc).__name__}")
    if not ok:
        make_silence(raw)
        state["voice_mode"] = "silence"
        state["fallbacks"].append("All TTS unavailable; generated silence")
    duration = normalize_voice(raw, final, ffmpeg)
    return final, duration


def generate_background(seconds: float) -> Path:
    rate = 44100
    t = np.arange(int(rate * seconds), dtype=np.float64) / rate
    sweep = 43 + 3 * np.sin(2 * np.pi * 0.035 * t)
    phase = 2 * np.pi * np.cumsum(sweep) / rate
    drone = 1500 * np.sin(phase) + 600 * np.sin(phase * 0.503)
    pulse = 450 * np.sin(2 * np.pi * 0.22 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.04 * t))
    audio = drone + pulse
    for tick in np.arange(0.7, seconds, 1.0):
        start = int(tick * rate)
        length = min(int(0.045 * rate), len(audio) - start)
        if length > 0:
            env = np.exp(-np.linspace(0, 8, length))
            audio[start:start + length] += 3000 * env * np.sin(2 * np.pi * 1250 * np.arange(length) / rate)
    fade = np.minimum(np.minimum(t / 1.5, (seconds - t) / 1.5), 1.0)
    output = AUDIO / "background.wav"
    write_wav(output, audio * np.clip(fade, 0, 1), rate)
    return output


def srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_subtitles(seconds: float) -> list[dict]:
    weights = [max(5, len(item.replace("|", ""))) for item in SUBTITLE_LINES]
    unit = seconds / sum(weights)
    entries, cursor = [], 0.0
    for index, (text, weight) in enumerate(zip(SUBTITLE_LINES, weights), 1):
        end = min(seconds, cursor + weight * unit)
        entries.append({"index": index, "start": cursor, "end": end, "text": text})
        cursor = end
    lines = []
    for entry in entries:
        lines.extend([str(entry["index"]), f"{srt_time(entry['start'])} --> {srt_time(entry['end'])}",
                      entry["text"].replace("|", "\n"), ""])
    (DIST / "subtitles.srt").write_text("\n".join(lines), encoding="utf-8-sig")
    return entries


def subtitle_layer(text: str) -> Image.Image:
    layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    lines = text.split("|")
    fnt = font(48, True)
    boxes = [draw.textbbox((0, 0), line, font=fnt, stroke_width=3) for line in lines]
    block_h = len(lines) * 70
    top = 1590 - block_h // 2
    draw.rounded_rectangle((55, top - 24, 1025, top + block_h + 18), radius=24, fill=(0, 0, 0, 145))
    for n, (line, box) in enumerate(zip(lines, boxes)):
        x = (WIDTH - (box[2] - box[0])) / 2
        draw.text((x, top + n * 70), line, font=fnt, fill=(255, 255, 255, 255),
                  stroke_width=3, stroke_fill=(0, 0, 0, 235))
    return layer


def find_ffmpeg() -> str | None:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def render_silent_video(images: list[Path], subtitles: list[dict], seconds: float) -> Path:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("OpenCV is required for the offline renderer. Install opencv-python.") from exc
    output = TEMP / "silent.mp4"
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open an MP4 video writer.")
    scene_seconds = seconds / len(images)
    total_frames = int(round(seconds * FPS))
    loaded = [np.array(Image.open(path).convert("RGB")) for path in images]
    layers = {entry["index"]: np.array(subtitle_layer(entry["text"])) for entry in subtitles}
    try:
        for frame_no in range(total_frames):
            now = frame_no / FPS
            scene_idx = min(int(now / scene_seconds), len(images) - 1)
            local = (now - scene_idx * scene_seconds) / scene_seconds
            source = loaded[scene_idx]
            zoom = 1.0 + 0.035 * local
            crop_w, crop_h = int(WIDTH / zoom), int(HEIGHT / zoom)
            pan = int(math.sin(local * math.pi) * 18)
            left = max(0, min(WIDTH - crop_w, (WIDTH - crop_w) // 2 + pan))
            top = max(0, min(HEIGHT - crop_h, (HEIGHT - crop_h) // 2))
            frame = cv2.resize(source[top:top + crop_h, left:left + crop_w], (WIDTH, HEIGHT),
                               interpolation=cv2.INTER_LINEAR)
            fade = min(1.0, local / 0.10, (1.0 - local) / 0.08)
            frame = (frame.astype(np.float32) * max(0.0, fade)).astype(np.uint8)
            active = next((e for e in subtitles if e["start"] <= now < e["end"]), None)
            if active:
                overlay = layers[active["index"]]
                alpha = overlay[:, :, 3:4].astype(np.float32) / 255.0
                frame = (frame * (1 - alpha) + overlay[:, :, :3] * alpha).astype(np.uint8)
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            if frame_no % (FPS * 9) == 0:
                log(f"rendering video: {int(frame_no / total_frames * 100)}%")
    finally:
        writer.release()
    return output


def mux_video(ffmpeg: str, silent: Path, narration: Path, background: Path, seconds: float) -> Path:
    output = DIST / "douyin_ai_webnovel_video.mp4"
    command = [
        ffmpeg, "-y", "-i", str(silent), "-i", str(narration), "-i", str(background),
        "-filter_complex",
        f"[1:a]volume=1.0,apad=pad_dur={seconds}[voice];"
        f"[2:a]volume=0.16[bg];[voice][bg]amix=inputs=2:duration=longest:dropout_transition=2[a]",
        "-map", "0:v:0", "-map", "[a]", "-t", f"{seconds:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(output),
    ]
    subprocess.run(command, check=True)
    return output


def make_cover(scene: Path) -> Path:
    with Image.open(scene) as source:
        image = source.convert("RGB").filter(ImageFilter.GaussianBlur(1.2))
    shade = Image.new("RGBA", image.size, (0, 0, 0, 70))
    image = Image.alpha_composite(image.convert("RGBA"), shade)
    draw = ImageDraw.Draw(image, "RGBA")
    draw.rectangle((0, 0, WIDTH, HEIGHT), outline=(235, 42, 70, 255), width=18)
    draw.rounded_rectangle((55, 175, 1025, 775), radius=28, fill=(2, 8, 18, 205),
                           outline=(235, 42, 70, 210), width=4)
    centered(draw, "AI能写出", 230, font(104, True), (255, 255, 255), 3)
    centered(draw, "爆款网文吗？", 370, font(104, True), (255, 221, 66), 3)
    centered(draw, "主角能力：日程表", 570, font(62, True), (255, 72, 91), 2)
    draw.rounded_rectangle((90, 1480, 990, 1675), radius=30, fill=(2, 8, 18, 215))
    centered(draw, "全球副本化 / 规则怪谈 / AI实验", 1540, font(35, True), (225, 237, 248), 1)
    output = DIST / "cover.png"
    image.convert("RGB").save(output)
    return output


def probe_video(ffmpeg: str, path: Path) -> dict:
    probe = str(Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe"))
    if not Path(probe).exists():
        return {"size_bytes": path.stat().st_size}
    try:
        result = subprocess.run(
            [probe, "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_name",
             "-of", "json", str(path)], capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)
    except Exception:
        return {"size_bytes": path.stat().st_size}


def main() -> None:
    ensure_dirs()
    config = load_env()
    state = {
        "openai_configured": bool(config["key"]),
        "openai_images_used": False,
        "openai_tts_used": False,
        "image_mode": "openai" if config["key"] and config["images"] else "pillow",
        "voice_mode": "pending",
        "fallbacks": [],
    }
    (DIST / "script.txt").write_text(SCRIPT, encoding="utf-8-sig")
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "FFmpeg not found. Install imageio-ffmpeg with: python -m pip install imageio-ffmpeg"
        )
    log("generating nine scene images")
    images = generate_images(config, state)
    log("generating narration with automatic fallback")
    narration, voice_seconds = generate_narration(config, state, ffmpeg)
    seconds = min(60.0, max(45.0, voice_seconds + 0.8, TARGET_SECONDS))
    if voice_seconds > seconds:
        seconds = min(60.0, voice_seconds)
    log(f"timeline duration: {seconds:.2f}s; voice mode: {state['voice_mode']}")
    background = generate_background(seconds)
    subtitles = make_subtitles(seconds)
    cover = make_cover(images[6])
    silent = render_silent_video(images, subtitles, seconds)
    log("muxing H.264 video and mixed audio")
    video = mux_video(ffmpeg, silent, narration, background, seconds)
    if not video.exists() or video.stat().st_size < 100_000:
        raise RuntimeError("Final video validation failed: output is missing or too small.")
    manifest = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "project": "AI网文实验抖音宣传视频",
        "fictional_names": ["星澜市", "青曜高中", "林昼"],
        "images": [str(path.relative_to(ROOT)).replace("\\", "/") for path in images],
        "audio": [
            str(narration.relative_to(ROOT)).replace("\\", "/"),
            str(background.relative_to(ROOT)).replace("\\", "/"),
        ],
        "video": str(video.relative_to(ROOT)).replace("\\", "/"),
        "cover": str(cover.relative_to(ROOT)).replace("\\", "/"),
        "subtitles": "dist/subtitles.srt",
        "script": "dist/script.txt",
        "duration_seconds": round(seconds, 3),
        "resolution": [WIDTH, HEIGHT],
        "fps": FPS,
        "api": {
            "openai_configured": state["openai_configured"],
            "openai_images_used": state["openai_images_used"],
            "openai_tts_used": state["openai_tts_used"],
        },
        "fallback": {
            "image_mode": state["image_mode"],
            "voice_mode": state["voice_mode"],
            "events": state["fallbacks"],
        },
        "validation": probe_video(ffmpeg, video),
    }
    (DIST / "assets_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"complete: {video}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[builder] ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
