#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ラズパイPLC UI ランチャー
Webアプリケーション + Chromiumキオスクモードの同時起動
"""

import os
import sys
import time
import subprocess
import threading
import signal
import socket
from pathlib import Path

# プロジェクトのルートディレクトリに移動
project_root = Path(__file__).parent
os.chdir(project_root)

# 環境変数設定
os.environ['PYTHONPATH'] = str(project_root)
os.environ['FLASK_ENV'] = 'production'

class RaspiUILauncher:
    def __init__(self):
        self.web_process = None
        self.browser_process = None
        self.running = True
        
        # 設定
        self.web_port = 5001
        self.web_host = "127.0.0.1"
        self.startup_delay = 10  # Webアプリ起動後、ブラウザ起動までの待機時間（秒）
        
        # シグナルハンドラー設定
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """終了シグナルハンドラー"""
        print(f"🛑 終了シグナル受信 ({signum})")
        self.shutdown()
        sys.exit(0)
    
    def check_display(self):
        """ディスプレイ環境の確認"""
        display = os.environ.get('DISPLAY')
        if not display:
            print("⚠️ DISPLAY環境変数が設定されていません")
            # ラズパイの場合、通常は :0.0 を設定
            os.environ['DISPLAY'] = ':0.0'
            print("🔧 DISPLAY=:0.0 に設定しました")
        else:
            print(f"✅ DISPLAY={display}")
    
    def wait_for_web_server(self):
        """Webサーバーの起動を待機"""
        print(f"⏳ Webサーバー起動待機中... ({self.web_host}:{self.web_port})")
        
        for attempt in range(30):  # 最大30秒待機
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(1)
                    result = sock.connect_ex((self.web_host, self.web_port))
                    if result == 0:
                        print("✅ Webサーバー起動確認")
                        return True
            except Exception:
                pass
            
            time.sleep(1)
            if attempt % 5 == 0:
                print(f"⏳ Webサーバー待機中... ({attempt + 1}/30)")
        
        print("❌ Webサーバー起動を確認できませんでした")
        return False
    
    def start_web_app(self):
        """Webアプリケーションを起動"""
        print("🚀 Webアプリケーション起動中...")
        
        try:
            # main.pyを起動
            cmd = [sys.executable, "main.py"]
            self.web_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                cwd=project_root
            )
            
            print(f"✅ Webアプリケーション起動 (PID: {self.web_process.pid})")
            
            # ログ出力用スレッド
            def log_output():
                if self.web_process and self.web_process.stdout:
                    for line in iter(self.web_process.stdout.readline, ''):
                        if self.running:
                            print(f"[WebApp] {line.rstrip()}")
            
            log_thread = threading.Thread(target=log_output, daemon=True)
            log_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Webアプリケーション起動エラー: {e}")
            return False
    
    def start_chromium_kiosk(self):
        """Chromiumキオスクモードを起動"""
        print("🌐 Chromiumキオスクモード起動中...")
        
        # ディスプレイ環境確認
        self.check_display()
        
        # URL設定
        url = f"http://{self.web_host}:{self.web_port}"
        
        # Chromiumコマンド設定（キオスクモード）
        chromium_cmd = [
            "chromium-browser",
            "--kiosk",  # キオスクモード（全画面表示）
            "--no-first-run",  # 初回起動画面をスキップ
            "--disable-infobars",  # 情報バーを無効化
            "--disable-translate",  # 翻訳機能を無効化
            "--disable-features=TranslateUI",  # 翻訳UIを無効化
            "--disable-component-extensions-with-background-pages",  # バックグラウンド拡張機能を無効化
            "--disable-background-timer-throttling",  # バックグラウンドタイマーを無効化
            "--disable-renderer-backgrounding",  # レンダラーバックグラウンド処理を無効化
            "--disable-backgrounding-occluded-windows",  # 隠れたウィンドウのバックグラウンド処理を無効化
            "--force-device-scale-factor=1",  # スケール固定
            "--window-position=0,0",  # ウィンドウ位置
            "--start-maximized",  # 最大化で起動
            "--autoplay-policy=no-user-gesture-required",  # 自動再生許可
            "--no-sandbox",  # サンドボックス無効化（ラズパイ対応）
            "--disable-dev-shm-usage",  # /dev/shm使用を無効化
            "--disable-gpu",  # GPU無効化（ラズパイ対応）
            url
        ]
        
        try:
            print(f"🌐 起動URL: {url}")
            print(f"🔧 Chromiumコマンド: {' '.join(chromium_cmd[:5])}...")
            
            self.browser_process = subprocess.Popen(
                chromium_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=os.environ.copy()
            )
            
            print(f"✅ Chromiumキオスクモード起動 (PID: {self.browser_process.pid})")
            return True
            
        except FileNotFoundError:
            print("❌ chromium-browserが見つかりません")
            print("💡 インストール方法: sudo apt install chromium-browser")
            return False
        except Exception as e:
            print(f"❌ Chromium起動エラー: {e}")
            return False
    
    def shutdown(self):
        """アプリケーション終了処理"""
        print("🔄 アプリケーション終了処理...")
        self.running = False
        
        # ブラウザ終了
        if self.browser_process:
            try:
                print("🛑 Chromium終了中...")
                self.browser_process.terminate()
                self.browser_process.wait(timeout=5)
                print("✅ Chromium終了")
            except subprocess.TimeoutExpired:
                print("⚠️ Chromium強制終了")
                self.browser_process.kill()
            except Exception as e:
                print(f"⚠️ Chromium終了エラー: {e}")
        
        # Webアプリ終了
        if self.web_process:
            try:
                print("🛑 Webアプリケーション終了中...")
                self.web_process.terminate()
                self.web_process.wait(timeout=10)
                print("✅ Webアプリケーション終了")
            except subprocess.TimeoutExpired:
                print("⚠️ Webアプリケーション強制終了")
                self.web_process.kill()
            except Exception as e:
                print(f"⚠️ Webアプリケーション終了エラー: {e}")
    
    def run(self):
        """メイン実行ループ"""
        print("🚀 ラズパイPLC UIランチャー開始")
        print(f"📂 作業ディレクトリ: {project_root}")
        
        try:
            # 1. Webアプリケーション起動
            if not self.start_web_app():
                print("❌ Webアプリケーション起動に失敗しました")
                return False
            
            # 2. Webサーバーの起動を待機
            if not self.wait_for_web_server():
                print("❌ Webサーバーの起動を確認できませんでした")
                return False
            
            # 3. 少し待機してからブラウザ起動
            print(f"⏳ {self.startup_delay}秒待機後、ブラウザを起動します...")
            time.sleep(self.startup_delay)
            
            # 4. Chromiumキオスクモード起動
            if not self.start_chromium_kiosk():
                print("⚠️ Chromium起動に失敗しましたが、Webアプリは継続実行します")
                print(f"💡 手動でブラウザからアクセス: http://{self.web_host}:{self.web_port}")
            
            print("✅ システム起動完了")
            print("💡 終了するには Ctrl+C を押してください")
            
            # 5. プロセス監視ループ
            while self.running:
                # Webアプリプロセスの監視
                if self.web_process and self.web_process.poll() is not None:
                    print("⚠️ Webアプリケーションが終了しました")
                    break
                
                # ブラウザプロセスの監視（終了時は再起動）
                if self.browser_process and self.browser_process.poll() is not None:
                    print("⚠️ Chromiumが終了しました。再起動中...")
                    time.sleep(5)
                    self.start_chromium_kiosk()
                
                time.sleep(5)  # 5秒間隔で監視
            
            return True
            
        except KeyboardInterrupt:
            print("\n🛑 Ctrl+C で終了要求")
            return True
        except Exception as e:
            print(f"❌ 予期しないエラー: {e}")
            return False
        finally:
            self.shutdown()

def main():
    """メイン関数"""
    # 必要なパッケージの確認
    try:
        import flask
        print("✅ Flask インストール確認済み")
    except ImportError:
        print("❌ Flask がインストールされていません")
        print("💡 インストール方法: pip install flask")
        return False
    
    # ランチャー実行
    launcher = RaspiUILauncher()
    return launcher.run()

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 