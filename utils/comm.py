# utils/comm.py（共通インターフェース）
def test_plc_connection(ip, port, manufacturer):
    if manufacturer == "Mitsubishi":
        from .mitsubishi import test_connection
        return test_connection(ip, port)
    elif manufacturer == "Omron":
        from .omron import test_connection
        return test_connection(ip, port)
    elif manufacturer == "Keyence":
        from .keyence import test_connection
        return test_connection(ip, port)
    else:
        return False
# utils/comm.py

def read_d100(ip, port, manufacturer):
    if manufacturer == "Mitsubishi":
        try:
            from .mitsubishi import read_d100
            return read_d100(ip, port)
        except Exception as e:
            print(f"[モック] Mitsubishi通信失敗 → 仮値返す: {e}")
            return 123

    # 他メーカーは仮実装
    print(f"[モック] {manufacturer}の読み取り: 仮に100を返す")
    return 100

