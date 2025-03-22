# iRFuelDelta

## インストール
```git clone https://github.com/ellettie/iRFuelDelta```

## 使用方法
pythonをインストールしてください  https://www.python.org/downloads/  
コマンドプロンプト等で、このパッケージに移動し、setup.batを実行してください。仮想環境が作成され、必要なライブラリがインストールされます。  
setup-clean.batは終了時に仮想環境を破棄します。  

オーバーレイ上で右クリックをすることでメニューを開きます。

## 要件
python 3.10 - 3.11

## 仕様
トラック上の位置ごとの燃料の使用状況をそれまでの平均使用状況と比較します。  
ピットレーンを走行したラップ(アウトラップやインラップ)のデータは使用されません。  
パレードラップのデータは使用されません。  
なのでアウトラップから数えて3周目からデルタバーが表示されます。

## 使用ライブラリとライセンス
このアプリケーションは以下のオープンソースライブラリを使用しています：

- PySide6 (LGPL-3.0) - https://doc.qt.io/qtforpython-6/licenses.html
- NumPy (BSD-3-Clause) - https://numpy.org/doc/stable/license.html
- pyirsdk (MIT) - https://github.com/kutu/pyirsdk/blob/master/LICENSE

各ライブラリの詳細なライセンス情報については、それぞれの公式サイトをご参照してください。
