from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from src.model import Model

class FuelUsageView(QWidget):
    def __init__(self, model:Model, parent=None):
        super().__init__(parent)
        self.model = model
        self.inst_delta = 0.0  # 瞬間的な燃料使用量差分
        self.cumul_delta = 0.0  # 累積燃料使用量差分
        self.current_usage = 0.0  # 現在の燃料使用量
        self.avg_usage = 0.0  # 平均燃料使用量
        self.current_lap_pct = 0.0  # 現在のラップ進行度
        self.track_loc = 0  # 現在のTrackLoc値
        
        # 色の平滑化用の変数
        self._current_color = QColor(200, 200, 200)  # 現在表示中の色（初期値はグレー）
        self._target_color = QColor(200, 200, 200)   # 目標色
        self._color_transition_speed = 0.15          # 色の遷移速度（0.0～1.0）
        self._color_update_timer = QTimer(self)
        self._color_update_timer.timeout.connect(self._update_display_color)
        self._color_update_timer.start(16)  # ~60fps
        
        # ウィジェットの設定
        self.setWindowTitle("燃料使用量比較")
        # モデルの設定からサイズを取得
        self.__config = model.config
        
        # 設定にフォントサイズが含まれていない場合、デフォルト値を追加
        if 'font_size' not in self.__config:
            self.__config['font_size'] = 20  # デフォルトフォントサイズ
            model.set_config(self.__config)
        
        self.setGeometry(self.__config['x'], self.__config['y'], self.__config['w'], self.__config['h'])
        self.set_opacity(self.__config['opacity'])
        
        # 色と描画設定 - 単純化
        self.positive_color = QColor.fromHsv(0, 220, 230)    # 燃費が悪い場合の色（赤）
        self.negative_color = QColor.fromHsv(120, 220, 230)    # 燃費が良い場合の色（緑）
        self.neutral_color = QColor(200, 200, 200)   # 変化なしの色（灰色）
        self.text_color = QColor(255, 255, 255)      # テキスト色（白）
        self.bg_color = QColor(40, 40, 40, 0)        # 背景色（透明）
        
        # ウィジェット属性の設定
        self.setAttribute(Qt.WA_TranslucentBackground)  # 背景を半透明に
        self.setWindowFlag(Qt.WindowStaysOnTopHint)    # 常に最前面に表示
        self.setWindowFlag(Qt.FramelessWindowHint)     # フレームなし
        
        # モデルのシグナルに接続
        self.model.fuel_data_updated.connect(self.update)  # 更新シグナルをウィジェットの再描画に接続
        self.model.ir_connected.connect(self.show)
        self.model.ir_disconnected.connect(self.hide)
        self.model.view_update.connect(self.update_fuel_data)  # 重要：デルタデータ更新用シグナル接続
        
        # マウスドラッグ用の変数
        self.dragging = False
        self.drag_position = QPoint()
        self.setMouseTracking(True)
        
        # リサイズ用の変数
        self.resizing = False
        self.resize_start = QPoint()
        self.start_size = QSize()
        self.resize_margin = 10  # リサイズ可能な端からのピクセル数
        
        # 最小サイズを設定
        self.setMinimumSize(1, 1)
        
    def _update_display_color(self):
        """色を目標色に向かって徐々に変化させる（HSVベース）"""
        if self._current_color == self._target_color:
            return
            
        # 現在の色とターゲット色をHSV形式で取得
        h1, s1, v1, a1 = self._current_color.getHsv()
        h2, s2, v2, a2 = self._target_color.getHsv()
        
        # 色相（Hue）の特別な処理
        # 色相は0-359の循環値なので、最短経路で補間する必要がある
        # 例：350から10への変化は、+20ではなく-340するべき
        if abs(h2 - h1) > 180:
            if h1 < h2:
                h1 += 360
            else:
                h2 += 360
        
        # 新しい色の計算
        h = int(h1 + (h2 - h1) * self._color_transition_speed) % 360
        s = int(s1 + (s2 - s1) * self._color_transition_speed)
        v = int(v1 + (v2 - v1) * self._color_transition_speed)
        a = int(a1 + (a2 - a1) * self._color_transition_speed)
        
        # 更新された色を設定
        self._current_color = QColor.fromHsv(h, s, v, a)
        
        # 再描画をトリガー
        self.update()

    def get_color_by_delta(self, delta):
        """
        inst_delta の値に基づいて彩度を調整し、固定のHSV値から QColor を生成する。
        delta がほぼ 0 の場合は中立色（グレー）を返す。
        結果は直接表示せず、_target_colorに設定する。
        """
        if abs(delta) < 0.0001:
            # 中立色：彩度 0 のグレー（明度 200）
            target_color = QColor.fromHsv(0, 0, 200)
        else:
            # delta の符号に応じて基本の Hue を決定
            hue = 120 if delta < 0 else 0  # 燃費が良い場合は緑、悪い場合は赤
            # インスタント差分が 0.004 以上なら彩度は最大（220）、0 に近ければ最低彩度（150）
            min_sat = 150
            max_delta = 0.004
            # 線形補間：abs(delta)/max_delta の割合で彩度を決定（最大 1.0 でクランプ）
            saturation = min_sat + (220 - min_sat) * min(1.0, abs(delta) / max_delta)
            saturation = int(saturation)
            value = 230  # 明度固定
            target_color = QColor.fromHsv(hue, saturation, value)
        
        # 目標色を設定
        self._target_color = target_color
        
        # 現在の表示色を返す
        return self._current_color
    
    def update_fuel_data(self, inst_delta, cumul_delta, current, avg, lap_pct, track_loc):
        """Modelから送信されたデータを保存して再描画をトリガー"""
        self.inst_delta = inst_delta      # 瞬間的な燃料使用量差分
        self.cumul_delta = cumul_delta    # 累積燃料使用量差分
        self.current_usage = current
        self.avg_usage = avg
        self.current_lap_pct = lap_pct
        self.track_loc = track_loc
        
        # 色の更新処理をトリガー（実際の色変更は_update_display_colorで行う）
        if self.track_loc != 1 and self.track_loc != 2:
            self.get_color_by_delta(self.inst_delta)
        else:
            self._target_color = self.neutral_color
            
        self.update()
    
    def paintEvent(self, event):
        """ウィジェットの描画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 追加パディングの設定（ウィンドウの端に余裕を持たせる）
        window_padding = 20
        text_padding = 5
        
        # 背景の描画
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.bg_color)
        painter.drawRoundedRect(self.rect(), 10, 10)
        
        # 画面の中央に配置するための計算例
        center_x = self.width() // 2
        bar_height = max(20, int(self.height() * 0.15))  # 画面高さの15%をバーの高さとして採用（最小20ピクセル）
        bar_y = int((self.height() - bar_height) / 2)     # 垂直中央に配置
        max_bar_width = (self.width() - window_padding * 2 - 40) // 2  # パディングを考慮
        
        # デルタバー背景の描画（パディングを考慮）
        bg_rect = QRect(window_padding + 20, bar_y, self.width() - window_padding * 2 - 40, bar_height)
        painter.setBrush(QColor(20, 20, 20, 150))
        painter.drawRoundedRect(bg_rect, 5, 5)
        
        painter.setPen(Qt.NoPen)
        
        # バーの幅は従来通り累計差分で決定
        normalized_delta = min(1.0, abs(self.cumul_delta) / 0.125)
        bar_width = int(normalized_delta * max_bar_width)

        if bar_width > 1:
            # バーの向きと幅は累計差分で決定
            if self.cumul_delta < 0:  # 累計差分が負の場合（燃費が良い）
                # 色は現在の表示色を使用（平滑化された色）
                painter.setBrush(self._current_color)

                # バーは右側に描画
                painter.drawRect(
                center_x, bar_y + 2, bar_width, bar_height - 4)
            elif self.cumul_delta > 0:  # 累計差分が正の場合（燃費が悪い）
                # 色は現在の表示色を使用（平滑化された色）
                painter.setBrush(self._current_color)

                # バーは左側に描画
                painter.drawRect(
                center_x - bar_width, bar_y + 2, bar_width, bar_height - 4)
        
        # 設定されたフォントサイズを使用
        painter.setFont(QFont("Arial", self.__config['font_size'], QFont.Bold))
        delta_text = f"{self.cumul_delta:+.3f}L"  # テキストは従来通り累計差分を表示
        
        # テキストのサイズ計算
        text_rect = painter.fontMetrics().boundingRect(delta_text)
        text_width = text_rect.width() + text_padding * 2  # パディングを含むテキスト幅
        
        # テキスト位置の計算（累積差分に基づく）
        if self.cumul_delta > 0:
            text_x_offset = min(1.0, self.cumul_delta / 0.125)
        else:
            text_x_offset = max(-1.0, self.cumul_delta / 0.125)
        
        # 基本位置の計算
        base_x = center_x - int(text_x_offset * max_bar_width) - text_width // 2
        
        # ウィンドウの端からのパディングを確保
        safe_left = window_padding
        safe_right = self.width() - window_padding - text_width
        
        # 端に寄りすぎないように位置を調整
        text_x = max(safe_left, min(base_x, safe_right))
        text_y = bar_y + bar_height + text_rect.height() + 10
        
        # テキスト背景矩形の設定
        text_bg_rect = QRect(text_x, text_y - text_rect.height(), text_width, text_rect.height() + text_padding)
        
        # テキスト背景を描画
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(20, 20, 20, 150))
        painter.drawRoundedRect(text_bg_rect, 5, 5)
        
        # テキストの色は累計差分に基づく（中間色なし）
        if abs(self.cumul_delta) < 0.001 or (self.track_loc == 1 or self.track_loc == 2):
            painter.setPen(self.neutral_color)
        elif self.cumul_delta > 0:
            painter.setPen(self.positive_color)  # 燃費が悪い場合は赤
        else:
            painter.setPen(self.negative_color)  # 燃費が良い場合は緑
        
        # 調整された位置にテキストを描画
        painter.drawText(text_bg_rect, Qt.AlignCenter, delta_text)
        
        # リサイズハンドルなどの描画
        if not self.__config['locked']:
            pen = QPen(QColor(255, 255, 255, 80))
            pen.setWidth(1)
            painter.setPen(pen)
            resize_triangle = QPolygon([
                QPoint(self.width() - 10, self.height()),
                QPoint(self.width(), self.height() - 10),
                QPoint(self.width(), self.height())
            ])
            painter.setBrush(QColor(255, 255, 255, 80))
            painter.drawPolygon(resize_triangle)
    
    def contextMenuEvent(self, event):
        """右クリックメニューの表示"""
        menu = QMenu(self)
        
        # ロックアクション
        lock_action = menu.addAction("ウィンドウをロック")
        lock_action.setCheckable(True)
        lock_action.setChecked(self.__config['locked'])
        lock_action.triggered.connect(self.toggle_lock)
        
        # 透明度設定のサブメニュー
        opacity_menu = menu.addMenu("透明度")
        
        # 透明度のオプション
        opacity_options = [("100%", 1.0), ("90%", 0.9), ("80%", 0.8), ("70%", 0.7), ("60%", 0.6), ("50%", 0.5)]
        opacity_group = QActionGroup(self)
        
        for label, value in opacity_options:
            action = opacity_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(abs(self.windowOpacity() - value) < 0.09)  # 現在の値に近いものをチェック
            action.triggered.connect(lambda checked, v=value: self.set_opacity(v))
            opacity_group.addAction(action)
        
        # フォントサイズ設定のサブメニュー
        font_menu = menu.addMenu("フォントサイズ")
        
        # フォントサイズのオプション
        font_size_options = [16, 18, 20, 22, 24, 26, 28, 30]
        font_group = QActionGroup(self)
        
        for size in font_size_options:
            action = font_menu.addAction(f"{size}px")
            action.setCheckable(True)
            action.setChecked(self.__config['font_size'] == size)
            action.triggered.connect(lambda checked, s=size: self.set_font_size(s))
            font_group.addAction(action)
        
        # カスタムフォントサイズオプションの追加
        font_menu.addSeparator()
        custom_font_action = font_menu.addAction("カスタムサイズ...")
        custom_font_action.triggered.connect(self.show_custom_font_dialog)
        
        # セパレータ
        menu.addSeparator()
        
        # リセットアクション
        reset_position_action = menu.addAction("位置をリセット")
        reset_position_action.triggered.connect(self.reset_position)
        
        # データリセットアクション
        reset_data_action = menu.addAction("データをリセット")
        reset_data_action.triggered.connect(self.reset_data)
        
        # セパレータ
        menu.addSeparator()
        
        # 終了アクション
        exit_action = menu.addAction("終了")
        exit_action.triggered.connect(QApplication.instance().quit)
        
        # メニューを表示
        menu.exec(event.globalPos())

    def reset_data(self):
        """データをリセットする（モデルの初期化）"""
        # 確認ダイアログを表示
        reply = QMessageBox.question(
            self, 
            "データリセット確認", 
            "現在の燃料使用データをリセットしますか？\nこの操作は元に戻せません。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # デフォルトはNoボタン
        )
        
        if reply == QMessageBox.Yes:
            # モデルのinitialize_modelメソッドを実行してデータをリセット
            self.model.initialize_model()
            self.model.delete_fuel_data()
            # 通知
            QToolTip.showText(
                self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2)),
                "データがリセットされました",
                self
            )

    def show_custom_font_dialog(self):
        """カスタムフォントサイズ設定ダイアログを表示"""
        current_size = self.__config['font_size']
        
        # 入力ダイアログを表示
        size, ok = QInputDialog.getInt(
            self, 
            "カスタムフォントサイズ",
            "フォントサイズを入力してください（8～72px）:",
            current_size,  # デフォルト値
            8,             # 最小値
            72,            # 最大値
            1              # ステップ値
        )
        
        # OKが押された場合のみフォントサイズを変更
        if ok:
            self.set_font_size(size)

    def set_font_size(self, size):
        """フォントサイズを設定"""
        self.__config['font_size'] = size
        self.model.set_config(self.__config)
        self.update()  # 画面を再描画
        
        # 設定変更を通知（一時的なトースト通知）
        QToolTip.showText(self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2)), 
                        f"フォントサイズを{size}pxに変更しました", self)
    
    def toggle_lock(self, checked):
        """ウィンドウのロック状態を切り替え"""
        self.__config['locked'] = checked
        self.model.set_config(self.__config)
        self.update()  # リサイズハンドルの表示/非表示を更新
        
        # ロック状態を表示（一時的なトースト通知）
        status = "ロックされました" if checked else "ロック解除されました"
        QToolTip.showText(self.mapToGlobal(QPoint(self.width() // 2, self.height() // 2)), status, self)
    
    def set_opacity(self, opacity):
        """ウィンドウの透明度を設定"""
        self.setWindowOpacity(opacity)
        self.__config['opacity'] = opacity
        self.model.set_config(self.__config)
    
    def reset_position(self):
        """ウィンドウの位置をリセット"""
        self.move(0,0)
        
        # 位置をモデルの設定に保存
        self.__config['x'] = self.x()
        self.__config['y'] = self.y()
        self.model.set_config(self.__config)
    
    def mousePressEvent(self, event):
        """マウスボタン押下イベント - ドラッグまたはリサイズ開始"""
        if self.__config['locked']:
            return  # ロックされている場合は何もしない
            
        if event.button() == Qt.LeftButton:
            # 右下の角をクリックした場合はリサイズ開始
            if self.is_in_resize_area(event.position().toPoint()):
                self.resizing = True
                self.resize_start = event.globalPosition().toPoint()
                self.start_size = self.size()
                self.setCursor(Qt.SizeFDiagCursor)  # リサイズカーソルに変更
            else:
                # それ以外の場所をクリックした場合はドラッグ開始
                self.dragging = True
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                self.setCursor(Qt.ClosedHandCursor)  # 手のひらを閉じたカーソルに変更
            
            event.accept()
    
    def mouseMoveEvent(self, event):
        """マウス移動イベント - ウィンドウ移動またはリサイズ"""
        if self.__config['locked']:
            return  # ロックされている場合は何もしない
            
        if self.resizing and event.buttons() & Qt.LeftButton:
            # リサイズ中
            diff = event.globalPosition().toPoint() - self.resize_start
            new_width = max(self.minimumWidth(), self.start_size.width() + diff.x())
            new_height = max(self.minimumHeight(), self.start_size.height() + diff.y())
            self.resize(new_width, new_height)
            event.accept()
        elif self.dragging and event.buttons() & Qt.LeftButton:
            # ドラッグ中
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
        else:
            # マウスカーソルの形状を変更
            if self.is_in_resize_area(event.position().toPoint()) and not self.__config['locked']:
                self.setCursor(Qt.SizeFDiagCursor)  # リサイズカーソル
            else:
                self.setCursor(Qt.ArrowCursor)  # 通常カーソル
    
    def mouseReleaseEvent(self, event):
        """マウスボタンリリースイベント - ドラッグまたはリサイズ終了"""
        if self.__config['locked']:
            return  # ロックされている場合は何もしない
            
        if event.button() == Qt.LeftButton:
            # ドラッグ終了
            if self.dragging:
                self.dragging = False
                # 位置をモデルの設定に保存
                self.__config['x'] = self.x()
                self.__config['y'] = self.y()
            
            # リサイズ終了
            if self.resizing:
                self.resizing = False
                # サイズをモデルの設定に保存
                self.__config['w'] = self.width()
                self.__config['h'] = self.height()
                
            self.model.set_config(self.__config)
            
            # カーソルを元に戻す
            self.setCursor(Qt.ArrowCursor)
            
            event.accept()
    
    def is_in_resize_area(self, pos):
        """指定された位置がリサイズエリア内かどうかをチェック"""
        return (self.width() - pos.x() <= self.resize_margin and 
                self.height() - pos.y() <= self.resize_margin)