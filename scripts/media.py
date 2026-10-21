# 视频后处理：每 N 秒截一帧并拼成总览图；语音转文字。
# 图片用 cv2.imencode + tofile 写，Windows 上中文路径也能存（cv2.imwrite 会静默失败）。
import os, glob, shutil

SHEET_COLS, SHEET_ROWS, TILE_W = 3, 2, 480   # 一张总览图拼 6 帧
PROMPT = "以下是普通话的句子，使用简体中文和标点。"


def _save(path, img):
    import cv2
    cv2.imencode(".jpg", img)[1].tofile(path)


def keyframes(video, folder, every=5.0):
    """每 every 秒截一张存到 frames/，再拼成总览图 sheet_*.jpg（左上角标秒数）。返回截图张数"""
    import cv2
    import numpy as np
    frames_dir = os.path.join(folder, "frames")
    shutil.rmtree(frames_dir, ignore_errors=True)
    for old in glob.glob(os.path.join(folder, "sheet_*.jpg")):
        os.remove(old)
    os.makedirs(frames_dir)
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(fps * every))
    shots, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % step == 0:
            shots.append((i / fps, frame))
        i += 1
    cap.release()
    for t, frame in shots:
        _save(os.path.join(frames_dir, f"{t:05.0f}s.jpg"), frame)

    per = SHEET_COLS * SHEET_ROWS
    for n in range(0, len(shots), per):
        tiles = []
        for t, frame in shots[n:n + per]:
            h = int(frame.shape[0] * TILE_W / frame.shape[1])
            tile = cv2.resize(frame, (TILE_W, h))
            cv2.putText(tile, f"{t:.0f}s", (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            tiles.append(tile)
        tiles += [np.zeros_like(tiles[0])] * (per - len(tiles))
        rows = [np.hstack(tiles[r * SHEET_COLS:(r + 1) * SHEET_COLS]) for r in range(SHEET_ROWS)]
        _save(os.path.join(folder, f"sheet_{n // per + 1:02d}.jpg"), np.vstack(rows))
    return len(shots)


_whisper = None


def transcribe(video, model="small"):
    """faster-whisper 转文字（CPU 即可，模型第一次用会自动下载），每句带 [秒数]，转成简体"""
    global _whisper
    from faster_whisper import WhisperModel
    import opencc
    if _whisper is None:
        _whisper = WhisperModel(model, device="cpu", compute_type="int8")
    segs, _ = _whisper.transcribe(video, language="zh", vad_filter=True, initial_prompt=PROMPT)
    lines = [f"[{s.start:.0f}s] {s.text.strip()}" for s in segs]
    return opencc.OpenCC("t2s").convert("\n".join(lines))
