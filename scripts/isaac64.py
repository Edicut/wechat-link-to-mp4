# 视频号视频解密：文件开头 128KB 和 ISAAC64 密钥流异或，种子是 decodeKey。
# 和 res-downloader 的 decrypt.js（微信 WxIsaac64）逐字节对过，结果一致。
M = (1 << 64) - 1
GOLD = 0x9e3779b97f4a7c13
ENC_LEN = 131072


def _mix(s):
    a, b, c, d, e, f, g, h = s
    a = (a - e) & M; f ^= h >> 9;  h = (h + a) & M
    b = (b - f) & M; g ^= (a << 9) & M; a = (a + b) & M
    c = (c - g) & M; h ^= b >> 23; b = (b + c) & M
    d = (d - h) & M; a ^= (c << 15) & M; c = (c + d) & M
    e = (e - a) & M; b ^= d >> 14; d = (d + e) & M
    f = (f - b) & M; c ^= (e << 20) & M; e = (e + f) & M
    g = (g - c) & M; d ^= f >> 17; f = (f + g) & M
    h = (h - d) & M; e ^= (g << 14) & M; g = (g + h) & M
    return [a, b, c, d, e, f, g, h]


class Isaac64:
    def __init__(self, seed):
        rsl = [0] * 256
        rsl[0] = seed & M
        s = [GOLD] * 8
        for _ in range(4):
            s = _mix(s)
        mm = [0] * 256
        for src in (rsl, mm):
            for i in range(0, 256, 8):
                s = _mix([(s[j] + src[i + j]) & M for j in range(8)])
                mm[i:i + 8] = s
        self.mm, self.a, self.b, self.c = mm, 0, 0, 0
        self.rsl = [0] * 256
        self.step()

    def step(self):
        mm, r = self.mm, self.rsl
        self.c = (self.c + 1) & M
        a, b = self.a, (self.b + self.c) & M
        for i in range(256):
            x = mm[i]
            k = i & 3
            if k == 0:
                a = ~(a ^ ((a << 21) & M)) & M
            elif k == 1:
                a ^= a >> 5
            elif k == 2:
                a ^= (a << 12) & M
            else:
                a ^= a >> 33
            a = (a + mm[(i + 128) & 255]) & M
            y = (mm[(x >> 3) & 255] + a + b) & M
            mm[i] = y
            b = (mm[(y >> 11) & 255] + x) & M
            r[i] = b
        self.a, self.b = a, b


def keystream(seed, n=ENC_LEN):
    g, out = Isaac64(int(seed)), bytearray()
    while len(out) < n:
        for w in reversed(g.rsl):
            out += w.to_bytes(8, "big")
        g.step()
    return bytes(out[:n])


def decrypt_file(path, decode_key):
    """原地解密：只改文件开头 128KB"""
    with open(path, "r+b") as f:
        head = f.read(ENC_LEN)
        ks = keystream(decode_key, len(head))
        f.seek(0)
        f.write(bytes(a ^ b for a, b in zip(head, ks)))
