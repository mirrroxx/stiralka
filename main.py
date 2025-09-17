from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = Flask(__name__)

@app.route("/", methods=['POST', 'GET'])
def main():
    print(request.json)
    return "52"


if __name__ == "__main__":
    app.run()