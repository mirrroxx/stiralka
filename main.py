from flask import Flask, request
app = Flask(__name__)

@app.route("/", methods=['POST'])
def main():
    print(request.json['message']['text'])
    return "52"


if __name__ == "__main__":
    app.run()