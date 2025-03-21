import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import signal
from src.model import Model
from src.view import FuelUsageView

def main():
    # アプリケーションの初期化
    app = QApplication(sys.argv)
    
    print("燃料使用データ比較アプリケーション 起動中...")
    
    # モデルとビューの作成
    model = Model()
    view = FuelUsageView(model)
    
    # 燃料データが更新されたときのハンドラ
    def on_fuel_data_updated():
        print("燃料使用履歴データが更新されました")
    
    model.fuel_data_updated.connect(on_fuel_data_updated)
    
    # 終了シグナルハンドラ
    def signal_handler(sig, frame):
        print("\nアプリケーションを終了します")
        
        if model.save_fuel_data():
            print('燃料使用データを保存しました')
        app.quit()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    app.aboutToQuit.connect(lambda: model.save_fuel_data())
    
    # デバッグ用状態表示タイマー（オプション）
    status_timer = QTimer()
    status_timer.timeout.connect(model.print_current_status)
    status_timer.start(5000)  # 5秒ごとに状態を表示
    
    print("アプリケーション起動完了")
    print("Ctrl+Cで終了")
    
    # アプリケーション実行
    sys.exit(app.exec())

if __name__ == "__main__":
    main()