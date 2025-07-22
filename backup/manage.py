from flask.cli import FlaskGroup
from app import app, db, periodic_log_fetch, wait_for_db
import threading

# 🔽 モデルを明示的にimport
from db.models import Equipment, Log

cli = FlaskGroup(app)

@cli.command("runserver")
def runserver():
    with app.app_context():
        wait_for_db(db.session)
        threading.Thread(target=periodic_log_fetch, daemon=True).start()
        app.run(debug=True, host="0.0.0.0")

if __name__ == '__main__':
    cli()