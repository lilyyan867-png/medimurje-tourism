from flask import Flask, send_from_directory, Response
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "mirror", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "mirror", "static")

app = Flask(
    __name__,
    template_folder="mirror/templates",
    static_folder="mirror/static",
    static_url_path="/static"
)


def serve_html(filename):
    """直接返回 HTML 文件内容，不经过 Jinja2 模板引擎"""
    path = os.path.join(TEMPLATE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    return Response(html, mimetype="text/html")


@app.route("/")
def index():
    return serve_html("index.html")


@app.route("/nature")
def nature():
    return serve_html("nature.html")


@app.route("/attractions")
def attractions():
    return serve_html("attractions.html")


@app.route("/events")
def events():
    return serve_html("events.html")


@app.route("/taste")
def taste():
    return serve_html("taste.html")


@app.route("/plan")
def plan():
    return serve_html("plan.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)