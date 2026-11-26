"""Serve the chat page and forward model calls to the local servers.

The phone opens this page on the PC's Tailscale address. llama-server stays on
127.0.0.1:8080 for text. The picture server stays on 127.0.0.1:7861. This
page is the only address the phone needs. Chat and pictures share one 12 GB
GPU, so switching stops the other program.
"""

import json
import os
import socket
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = os.path.dirname(os.path.abspath(__file__))
LLAMA = "http://127.0.0.1:8080"
SD = "http://127.0.0.1:7861"
SD_PORT = 7861
LLAMA_PORT = 8080
HOST = "0.0.0.0"
PORT = 8765
SD_ROOT = os.path.join(ROOT, "sd")
MODELS = os.path.join(SD_ROOT, "models")
ENGINE_FILE = os.path.join(SD_ROOT, "engine.txt")
STAMP_FILE = os.path.join(SD_ROOT, "launch.txt")
LOCK = threading.Lock()
TOKEN = 0
STATE = {"phase": "idle", "error": "", "message": ""}

MODES = {
    "picture": {
        "label": "FLUX.2 Klein 4B",
        "files": [
            os.path.join(MODELS, "diffusion_models", "flux-2-klein-4b-Q4_K.gguf"),
            os.path.join(MODELS, "vae", "flux2-vae.safetensors"),
            os.path.join(MODELS, "text_encoders", "Qwen3-4B-Q4_K_M.gguf"),
        ],
    },
    "qwen": {
        "label": "Qwen-Image 2.1",
        "files": [
            os.path.join(MODELS, "diffusion_models", "qwen_image_2.1-Q4_K.gguf"),
            os.path.join(MODELS, "vae", "qwen_image_2.1_vae_bf16.safetensors"),
            os.path.join(MODELS, "text_encoders", "Qwen3VL-8B-Instruct-Q4_K_M.gguf"),
        ],
        "vision": os.path.join(MODELS, "text_encoders", "mmproj-Qwen3VL-8B-Instruct-F16.gguf"),
    },
    "zimage": {
        "label": "Z-Image Turbo",
        "files": [
            os.path.join(MODELS, "diffusion_models", "z_image_turbo-Q4_K.gguf"),
            os.path.join(MODELS, "vae", "ae.safetensors"),
            os.path.join(MODELS, "text_encoders", "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"),
        ],
    },
    "animate": {
        "label": "Wan 2.2 TI2V 5B",
        "files": [
            os.path.join(MODELS, "diffusion_models", "Wan2.2-TI2V-5B-Q4_K_S.gguf"),
            os.path.join(MODELS, "vae", "wan2.2_vae.safetensors"),
            os.path.join(MODELS, "text_encoders", "umt5-xxl-encoder-Q4_K_M.gguf"),
        ],
    },
}


def port_open(port):
    with socket.socket() as sock:
        sock.settimeout(0.4)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_port(port, seconds, want_open):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if port_open(port) == want_open:
            return True
        time.sleep(1)
    return port_open(port) == want_open


def read_engine():
    try:
        with open(ENGINE_FILE, encoding="utf-8") as handle:
            name = handle.read().strip()
    except OSError:
        name = ""
    return name if name in MODES or name == "chat" else "chat"


def write_engine(name):
    os.makedirs(SD_ROOT, exist_ok=True)
    with open(ENGINE_FILE, "w", encoding="utf-8") as handle:
        handle.write(name)


def launch_signature(mode):
    parts = [mode]
    if MODES.get(mode, {}).get("vision"):
        parts.append("vision")
    return " ".join(parts)


def read_stamp():
    try:
        with open(STAMP_FILE, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def write_stamp(mode):
    os.makedirs(SD_ROOT, exist_ok=True)
    with open(STAMP_FILE, "w", encoding="utf-8") as handle:
        handle.write(launch_signature(mode))


MIN_BYTES = {
    "flux-2-klein-4b-Q4_K.gguf": 2400000000,
    "flux2-vae.safetensors": 300000000,
    "Qwen3-4B-Q4_K_M.gguf": 2200000000,
    "qwen_image_2.1-Q4_K.gguf": 3800000000,
    "qwen_image_2.1_vae_bf16.safetensors": 500000000,
    "Qwen3VL-8B-Instruct-Q4_K_M.gguf": 4200000000,
    "mmproj-Qwen3VL-8B-Instruct-F16.gguf": 1100000000,
    "Wan2.2-TI2V-5B-Q4_K_S.gguf": 2500000000,
    "wan2.2_vae.safetensors": 1200000000,
    "umt5-xxl-encoder-Q4_K_M.gguf": 3400000000,
    "z_image_turbo-Q4_K.gguf": 3800000000,
    "ae.safetensors": 320000000,
    "Qwen3-4B-Instruct-2507-Q4_K_M.gguf": 2400000000,
}


def mode_files(mode):
    paths = list(MODES[mode]["files"])
    vision = MODES[mode].get("vision")
    if vision:
        paths.append(vision)
    return paths


def missing_files(mode):
    missing = []
    for path in mode_files(mode):
        minimum = MIN_BYTES.get(os.path.basename(path), 1000000)
        if not os.path.isfile(path) or os.path.getsize(path) < minimum:
            missing.append(path)
    return missing


def find_sd_exe():
    for folder, _dirs, files in os.walk(SD_ROOT):
        if "sd-server.exe" in files:
            return os.path.join(folder, "sd-server.exe")
    return ""


def stop_image(image_name):
    subprocess.run(
        ["taskkill", "/IM", image_name, "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def log_tail():
    path = os.path.join(SD_ROOT, "sd-server.log")
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 2500))
            text = handle.read().decode("utf-8", "replace")
    except OSError:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines[-8:])


def watch_port(token, mode, port, seconds, ready_message, fail_message):
    if wait_port(port, seconds, True):
        if token != TOKEN:
            return
        write_engine(mode)
        STATE["phase"] = "ready"
        STATE["error"] = ""
        STATE["message"] = ready_message
        return
    if token != TOKEN:
        return
    STATE["phase"] = "error"
    STATE["error"] = fail_message + " " + log_tail()
    STATE["message"] = fail_message


def begin(mode, message):
    global TOKEN
    TOKEN += 1
    STATE["phase"] = "loading"
    STATE["target"] = mode
    STATE["error"] = ""
    STATE["message"] = message
    return TOKEN


def launch_llama(token):
    if token != TOKEN:
        return
    stop_image("sd-server.exe")
    wait_port(SD_PORT, 20, False)
    if token != TOKEN:
        return
    if not port_open(LLAMA_PORT):
        bat = os.path.join(ROOT, "llama", "start-llama.bat")
        subprocess.Popen('start "Chat model" cmd /c "' + bat + '"', shell=True, cwd=ROOT)
    watch_port(token, "chat", LLAMA_PORT, 180, "Chat is ready.", "llama-server did not start.")


def launch_sd(token, mode, exe):
    if token != TOKEN:
        return
    stop_image("llama-server.exe")
    stop_image("sd-server.exe")
    wait_port(LLAMA_PORT, 25, False)
    wait_port(SD_PORT, 15, False)
    if token != TOKEN:
        return
    label = MODES[mode]["label"]
    diffusion, vae, encoder = MODES[mode]["files"]
    vision = MODES[mode].get("vision", "")
    args = [
        exe,
        "--listen-ip", "127.0.0.1",
        "--listen-port", str(SD_PORT),
        "--model-dir", MODELS,
        "--offload-to-cpu",
        "--flash-attn", "on",
        "--diffusion-model", diffusion,
        "--vae", vae,
    ]
    if mode == "animate":
        args += ["--t5xxl", encoder, "--cfg-scale", "6.0", "--vae-tiling"]
    elif mode == "qwen":
        args += ["--llm", encoder, "--llm_vision", vision, "--cfg-scale", "6.0", "--backend", "te=cpu", "--vae-tiling"]
    else:
        args += ["--llm", encoder, "--cfg-scale", "1.0"]
    write_stamp(mode)
    log_path = os.path.join(SD_ROOT, "sd-server.log")
    with open(log_path, "ab") as log:
        log.write(("\n--- start %s ---\n" % mode).encode())
        subprocess.Popen(args, cwd=os.path.dirname(exe), stdout=log, stderr=subprocess.STDOUT)
    watch_port(token, mode, SD_PORT, 300, label + " is ready.", label + " did not start.")


def start_llama():
    if port_open(LLAMA_PORT) and not port_open(SD_PORT):
        write_engine("chat")
        STATE["phase"] = "ready"
        STATE["target"] = "chat"
        STATE["error"] = ""
        STATE["message"] = "Chat is ready."
        return "Chat is ready."
    if STATE["phase"] == "loading" and STATE.get("target") == "chat":
        return STATE["message"]
    token = begin("chat", "Starting chat…")
    threading.Thread(target=launch_llama, args=(token,), daemon=True).start()
    return "Starting chat…"


def start_sd(mode):
    missing = missing_files(mode)
    if missing:
        names = ", ".join(os.path.basename(path) for path in missing)
        raise RuntimeError("Still downloading " + names + ".")
    exe = find_sd_exe()
    if not exe:
        raise RuntimeError("The picture server is not installed yet. Wait a minute and try again.")
    if port_open(SD_PORT) and read_engine() == mode and read_stamp() == launch_signature(mode) and STATE["phase"] != "error":
        STATE["phase"] = "ready"
        STATE["target"] = mode
        STATE["error"] = ""
        STATE["message"] = MODES[mode]["label"] + " is ready."
        return STATE["message"]
    if STATE["phase"] == "loading" and STATE.get("target") == mode:
        return STATE["message"]
    label = MODES[mode]["label"]
    token = begin(mode, "Loading " + label + "…")
    threading.Thread(target=launch_sd, args=(token, mode, exe), daemon=True).start()
    return "Loading " + label + "…"


def switch_engine(name):
    if name == "chat":
        return start_llama()
    if name in MODES:
        return start_sd(name)
    raise RuntimeError("Unknown mode.")


def status():
    return {
        "engine": read_engine(),
        "phase": STATE["phase"],
        "error": STATE["error"],
        "message": STATE["message"],
        "llama": port_open(LLAMA_PORT),
        "picture_server": port_open(SD_PORT),
        "picture_ready": not missing_files("picture"),
        "animate_ready": not missing_files("animate"),
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/local/status":
            self.send_json(200, status())
            return
        if not self.proxy():
            super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/local/engine":
            self.switch()
            return
        if not self.proxy():
            self.send_error(404)

    def switch(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            name = json.loads(raw.decode("utf-8") or "{}").get("name", "")
        except json.JSONDecodeError:
            self.send_json(400, {"error": "The mode request was not valid."})
            return
        if not LOCK.acquire(blocking=False):
            self.send_json(409, {"error": "The GPU is already switching. Wait for that to finish."})
            return
        try:
            message = switch_engine(name)
        except RuntimeError as error:
            self.send_json(409, {"error": str(error)})
            return
        finally:
            LOCK.release()
        body = status()
        body["message"] = message
        self.send_json(200, body)

    def send_json(self, code, payload):
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(raw)

    def proxy(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/sdcpp/"):
            upstream = SD
            label = "picture server"
        elif path.startswith("/api/") or path.startswith("/v1/"):
            upstream = LLAMA
            label = "llama-server"
        else:
            return False
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length) if length else None
        request = Request(upstream + self.path, data=body, method=self.command)
        content_type = self.headers.get("Content-Type")
        if content_type:
            request.add_header("Content-Type", content_type)
        try:
            with urlopen(request, timeout=600) as response:
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except HTTPError as error:
            payload = error.read()
            self.send_response(error.code)
            self.send_header("Content-Type", error.headers.get("Content-Type", "text/plain"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except URLError as error:
            payload = f"{label} is not reachable at {upstream}. {error.reason}".encode()
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        return True


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local chat: http://127.0.0.1:{PORT}/")
    print("From a phone on Tailscale, open http://<this-pc-tailscale-ip>:%s/" % PORT)
    print("Leave this window open. Chat uses llama-server. Picture and Animate use the picture server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
