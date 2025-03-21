import sys
import numpy as np
from PySide6.QtCore import *
from PySide6.QtWidgets import QApplication
from irsdk import IRSDK, SessionState
import json
import os
import pickle

PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE_PATH = os.path.join(PATH, 'config.json')
FUEL_DATA_FILE_PATH = os.path.join(PATH, 'last_usage_data.picke')

class Model(QObject):
    ir_connected = Signal()
    ir_disconnected = Signal()
    fuel_data_updated = Signal()  # 燃料データが更新されたことを通知するシグナル
    view_update = Signal(float, float, float, float, float, int)  # デルタ値、現在使用量、平均使用量、進行度、TrackLoc
    
    def __init__(self):
        super().__init__()
        self.__ir = IRSDK()
        self.__is_ir_connected = False
        self.__array_length = 100  # デフォルト配列長（initialize_modelで更新）
        self.load_config()
        
        # 初期化メソッドを呼び出し
        # self.initialize_model()
        
        self.__timer = QTimer()
        self.__timer.timeout.connect(self.check_iracing)
        self.__timer.timeout.connect(self.update_fuel_usage)
        self.__timer.timeout.connect(self.update_view_data)
        self.__timer.start(16)  # 約60fps
    
    def initialize_model(self):
        """モデルのデータを初期化"""
        # まず配列の長さを計算（コースの長さに基づく）
        if self.__is_ir_connected and self.__ir.is_initialized:
            try:
                # コースの長さをキロメートル単位で取得（マイルの場合はキロメートルに変換）
                track_length_km = float(str(self.__ir['WeekendInfo']['TrackLength']).split(' ')[0])
                
                # 1km当たり500要素、小数点以下切り捨て
                self.__array_length = int(track_length_km * 500)
                self.__array_length = max(100, self.__array_length)  # 最小サイズを保証
                
                print(f"コース長: {track_length_km:.2f}km, 配列サイズ: {self.__array_length}")
            except Exception as e:
                print(f"コース長の取得に失敗: {e}")
                self.__array_length = 100  # デフォルト値
        else:
            self.__array_length = 100  # 接続されていない場合はデフォルト値
        
        # 配列を初期化（各行は[ラップの割合, 燃料使用量]）
        self.__avg_fuel_usage = np.zeros((self.__array_length, 2))
        for i in range(self.__array_length):
            self.__avg_fuel_usage[i, 0] = i / (self.__array_length - 1)  # X軸の値を0～1の範囲に初期化
            
        self.__collected_laps_count = 0  # 収集したラップ数
        self.__lap_start_fuel = 0
        self.__current_lap = self.__ir['Lap']
        self.__collecting_lap_data = False
        # 空のNumPy配列として初期化（列は[ラップの割合, 燃料使用量]）
        self.__current_lap_data = np.empty((0, 2))
        self.__invalid_lap = -1  # ピットレーンに入って無効になったラップを記録
        
        # 瞬間的な変化を計算するためのインデックス履歴
        self.__index_history = []  # インデックスの履歴
        self.__usage_history = []  # 使用量の履歴
        self.__history_length = 5  # 履歴の長さ（5つ前と比較）
        
        print("モデルデータを初期化しました")
    
    @property
    def ir(self):
        return self.__ir
    
    @property
    def config(self):
        return self.__config.copy()
    
    @property
    def avg_fuel_usage(self):
        """平均燃料使用量データを取得するためのプロパティ"""
        return self.__avg_fuel_usage.copy()
    
    @property
    def collected_laps_count(self):
        """収集したラップ数を取得するためのプロパティ"""
        return self.__collected_laps_count
    
    @property
    def array_length(self):
        """配列の長さを取得するためのプロパティ"""
        return self.__array_length
    
    def load_fuel_data(self):
        """保存されたデータを読み込むメソッド"""
        if not self.__is_ir_connected or not self.__ir.is_initialized:
            return False
            
        try:         
            # ファイルが存在するか確認
            if not os.path.exists(FUEL_DATA_FILE_PATH):
                print(f"保存されたデータがありません: {FUEL_DATA_FILE_PATH}")
                return False
                
            # ピクルファイルからデータを読み込む
            with open(FUEL_DATA_FILE_PATH, 'rb') as f:
                data = pickle.load(f)
                
            # 保存されたデータが正しい形式か確認
            if (isinstance(data, dict) and 
                'track_id' in data and 
                'car_id' in data and 
                'avg_fuel_usage' in data and 
                'collected_laps_count' in data):
                
                # 現在のトラックと車両が一致するか確認
                if data['track_id'] == self.track_id and data['car_id'] == self.car_id:
                    # データを復元
                    self.__avg_fuel_usage = np.array(data['avg_fuel_usage'])
                    self.__collected_laps_count = data['collected_laps_count']
                    print(f"燃料データを読み込みました: トラックID={self.track_id}, 車両ID={self.car_id}, ラップ数={self.__collected_laps_count}")
                    return True
                else:
                    print(f"保存されたデータが現在の環境と一致しません。保存: Track={data['track_id']}, Car={data['car_id']} 現在: Track={self.track_id}, Car={self.car_id}")
            else:
                print("無効なデータ形式です")
        except Exception as e:
            print(f"データ読み込みエラー: {e}")
        
        return False

    def save_fuel_data(self):
        """燃料使用データを保存するメソッド"""
        # 保存するデータがない場合は終了
        if self.__collected_laps_count == 0:
            print("保存するデータがありません")
            return False
            
        try:
            # 保存するデータを準備
            data = {
                'track_id': self.track_id,
                'car_id': self.car_id,
                'avg_fuel_usage': self.__avg_fuel_usage.tolist(),
                'collected_laps_count': self.__collected_laps_count
            }
            
            # ピクルファイルにデータを保存
            with open(FUEL_DATA_FILE_PATH, 'wb') as f:
                pickle.dump(data, f)
                
            print(f"燃料データを保存しました: {FUEL_DATA_FILE_PATH}")
            return True
        except Exception as e:
            print(f"データ保存エラー: {e}")
            return False
        
    def delete_fuel_data(self):
        try:
            os.remove(FUEL_DATA_FILE_PATH)
        except Exception as e:
            print(f'ファイルの削除に失敗しました: {e}')
    
    def load_config(self):
        """設定ファイルから設定を読み込む。ファイルがない場合はデフォルト値を使用"""
        try:
            # ファイルが存在する場合は読み込み
            if os.path.exists(CONFIG_FILE_PATH):
                with open(CONFIG_FILE_PATH, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 古い設定ファイルに対応するため、デフォルト値を確認
                    self.__config = {
                        'x': loaded_config.get('x', 0),
                        'y': loaded_config.get('y', 0),
                        'w': loaded_config.get('w', 400),
                        'h': loaded_config.get('h', 100),
                        'locked': loaded_config.get('locked', False),
                        'opacity': loaded_config.get('opacity', 1.0),
                        'font_size': loaded_config.get('font_size', 20)
                    }
            else:
                # ファイルが存在しない場合はデフォルト値
                self.__config = {
                    'x': 0,
                    'y': 0,
                    'w': 400,
                    'h': 100,
                    'locked': False,
                    'opacity': 1.0,
                    'font_size': 20
                }
        except Exception as e:
            print(f"設定ファイルの読み込みに失敗しました: {e}")
            # 例外発生時もデフォルト値を設定
            self.__config = {
                'x': 0,
                'y': 0,
                'w': 400,
                'h': 100,
                'locked': False,
                'opacity': 1.0,
                'font_size': 20
            }
    
    def save_config(self):
        """現在の設定をJSONファイルに保存"""
        try:
            with open(CONFIG_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.__config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"設定ファイルの保存に失敗しました: {e}")
        
    def set_config(self, config:dict):
        self.__config = config.copy()
        self.save_config()
        print('設定を変更しました')
        
    def check_iracing(self):
        if self.__is_ir_connected and not (self.__ir.is_initialized and self.__ir.is_connected):
            self.__is_ir_connected = False
            self.ir_disconnected.emit()
            if self.__collected_laps_count > 0:
                self.save_fuel_data()
            self.__ir.shutdown()
            print('iracing disconnected')
        elif not self.__is_ir_connected and self.__ir.startup() and self.__ir.is_initialized:
            self.__is_ir_connected = True
            self.initialize_model()
            self.track_id = self.__ir['WeekendInfo']['TrackID']
            self.car_id = self.__ir['DriverInfo']['Drivers'][self.__ir['DriverInfo']['DriverCarIdx']]['CarID']
            if self.load_fuel_data():
                self.fuel_data_updated.emit()
            self.ir_connected.emit()
            print('iracing connected!')
            
    def update_fuel_usage(self):
        """燃料使用データを更新するためのメソッド"""
        if not self.__is_ir_connected:
            return
            
        # 必要なデータを取得
        try:
            current_lap = self.__ir['Lap']
            current_fuel = self.__ir['FuelLevel']
            current_lap_pct = self.__ir['LapDistPct']
            track_loc = self.__ir['CarIdxTrackSurface'][self.__ir['DriverInfo']['DriverCarIdx']]  # ピットレーンの検出用
            session_state = self.__ir['SessionState']  # セッション状態を取得
            
        except Exception as e:
            print(f"データ取得エラー: {e}")
            return
        
        # セッション状態が4（レース中）でない場合、データ収集を中止
        if session_state != 4:
            if self.__collecting_lap_data:
                print(f"レース中ではないため、データ収集を中止します。SessionState: {session_state}")
                self.__collecting_lap_data = False
                self.__current_lap_data = np.empty((0, 2))
            return
            
        # 新しいラップの開始を検出
        if current_lap != self.__current_lap:
            # 前のラップが有効かつ完了していれば、データを処理
            if self.__collecting_lap_data and len(self.__current_lap_data) > 0:
                # ここで再度TrackLocをチェック - 安全のため、直前のラップのデータが有効かを確認
                # 任意の条件を追加できる（例：ピットに入っていない、十分なデータポイント数、etc）
                if not (track_loc == 3 or track_loc == 0):
                    print(f"周回 {self.__current_lap} は無効です: ラップ終了時にピットレーン検出")
                elif len(self.__current_lap_data) < 30:
                    print(f"周回 {self.__current_lap} は無効です: データポイント不足 ({len(self.__current_lap_data)}ポイント)")
                else:
                    # データをラップ%でソート
                    sorted_indices = np.argsort(self.__current_lap_data[:, 0])
                    sorted_data = self.__current_lap_data[sorted_indices]
                    
                    # 周回の完了度をチェック
                    max_pct = np.max(sorted_data[:, 0])
                    if max_pct < 0.75:
                        print(f"周回 {self.__current_lap} は無効です: 周回完了度不足 ({max_pct:.2f})")
                    else:
                        # 配列長に基づいてデータを正規化
                        normalized_data = np.zeros((self.__array_length, 2))
                        for i in range(self.__array_length):
                            pct = i / (self.__array_length - 1)
                            normalized_data[i, 0] = pct
                            
                            # その%に最も近いデータポイントを見つける
                            closest_idx = np.argmin(np.abs(sorted_data[:, 0] - pct))
                            normalized_data[i, 1] = sorted_data[closest_idx, 1]
                        
                        # 平均データを更新
                        if self.__collected_laps_count == 0:
                            # 初回データ取得時は、そのまま代入
                            self.__avg_fuel_usage = normalized_data.copy()
                        else:
                            # 2回目以降は、既存データと新データの単純平均を計算（要素ごと）
                            self.__avg_fuel_usage = (self.__avg_fuel_usage + normalized_data) / 2
                        
                        self.__collected_laps_count += 1
                        self.fuel_data_updated.emit()
                        print(f"周回 {self.__current_lap} の燃料使用データを処理しました。合計 {self.__collected_laps_count} 周のデータを収集済み。")
            
            # 新しいラップの開始
            self.__current_lap = current_lap
            self.__lap_start_fuel = current_fuel
            
            # 新しいラップ開始時にTrackLocをチェック - ピットレーン/コース外なら即無効化
            if not (track_loc == 3 or track_loc == 0):
                print(f"周回 {current_lap} は無効です: ラップ開始時にピットレーン検出")
                self.__invalid_lap = current_lap
                self.__collecting_lap_data = False
            else:
                # 無効なラップフラグをリセット（新しいラップが有効なので）
                self.__invalid_lap = -1
                self.__collecting_lap_data = True
            
            self.__current_lap_data = np.empty((0, 2))
        
        # 走行中にピットレーンに入った場合、この周のデータ収集をキャンセル
        if not (track_loc == 3 or track_loc == 0):  # トラック外
            if self.__invalid_lap != current_lap:
                print(f"ピットレーン検出: 周回 {current_lap} のデータ収集を中止します。")
                self.__invalid_lap = current_lap  # このラップを無効としてマーク
            
            self.__collecting_lap_data = False
            self.__current_lap_data = np.empty((0, 2))
            return
            
        # 現在のラップのデータを収集（無効なラップでなければ）
        if self.__collecting_lap_data and self.__invalid_lap != current_lap:
            fuel_used = self.__lap_start_fuel - current_fuel
            # 新しいデータポイントを配列に追加
            new_data_point = np.array([[current_lap_pct, fuel_used]])
            self.__current_lap_data = np.vstack((self.__current_lap_data, new_data_point))
    
    def update_view_data(self):
        """ビューを更新するためのデータを計算し、シグナルを発行"""
        if not self.__is_ir_connected:
            return

        try:
            current_lap_pct = self.__ir['LapDistPct']
            track_loc = self.__ir['CarIdxTrackSurface'][self.__ir['DriverInfo']['DriverCarIdx']]
            session_state = self.__ir['SessionState']  # セッション状態を取得
            
            # セッション状態が4（レース中）でない場合、ゼロ値を送信
            if session_state != 4:
                self.view_update.emit(0.0, 0.0, 0.0, 0.0, current_lap_pct, track_loc)
                return
            
            if self.__collecting_lap_data and self.__invalid_lap != self.__ir['Lap'] and self.__collected_laps_count > 0:
                current_usage = self.__lap_start_fuel - self.__ir['FuelLevel']
                avg_data = self.__avg_fuel_usage.copy()
                
                # 現在の進行度に対応するインデックス
                current_idx = current_lap_pct * (self.__array_length - 1)
                
                # 履歴に現在のインデックスと使用量を追加（履歴は保持するが補間には使用しない）
                self.__index_history.append(current_idx)
                self.__usage_history.append(current_usage)
                if len(self.__index_history) > self.__history_length:
                    self.__index_history.pop(0)
                    self.__usage_history.pop(0)
                
                # 現在位置における平均燃料使用量を計算（線形補間）
                exact_idx = current_lap_pct * (self.__array_length - 1)
                lower_idx = int(exact_idx)
                upper_idx = min(lower_idx + 1, self.__array_length - 1)
                fraction = exact_idx - lower_idx
                lower_value = avg_data[lower_idx, 1]
                upper_value = avg_data[upper_idx, 1]
                cum_avg_usage = lower_value + fraction * (upper_value - lower_value)
                
                # 累積差分の計算
                cumul_delta = current_usage - cum_avg_usage
                
                # 瞬間的な燃料使用量の変化率を計算
                # 最新の2点のデータがあれば、その変化率を計算
                if len(self.__usage_history) >= 2 and len(self.__index_history) >= 2:
                    # 最新の2点から変化率を計算
                    latest_usage_diff = self.__usage_history[-1] - self.__usage_history[-2]
                    latest_idx_diff = self.__index_history[-1] - self.__index_history[-2]
                    
                    # インデックスの差が0より大きい場合のみ計算
                    if latest_idx_diff > 0:
                        current_rate = latest_usage_diff / latest_idx_diff
                        
                        # 平均データからも同様の区間での変化率を計算
                        latest_lower_idx = int(self.__index_history[-2])
                        latest_upper_idx = int(self.__index_history[-1])
                        
                        # インデックスが同じ場合は1つ前と比較
                        if latest_lower_idx == latest_upper_idx:
                            latest_lower_idx = max(0, latest_lower_idx - 1)
                        
                        # 配列範囲内に収める
                        latest_lower_idx = max(0, min(latest_lower_idx, self.__array_length - 1))
                        latest_upper_idx = max(0, min(latest_upper_idx, self.__array_length - 1))
                        
                        avg_usage_diff = avg_data[latest_upper_idx, 1] - avg_data[latest_lower_idx, 1]
                        avg_rate = avg_usage_diff / (latest_upper_idx - latest_lower_idx) if latest_upper_idx > latest_lower_idx else 0
                        
                        # 瞬間的な差分 = 現在の変化率 - 平均の変化率
                        inst_delta = current_rate - avg_rate
                    else:
                        inst_delta = 0.0
                else:
                    inst_delta = 0.0
                
                self.view_update.emit(inst_delta, cumul_delta, current_usage, cum_avg_usage, current_lap_pct, track_loc)
            else:
                self.view_update.emit(0.0, 0.0, 0.0, 0.0, current_lap_pct, track_loc)
        
        except Exception as e:
            print(f"ビューデータ更新エラー: {e}")
            
    def print_current_status(self):
        """現在の状態を表示（テスト用）"""
        if not self.__is_ir_connected:
            print("iRacingに接続していません。")
            return
            
        try:
            # 基本情報の表示
            session_state:SessionState = self.__ir['SessionState']
            track_surface = self.__ir['CarIdxTrackSurface'][self.__ir['DriverInfo']['DriverCarIdx']]
            track_location = "トラック上" if (track_surface == 3 or track_surface == 0) else "ピット/コース外"
            
            collection_status = "収集中" if self.__collecting_lap_data and self.__invalid_lap != self.__ir['Lap'] else "停止中"
            
            print(f"--------- ステータス情報 ---------")
            print(f'セッション状態: {session_state}')
            print(f"ラップ: {self.__ir['Lap']} | 進行度: {self.__ir['LapDistPct']:.2f} | 位置: {track_location}")
            print(f"TrackLoc値: {track_surface}")
            print(f"燃料レベル: {self.__ir['FuelLevel']:.2f}L | データ収集: {collection_status}")
            print(f"配列サイズ: {self.__array_length}")
            
            if self.__collecting_lap_data and self.__invalid_lap != self.__ir['Lap']:
                current_points = len(self.__current_lap_data)
                if current_points > 0:
                    current_usage = self.__current_lap_data[-1, 1] if current_points > 0 else 0
                    print(f"現在の周 - データポイント数: {current_points} | 現在の使用量: {current_usage:.4f}L")
            
            # 無効なラップの表示
            if self.__invalid_lap == self.__ir['Lap']:
                print(f"注意: 現在の周回 {self.__ir['Lap']} は無効としてマークされています（ピットレーン検出）")
            
            # 収集データの統計
            collected_laps = self.__collected_laps_count
            print(f"収集済みラップ数: {collected_laps}")
            
            if collected_laps > 0:
                # 燃料使用量の統計情報
                avg_fuel_data = self.__avg_fuel_usage
                
                max_usage = np.max(avg_fuel_data[:, 1])
                min_usage = np.min(avg_fuel_data[:, 1]) if np.min(avg_fuel_data[:, 1]) > 0 else 0
                avg_usage = np.mean(avg_fuel_data[:, 1])
                total_usage = avg_fuel_data[-1, 1]  # 周回終了時の合計使用量
                
                print(f"平均燃料使用量 - 周合計: {total_usage:.4f}L | 平均: {avg_usage:.4f}L | 最大: {max_usage:.4f}L | 最小: {min_usage:.4f}L")
                
                # 簡易なデータ分布表示（25%, 50%, 75%, 100%地点でのデータ）
                quarter_points = [
                    int(self.__array_length * 0.25) - 1,
                    int(self.__array_length * 0.5) - 1,
                    int(self.__array_length * 0.75) - 1,
                    self.__array_length - 1
                ]
                print(f"燃料使用パターン（周の進行度に対する消費量）:")
                for idx in quarter_points:
                    print(f"  {avg_fuel_data[idx, 0]*100:3.0f}%地点: {avg_fuel_data[idx, 1]:.4f}L")
                
            print(f"--------------------------------")
        except Exception as e:
            print(f"データ表示エラー: {e}")


# テスト用コード
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    print("燃料使用履歴テスト開始")
    
    model = Model()
    
    # 燃料データが更新されたときのハンドラを接続
    def on_fuel_data_updated():
        print("燃料データが更新されました!")
        
    model.fuel_data_updated.connect(on_fuel_data_updated)
    
    # 定期的に状態を表示するタイマー
    status_timer = QTimer()
    status_timer.timeout.connect(model.print_current_status)
    status_timer.start(1000)  # 1秒ごとに状態を表示
    
    print("Ctrl+Cで終了")
    
    # 終了シグナルハンドラ
    def signal_handler(signal, frame):
        print("\nテスト終了")
        app.quit()
    
    import signal
    signal.signal(signal.SIGINT, signal_handler)
    
    sys.exit(app.exec())