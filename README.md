# wechat-link-to-mp4

English | [简体中文](README.zh-CN.md)

Turn a **WeChat Channels (视频号) share link** into a local mp4, plus a **timestamped transcript** and **contact-sheet thumbnails** that are easy to hand to an AI for analysis.
Works as a command-line tool or as a Claude Code skill (see `SKILL.md`).

> Windows + WeChat for Windows (4.x) only. Only download content you have the right to save, for personal use.

## How it works

1. Starts a temporary [mitmproxy](https://mitmproxy.org/) instance and sets it as the system proxy. Only `qq.com` traffic is intercepted; everything else is passed through untouched. It can chain to an existing upstream proxy.
2. Drives the WeChat desktop window: searches for 文件传输助手 (File Transfer), **verifies the chat title before sending anything**, sends the link, then clicks it.
3. The proxy injects a small snippet into the Channels page JS to capture the video URL, `urlToken` and `decodeKey`.
4. Downloads the video and decrypts its first 128 KB with an ISAAC64 keystream (the scheme Channels uses), then checks the mp4 header.
5. **Restores your original proxy settings, whether the run succeeds or fails.**
6. Grabs a frame every N seconds and tiles them into 3×2 contact sheets; transcribes speech with faster-whisper.

## Install

```bash
pip install -r requirements.txt
```

- Dependencies: `mitmproxy requests opencv-python numpy pillow faster-whisper "av<16" opencc-python-reimplemented`
- mitmproxy can also live in its own venv at `~/.wechat-link-to-mp4/venv`; the script prefers it when present.
- The first run shows a **UAC prompt** to install the mitmproxy root certificate into Trusted Root Certification Authorities (needed to decrypt HTTPS). To remove it later, delete the `mitmproxy` certificate in `certmgr.msc`.
- The speech model (faster-whisper small, ~460 MB) downloads automatically on first use.

## Usage

```bash
python scripts/wechat_link_to_mp4.py "https://weixin.qq.com/sph/xxxxxxxx"
```

Open and log in to WeChat for Windows first.

| Option | Effect |
|---|---|
| `--every 10` | Contact-sheet interval in seconds (default 5) |
| `--video-only` | Download the video only |
| `--no-speech` | Skip transcription |
| `--no-open` | Don't drive WeChat; open the link in WeChat yourself |
| `--out <dir>` | Output directory (default `~/Downloads/wechat-link-to-mp4`) |
| `--upstream host:port` | Upstream proxy; default auto-detects local 7890/7897, `none` for direct |

The working directory (certificate, temp files) defaults to `~/.wechat-link-to-mp4`; override it with the `WECHAT_LINK_TO_MP4_HOME` environment variable.

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

The transcript comes from the audio, so expect some homophone errors in Chinese. The on-screen subtitles are visible in the contact sheets, so an AI reading both can correct them.

## Files

| File | Purpose |
|---|---|
| `scripts/wechat_link_to_mp4.py` | Main pipeline |
| `scripts/mitm_addon.py` | mitmproxy addon: injects JS, receives video info |
| `scripts/wechat_open.py` | Drives the WeChat window (standalone: `shot <png>`, `click X Y`) |
| `scripts/isaac64.py` | Channels decryption |
| `scripts/media.py` | Frame grabbing, contact sheets, transcription |
| `scripts/templates/` | Image templates for finding File Transfer (captured at 150% display scaling in light theme; auto-scaled to your DPI) |

## Troubleshooting

- **"Couldn't locate the link" / "Couldn't open File Transfer"**: the script keeps waiting (120 s by default). Run `python scripts/wechat_open.py shot wx.png`, look at the screenshot, then `python scripts/wechat_open.py click X Y` to open the link (window-relative coordinates).
- **Templates don't match** (WeChat update, dark theme, different display scaling): take a screenshot and re-crop the two images in `scripts/templates/`.
- **Nothing captured**: make sure the video page actually opened and started playing in WeChat; use `--upstream` if your proxy runs on another port.

## Credits

The capture and decryption approach follows [putyy/res-downloader](https://github.com/putyy/res-downloader) (Apache-2.0). Decrypted output was verified byte-for-byte against it.

## License

MIT
