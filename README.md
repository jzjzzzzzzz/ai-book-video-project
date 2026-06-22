# AI 网文实验抖音宣传视频生成器

生成 9:16、45-60 秒的中文配音宣传视频。云 API 不可用时，会自动使用 Pillow 分镜卡片、Windows 中文语音或 edge-tts，以及程序生成的低频氛围音。

## 项目结构

- `generate_video.py`: 主生成脚本。
- `assets/images/`: 生成或缓存的分镜图片。
- `assets/audio/`: 生成或缓存的旁白和背景音。
- `dist/`: 最终视频、封面、字幕和脚本文稿输出目录。
- `.env.example`: OpenAI 和生成开关的安全配置模板。

## 安装

```powershell
cd video_project
python -m pip install -r requirements.txt
```

系统需有 FFmpeg。安装 `imageio-ffmpeg` 后脚本可自动使用其内置 FFmpeg，无需配置 PATH。

## 配置

```powershell
Copy-Item .env.example .env
```

在 `.env` 中填写 `OPENAI_API_KEY`。不填写或 API 失败时会自动 fallback。脚本不会打印或写出 API Key。

## 运行

```powershell
python generate_video.py
```

重复运行会覆盖旧产物。输出位于 `dist/`：

- `douyin_ai_webnovel_video.mp4`
- `cover.png`
- `subtitles.srt`
- `script.txt`
- `assets_manifest.json`

## Fallback 顺序

- 图片：OpenAI Images -> Pillow 科技感文字分镜
- 配音：OpenAI TTS -> edge-tts -> Windows SAPI/pyttsx3 -> 静音
- 视频：OpenCV 生成画面 + FFmpeg 封装；自动查找系统或 `imageio-ffmpeg` 的 FFmpeg
- 音乐：始终可由 NumPy/WAV 标准库生成低频 drone 和滴答氛围音

## 注意事项

- `.env` 不能提交到 git。
- `assets/temp/` 是临时工作目录，可以随时删除。
- `dist/` 是生成结果目录；需要重新生成时直接再次运行脚本。
