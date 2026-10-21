# 驱动电脑版微信：把链接发到「文件传输助手」再点开，让视频号在微信内置浏览器里播放。
# 只用 ctypes + Pillow + numpy，坐标都是相对微信窗口的。
#   python wechat_open.py send "<链接>"     发链接并点开
#   python wechat_open.py shot out.png      截微信窗口（自动点不中时给 AI 看图）
#   python wechat_open.py click X Y          点窗口内坐标
import ctypes, os, sys, time
from ctypes import wintypes
import numpy as np
from PIL import Image, ImageGrab

TEMPLATES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

ctypes.windll.shcore.SetProcessDpiAwareness(2)
u, k = ctypes.windll.user32, ctypes.windll.kernel32
u.GetClipboardData.restype = wintypes.HANDLE
k.GlobalAlloc.restype = wintypes.HGLOBAL
k.GlobalLock.restype = ctypes.c_void_p
k.GlobalLock.argtypes = [wintypes.HGLOBAL]
k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
CTRL, ENTER, V, F, ESC = 0x11, 0x0D, 0x56, 0x46, 0x1B


def _exe_of(h):
    pid = wintypes.DWORD()
    u.GetWindowThreadProcessId(h, ctypes.byref(pid))
    ph = k.OpenProcess(0x1000, False, pid.value)
    if not ph:
        return ""
    b, n = ctypes.create_unicode_buffer(520), wintypes.DWORD(520)
    k.QueryFullProcessImageNameW(ph, 0, b, ctypes.byref(n))
    k.CloseHandle(ph)
    return b.value.rsplit("\\", 1)[-1].lower()


def find_wechat():
    """主窗口标题是「微信」，类名 Qt…QWindowIcon；关到托盘时是隐藏的，照样能找到。
    别碰 WxTrayIconMessageWindow 之类的隐藏辅助窗口"""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        t = ctypes.create_unicode_buffer(64)
        c = ctypes.create_unicode_buffer(64)
        u.GetWindowTextW(h, t, 64)
        u.GetClassNameW(h, c, 64)
        if t.value in ("微信", "Weixin") and c.value.endswith("QWindowIcon") and _exe_of(h) == "weixin.exe":
            r = wintypes.RECT()
            u.GetWindowRect(h, ctypes.byref(r))
            found.append(((r.right - r.left) * (r.bottom - r.top), h))
        return True
    u.EnumWindows(cb, 0)
    if not found:
        raise RuntimeError("没找到微信窗口，先打开并登录电脑版微信")
    return max(found)[1]   # 还有个小的 Weixin 弹窗，取最大的那个


def focus(h):
    u.ShowWindow(h, 9)
    u.keybd_event(0x12, 0, 0, 0); u.keybd_event(0x12, 0, 2, 0)   # 按一下 Alt，SetForegroundWindow 才生效
    u.SetForegroundWindow(h)
    time.sleep(0.8)
    r = wintypes.RECT()
    u.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def key(vk, mods=()):
    for m in mods:
        u.keybd_event(m, 0, 0, 0)
    u.keybd_event(vk, 0, 0, 0); u.keybd_event(vk, 0, 2, 0)
    for m in reversed(mods):
        u.keybd_event(m, 0, 2, 0)
    time.sleep(0.25)


def set_clipboard(text):
    data = text.encode("utf-16-le") + b"\0\0"
    for _ in range(10):
        if u.OpenClipboard(None):
            break
        time.sleep(0.1)
    u.EmptyClipboard()
    hmem = k.GlobalAlloc(0x0002, len(data))
    ctypes.memmove(k.GlobalLock(hmem), data, len(data))
    k.GlobalUnlock(hmem)
    u.SetClipboardData(13, hmem)
    u.CloseClipboard()


def paste(text):
    set_clipboard(text)
    time.sleep(0.2)
    key(V, (CTRL,))
    time.sleep(0.4)


def click(rect, x, y):
    u.SetCursorPos(rect[0] + int(x), rect[1] + int(y))
    time.sleep(0.15)
    u.mouse_event(2, 0, 0, 0, 0); u.mouse_event(4, 0, 0, 0, 0)
    time.sleep(0.3)


def find_last_link(rect):
    """找聊天区最下面那个绿色气泡（自己刚发的链接），返回气泡里链接文字的中心（窗口内坐标）。
    只在气泡范围里找，不会点到旁边的头像"""
    img = np.asarray(ImageGrab.grab(bbox=rect).convert("RGB")).astype(int)
    h, w, _ = img.shape
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    green = (g > 210) & (g - r > 45) & (g - b > 50)   # 气泡底色约 (169,234,160)
    green[:120] = False                               # 标题栏
    green[h - 240:] = False                           # 输入框
    green[:, :345] = False                            # 左边导航和会话列表
    green[:, w - 100:] = False                        # 右边头像
    rows = np.where(green.sum(axis=1) >= 40)[0]
    if len(rows) == 0:
        return None
    y1 = rows.max()
    y0 = y1
    while y0 - 1 in set(rows[rows >= y1 - 300]):      # 往上找到同一个气泡的顶
        y0 -= 1
    cols = np.where(green[y0:y1 + 1].any(axis=0))[0]
    x0, x1 = cols.min(), cols.max()
    box = img[y0:y1 + 1, x0:x1 + 1]
    text = (box[..., 2] - box[..., 0] > 40) & (box[..., 1] < 200)   # 气泡里的蓝色链接字
    ys, xs = np.where(text)
    if len(ys) < 20:
        return None
    return int(x0 + np.median(xs)), int(y0 + np.median(ys))


def find_template(rect, name, thr=0.85, region=None):
    """在窗口截图里找 templates/<name>，返回窗口内中心坐标；region=(x0,y0,x1,y1) 限定范围"""
    import cv2
    img = cv2.cvtColor(np.asarray(ImageGrab.grab(bbox=rect).convert("RGB")), cv2.COLOR_RGB2GRAY)
    x0, y0 = 0, 0
    if region:
        x0, y0, x1, y1 = region
        img = img[y0:y1, x0:x1]
    t = cv2.cvtColor(np.asarray(Image.open(os.path.join(TEMPLATES, name)).convert("RGB")), cv2.COLOR_RGB2GRAY)
    res = cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED)
    _, best, _, (x, y) = cv2.minMaxLoc(res)
    return (x0 + x + t.shape[1] // 2, y0 + y + t.shape[0] // 2) if best >= thr else None


def open_filehelper(h):
    """搜索并打开「文件传输助手」；确认聊天标题是它才返回 True，否则什么都不发"""
    rect = focus(h)
    click(rect, 248, 83)                      # 左上角放大镜（Ctrl+F 在新版微信里不管用）
    time.sleep(0.8)
    paste("文件传输助手")
    time.sleep(1.5)
    p = find_template(rect, "filehelper_icon.png", region=(200, 100, rect[2] - rect[0], rect[3] - rect[1]))
    if not p:                                 # 回车会变成「搜索网络结果」，所以必须点「功能」里那一项
        key(ESC)
        return False
    click(rect, *p)
    time.sleep(1.5)
    return find_template(rect, "filehelper_title.png", region=(340, 50, rect[2] - rect[0], 120)) is not None


def send_and_open(link):
    """返回 'opened'（已点开）/ 'sent'（发了但没认出链接位置）/ 'no-chat'（没打开文件传输助手，什么都没发）"""
    h = find_wechat()
    if not open_filehelper(h):
        return "no-chat"
    rect = focus(h)
    w, hh = rect[2] - rect[0], rect[3] - rect[1]
    click(rect, (340 + w) // 2, hh - 160)    # 输入框
    paste(link)
    key(ENTER)
    time.sleep(2.5)
    p = find_last_link(rect)
    if not p:
        return "sent"
    click(rect, *p)
    return "opened"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1]
    if cmd == "send":
        print(send_and_open(sys.argv[2]))
    elif cmd == "shot":
        ImageGrab.grab(bbox=focus(find_wechat())).save(sys.argv[2])
        print(sys.argv[2])
    elif cmd == "click":
        click(focus(find_wechat()), int(sys.argv[2]), int(sys.argv[3]))
