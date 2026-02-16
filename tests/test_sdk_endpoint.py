import urllib.request
import urllib.parse
import json
import cv2
import numpy as np
import io
import uuid

def create_dummy_image(color=(0, 0, 0)):
    """Create a 100x100 dummy image."""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:] = color
    _, encoded = cv2.imencode('.jpg', img)
    return encoded.tobytes()

def test_sdk_verify_endpoint():
    print("Testing SDK Verify Endpoint...")
    url = "http://localhost:8000/api/v1/sdk/verify"
    
    # Create dummy images
    id_front_bytes = create_dummy_image((255, 255, 255))
    id_back_bytes = create_dummy_image((200, 200, 200))
    selfie_bytes = create_dummy_image((100, 100, 100))
    
    boundary = '----WebKitFormBoundary' + uuid.uuid4().hex
    data = []
    
    # Helper to add file part
    def add_file(name, filename, content):
        data.append(f'--{boundary}'.encode())
        data.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode())
        data.append('Content-Type: image/jpeg'.encode())
        data.append(''.encode())
        data.append(content)
        data.append(''.encode())

    add_file("id_front", "front.jpg", id_front_bytes)
    add_file("id_back", "back.jpg", id_back_bytes)
    add_file("selfie", "selfie.jpg", selfie_bytes)
    
    data.append(f'--{boundary}--'.encode())
    data.append(''.encode())
    
    body = b'\r\n'.join(data)
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Content-Length': str(len(body))
    }
    
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_body = response.read().decode('utf-8')
            
            print(f"Status Code: {status_code}")
            print("Response JSON:")
            print(response_body)
            
            if status_code == 200:
                data = json.loads(response_body)
                if not data["success"]:
                     print("\nSUCCESS: Endpoint is reachable and returned expected validation failure (dummy images).")
                else:
                     print("\nUNEXPECTED SUCCESS: Dummy images should have failed!")
            else:
                print("\nFAILURE: Endpoint returned non-200 status.")
                
    except urllib.error.URLError as e:
        print(f"\nERROR: Could not connect to server. Is it running? {e}")
    except urllib.error.HTTPError as e:
        print(f"\nHTTP ERROR: {e.code} - {e.reason}")
        print(e.read().decode('utf-8'))

if __name__ == "__main__":
    test_sdk_verify_endpoint()
