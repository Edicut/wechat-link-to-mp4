# 微信视频号链接 -> 无水印原视频（自动解密）+ 字幕.txt（语音转文字）+ 总览图 sheet_*.jpg
#
# 原理：临时开一个 mitmproxy 代理并设成系统代理；在电脑微信里把链接发给「文件传输助手」并点开；
#       代理往视频号页面的 JS 里插一段代码，拿到视频地址和解密 key；下载、解密开头 128KB；最后恢复原代理设置。
#
# 用法：
#   python wechat_link_to_mp4.py "https://weixin.qq.com/sph/xxxx"
#   python wechat_link_to_mp4.py "<链接>" --every 10       总览图每 10 秒一张（默认 5）
#   python wechat_link_to_mp4.py "<链接>" --no-open        不自动操作微信，自己去微信里点开链接
#   python wechat_link_to_mp4.py "<链接>" --video-only     只下视频
#
# 工作目录（mitmproxy 证书、临时文件）默认 ~/.wechat-link-to-mp4，可用环境变量 WECHAT_LINK_TO_MP4_HOME 改。
import os, re, sys, json, glob, time, shutil, socket, ssl, hashlib, argparse, subprocess, tempfile, winreg, ctypes
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
HOME = os.environ.get("WECHAT_LINK_TO_MP4_HOME", os.path.join(os.path.expanduser("~"), ".wechat-link-to-mp4"))
CONFDIR = os.path.join(HOME, "mitm")
INET = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
COMMON_PROXY_PORTS = (7890, 7897)   # Clash 系常见端口，开着就自动当上游
sys.path.insert(0, HERE)


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_mitmdump():
    venv = os.path.join(HOME, "venv", "Scripts", "mitmdump.exe")
    exe = venv if os.path.isfile(venv) else shutil.which("mitmdump")
    if not exe:
        raise RuntimeError(f"没找到 mitmdump：pip install mitmproxy，或装到 {os.path.dirname(os.path.dirname(venv))}")
    return exe


# ---------- 证书：mitmproxy 根证书装进「受信任的根证书」，只需一次（会弹 UAC） ----------
def ensure_ca():
    pem = os.path.join(CONFDIR, "mitmproxy-ca-cert.pem")
    if not os.path.isfile(pem):
        raise RuntimeError("还没生成 mitmproxy 证书")
    thumb = hashlib.sha1(ssl.PEM_cert_to_DER_cert(open(pem).read())).hexdigest()
    if subprocess.run(["certutil", "-store", "Root", thumb], capture_output=True).returncode == 0:
        return
    print("第一次使用：安装代理证书（请在弹出的 UAC 窗口点「是」）...")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    f"Start-Process certutil -ArgumentList '-addstore','Root','\"{pem}\"' -Verb RunAs -Wait"])
    if subprocess.run(["certutil", "-store", "Root", thumb], capture_output=True).returncode != 0:
        raise RuntimeError("证书没装上（UAC 被拒绝？）")


# ---------- 系统代理：记下原设置，结束时原样恢复 ----------
def _refresh_proxy():
    wininet = ctypes.windll.wininet
    wininet.InternetSetOptionW(None, 39, None, 0)   # SETTINGS_CHANGED
    wininet.InternetSetOptionW(None, 37, None, 0)   # REFRESH


def get_proxy():
    saved = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INET) as kk:
        for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
            try:
                saved[name] = winreg.QueryValueEx(kk, name)
            except FileNotFoundError:
                saved[name] = None
    return saved


def set_proxy(port):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INET, 0, winreg.KEY_SET_VALUE) as kk:
        winreg.SetValueEx(kk, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(kk, "ProxyServer", 0, winreg.REG_SZ, f"127.0.0.1:{port}")
        winreg.SetValueEx(kk, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.*;<local>")
    _refresh_proxy()


def restore_proxy(saved):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INET, 0, winreg.KEY_SET_VALUE) as kk:
        for name, val in saved.items():
            if val is None:
                try:
                    winreg.DeleteValue(kk, name)
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(kk, name, 0, val[1], val[0])
    _refresh_proxy()


def start_mitm(port, upstream, capture_dir):
    cmd = [find_mitmdump(), "-q", "-s", os.path.join(HERE, "mitm_addon.py"), "--listen-port", str(port),
           "--set", f"confdir={CONFDIR}", "--set", r"allow_hosts=qq\.com"]   # 只解密 qq.com，其他网站原样转发
    if upstream:
        cmd[1:1] = ["--mode", f"upstream:http://{upstream}"]
    env = dict(os.environ, SPH_CAPTURE_DIR=capture_dir)
    p = subprocess.Popen(cmd, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(40):
        if port_open(port):
            return p
        if p.poll() is not None:
            break
        time.sleep(0.5)
    p.kill()
    raise RuntimeError("代理没启动起来")


def wait_capture(capture_dir, timeout):
    end = time.time() + timeout
    while time.time() < end:
        files = sorted(glob.glob(os.path.join(capture_dir, "*.json")))
        if files:
            time.sleep(1)   # 同一个视频可能连发几次，取第一条
            return json.load(open(files[0], encoding="utf-8"))
        time.sleep(1)
    return None


def safe_name(text, ts):
    text = re.sub(r"#\S+", "", text or "").strip()
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", text).strip()
    return f"{(text[:30].strip() or '视频号')}_{ts}"


def download(desc, path):
    media = desc["media"][0]
    url = media["url"] + media.get("urlToken", "")
    s = requests.Session()
    s.trust_env = False   # 不走系统代理（这时系统代理还指着 mitmproxy）
    with s.get(url, headers={"User-Agent": UA}, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    key = media.get("decodeKey")
    if key:
        import isaac64
        isaac64.decrypt_file(path, key)
    with open(path, "rb") as f:
        if f.read(12)[4:8] != b"ftyp":
            raise RuntimeError("解密后文件头不对，视频可能已损坏：" + path)


def postprocess(video, folder, every, speech_on):
    import media
    n = media.keyframes(video, folder, every)
    print(f"  总览图：{n} 张截图（每 {every:g} 秒一张），拼成 {len(glob.glob(os.path.join(folder, 'sheet_*.jpg')))} 张 sheet_*.jpg")
    if speech_on:
        print("  语音转文字（几分钟）...")
        text = media.transcribe(video)
        with open(os.path.join(folder, "字幕.txt"), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"  字幕：{len(text.splitlines())} 句" if text else "  字幕：没有人声")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="微信视频号链接 -> 视频 + 字幕 + 总览图")
    p.add_argument("link")
    p.add_argument("--out", default=os.path.join(os.path.expanduser("~"), "Downloads", "wechat-link-to-mp4"))
    p.add_argument("--every", type=float, default=5, help="总览图每几秒截一张")
    p.add_argument("--no-speech", action="store_true", help="不做语音转文字")
    p.add_argument("--video-only", action="store_true", help="只下视频")
    p.add_argument("--no-open", action="store_true", help="不自动操作微信，自己去点开链接")
    p.add_argument("--upstream", default="auto",
                   help="上游代理 host:port；auto = 本机 7890/7897 有代理就用；none = 直连")
    p.add_argument("--port", type=int, default=8898, help="本工具代理监听的端口")
    p.add_argument("--timeout", type=int, default=120, help="等多久抓不到就放弃（秒）")
    args = p.parse_args()

    if args.upstream == "auto":
        upstream = next((f"127.0.0.1:{pt}" for pt in COMMON_PROXY_PORTS if port_open(pt)), None)
    else:
        upstream = None if args.upstream == "none" else args.upstream
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(os.path.join(HOME, "tmp"), exist_ok=True)
    capture_dir = tempfile.mkdtemp(prefix="cap_", dir=os.path.join(HOME, "tmp"))

    saved = get_proxy()
    mitm = start_mitm(args.port, upstream, capture_dir)
    try:
        ensure_ca()
        set_proxy(args.port)
        print(f"代理已开（127.0.0.1:{args.port} → {upstream or '直连'}），原代理设置会在结束时恢复")
        if args.no_open:
            print("请在电脑微信里点开这个链接并播放：", args.link)
        else:
            import wechat_open
            print({"opened": "已在微信里发送并点开链接",
                   "sent": "链接已发到文件传输助手，但没认出链接位置：用 wechat_open.py shot/click 手动点开",
                   "no-chat": "没能打开文件传输助手（什么都没发）：用 wechat_open.py shot/click 手动操作"}
                  [wechat_open.send_and_open(args.link)])
        sys.stdout.flush()
        desc = wait_capture(capture_dir, args.timeout)
    finally:
        restore_proxy(saved)
        mitm.kill()
        shutil.rmtree(capture_dir, ignore_errors=True)
    if not desc:
        print(f"{args.timeout} 秒内没抓到视频。微信里的视频页打开了吗？代理设置已恢复。")
        sys.exit(2)

    name = safe_name(desc.get("description"), time.strftime("%Y%m%d%H%M%S"))
    video = os.path.join(args.out, name + ".mp4")
    print("抓到了：", (desc.get("description") or "")[:60].replace("\n", " "))
    print("  下载并解密...")
    download(desc, video)
    print(f"  视频：{video}（{os.path.getsize(video) / 1e6:.1f} MB）")
    folder = os.path.join(args.out, name)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "info.json"), "w", encoding="utf-8") as f:
        json.dump({"link": args.link, "description": desc.get("description"), "video": video},
                  f, ensure_ascii=False, indent=2)
    if not args.video_only:
        postprocess(video, folder, args.every, not args.no_speech)
    print("完成 →", folder)


if __name__ == "__main__":
    main()
