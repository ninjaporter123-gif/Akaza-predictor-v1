FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

COPY . .

CMD ["python", "bot.py", "0"]
