# Local chat

One page on this PC for text chat, pictures, and short clips. Chat, Picture, and Animate share the 12 GB graphics card, so the page closes the other model when you switch.

## Open the page

Double-click `local-chat\start-chat.bat` and leave that window open.

- On this PC: http://127.0.0.1:8765/
- On a phone, with Tailscale connected: the address printed in that window

## Page controls

- **Chat** talks to Qwen3-Coder. The first reply after a switch can take a minute.
- **Picture** makes a still image. In Settings, choose **FLUX.2 Klein** for a fast picture or **Qwen-Image 2.1** for the larger image model. Size and steps are in Settings.
- **Animate** makes a short Wan 2.2 clip. Settings has the clip length and an optional start picture.
- Tap a finished picture to open it full size. Tap again, tap **Close**, or press Escape to return.

## Model sources

The weight files stay on this PC. These are the pages they came from.

### Chat

| File used here | Source |
| --- | --- |
| Qwen3-Coder 30B, Q4, already stored by Ollama | https://ollama.com/library/qwen3-coder:30b |
| Text server, llama.cpp CUDA build b12521 | https://github.com/ggml-org/llama.cpp/releases/tag/b12521 |

### Picture: FLUX.2 Klein 4B

| File | Source |
| --- | --- |
| `flux-2-klein-4b-Q4_K.gguf` | https://huggingface.co/adithya-balaji/FLUX.2-klein-4B-GGUF |
| `flux2-vae.safetensors` | https://huggingface.co/Comfy-Org/flux2-dev |
| `Qwen3-4B-Q4_K_M.gguf` | https://huggingface.co/unsloth/Qwen3-4B-GGUF |

### Picture: Qwen-Image 2.1

| File | Source |
| --- | --- |
| `qwen_image_2.1-Q4_K.gguf` | https://huggingface.co/leejet/Qwen-Image-2.1-GGUF |
| `qwen_image_2.1_vae_bf16.safetensors` | https://huggingface.co/Comfy-Org/Qwen-Image-2.1 |
| `Qwen3VL-8B-Instruct-Q4_K_M.gguf` | https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF |

### Animate: Wan 2.2 TI2V 5B

| File | Source |
| --- | --- |
| `Wan2.2-TI2V-5B-Q4_K_S.gguf` | https://huggingface.co/off-grid-ai/Wan2.2-TI2V-5B-GGUF |
| `wan2.2_vae.safetensors` | https://huggingface.co/off-grid-ai/Wan2.2-TI2V-5B-GGUF |
| `umt5-xxl-encoder-Q4_K_M.gguf` | https://huggingface.co/off-grid-ai/Video-Companions-GGUF |

Picture and Animate run on stable-diffusion.cpp: https://github.com/leejet/stable-diffusion.cpp/releases/tag/master-1106-532d2c1
