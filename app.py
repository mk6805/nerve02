from flask import Flask
import os


app=Flask(__name__)

from controllers  import bp
app.register_blueprint(bp)

if __name__=="__main__":
    app.run(debug=True)
