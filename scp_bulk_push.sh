#!/bin/bash

PROJECT_DIR="raspi_plc_ui-main"
TARGET_DIR="/home/pi/"
SERVICE_FILE="systemd/plc_ui.service"
REMOTE_SERVICE_PATH="/etc/systemd/system/plc_ui.service"
USER="pi"
CSV_FILE="ip_list.csv"
LOG_DIR="transfer_log"
TIMESTAMP=$(date +"%Y%m%d_%H%M")
LOG_FILE="$LOG_DIR/transfer_$TIMESTAMP.txt"

mkdir -p "$LOG_DIR"

echo "📦 プロジェクトと systemd の一括転送開始"
echo "==== $(date) ====" > "$LOG_FILE"

while IFS=, read -r ip; do
  [[ "$ip" == "ip_address" ]] && continue
  echo "📤 $ip に転送中..."

  # 1. プロジェクト転送
  scp -r "$PROJECT_DIR" "$USER@$ip:$TARGET_DIR" &>> "$LOG_FILE"
  if [[ $? -ne 0 ]]; then
    echo "❌ プロジェクト転送失敗: $ip" | tee -a "$LOG_FILE"
    continue
  fi

  # 2. systemd サービスファイル転送
  scp "$SERVICE_FILE" "$USER@$ip:/home/pi/" &>> "$LOG_FILE"

  # 3. systemd 設定（SSH実行）
  ssh "$USER@$ip" <<EOF
sudo mv /home/pi/$(basename $SERVICE_FILE) $REMOTE_SERVICE_PATH
sudo systemctl daemon-reload
sudo systemctl enable plc_ui.service
sudo systemctl start plc_ui.service
EOF

  if [[ $? -eq 0 ]]; then
    echo "✅ $ip: 転送＆systemd 起動成功" | tee -a "$LOG_FILE"
  else
    echo "❌ $ip: systemd 設定エラー" | tee -a "$LOG_FILE"
  fi

done < "$CSV_FILE"

echo "🏁 全転送＆起動処理完了: $LOG_FILE"
