import os
import subprocess
from flask import Flask, request, jsonify
from threading import Thread

app = Flask(__name__)

# Start LocalTunnel in a separate thread to avoid blocking
def start_localtunnel():
    result = subprocess.run(
        ["lt", "--port", "5000"], capture_output=True, text=True
    )
    output = result.stdout
    if result.returncode == 0:
        print(f"LocalTunnel public URL: {output.strip()}")
        with open("localtunnel_url.txt", "w") as file:
            file.write(output.strip())
        print("LocalTunnel public URL saved to localtunnel_url.txt")
    else:
        print(f"Error starting LocalTunnel: {result.stderr}")

# Start LocalTunnel on a separate thread
tunnel_thread = Thread(target=start_localtunnel)
tunnel_thread.start()

@app.route('/run_Spike', methods=['POST'])
def run_spike():
    # Extract parameters from JSON request
    data = request.get_json()
    ip = data.get("ip")
    port = data.get("port")
    duration = data.get("time")
    packet_size = data.get("packet_size")
    threads = data.get("threads")

    # Validate inputs
    if not (ip and port and duration and packet_size and threads):
        return jsonify({"error": "Missing required parameters (ip, port, time, packet_size, threads)"}), 400

    try:
        # Run the Spike binary with provided parameters
        result = subprocess.run(
            ["./Spike", ip, str(port), str(duration), str(packet_size), str(threads)],
            capture_output=True, text=True
        )

        # Capture stdout and stderr
        output = result.stdout
        error = result.stderr
        return jsonify({"output": output, "error": error})

    except Exception as e:
        return jsonify({"error": f"Failed to run Spike: {str(e)}"}), 500

if __name__ == '__main__':
    print("Server running on local port 5000")
    app.run(port=5000)
    