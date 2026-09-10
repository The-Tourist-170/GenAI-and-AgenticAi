from server import app
import uvicorn

def main():
    uvicorn.run(app, host="0.0.0.0", port=8080)

main()
