# mitmdump 插件：在微信视频号页面的 JS 里插一段代码，把视频信息（地址 + 解密 key）发回来存成 JSON。
# 做法照 res-downloader（putyy/res-downloader, Apache-2.0）的 plugin.qq.com.go。
# 环境变量 SPH_CAPTURE_DIR：抓到的视频信息写到这个目录，一条一个 json。
import os, re, time, json
from mitmproxy import http

CAPTURE_DIR = os.environ.get("SPH_CAPTURE_DIR", ".")
HOOK_URL = "https://wxapp.tc.qq.com/wechat-link-to-mp4/capture"
V = str(int(time.time()))   # 给 JS 地址加版本号，绕过微信缓存，确保拿到的是插过代码的 JS

MEDIA_RE = re.compile(r"get\s*media\(\)\{")
HOOK_JS = ("get media(){if(this.objectDesc){fetch(\"%s\",{method:\"POST\",mode:\"no-cors\","
           "body:JSON.stringify(this.objectDesc)});};" % HOOK_URL)


def request(flow: http.HTTPFlow):
    if flow.request.pretty_url.startswith(HOOK_URL):
        try:
            desc = json.loads(flow.request.get_text())
            media = (desc.get("media") or [{}])[0]
            if media.get("url"):
                name = f"{int(time.time() * 1000)}.json"
                with open(os.path.join(CAPTURE_DIR, name), "w", encoding="utf-8") as f:
                    json.dump(desc, f, ensure_ascii=False)
        except Exception as e:
            print("wechat-link-to-mp4 capture error:", e)
        flow.response = http.Response.make(200, b"ok", {"Content-Type": "text/plain"})


def response(flow: http.HTTPFlow):
    if not flow.response or flow.response.status_code not in (200, 206):
        return
    host, path = flow.request.host, flow.request.path
    if host.endswith("channels.weixin.qq.com") and ("/web/pages/feed" in path or "/web/pages/home" in path):
        flow.response.text = flow.response.text.replace('.js"', f'.js?v={V}"')
    elif host.endswith("res.wx.qq.com"):
        busted = flow.request.path.endswith(f".js?v={V}")
        hooked = "web/web-finder/res/js/virtual_svg-icons-register.publish" in path
        if not (busted or hooked):
            return
        text = flow.response.text
        if busted:
            text = text.replace('.js"', f'.js?v={V}"')
        if hooked:
            text = MEDIA_RE.sub(lambda m: HOOK_JS, text)
        flow.response.text = text
