# How to Create a Public API URL

There are two main ways to make your local API accessible via a public URL: **Tunneling** (for temporary testing) and **Deployment** (for permanent access).

## Option 1: Tunneling with ngrok (Recommended for Dev)
Use this if you want to quickly show your running local app to someone or test it from another device.

1.  **Download ngrok**: Go to [ngrok.com](https://ngrok.com/download) and sign up/download.
2.  **Authenticate**: Run the command provided on your dashboard:
    ```bash
    ngrok config add-authtoken <your-token>
    ```
3.  **Start your API**: ensure your FastAPI app is running on a port (e.g., 8000).
    ```bash
    uvicorn main:app --reload --port 8000
    ```
4.  **Start the tunnel**:
    ```bash
    ngrok http 8000
    ```
5.  **Result**: ngrok will give you a URL like `https://1234-56-78.ngrok-free.app` that points to your localhost.

## Option 2: Localtunnel (Free, no account needed)
A quick alternative using Node.js.

1.  **Start your API** locally on port 8000.
2.  **Run with npx**:
    ```bash
    npx localtunnel --port 8000
    ```
3.  **Result**: You'll get a URL like `https://floppy-donkey-45.loca.lt`.
    *Note: You might need to enter a password (your public IP) on the first visit for security.*

## Option 3: Production Deployment
For a permanent URL that stays online even when your computer is off.

### Using Render (Free Tier available)
1.  Push your code to **GitHub**.
2.  Sign up at [render.com](https://render.com).
3.  Click "New +", select **Web Service**.
4.  Connect your GitHub repo.
5.  **Settings**:
    *   **Runtime**: Python 3
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6.  Click **Create Web Service**. Render will build it and give you a URL like `https://your-app.onrender.com`.
