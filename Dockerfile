FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir requests

COPY . .

EXPOSE 8080

CMD ["python", "bot.py", "0"]
