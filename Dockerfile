FROM python:3.11-slim

# ロケール設定（← ここを追加）
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 作業ディレクトリの作成
WORKDIR /app

# 依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリコードをコピー
COPY . .

# Flaskのポートを公開
EXPOSE 5000

# サーバ起動コマンド
CMD ["python", "app.py"]
