FROM python:3.12-slim-bookworm
ARG TORCH_VARIANT=cpu
ARG COMFYUI_REF=master
RUN apt-get update && apt-get install -y --no-install-recommends git libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch ${COMFYUI_REF} https://github.com/comfyanonymous/ComfyUI.git /opt/ComfyUI
WORKDIR /opt/ComfyUI
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/${TORCH_VARIANT} \
    && pip install --no-cache-dir -r requirements.txt
EXPOSE 8188
ENTRYPOINT ["python", "main.py", "--listen", "0.0.0.0", "--port", "8188"]
# Em CPU o ComfyUI precisa de --cpu; o compose base adiciona via CMD.
CMD ["--cpu"]
