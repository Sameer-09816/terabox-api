from flask import Flask, request, Response
from flask_cors import CORS # Import CORS
import requests
import os

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}) # Enable CORS for /api/* routes from any origin

TARGET_API_BASE_URL = "https://terabox-pika.vercel.app/?url="

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    # Check if the request is for an API route or something else
    if request.path.startswith('/api/'):
        # If it's an API path but not matched by a specific route, return 404
        return {"error": "API endpoint not found"}, 404
    return """
    <h1>Proxy API</h1>
    <p>This API proxies requests to the terabox-pika service.</p>
    <p>Usage: Make a GET request to <code>/api/proxy?terabox_url=<your_terabox_video_url></code></p>
    <p>For example: <code>/api/proxy?terabox_url=https://www.terabox.com/sharing/somevideo123</code></p>
    """, 200 # Changed to 200 for the root/instruction page

@app.route('/api/proxy', methods=['GET'])
def proxy_to_terabox_pika():
    terabox_video_url = request.args.get('terabox_url')

    if not terabox_video_url:
        return {"error": "Missing 'terabox_url' query parameter"}, 400

    target_url = f"{TARGET_API_BASE_URL}{terabox_video_url}"

    try:
        # Forward only essential headers like User-Agent. Avoid forwarding Host, etc.
        # The target API might behave differently or reject requests with unexpected forwarded headers.
        headers_to_forward = {
            'User-Agent': request.headers.get('User-Agent', 'ProxyFetcher/1.0')
        }
        
        external_response = requests.get(
            target_url, 
            headers=headers_to_forward, 
            stream=True, 
            timeout=30 # 30 second timeout for the external request
        )
        external_response.raise_for_status()

        def generate_stream():
            for chunk in external_response.iter_content(chunk_size=8192):
                yield chunk

        response_headers = {}
        if 'Content-Type' in external_response.headers:
            response_headers['Content-Type'] = external_response.headers['Content-Type']
        if 'Content-Disposition' in external_response.headers:
            response_headers['Content-Disposition'] = external_response.headers['Content-Disposition']
        if 'Content-Length' in external_response.headers:
            response_headers['Content-Length'] = external_response.headers['Content-Length']

        return Response(
            generate_stream(),
            status=external_response.status_code,
            headers=response_headers
        )

    except requests.exceptions.Timeout:
        return {"error": "The request to the target API timed out"}, 504
    except requests.exceptions.HTTPError as e:
        try:
            error_content = e.response.json()
        except ValueError:
            error_content = e.response.text
        return {"error": "Target API returned an error", "status_code": e.response.status_code, "details": error_content}, e.response.status_code
    except requests.exceptions.RequestException as e:
        app.logger.error(f"RequestException during proxy: {str(e)}")
        return {"error": f"Could not connect to target API: {str(e)}"}, 502
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}")
        return {"error": "An internal server error occurred"}, 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001)) # Changed local port slightly just for differentiation
    app.run(host='0.0.0.0', port=port, debug=True)
