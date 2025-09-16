from flask import Flask
import sqlite3

app = Flask(__name__)

cur = sqlite3.connect('schedule.bd')
cur.cursor()
cur.execute("CREATE TABLE stiralka")

@app.route('/')
def main():
    return '52'


if __name__ == '__main__':
    app.run(debug=True)