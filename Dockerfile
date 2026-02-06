# Dockerfile - fixed syntax for Railway + Camoufox

FROM python:3.11-bookworm

# Install all required system libs for Camoufox headless Firefox
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgtk-3-0 \
    libnss3 \
    libdbusmenu-gtk3-4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcairo2 \
    libpango-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libxrandr2 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxfixes3 \
    libxscrnsaver \
    libxmu6 \
    libxpm4 \
    libxft2 \
    libxinerama1 \
    libxkbcommon0 \
    libxkbfile1 \
    libxshmfence1 \
    libxxf86vm1 \
    libgl1-mesa-glx \
    libegl1-mesa \
    libgbm1 \
    libasound2 \
    libstdc++6 \
    wget \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV PORT=8080

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "$PORT", "--log-level", "info"]
