from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello Bora 🚀, uygulaman çalışıyor!"

# Gunicorn app:app ile çalışacağı için alttaki blok yerelde işe yarar,
# Render/Gunicorn için şart değil ama kalmasında sakınca yok.
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
