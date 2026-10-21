# wechat-link-to-mp4

[English](README.md) | 简体中文

把**微信视频号链接**变成本地 mp4，并顺手生成**字幕文本**和**画面总览图**，方便丢给 AI 分析。
可以当命令行工具用，也可以当 Claude Code skill 用（见 `SKILL.md`）。

> 仅支持 Windows + 电脑版微信（4.x）。请只下载你有权保存的内容，供个人学习使用。

## 它做了什么

1. 临时启动一个 [mitmproxy](https://mitmproxy.org/) 代理并设为系统代理（只解密 `qq.com` 的流量，其他网站原样转发；可串联你已有的代理）。
2. 自动操作电脑微信：搜索「文件传输助手」→ **核对聊天标题后**才发送链接 → 点开链接。
3. 代理在视频号页面的 JS 里插入一小段代码，拿到视频地址、`urlToken` 和 `decodeKey`。
4. 下载视频，用 ISAAC64 密钥流解密文件开头 128KB（视频号的加密方式），检查 mp4 文件头。
5. **无论成功失败都恢复原来的系统代理设置。**
6. 每 N 秒截一帧，拼成 3×2 的总览图；用 faster-whisper 把说话声转成带时间戳的文字。

## 安装

```bash
pip install -r requirements.txt
```

- 依赖：`mitmproxy requests opencv-python numpy pillow faster-whisper "av<16" opencc-python-reimplemented`
- mitmproxy 也可以单独装在 `~/.wechat-link-to-mp4/venv` 里，脚本会优先用它。
- 第一次运行会弹 **UAC**，把 mitmproxy 根证书装进「受信任的根证书颁发机构」（解密 HTTPS 必需）。不用了可以在 `certmgr.msc` 里删掉 `mitmproxy` 证书。
- 语音模型（faster-whisper small，约 460MB）第一次用时自动下载。

## 用法

```bash
python scripts/wechat_link_to_mp4.py "https://weixin.qq.com/sph/xxxxxxxx"
```

运行前打开并登录电脑版微信。常用参数：`--every 10`（总览图间隔）、`--video-only`、`--no-speech`、`--no-open`（自己在微信里点开链接）、`--out <目录>`、`--upstream host:port|none`。

工作目录（证书、临时文件）默认 `~/.wechat-link-to-mp4`，可用环境变量 `WECHAT_LINK_TO_MP4_HOME` 修改。

## 文件

| 文件 | 作用 |
|---|---|
| `scripts/wechat_link_to_mp4.py` | 主流程 |
| `scripts/mitm_addon.py` | mitmproxy 插件：注入 JS、接收视频信息 |
| `scripts/wechat_open.py` | 驱动微信窗口（也可单独用：`shot` 截图、`click X Y` 点击） |
| `scripts/isaac64.py` | 视频号解密 |
| `scripts/media.py` | 截图拼总览图、语音转文字 |
| `scripts/templates/` | 识别「文件传输助手」的图片模板（在 150% 缩放、浅色主题下截取，会按你的缩放自动换算） |

## 封号风险

**不保证**微信不会处理你的账号。从微信那边看，这个工具做的事是：

- 给**自己的**文件传输助手发一条链接并点开，和手动操作一样；
- 下载的就是播放时本来就会加载的视频文件；
- **在本地（通过代理）改了视频号网页的一小段 JS**，用来拿解密 key。这是唯一和正常使用不同的地方，理论上可能被检测到。res-downloader 等工具也是同样原理，用的人很多。

降低风险：

- **别短时间大量抓**（几十上百个）。像机器人一样的频率最容易被盯上。
- 偶尔抓一两个自己要看的视频，和正常使用差别不大。
- 担心的话，在用来抓取的电脑上登**小号**。

风险自负。

## 致谢

抓取和解密思路参考 [putyy/res-downloader](https://github.com/putyy/res-downloader)（Apache-2.0）。解密结果已与它逐字节比对一致。

## License

MIT
