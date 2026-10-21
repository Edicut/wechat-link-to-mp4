---
name: wechat-link-to-mp4
description: Windows only. WeChat Channels (视频号) link (weixin.qq.com/sph/…, channels.weixin.qq.com) → automatically opens it in WeChat for Windows, captures and decrypts the original mp4, then produces 字幕.txt (speech transcript) and contact sheets sheet_*.jpg. Trigger when the user sends a Channels link or asks to download / rip a 视频号 video, or wants its transcript or contact sheets ("下载视频号", "扒视频号", "视频号字幕", "视频号总览图").
---

# wechat-link-to-mp4

The user sends a Channels link → run the script directly; the user doesn't need to do anything.

## One command

```bash
python scripts/wechat_link_to_mp4.py "<Channels link>"
```

Before running, tell the user: **the WeChat window will be driven automatically for a few seconds** (it only sends to 文件传输助手 / File Transfer). Transcription takes a few minutes, so run it in the background.

| Option | Effect |
|---|---|
| `--every 10` | Contact-sheet interval in seconds (default 5; an 8-minute video at 5 s ≈ 17 sheets) |
| `--video-only` | Download the video only |
| `--no-speech` | Skip transcription |
| `--no-open` | Don't drive WeChat; let the user open the link in WeChat |
| `--out <dir>` | Output directory (default `~/Downloads/wechat-link-to-mp4`) |
| `--upstream host:port` | Upstream proxy; default auto-detects local 7890/7897, `none` for direct |

## Output

```
<out>/
  <title>_<time>.mp4        decrypted original video
  <title>_<time>/
    字幕.txt                transcript, one line per sentence with [seconds]
    sheet_01.jpg …          contact sheets, 6 frames each, timestamp in the corner
    frames/                 individual frames
    info.json               link and video description
```

Before delivering, **open one sheet and look at it** to confirm the frames are fine.

## When something goes wrong

- **Prints "couldn't locate the link" or "couldn't open File Transfer"**: the script is still waiting (120 s by default). Immediately run `python scripts/wechat_open.py shot <png>`, look at the screenshot, then `python scripts/wechat_open.py click X Y` to open the link (window-relative coordinates). **Never press Enter in a chat box** until you've confirmed the open chat is 文件传输助手.
- **Templates don't match** (WeChat update / theme / display scaling): take a screenshot and re-crop the two images in `scripts/templates/`.
- **Homophone errors in the transcript**: it's transcribed from audio; the on-screen subtitles are in the contact sheets. Tell whoever reads the results to cross-check against the sheets.
- **Nothing captured**: confirm the video page actually opened and started playing in WeChat; use `--upstream` if the proxy port is different.

How it works and installation: see README.md.
