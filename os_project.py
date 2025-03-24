import os
import sys
import re
import threading
from socket import *
import webbrowser
from hashlib import md5
from datetime import datetime
from urllib.parse import urlparse

# Global constants
DEFAULT_PORT = 8080
CACHE_FOLDER = "cache/"
LOG_FILE = "log.txt"

class ProxyServer:
    def __init__(self, port):
        """Initialize the proxy server."""
        try:
            self.server_socket = socket(AF_INET, SOCK_STREAM)
            self.server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.server_socket.bind(('', port))
            self.server_socket.listen(10)
            print(f"Proxy server is listening on port {port}")
            self.log(f"Proxy server started on port {port}")
        except Exception as e:
            print(f"Error initializing server: {e}")
            self.log(f"Error initializing server: {e}")
            sys.exit(1)

    def log(self, message):
        """Log messages to a file."""
        with open(LOG_FILE, "a") as log_file:
            log_file.write(f"{datetime.now()}: {message}\n")

    def handle_client(self, client_socket, client_address):
        """Handle individual client connections."""
        try:
            request = client_socket.recv(1024).decode()
            if not request:
                return
            print(f"Request received from {client_address}: {request.splitlines()[0]}")
            self.log(f"Request received from {client_address}: {request.splitlines()[0]}")

            # Parse the client request
            first_line = request.splitlines()[0]
            if first_line.startswith("GET"):
                url = first_line.split(" ")[1]

                # Add protocol if missing
                if not url.startswith("http://") and not url.startswith("https://"):
                    url = "http://" + url

                # Extract host and path
                url_components = url.split("//")[1].split("/", 1)
                host = url_components[0]
                path = "/" + url_components[1] if len(url_components) > 1 else "/"

                # Hash the URL for consistent caching
                url_hash = md5(url.encode()).hexdigest()
                cached_file = CACHE_FOLDER + url_hash

                # Check cache
                if self.serve_from_cache(cached_file, client_socket):
                    return

                # Fetch from target server
                self.fetch_from_server(host, path, cached_file, client_socket)
            else:
                response = "HTTP/1.1 400 Bad Request\r\n\r\n"
                client_socket.sendall(response.encode())
        except Exception as e:
            print(f"Error handling client: {e}")
            self.log(f"Error handling client: {e}")
        finally:
            client_socket.close()

    def serve_from_cache(self, cached_file, client_socket):
        """Serve content from the cache if available."""
        try:
            with open(cached_file, "rb") as file:
                response = file.read()
                client_socket.sendall(response)
                print(f"Served from cache: {cached_file}")
                self.log(f"Served from cache: {cached_file}")
                return True
        except FileNotFoundError:
            return False

    def fetch_from_server(self, host, path, cached_file, client_socket):
        """Fetch content from the target server."""
        try:
            server_socket = socket(AF_INET, SOCK_STREAM)
            server_socket.connect((host, 80))
            request_line = f"GET {path} HTTP/1.1\r\nHost: {host}\r\n\r\n"
            server_socket.sendall(request_line.encode())
            response = b""

            # Receive the response from the server
            while True:
                data = server_socket.recv(4096)
                if not data:
                    break
                response += data

            # Split HTTP headers and body
            headers, _, body = response.partition(b"\r\n\r\n")

            # Cache the full response
            with open(cached_file, "wb") as file:
                file.write(response)

            # Save HTML content to a file
            if b"text/html" in headers:  # Check if response is HTML
                self.save_html_content(body, host)

            # Send the response to the client
            client_socket.sendall(response)
            print(f"Fetched from server and cached: {host}{path}")
            self.log(f"Fetched from server and cached: {host}{path}")
        except Exception as e:
            print(f"Error fetching from server: {e}")
            self.log(f"Error fetching from server: {e}")
            response = "HTTP/1.1 502 Bad Gateway\r\n\r\n"
            client_socket.sendall(response.encode())
        finally:
            server_socket.close()

    def save_html_content(self, html_content, host):
        """Save the HTML content to a file."""
        try:
            # Generate a filename using the domain name and a timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{host}_{timestamp}.html"
            filepath = os.path.join(CACHE_FOLDER, filename)

            # Save the HTML content to the file
            with open(filepath, "wb") as file:
                file.write(html_content)
            print(f"Saved HTML content to: {filepath}")
            self.log(f"Saved HTML content to: {filepath}")
        except Exception as e:
            print(f"Error saving HTML content: {e}")
            self.log(f"Error saving HTML content: {e}")

    def start(self):
        """Start listening for client connections."""
        while True:
            client_socket, client_address = self.server_socket.accept()
            print(f"Connection established with {client_address}")
            self.log(f"Connection established with {client_address}")

            # Handle each client in a new thread
            threading.Thread(target=self.handle_client, args=(client_socket, client_address)).start()

def open_urls_and_save_to_html():
    """Open multiple user-provided URLs in new browser tabs, then save them to an HTML file."""
    while True:
        user_input = input("Enter URLs to open in new browser tabs (separated by spaces or commas, or type 'exit' to quit): ").strip()
        if user_input.lower() == 'exit':
            print("Exiting the program.")
            break

        # Clean and split the input into individual URLs
        urls = re.split(r'[ ,;]+', user_input)  # Split by spaces, commas, or semicolons
        urls = [url.strip() for url in urls if url]  # Remove empty entries

        if not urls:
            print("No valid URLs provided. Please try again.")
            continue

        # Ensure each URL has the correct protocol and open it in a browser tab
        for url in urls:
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "http://" + url

            try:
                print(f"Opening URL: {url}")
                webbrowser.open_new_tab(url)  # Open the URL in a new tab
            except Exception as e:
                print(f"Error opening URL '{url}': {e}")

        # After opening URLs, save them to an HTML file
        save_urls_to_html_with_names(urls)
        print("URLs have been opened and saved to an HTML file.\n")

def save_urls_to_html_with_names(urls):
    """Create an HTML file with clickable links for the provided URLs with descriptive names."""
    if not urls:
        print("No URLs to save.")
        return

    html_filename = "links_with_names.html"
    with open(html_filename, 'w') as file:
        file.write("<html>\n")
        file.write("<head><title>Clickable Links</title></head>\n")
        file.write("<body>\n")
        file.write("<h1>Click on the links below:</h1>\n")

        for url in urls:
            parsed_url = urlparse(url)
            name = parsed_url.netloc or "Unknown"
            file.write(f'<a href="{url}" target="_blank">{name}</a><br>\n')

        file.write("</body>\n")
        file.write("</html>\n")

    print(f"HTML file created: {html_filename}")
    webbrowser.open(html_filename)

if __name__ == "__main__":
    # Ensure the cache folder exists
    if not os.path.exists(CACHE_FOLDER):
        os.makedirs(CACHE_FOLDER)

    # Start the proxy server in a separate thread
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    proxy_server = ProxyServer(port)
    threading.Thread(target=proxy_server.start, daemon=True).start()

    # Open URLs first and then save them to an HTML file
    open_urls_and_save_to_html()


