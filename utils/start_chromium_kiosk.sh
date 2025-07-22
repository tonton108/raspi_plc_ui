#!/bin/bash
# ラズパイ用 Chromium キオスクモード起動スクリプト
# 使用方法: ./start_chromium_kiosk.sh [URL] [DISPLAY]

# 設定
DEFAULT_URL="http://localhost:5001"
DEFAULT_DISPLAY=":0.0"
WAIT_TIME=10  # Webサーバー起動待機時間（秒）

# 引数設定
URL=${1:-$DEFAULT_URL}
DISPLAY_NUM=${2:-$DEFAULT_DISPLAY}

echo "🌐 Chromium キオスクモード起動スクリプト"
echo "📍 URL: $URL"
echo "🖥️ DISPLAY: $DISPLAY_NUM"

# DISPLAY環境変数設定
export DISPLAY=$DISPLAY_NUM

# Webサーバーの起動確認
echo "⏳ Webサーバーの起動を確認中..."
for i in $(seq 1 $WAIT_TIME); do
    if curl -s --connect-timeout 2 "$URL" > /dev/null 2>&1; then
        echo "✅ Webサーバー起動確認"
        break
    fi
    
    echo "⏳ Webサーバー待機中... ($i/$WAIT_TIME)"
    sleep 1
    
    if [ $i -eq $WAIT_TIME ]; then
        echo "⚠️ Webサーバーの起動を確認できませんでした"
        echo "💡 手動でWebアプリを起動してから再実行してください"
        exit 1
    fi
done

# 既存のChromiumプロセスを終了
echo "🔄 既存のChromiumプロセスを確認中..."
if pgrep -f "chromium-browser" > /dev/null; then
    echo "🛑 既存のChromiumプロセスを終了します"
    pkill -f "chromium-browser"
    sleep 2
fi

# Chromiumキオスクモード起動
echo "🚀 Chromiumキオスクモード起動中..."

chromium-browser \
    --kiosk \
    --no-first-run \
    --disable-infobars \
    --disable-translate \
    --disable-features=TranslateUI \
    --disable-component-extensions-with-background-pages \
    --disable-background-timer-throttling \
    --disable-renderer-backgrounding \
    --disable-backgrounding-occluded-windows \
    --force-device-scale-factor=1 \
    --window-position=0,0 \
    --start-maximized \
    --autoplay-policy=no-user-gesture-required \
    --no-sandbox \
    --disable-dev-shm-usage \
    --disable-gpu \
    --disable-software-rasterizer \
    --disable-features=VizDisplayCompositor \
    --no-zygote \
    --single-process \
    "$URL" &

CHROMIUM_PID=$!
echo "✅ Chromium起動完了 (PID: $CHROMIUM_PID)"
echo "💡 終了するには Ctrl+C を押すか、プロセスを手動で終了してください"

# シグナルハンドラー
trap 'echo "🛑 終了要求受信"; kill $CHROMIUM_PID 2>/dev/null; exit 0' INT TERM

# プロセス監視
while kill -0 $CHROMIUM_PID 2>/dev/null; do
    sleep 5
done

echo "�� Chromiumが終了しました" 