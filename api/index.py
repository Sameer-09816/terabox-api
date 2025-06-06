from flask import Flask, request, Response
import requests
import os

app = Flask(__name__)

TARGET_API_BASE_URL = "https://terabox-pika.vercel.app/?url="

@app.route('/', defaults={'path': ''}) # Optional: Catch-all for root, redirects to instructions
@app.route('/<path:path>') # Optional: Catch-all for other paths
def catch_all(path):
    return """
    <h1>Proxy API</h1>
    <p>Usage: Make a GET request to <code>/api/proxy?terabox_url=<your_terabox_video_url></code></p>
    <p>For example: <code>/api/proxy?terabox_url=https://www.terabox.com/sharing/somevideo123</code></p>
    """, 404

@app.route('/api/proxy', methods=['GET'])
def proxy_to_terabox_pika():
    # Get the 'terabox_url' query parameter from the request
    terabox_video_url = request.args.get('terabox_url')

    if not terabox_video_url:
        return {"error": "Missing 'terabox_url' query parameter"}, 400

    # Construct the full URL for the target API
    target_url = f"{TARGET_API_BASE_URL}{terabox_video_url}"

    try:
        # Make the request to the target API
        # We'll stream the response to handle potentially large files efficiently
        # and pass through headers like Content-Type.
        
        headers = {key: value for (key, value) in request.headers if key.lower() == 'user-agent'}
        
        external_response = requests.get(target_url, headers=headers, stream=True, timeout=30) # 30 second timeout
        external_response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        # Create a Flask response object, streaming the content
        # and copying relevant headers from the external response.
        response = Response(
            external_response.iter_content(chunk_size=8192), # Stream content in chunks
            status=external_response.status_code,
            content_type=external_response.headers.get('Content-Type')
        )
        
        # Optionally copy other headers you might need
        # For example, Content-Disposition if the target API sets it for downloads
        if 'Content-Disposition' in external_response.headers:
            response.headers['Content-Disposition'] = external_response.headers['Content-Disposition']
        if 'Content-Length' in external_response.headers:
            response.headers['Content-Length'] = external_response.headers['Content-Length']
            
        return response

    except requests.exceptions.Timeout:
        return {"error": "The request to the target API timed out"}, 504 # Gateway Timeout
    except requests.exceptions.HTTPError as e:
        # Try to return the error from the external API if possible
        try:
            error_content = e.response.json()
        except ValueError: # Not JSON
            error_content = e.response.text
        return {"error": "Target API returned an error", "status_code": e.response.status_code, "details": error_content}, e.response.status_code
    except requests.exceptions.RequestException as e:
        # For other network errors (DNS failure, connection refused, etc.)
        return {"error": f"Could not connect to target API: {str(e)}"}, 502 # Bad Gateway
    except Exception as e:
        # Catch-all for any other unexpected errors
        app.logger.error(f"An unexpected error occurred: {str(e)}")
        return {"error": "An internal server error occurred"}, 500

# This is for local development testing (e.g., python api/index.py)
# Vercel will use a WSGI server like Gunicorn and won't run this directly.
if __name__ == '__main__':
    # When running locally, Flask's development server will listen on port 5000 by default.
    # Vercel assigns a port automatically.
    port = int(os.environ.get('PORT', 5000)) 
    app.run(host='0.0.0.0', port=port, debug=True)
