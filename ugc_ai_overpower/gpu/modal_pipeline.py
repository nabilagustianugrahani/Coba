"""Modal.com pipeline — deploy & manage avatar models (NAVA, HappyHorse-1.0, SoulX).

2026 SOTA Avatar Models:
  - NAVA (Native Audio-Visual Alignment): 6.3B params, 720p ~1min, native stereo audio+video, Apache 2.0
  - HappyHorse-1.0: 15B params, text-to-video + image-to-video + native audio + 7-language lip-sync, 1080p in 38s on H100, Apache 2.0
  - SoulX-FlashHead: legacy fallback, A10G compatible
"""
import os, json, logging, base64, uuid, subprocess, time
from pathlib import Path
from typing import Optional

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)

MODAL_APP_NAME = "skynet-avatar-2026"
OUTPUT_VOLUME = "skynet-avatar-outputs"
NAVA_REPO = "https://github.com/bytedance/NAVA"
HAPPYHORSE_REPO = "https://github.com/SoulX-Research/HappyHorse-1.0"
SOULX_REPO = "https://github.com/SoulX-Research/SoulX-FlashHead"


def _get_accounts() -> list[dict]:
    raw = skynet_config.get("modal", "accounts", default=[])
    if not raw:
        tid = os.getenv("MODAL_TOKEN_ID", "")
        tsec = os.getenv("MODAL_TOKEN_SECRET", "")
        if tid and tsec:
            raw = [{"token_id": tid, "token_secret": tsec}]
    return raw


class ModalPipeline:
    _account_rotation_index = 0

    def __init__(self):
        self._current_account: Optional[dict] = None
        self._engine = skynet_config.get("avatar", "engine", default="happyhorse")

    def _get_rotated_account(self) -> dict:
        accounts = _get_accounts()
        if not accounts:
            raise RuntimeError("No Modal accounts configured. Set MODAL_TOKEN_ID + MODAL_TOKEN_SECRET or add to config modal.accounts")
        idx = ModalPipeline._account_rotation_index % len(accounts)
        ModalPipeline._account_rotation_index += 1
        return accounts[idx]

    @property
    def account(self) -> dict:
        if not self._current_account:
            self._current_account = self._get_rotated_account()
        return self._current_account

    def _modal_config(self):
        import modal
        acc = self.account
        modal.config.token_id = acc["token_id"]
        modal.config.token_secret = acc["token_secret"]

    def is_available(self) -> bool:
        try:
            import modal
            self._modal_config()
            with modal.Client() as c:
                _ = c.workspace
            return True
        except Exception as exc:
            log.warning("Modal unavailable: %s", exc)
            return False

    @property
    def engine(self) -> str:
        return self._engine

    @engine.setter
    def engine(self, val: str):
        if val in ("nava", "happyhorse", "soulx"):
            self._engine = val
            skynet_config.set("avatar", "engine", value=val)

    def deploy(self) -> dict:
        """Deploy selected avatar inference function to Modal GPU."""
        import modal
        self._modal_config()

        app = modal.App(MODAL_APP_NAME)
        vol = modal.SharedVolume().persist(OUTPUT_VOLUME)

        if self._engine == "nava":
            return self._deploy_nava(app, modal, vol)
        elif self._engine == "happyhorse":
            return self._deploy_happyhorse(app, modal, vol)
        else:
            return self._deploy_soulx(app, modal, vol)

    def _deploy_nava(self, app, modal, vol) -> dict:
        """Deploy NAVA (2026 SOTA) — 6.3B params, native audio+video, Apache 2.0."""
        image = self._build_nava_image(modal)

        @app.function(
            image=image,
            gpu="A10G",
            shared_volumes={"/outputs": vol},
            timeout=600,
            container_idle_timeout=300,
        )
        def generate_avatar(face_b64: str, audio_b64: str) -> str:
            import base64, uuid
            face_path = "/tmp/face.png"
            audio_path = "/tmp/audio.wav"
            with open(face_path, "wb") as f:
                f.write(base64.b64decode(face_b64))
            with open(audio_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            out_path = f"/outputs/avatar_{uuid.uuid4().hex[:12]}.mp4"
            log.info("Running NAVA inference...")
            result = subprocess.run(
                ["python3", "/nava/inference.py", "--face", face_path,
                 "--audio", audio_path, "--out", out_path],
                capture_output=True, text=True, timeout=500,
            )
            if result.returncode != 0:
                raise RuntimeError(f"NAVA inference failed: {result.stderr}")
            log.info("NAVA avatar: %s", out_path)
            return out_path

        log.info("Deploying NAVA (A10G) 6.3B params...")
        deploy_result = app.deploy()
        return {"status": "deployed", "app": MODAL_APP_NAME, "engine": "NAVA", "gpu": "A10G"}

    def _deploy_happyhorse(self, app, modal, vol) -> dict:
        """Deploy HappyHorse-1.0 (2026 SOTA) — 15B params, 1080p/38s, 7-language lip-sync, Apache 2.0."""
        image = self._build_happyhorse_image(modal)

        @app.function(
            image=image,
            gpu="H100",
            shared_volumes={"/outputs": vol},
            timeout=600,
            container_idle_timeout=300,
        )
        def generate_avatar(face_b64: str, audio_b64: str) -> str:
            import base64, uuid
            face_path = "/tmp/face.png"
            audio_path = "/tmp/audio.wav"
            with open(face_path, "wb") as f:
                f.write(base64.b64decode(face_b64))
            with open(audio_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            out_path = f"/outputs/avatar_{uuid.uuid4().hex[:12]}.mp4"
            log.info("Running HappyHorse-1.0 inference...")
            result = subprocess.run(
                ["python3", "/happyhorse/inference.py", "--face", face_path,
                 "--audio", audio_path, "--out", out_path, "--resolution", "1080p"],
                capture_output=True, text=True, timeout=500,
            )
            if result.returncode != 0:
                raise RuntimeError(f"HappyHorse inference failed: {result.stderr}")
            log.info("HappyHorse avatar: %s", out_path)
            return out_path

        log.info("Deploying HappyHorse-1.0 (H100) 15B params...")
        deploy_result = app.deploy()
        return {"status": "deployed", "app": MODAL_APP_NAME, "engine": "HappyHorse-1.0", "gpu": "H100"}

    def _deploy_soulx(self, app, modal, vol) -> dict:
        """Deploy SoulX-FlashHead (legacy fallback)."""
        image = self._build_image(modal)

        @app.function(
            image=image,
            gpu="A10G",
            shared_volumes={"/outputs": vol},
            timeout=600,
            container_idle_timeout=300,
        )
        def generate_avatar(face_b64: str, audio_b64: str) -> str:
            face_path = "/tmp/face.png"
            audio_path = "/tmp/audio.wav"
            with open(face_path, "wb") as f:
                f.write(base64.b64decode(face_b64))
            with open(audio_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            out_path = f"/outputs/avatar_{uuid.uuid4().hex[:12]}.mp4"
            result = subprocess.run(
                ["python3", "/soulx/inference.py", "--face", face_path,
                 "--audio", audio_path, "--out", out_path],
                capture_output=True, text=True, timeout=500,
            )
            if result.returncode != 0:
                raise RuntimeError(f"SoulX inference failed: {result.stderr}")
            return out_path

        log.info("Deploying SoulX-FlashHead (A10G)...")
        deploy_result = app.deploy()
        return {"status": "deployed", "app": MODAL_APP_NAME, "engine": "SoulX-FlashHead", "gpu": "A10G"}

    def call_avatar(self, face_b64: str, audio_b64: str) -> bytes:
        """Call deployed avatar model on Modal, return raw MP4 bytes.

        Supports NAVA / HappyHorse-1.0 / SoulX via config.
        Auto-rotates Modal accounts on failure.
        """
        import modal
        for attempt in range(max(2, len(_get_accounts()))):
            try:
                self._modal_config()
                f = modal.Function.lookup(MODAL_APP_NAME, "generate_avatar")
                remote_path = f.call(face_b64, audio_b64)
                vol = modal.SharedVolume.lookup(OUTPUT_VOLUME)
                return vol.read_file(remote_path)
            except Exception as e:
                log.warning("Modal call attempt %d failed: %s", attempt + 1, e)
                self._current_account = self._get_rotated_account()
        raise RuntimeError("All Modal accounts exhausted")

    def list_models(self) -> dict:
        return {
            "current_engine": self._engine,
            "available": {
                "nava": "6.3B params, 720p, native audio+video, Apache 2.0",
                "happyhorse": "15B params, 1080p/38s on H100, 7-lang lip-sync, Apache 2.0",
                "soulx": "legacy, A10G compatible",
            },
        }

    def get_quota(self) -> dict:
        try:
            import modal
            self._modal_config()
            with modal.Client() as c:
                usage = c.api_request("GET", "/v1/usage")
                used = usage.get("used_credits", 0.0)
                limit = usage.get("credit_limit", 100.0)
                return {
                    "credits_used": used,
                    "credits_limit": limit,
                    "credits_remaining": max(0.0, limit - used),
                    "period_end": usage.get("period_end"),
                }
        except Exception as exc:
            log.warning("Quota query failed: %s", exc)
            return {"error": str(exc)}

    def list_accounts(self) -> list[dict]:
        results = []
        for i, acc in enumerate(_get_accounts()):
            try:
                import modal
                modal.config.token_id = acc["token_id"]
                modal.config.token_secret = acc["token_secret"]
                with modal.Client() as c:
                    _ = c.workspace
                results.append({"index": i, "status": "connected"})
            except Exception:
                results.append({"index": i, "status": "unreachable"})
        return results

    def rotate(self) -> dict:
        self._current_account = self._get_rotated_account()
        return self._current_account

    def _build_nava_image(self, modal):
        return (
            modal.Image.from_registry("nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04")
            .apt_install("python3", "python3-pip", "ffmpeg", "git", "libgl1-mesa-glx")
            .run_commands(
                "pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124",
                "pip3 install opencv-python pillow numpy scipy moviepy",
                "pip3 install face-alignment",
                f"git clone {NAVA_REPO} /nava --depth 1",
                "cd /nava && pip3 install -r requirements.txt || true",
                "cd /nava && mkdir -p pretrained_models",
            )
        )

    def _build_happyhorse_image(self, modal):
        return (
            modal.Image.from_registry("nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04")
            .apt_install("python3", "python3-pip", "ffmpeg", "git", "libgl1-mesa-glx")
            .run_commands(
                "pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124",
                "pip3 install opencv-python pillow numpy scipy moviepy",
                "pip3 install face-alignment",
                f"git clone {HAPPYHORSE_REPO} /happyhorse --depth 1",
                "cd /happyhorse && pip3 install -r requirements.txt || true",
                "cd /happyhorse && mkdir -p pretrained_models",
            )
        )

    @staticmethod
    def _build_image(modal):
        return (
            modal.Image.from_registry("nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04")
            .apt_install("python3", "python3-pip", "ffmpeg", "git", "libgl1-mesa-glx")
            .run_commands(
                "pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124",
                "pip3 install opencv-python pillow numpy scipy moviepy",
                "pip3 install facenet-pytorch face-alignment",
                f"git clone {SOULX_REPO} /soulx --depth 1",
                "cd /soulx && pip3 install -r requirements.txt || true",
                "cd /soulx && mkdir -p pretrained_models",
            )
        )


def generate_dockerfile(engine: str = "happyhorse") -> str:
    if engine == "nava":
        repo = NAVA_REPO
    elif engine == "happyhorse":
        repo = HAPPYHORSE_REPO
    else:
        repo = SOULX_REPO
    return f"""FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04
RUN apt-get update && apt-get install -y python3 python3-pip ffmpeg git libgl1-mesa-glx && rm -rf /var/lib/apt/lists/*
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
RUN pip3 install opencv-python pillow numpy scipy moviepy
RUN pip3 install face-alignment
RUN git clone {repo} /avatar --depth 1
RUN cd /avatar && pip3 install -r requirements.txt || true && mkdir -p pretrained_models
WORKDIR /avatar
ENTRYPOINT ["python3", "inference.py"]
"""


def check_modal_installed() -> bool:
    try:
        import modal
        return True
    except ImportError:
        return False
