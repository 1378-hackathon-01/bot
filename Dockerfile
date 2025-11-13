# A?>;L7C5< >D8F80;L=K9 >1@07 Python 3.13
FROM python:3.13-slim

# #AB0=02;8205< @01>GCN 48@5:B>@8N
WORKDIR /app

# >?8@C5< D09; A 7028A8<>ABO<8
COPY StudGram_bot/requirements.txt .

# 1=>2;O5< pip 8 CAB0=02;8205< 7028A8<>AB8
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# >?8@C5< 25AL :>4 1>B0
COPY StudGram_bot/ .

# #AB0=02;8205< ?5@5<5==K5 >:@C65=8O 4;O :>@@5:B=>9 @01>BK A UTF-8
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=utf-8

# 0?CA:05< 1>B0
CMD ["python", "main.py"]