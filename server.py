from flask import Flask, request, send_file
from PIL import Image
import boto3, os

app = Flask(__name__)
session = boto3.session.Session()

# connect server s3
s3 = session.client(
    's3',
    endpoint_url = 'https://sgp1.digitaloceanspaces.com',
    aws_access_key_id = 'DO009UETF8JC39EPN6C4',
    aws_secret_access_key = 'wQSw/gBmZ2JTikESjHSbQqe9p4BWthW05JYbnmNY32k',
)



@app.errorhandler(404)
def page_not_found(e):
    return '', 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)