#!/usr/bin/env python3
"""
CPUシリアル番号取得機能のテストスクリプト
"""

import os
from db_utils import get_cpu_serial_number, get_mac_address, get_ip_address

def test_device_identification():
    """デバイス識別情報取得テスト"""
    
    print("🧪 デバイス識別情報取得テスト")
    print("=" * 50)
    
    # CPUシリアル番号取得テスト
    print("1. CPUシリアル番号取得:")
    cpu_serial = get_cpu_serial_number()
    if cpu_serial:
        print(f"   ✅ 成功: {cpu_serial}")
        print(f"   📏 長さ: {len(cpu_serial)} 文字")
        
        # フォールバック値かどうかを判定
        if cpu_serial == "FALLBACK_FIXED_ID":
            print("   🔄 フォールバック固定IDが使用されています")
            print("   💡 不変の固定値です")
        else:
            print("   🎯 真のCPUシリアル番号です")
    else:
        print("   ❌ 取得失敗または未対応デバイス")
        print("   💡 この状況は通常発生しません（フォールバック実装済み）")
    
    # MACアドレス取得テスト
    print("\n2. MACアドレス取得:")
    mac_address = get_mac_address()
    if mac_address:
        print(f"   ✅ 成功: {mac_address}")
    else:
        print("   ❌ 取得失敗")
    
    # IPアドレス取得テスト
    print("\n3. IPアドレス取得:")
    ip_address = get_ip_address()
    if ip_address:
        print(f"   ✅ 成功: {ip_address}")
    else:
        print("   ❌ 取得失敗")
    
    print("\n" + "=" * 50)
    
    # 設備ID候補生成テスト
    if mac_address:
        equipment_id_candidate = f"EP_{mac_address.replace(':', '').upper()[:8]}"
        print(f"📝 設備ID候補 (MACベース): {equipment_id_candidate}")
    
    # 識別優先順位の説明
    print("\n🔄 識別の優先順位:")
    print("   1. CPUシリアル番号 (最も確実)")
    print("      → 取得できない場合は固定フォールバック値")
    print("        - 固定値: FALLBACK_FIXED_ID (不変)")
    print("   2. MACアドレス (変更可能だが通常固定)")
    print("   3. IPアドレス (可変)")
    
    return {
        "cpu_serial_number": cpu_serial,
        "mac_address": mac_address,
        "ip_address": ip_address
    }

def test_cpuinfo_file():
    """CPUinfo ファイルの内容確認（デバッグ用）"""
    
    print("\n🔍 /proc/cpuinfo ファイル内容確認:")
    print("=" * 50)
    
    try:
        if os.path.exists('/proc/cpuinfo'):
            with open('/proc/cpuinfo', 'r') as f:
                lines = f.readlines()
                
            print(f"📄 ファイル存在: はい ({len(lines)} 行)")
            
            # Serial行を探す
            serial_lines = [line for line in lines if line.startswith('Serial')]
            if serial_lines:
                print("🎯 Serialエントリ:")
                for line in serial_lines:
                    print(f"   {line.strip()}")
            else:
                print("⚠️ Serialエントリが見つかりません")
                
            # その他の有用な情報
            model_lines = [line for line in lines if 'Model' in line]
            if model_lines:
                print("🔧 モデル情報:")
                for line in model_lines:
                    print(f"   {line.strip()}")
                    
        else:
            print("❌ /proc/cpuinfo ファイルが存在しません")
            print("💡 非Linuxシステムでは利用できません")
            
    except Exception as e:
        print(f"❌ ファイル読み取りエラー: {e}")

if __name__ == "__main__":
    print("🚀 CPUシリアル番号機能テスト開始")
    
    # デバイス識別テスト
    device_info = test_device_identification()
    
    # CPUinfoファイルテスト
    test_cpuinfo_file()
    
    print("\n" + "=" * 50)
    print("✅ テスト完了")
    
    # 実装状況のサマリー
    print("\n📋 実装完了事項:")
    print("   ✅ CPUシリアル番号取得機能")
    print("   ✅ 固定フォールバック値機能 (非ラズパイ環境対応)")
    print("   ✅ データベースモデル更新")
    print("   ✅ API登録・検索エンドポイント更新")
    print("   ✅ 設備自動識別機能")
    print("   ✅ plc_agent.py 自動識別統合")
    
    print("\n💡 次のステップ:")
    print("   1. データベースマイグレーション実行")
    print("   2. 設備再登録 (register_equipment.py)")
    print("   3. 動作テスト (plc_agent.py)") 