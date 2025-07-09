from pymcprotocol import Type3E
import socket

def test_connection(ip: str, port: int, timeout: float = 3.0) -> bool:
    """
    三菱PLC（MCプロトコル）との通信テスト

    - 指定IP/ポートに接続
    - D100番地を1点読んで、応答があれば「接続成功」
    """
    try:
        # 先に socket だけで接続確認（タイムアウト対応）
        sock = socket.create_connection((ip, port), timeout=timeout)
        sock.close()

        mc = Type3E()
        mc.connect(ip, port)  # timeoutは渡さない

        # 実際の通信：D100 を1点だけ読んでみる
        result = mc.batchread_wordunits(headdevice="D100", readsize=1)

        # 通信結果が取得できれば接続成功と判定
        if result and isinstance(result, list):
            return True

    except (socket.timeout, socket.error) as e:
        print(f"[接続失敗] 通信エラー: {e}")
    except Exception as e:
        print(f"[接続失敗] その他のエラー: {e}")

    return False

def read_d100(ip: str, port: int) -> int:
    mc = Type3E()
    mc.connect(ip, port)
    result = mc.batchread_wordunits(headdevice="D100", readsize=1)
    if result and isinstance(result, list):
        return int(result[0])
    raise Exception("読み取り失敗")