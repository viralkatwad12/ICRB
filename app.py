from flask import Flask, request, abort
import hmac
import hashlib
import os
from github import Github

app = Flask(__name__)
GITHUB_SECRET = os.environ.get("GITHUB_SECRET")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
g = Github(GITHUB_TOKEN)

def verify_signature(data, signature):
    mac = hmac.new(GITHUB_SECRET.encode(), msg=data, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected_signature, signature)

@app.route("/webhook", methods=["POST"])
def github_webhook():
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature or not verify_signature(request.data, signature):
        abort(403)
    
    event = request.headers.get("X-GitHub-Event")
    payload = request.json

    if event == "pull_request" and payload.get("action") in ["opened", "synchronize"]:
        pr_url = payload["pull_request"]["url"]
        # Here you would call your function to analyze the PR diff
        # For example: analyze_and_comment(pr_url)
        print(f"Received PR event: {pr_url}")

    return "", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
