from flask_sqlalchemy import SQLAlchemy

# SQLAlchemy インスタンスを作成
db = SQLAlchemy()

def init_db(app):
    """データベースを初期化する"""
    import os
    
    # 環境変数からDATABASE_URLを取得、なければSQLiteをデフォルトとする
    database_url = os.getenv('DATABASE_URL', 'sqlite:///equipment.db')
    
    print(f"🔍 [DEBUG] データベース設定: {database_url}")
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # データベースを初期化
    db.init_app(app)
    
    with app.app_context():
        # テーブルを作成
        db.create_all()
        print("✅ データベースが初期化されました") 