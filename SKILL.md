---
name: wechat-link-to-mp4
description: Windows only. 微信视频号链接（weixin.qq.com/sph/…、channels.weixin.qq.com）→ 自动在电脑微信里点开、抓取并解密原视频 mp4，再出 字幕.txt（语音转文字）和 总览图 sheet_*.jpg。触发：用户发来视频号链接，或说"下载视频号"/"扒视频号"/"视频号字幕"/"视频号总览图"。
---

# wechat-link-to-mp4

用户发视频号链接 → 直接跑脚本，不用让用户动手。

## 一条命令

```bash
python scripts/wechat_link_to_mp4.py "<视频号链接>"
```

跑之前告诉用户：**电脑微信窗口会被自动操作几秒**（只发到「文件传输助手」）。语音转文字要几分钟，适合放后台跑。

| 参数 | 作用 |
|---|---|
| `--every 10` | 总览图每 10 秒一张（默认 5；8 分钟视频 5 秒一张 ≈ 17 张拼图） |
| `--video-only` | 只下视频 |
| `--no-speech` | 不做语音转文字 |
| `--no-open` | 不自动操作微信，让用户自己在微信里点开链接 |
| `--out <目录>` | 输出目录（默认 `~/Downloads/wechat-link-to-mp4`） |
| `--upstream host:port` | 上游代理；默认自动检测本机 7890/7897，`none` 直连 |

## 产出

```
<out>\
  <标题>_<时间>.mp4          原视频（已解密）
  <标题>_<时间>\
    字幕.txt                 说话声转文字，每句带 [秒数]
    sheet_01.jpg …           总览图，一张拼 6 帧，左上角标秒数
    frames\                  单帧截图
    info.json                链接、视频描述
```

交付前**打开一张 sheet 看一眼**，确认画面正常。

## 出问题时

- **输出「没认出链接位置」或「没能打开文件传输助手」**：脚本还在等（默认 120 秒）。马上 `python scripts/wechat_open.py shot <png>` 截微信窗口，看图后 `python scripts/wechat_open.py click X Y` 点开链接（窗口内坐标）。没确认是「文件传输助手」之前**绝不在聊天框里按回车**。
- **模板认不出**（微信改版 / 换主题 / 换缩放比例）：手动截一张，重新裁 `scripts/templates/` 里的两张图。
- **字幕有同音错字**：字幕是听声音转的，画面上的字幕要看总览图。让读结果的 AI 对照总览图纠正。
- **抓不到**：确认微信里视频页真的打开并开始播放了；上游代理端口不对就用 `--upstream`。

原理和安装见 README.md。
